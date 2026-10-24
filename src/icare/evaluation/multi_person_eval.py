"""Multi-person evaluation on composite videos built from real recordings.

    python -m icare.evaluation.multi_person_eval --fall-clip FALL.mp4 --normal-clip NORMAL.mp4

Each scenario tiles real footage (a person falling, walking, standing still or
lying) into one frame with known per-tile labels and fall onsets, runs the real
engine, and scores per-person events. Composites test tracking, isolation and
per-person event logic with the real models; they are not a substitute for
labelled recordings of real multi-person scenes. Clip-specific annotations
(``FALL_ONSET``, ``WALK_END``, ``CROP``) describe the fall clip used during
development, a 6 s montage: one person walks until about 4.25 s, a cross-dissolve
follows, and a second person falls from about 4.7 s. Pass your own values for
other clips. Outputs go to ignored artifacts/.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import threading

import cv2
import numpy as np

from icare.api.incidents import PersonIncidents
from icare.inference.engine import PoseC3DEngine, load_engine

FPS = 12.0
TILE = (768, 720)          # width, height of one person's tile
EVENT_WINDOW = 3.0         # an incident within this many seconds of onset is a detection


@dataclass(frozen=True)
class Tile:
    kind: str              # fall | walk | stand | lying | empty
    offset: float = 0.0    # seconds of static first frame before the content starts
    mirror: bool = False
    occlude: tuple[float, float] | None = None  # (start, end) of a grey occluder


@dataclass(frozen=True)
class Scenario:
    name: str
    description: str
    columns: int
    tiles: tuple[Tile, ...]
    duration: float


def scenarios() -> list[Scenario]:
    F, W, S, L, E = (lambda **k: Tile("fall", **k)), (lambda **k: Tile("walk", **k)), Tile("stand"), Tile("lying"), Tile("empty")
    return [
        Scenario("fall_with_walker", "One falls while another walks", 2, (F(), W()), 6.0),
        Scenario("fall_with_lying_person", "One falls; another is lying from the start", 2, (F(), L), 6.0),
        Scenario("two_simultaneous_falls", "Two people fall at the same time", 2, (F(), F(mirror=True)), 6.0),
        # The development fall clip is a montage: the falling person appears only
        # 1.5 s before it ends, too briefly for a 2 s window if the video stops
        # there. These variants keep them lying on the floor for 3 s more.
        Scenario("two_simultaneous_falls_then_lying", "Two people fall together, then stay down", 2,
                 (F(), F(mirror=True)), 9.0),
        Scenario("two_consecutive_falls", "Second person falls 4 s after the first", 2, (F(), F(offset=4.0, mirror=True)), 10.0),
        Scenario("five_people_one_fall", "Five people; one falls, others walk, stand or lie", 3,
                 (F(offset=1.0), W(), S, L, W(offset=1.5, mirror=True), E), 8.0),
        Scenario("five_people_no_fall", "Five people walking, standing or lying; nobody falls", 3,
                 (W(), S, L, W(offset=1.5, mirror=True), Tile("stand", mirror=True), E), 8.0),
        Scenario("four_rapid_falls", "Four falls 0.5 s apart", 3,
                 (F(), F(offset=0.5, mirror=True), F(offset=1.0), F(offset=1.5, mirror=True), E, E), 8.0),
        Scenario("four_rapid_falls_then_lying", "Four falls 0.5 s apart, then everyone stays down", 3,
                 (F(), F(offset=0.5, mirror=True), F(offset=1.0), F(offset=1.5, mirror=True), E, E), 11.0),
        Scenario("fall_at_end", "Fall in the last 1.5 s of the clip", 2, (W(), F(offset=4.5)), 10.7),
        Scenario("occluded_before_fall", "Faller hidden for 0.6 s just before falling", 2, (F(occlude=(3.0, 3.6)), W()), 6.0),
        Scenario("long_four_falls", "30 s, four falls at different times", 3,
                 (F(), F(offset=8.0, mirror=True), F(offset=16.0), F(offset=23.0, mirror=True), W(), S), 30.0),
    ]


class Sources:
    def __init__(self, fall_clip: Path, crop: tuple[int, int], walk_end: float):
        capture = cv2.VideoCapture(str(fall_clip))
        fps = capture.get(cv2.CAP_PROP_FPS)
        frames = []
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            frames.append(cv2.resize(frame[:, crop[0]:crop[1]], TILE, interpolation=cv2.INTER_AREA))
        capture.release()
        if not frames:
            raise SystemExit(f"Could not read {fall_clip}")
        self.fps, self.frames = fps, frames
        self.fall_seconds = len(frames) / fps
        walk = frames[:int(walk_end * fps)]
        self.walk = walk + walk[::-1]           # ping-pong keeps the walk continuous
        self.blank = np.full_like(frames[0], 114)

    def frame(self, tile: Tile, t: float) -> np.ndarray:
        local = t - tile.offset
        if tile.kind == "empty":
            image = self.blank
        elif tile.kind == "stand":
            image = self.frames[0]
        elif tile.kind == "lying":
            image = self.frames[-1]
        elif tile.kind == "fall":
            image = self.frames[min(max(int(local * self.fps), 0), len(self.frames) - 1)]
        else:
            image = self.walk[max(int(local * self.fps), 0) % len(self.walk)]
        image = image[:, ::-1] if tile.mirror else image
        if tile.occlude and tile.occlude[0] <= t < tile.occlude[1]:
            image = image.copy()
            image[60:-60, 140:-140] = 128
        return image


def render(scenario: Scenario, sources: Sources, path: Path) -> None:
    rows = int(np.ceil(len(scenario.tiles) / scenario.columns))
    size = (TILE[0] * scenario.columns, TILE[1] * rows)
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), FPS, size)
    if not writer.isOpened():
        raise SystemExit("OpenCV cannot write MP4 here")
    for index in range(int(round(scenario.duration * FPS))):
        t = index / FPS
        canvas = np.full((size[1], size[0], 3), 114, dtype=np.uint8)
        for position, tile in enumerate(scenario.tiles):
            r, c = divmod(position, scenario.columns)
            canvas[r * TILE[1]:(r + 1) * TILE[1], c * TILE[0]:(c + 1) * TILE[0]] = sources.frame(tile, t)
        writer.write(canvas)
    writer.release()


class LargestOnly:
    """The pre-tracking behaviour: only the largest person enters the pipeline."""

    def __init__(self, extractor):
        self.extractor, self.model_version = extractor, extractor.model_version

    def fork(self):
        return self

    def extract_all(self, frame, t):
        return self.extractor.extract_all(frame, t)[:1]


def analyse(engine: PoseC3DEngine, video: Path, confirmations: int, legacy: bool) -> dict:
    poses, predictions, incidents = [], [], []
    book = PersonIncidents(confirmations)

    def on_prediction(record):
        predictions.append(record)
        person = 0 if legacy else record["track_id"]
        if book.observe(person, record["fall_probability"]):
            incidents.append({"track_id": record["track_id"], "t": record["timestamp_seconds"],
                              "p": record["fall_probability"]})

    summary = engine.analyze_video(video, on_pose=poses.append, on_prediction=on_prediction,
                                   on_progress=lambda _: None, cancel_event=threading.Event())
    return {"summary": summary, "poses": poses, "predictions": predictions, "incidents": incidents}


def score(scenario: Scenario, run: dict, fall_onset: float) -> dict:
    columns = scenario.columns

    def tile_of(bbox):
        cx, cy = (bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2
        return int(cy // TILE[1]) * columns + int(cx // TILE[0])

    per_track: dict[int, list[int]] = {}
    tile_frames: dict[int, dict[float, set]] = {}
    for pose in run["poses"]:
        tile = tile_of(pose["bbox_xyxy"])
        per_track.setdefault(pose["track_id"], []).append(tile)
        tile_frames.setdefault(tile, {}).setdefault(pose["timestamp_seconds"], set()).add(pose["track_id"])
    track_tile = {tid: max(set(tiles), key=tiles.count) for tid, tiles in per_track.items()}

    sampled = sorted({round(i / 6, 6) for i in range(int(scenario.duration * 6))})
    tiles = []
    for position, tile in enumerate(scenario.tiles):
        frames = tile_frames.get(position, {})
        ids = [min(frames[t]) for t in sampled if t in frames]
        tiles.append({"tile": position, "kind": tile.kind,
                      "detected_fraction": round(len(frames) / len(sampled), 3),
                      "track_ids": sorted({tid for ids_at in frames.values() for tid in ids_at}),
                      "id_switches": sum(1 for a, b in zip(ids, ids[1:]) if a != b)})

    expected = [(position, tile.offset + fall_onset) for position, tile in enumerate(scenario.tiles)
                if tile.kind == "fall" and tile.offset + fall_onset < scenario.duration]
    matched, latencies, false_positives, duplicates = set(), [], [], 0
    for incident in run["incidents"]:
        tile = track_tile.get(incident["track_id"]) if incident["track_id"] is not None else None
        hit = next((i for i, (position, onset) in enumerate(expected)
                    if (tile == position or tile is None) and onset <= incident["t"] <= onset + EVENT_WINDOW), None)
        if hit is None:
            false_positives.append(incident)
        elif hit in matched:
            duplicates += 1
        else:
            matched.add(hit)
            latencies.append(round(incident["t"] - expected[hit][1], 3))
    return {"expected_falls": len(expected), "detected_falls": len(matched),
            "missed_falls": len(expected) - len(matched), "false_alarms": len(false_positives),
            "duplicate_alerts": duplicates, "latency_seconds": latencies,
            "incidents": run["incidents"], "tiles": tiles,
            "people_tracked": run["summary"]["metrics"].get("people_tracked"),
            "max_people_in_frame": run["summary"]["metrics"].get("max_people_in_frame"),
            "engine_seconds": run["summary"]["metrics"].get("engine_wall_seconds")}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--fall-clip", type=Path, required=True)
    parser.add_argument("--normal-clip", type=Path, required=True)
    parser.add_argument("--fall-onset", type=float, default=4.7, help="annotated onset in the fall clip (s)")
    parser.add_argument("--walk-end", type=float, default=4.2, help="last second of walking before the cut")
    parser.add_argument("--crop", type=int, nargs=2, default=(240, 1008), help="x range of the people")
    parser.add_argument("--confirmations", type=int, default=1)
    parser.add_argument("--output", type=Path, default=Path("artifacts/multi_person_eval"))
    args = parser.parse_args(argv)
    args.output.mkdir(parents=True, exist_ok=True)

    sources = Sources(args.fall_clip, tuple(args.crop), args.walk_end)
    engine = load_engine({"model_path": "models/posec3d_fall.onnx"})
    legacy = PoseC3DEngine(engine.config, LargestOnly(engine._extractor), engine._classifier,
                           **engine._buffer_settings)
    report = {"fall_onset": args.fall_onset, "confirmations": args.confirmations,
              "model_version": engine.model_version, "scenarios": []}
    try:
        solo = [("solo_fall", "Original fall clip, one person", args.fall_clip, args.fall_onset),
                ("solo_walk_far", "Original small, distant walker; no fall", args.normal_clip, None)]
        for name, description, path, onset in solo:
            for mode, active in (("tracked", engine), ("legacy", legacy)):
                run = analyse(active, path, args.confirmations, mode == "legacy")
                expected = 1 if onset is not None else 0
                hits = [i for i in run["incidents"] if onset is not None and onset <= i["t"] <= onset + EVENT_WINDOW]
                report["scenarios"].append({"name": name, "description": description, "mode": mode,
                    "expected_falls": expected, "detected_falls": min(len(hits), expected),
                    "missed_falls": expected - min(len(hits), expected),
                    "false_alarms": len(run["incidents"]) - len(hits), "duplicate_alerts": max(len(hits) - 1, 0),
                    "latency_seconds": [round(hits[0]["t"] - onset, 3)] if hits else [],
                    "incidents": run["incidents"],
                    "people_tracked": run["summary"]["metrics"].get("people_tracked")})
        for scenario in scenarios():
            video = args.output / f"{scenario.name}.mp4"
            render(scenario, sources, video)
            for mode, active in (("tracked", engine), ("legacy", legacy)):
                run = analyse(active, video, args.confirmations, mode == "legacy")
                report["scenarios"].append({"name": scenario.name, "description": scenario.description,
                                            "mode": mode, **score(scenario, run, args.fall_onset)})
                print(f"{scenario.name:24} {mode:8} falls {report['scenarios'][-1]['detected_falls']}"
                      f"/{report['scenarios'][-1]['expected_falls']}  false alarms {report['scenarios'][-1]['false_alarms']}")
    finally:
        engine.close()

    for mode in ("tracked", "legacy"):
        rows = [s for s in report["scenarios"] if s["mode"] == mode]
        expected = sum(s["expected_falls"] for s in rows)
        detected = sum(s["detected_falls"] for s in rows)
        alarms = sum(s["false_alarms"] + s["duplicate_alerts"] for s in rows)
        latencies = [x for s in rows for x in s["latency_seconds"]]
        report[f"totals_{mode}"] = {
            "fall_recall": round(detected / expected, 3) if expected else None,
            "fall_precision": round(detected / (detected + alarms), 3) if detected + alarms else None,
            "expected_falls": expected, "detected_falls": detected, "false_or_duplicate_alerts": alarms,
            "median_latency_seconds": float(np.median(latencies)) if latencies else None,
            "max_latency_seconds": max(latencies) if latencies else None}
    (args.output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k.startswith("totals")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Run the real models on videos and score behaviour events against expected labels.

    python -m icare.evaluation.behaviour_eval --out artifacts/behaviour_eval \\
        --fall-clip F.mp4 --walk-clip W.mp4 --still-clip S.mp4 [--negatives N1.mp4 ...]

Real recordings of pacing, long stillness and long lies were not available, so
positives are assembled from real footage: a walker's continuous track played
forwards and backwards (pacing), a motionless person looped the same way (no
movement), and a real fall followed by its final frame held (still down). The
poses and fall predictions all come from the real YOLO26n-pose + PoseC3D models.
Negatives are the listed videos unchanged, which must produce no event. These
test the rules on real pose estimates; they are not an accuracy measurement on
real care-home behaviour.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from time import perf_counter

import numpy as np

from icare.api.incidents import PersonIncidents
from icare.inference.behaviour import BehaviourMonitor, BehaviourSettings


def _read(path: Path):
    import cv2

    capture = cv2.VideoCapture(str(path))
    fps = capture.get(cv2.CAP_PROP_FPS)
    frames = []
    while True:
        ok, frame = capture.read()
        if not ok:
            break
        frames.append(frame)
    capture.release()
    if not frames or not fps:
        raise ValueError(f"Could not read {path}")
    return frames, float(fps)


def _duration(path: Path) -> float:
    import cv2

    capture = cv2.VideoCapture(str(path))
    try:
        return round(capture.get(cv2.CAP_PROP_FRAME_COUNT) / max(capture.get(cv2.CAP_PROP_FPS), 1e-6), 3)
    finally:
        capture.release()


def _write(path: Path, frames, fps: float) -> Path:
    import cv2

    height, width = frames[0].shape[:2]
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))
    for frame in frames:
        writer.write(frame)
    writer.release()
    return path


def ping_pong(source: Path, target: Path, seconds: float, start: float = 0.0, end: float | None = None) -> Path:
    """Play [start, end] of ``source`` forwards then backwards until ``seconds`` long."""
    frames, fps = _read(source)
    segment = frames[int(start * fps):int(end * fps) if end else None]
    cycle = segment + segment[-2:0:-1]
    count = int(seconds * fps)
    return _write(target, [cycle[i % len(cycle)] for i in range(count)], fps)


def hold_end(source: Path, target: Path, hold_seconds: float) -> Path:
    """``source`` followed by its final frame held for ``hold_seconds``."""
    frames, fps = _read(source)
    return _write(target, frames + [frames[-1]] * int(hold_seconds * fps), fps)


def visible_span(engine, path: Path) -> tuple[float, float]:
    """Start/end of the longest continuous track (gaps <= 0.5 s) of the first person."""
    poses = []
    engine.analyze_video(path, on_pose=poses.append, on_prediction=lambda _: None, on_progress=lambda _: None)
    times = sorted(p["timestamp_seconds"] for p in poses if p["track_id"] == 1)
    best, start = (0.0, 0.0), times[0]
    for previous, current in zip(times, times[1:] + [float("inf")]):
        if current - previous > 0.5:
            if previous - start > best[1] - best[0]:
                best = (start, previous)
            start = current
    return best


def analyse(engine, path: Path, settings: BehaviourSettings) -> dict:
    """Engine poses and predictions → falls (API incident rule) → behaviour events."""
    monitor = BehaviourMonitor(settings)
    incidents = PersonIncidents()
    falls, cost = [], [0.0, 0]

    def on_pose(pose):
        started = perf_counter()
        monitor.observe(pose)
        cost[0] += perf_counter() - started
        cost[1] += 1

    def on_prediction(prediction):
        if incidents.observe(prediction["track_id"] or 0, prediction["fall_probability"]):
            falls.append(prediction["timestamp_seconds"])
            monitor.note_fall(prediction["track_id"], prediction["timestamp_seconds"])

    from icare.inference.engine import EngineError

    try:
        summary = engine.analyze_video(path, on_pose=on_pose, on_prediction=on_prediction,
                                       on_progress=lambda _: None)
        duration, error = summary["duration_seconds"], None
    except EngineError as exc:  # e.g. too short for PoseC3D; the poses were still observed
        duration, error = _duration(path), exc.code
    monitor.finish()
    return {"video": path.name, "duration_seconds": duration, "engine_error": error, "falls": falls,
            "events": monitor.events, "pose_records": cost[1],
            "monitor_us_per_pose": round(1e6 * cost[0] / max(cost[1], 1), 1)}


def score(result: dict, expected: list[str]) -> dict:
    found = [event["event_type"] for event in result["events"]]
    missed = [kind for kind in expected if kind not in found]
    false = [event for event in result["events"] if event["event_type"] not in expected]
    delays = {event["event_type"]: round(event["detected_at_seconds"] - event["start_seconds"], 2)
              for event in result["events"] if event["event_type"] in expected}
    return {**result, "expected": expected, "missed": missed, "false_alerts": len(false), "delay_seconds": delays}


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--fall-clip", type=Path, required=True, help="a real fall that ends lying down")
    parser.add_argument("--walk-clip", type=Path, required=True, help="one person walking across the view")
    parser.add_argument("--still-clip", type=Path, required=True, help="one person standing motionless")
    parser.add_argument("--negatives", type=Path, nargs="*", default=[], help="ordinary videos: no event expected")
    parser.add_argument("--inactivity-seconds", type=float, default=BehaviourSettings.inactivity_seconds)
    parser.add_argument("--long-lie-seconds", type=float, default=BehaviourSettings.long_lie_seconds)
    parser.add_argument("--pacing-turns", type=int, default=BehaviourSettings.pacing_reversals)
    args = parser.parse_args(argv)

    from icare.inference.engine import load_engine

    settings = BehaviourSettings(inactivity_seconds=args.inactivity_seconds,
                                 long_lie_seconds=args.long_lie_seconds, pacing_reversals=args.pacing_turns)
    args.out.mkdir(parents=True, exist_ok=True)
    engine = load_engine({"model_path": "models/posec3d_fall.onnx"})
    try:
        start, end = visible_span(engine, args.walk_clip)
        legs = args.pacing_turns + 2
        scenarios = [
            (ping_pong(args.walk_clip, args.out / "pacing.mp4", (end - start) * legs, start, end), ["pacing"]),
            (ping_pong(args.still_clip, args.out / "no_movement.mp4", args.inactivity_seconds + 20),
             ["prolonged_inactivity"]),
            (hold_end(args.fall_clip, args.out / "still_down_after_fall.mp4", args.long_lie_seconds + 15),
             ["long_lie"]),
            # Same footage too short to qualify: nothing may fire early.
            (ping_pong(args.still_clip, args.out / "short_stillness.mp4", args.inactivity_seconds * 0.6), []),
            (hold_end(args.fall_clip, args.out / "short_lie_after_fall.mp4", args.long_lie_seconds * 0.6), []),
            *[(path, []) for path in args.negatives],
        ]
        report = [score(analyse(engine, path, settings), expected) for path, expected in scenarios]
    finally:
        engine.close()

    hours = sum(r["duration_seconds"] for r in report if not r["expected"]) / 3600
    totals = {
        "settings": {"inactivity_seconds": settings.inactivity_seconds,
                     "long_lie_seconds": settings.long_lie_seconds, "pacing_turns": settings.pacing_reversals},
        "positives_detected": sum(not r["missed"] for r in report if r["expected"]),
        "positives": sum(bool(r["expected"]) for r in report),
        "false_alerts": sum(r["false_alerts"] for r in report),
        "negative_video_hours": round(hours, 4),
        "monitor_us_per_pose_max": max(r["monitor_us_per_pose"] for r in report),
        "videos": report,
    }
    (args.out / "report.json").write_text(json.dumps(totals, indent=2))
    for r in report:
        print(f"{r['video'][:40]:40} {r['duration_seconds']:7.1f}s expected={r['expected'] or '-'} "
              f"found={[e['event_type'] for e in r['events']] or '-'} delay={r['delay_seconds'] or '-'}")
    print(f"positives {totals['positives_detected']}/{totals['positives']}, false alerts {totals['false_alerts']} "
          f"in {hours * 60:.1f} min of negatives; monitor ≤ {totals['monitor_us_per_pose_max']} µs per pose")


if __name__ == "__main__":
    main()

from __future__ import annotations

import argparse
import csv
from pathlib import Path

from icare_app.pose_signals import PoseSignalEstimator


VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".mpeg", ".mpg", ".m4v"}
TRACE_FIELDS = [
    "video",
    "label",
    "timestamp_seconds",
    "urgency",
    "reliability",
    "downward_velocity",
    "torso_rotation_rate",
    "joint_motion_rate",
    "bbox_aspect_change_rate",
    "mean_keypoint_confidence",
    "visible_joint_fraction",
    "torso_visibility",
    "temporal_stability",
    "frame_containment",
]


def collect_videos(
    directories: list[Path], explicit: list[Path], limit: int
) -> list[Path]:
    candidates = [path for path in explicit if path.suffix.lower() in VIDEO_EXTENSIONS]
    for directory in directories:
        candidates.extend(
            path
            for path in sorted(directory.rglob("*"))
            if path.suffix.lower() in VIDEO_EXTENSIONS
        )
    unique = list(dict.fromkeys(path.resolve() for path in candidates if path.exists()))
    return unique[:limit]


def analyze_video(
    video: Path,
    label: str,
    extractor,
    target_fps: float,
) -> list[dict]:
    import cv2

    capture = cv2.VideoCapture(str(video))
    if not capture.isOpened():
        raise RuntimeError(f"Could not open {video}")
    source_fps = capture.get(cv2.CAP_PROP_FPS)
    source_fps = source_fps if source_fps and source_fps > 0 else 30.0
    frame_step = max(1, round(source_fps / target_fps))
    estimator = PoseSignalEstimator()
    extractor.reset()
    rows: list[dict] = []
    frame_index = 0
    while True:
        ok, frame_bgr = capture.read()
        if not ok:
            break
        if frame_index % frame_step:
            frame_index += 1
            continue
        timestamp = frame_index / source_fps
        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        pose = extractor.extract(frame_rgb, timestamp)
        if pose is not None:
            signals = estimator.update(pose).as_dict()
            rows.append({"video": video.name, "label": label, **signals})
        frame_index += 1
    capture.release()
    return rows


def save_plot(rows: list[dict], output: Path) -> None:
    try:
        import matplotlib.pyplot as plt
    except ImportError as exc:
        raise RuntimeError("Install requirements.txt to create urgency plots.") from exc

    groups: dict[tuple[str, str], list[dict]] = {}
    for row in rows:
        groups.setdefault((row["label"], row["video"]), []).append(row)
    items = list(groups.items())
    columns = 4
    row_count = max(1, (len(items) + columns - 1) // columns)
    figure, axes = plt.subplots(
        row_count, columns, figsize=(16, 3.2 * row_count), squeeze=False
    )
    for axis, ((label, name), trace) in zip(axes.flat, items):
        times = [row["timestamp_seconds"] for row in trace]
        urgency = [row["urgency"] for row in trace]
        reliability = [row["reliability"] for row in trace]
        axis.plot(times, urgency, color="#d1495b", label="Urgency", linewidth=2)
        axis.plot(
            times,
            reliability,
            color="#2a9d8f",
            label="Reliability",
            linewidth=1.5,
            alpha=0.8,
        )
        axis.set_ylim(0, 1.05)
        axis.set_title(f"{label}: {name}", fontsize=9)
        axis.set_xlabel("Time (s)")
        axis.grid(alpha=0.25)
    for axis in axes.flat[len(items) :]:
        axis.axis("off")
    if items:
        axes.flat[0].legend(loc="upper right", fontsize=8)
    figure.suptitle("ICare motion urgency and pose reliability", fontsize=16)
    figure.tight_layout()
    output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output, dpi=160, bbox_inches="tight")
    plt.close(figure)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Plot urgency and reliability for fall and non-fall videos."
    )
    parser.add_argument("--fall-dir", action="append", type=Path, default=[])
    parser.add_argument("--no-fall-dir", action="append", type=Path, default=[])
    parser.add_argument("--fall-video", action="append", type=Path, default=[])
    parser.add_argument("--no-fall-video", action="append", type=Path, default=[])
    parser.add_argument("--count-per-class", type=int, default=10)
    parser.add_argument("--target-fps", type=float, default=6.0)
    parser.add_argument("--device", default="cpu")
    parser.add_argument(
        "--output-dir", type=Path, default=Path("artifacts/evaluation/urgency")
    )
    args = parser.parse_args()

    from icare_app.pose import RTMPoseExtractor

    fall_videos = collect_videos(
        args.fall_dir, args.fall_video, args.count_per_class
    )
    no_fall_videos = collect_videos(
        args.no_fall_dir, args.no_fall_video, args.count_per_class
    )
    if not fall_videos and not no_fall_videos:
        raise SystemExit("No videos found. Provide --fall-dir/--no-fall-dir or videos.")

    extractor = RTMPoseExtractor(device=args.device)
    rows: list[dict] = []
    for label, videos in (("fall", fall_videos), ("no_fall", no_fall_videos)):
        for index, video in enumerate(videos, start=1):
            print(f"[{label} {index}/{len(videos)}] {video}")
            rows.extend(analyze_video(video, label, extractor, args.target_fps))

    args.output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = args.output_dir / "urgency_traces.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=TRACE_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    plot_path = args.output_dir / "urgency_traces.png"
    save_plot(rows, plot_path)
    print(f"Wrote {csv_path}")
    print(f"Wrote {plot_path}")


if __name__ == "__main__":
    main()

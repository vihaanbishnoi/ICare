"""Run the real engine on one clip and print or save what it measured.

    python -m tools.run_engine_clip path/to/clip.mp4 --output artifacts/engine/clip.json

Uses the real YOLOX/RTMPose/PoseC3D models (rtmlib downloads and caches the pose
models on first use). Output goes to ignored artifacts/ by default; it is local
evidence for Person 4's benchmarks, not a file to commit.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import threading

from icare_app.engine import EngineError, load_engine


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("video", type=Path)
    parser.add_argument("--model", type=Path, default=Path("models/posec3d_fall.onnx"))
    parser.add_argument("--sample-fps", type=float, default=6.0)
    parser.add_argument("--output", type=Path, help="write the full poses/predictions JSON here")
    args = parser.parse_args(argv)

    poses: list = []
    predictions: list = []
    engine = load_engine(
        {"model_path": args.model, "device": "cpu", "sample_fps": args.sample_fps}
    )
    try:
        summary = engine.analyze_video(
            args.video,
            on_pose=poses.append,
            on_prediction=predictions.append,
            on_progress=lambda value: None,
            cancel_event=threading.Event(),
        )
        configuration = engine.describe()
    except EngineError as exc:
        print(f"{exc.code}: {exc}", file=sys.stderr)
        return 2
    finally:
        engine.close()

    probabilities = [p["fall_probability"] for p in predictions]
    print(json.dumps({
        "configuration": configuration,
        "summary": summary,
        "predictions": len(predictions),
        "max_fall_probability": max(probabilities),
        "last_fall_probability": probabilities[-1],
    }, indent=2))
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps({"configuration": configuration, "summary": summary,
                        "predictions": predictions, "poses": poses}),
            encoding="utf-8",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

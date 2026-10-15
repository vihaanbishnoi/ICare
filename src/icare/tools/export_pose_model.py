"""Export the YOLO26n-pose ONNX file the engine uses, with its metadata.

    python -m pip install "ultralytics==8.4.177" onnx onnxslim
    python -m icare.tools.export_pose_model

Development only: the product runs the exported ONNX with ONNX Runtime and needs
neither Ultralytics nor PyTorch. The export is end-to-end (NMS-free): one
forward pass returns at most 300 people as rows of
[x1, y1, x2, y2, score, class, 17 x (x, y, visibility)] in letterboxed input pixels.

The weights are Ultralytics YOLO26 and are licensed AGPL-3.0
(https://ultralytics.com/license); see models/README.md.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tempfile

ULTRALYTICS_VERSION = "8.4.177"
WEIGHTS = "yolo26n-pose.pt"
IMAGE_SIZE = 640


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output", type=Path, default=Path("models/yolo26n_pose.onnx"))
    args = parser.parse_args(argv)

    import ultralytics
    from ultralytics import YOLO

    if ultralytics.__version__ != ULTRALYTICS_VERSION:
        parser.error(f"use ultralytics=={ULTRALYTICS_VERSION}, found {ultralytics.__version__}")

    with tempfile.TemporaryDirectory() as temp:
        weights = Path(temp) / WEIGHTS
        model = YOLO(str(weights))  # downloads the official release asset into temp
        exported = Path(model.export(format="onnx", imgsz=IMAGE_SIZE, simplify=True,
                                     end2end=True, dynamic=False))
        args.output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(exported, args.output)
        source_digest = sha256(weights)

    metadata = {
        "architecture": "YOLO26n-pose (Ultralytics), end-to-end NMS-free export",
        "file": args.output.name,
        "sha256": sha256(args.output),
        "source_weights": WEIGHTS,
        "source_weights_sha256": source_digest,
        "ultralytics_version": ULTRALYTICS_VERSION,
        "input_name": "images",
        "input_shape": [1, 3, IMAGE_SIZE, IMAGE_SIZE],
        "output_shape": [1, 300, 57],
        "keypoints": "COCO-17",
        "license": "AGPL-3.0 (https://ultralytics.com/license)",
    }
    args.output.with_suffix(".json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(metadata, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

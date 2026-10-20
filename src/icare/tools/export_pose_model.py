"""Export the official YOLO26n-pose checkpoint to the fixed CPU ONNX contract.

Install requirements-export.txt in a separate environment, then run from the root:
    python -m icare.tools.export_pose_model
The PyTorch checkpoint and exporter output remain in ignored artifacts/.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import shutil


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--checkpoint", type=Path, default=Path("artifacts/yolo26/yolo26n-pose.pt"))
    parser.add_argument("--output", type=Path, default=Path("models/yolo26n-pose.onnx"))
    args = parser.parse_args()
    from ultralytics import YOLO

    args.checkpoint.parent.mkdir(parents=True, exist_ok=True)
    model = YOLO(str(args.checkpoint))
    settings = dict(format="onnx", imgsz=640, batch=1, dynamic=False,
                    simplify=False, nms=False, opset=17, device="cpu")
    exported = Path(model.export(**settings))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if exported.resolve() != args.output.resolve():
        shutil.copyfile(exported, args.output)
    metadata = {
        "architecture": "YOLO26n-pose", "dataset": "COCO keypoints",
        "keypoint_order": "COCO-17", "input_shape": [1, 3, 640, 640],
        "output_shape": [1, 300, 57], "output_layout": "xyxy, confidence, class, 17*(x,y,confidence)",
        "onnx_model": args.output.name,
        "sha256": hashlib.sha256(args.output.read_bytes()).hexdigest(),
        "checkpoint_sha256": hashlib.sha256(args.checkpoint.read_bytes()).hexdigest(),
        "ultralytics_version": importlib.metadata.version("ultralytics"),
        "export": settings,
        "source": "https://github.com/ultralytics/assets/releases/download/v8.4.0/yolo26n-pose.pt",
        "documentation": "https://docs.ultralytics.com/models/yolo26/",
        "license": "AGPL-3.0; upstream also offers Enterprise licensing",
        "license_url": "https://www.ultralytics.com/license",
        "fall_accuracy_revalidated": False,
    }
    args.output.with_suffix(".json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    distribution = importlib.metadata.distribution("ultralytics")
    license_path = next(p for p in distribution.files if str(p).endswith(".dist-info/licenses/LICENSE"))
    shutil.copyfile(distribution.locate_file(license_path), args.output.with_name("YOLO26_LICENSE"))
    print(f"Exported {args.output} sha256={metadata['sha256']}")


if __name__ == "__main__":
    main()

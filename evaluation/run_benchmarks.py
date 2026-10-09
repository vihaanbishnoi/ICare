"""Executable CLI runner for Person 4 ICare benchmark evaluation suite.

Usage:
    python -m evaluation.run_benchmarks --catalog examples/catalog.json --output artifacts/evaluation/benchmark_report.json

Notes:
    - Runs the real inference engine (icare_app.engine.load_engine).
    - If media status is pending or video files do not exist locally, it reports
      media status as pending and does NOT fabricate metrics per docs/interfaces/metrics.md.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time
from typing import Any, Dict, List, Optional

from evaluation.benchmark_harness import BenchmarkConfig, BenchmarkHarness, ClipAnnotation, MetricResults


def load_annotations_from_catalog(catalog_path: Path) -> Tuple[List[ClipAnnotation], str]:
    """Load clip annotations from catalog.json or manifest.json."""
    if not catalog_path.exists():
        raise FileNotFoundError(f"Catalog file not found: {catalog_path}")

    data = json.loads(catalog_path.read_text(encoding="utf-8"))
    status = data.get("status", "pending")
    items = data.get("examples", data.get("clips", []))

    annotations: List[ClipAnnotation] = []
    for item in items:
        clip_id = item.get("example_id", item.get("id"))
        filename = Path("examples") / item.get("file", item.get("filename", ""))
        onset_sec = item.get("annotated_onset_seconds")
        if onset_sec is None:
            onset_sec = item.get("fall_onset_seconds", item.get("fall_onset_sec"))
        annotations.append(ClipAnnotation(
            clip_id=clip_id,
            filename=filename,
            true_label=item.get("expected_outcome", item.get("label", "No Fall")),
            fall_onset_seconds=onset_sec,
            duration_seconds=item.get("duration_seconds", item.get("duration_sec")),
            provenance_status=item.get("provenance_status", status),
        ))
    return annotations, status


def run_benchmark_suite(
    catalog_path: Path,
    output_path: Optional[Path] = None,
    model_path: Path = Path("models/posec3d_fall.onnx"),
    device: str = "cpu",
) -> Dict[str, Any]:
    """Execute benchmark suite against the real engine if approved media files exist."""
    annotations, status = load_annotations_from_catalog(catalog_path)

    # Check if video files exist locally
    available_annotations = [a for a in annotations if a.filename.is_file()]

    if not available_annotations or status == "pending_approved_media":
        report = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "catalog_file": str(catalog_path),
            "media_provenance_status": "pending_approved_media",
            "evaluated_clips": 0,
            "total_catalog_clips": len(annotations),
            "baseline_metrics": None,
            "notice": "Approved media asset procurement is pending. Benchmark suite does not generate fabricated metrics when video files are unavailable."
        }
        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        return report

    # Real engine execution
    from icare_app.engine import load_engine

    config = BenchmarkConfig(model_path=model_path, device=device)
    harness = BenchmarkHarness(config)
    engine = load_engine({"model_path": model_path, "device": device})

    records = []
    try:
        for annot in available_annotations:
            record = harness.run_engine_clip(engine, annot)
            records.append(record)
    finally:
        engine.close()

    metrics = harness.compute_metrics(records, available_annotations)

    report = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "catalog_file": str(catalog_path),
        "media_provenance_status": status,
        "evaluated_clips": len(records),
        "total_catalog_clips": len(annotations),
        "baseline_metrics": metrics.to_dict(),
        "evaluation_notes": [
            "Baseline metrics measured using real icare_app.engine.",
            "Reported numbers distinguish group-aware baseline classifier results from deployed service."
        ]
    }

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    return report


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Run ICare Person 4 Evaluation Benchmark Suite")
    parser.add_argument(
        "--catalog",
        type=Path,
        default=Path("examples/catalog.json"),
        help="Path to catalog JSON containing clip annotations"
    )
    parser.add_argument(
        "--model",
        type=Path,
        default=Path("models/posec3d_fall.onnx"),
        help="Path to PoseC3D ONNX model"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/evaluation/benchmark_report.json"),
        help="Path where output benchmark report JSON will be written"
    )

    args = parser.parse_args(argv)

    try:
        report = run_benchmark_suite(args.catalog, args.output, model_path=args.model)
        if report.get("baseline_metrics"):
            print(json.dumps(report["baseline_metrics"], indent=2))
        else:
            print(f"[{report.get('media_provenance_status')}] {report.get('notice')}")
        return 0
    except Exception as exc:
        print(f"Error executing benchmark suite: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

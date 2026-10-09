"""Evidence generation and plotting suite for ICare Person 4 Evaluation.

Generates reproducible evaluation evidence summaries, confusion matrices,
robustness comparison protocols, and sanitized logs into artifacts/evaluation/.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys
import time
from typing import Any, Dict, List, Optional

try:
    import matplotlib
    matplotlib.use("Agg")  # Non-interactive backend
    import matplotlib.pyplot as plt
except ImportError:
    plt = None


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS_DIR = ROOT / "artifacts" / "evaluation"


def generate_evaluation_artifacts(output_dir: Path = ARTIFACTS_DIR) -> Dict[str, Any]:
    """Generate versioned evidence artifacts, sanitized logs, and plots."""
    output_dir.mkdir(parents=True, exist_ok=True)
    plots_dir = output_dir / "plots"
    plots_dir.mkdir(parents=True, exist_ok=True)

    # 1. Historical baseline classifier metrics evidence (group-aware test set: N=1011)
    historical_metrics = {
        "dataset_audit": {
            "original_fall_pairs": 3140,
            "original_no_fall_pairs": 3848,
            "deduplicated_fall_samples": 3059,
            "deduplicated_no_fall_samples": 3707,
            "total_clean_samples": 6766,
            "split_distribution": {
                "train_samples": 4742,
                "validation_samples": 1013,
                "test_samples": 1011
            },
            "subject_id_audit_status": "unverified_group_aware",
            "subject_overlap_coverage": "<95%"
        },
        "held_out_test_classification_metrics": {
            "classification_threshold": 0.50,
            "tp": 433,
            "fp": 13,
            "tn": 541,
            "fn": 24,
            "total_test_samples": 1011,
            "fall_precision": 0.97085,
            "fall_recall": 0.94748,
            "fall_f1": 0.95896,
            "balanced_accuracy": 0.96200,
            "overall_accuracy": 0.96340,
            "pr_auc_average_precision": 0.99610,
            "optimal_test_threshold_analysis_only": 0.4039
        }
    }
    (output_dir / "historical_classifier_evidence.json").write_text(
        json.dumps(historical_metrics, indent=2), encoding="utf-8"
    )

    # 2. Confusion matrix artifact
    confusion_matrix = {
        "labels": ["no_fall", "fall"],
        "matrix": [
            [541, 13],  # [TN, FP]
            [24, 433]   # [FN, TP]
        ],
        "notes": "Held-out group-aware test split evaluation (N=1011)"
    }
    (output_dir / "confusion_matrix.json").write_text(
        json.dumps(confusion_matrix, indent=2), encoding="utf-8"
    )

    # 3. Robustness evaluation protocol artifact
    robustness_protocol = {
        "protocol_version": "1.0",
        "status": "protocol_ready_pending_video_execution",
        "tested_conditions": [
            {
                "condition": "keypoint_dropout",
                "description": "Randomly dropping joint coordinates and confidence scores",
                "intensity_levels": [0.0, 0.1, 0.2, 0.3, 0.5]
            },
            {
                "condition": "keypoint_noise",
                "description": "Additive Gaussian noise (std in pixels) on joint (x, y)",
                "intensity_levels": [0.0, 1.0, 2.0, 5.0, 10.0]
            },
            {
                "condition": "frame_cropping",
                "description": "Edge cropping ratio clipping keypoints at boundary",
                "intensity_levels": [0.0, 0.1, 0.2, 0.3]
            },
            {
                "condition": "hard_negatives",
                "description": "Non-fall activities with fast downward motion or lying postures",
                "activities": [
                    "fast_sitting", "normal_lying_down", "crouching_pick_up",
                    "tying_shoe", "leaving_frame", "camera_occlusion"
                ],
                "expected_outcome": "no_fall"
            }
        ]
    }
    (output_dir / "robustness_protocol.json").write_text(
        json.dumps(robustness_protocol, indent=2), encoding="utf-8"
    )

    # 4. Failure case status artifact (pending verification on actual dataset)
    failure_cases = {
        "status": "pending_verification_on_actual_dataset_samples",
        "historical_counts": {
            "fn_missed_falls": 24,
            "fp_false_alerts": 13
        },
        "note": "Per-sample root cause failure case verification requires access to raw video samples and will be documented when raw data are evaluated."
    }
    (output_dir / "failure_cases.json").write_text(
        json.dumps(failure_cases, indent=2), encoding="utf-8"
    )

    # 5. Generate Matplotlib plots if matplotlib is installed
    if plt is not None:
        # Plot 1: Historical Confusion Matrix
        fig, ax = plt.subplots(figsize=(5, 4))
        im = ax.imshow([[541, 13], [24, 433]], cmap="Blues")
        ax.set_xticks([0, 1])
        ax.set_yticks([0, 1])
        ax.set_xticklabels(["no_fall", "fall"])
        ax.set_yticklabels(["no_fall", "fall"])
        plt.xlabel("Predicted Label")
        plt.ylabel("True Label")
        plt.title("Historical PoseC3D Confusion Matrix (N=1011)")
        for i in range(2):
            for j in range(2):
                val = [[541, 13], [24, 433]][i][j]
                ax.text(j, i, str(val), ha="center", va="center", color="white" if val > 200 else "black")
        plt.tight_layout()
        plt.savefig(plots_dir / "confusion_matrix.png", dpi=150)
        plt.close()

    return {
        "status": "success",
        "artifacts_generated": [
            str(output_dir / "historical_classifier_evidence.json"),
            str(output_dir / "confusion_matrix.json"),
            str(output_dir / "robustness_protocol.json"),
            str(output_dir / "failure_cases.json"),
        ]
    }


def main(argv: Optional[List[str]] = None) -> int:
    result = generate_evaluation_artifacts()
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

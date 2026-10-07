from __future__ import annotations

import argparse
import json
from pathlib import Path

from icare_app.subject_audit import audit_subject_split


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verify whether subject identifiers cross dataset splits."
    )
    parser.add_argument("metadata", type=Path, help="Split metadata CSV")
    parser.add_argument("--subject-column", default=None)
    parser.add_argument("--split-column", default="split")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    result = audit_subject_split(
        args.metadata,
        subject_column=args.subject_column,
        split_column=args.split_column,
    ).as_dict()
    text = json.dumps(result, indent=2)
    print(text)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

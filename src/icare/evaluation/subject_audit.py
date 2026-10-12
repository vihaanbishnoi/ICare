from __future__ import annotations

import csv
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path


SUBJECT_COLUMNS = (
    "subject_id",
    "subject",
    "person_id",
    "participant_id",
    "participant",
    "actor_id",
    "actor",
    "performer_id",
)
PATH_COLUMNS = (
    "video_relative_path",
    "video_path",
    "csv_relative_path",
    "csv_path",
    "normalized_stem",
    "filename",
)
SUBJECT_PATTERN = re.compile(
    r"(?:subject|subj|person|participant|actor|performer)[_\s-]*([a-z0-9]+)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class SubjectAuditResult:
    status: str
    metadata_path: str
    rows: int
    split_column: str | None
    subject_source: str | None
    subject_coverage: float
    unique_subjects: int
    subjects_per_split: dict[str, int]
    overlaps: dict[str, list[str]]
    message: str

    def as_dict(self) -> dict:
        return {
            "status": self.status,
            "metadata_path": self.metadata_path,
            "rows": self.rows,
            "split_column": self.split_column,
            "subject_source": self.subject_source,
            "subject_coverage": round(self.subject_coverage, 6),
            "unique_subjects": self.unique_subjects,
            "subjects_per_split": self.subjects_per_split,
            "overlaps": self.overlaps,
            "message": self.message,
        }


def audit_subject_split(
    metadata_path: str | Path,
    subject_column: str | None = None,
    split_column: str = "split",
) -> SubjectAuditResult:
    path = Path(metadata_path)
    with path.open(newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)
        rows = list(reader)
        columns = tuple(reader.fieldnames or ())

    if split_column not in columns:
        return SubjectAuditResult(
            status="unverifiable",
            metadata_path=str(path.resolve()),
            rows=len(rows),
            split_column=None,
            subject_source=None,
            subject_coverage=0.0,
            unique_subjects=0,
            subjects_per_split={},
            overlaps={},
            message=f"Metadata has no '{split_column}' column.",
        )

    chosen = subject_column if subject_column in columns else None
    if chosen is None:
        chosen = next((name for name in SUBJECT_COLUMNS if name in columns), None)

    subjects: list[str | None]
    source: str | None
    if chosen is not None:
        subjects = [_clean(row.get(chosen)) for row in rows]
        source = f"column:{chosen}"
    else:
        path_column = next((name for name in PATH_COLUMNS if name in columns), None)
        if path_column is None:
            subjects = [None] * len(rows)
            source = None
        else:
            subjects = [_subject_from_path(row.get(path_column)) for row in rows]
            source = f"conservative_path_pattern:{path_column}"

    identified = sum(subject is not None for subject in subjects)
    coverage = identified / len(rows) if rows else 0.0
    if not rows or coverage < 0.95:
        return SubjectAuditResult(
            status="unverifiable",
            metadata_path=str(path.resolve()),
            rows=len(rows),
            split_column=split_column,
            subject_source=source,
            subject_coverage=coverage,
            unique_subjects=len({value for value in subjects if value is not None}),
            subjects_per_split={},
            overlaps={},
            message=(
                "At least 95% subject-ID coverage is required. Add a verified "
                "subject_id column rather than guessing identities from filenames."
            ),
        )

    by_split: dict[str, set[str]] = defaultdict(set)
    for row, subject in zip(rows, subjects):
        if subject is not None:
            by_split[str(row[split_column]).strip().lower()].add(subject)

    overlaps: dict[str, list[str]] = {}
    split_names = sorted(by_split)
    for index, first in enumerate(split_names):
        for second in split_names[index + 1 :]:
            shared = sorted(by_split[first] & by_split[second])
            if shared:
                overlaps[f"{first}__{second}"] = shared

    status = "failed" if overlaps else "verified_subject_disjoint"
    message = (
        "The same subject appears in more than one split."
        if overlaps
        else "No verified subject identifier crosses splits."
    )
    return SubjectAuditResult(
        status=status,
        metadata_path=str(path.resolve()),
        rows=len(rows),
        split_column=split_column,
        subject_source=source,
        subject_coverage=coverage,
        unique_subjects=len({subject for subject in subjects if subject is not None}),
        subjects_per_split={key: len(value) for key, value in sorted(by_split.items())},
        overlaps=overlaps,
        message=message,
    )


def summarize_subject_values(metadata_path: str | Path, column: str) -> Counter:
    path = Path(metadata_path)
    with path.open(newline="", encoding="utf-8-sig") as file:
        return Counter(row.get(column, "") for row in csv.DictReader(file))


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip().lower()
    return cleaned or None


def _subject_from_path(value: str | None) -> str | None:
    cleaned = _clean(value)
    if cleaned is None:
        return None
    match = SUBJECT_PATTERN.search(cleaned)
    return match.group(1).lower() if match else None

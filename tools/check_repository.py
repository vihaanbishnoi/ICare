"""Portable source and documentation checks without model initialization."""
from __future__ import annotations

import ast
import json
from pathlib import Path
import re
import subprocess
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parents[1]
MARKDOWN_LINK = re.compile(r"!?\[[^\]]*\]\(([^\s)]+)(?:\s+\"[^\"]*\")?\)")


def main() -> int:
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=ROOT, capture_output=True, check=True,
    )
    paths = sorted(set(result.stdout.decode("utf-8").split("\0")) - {""})
    errors: list[str] = []
    python_count = link_count = 0
    for relative in paths:
        path = ROOT / relative
        if not path.is_file():
            # Pending deletions are represented in the index until committed.
            continue
        if path.suffix == ".py":
            try:
                ast.parse(path.read_text(encoding="utf-8-sig"), filename=relative)
                python_count += 1
            except (SyntaxError, UnicodeError) as exc:
                errors.append(f"{relative}: {exc}")
        if path.suffix == ".md":
            text = path.read_text(encoding="utf-8-sig")
            for match in MARKDOWN_LINK.finditer(text):
                target = match.group(1).strip("<>")
                parsed = urlsplit(target)
                if parsed.scheme or parsed.netloc or not parsed.path:
                    continue
                resolved = (path.parent / unquote(parsed.path)).resolve()
                if not resolved.is_relative_to(ROOT) or not resolved.exists():
                    errors.append(f"{relative}: missing local link {target}")
                link_count += 1

    required = [
        "AGENTS.md", "CLAUDE.md", "CONTRIBUTING.md", ".github/CODEOWNERS",
        "docs/team/ai_workflow.md", "docs/project/stack.md",
        ".github/workflows/ci.yml", ".github/workflows/security.yml",
        "requirements-test.txt",
        "models/posec3d_fall.onnx", "models/posec3d_runtime.json",
        "docs/team/ownership.md", "docs/team/backlog.md", "deployment/README.md",
        "docs/project/ICare_Report_Skeleton.docx",
    ]
    for relative in required:
        if not (ROOT / relative).is_file():
            errors.append(f"Required file missing: {relative}")
    ignored = subprocess.run(
        ["git", "check-ignore", "--stdin"], cwd=ROOT,
        input="\n".join(required) + "\n", capture_output=True, text=True,
    )
    if ignored.returncode not in (0, 1):
        errors.append(f"Could not verify ignore rules: {ignored.stderr.strip()}")
    for relative in ignored.stdout.splitlines():
        errors.append(f"Required repository file is ignored: {relative}")
    try:
        metadata = json.loads((ROOT / "models/posec3d_runtime.json").read_text(encoding="utf-8"))
        if metadata.get("classes") != ["No Fall", "Fall"]:
            errors.append("Model metadata must identify No Fall and Fall in that order")
    except (OSError, ValueError) as exc:
        errors.append(f"Model metadata: {exc}")

    for error in errors:
        print(error)
    if errors:
        return 1
    print(f"Repository checks passed: {python_count} Python files, {link_count} local documentation links.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

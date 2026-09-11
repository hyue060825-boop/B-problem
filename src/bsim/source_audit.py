"""按题面目录的校验清单检查原件，不依赖开发提示词。"""
import hashlib
import re
from pathlib import Path


def audit_sources(directory):
    root = Path(directory).resolve()
    rows = []
    seen = set()
    for line in (root / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        match = re.fullmatch(r"([0-9a-fA-F]{64}) [ *](.+)", line)
        if not match:
            raise ValueError("invalid SHA256SUMS entry")
        expected, name = match.groups()
        path = (root / name).resolve()
        try:
            path.relative_to(root)
        except ValueError:
            raise ValueError("source path must stay inside the problem directory")
        if name in seen:
            raise ValueError("duplicate source entry")
        seen.add(name)
        actual = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
        rows.append({"file": name, "expected": expected.lower(), "actual": actual,
                     "status": "MISSING" if actual is None else (
                         "PASS" if actual == expected.lower() else "CHANGED_REVIEW_REQUIRED")})
    if not rows:
        raise ValueError("empty SHA256SUMS")
    return {"label": "LOCAL-source-audit",
            "status": "PASS" if all(r["status"] == "PASS" for r in rows) else "FAIL",
            "sources": rows}

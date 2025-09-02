from __future__ import annotations

import fnmatch
import re
from pathlib import Path

import yaml

CONFIG_PATH = Path(__file__).resolve().parent.parent / "tools" / "forbidden_literals.yml"


def _load_cfg() -> tuple[list[tuple[str, re.Pattern[str]]], list[str], list[str]]:
    cfg = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    patterns = [
        (label, re.compile(regex, re.IGNORECASE | re.ASCII))
        for label, regex in cfg["patterns"].items()
    ]
    return patterns, cfg["include_globs"], cfg["exclude_globs"]


def _iter_files(root: Path, includes: list[str], excludes: list[str]) -> list[Path]:
    files: list[Path] = []
    for path in root.rglob("*"):
        if path.is_dir():
            continue
        rel = path.relative_to(root)
        rel_str = str(rel)
        skip = False
        for pattern in excludes:
            if pattern.endswith("/"):
                if rel_str.startswith(pattern):
                    skip = True
                    break
            elif fnmatch.fnmatch(rel_str, pattern):
                skip = True
                break
        if skip:
            continue
        if not any(fnmatch.fnmatch(rel_str, pattern) for pattern in includes):
            continue
        if path.stat().st_size > 2_000_000:
            continue
        files.append(path)
    return files


def test_forbidden_literals() -> None:
    root = Path(__file__).resolve().parents[1]
    patterns, includes, excludes = _load_cfg()
    findings: list[tuple[Path, int, str, str]] = []
    for path in _iter_files(root, includes, excludes):
        text = path.read_text(encoding="utf-8", errors="ignore")
        for label, rx in patterns:
            for m in rx.finditer(text):
                line = text.count("\n", 0, m.start()) + 1
                findings.append((path, line, label, m.group(0)))
                if len(findings) >= 10:
                    break
            if len(findings) >= 10:
                break
    assert not findings, "forbidden literal(s) found:\n" + "\n".join(
        f"{p}:{ln}: {label}: {snippet}" for p, ln, label, snippet in findings
    )

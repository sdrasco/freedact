from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from redactor.detect.base import EntityLabel

_ROOT = Path(__file__).resolve().parent


def list_fixtures(root: Path | str = _ROOT) -> list[str]:
    """Return fixture basenames where both .txt and .spans.json exist."""
    root = Path(root)
    names: list[str] = []
    for txt in root.glob("*.txt"):
        if (root / f"{txt.stem}.spans.json").exists():
            names.append(txt.stem)
    return sorted(names)


def load_fixture(name: str) -> tuple[str, dict[str, object]]:
    """Return (text, annotation dict) for fixture ``name``."""
    txt_path = _ROOT / f"{name}.txt"
    ann_path = _ROOT / f"{name}.spans.json"
    text = txt_path.read_text(encoding="utf-8")
    ann = json.loads(ann_path.read_text(encoding="utf-8"))
    expected_doc = txt_path.name
    if ann.get("doc") != expected_doc:
        raise ValueError(f"annotation doc mismatch: {ann.get('doc')} != {expected_doc}")
    return text, ann


def validate_spans(text: str, ann: dict[str, object]) -> list[str]:
    """Return a list of validation error messages for spans."""
    errors: list[str] = []
    length = len(text)
    valid_labels = {label.value for label in EntityLabel}
    spans = cast(list[dict[str, Any]], ann.get("spans", []))
    for idx, sp in enumerate(spans):
        start = cast(int, sp.get("start"))
        end = cast(int, sp.get("end"))
        label = cast(str, sp.get("label"))
        span_text = cast(str, sp.get("text", ""))
        if not isinstance(start, int) or not isinstance(end, int):
            errors.append(f"{idx}: invalid indices")
            continue
        if not (0 <= start < end <= length):
            errors.append(f"{idx}: indices {start}-{end} out of bounds")
            continue
        actual = text[start:end]
        if actual != span_text:
            errors.append(f"{idx}: text mismatch '{actual}' != '{span_text}'")
        if label not in valid_labels:
            errors.append(f"{idx}: unknown label '{label}'")
    return errors

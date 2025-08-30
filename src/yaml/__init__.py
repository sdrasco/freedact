"""Minimal YAML subset parser for offline environments.

This stub implements :func:`safe_load` compatible with a very small subset of
YAML sufficient for the project's configuration tests.  It supports:

* Mappings with indentation using spaces
* Lists of scalars
* Scalars: strings, quoted strings, integers, floats, ``true``/``false``, and
  ``null``

The parser ignores comments starting with ``#``.  It is **not** a full YAML
implementation and should be replaced by ``PyYAML`` in production.
"""

from __future__ import annotations

import re
from typing import Any, List, Tuple

__all__ = ["safe_load"]


def safe_load(stream: Any) -> Any:
    if hasattr(stream, "read"):
        stream = stream.read()
    lines = _prep_lines(str(stream))
    data, _ = _parse_mapping(lines, 0, 0)
    return data


def _prep_lines(stream: str) -> List[str]:
    out: List[str] = []
    for raw in stream.splitlines():
        line = raw.split("#", 1)[0].rstrip()
        if line.strip():
            out.append(line)
    return out


def _parse_mapping(lines: List[str], idx: int, indent: int) -> Tuple[Any, int]:
    result: dict[str, Any] = {}
    while idx < len(lines):
        line = lines[idx]
        cur_indent = len(line) - len(line.lstrip(" "))
        if cur_indent < indent:
            break
        if cur_indent > indent:
            raise ValueError("invalid indentation")
        line = line[indent:]
        if line.startswith("- "):
            return _parse_list(lines, idx, indent)
        key, rest = line.split(":", 1)
        key = key.strip()
        rest = rest.strip()
        idx += 1
        if rest:
            result[key] = _parse_scalar(rest)
        else:
            if idx < len(lines) and lines[idx].lstrip().startswith("- "):
                lst, idx = _parse_list(lines, idx, indent + 2)
                result[key] = lst
            else:
                sub, idx = _parse_mapping(lines, idx, indent + 2)
                result[key] = sub
    return result, idx


def _parse_list(lines: List[str], idx: int, indent: int) -> Tuple[Any, int]:
    items: list[Any] = []
    while idx < len(lines):
        line = lines[idx]
        cur_indent = len(line) - len(line.lstrip(" "))
        if cur_indent < indent or not line.lstrip().startswith("-"):
            break
        content = line[cur_indent + 1 :].lstrip()
        idx += 1
        if content:
            items.append(_parse_scalar(content))
        else:
            sub, idx = _parse_mapping(lines, idx, indent + 2)
            items.append(sub)
    return items, idx


def _parse_scalar(value: str) -> Any:
    if value.startswith("'") and value.endswith("'"):
        return value[1:-1]
    if value.startswith('"') and value.endswith('"'):
        return value[1:-1]
    if value in {"true", "True"}:
        return True
    if value in {"false", "False"}:
        return False
    if value in {"null", "Null", "None"}:
        return None
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    if re.fullmatch(r"-?\d+\.\d+", value):
        return float(value)
    return value

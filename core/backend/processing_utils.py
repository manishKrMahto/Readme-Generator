from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ParsedSymbol:
    kind: str
    name: str
    start_line: int | None = None
    end_line: int | None = None
    extra: dict | None = None


JS_FUNCTION_RE = re.compile(
    r"^\s*(export\s+)?(async\s+)?function\s+(?P<name>[A-Za-z_\$][\w\$]*)\s*\(",
    re.MULTILINE,
)
JS_CLASS_RE = re.compile(
    r"^\s*(export\s+)?class\s+(?P<name>[A-Za-z_\$][\w\$]*)\b", re.MULTILINE
)


def regex_parse_js_ts(source: str) -> list[ParsedSymbol]:
    out: list[ParsedSymbol] = []
    for m in JS_CLASS_RE.finditer(source):
        out.append(ParsedSymbol(kind="class", name=m.group("name"), start_line=_line_of(source, m.start())))
    for m in JS_FUNCTION_RE.finditer(source):
        out.append(ParsedSymbol(kind="function", name=m.group("name"), start_line=_line_of(source, m.start())))
    return out


def _line_of(source: str, idx: int) -> int:
    return source.count("\n", 0, idx) + 1


from __future__ import annotations

import re
from pathlib import Path

_STRINGS_PAIR_RE = re.compile(r'\s*"((?:\\.|[^"\\])*)"\s*=\s*"((?:\\.|[^"\\])*)"\s*;\s*$')


def escape_ios_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\"", "\\\"").replace("\n", "\\n")


def unescape_ios_string(value: str) -> str:
    out = []
    i = 0
    n = len(value)
    while i < n:
        ch = value[i]
        if ch == "\\" and i + 1 < n:
            nxt = value[i + 1]
            if nxt == "n":
                out.append("\n")
                i += 2
                continue
            out.append(nxt)
            i += 2
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def parse_strings_file(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    if not path.exists():
        return result

    in_block_comment = False
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if in_block_comment:
            if "*/" in line:
                in_block_comment = False
            continue
        if line.startswith("/*"):
            if "*/" not in line:
                in_block_comment = True
            continue
        if line.startswith("//"):
            continue
        m = _STRINGS_PAIR_RE.match(line)
        if not m:
            continue
        key = unescape_ios_string(m.group(1))
        val = unescape_ios_string(m.group(2))
        result[key] = val
    return result


def dump_strings_file(path: Path, pairs: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    for key in sorted(pairs.keys()):
        val = pairs[key]
        lines.append(f'"{escape_ios_string(key)}" = "{escape_ios_string(val)}";')
    content = "\n".join(lines) + ("\n" if lines else "")
    path.write_text(content, encoding="utf-8")

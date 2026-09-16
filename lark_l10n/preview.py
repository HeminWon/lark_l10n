from __future__ import annotations

import difflib
import json
import sys
import tempfile
from pathlib import Path

from .ios_strings import render_strings


def import_details(plan: dict) -> str:
    lines = []
    for item in plan["append_details"]:
        for lang, value in item["values"].items():
            lines.extend([f'@@ {json.dumps(item["key"], ensure_ascii=False)} [{lang}] @@',
                          f'+ {json.dumps(value, ensure_ascii=False)}', ""])
    for item in plan["update_details"]:
        for lang, change in item["changes"].items():
            lines.extend([f'@@ {json.dumps(item["key"], ensure_ascii=False)} [{lang}] @@',
                          f'- {json.dumps(change["from"], ensure_ascii=False)}',
                          f'+ {json.dumps(change["to"], ensure_ascii=False)}', ""])
    for item in plan.get("delete_details", []):
        lines.extend([f'@@ 删除整行 {item["row"]} @@', f'- key: {json.dumps(item["key"], ensure_ascii=False)}', ""])
    return "\n".join(lines)


def file_changes(files: list[tuple[Path, dict[str, str]]]) -> tuple[list, str]:
    changed = []
    details = []
    for path, pairs in files:
        exists = path.exists()
        before = path.read_text(encoding="utf-8") if exists else ""
        after = render_strings(pairs)
        if exists and before == after:
            continue
        changed.append((path, pairs))
        diff = difflib.unified_diff(
            before.splitlines(keepends=True), after.splitlines(keepends=True),
            fromfile=str(path) if exists else "/dev/null", tofile=str(path),
        )
        for line in diff:
            details.append(line if line.endswith("\n") else line + "\n\\ No newline at end of file\n")
        if not exists and not after:
            details.append(f"新增空文件：{path}\n")
    return changed, "".join(details)


def confirm_write(summary: str, details: str, yes: bool, has_changes: bool) -> bool:
    print(summary, flush=True)
    if not has_changes:
        print("无变更。")
        return False
    if yes:
        return True

    detail_path = None
    while True:
        print("[Y] 写入  [D] 查看明细  [N] 取消（默认）：", end="", file=sys.stderr, flush=True)
        try:
            choice = input().strip().lower()
        except (EOFError, KeyboardInterrupt):
            choice = "n"
        if choice in {"y", "yes"}:
            return True
        if choice in {"", "n", "no"}:
            print("已取消，未写入任何更改。")
            return False
        if choice == "d":
            if len(details.splitlines()) <= 20:
                print(details, flush=True)
            else:
                if detail_path is None:
                    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", prefix="lark-l10n-", suffix=".diff", delete=False) as output:
                        output.write(summary + "\n\n" + details)
                        detail_path = output.name
                print(f"完整明细：{detail_path}", flush=True)
        else:
            print("请输入 Y、D 或 N。", file=sys.stderr)

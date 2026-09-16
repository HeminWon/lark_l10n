#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys

from .backup import backup_sheet_rows
from .config_loader import load_project_config
from .feishu_api import LarkCliError, LarkSheetsClient, build_a1_range, start_row_from_range
from .ios_strings import dump_strings_file, parse_strings_file
from .preview import confirm_write, file_changes, import_details
from .sync_core import (
    build_export_payload,
    build_rows_for_existing_header,
    build_sheet_rows_from_local,
    compute_import_plan,
    load_localized_strings,
    normalize_sheet_rows,
)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Lark Sheets <-> iOS Localizable.strings sync tool")
    sub = p.add_subparsers(dest="command", required=True)

    pull_p = sub.add_parser("pull", help="Lark Sheets -> iOS .strings")
    pull_p.add_argument("--config", required=True, help="Path to config file (YAML)")

    push_p = sub.add_parser("push", help="iOS .strings -> Lark Sheets")
    push_p.add_argument("--config", required=True, help="Path to config file (YAML)")

    sort_p = sub.add_parser("sort", help="Sort iOS .strings files by key")
    sort_p.add_argument("--config", required=True, help="Path to config file (YAML)")

    for command_parser in (pull_p, push_p, sort_p):
        command_parser.add_argument(
            "--yes", "-y", action="store_true", help="Write immediately without confirmation"
        )

    return p


def resolve_range(client: LarkSheetsClient, given_range: str | None) -> str:
    if given_range:
        return given_range
    info = client.sheet_info()
    return build_a1_range(info.row_count, info.column_count)


def run_pull(config_path: str, yes: bool = False) -> int:
    cfg = load_project_config(config_path)
    if cfg.ios.output_dir is None:
        raise ValueError("pull requires ios.output_dir to be set")

    token = cfg.feishu.spreadsheet_token
    if not token:
        raise ValueError("missing feishu.spreadsheet_token in config")

    langs = cfg.columns.languages
    key_column = cfg.columns.key_column
    client = LarkSheetsClient(token, cfg.feishu.sheet_id)

    a1 = resolve_range(client, cfg.feishu.range_a1)
    rows = client.read_rows(a1)
    items = normalize_sheet_rows(rows, key_column, langs)
    payload, stats = build_export_payload(items, key_column, langs)

    pending_files = []
    for lang in langs:
        candidates = cfg.mapping.get(lang, [])
        lproj = candidates[0]
        out_file = cfg.ios.output_dir / lproj / f"{cfg.ios.table_name}.strings"
        pending_files.append((out_file, payload[lang]))

    pending_files, details = file_changes(pending_files)
    summary = f"飞书 → 本地 · 写入 {len(pending_files)} 个文件 · {stats.total_keys} 个 key"
    if confirm_write(summary, details, yes, bool(pending_files)):
        for out_file, pairs in pending_files:
            dump_strings_file(out_file, pairs)
        print(f"已写入 {len(pending_files)} 个文件。")
    return 0


def run_push(config_path: str, yes: bool = False) -> int:
    cfg = load_project_config(config_path, require_push=True)
    if cfg.ios.input_dir is None:
        raise ValueError("push requires ios.input_dir to be set")

    token = cfg.feishu.spreadsheet_token
    if not token:
        raise ValueError("missing feishu.spreadsheet_token in config")

    langs = cfg.columns.languages
    key_column = cfg.columns.key_column
    client = LarkSheetsClient(token, cfg.feishu.sheet_id)

    a1 = resolve_range(client, cfg.feishu.range_a1)
    remote_rows = client.read_rows(a1)
    remote_items = normalize_sheet_rows(remote_rows, key_column, langs)
    remote_header = remote_rows[0] if remote_rows else [key_column] + langs

    local_values = load_localized_strings(
        input_dir=cfg.ios.input_dir,
        langs=langs,
        table_name=cfg.ios.table_name,
        lang_to_lproj_candidates=cfg.mapping,
        strict=cfg.push.delete_missing,
    )
    local_items = build_sheet_rows_from_local(local_values, key_column, langs)
    delete_details = []
    if cfg.push.delete_missing:
        local_keys = {item[key_column] for item in local_items}
        if not local_keys:
            raise ValueError("push.delete_missing refused: no local keys found")
        key_index = remote_header.index(key_column)
        start_row = start_row_from_range(a1)
        for index, row in enumerate(remote_rows[1:], start=1):
            key = row[key_index].strip() if key_index < len(row) else ""
            if key and key not in local_keys:
                delete_details.append({"key": key, "row": start_row + index})


    _merged_all, updates, appends, stats = compute_import_plan(
        remote_items=remote_items,
        local_items=local_items,
        key_column=key_column,
        langs=langs,
        mode=cfg.push.mode,
        conflict=cfg.push.conflict,
        empty_overwrite=cfg.push.empty_overwrite,
    )

    remote_map = {item[key_column]: item for item in remote_items}
    update_details = []
    for item in updates:
        key = item.get(key_column, "")
        before = remote_map.get(key, {})
        changes: dict[str, dict[str, str]] = {}
        for lang in langs:
            old_v = before.get(lang, "")
            new_v = item.get(lang, "")
            if old_v != new_v:
                changes[lang] = {
                    "from": old_v,
                    "to": new_v,
                }
        if changes:
            update_details.append({
                "key": key,
                "changes": changes,
            })

    append_details = []
    for item in appends:
        append_details.append({
            "key": item.get(key_column, ""),
            "values": {lang: item.get(lang, "") for lang in langs},
        })

    plan = {
        "command": "push",
        "config": config_path,
        "range": a1,
        "mode": cfg.push.mode,
        "conflict": cfg.push.conflict,
        "empty_overwrite": cfg.push.empty_overwrite,
        "total_keys": stats.total_keys,
        "added": stats.added,
        "updated": stats.updated,
        "skipped": stats.skipped,
        "conflicts": stats.conflicts,
        "append_rows": len(appends),
        "update_rows": len(updates),
        "append_details": append_details,
        "update_details": update_details,
        "delete_details": delete_details,
    }

    summary = f"本地 → 飞书 · 新增 {stats.added} · 更新 {stats.updated} · 删除 {len(delete_details)} 行 · 跳过 {stats.skipped}"
    if confirm_write(summary, import_details(plan), yes, bool(updates or appends or delete_details)):
        backup_rows, backup_range = remote_rows, a1
        if delete_details:
            # Row deletion affects every column, including columns outside the sync range.
            backup_client = LarkSheetsClient(token, cfg.feishu.sheet_id)
            backup_range = resolve_range(backup_client, None)
            backup_rows = backup_client.read_rows(backup_range)
            if not backup_rows:
                raise ValueError("cannot delete rows: full worksheet backup returned no data")
        backup_path = backup_sheet_rows(token, cfg.feishu.sheet_id, backup_rows)
        print(f"飞书数据已备份：{backup_path}（范围：{backup_range}）", flush=True)
        if cfg.push.mode == "upsert" and updates:
            header_idx = {name: i for i, name in enumerate(remote_header)}
            row_idx_by_key: dict[str, int] = {}
            for i, row in enumerate(remote_rows[1:], start=1):
                if key_column in header_idx:
                    key_idx = header_idx[key_column]
                    if key_idx < len(row):
                        key = row[key_idx]
                        if key and key not in row_idx_by_key:
                            row_idx_by_key[key] = i

            write_rows = [list(row) for row in remote_rows]
            width = len(remote_header)
            for update in updates:
                key = update.get(key_column, "")
                row_idx = row_idx_by_key.get(key)
                if row_idx is None:
                    continue

                row = write_rows[row_idx]
                if len(row) < width:
                    row.extend([""] * (width - len(row)))

                for lang in langs:
                    col_idx = header_idx.get(lang)
                    if col_idx is None:
                        continue
                    row[col_idx] = update.get(lang, "")

            client.write_rows(a1, write_rows)

        if appends:
            append_rows = build_rows_for_existing_header(appends, remote_header, key_column, langs)
            client.append_rows(a1, append_rows)

        if delete_details:
            client.delete_rows([item["row"] for item in delete_details])
        print(f"已写入飞书：新增 {len(appends)} · 更新 {len(updates)} · 删除 {len(delete_details)} 行。")

    return 0


def run_sort(config_path: str, yes: bool = False) -> int:
    cfg = load_project_config(config_path)
    if cfg.ios.input_dir is None:
        raise ValueError("sort requires ios.input_dir to be set")

    langs = cfg.columns.languages
    files = []
    pending_files = []

    for lang in langs:
        candidates = cfg.mapping.get(lang, [])
        target = None
        for lproj in candidates:
            path = cfg.ios.input_dir / lproj / f"{cfg.ios.table_name}.strings"
            if path.exists():
                target = path
                break

        if target is None:
            files.append({"lang": lang, "file": str(cfg.ios.input_dir / (candidates[0] if candidates else f"{lang}.lproj") / f"{cfg.ios.table_name}.strings"), "status": "missing", "key_count": 0})
            continue

        pairs = parse_strings_file(target)
        pending_files.append((target, pairs))
        files.append({"lang": lang, "file": str(target), "status": "sorted", "key_count": len(pairs)})

    missing_count = sum(1 for f in files if f["status"] == "missing")

    pending_files, details = file_changes(pending_files)
    summary = f"本地排序 · 修改 {len(pending_files)} 个文件 · 缺失 {missing_count} 个文件"
    if confirm_write(summary, details, yes, bool(pending_files)):
        for target, pairs in pending_files:
            dump_strings_file(target, pairs)
        print(f"已写入 {len(pending_files)} 个文件。")
    return 0


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        if args.command == "pull":
            return run_pull(args.config, yes=args.yes)
        if args.command == "push":
            return run_push(args.config, yes=args.yes)
        if args.command == "sort":
            return run_sort(args.config, yes=args.yes)
        parser.print_help()
        return 2
    except (ValueError, LarkCliError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

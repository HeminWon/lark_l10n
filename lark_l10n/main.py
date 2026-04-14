#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys

from .config_loader import load_project_config
from .feishu_api import LarkCliError, LarkSheetsClient, build_a1_range
from .ios_strings import dump_strings_file
from .sync_core import (
    build_export_payload,
    build_rows_for_sheet,
    build_sheet_rows_from_local,
    compute_import_plan,
    load_localized_strings,
    normalize_sheet_rows,
)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Lark Sheets <-> iOS Localizable.strings sync tool")
    sub = p.add_subparsers(dest="command", required=True)

    export_p = sub.add_parser("export", help="Lark Sheets -> iOS .strings")
    export_p.add_argument("--config", required=True, help="Path to config file (YAML)")

    import_p = sub.add_parser("import", help="iOS .strings -> Lark Sheets")
    import_p.add_argument("--config", required=True, help="Path to config file (YAML)")

    return p


def resolve_range(client: LarkSheetsClient, given_range: str | None) -> str:
    if given_range:
        return given_range
    info = client.sheet_info()
    return build_a1_range(info.row_count, info.column_count)


def run_export(config_path: str) -> int:
    cfg = load_project_config(config_path)
    if cfg.ios.output_dir is None:
        raise ValueError("export requires ios.output_dir to be set")

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

    plan = {
        "command": "export",
        "config": config_path,
        "range": a1,
        "total_keys": stats.total_keys,
        "total_count_by_lang": stats.total_count_by_lang,
        "empty_count_by_lang": stats.empty_count_by_lang,
        "files": [],
    }

    for lang in langs:
        candidates = cfg.mapping.get(lang, [])
        lproj = candidates[0]
        out_file = cfg.ios.output_dir / lproj / f"{cfg.ios.table_name}.strings"
        plan["files"].append(str(out_file))
        if not cfg.sync.dry_run:
            dump_strings_file(out_file, payload[lang])

    print(json.dumps(plan, ensure_ascii=False, indent=2))
    return 0


def run_import(config_path: str) -> int:
    cfg = load_project_config(config_path)
    if cfg.ios.input_dir is None:
        raise ValueError("import requires ios.input_dir to be set")

    token = cfg.feishu.spreadsheet_token
    if not token:
        raise ValueError("missing feishu.spreadsheet_token in config")

    langs = cfg.columns.languages
    key_column = cfg.columns.key_column
    client = LarkSheetsClient(token, cfg.feishu.sheet_id)

    a1 = resolve_range(client, cfg.feishu.range_a1)
    remote_rows = client.read_rows(a1)
    remote_items = normalize_sheet_rows(remote_rows, key_column, langs)

    local_values = load_localized_strings(
        input_dir=cfg.ios.input_dir,
        langs=langs,
        table_name=cfg.ios.table_name,
        lang_to_lproj_candidates=cfg.mapping,
    )
    local_items = build_sheet_rows_from_local(local_values, key_column, langs)

    merged_all, updates, appends, stats = compute_import_plan(
        remote_items=remote_items,
        local_items=local_items,
        key_column=key_column,
        langs=langs,
        mode=cfg.sync.mode,
        conflict=cfg.sync.conflict,
        empty_overwrite=cfg.sync.empty_overwrite,
    )

    plan = {
        "command": "import",
        "config": config_path,
        "range": a1,
        "mode": cfg.sync.mode,
        "conflict": cfg.sync.conflict,
        "empty_overwrite": cfg.sync.empty_overwrite,
        "dry_run": cfg.sync.dry_run,
        "total_keys": stats.total_keys,
        "added": stats.added,
        "updated": stats.updated,
        "skipped": stats.skipped,
        "conflicts": stats.conflicts,
        "append_rows": len(appends),
        "update_rows": len(updates),
    }

    if not cfg.sync.dry_run:
        header = [key_column] + langs

        if cfg.sync.mode == "upsert" and updates:
            write_rows = [header] + build_rows_for_sheet(merged_all, key_column, langs)
            client.write_rows(a1, write_rows)

        if appends:
            append_rows = build_rows_for_sheet(appends, key_column, langs)
            client.append_rows(a1, append_rows)

    print(json.dumps(plan, ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        if args.command == "export":
            return run_export(args.config)
        if args.command == "import":
            return run_import(args.config)
        parser.print_help()
        return 2
    except (ValueError, LarkCliError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

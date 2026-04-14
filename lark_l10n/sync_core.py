from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .ios_strings import parse_strings_file


@dataclass
class SyncStats:
    total_keys: int = 0
    total_count_by_lang: dict[str, int] = field(default_factory=dict)
    empty_count_by_lang: dict[str, int] = field(default_factory=dict)
    added: int = 0
    updated: int = 0
    skipped: int = 0
    conflicts: int = 0


def normalize_sheet_rows(rows: list[list[str]], key_column: str, langs: list[str]) -> list[dict[str, str]]:
    if not rows:
        return []
    header = rows[0]
    header_idx = {name: i for i, name in enumerate(header)}
    if key_column not in header_idx:
        raise ValueError(f"sheet header missing required column: {key_column}")

    missing_langs = [lang for lang in langs if lang not in header_idx]
    if missing_langs:
        raise ValueError(f"sheet header missing language columns: {', '.join(missing_langs)}")

    result: list[dict[str, str]] = []
    for row in rows[1:]:
        key = _cell(row, header_idx[key_column]).strip()
        if not key:
            continue
        item = {key_column: key}
        for lang in langs:
            item[lang] = _cell(row, header_idx[lang])
        result.append(item)
    return result


def build_export_payload(items: list[dict[str, str]], key_column: str, langs: list[str]) -> tuple[dict[str, dict[str, str]], SyncStats]:
    by_lang: dict[str, dict[str, str]] = {lang: {} for lang in langs}
    stats = SyncStats(total_keys=len(items))

    for item in items:
        key = item[key_column]
        for lang in langs:
            value = item.get(lang, "")
            by_lang[lang][key] = value
            stats.total_count_by_lang[lang] = stats.total_count_by_lang.get(lang, 0) + 1
            if value == "":
                stats.empty_count_by_lang[lang] = stats.empty_count_by_lang.get(lang, 0) + 1

    return by_lang, stats


def load_localized_strings(
    input_dir: Path,
    langs: list[str],
    table_name: str,
    lang_to_lproj_candidates: dict[str, list[str]],
) -> dict[str, dict[str, str]]:
    values_by_lang: dict[str, dict[str, str]] = {}
    for lang in langs:
        candidates = lang_to_lproj_candidates.get(lang, [])
        path = _pick_existing_strings_file(input_dir, table_name, candidates)
        if path is None and candidates:
            path = input_dir / candidates[0] / f"{table_name}.strings"
        values_by_lang[lang] = parse_strings_file(path) if path else {}
    return values_by_lang


def build_sheet_rows_from_local(values_by_lang: dict[str, dict[str, str]], key_column: str, langs: list[str]) -> list[dict[str, str]]:
    all_keys: set[str] = set()
    for lang_values in values_by_lang.values():
        all_keys.update(lang_values.keys())

    rows: list[dict[str, str]] = []
    for key in sorted(all_keys):
        row = {key_column: key}
        for lang in langs:
            row[lang] = values_by_lang.get(lang, {}).get(key, "")
        rows.append(row)
    return rows


def compute_import_plan(
    remote_items: list[dict[str, str]],
    local_items: list[dict[str, str]],
    key_column: str,
    langs: list[str],
    mode: str,
    conflict: str,
    empty_overwrite: bool,
) -> tuple[list[dict[str, str]], list[dict[str, str]], list[dict[str, str]], SyncStats]:
    """Returns (merged_all, updates, appends, stats).
    merged_all is the full remote list with all updates applied, ready for a full write.
    """
    stats = SyncStats()
    remote_map = {it[key_column]: it for it in remote_items}

    updates: list[dict[str, str]] = []
    appends: list[dict[str, str]] = []

    for local in local_items:
        key = local[key_column]
        remote = remote_map.get(key)
        if remote is None:
            appends.append(local)
            stats.added += 1
            continue

        if mode == "append":
            stats.skipped += 1
            continue

        merged = dict(remote)
        changed = False

        for lang in langs:
            local_v = local.get(lang, "")
            remote_v = remote.get(lang, "")

            if local_v == remote_v:
                continue

            if local_v == "" and not empty_overwrite:
                continue

            if local_v != "" and remote_v != "" and local_v != remote_v:
                stats.conflicts += 1
                if conflict == "sheet-first":
                    continue

            merged[lang] = local_v
            changed = True

        if changed:
            updates.append(merged)
            stats.updated += 1
        else:
            stats.skipped += 1

    stats.total_keys = len(local_items)

    # build final write list by applying updates in-place
    merged_all = list(remote_items)
    if updates:
        index = {item[key_column]: i for i, item in enumerate(merged_all)}
        for it in updates:
            if it[key_column] in index:
                merged_all[index[it[key_column]]] = it

    return merged_all, updates, appends, stats


def build_rows_for_existing_header(
    items: list[dict[str, str]],
    header: list[str],
    key_column: str,
    langs: list[str],
) -> list[list[str]]:
    header_idx = {name: i for i, name in enumerate(header)}
    if key_column not in header_idx:
        raise ValueError(f"sheet header missing required column: {key_column}")

    missing_langs = [lang for lang in langs if lang not in header_idx]
    if missing_langs:
        raise ValueError(f"sheet header missing language columns: {', '.join(missing_langs)}")

    rows: list[list[str]] = []
    width = len(header)
    for item in items:
        row = [""] * width
        row[header_idx[key_column]] = item.get(key_column, "")
        for lang in langs:
            row[header_idx[lang]] = item.get(lang, "")
        rows.append(row)
    return rows


def build_rows_for_sheet(items: list[dict[str, str]], key_column: str, langs: list[str]) -> list[list[str]]:
    rows: list[list[str]] = []
    for item in items:
        row = [item.get(key_column, "")]
        for lang in langs:
            row.append(item.get(lang, ""))
        rows.append(row)
    return rows


def _pick_existing_strings_file(input_dir: Path, table_name: str, candidates: list[str]) -> Path | None:
    for lproj in candidates:
        path = input_dir / lproj / f"{table_name}.strings"
        if path.exists():
            return path
    return None


def _cell(row: list[str], idx: int) -> str:
    if idx < 0 or idx >= len(row):
        return ""
    return row[idx]

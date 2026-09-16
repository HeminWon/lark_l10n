from __future__ import annotations

from pathlib import Path
from typing import Any

from .feishu_api import extract_spreadsheet_token
from .models import ColumnsConfig, FeishuConfig, IOSConfig, ProjectConfig, PushConfig


def load_project_config(config_path: str, *, require_push: bool = False) -> ProjectConfig:
    path = Path(config_path)
    if not path.exists():
        raise ValueError(f"config file not found: {path}")

    raw = path.read_text(encoding="utf-8")
    data = _parse_config_text(path, raw)

    feishu_raw = _expect_dict(data, "feishu")
    ios_raw = _expect_dict(data, "ios")
    if require_push and "push" not in data:
        raise ValueError("config requires push section; rename the old sync section to push")
    push_raw = _expect_dict(data, "push") if require_push else {
        "mode": "upsert", "conflict": "local-first", "empty_overwrite": False
    }
    columns_raw = _expect_dict(data, "columns")
    mapping_raw = _optional_dict(data, "mapping")

    spreadsheet_token = _optional_str(feishu_raw, "spreadsheet_token")
    url = _optional_str(feishu_raw, "url")
    if not spreadsheet_token and not url:
        raise ValueError("feishu.spreadsheet_token or feishu.url is required")
    if not spreadsheet_token and url:
        spreadsheet_token = extract_spreadsheet_token(url)

    sheet_id = _required_str(feishu_raw, "sheet_id")
    range_a1 = _optional_str(feishu_raw, "range")

    input_dir = _optional_str(ios_raw, "input_dir")
    output_dir = _optional_str(ios_raw, "output_dir")
    table_name = _required_str(ios_raw, "table_name")

    mode = _required_str(push_raw, "mode")
    if mode not in {"append", "upsert"}:
        raise ValueError("push.mode must be 'append' or 'upsert'")

    conflict = _required_str(push_raw, "conflict")
    if conflict not in {"sheet-first", "local-first"}:
        raise ValueError("push.conflict must be 'sheet-first' or 'local-first'")

    empty_overwrite = _required_bool(push_raw, "empty_overwrite")
    delete_missing = _required_bool({"delete_missing": push_raw.get("delete_missing", False)}, "delete_missing")
    if delete_missing and mode != "upsert":
        raise ValueError("push.delete_missing requires push.mode: upsert")

    key_column = _required_str(columns_raw, "key_column")
    languages = _required_str_list(columns_raw, "languages")
    if not languages:
        raise ValueError("columns.languages must not be empty")

    mapping: dict[str, list[str]] = {}
    for lang in languages:
        if lang in mapping_raw:
            candidates = mapping_raw[lang]
            if not isinstance(candidates, list) or not candidates:
                raise ValueError(f"mapping.{lang} must be a non-empty list of strings")
            parsed = [str(x).strip() for x in candidates if str(x).strip()]
            if not parsed:
                raise ValueError(f"mapping.{lang} must not be empty")
            mapping[lang] = parsed
        else:
            mapping[lang] = [f"{lang}.lproj"]

    return ProjectConfig(
        feishu=FeishuConfig(
            spreadsheet_token=spreadsheet_token,
            sheet_id=sheet_id,
            range_a1=range_a1,
        ),
        ios=IOSConfig(
            input_dir=Path(input_dir) if input_dir else None,
            output_dir=Path(output_dir) if output_dir else None,
            table_name=table_name,
        ),
        push=PushConfig(
            mode=mode,
            conflict=conflict,
            empty_overwrite=empty_overwrite,
            delete_missing=delete_missing,
        ),
        columns=ColumnsConfig(
            key_column=key_column,
            languages=languages,
        ),
        mapping=mapping,
    )


def _parse_config_text(path: Path, raw: str) -> dict[str, Any]:
    if path.suffix.lower() not in {".yaml", ".yml"}:
        raise ValueError(f"only .yaml/.yml config files are supported (got: {path.name})")

    try:
        import yaml  # type: ignore
    except ModuleNotFoundError as exc:
        raise ValueError("PyYAML is required: pip install pyyaml") from exc

    try:
        data = yaml.safe_load(raw)
    except Exception as exc:
        raise ValueError(f"config file is not valid YAML: {path}") from exc

    if not isinstance(data, dict):
        raise ValueError(f"YAML top-level must be a mapping: {path}")
    return data


def _optional_dict(data: dict[str, Any], key: str) -> dict[str, Any]:
    v = data.get(key)
    if v is None:
        return {}
    if not isinstance(v, dict):
        raise ValueError(f"config field '{key}' must be a mapping")
    return v


def _expect_dict(data: dict[str, Any], key: str) -> dict[str, Any]:
    v = data.get(key)
    if not isinstance(v, dict):
        raise ValueError(f"config missing required mapping: '{key}'")
    return v


def _required_str(data: dict[str, Any], key: str) -> str:
    v = data.get(key)
    if not isinstance(v, str) or not v.strip():
        raise ValueError(f"config field '{key}' must be a non-empty string")
    return v.strip()


def _optional_str(data: dict[str, Any], key: str) -> str | None:
    v = data.get(key)
    if v is None:
        return None
    if not isinstance(v, str):
        raise ValueError(f"config field '{key}' must be a string")
    v = v.strip()
    return v or None


def _required_bool(data: dict[str, Any], key: str) -> bool:
    v = data.get(key)
    if not isinstance(v, bool):
        raise ValueError(f"config field '{key}' must be a boolean")
    return v


def _required_str_list(data: dict[str, Any], key: str) -> list[str]:
    v = data.get(key)
    if not isinstance(v, list):
        raise ValueError(f"config field '{key}' must be a list of strings")
    out = [str(x).strip() for x in v if str(x).strip()]
    return out

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class FeishuConfig:
    spreadsheet_token: str | None
    sheet_id: str
    range_a1: str | None


@dataclass
class IOSConfig:
    input_dir: Path | None
    output_dir: Path | None
    table_name: str


@dataclass
class PushConfig:
    mode: str
    conflict: str
    empty_overwrite: bool
    delete_missing: bool = False


@dataclass
class ColumnsConfig:
    key_column: str
    languages: list[str]


@dataclass
class ProjectConfig:
    feishu: FeishuConfig
    ios: IOSConfig
    push: PushConfig
    columns: ColumnsConfig
    mapping: dict[str, list[str]]

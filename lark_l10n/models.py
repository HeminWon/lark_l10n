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
class SyncConfig:
    mode: str
    conflict: str
    empty_overwrite: bool
    dry_run: bool


@dataclass
class ColumnsConfig:
    key_column: str
    languages: list[str]


@dataclass
class ProjectConfig:
    feishu: FeishuConfig
    ios: IOSConfig
    sync: SyncConfig
    columns: ColumnsConfig
    mapping: dict[str, list[str]]

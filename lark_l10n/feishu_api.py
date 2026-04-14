from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from typing import Any


class LarkCliError(RuntimeError):
    pass


@dataclass
class SheetInfo:
    row_count: int
    column_count: int


_TOKEN_RE = re.compile(r"/sheets/([a-zA-Z0-9]+)")


def extract_spreadsheet_token(url: str) -> str:
    m = _TOKEN_RE.search(url)
    if not m:
        raise ValueError(f"cannot extract spreadsheet token from URL: {url}")
    return m.group(1)


def column_index_to_name(idx: int) -> str:
    if idx < 1:
        raise ValueError("column index must be >= 1")
    result = []
    n = idx
    while n > 0:
        n, rem = divmod(n - 1, 26)
        result.append(chr(ord("A") + rem))
    return "".join(reversed(result))


def build_a1_range(row_count: int, column_count: int) -> str:
    if row_count < 1 or column_count < 1:
        return "A1:A1"
    return f"A1:{column_index_to_name(column_count)}{row_count}"


class LarkSheetsClient:
    def __init__(self, spreadsheet_token: str, sheet_id: str) -> None:
        self.spreadsheet_token = spreadsheet_token
        self.sheet_id = sheet_id

    def sheet_info(self) -> SheetInfo:
        data = self._run_json([
            "lark-cli",
            "sheets",
            "+info",
            "--spreadsheet-token",
            self.spreadsheet_token,
        ])

        sheets = _pick(data, ["data", "sheets", "sheets"])
        if not isinstance(sheets, list):
            raise LarkCliError("+info response missing sheets list")

        target: dict[str, Any] | None = None
        for sheet in sheets:
            if isinstance(sheet, dict) and sheet.get("sheet_id") == self.sheet_id:
                target = sheet
                break

        if target is None:
            raise LarkCliError(f"+info response does not contain sheet_id={self.sheet_id}")

        grid = target.get("grid_properties")
        if not isinstance(grid, dict):
            raise LarkCliError("+info response missing grid_properties")

        row_count = grid.get("row_count")
        col_count = grid.get("column_count")
        if not isinstance(row_count, int) or not isinstance(col_count, int):
            raise LarkCliError("cannot parse row_count/column_count from +info response")

        return SheetInfo(row_count=row_count, column_count=col_count)

    def read_rows(self, a1_range: str) -> list[list[str]]:
        data = self._run_json([
            "lark-cli",
            "sheets",
            "+read",
            "--spreadsheet-token",
            self.spreadsheet_token,
            "--sheet-id",
            self.sheet_id,
            "--range",
            a1_range,
        ])
        return _extract_values(data)

    def write_rows(self, a1_range: str, rows: list[list[str]]) -> None:
        payload = json.dumps(rows, ensure_ascii=False)
        self._run_json([
            "lark-cli",
            "sheets",
            "+write",
            "--spreadsheet-token",
            self.spreadsheet_token,
            "--sheet-id",
            self.sheet_id,
            "--range",
            a1_range,
            "--values",
            payload,
        ])

    def append_rows(self, a1_range: str, rows: list[list[str]]) -> None:
        payload = json.dumps(rows, ensure_ascii=False)
        self._run_json([
            "lark-cli",
            "sheets",
            "+append",
            "--spreadsheet-token",
            self.spreadsheet_token,
            "--sheet-id",
            self.sheet_id,
            "--range",
            a1_range,
            "--values",
            payload,
        ])

    def _run_json(self, cmd: list[str]) -> dict[str, Any]:
        try:
            proc = subprocess.run(cmd, text=True, capture_output=True, timeout=30)
        except subprocess.TimeoutExpired:
            raise LarkCliError(f"lark-cli timed out (30s): {' '.join(cmd)}")
        if proc.returncode != 0:
            stderr = (proc.stderr or "").strip()
            stdout = (proc.stdout or "").strip()
            detail = stderr or stdout or "unknown error"
            raise LarkCliError(f"lark-cli failed: {' '.join(cmd)}\n{detail}")

        raw = (proc.stdout or "").strip()
        if not raw:
            return {}
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise LarkCliError(f"lark-cli output is not valid JSON: {raw[:500]}") from exc


def _pick(data: dict[str, Any], path: list[str]) -> Any:
    cur: Any = data
    for key in path:
        if not isinstance(cur, dict) or key not in cur:
            return None
        cur = cur[key]
    return cur


def _extract_values(data: dict[str, Any]) -> list[list[str]]:
    values = _pick(data, ["data", "valueRange", "values"])
    if values is None:
        return []
    if not isinstance(values, list):
        raise LarkCliError("+read response values has unexpected structure")

    rows: list[list[str]] = []
    for row in values:
        if not isinstance(row, list):
            continue
        rows.append(["" if v is None else str(v) for v in row])
    return rows

from __future__ import annotations

import csv
import io
import json
import os
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
_ROW_PREFIX_RE = re.compile(r"^\[row=\d+\]\s*")
_CELL_RE = re.compile(r"^([A-Za-z]+)(\d+)$")


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
        self._last_read_row_count = 0

    def sheet_info(self) -> SheetInfo:
        data = self._run_json([
            "lark-cli",
            "sheets",
            "+workbook-info",
            "--spreadsheet-token",
            self.spreadsheet_token,
        ])

        sheets = _extract_sheets(data)
        target: dict[str, Any] | None = None
        for sheet in sheets:
            if isinstance(sheet, dict) and sheet.get("sheet_id") == self.sheet_id:
                target = sheet
                break

        if target is None:
            raise LarkCliError(f"+workbook-info response does not contain sheet_id={self.sheet_id}")

        resource_type = target.get("resource_type")
        if resource_type not in {None, "sheet"}:
            raise LarkCliError(f"sheet_id={self.sheet_id} is not a grid sheet (resource_type={resource_type})")

        row_count = target.get("row_count")
        col_count = target.get("column_count")
        if not isinstance(row_count, int) or not isinstance(col_count, int):
            raise LarkCliError("cannot parse row_count/column_count from +workbook-info response")

        return SheetInfo(row_count=row_count, column_count=col_count)

    def read_rows(self, a1_range: str) -> list[list[str]]:
        data = self._run_json([
            "lark-cli",
            "sheets",
            "+csv-get",
            "--spreadsheet-token",
            self.spreadsheet_token,
            "--sheet-id",
            self.sheet_id,
            "--range",
            a1_range,
            "--include-row-prefix=true",
        ])
        rows = _extract_csv_rows(data)
        self._last_read_row_count = len(rows)
        return rows

    def write_rows(self, a1_range: str, rows: list[list[str]]) -> None:
        payload = _rows_to_csv(rows)
        self._run_json([
            "lark-cli",
            "sheets",
            "+csv-put",
            "--spreadsheet-token",
            self.spreadsheet_token,
            "--sheet-id",
            self.sheet_id,
            "--start-cell",
            _start_cell_from_range(a1_range),
            "--csv",
            "-",
        ], input_text=payload)

    def append_rows(self, a1_range: str, rows: list[list[str]]) -> None:
        if not rows:
            return
        payload = _rows_to_csv(rows)
        start_cell = f"{_start_col_from_range(a1_range)}{self._last_read_row_count + start_row_from_range(a1_range)}"
        self._run_json([
            "lark-cli",
            "sheets",
            "+csv-put",
            "--spreadsheet-token",
            self.spreadsheet_token,
            "--sheet-id",
            self.sheet_id,
            "--start-cell",
            start_cell,
            "--csv",
            "-",
        ], input_text=payload)

    def delete_rows(self, row_numbers: list[int]) -> None:
        # Group adjacent rows and delete highest batches first to keep indexes stable.
        rows = sorted(set(row_numbers))
        if any(row < 1 for row in rows):
            raise ValueError("row numbers must be positive")
        groups = []
        for row in rows:
            if groups and row == groups[-1][1] + 1:
                groups[-1][1] = row
            else:
                groups.append([row, row])
        ranges = [f"{start}:{end}" for start, end in reversed(groups)]
        for offset in range(0, len(ranges), 100):
            self._run_json([
                "lark-cli", "sheets", "+dim-delete",
                "--spreadsheet-token", self.spreadsheet_token,
                "--sheet-id", self.sheet_id,
                "--ranges", json.dumps(ranges[offset:offset + 100]), "--yes",
            ])

    def _run_json(self, cmd: list[str], input_text: str | None = None) -> dict[str, Any]:
        env = os.environ.copy()
        env.setdefault("LARKSUITE_CLI_NO_UPDATE_NOTIFIER", "1")
        env.setdefault("LARKSUITE_CLI_NO_SKILLS_NOTIFIER", "1")

        try:
            proc = subprocess.run(cmd, input=input_text, text=True, capture_output=True, timeout=30, env=env)
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


def _extract_sheets(data: dict[str, Any]) -> list[Any]:
    sheets = _pick(data, ["data", "sheets"])
    if isinstance(sheets, list):
        return sheets

    old_sheets = _pick(data, ["data", "sheets", "sheets"])
    if isinstance(old_sheets, list):
        return old_sheets

    raise LarkCliError("+workbook-info response missing sheets list")


def _extract_csv_rows(data: dict[str, Any]) -> list[list[str]]:
    text = _pick(data, ["data", "annotated_csv"])
    if text is None:
        return []
    if not isinstance(text, str):
        raise LarkCliError("+csv-get response annotated_csv has unexpected structure")
    return _trim_trailing_empty_rows(_csv_to_rows(text))


def _csv_to_rows(text: str) -> list[list[str]]:
    rows: list[list[str]] = []
    for row in csv.reader(io.StringIO(text)):
        if row:
            row[0] = _strip_row_prefix(row[0])
        rows.append(["" if v is None else str(v) for v in row])
    return rows


def _rows_to_csv(rows: list[list[str]]) -> str:
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerows(rows)
    return out.getvalue()


def _strip_row_prefix(value: str) -> str:
    return _ROW_PREFIX_RE.sub("", value, count=1)


def _trim_trailing_empty_rows(rows: list[list[str]]) -> list[list[str]]:
    end = len(rows)
    while end > 0 and all(cell == "" for cell in rows[end - 1]):
        end -= 1
    return rows[:end]


def _start_cell_from_range(a1_range: str) -> str:
    start = a1_range.split(":", 1)[0].strip()
    if not _CELL_RE.match(start):
        raise ValueError(f"invalid A1 range: {a1_range}")
    return start.upper()


def _start_col_from_range(a1_range: str) -> str:
    start = _start_cell_from_range(a1_range)
    m = _CELL_RE.match(start)
    if not m:
        raise ValueError(f"invalid A1 range: {a1_range}")
    return m.group(1).upper()


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


def start_row_from_range(a1_range: str) -> int:
    start = _start_cell_from_range(a1_range)
    row = int(_CELL_RE.fullmatch(start).group(2))
    if row < 1:
        raise ValueError(f"invalid A1 range: {a1_range}")
    return row

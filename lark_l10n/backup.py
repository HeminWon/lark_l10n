from __future__ import annotations

import csv
import os
import re
from datetime import datetime
from pathlib import Path


def backup_sheet_rows(spreadsheet_token: str, sheet_id: str, rows: list[list[str]]) -> Path:
    """Save the pre-write values, including headers and non-language columns."""
    for component in (spreadsheet_token, sheet_id):
        if not re.fullmatch(r"[A-Za-z0-9_-]+", component):
            raise ValueError("invalid spreadsheet token or sheet ID for backup path")
    directory = Path.home() / ".lark_l10n" / "backups" / spreadsheet_token / sheet_id
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{datetime.now():%Y%m%d_%H%M%S_%f}.csv"
    # Exclusive creation prevents an existing backup from being overwritten.
    with path.open("x", encoding="utf-8-sig", newline="") as output:
        try:
            csv.writer(output).writerows(rows)
            output.flush()
            os.fsync(output.fileno())
        except BaseException:
            path.unlink(missing_ok=True)
            raise
    return path

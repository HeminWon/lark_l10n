import csv
import io
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from lark_l10n.backup import backup_sheet_rows
from lark_l10n.main import main


class BackupTests(unittest.TestCase):
    def test_csv_round_trip_and_unique_paths(self):
        rows = [["key", "en", "备注"], ["001", 'Hello, "world"\nNext line', "中文"], ["empty", "", "=literal"]]
        with tempfile.TemporaryDirectory() as tmp, patch("pathlib.Path.home", return_value=Path(tmp)):
            first = backup_sheet_rows("token", "sheet", rows)
            second = backup_sheet_rows("token", "sheet", rows)
            self.assertNotEqual(first, second)
            self.assertEqual(first.parent, Path(tmp) / ".lark_l10n/backups/token/sheet")
            self.assertTrue(first.read_bytes().startswith(b"\xef\xbb\xbf"))
            with first.open(encoding="utf-8-sig", newline="") as source:
                self.assertEqual(list(csv.reader(source)), rows)

    def test_failed_backup_removes_partial_file(self):
        with tempfile.TemporaryDirectory() as tmp, patch("pathlib.Path.home", return_value=Path(tmp)), patch("lark_l10n.backup.os.fsync", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                backup_sheet_rows("token", "sheet", [["key", "en"]])
            self.assertEqual(list(Path(tmp).rglob("*.csv")), [])

    def test_push_backup_lifecycle(self):
        for scenario in ("write", "backup_failure", "remote_failure", "unchanged", "details_cancel", "append_only"):
            with self.subTest(scenario=scenario), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                cfg = SimpleNamespace(
                    ios=SimpleNamespace(input_dir=root, table_name="Localizable"),
                    feishu=SimpleNamespace(spreadsheet_token="token", sheet_id="sheet", range_a1="A1:C2"),
                    columns=SimpleNamespace(languages=["en"], key_column="key"),
                    push=SimpleNamespace(mode="upsert", conflict="local-first", empty_overwrite=False, delete_missing=False),
                    mapping={"en": ["en.lproj"]},
                )
                remote = [["key", "en", "notes"], ["a", "old", "keep me"]]
                values = {"a": "old"} if scenario == "unchanged" else {"a": "new", "b": "added"}
                if scenario == "append_only":
                    values["a"] = "old"
                argv = ["lark-l10n", "push", "--config", "unused.yaml"]
                if scenario != "details_cancel":
                    argv.append("--yes")
                with patch("sys.argv", argv), patch("pathlib.Path.home", return_value=root), patch("lark_l10n.main.load_project_config", return_value=cfg), patch("lark_l10n.main.load_localized_strings", return_value={"en": values}), patch("lark_l10n.main.LarkSheetsClient") as client_type, patch("builtins.input", side_effect=["D", "N"]) as prompt, redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                    client = client_type.return_value
                    client.read_rows.return_value = remote

                    def check_backup(*args):
                        paths = list(root.rglob("*.csv"))
                        self.assertEqual(len(paths), 1)
                        with paths[0].open(encoding="utf-8-sig", newline="") as source:
                            self.assertEqual(list(csv.reader(source)), remote)
                        if scenario == "remote_failure":
                            raise OSError("network failed")

                    client.write_rows.side_effect = check_backup
                    client.append_rows.side_effect = check_backup
                    if scenario == "backup_failure":
                        with patch("lark_l10n.backup.os.fsync", side_effect=OSError("disk full")):
                            result = main()
                    else:
                        result = main()
                    self.assertEqual(result, 1 if scenario in ("backup_failure", "remote_failure") else 0)
                    if scenario in ("backup_failure", "unchanged", "details_cancel"):
                        client.write_rows.assert_not_called()
                        client.append_rows.assert_not_called()
                        self.assertEqual(list(root.rglob("*.csv")), [])
                    else:
                        self.assertEqual(len(list(root.rglob("*.csv"))), 1)
                        if scenario == "write":
                            client.write_rows.assert_called_once_with("A1:C2", [["key", "en", "notes"], ["a", "new", "keep me"]])
                            client.append_rows.assert_called_once_with("A1:C2", [["b", "added", ""]])
                        elif scenario == "append_only":
                            client.write_rows.assert_not_called()
                            client.append_rows.assert_called_once()
                        else:
                            client.append_rows.assert_not_called()
                    if scenario != "details_cancel":
                        prompt.assert_not_called()

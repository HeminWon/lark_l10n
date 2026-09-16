import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path
from unittest.mock import patch, Mock

import yaml

from lark_l10n.config_loader import load_project_config
from lark_l10n.feishu_api import LarkSheetsClient, SheetInfo
from lark_l10n.main import main


class DeleteMissingTests(unittest.TestCase):
    def test_push_deletion_and_guards(self):
        for scenario in ("mixed", "delete_only", "cancel", "missing", "empty", "invalid", "comment", "disabled", "append", "backup_failure", "delete_failure", "empty_backup"):
            with self.subTest(scenario=scenario), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                for lang in ("en", "zh"):
                    folder = root / f"{lang}.lproj"
                    folder.mkdir()
                    (folder / "Localizable.strings").write_text('"keep" = "";\n' if lang == "en" else '"zh_only" = "保留";\n')
                en = root / "en.lproj/Localizable.strings"
                if scenario == "mixed":
                    en.write_text('"keep" = "new";\n"new_key" = "added";\n')
                if scenario == "missing":
                    en.unlink()
                if scenario == "invalid":
                    en.write_text('"keep" = "ok";\nbad syntax\n')
                if scenario == "comment":
                    en.write_text('"keep" = "ok";\n/* unclosed\n')
                if scenario == "empty":
                    for lang in ("en", "zh"):
                        (root / f"{lang}.lproj/Localizable.strings").write_text("")
                config_data = {
                    "feishu": {"spreadsheet_token": "token", "sheet_id": "sheet", "range": "B3:D8"},
                    "ios": {"input_dir": str(root), "table_name": "Localizable"},
                    "columns": {"key_column": "key", "languages": ["en", "zh"]},
                    "push": {"mode": "append" if scenario == "append" else "upsert", "conflict": "local-first", "empty_overwrite": False, "delete_missing": scenario != "disabled"},
                }
                config = root / "config.yaml"
                config.write_text(yaml.safe_dump(config_data))
                remote = [["key", "en", "zh"], ["gone", "old", "旧"], ["keep", "old", ""], ["", "", ""], ["zh_only", "", "保留"], ["gone2", "old", "旧"]]
                sync_client, backup_client = Mock(), Mock()
                sync_client.read_rows.return_value = remote
                backup_client.sheet_info.return_value = SheetInfo(8, 5)
                backup_client.read_rows.return_value = [["full", "backup", "notes"]]
                if scenario == "empty_backup":
                    backup_client.read_rows.return_value = []
                events = []
                def backup(*args):
                    self.assertEqual(args[2], [["full", "backup", "notes"]])
                    events.append("backup")
                    if scenario == "backup_failure":
                        raise OSError("disk full")
                    return root / "backup.csv"
                sync_client.write_rows.side_effect = lambda *args: events.append("update")
                sync_client.append_rows.side_effect = lambda *args: events.append("append")
                def delete(rows):
                    self.assertEqual(rows, [4, 8])
                    events.append("delete")
                    if scenario == "delete_failure":
                        raise OSError("delete failed")
                sync_client.delete_rows.side_effect = delete
                argv = ["lark-l10n", "push", "--config", str(config)]
                if scenario != "cancel":
                    argv.append("--yes")
                with patch("sys.argv", argv), patch("lark_l10n.main.LarkSheetsClient", side_effect=[sync_client, backup_client]), patch("lark_l10n.main.backup_sheet_rows", side_effect=backup), patch("builtins.input", side_effect=["D", "N"]), redirect_stdout(io.StringIO()) as output, redirect_stderr(io.StringIO()):
                    code = main()
                failed = scenario in ("missing", "empty", "invalid", "comment", "append", "backup_failure", "delete_failure", "empty_backup")
                self.assertEqual(code, int(failed))
                if scenario == "mixed":
                    self.assertEqual(events, ["backup", "update", "append", "delete"])
                elif scenario in ("delete_only", "delete_failure"):
                    self.assertEqual(events, ["backup", "delete"])
                elif scenario == "backup_failure":
                    self.assertEqual(events, ["backup"])
                else:
                    self.assertEqual(events, [])
                if scenario == "cancel":
                    self.assertIn('key: "gone"', output.getvalue())
                    self.assertIn("删除整行 4", output.getvalue())

    def test_config_migration_and_optional_push(self):
        data = {"feishu": {"spreadsheet_token": "token", "sheet_id": "sheet"}, "ios": {"table_name": "Localizable"}, "columns": {"key_column": "key", "languages": ["en"]}}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.yaml"
            path.write_text(yaml.safe_dump(data))
            load_project_config(str(path))  # pull and sort do not need push policies
            with self.assertRaisesRegex(ValueError, "rename"):
                load_project_config(str(path), require_push=True)
            data["push"] = {"mode": "upsert", "conflict": "local-first", "empty_overwrite": False}
            path.write_text(yaml.safe_dump(data))
            self.assertFalse(load_project_config(str(path), require_push=True).push.delete_missing)
            data["push"]["delete_missing"] = "true"
            path.write_text(yaml.safe_dump(data))
            with self.assertRaisesRegex(ValueError, "boolean"):
                load_project_config(str(path), require_push=True)

    def test_delete_row_groups_descending_and_batched(self):
        client = LarkSheetsClient("token", "sheet")
        with patch.object(client, "_run_json") as run:
            client.delete_rows([8, 4, 5, 8])
            args = run.call_args.args[0]
            self.assertEqual(json.loads(args[args.index("--ranges") + 1]), ["8:8", "4:5"])
            self.assertEqual(args[-1], "--yes")
            run.reset_mock()
            client.delete_rows(list(range(2, 406, 2)))
            self.assertEqual(run.call_count, 3)
            batches = [json.loads(call.args[0][call.args[0].index("--ranges") + 1]) for call in run.call_args_list]
            self.assertEqual([r for batch in batches for r in batch], [f"{n}:{n}" for n in range(404, 1, -2)])

    def test_append_uses_range_start_row(self):
        client = LarkSheetsClient("token", "sheet")
        client._last_read_row_count = 6
        with patch.object(client, "_run_json") as run:
            client.append_rows("B3:D8", [["new"]])
            args = run.call_args.args[0]
            self.assertEqual(args[args.index("--start-cell") + 1], "B9")

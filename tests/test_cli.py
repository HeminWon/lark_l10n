import io
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

import yaml

from lark_l10n.main import main


class WriteConfirmationTests(unittest.TestCase):
    def test_all_commands_require_confirmation_before_any_write(self):
        for command in ("pull", "push", "sort"):
            for answer in ("", "n", EOFError(), KeyboardInterrupt(), "y", " YES ", "automatic"):
                with self.subTest(command=command, answer=answer), tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    source = root / "en.lproj" / "Localizable.strings"
                    source.parent.mkdir()
                    original = '"z" = "last";\n"a" = "new";\n'
                    source.write_text(original)
                    output = root / "out" / "en.lproj" / "Localizable.strings"
                    config = root / "config.yaml"
                    config.write_text(yaml.safe_dump({
                        "feishu": {"spreadsheet_token": "test", "sheet_id": "sheet", "range": "A1:B2"},
                        "ios": {"input_dir": str(root), "output_dir": str(root / "out"), "table_name": "Localizable"},
                        "push": {"mode": "upsert", "conflict": "local-first", "empty_overwrite": False},
                        "columns": {"key_column": "key", "languages": ["en"]},
                    }))
                    argv = ["lark-l10n", command, "--config", str(config)]
                    if answer == "automatic":
                        argv.append("--yes")
                    stdout = io.StringIO()
                    with patch("sys.argv", argv), patch("lark_l10n.main.LarkSheetsClient") as client_cls, redirect_stdout(stdout), redirect_stderr(io.StringIO()), patch("pathlib.Path.home", return_value=root):
                        client = client_cls.return_value
                        client.read_rows.return_value = [["key", "en"], ["a", "old"]]

                        def respond():
                            # The summary must be visible, with no changes yet.
                            self.assertTrue(stdout.getvalue())
                            self.assertEqual(source.read_text(), original)
                            self.assertFalse(output.exists())
                            client.write_rows.assert_not_called()
                            client.append_rows.assert_not_called()
                            if isinstance(answer, BaseException):
                                raise answer
                            return answer

                        with patch("builtins.input", side_effect=respond) as prompt:
                            self.assertEqual(main(), 0)
                        if answer == "automatic":
                            prompt.assert_not_called()
                        else:
                            prompt.assert_called_once()
                        confirmed = answer in ("y", " YES ", "automatic")
                        backups = list((root / ".lark_l10n").rglob("*.csv"))
                        self.assertEqual(len(backups), int(command == "push" and confirmed))
                        if command == "pull":
                            self.assertEqual(output.exists(), confirmed)
                            if confirmed:
                                self.assertIn('"a" = "old";', output.read_text())
                        elif command == "sort":
                            self.assertEqual(source.read_text() != original, confirmed)
                            if confirmed:
                                self.assertLess(source.read_text().index('"a"'), source.read_text().index('"z"'))
                        else:
                            self.assertEqual(client.write_rows.call_count, int(confirmed))
                            self.assertEqual(client.append_rows.call_count, int(confirmed))
                            if confirmed:
                                client.write_rows.assert_called_once_with("A1:B2", [["key", "en"], ["a", "new"]])
                                client.append_rows.assert_called_once_with("A1:B2", [["z", "last"]])


if __name__ == "__main__":
    unittest.main()

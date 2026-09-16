import io
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path
from unittest.mock import patch

from lark_l10n.preview import confirm_write, file_changes, import_details


class PreviewTests(unittest.TestCase):
    def test_details_then_confirm_or_cancel(self):
        for choice, expected in (("Y", True), ("N", False)):
            with self.subTest(choice=choice), patch("builtins.input", side_effect=["invalid", "D", choice]) as prompt, redirect_stdout(io.StringIO()) as output, redirect_stderr(io.StringIO()):
                self.assertEqual(confirm_write("summary", "- old\n+ new", False, True), expected)
                self.assertIn("- old\n+ new", output.getvalue())
                self.assertEqual(prompt.call_count, 3)

    def test_large_details_complete_and_reused(self):
        details = "\n".join(f"+ value {i}" for i in range(21))
        with tempfile.TemporaryDirectory() as tmp, patch("tempfile.tempdir", tmp), patch("builtins.input", side_effect=["D", "d", "n"]), redirect_stdout(io.StringIO()) as output, redirect_stderr(io.StringIO()):
            self.assertFalse(confirm_write("summary", details, False, True))
            files = list(Path(tmp).glob("*.diff"))
            self.assertEqual(len(files), 1)
            self.assertEqual(files[0].read_text(), "summary\n\n" + details)
            self.assertEqual(output.getvalue().count(str(files[0])), 2)
            self.assertNotIn("+ value", output.getvalue())

    def test_twenty_lines_stay_inline(self):
        details = "\n".join(["+ value"] * 20)
        with patch("builtins.input", side_effect=["d", "n"]), patch("tempfile.NamedTemporaryFile") as temp, redirect_stdout(io.StringIO()) as output, redirect_stderr(io.StringIO()):
            self.assertFalse(confirm_write("summary", details, False, True))
            temp.assert_not_called()
            self.assertIn(details, output.getvalue())

    def test_yes_and_no_changes_skip_prompt(self):
        with patch("builtins.input") as prompt, redirect_stdout(io.StringIO()):
            self.assertTrue(confirm_write("summary", "details", True, True))
            self.assertFalse(confirm_write("summary", "", False, False))
            prompt.assert_not_called()

    def test_redirected_input_uses_normal_confirmation(self):
        for answer, expected in (("y\n", True), ("n\n", False), ("", False)):
            with self.subTest(answer=answer), patch("sys.stdin", io.StringIO(answer)), redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                self.assertEqual(confirm_write("summary", "details", False, True), expected)

    def test_file_changes_skip_identical_and_include_removed_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "Localizable.strings"
            path.write_text('"a" = "old";\n')
            self.assertEqual(file_changes([(path, {"a": "old"})]), ([], ""))
            changed, details = file_changes([(path, {"b": "new"})])
            self.assertEqual(len(changed), 1)
            self.assertIn('-"a" = "old";', details)
            self.assertIn('+"b" = "new";', details)

    def test_import_details_preserve_all_languages_and_escape_newlines(self):
        details = import_details({"append_details": [{"key": "theme", "values": {"en": "Theme", "zh_CN": "主题"}}], "update_details": [{"key": "title", "changes": {"en": {"from": "old", "to": "new\nline"}}}]})
        for text in ('[en]', '[zh_CN]', '+ "主题"', '- "old"', '+ "new\\nline"'):
            self.assertIn(text, details)

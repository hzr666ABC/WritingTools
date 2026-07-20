import unittest

from text_application import build_diff_html


class TextApplicationTests(unittest.TestCase):
    def test_diff_marks_changes_and_escapes_html(self):
        output = build_diff_html("你好 <旧>", "你好，新世界 <新>")
        self.assertIn('class="deleted"', output)
        self.assertIn('class="inserted"', output)
        self.assertNotIn("<旧>", output)
        self.assertIn("&lt;", output)


if __name__ == "__main__":
    unittest.main()

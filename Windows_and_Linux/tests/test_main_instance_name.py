import os
import unittest
from unittest.mock import patch

from main import configured_instance_name


class MainInstanceNameTests(unittest.TestCase):
    def test_default_instance_name_keeps_production_single_instance_behavior(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(
                configured_instance_name(),
                "WritingToolsCN.Desktop.Instance",
            )

    def test_explicit_safe_test_instance_name_is_supported(self):
        with patch.dict(
            os.environ,
            {"WRITINGTOOLS_INSTANCE_NAME": "WritingToolsCN.SharpInput.Test.Instance"},
            clear=True,
        ):
            self.assertEqual(
                configured_instance_name(),
                "WritingToolsCN.SharpInput.Test.Instance",
            )

    def test_unsafe_instance_name_falls_back_to_production_default(self):
        with patch.dict(
            os.environ,
            {"WRITINGTOOLS_INSTANCE_NAME": "bad\\name"},
            clear=True,
        ):
            self.assertEqual(
                configured_instance_name(),
                "WritingToolsCN.Desktop.Instance",
            )


if __name__ == "__main__":
    unittest.main()

import unittest

from quick_action_workflow import (
    bottom_right_position,
    number_key_to_index,
    record_trigger,
    resolve_remembered_option,
)


class FakeGeometry:
    def right(self):
        return 1919

    def bottom(self):
        return 1039


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.options = {"Proofread": {}, "Summary": {}, "Custom": {}}

    def test_remember_mode_runs_last_valid_preset(self):
        config = {"remember_last_action": True, "last_used_option": "Summary"}
        self.assertEqual(resolve_remembered_option(config, self.options), "Summary")

    def test_disabled_or_invalid_remember_mode_shows_popup(self):
        self.assertIsNone(resolve_remembered_option({}, self.options))
        self.assertIsNone(resolve_remembered_option(
            {"remember_last_action": True, "last_used_option": "Custom"},
            self.options,
        ))
        self.assertIsNone(resolve_remembered_option(
            {"remember_last_action": True, "last_used_option": "Missing"},
            self.options,
        ))

    def test_number_shortcuts_use_visible_one_based_order(self):
        self.assertEqual(number_key_to_index(1, 8), 0)
        self.assertEqual(number_key_to_index(8, 8), 7)
        self.assertIsNone(number_key_to_index(9, 8))
        self.assertIsNone(number_key_to_index(0, 8))

    def test_popup_sits_inside_bottom_right_work_area(self):
        self.assertEqual(bottom_right_position(FakeGeometry(), 390, 553), (1510, 467))

    def test_rapid_trigger_is_throttled_without_requesting_app_exit(self):
        recent = []
        for timestamp in (10.0, 10.2):
            recent, throttled = record_trigger(recent, timestamp)
            self.assertFalse(throttled)

        recent, throttled = record_trigger(recent, 10.4)
        self.assertTrue(throttled)
        self.assertEqual(recent, [10.0, 10.2, 10.4])

        recent, throttled = record_trigger(recent, 12.0)
        self.assertFalse(throttled)
        self.assertEqual(recent, [12.0])


if __name__ == "__main__":
    unittest.main()

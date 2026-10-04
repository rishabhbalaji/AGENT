import unittest
from datetime import datetime
from pathlib import Path

from job_engine.config import load_config
from job_engine.modes import OperatingMode, resolve_mode


SCHEDULE = load_config(Path(__file__).parents[1] / "config" / "examples").schedule


class OperatingModeTests(unittest.TestCase):
    def test_full_time_window_includes_start_and_excludes_end(self):
        at_start = resolve_mode(SCHEDULE, datetime(2026, 1, 5, 8, 0))
        at_end = resolve_mode(SCHEDULE, datetime(2026, 1, 5, 20, 0))
        self.assertEqual(at_start.mode, OperatingMode.FULL_TIME)
        self.assertTrue(at_start.allows("approved_external_applications"))
        self.assertEqual(at_end.mode, OperatingMode.PART_TIME)

    def test_midnight_spanning_part_time_window(self):
        before_midnight = resolve_mode(SCHEDULE, datetime(2026, 1, 5, 23, 59))
        after_midnight = resolve_mode(SCHEDULE, datetime(2026, 1, 6, 7, 59))
        self.assertEqual(before_midnight.mode, OperatingMode.PART_TIME)
        self.assertEqual(after_midnight.mode, OperatingMode.PART_TIME)
        self.assertTrue(after_midnight.allows("discovery"))

    def test_overlapping_maintenance_and_part_time_actions_are_unioned(self):
        state = resolve_mode(SCHEDULE, datetime(2026, 1, 6, 2, 0))
        self.assertEqual(state.mode, OperatingMode.PART_TIME)
        self.assertIn("maintenance", state.matched_windows)
        self.assertTrue(state.allows("discovery"))
        self.assertTrue(state.allows("status_ingestion"))
        self.assertTrue(state.allows("agent_corner"))

    def test_pause_stops_all_actions(self):
        state = resolve_mode(SCHEDULE, datetime(2026, 1, 5, 10, 0), paused=True)
        self.assertEqual(state.mode, OperatingMode.PAUSED)
        self.assertFalse(state.actions)
        self.assertFalse(state.allows("discovery"))

    def test_idle_gap_is_explicit(self):
        schedule = {
            "timezone": "Europe/London",
            "windows": {"short": {"start": "10:00", "end": "11:00", "allow": ["discovery"]}},
        }
        state = resolve_mode(schedule, datetime(2026, 1, 5, 12, 0))
        self.assertEqual(state.mode, OperatingMode.IDLE)
        self.assertFalse(state.allows("discovery"))

"""Verify that retired event IDs cannot keep writing return dates."""
import unittest
import build_reinforcement_transit_trial as builder
from test_scattered_fleet_organizer import parse


class RetirementTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        builder.build()
        cls.events = parse((builder.OUT / "events/qol_transit_trial.txt").read_text(encoding="utf-8"))

    def test_old_events_have_no_effects(self):
        for kind, _, rows in self.events:
            if kind not in ("country_event", "fleet_event"):
                continue
            number = next(v for k, o, v in rows if k == "id").rsplit(".", 1)[1]
            if number == "1":
                continue
            with self.subTest(event=number):
                self.assertIn(("hide_window", "=", "yes"), rows)
                self.assertIn(("trigger", "=", [("always", "=", "no")]), rows)
                self.assertFalse(any(k in ("immediate", "option") for k, o, v in rows))

    def test_menu_only_closes(self):
        rows = next(rows for kind, o, rows in self.events if kind == "country_event")
        self.assertFalse(any(k == "immediate" for k, o, v in rows))
        options = [v for k, o, v in rows if k == "option"]
        self.assertEqual(len(options), 1)
        self.assertFalse(any(k in ("hidden_effect", "effect") for k, o, v in options[0]))

    def test_no_timer_writes_callbacks_or_visible_edict(self):
        builder.validate()


if __name__ == "__main__":
    unittest.main()

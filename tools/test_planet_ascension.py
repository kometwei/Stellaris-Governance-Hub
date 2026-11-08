"""Scope and tier boundary checks; these do not run the Stellaris engine."""
from pathlib import Path
import unittest

from test_construction_speed import parse

ROOT = Path(__file__).resolve().parents[1]
EFFECT = "common/scripted_effects/auto_qol_planet_ascension_effects.txt"


def value(rows, key):
    return next(v for k, _, v in rows if k == key)


class PlanetAscensionTests(unittest.TestCase):
    def test_player_scope_and_tier_boundaries(self):
        rows = parse((ROOT / EFFECT).read_text(encoding="utf-8"))
        action = value(value(rows, "auto_qol_ascend_owned_colonies_to_10"), "if")
        self.assertEqual(value(action, "limit"), [("is_ai", "=", "no")])
        colonies = value(action, "every_owned_colony")
        self.assertEqual(value(colonies, "limit"), [("has_planetary_ascension_tier", "<", "10")])
        target = int(value(colonies, "set_planetary_ascension_tier"))
        self.assertEqual(target, 10)
        self.assertEqual({k for k, _, _ in colonies}, {"limit", "set_planetary_ascension_tier"})
        # Apply the parsed tier predicate and assignment to mixed-level colonies.
        def apply(tiers):
            threshold = int(value(value(colonies, "limit"), "has_planetary_ascension_tier"))
            return [target if tier < threshold else tier for tier in tiers]
        self.assertEqual(apply([0, 1, 9, 10, 15]), [10, 10, 10, 10, 15])
        self.assertEqual(apply(apply([0, 9, 15])), [10, 10, 15])
        self.assertEqual(apply([]), [])

    def test_active_public_build_contains_action_and_localisation(self):
        root = ROOT / "dist/stellaris_mod_enhancer_core"
        self.assertEqual((root / EFFECT).read_bytes(), (ROOT / EFFECT).read_bytes())
        menu = (root / "events/auto_qol_hub_gui_events.txt").read_text(encoding="utf-8")
        self.assertIn('name = "auto_qol_menu.planet_ascension_10"', menu)
        self.assertIn("auto_qol_ascend_owned_colonies_to_10 = yes", menu)
        loc = (root / "localisation/simp_chinese/auto_qol_l_simp_chinese.yml").read_bytes()
        self.assertTrue(loc.startswith(b"\xef\xbb\xbfl_simp_chinese:"))
        self.assertIn("auto_qol_menu.planet_ascension_10_tt:0", loc.decode("utf-8-sig"))


if __name__ == "__main__":
    unittest.main()

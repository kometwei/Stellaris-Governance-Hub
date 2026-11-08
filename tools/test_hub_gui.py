"""Central dashboard integration: preserve gameplay actions and legacy routing."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from build_hub_gui import ROOT, MENU, build, generate, ensure_router, events
from test_construction_speed import parse


def value(rows, key):
    return next(v for k, _, v in rows if k == key)


def definitions(text):
    return {value(v, "id"): v for k, _, v in parse(text) if k == "country_event"}


class HubGuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.files = generate()
        cls.menu = definitions((ROOT / MENU).read_text(encoding="utf-8-sig"))
        cls.hub = definitions(cls.files["events/auto_qol_hub_gui_events.txt"])

    def page(self, entry):
        def find(rows):
            for key, _, arg in rows:
                if key == "country_event" and value(arg, "id").startswith("auto_qol_hub_native_page."):
                    return value(arg, "id")
                if isinstance(arg, list):
                    result = find(arg)
                    if result:
                        return result
        return self.hub[find(value(self.hub[entry], "immediate"))]

    def test_stable_entry_returns_to_hub_and_legacy_self_refresh_stays_legacy(self):
        router = self.menu["auto_qol_menu.1"]
        self.assertEqual(value(router, "hide_window"), "yes")
        self.assertEqual(value(value(value(router, "immediate"), "country_event"), "id"), "auto_qol_hub.1")
        legacy = self.menu["auto_qol_menu.900"]
        self.assertIn("auto_qol_menu.900", repr(legacy))
        self.assertNotIn("auto_qol_menu.1'", repr(legacy))
        setup = value(legacy, "immediate")
        self.assertEqual(value(self.hub["auto_qol_hub.1"], "immediate")[:len(setup)], setup)

    def test_home_preserves_original_module_actions_and_prerequisites(self):
        def options(rows):
            return {value(v, "name"): v for k, _, v in rows if k == "option"}

        def route(rows):
            targets = {"auto_qol_menu.900": "auto_qol_hub.1", "auto_qol_assimilation.1": "auto_qol_assimilation_gui.1", "auto_qol_ascension.1": "auto_qol_ascension_gui.1"}
            return [(k, o, route(v) if isinstance(v, list) else targets.get(v, v) if k == "id" else v) for k, o, v in rows]

        before = options(self.menu["auto_qol_menu.900"])
        after = options(self.page("auto_qol_hub.1"))
        for key in ("auto_qol_menu.planet_ascension_10", "auto_qol_military_open", "auto_qol_council_gui_open", "auto_qol_menu.assimilation", "auto_qol_menu.ascension_slots", "auto_qol_menu.psionic_bundle_ready", "auto_qol_menu.psionic_bundle_complete", "auto_qol_menu.psionic_bundle_locked"):
            self.assertEqual(after[key], route(before[key]))
        self.assertNotIn("auto_qol_menu.fleet_menu", after)
        self.assertNotIn("auto_qol_menu.council_menu", after)
        self.assertNotIn("auto_qol_hub_compat", after)

    def test_home_module_order_groups_construction_and_keeps_conditional_actions(self):
        page = self.page("auto_qol_hub.1")
        names = [value(rows, "name") for key, _, rows in page if key == "option" and not any(k == "custom_gui" for k, _, _ in rows)]
        self.assertEqual(names, [
            "auto_qol_military_open", "auto_qol_hub_megastructures",
            "auto_qol_hub_starbase_clear", "auto_qol_council_gui_open",
            "auto_qol_menu.assimilation", "auto_qol_menu.ascension_slots",
            "auto_qol_menu.planet_ascension_10", "auto_qol_menu.psionic_bundle_ready",
            "auto_qol_menu.psionic_bundle_complete", "auto_qol_menu.psionic_bundle_locked",
        ])

    def test_no_legacy_menu_entry_in_any_normal_gui(self):
        self.assertNotIn("auto_qol_hub.2", self.hub)
        for path in (ROOT / "events").glob("*gui_events.txt"):
            text = path.read_text(encoding="utf-8-sig")
            self.assertNotIn("id = auto_qol_hub.2", text)
            self.assertNotIn("id = auto_qol_menu.900", text)
            self.assertNotIn("id = auto_qol_fleet_menu.1", text)
            self.assertNotIn("id = auto_qol_council_menu.1", text)

    def test_native_scrollbars_and_player_scopes_are_present(self):
        gui = self.files["interface/auto_qol_hub.gui"]
        self.assertIn('scrollbarType = "standardtext_slider"', gui)
        self.assertIn('scrollbarType = "standardlistbox_slider"', gui)
        self.assertIn('quadTextureSprite = "GFX_main_close_button"', gui)
        self.assertNotIn('name = "auto_qol_hub_home"', gui)
        self.assertNotIn('name = "auto_qol_hub_compat"', gui)
        # Fixed effect-button navigation previously stacked visible windows.
        # Only the hidden encounter handler may be fired by homepage toggles.
        button_scripts = self.files["common/button_effects/auto_qol_hub_buttons.txt"]
        self.assertNotIn("id = auto_qol_menu.1", button_scripts)
        self.assertNotIn("id = auto_qol_hub.", button_scripts)
        for rows in self.hub.values():
            self.assertEqual(value(rows, "trigger"), [("is_ai", "=", "no")])
        for name, _, rows in parse(self.files["common/button_effects/auto_qol_hub_buttons.txt"]):
            self.assertEqual(value(rows, "allow"), value(rows, "potential"))
            self.assertIn(("is_ai", "=", "no"), value(value(rows, "allow"), "from"))
            hidden = value(value(rows, "effect"), "hidden_effect")
            self.assertEqual([k for k, _, _ in hidden], ["from"])
            if not name.endswith(("_home", "_compat")):
                self.assertNotIn("auto_qol_hub.1", repr(hidden))

    def test_router_migration_and_regeneration_are_idempotent(self):
        scratch = ROOT / "scratch"
        scratch.mkdir(exist_ok=True)
        with TemporaryDirectory(dir=scratch) as directory:
            root = Path(directory)
            self.assertIn(ROOT.resolve(), root.resolve().parents)
            path = root / MENU
            path.parent.mkdir(parents=True)
            # Exercise a pre-dashboard source, then build twice.
            original = next(block for block in events((ROOT / MENU).read_text(encoding="utf-8-sig")) if 'id = auto_qol_menu.900' in block)
            path.write_text("namespace = auto_qol_menu\n" + original.replace("auto_qol_menu.900", "auto_qol_menu.1"), encoding="utf-8")
            ensure_router(root)
            once = path.read_bytes()
            build(root)
            first = {relative: (root / relative).read_bytes() for relative in generate(root)}
            build(root)
            self.assertEqual(once, path.read_bytes())
            self.assertEqual(first, {relative: (root / relative).read_bytes() for relative in generate(root)})
        for relative, expected in self.files.items():
            self.assertEqual((ROOT / relative).read_text(encoding="utf-8-sig"), expected)

    def test_public_profile_does_not_reintroduce_development_traditions(self):
        from build_release_profiles import remove_named_option
        scratch = ROOT / "scratch"
        scratch.mkdir(exist_ok=True)
        with TemporaryDirectory(dir=scratch) as directory:
            root = Path(directory)
            self.assertIn(ROOT.resolve(), root.resolve().parents)
            path = root / MENU
            path.parent.mkdir(parents=True)
            path.write_text(remove_named_option((ROOT / MENU).read_text(encoding="utf-8-sig"), "auto_qol_menu.tradition_menu"), encoding="utf-8")
            build(root)
            text = (root / "events/auto_qol_hub_gui_events.txt").read_text(encoding="utf-8-sig")
            self.assertNotIn("tradition_unlock_menu.1", text)
            self.assertNotIn('name = "auto_qol_menu.tradition_menu"', text)


if __name__ == "__main__":
    unittest.main()

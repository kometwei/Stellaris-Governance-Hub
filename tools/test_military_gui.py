"""GUI/script integration checks; these do not emulate the Clausewitz renderer."""
import re
import unittest
from unittest.mock import patch
from pathlib import Path

from build_military_gui import GUI_ACCEPTED, generate
from build_release_profiles import collect_localisation_references
from test_construction_speed import Runtime, named, parse

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = {
    "navy_cap": (500, 1000, 2500, 5000, 10000, 50000),
    "cmd_limit": (50, 100, 200, 500, 1000, 5000),
    "starbase_module_speed": (50, 100, 200, 500, 1000, 2000),
    "defense_platform_speed": (50, 100, 200, 500, 1000, 2000),
    "army_recruit_speed": (50, 100, 200, 500, 1000, 2000),
    "ship_build_speed": (50, 100, 200, 500, 1000, 2000),
    "planet_construction": (1, 2, 5, 10),
    "planet_build_speed": (50, 100, 200, 500, 1000, 2000),
    "planet_jobs_speed": (10, 25, 50, 100, 200, 1000),
    "automated_ratio": (1, 5, 10, 25, 50, 100),
    "automated_output": (10, 25, 50, 100, 200, 1000),
    "mega_build_speed": (50, 100, 200, 500, 1000, 2000),
    "mega_construction": (1, 2, 5, 10),
    "mega_production": (10, 25, 50, 100, 200, 1000),
}


def read(relative):
    return (ROOT / relative).read_text(encoding="utf-8-sig")


def field(rows, key):
    return next(v for k, o, v in rows if k == key)


class MilitaryGuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.gui = read("interface/auto_qol_military.gui")
        cls.buttons = read("common/button_effects/auto_qol_military_buttons.txt")
        cls.effects = read("common/scripted_effects/auto_qol_fleet_scripted_effects.txt")
        cls.effects += read("common/scripted_effects/auto_qol_military_gui_effects.txt")
        cls.static = read("common/static_modifiers/auto_qol_static_modifiers.txt")
        cls.static += read("common/static_modifiers/auto_qol_automation_ratio_modifiers.txt")

    def runtime(self, variables=None):
        return Runtime(self.effects, self.static, variables)

    def click(self, runtime, name):
        definition = named(self.buttons, name + " = {")
        # The player checks must also be scoped to From, independent of selection.
        guard = [("from", "=", [("is_ai", "=", "no")])]
        self.assertEqual(field(definition, "potential"), guard)
        self.assertEqual(field(definition, "allow"), guard)
        body = field(field(definition, "effect"), "hidden_effect")
        self.assertEqual(len(body), 1)
        self.assertEqual(body[0][0], "from")
        runtime.run(body[0][2])
        self.assertEqual(runtime.events, [], "Adjusting must not queue another window")

    def test_every_step_applies_clamps_and_resets_only_own_bonus(self):
        for feature, amounts in EXPECTED.items():
            variable = "qol_custom_" + feature
            own_modifier = variable + "_modifier"
            for amount in amounts:
                with self.subTest(feature=feature, amount=amount):
                    runtime = self.runtime()
                    self.click(runtime, f"auto_qol_military_{feature}_add_{amount}")
                    self.assertEqual(runtime.variables[variable], amount)
                    self.assertIn(own_modifier, runtime.modifiers)
                    # Stacking and overshoot exercise the real scripted clamp.
                    self.click(runtime, f"auto_qol_military_{feature}_add_{amount}")
                    self.assertEqual(runtime.variables[variable], min(100, 2 * amount) if feature == "automated_ratio" else 2 * amount)
                    for _ in range(3):
                        self.click(runtime, f"auto_qol_military_{feature}_sub_{amount}")
                    self.assertEqual(runtime.variables[variable], 0)
                    self.assertNotIn(own_modifier, runtime.modifiers)
                    self.click(runtime, f"auto_qol_military_{feature}_add_{amount}")
                    self.click(runtime, f"auto_qol_military_{feature}_reset")
                    self.assertNotIn(own_modifier, runtime.modifiers)
                    self.assertEqual(runtime.modifiers["unrelated"], {"bonus": 17})

    def test_megastructure_bonuses_use_generic_modifiers_and_reset_independently(self):
        runtime = self.runtime()
        runtime.modifiers['aow_existing'] = {'megastructure_build_speed_mult': 1.0}
        runtime.modifiers['aow_production'] = {'megastructures_produces_mult': 1.0}
        self.click(runtime, 'auto_qol_military_mega_build_speed_add_200')
        self.click(runtime, 'auto_qol_military_mega_construction_add_5')
        self.assertEqual(runtime.modifiers['qol_custom_mega_build_speed_modifier'], {'megastructure_build_speed_mult': 2.0})
        self.assertEqual(runtime.modifiers['qol_custom_mega_construction_modifier'], {'country_megastructure_build_cap_add': 5.0})
        self.click(runtime, 'auto_qol_military_mega_build_speed_reset')
        self.assertNotIn('qol_custom_mega_build_speed_modifier', runtime.modifiers)
        self.assertEqual(runtime.modifiers['aow_existing'], {'megastructure_build_speed_mult': 1.0})
        self.assertIn('qol_custom_mega_construction_modifier', runtime.modifiers)
        self.click(runtime, 'auto_qol_military_mega_production_add_100')
        self.assertEqual(runtime.modifiers['qol_custom_mega_production_modifier'], {'megastructures_produces_mult': 1.0})
        self.click(runtime, 'auto_qol_military_mega_production_reset')
        self.assertNotIn('qol_custom_mega_production_modifier', runtime.modifiers)
        self.assertEqual(runtime.modifiers['aow_production'], {'megastructures_produces_mult': 1.0})
        self.assertIn('qol_custom_mega_construction_modifier', runtime.modifiers)

    def test_automation_ratio_and_efficiency_are_independent_and_preserve_external_sources(self):
        from automated_workforce import jobs, generate as generate_ratio
        eligible = jobs()
        for name in ('technician', 'miner', 'farmer', 'alloy_drone', 'physicist'):
            self.assertIn(name, eligible)
        for name in ('telepath_drone', 'test_subject', 'criminal', 'civilian', 'assimilation'):
            self.assertNotIn(name, eligible)
        self.assertEqual(read('common/static_modifiers/auto_qol_automation_ratio_modifiers.txt'), generate_ratio())
        runtime = self.runtime()
        runtime.modifiers['automation_building'] = {'job_technician_automated_workforce_mult': 0.25}
        self.click(runtime, 'auto_qol_military_automated_ratio_add_25')
        self.click(runtime, 'auto_qol_military_automated_output_add_100')
        ratio = runtime.modifiers['qol_custom_automated_ratio_modifier']
        self.assertEqual(ratio['job_technician_automated_workforce_mult'], 0.25)
        self.assertEqual(ratio['job_alloy_drone_automated_workforce_mult'], 0.25)
        self.assertEqual(runtime.modifiers['qol_custom_automated_output_modifier'], {'bonus_automated_workforce_mult': 1.0})
        self.click(runtime, 'auto_qol_military_automated_ratio_add_100')
        self.assertEqual(runtime.variables['qol_custom_automated_ratio'], 100)
        runtime.run(named(self.effects, 'auto_qol_military_prepare = {'))
        self.assertEqual(runtime.modifiers['qol_custom_automated_ratio_modifier']['job_technician_automated_workforce_mult'], 1.0)
        self.click(runtime, 'auto_qol_military_automated_ratio_reset')
        self.assertNotIn('qol_custom_automated_ratio_modifier', runtime.modifiers)
        self.assertIn('qol_custom_automated_output_modifier', runtime.modifiers)
        self.assertEqual(runtime.modifiers['automation_building'], {'job_technician_automated_workforce_mult': 0.25})
        self.click(runtime, 'auto_qol_military_automated_ratio_add_10')
        self.click(runtime, 'auto_qol_military_automated_output_reset')
        self.assertIn('qol_custom_automated_ratio_modifier', runtime.modifiers)
        self.assertNotIn('qol_custom_automated_output_modifier', runtime.modifiers)

    def test_automation_uses_native_efficiency_and_preserves_other_sources(self):
        from paths import GAME_INSTALL_DIR
        from build_smart_council_system import strip_comments
        technologies = strip_comments((GAME_INSTALL_DIR / 'common/technology/00_eng_tech.txt').read_text(encoding='utf-8-sig'))
        self.assertIn('bonus_automated_workforce_mult = 0.10', technologies)
        runtime = self.runtime()
        runtime.modifiers['automation_tech'] = {'bonus_automated_workforce_mult': 0.1}
        self.click(runtime, 'auto_qol_military_automated_output_add_100')
        self.assertEqual(runtime.modifiers['qol_custom_automated_output_modifier'], {'bonus_automated_workforce_mult': 1.0})
        runtime.run(named(self.effects, 'auto_qol_military_prepare = {'))
        self.assertEqual(runtime.variables['qol_custom_automated_output'], 100)
        self.assertEqual(runtime.modifiers['qol_custom_automated_output_modifier'], {'bonus_automated_workforce_mult': 1.0})
        self.click(runtime, 'auto_qol_military_automated_output_reset')
        self.assertNotIn('qol_custom_automated_output_modifier', runtime.modifiers)
        self.assertEqual(runtime.modifiers['automation_tech'], {'bonus_automated_workforce_mult': 0.1})
        gui_windows = [v for k, _, v in field(parse(self.gui), 'guiTypes') if k == 'containerWindowType' and field(v, 'name').endswith('_window')]
        self.assertEqual(len(gui_windows), 3)
        planet = next(v for v in gui_windows if field(v, 'name') == 'auto_qol_military_planet_window')
        mega = next(v for v in gui_windows if field(v, 'name') == 'auto_qol_military_mega_window')
        self.assertIn('auto_qol_military_automated_output_add_100', repr(planet))
        self.assertNotIn('auto_qol_military_automated_output_add_100', repr(mega))
        self.assertIn('auto_qol_military_mega_production_add_100', repr(mega))

    def test_production_category_is_registered_and_missing_definition_is_rejected(self):
        from tempfile import TemporaryDirectory
        from build_release_profiles import validate_megastructure_production_category, CORE_FILES
        relative = "common/economic_categories/01_auto_qol_megastructure_categories.txt"
        self.assertIn(relative, CORE_FILES)
        from paths import GAME_INSTALL_DIR
        from build_smart_council_system import find_matching_brace, strip_comments
        original_text = strip_comments((GAME_INSTALL_DIR / "common/economic_categories/00_common_categories.txt").read_text(encoding='utf-8-sig'))
        start = re.search(r'(?m)^megastructures\s*=\s*\{', original_text).start()
        opening = original_text.index('{', start)
        original = original_text[start:find_matching_brace(original_text, opening) + 1]
        category = strip_comments(read(relative))
        # Preserve the full vanilla category definition, adding only 'produces'.
        expected = original.replace('cost', 'cost produces', 1)
        self.assertEqual(re.sub(r'\s+', '', category), re.sub(r'\s+', '', expected))
        scratch = ROOT / 'scratch'
        scratch.mkdir(exist_ok=True)
        with TemporaryDirectory(dir=scratch) as directory:
            root = Path(directory)
            self.assertIn(ROOT.resolve(), root.resolve().parents)
            static = root / 'common/static_modifiers/auto_qol_static_modifiers.txt'
            static.parent.mkdir(parents=True)
            static.write_text('test = { megastructures_produces_mult = 0.01 }', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'requires megastructures'):
                validate_megastructure_production_category(root)
            target = root / relative
            target.parent.mkdir(parents=True)
            target.write_text(read(relative), encoding='utf-8')
            validate_megastructure_production_category(root)

    def test_open_preserves_saved_values_and_migrates_old_starbase_once(self):
        runtime = self.runtime({"qol_custom_navy_cap": 1750,
                                "qol_custom_starbase_module_speed": 50,
                                "qol_custom_starbase_upgrade_speed": 200})
        runtime.variables['qol_custom_mega_production'] = 200
        prepare = named(self.effects, "auto_qol_military_prepare = {")
        runtime.run(prepare)
        self.assertEqual(runtime.variables["qol_custom_navy_cap"], 1750)
        self.assertEqual(runtime.modifiers['qol_custom_mega_production_modifier'], {'megastructures_produces_mult': 2.0})
        self.assertEqual(runtime.variables["qol_custom_starbase_module_speed"], 200)
        self.assertEqual(runtime.variables["qol_custom_starbase_upgrade_speed"], 0)
        self.click(runtime, "auto_qol_military_starbase_module_speed_reset")
        runtime.run(prepare)
        self.assertEqual(runtime.variables["qol_custom_starbase_module_speed"], 0)

    def test_reset_preserves_other_rows_without_global_action_buttons(self):
        runtime = self.runtime()
        self.click(runtime, "auto_qol_military_planet_jobs_speed_add_25")
        self.click(runtime, "auto_qol_military_ship_build_speed_add_200")
        self.click(runtime, "auto_qol_military_navy_cap_add_500")
        self.click(runtime, "auto_qol_military_cmd_limit_add_100")
        self.click(runtime, "auto_qol_military_navy_cap_reset")
        self.assertEqual(runtime.variables["qol_custom_navy_cap"], 0)
        self.assertEqual(runtime.variables["qol_custom_cmd_limit"], 100)
        self.assertEqual(runtime.modifiers["qol_custom_planet_jobs_speed_modifier"], {"planet_jobs_produces_mult": 0.25})
        self.assertEqual(runtime.variables["qol_custom_ship_build_speed"], 200)
        for removed in ("auto_qol_military_preset", "auto_qol_military_clear_fleet"):
            self.assertNotIn(removed, self.gui)
            self.assertNotIn(removed, self.buttons)

    def test_all_action_buttons_resolve_and_fit_without_overlap(self):
        windows = [v for k, o, v in field(parse(self.gui), "guiTypes")
                   if k == "containerWindowType" and field(v, "name") in
                   ("auto_qol_military_window", "auto_qol_military_planet_window", "auto_qol_military_mega_window")]
        self.assertEqual(len(windows), 3)
        referenced = set()
        for window in windows:
            boxes = []
            for kind, _, rows in window:
                if kind != "effectButtonType" or not any(k == "effect" for k, o, v in rows):
                    continue
                effect = field(rows, "effect")
                self.assertIn(effect + " = {", self.buttons)
                self.assertNotIn(effect, referenced)
                referenced.add(effect)
                pos = {k: int(v) for k, o, v in field(rows, "position")}
                size = {k: int(v) for k, o, v in field(rows, "size")}
                x, y, w, h = pos["x"], pos["y"], size["x"], size["y"]
                self.assertTrue(0 <= x < x + w <= 1030 and 0 <= y < y + h <= 600)
                for bx, by, bw, bh in boxes:
                    self.assertFalse(x < bx + bw and x + w > bx and y < by + bh and y + h > by)
                boxes.append((x, y, w, h))
        self.assertEqual(len(referenced), 174)
        self.assertEqual(referenced, {k for k, o, v in parse(self.buttons)})
        events = read("events/auto_qol_military_gui_events.txt")
        pages = {field(v, "id"): v for k, o, v in parse(events) if k == "country_event"}
        self.assertIn("auto_qol_military.3", pages)
        self.assertIn("auto_qol_military.3", repr(pages["auto_qol_military.1"]))
        self.assertIn("auto_qol_military.4", repr(pages["auto_qol_military.3"]))
        self.assertIn("auto_qol_military.1", repr(pages["auto_qol_military.4"]))

    def test_native_event_text_and_option_list_have_scrollbars(self):
        # 4.5.3 resets alien_message scrolling during event construction, even
        # offscreen. A missing scrollbar dereferences null (observed crash).
        window = next(v for k, o, v in field(parse(self.gui), "guiTypes")
                      if k == "containerWindowType" and field(v, "name") == "auto_qol_military_window")
        message = next(v for k, o, v in window if k == "instantTextBoxType" and field(v, "name") == "alien_message")
        self.assertEqual(field(message, "scrollbarType"), "standardtext_slider")
        self.assertGreater(int(field(message, "maxHeight")), 0)
        native = next(v for k, o, v in window if k == "containerWindowType" and field(v, "name") == "EVENT_DIPLO")
        listing = field(native, "listBoxType")
        self.assertEqual(field(listing, "scrollbarType"), "standardlistbox_slider")
        self.assertNotIn('"invisible_horizontal_slider"', self.gui)
        self.assertNotIn("smoothListBoxType", self.gui)
        # Four native navigation options fit without overflowing or scrolling.
        types = field(parse(self.gui), "guiTypes")
        option = next(v for k, o, v in types if field(v, "name") == "auto_qol_military_option")
        width = int(field(field(option, "size"), "width"))
        spacing = int(field(listing, "spacing"))
        available = int(field(field(listing, "size"), "x"))
        self.assertLessEqual(3 * width + 2 * spacing, available)
        for slot in range(3):
            template = next(v for k, o, v in types if field(v, "name") == f"auto_qol_military_footer_{slot}")
            control = field(template, "buttonType")
            pos = {k:int(v) for k,o,v in field(control, "position")}
            self.assertEqual(slot + pos["y"], 0)
            self.assertLessEqual(pos["x"] + 300, available)
        pages = {field(v, "id"):v for k,o,v in parse(read("events/auto_qol_military_gui_events.txt")) if k == "country_event"}
        for page_id in ("auto_qol_military.1", "auto_qol_military.3", "auto_qol_military.4"):
            options = [v for k,o,v in pages[page_id] if k == "option"]
            self.assertEqual([field(v, "custom_gui") for v in options], [f"auto_qol_military_footer_{i}" for i in range(3)])

    def test_entry_navigation_localisation_and_packaging(self):
        events = read("events/auto_qol_military_gui_events.txt")
        event = next(v for k, o, v in parse(events) if k == "country_event"
                     and any(key == "custom_gui" for key, _, value in v))
        self.assertEqual(field(event, "trigger"), [("is_ai", "=", "no")])
        self.assertEqual(field(event, "custom_gui"), "auto_qol_military_window")
        self.assertEqual(field(event, "custom_gui_option"), "auto_qol_military_option")
        self.assertIn('id = auto_qol_military.1', read("events/auto_qol_menu_events.txt"))
        self.assertNotIn('id = auto_qol_hub.2', events)
        self.assertIn('id = auto_qol_menu.1', events)
        keys = set()
        for path in (ROOT / "localisation").rglob("*.yml"):
            keys.update(re.findall(r'^\s*(\S+):\d+\s+"', path.read_text(encoding="utf-8-sig"), re.M))
        references = {k for k in collect_localisation_references(ROOT) if k.startswith("auto_qol_military")}
        self.assertTrue(references)
        self.assertFalse(references - keys)
        from build_release_profiles import CORE_FILES
        for relative in generate():
            if not relative.endswith(".yml"):
                self.assertIn(relative, CORE_FILES)

    def test_unaccepted_gui_cannot_open_from_the_normal_menu(self):
        with patch("build_military_gui.GUI_ACCEPTED", False):
            events = generate()["events/auto_qol_military_gui_events.txt"]
        fallback = named(events, "country_event = {")
        self.assertEqual(field(fallback, "id"), "auto_qol_military.1")
        self.assertEqual(field(fallback, "hide_window"), "yes")
        self.assertFalse(any(k == "custom_gui" for k, o, v in fallback))
        immediate = field(fallback, "immediate")
        self.assertEqual(field(field(immediate, "country_event"), "id"), "auto_qol_fleet_menu.1")
        # Only a direct console/test invocation may construct the candidate GUI.
        self.assertNotIn("id = auto_qol_military.2", read("events/auto_qol_menu_events.txt"))

    def test_generated_files_are_current_and_bom_is_single(self):
        for relative, expected in generate().items():
            self.assertEqual(read(relative), expected)
            if relative.endswith(".yml"):
                data = (ROOT / relative).read_bytes()
                self.assertTrue(data.startswith(b"\xef\xbb\xbf"))
                self.assertFalse(data.startswith(b"\xef\xbb\xbf" * 2))


if __name__ == "__main__":
    unittest.main()

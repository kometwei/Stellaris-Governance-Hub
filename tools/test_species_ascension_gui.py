"""Preserve confirmation effects, conditional descriptions and profile slot caps."""
from pathlib import Path
from tempfile import TemporaryDirectory
import re
import unittest

from build_species_ascension_gui import generate, clone_visible, ROOT
from test_construction_speed import parse
from test_species_assimilation import Runtime as SpeciesRuntime, species, person
from test_ascension_slots import Empire


def field(rows, key):
    return next(v for k, _, v in rows if k == key)


def definitions(text):
    return {field(v, "id"): v for k, _, v in parse(text) if k == "country_event"}


def destinations(rows):
    result = []
    for key, _, arg in rows:
        if key == "country_event": result.append(field(arg, "id"))
        elif isinstance(arg, list): result.extend(destinations(arg))
    return list(dict.fromkeys(result))


class FeatureGuiTests(unittest.TestCase):
    def test_five_adjustment_tiers_and_fill_fit_one_page_with_footer_home(self):
        events = definitions(self.files['events/auto_qol_ascension_gui_events.txt'])
        pages = [event for event in events.values() if any(key == 'title' for key, _, _ in event)]
        self.assertEqual(len(pages), 1)
        names = [field(option, 'name') for key, _, option in pages[0] if key == 'option']
        for step in (1, 2, 4, 8, 16):
            for direction in ('decrease', 'increase'):
                suffix = '_one' if step == 1 else '' if step == 8 else '_' + str(step)
                self.assertIn('auto_qol_ascension.' + direction + suffix, names)
        self.assertIn('auto_qol_ascension.unlock', names)
        self.assertIn('auto_qol_ascension_gui_home', names)
        self.assertNotIn('auto_qol_ascension.back', names)

    def test_localisation_remapping_does_not_rename_windows_or_event_namespaces(self):
        for feature in ("assimilation", "ascension"):
            prefix = f"auto_qol_{feature}_gui"
            pages = definitions(self.files[f"events/{prefix}_events.txt"])
            for event_id, event in pages.items():
                self.assertTrue(event_id.startswith((prefix + ".", f"auto_qol_{feature}_native_page.")), event_id)
                if any(key == "title" for key, _, _ in event):
                    self.assertEqual(field(event, "custom_gui"), prefix + "_window")
                    self.assertEqual(field(event, "custom_gui_option"), prefix + "_option")
            gui_names = set(re.findall(r'\bname\s*=\s*"([^"]+)"', self.files[f"interface/{prefix}.gui"]))
            self.assertIn(prefix + "_window", gui_names)
            self.assertIn(prefix + "_option", gui_names)

    def test_build_validation_rejects_tooltip_key_used_as_window(self):
        from build_release_profiles import validate_gui_references
        scratch = ROOT / "scratch"
        scratch.mkdir(exist_ok=True)
        with TemporaryDirectory(dir=scratch) as directory:
            root = Path(directory)
            (root / "events").mkdir()
            (root / "interface").mkdir()
            (root / "events/broken.txt").write_text('country_event = { custom_gui = "auto_qol_ascension_gui_unlock_tt_window" }', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "auto_qol_ascension_gui_unlock_tt_window"):
                validate_gui_references(root)

    @classmethod
    def setUpClass(cls):
        cls.files = generate()

    def test_visible_workflows_preserve_guards_descriptions_setup_and_actions(self):
        for feature in ("assimilation", "ascension"):
            raw = definitions(clone_visible(ROOT, feature))
            shipped = definitions(self.files[f"events/auto_qol_{feature}_gui_events.txt"])
            for event_id, expected in raw.items():
                with self.subTest(event=event_id):
                    entry = shipped[event_id]
                    self.assertEqual(field(entry, "hide_window"), "yes")
                    self.assertEqual(field(entry, "trigger"), field(expected, "trigger"))
                    setup = next((v for k, _, v in expected if k == "immediate"), [])
                    self.assertEqual(field(entry, "immediate")[:len(setup)], setup)
                    pages = [shipped[key] for key in destinations(field(entry, "immediate")) if key.startswith(f"auto_qol_{feature}_native_page.")]
                    self.assertTrue(pages)
                    actual_choices = []
                    for page in pages:
                        self.assertFalse(any(k == "immediate" for k, _, _ in page))
                        self.assertEqual([row for row in page if row[0] == "desc"], [row for row in expected if row[0] == "desc"])
                        actual_choices.extend(v for k, _, v in page if k == "option" and not any(key == "custom_gui" for key, _, _ in v))
                    self.assertEqual(actual_choices, [v for k, _, v in expected if k == "option"])
            self.assertNotIn(".100", " ".join(shipped))

    def test_empty_source_does_not_block_opening_assimilation_and_monthly_hook_stays_backend(self):
        events = definitions(self.files["events/auto_qol_assimilation_gui_events.txt"])
        self.assertEqual(field(events["auto_qol_assimilation_gui.1"], "trigger"), [("is_ai", "=", "no"), ("exists", "=", "species")])
        original = definitions((ROOT / "events/auto_qol_assimilation_events.txt").read_text(encoding="utf-8-sig"))
        self.assertIn("auto_qol_assimilation.100", original)
        self.assertNotIn("auto_qol_assimilation_gui.100", events)

    def test_gui_confirmation_converts_selected_species_without_enabling_leaders(self):
        events = definitions(self.files["events/auto_qol_assimilation_gui_events.txt"])
        confirm_page = next(key for key, rows in events.items() if any(k == "option" and field(v, "name") == "auto_qol_assimilation.confirm" for k, _, v in rows))
        run = SpeciesRuntime()
        run.events = events
        alien, other = species("alien"), species("other")
        run.country.pops = [person(alien), person(other)]
        run.local["auto_qol_assimilation_candidate"] = alien
        run.option(confirm_page, "auto_qol_assimilation.confirm")
        self.assertIs(run.country.pops[0].species, run.country.species)
        self.assertIs(run.country.pops[1].species, other)
        self.assertIn("auto_qol_assimilation_enabled", run.country.flags)
        self.assertNotIn("auto_qol_assimilation_leaders", run.country.flags)

    def test_ascension_gui_uses_resolved_cap_and_remains_idempotent(self):
        text = self.files["events/auto_qol_ascension_gui_events.txt"]
        cap = int(re.search(r"@auto_qol_ascension_gui_slot_target = (\d+)", text)[1])
        events = definitions(text)
        unlock = next(v for rows in events.values() for k, _, v in rows if k == "option" and field(v, "name") == "auto_qol_ascension.unlock")
        class GuiEmpire(Empire):
            def number(self, value):
                return cap if value == "@auto_qol_ascension_gui_slot_target" else super().number(value)
        for initial in (0, 1, 7, 8, 24, 256):
            empire = GuiEmpire(initial, target=None)
            empire.run(field(definitions(clone_visible(ROOT, "ascension"))["auto_qol_ascension_gui.1"], "immediate"))
            empire.run(field(unlock, "hidden_effect"))
            self.assertEqual(empire.base + empire.bonus, max(initial, cap))
            previous = empire.bonus
            empire.run(field(unlock, "hidden_effect"))
            self.assertEqual(empire.bonus, previous)
        scratch = ROOT / "scratch"
        scratch.mkdir(exist_ok=True)
        with TemporaryDirectory(dir=scratch) as directory:
            root = Path(directory).resolve()
            self.assertIn(ROOT.resolve(), root.parents)
            (root / "events").mkdir()
            for feature in ("assimilation", "ascension"):
                data = (ROOT / f"events/auto_qol_{feature}_events.txt").read_text(encoding="utf-8-sig")
                data = re.sub(r"@auto_qol_ascension_slot_target = \d+", "@auto_qol_ascension_slot_target = 256", data)
                (root / f"events/auto_qol_{feature}_events.txt").write_text(data, encoding="utf-8")
            self.assertIn("@auto_qol_ascension_gui_slot_target = 256", generate(root)["events/auto_qol_ascension_gui_events.txt"])

    def test_generated_assets_are_current_with_native_lists_and_no_backup_links(self):
        for relative, expected in self.files.items():
            path = ROOT / relative
            self.assertEqual(path.read_text(encoding="utf-8-sig"), expected)
            self.assertNotIn("id = auto_qol_hub.2", expected)
            if path.suffix == ".gui":
                self.assertNotIn("effectButtonType", expected)
                self.assertNotIn("smoothListBoxType", expected)
                self.assertIn('name = "option_list"', expected)
            elif path.suffix == ".yml":
                self.assertTrue(path.read_bytes().startswith(b"\xef\xbb\xbf"))
                self.assertFalse(path.read_bytes().startswith(b"\xef\xbb\xbf" * 2))


if __name__ == "__main__":
    unittest.main()

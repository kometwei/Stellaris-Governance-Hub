"""Check GUI routing and preserve the existing council assignment semantics."""
import re
import unittest
from pathlib import Path

from build_council_gui import generate, visible_events, gui_id, clone_events
from build_release_profiles import collect_localisation_references
from test_construction_speed import parse
from test_leader_pool import Pool
from native_dashboard_footer import REMOVED_OPTIONS, content_rows

ROOT = Path(__file__).resolve().parents[1]


def value(rows, key):
    return next(v for k, _, v in rows if k == key)


class CouncilGuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.files = generate()
        cls.events = {value(v, "id"): v for k, _, v in parse(cls.files["events/auto_qol_council_gui_events.txt"]) if k == "country_event"}
        cls.buttons = dict((k, v) for k, _, v in parse(cls.files["common/button_effects/auto_qol_council_gui_buttons.txt"]))

    def test_every_workflow_preserves_candidate_scopes_guards_and_effects(self):
        raw = {value(v, "id"): v for k, _, v in parse(clone_events(ROOT)) if k == "country_event"}
        def destinations(rows):
            result = []
            for key, _, arg in rows:
                if key == "country_event":
                    event_id = value(arg, "id")
                    if event_id.startswith("auto_qol_council_native_page."):
                        result.append(event_id)
                elif isinstance(arg, list):
                    result.extend(destinations(arg))
            return list(dict.fromkeys(result))
        for event_id, original in raw.items():
            if not any(k == "title" for k, _, _ in original):
                self.assertEqual(self.events[event_id], original)
                continue
            with self.subTest(event=event_id):
                wrapper = self.events[event_id]
                self.assertEqual(value(wrapper, "hide_window"), "yes")
                setup = next((v for k, _, v in original if k == "immediate"), [])
                self.assertEqual(value(wrapper, "immediate")[:len(setup)], setup)
                expected = [v for k, _, v in original if k == "option" and value(v, "name") not in REMOVED_OPTIONS]
                actual = []
                page_ids = destinations(value(wrapper, "immediate"))
                self.assertTrue(page_ids)
                for page_id in page_ids:
                    page = self.events[page_id]
                    self.assertFalse(any(k == "immediate" for k, _, _ in page), "Layout paging must not regenerate leader targets")
                    self.assertEqual(value(page, "custom_gui"), "auto_qol_council_window")
                    self.assertEqual(value(page, "title"), value(original, "title"))
                    self.assertEqual(value(page, "desc"), value(original, "desc"))
                    options = [v for k, _, v in page if k == "option" and not any(key == "custom_gui" and "_nav" in arg for key, _, arg in v)]
                    self.assertLessEqual(content_rows(["option = { name = "+chr(34)+value(v,"name")+chr(34)+" }" for v in options]), 12)
                    actual.extend(options)
                self.assertEqual(actual, expected)

    def test_native_widgets_retain_required_scrollbars_and_list_capacity(self):
        types = value(parse(self.files["interface/auto_qol_council_manager.gui"]), "guiTypes")
        window = next(v for k, _, v in types if value(v, "name") == "auto_qol_council_window")
        message = next(v for k, _, v in window if k == "instantTextBoxType" and value(v, "name") == "alien_message")
        self.assertEqual(value(message, "scrollbarType"), "standardtext_slider")
        self.assertEqual(value(message, "maxHeight"), "230")
        native = next(v for k, _, v in window if k == "containerWindowType" and value(v, "name") == "EVENT_DIPLO")
        listing = value(native, "listBoxType")
        self.assertEqual(value(listing, "scrollbarType"), "standardlistbox_slider")
        self.assertEqual(value(value(listing, "size"), "y"), "524")
        note = next(v for k, _, v in window if k == "instantTextBoxType" and value(v, "name") == "council_gui_note")
        title = next(v for k, _, v in native if k == "instantTextBoxType" and value(v, "name") == "action_title")
        self.assertLessEqual(int(value(value(note, "position"), "y")) + int(value(note, "maxHeight")) + 16,
                             int(value(value(title, "position"), "y")))
        self.assertLessEqual(int(value(value(title, "position"), "y")) + int(value(title, "maxHeight")) + 16,
                             int(value(value(listing, "position"), "y")))
        close = next(v for k, _, v in window if k == "buttonType" and value(v, "name") == "close")
        self.assertEqual(value(close, "quadTextureSprite"), "GFX_main_close_button")
        self.assertEqual(value(close, "orientation"), "upper_right")
        option = next(v for k, _, v in types if value(v, "name") == "auto_qol_council_option")
        self.assertLessEqual(int(value(value(option, "size"), "width")), 986)

    def test_buttons_are_player_scoped_and_do_not_open_duplicate_windows(self):
        for name, rows in self.buttons.items():
            self.assertEqual(value(rows, "potential"), value(rows, "allow"))
            guard = value(value(rows, "potential"), "from")
            self.assertIn(("is_ai", "=", "no"), guard)
            hidden = value(value(rows, "effect"), "hidden_effect")
            self.assertEqual(len(hidden), 1)
            self.assertEqual(hidden[0][0], "from")
            self.assertNotIn("country_event", repr(hidden))
        self.assertEqual(len(self.buttons), 6)

    def test_pool_buttons_repair_empty_pool_and_trim_only_excess(self):
        effects = dict((k, v) for k, _, v in parse((ROOT / "common/scripted_effects/auto_qol_leader_pool_scripted_effects.txt").read_text(encoding="utf-8-sig")))
        for size in (0, 5, 10, 11, 200):
            pool = Pool(effects, size)
            action = value(value(value(self.buttons["auto_qol_council_gui_trim"], "effect"), "hidden_effect"), "from")
            pool.run(action)
            self.assertEqual(pool.size, 9 if size == 0 else min(size, 10))
            self.assertEqual(pool.kills, max(0, size - 10))
            repair = value(value(value(self.buttons["auto_qol_council_gui_repair"], "effect"), "hidden_effect"), "from")
            pool.run(repair)
            self.assertEqual(pool.kills, max(0, size - 10))

    def test_main_entry_localisation_and_generated_files(self):
        main = (ROOT / "events/auto_qol_menu_events.txt").read_text(encoding="utf-8-sig")
        self.assertIn("id = auto_qol_council_gui.1", main)
        self.assertIn("id = auto_qol_council_menu.1", main)
        keys = set()
        for p in (ROOT / "localisation").rglob("*.yml"):
            keys.update(re.findall(r'(?m)^\s*([^#\s][^:]*):\d+\s+"', p.read_text(encoding="utf-8-sig")))
        self.assertFalse({key for key in collect_localisation_references(ROOT) if key.startswith("auto_qol_council_gui_")} - keys)
        for relative, expected in self.files.items():
            path = ROOT / relative
            self.assertEqual(path.read_text(encoding="utf-8-sig"), expected)
            if path.suffix == ".yml":
                self.assertTrue(path.read_bytes().startswith(b"\xef\xbb\xbf"))
                self.assertFalse(path.read_bytes().startswith(b"\xef\xbb\xbf" * 2))


if __name__ == "__main__":
    unittest.main()

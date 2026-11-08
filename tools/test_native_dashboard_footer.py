"""Verify native routing, filtered pagination and setup lifetime independently."""
import unittest
from native_dashboard_footer import transform_events, transform_gui, PAGE_SIZE
from build_council_gui import dashboard_shell, DASHBOARD_LIST_Y, DASHBOARD_LIST_HEIGHT
from test_construction_speed import parse


def value(rows, key):
    return next(v for k, _, v in rows if k == key)


def matches(rows, flags):
    def check(key, arg):
        if key == "always": return arg == "yes"
        if key == "has_country_flag": return arg in flags
        if key == "AND": return matches(arg, flags)
        if key == "OR": return any(matches([row], flags) for row in arg)
        raise AssertionError(key)
    return all(check(k, v) for k, _, v in rows)


def dispatch(rows, flags):
    taken = False
    for key, _, arg in rows:
        if key == "country_event": return value(arg, "id")
        if key in ("if", "else_if"):
            if key == "if": taken = False
            if not taken and matches(value(arg, "limit"), flags):
                taken = True
                result = dispatch([row for row in arg if row[0] != "limit"], flags)
                if result: return result
        elif key == "else" and not taken:
            result = dispatch(arg, flags)
            if result: return result
    return None


class NativeFooterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = '''namespace = fixture
country_event = {
 id = fixture.1
 title = "fixture_title"
 desc = "fixture_desc"
 is_triggered_only = yes
 trigger = { is_ai = no }
 immediate = { change_variable = { which = fixture_setup value = 1 } }
'''
        for index in range(27):
            source += f'''option = {{
 name = "choice_{index}"
 trigger = {{ has_country_flag = visible_{index} }}
 change_variable = {{ which = result value = {index} }}
}}
'''
        source += 'option = { name = "auto_qol.close_direct" default_hide_option = yes }\n}\n'
        cls.text = transform_events(source, "test_footer", "fixture_page")
        cls.events = {value(v, "id"): v for k, _, v in parse(cls.text) if k == "country_event"}

    def test_skips_empty_pages_in_both_directions_and_dispatches_once(self):
        flags = {"visible_0", "visible_26"}
        start = dispatch(value(self.events["fixture.1"], "immediate"), flags)
        self.assertEqual(start, "fixture_page.1")
        first = self.events[start]
        next_option = next(v for k, _, v in first if k == "option" and value(v, "name") == "test_footer_next")
        self.assertTrue(matches(value(next_option, "trigger"), flags))
        self.assertEqual(dispatch(value(next_option, "hidden_effect"), flags), "fixture_page.3")
        last = self.events["fixture_page.3"]
        previous = next(v for k, _, v in last if k == "option" and value(v, "name") == "test_footer_prev")
        self.assertEqual(dispatch(value(previous, "hidden_effect"), flags), "fixture_page.1")
        self.assertEqual(dispatch(value(self.events["fixture.1"], "immediate"), {"visible_26"}), "fixture_page.3")
        self.assertEqual(dispatch(value(self.events["fixture.1"], "immediate"), set()), "fixture_page.1")

    def test_setup_runs_only_in_hidden_entry_and_every_choice_survives(self):
        self.assertEqual(value(self.events["fixture.1"], "hide_window"), "yes")
        self.assertEqual(self.text.count("which = fixture_setup"), 1)
        choices = []
        for event_id, rows in self.events.items():
            if not event_id.startswith("fixture_page."): continue
            self.assertFalse(any(k == "immediate" for k, _, _ in rows))
            body = [v for k, _, v in rows if k == "option" and value(v, "name").startswith("choice_")]
            self.assertLessEqual(len(body), PAGE_SIZE)
            for option in body:
                index = int(value(option, "name").split("_")[1])
                self.assertEqual(value(option, "change_variable"), [("which", "=", "result"), ("value", "=", str(index))])
                choices.append(index)
            closing = next(v for k, _, v in rows if k == "option" and value(v, "name") == "test_footer_close")
            self.assertEqual(value(closing, "default_hide_option"), "yes")
        self.assertEqual(choices, list(range(27)))

    def test_footer_geometry_fits_and_has_no_scripted_navigation_buttons(self):
        gui = transform_gui(dashboard_shell("test_window").replace("@CONTENT@", ""), "test_footer", DASHBOARD_LIST_Y, DASHBOARD_LIST_HEIGHT)
        self.assertNotIn("effectButtonType", gui)
        types = value(parse(gui), "guiTypes")
        for count in (2, 4):
            rectangles = []
            for slot in range(count):
                template = next(v for k, _, v in types if value(v, "name") == f"test_footer_nav{count}_{slot}")
                self.assertEqual(value(value(template, "size"), "height"), "0")
                btn = value(template, "buttonType")
                pos = {k:int(v) for k, _, v in value(btn, "position")}
                size = {k:int(v) for k, _, v in value(btn, "size")}
                self.assertEqual(DASHBOARD_LIST_Y + pos["y"], 668)
                self.assertLessEqual(pos["x"] + size["x"], 986)
                for x, w in rectangles: self.assertGreaterEqual(pos["x"], x + w + 8)
                rectangles.append((pos["x"], size["x"]))
        self.assertLess(DASHBOARD_LIST_Y + PAGE_SIZE * 34, 606)
        self.assertNotIn('"invisible_horizontal_slider"', gui)
        for _, _, template in types:
            if not isinstance(template, list): continue
            for kind, _, control in template:
                if kind == "overlappingElementsBoxType" and value(control, "name") in ("trigger_icons", "effect_icons"):
                    pos = {k:int(v) for k, _, v in value(control, "position")}
                    self.assertLess(pos["x"], -1000)
                    self.assertLess(pos["y"], -1000)


if __name__ == "__main__":
    unittest.main()

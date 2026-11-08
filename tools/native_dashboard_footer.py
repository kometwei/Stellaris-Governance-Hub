"""Native option-level GUI templates, validated by the two-page footer probe.

All visible transitions stay in event options. Additional body pages are separate
visible events; only the original entry wrapper runs candidate/roster setup.
This preserves local leader targets when turning a layout page.
"""
import re
from build_smart_council_system import find_matching_brace

PAGE_SIZE = 12
REMOVED_OPTIONS = {
    "auto_qol.close_direct", "auto_qol_menu.close",
    "auto_qol_council_gui_legacy", "auto_qol_council_menu.back",
    "auto_qol_hub_compat", "auto_qol_hub_back",
}


def blocks(text, key):
    cursor = 0
    while match := re.search(r"\b" + re.escape(key) + r"\s*=\s*\{", text[cursor:]):
        start = cursor + match.start()
        end = find_matching_brace(text, text.index("{", start))
        if end < 0:
            raise ValueError("Unbalanced " + key)
        yield text[start:end + 1]
        cursor = end + 1


def body(block):
    return block[block.index("{") + 1:block.rfind("}")]


def top_blocks(text, key):
    """Read event/option fields without mistaking conditional desc triggers for guards."""
    pattern = r'"(?:\\.|[^"\\])*"|#[^\n]*|[{}]|\b' + re.escape(key) + r'\s*=\s*\{'
    depth = 0
    for match in re.finditer(pattern, text):
        token = match[0]
        if token == "{":
            depth += 1
        elif token == "}":
            depth -= 1
        elif token.startswith(("#", '"')):
            continue
        else:
            if depth == 1:
                end = find_matching_brace(text, text.index("{", match.start()))
                yield text[match.start():end + 1]
            depth += 1


def conditions(options):
    clauses = []
    for option in options:
        trigger = next(top_blocks(option, "trigger"), None)
        if trigger is None:
            return "always = yes"
        clauses.append("AND = { " + body(trigger) + " }")
    return "OR = {\n" + "\n".join(clauses) + "\n}" if clauses else "always = no"


def route(pages, fallback=None):
    result = ""
    for index, (page_id, options) in enumerate(pages):
        result += ("if" if index == 0 else "else_if") + " = {\n limit = { " + conditions(options) + " }\n country_event = { id = " + page_id + " }\n}\n"
    if fallback:
        result += ("else = { " if pages else "") + "country_event = { id = " + fallback + " }" + (" }" if pages else "")
    return result


def option_name(option):
    return re.search(r'\bname\s*=\s*"([^"\n]+)"', option)[1]


def content_rows(options):
    """Count the maximum simultaneously visible rows in known pickers."""
    names = {option_name(option) for option in options}
    starbases = {name for name in names if re.fullmatch(r"auto_qol_starbase_clear_slot_\d+", name)}
    starbase_navigation = {"auto_qol_starbase_clear_more", "auto_qol_starbase_clear_restart", "auto_qol_starbase_clear_empty"}
    if starbases and names - starbases == starbase_navigation:
        # More/restart are mutually exclusive; empty replaces all candidates.
        # Ten bases plus one batch action fit without a separate layout page.
        return max(len(starbases) + 1, 1)
    candidates = {name for name in names if re.fullmatch(r"auto_qol_assign\.cand_\d+", name)}
    navigation = {"auto_qol_assign.no_candidate", "auto_qol_assign.refresh", "auto_qol_assign.restart", "auto_qol_assign.back_to_cat"}
    if candidates and names - candidates == navigation:
        # With candidates: N rows + refresh OR restart + back. Without candidates:
        # no-candidate + back. Both navigation actions require candidate flag 1.
        return max(len(candidates) + 2, 2)
    return len(options)


def footer_option(prefix, slot, count, suffix, effect="", trigger="", close=False):
    return f'''option = {{
 name = "{prefix}_{suffix}"
 custom_gui = "{prefix}_nav{count}_{slot}"
''' + (" trigger = { " + trigger + " }\n" if trigger else "") + (" hidden_effect = {\n" + effect + "\n }\n" if effect else "") + (" default_hide_option = yes\n" if close else "") + "}\n"


def transform_events(script, prefix, page_namespace):
    originals = list(blocks(script, "country_event"))
    output = script[:script.index("country_event")] + f"namespace = {page_namespace}\n"
    page_number = 1
    for original in originals:
        if not re.search(r"(?m)^\s*title\s*=", original):
            output += original + "\n"
            continue
        event_id = re.search(r"(?m)^\s*id\s*=\s*(\w+\.\d+)", original)[1]
        header = original
        choices = []
        for option in top_blocks(original, "option"):
            header = header.replace(option, "", 1)
            if option_name(option) not in REMOVED_OPTIONS:
                choices.append(option)
        immediate = next(top_blocks(header, "immediate"), None)
        if immediate:
            header = header.replace(immediate, "", 1)
        trigger = next(top_blocks(header, "trigger"), None)
        guard = body(trigger) if trigger else "is_ai = no"
        chunks = [choices] if content_rows(choices) <= PAGE_SIZE else [choices[i:i + PAGE_SIZE] for i in range(0, len(choices), PAGE_SIZE)]
        pages = [(f"{page_namespace}.{page_number + i}", chunk) for i, chunk in enumerate(chunks)]
        page_number += len(pages)
        output += f'''country_event = {{
 id = {event_id}
 hide_window = yes
 is_triggered_only = yes
 trigger = {{ {guard} }}
 immediate = {{
''' + (body(immediate) if immediate else "") + "\n" + route(pages, pages[0][0]) + "\n }\n}\n"
        for index, (page_id, chunk) in enumerate(pages):
            current = re.sub(r"\bid\s*=\s*" + re.escape(event_id) + r"\b", "id = " + page_id, header, count=1)
            count = 4 if len(pages) > 1 else 2
            navigation = ""
            if count == 4:
                previous = list(reversed(pages[:index]))
                following = pages[index + 1:]
                if previous:
                    navigation += footer_option(prefix, 0, count, "prev", route(previous, pages[0][0]), conditions(["option = { trigger = { " + conditions(opts) + " } }" for _, opts in previous]))
                if following:
                    navigation += footer_option(prefix, 1, count, "next", route(following, pages[-1][0]), conditions(["option = { trigger = { " + conditions(opts) + " } }" for _, opts in following]))
            base = count - 2
            navigation += footer_option(prefix, base, count, "home", "country_event = { id = auto_qol_menu.1 }")
            navigation += footer_option(prefix, base + 1, count, "close", close=True)
            current = current[:current.rfind("}")] + navigation + "\n".join(chunk) + "\n}\n"
            output += current
    return output


def transform_gui(gui, prefix, list_y, list_height):
    gui = gui.replace("width = 630 height = 34", "width = 986 height = 34")
    gui = gui.replace("position = { x = 0 y = 0 }", "position = { x = 330 y = 0 }", 1)
    gui = gui.replace(f"x = 352 y = {list_y}", f"x = 22 y = {list_y}")
    gui = gui.replace(f"x = 650 y = {list_height}", f"x = 986 y = {708 - list_y}")
    gui = gui.replace('spacing = 2\n    scrollbarType = "standardlistbox_slider"', 'spacing = 0\n    scrollbarType = "standardlistbox_slider"')
    templates = ""
    for count, width, stride in ((2, 300, 330), (4, 235, 247)):
        for slot in range(count):
            templates += f'''
 containerWindowType = {{
  name = "{prefix}_nav{count}_{slot}"
  position = {{ x = 0 y = 0 }}
  size = {{ width = 986 height = 0 }}
  moveable = no
  buttonType = {{
   name = "option_button"
   quadTextureSprite = "GFX_button_light"
   position = {{ x = {slot * stride + (165 if count == 2 else 0)} y = {668 - list_y} }}
   size = {{ x = {width} y = 32 }}
   font = "cg_16b"
   text = "OPTION_TEXT"
  }}
  overlappingElementsBoxType = {{ name = "trigger_icons" position = {{ x = -10000 y = -10000 }} size = {{ x = 0 y = 0 }} }}
  overlappingElementsBoxType = {{ name = "effect_icons" position = {{ x = -10000 y = -10000 }} size = {{ x = 0 y = 0 }} }}
 }}
'''
    return gui[:gui.rfind("}")] + templates + "}\n"

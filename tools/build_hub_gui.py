"""Generate the central dashboard and compatibility page from legacy menu actions.

auto_qol_menu.1 remains the stable entry/return ID, forwarding to the dashboard.
The original menu lives at .900; its self-refreshes never reopen the dashboard.
"""
from pathlib import Path
import re

from build_council_gui import dashboard_shell, DASHBOARD_LIST_Y, DASHBOARD_LIST_HEIGHT
from native_dashboard_footer import transform_events, transform_gui
from build_military_gui import button, text_box
from build_smart_council_system import find_matching_brace
from console_home_cards import CARDS, decorate_events, decorate_gui

ROOT = Path(__file__).resolve().parents[1]
MENU = "events/auto_qol_menu_events.txt"
VISIBLE = {
    "auto_qol_military_open", "auto_qol_council_gui_open",
    "auto_qol_menu.ascension_slots", "auto_qol_menu.assimilation",
    "auto_qol_menu.planet_ascension_10",
    "auto_qol_menu.tradition_menu",
    "auto_qol_menu.psionic_bundle_ready", "auto_qol_menu.psionic_bundle_complete",
    "auto_qol_menu.psionic_bundle_locked",
}


# Keep related construction tools together, followed by administration and ascension.
MODULE_ORDER = (
    "auto_qol_military_open",
    "auto_qol_hub_megastructures",
    "auto_qol_hub_starbase_clear",
    "auto_qol_council_gui_open",
    "auto_qol_menu.assimilation",
    "auto_qol_menu.ascension_slots",
    "auto_qol_menu.planet_ascension_10",
    "auto_qol_menu.psionic_bundle_ready",
    "auto_qol_menu.psionic_bundle_complete",
    "auto_qol_menu.psionic_bundle_locked",
    "auto_qol_menu.tradition_menu",
)


def events(text):
    cursor = 0
    while match := re.search(r"\bcountry_event\s*=\s*\{", text[cursor:]):
        start = cursor + match.start()
        opening = text.index("{", start)
        end = find_matching_brace(text, opening)
        if end < 0:
            raise ValueError("Unbalanced menu event")
        yield text[start:end + 1]
        cursor = end + 1


def event_id(block):
    return re.search(r"(?m)^\s*id\s*=\s*(\w+\.\d+)", block)[1]


def ensure_router(root):
    path = Path(root) / MENU
    text = path.read_text(encoding="utf-8-sig")
    if any(event_id(block) == "auto_qol_menu.900" for block in events(text)):
        return
    # Rehome only the original main menu and its self-refresh IDs. All external
    # return paths continue to use .1 and therefore land at the new dashboard.
    text = re.sub(r"\bid\s*=\s*auto_qol_menu\.1\b", "id = auto_qol_menu.900", text)
    text += '''
# Stable entry for the edict and existing module return buttons.
country_event = {
 id = auto_qol_menu.1
 hide_window = yes
 is_triggered_only = yes
 trigger = { is_ai = no }
 immediate = { country_event = { id = auto_qol_hub.1 } }
}
'''
    path.write_text(text, encoding="utf-8")


def extract_options(block):
    cursor = 0
    while match := re.search(r"\boption\s*=\s*\{", block[cursor:]):
        start = cursor + match.start()
        end = find_matching_brace(block, block.index("{", start))
        if end < 0:
            raise ValueError("Unbalanced menu option")
        yield block[start:end + 1]
        cursor = end + 1


def native_option(key, destination):
    return f''' option = {{
  name = "{key}"
  hidden_effect = {{ country_event = {{ id = {destination} }} }}
 }}
'''


def generate(root=ROOT):
    root = Path(root)
    legacy = next(block for block in events((root / MENU).read_text(encoding="utf-8-sig")) if event_id(block) == "auto_qol_menu.900")
    options = []
    for option in extract_options(legacy):
        key = re.search(r'\bname\s*=\s*"([^"]+)"', option)[1]
        if key in VISIBLE:
            targets = {"auto_qol_menu.900": "auto_qol_hub.1", "auto_qol_assimilation.1": "auto_qol_assimilation_gui.1", "auto_qol_ascension.1": "auto_qol_ascension_gui.1"}
            options.append(re.sub(r"\bid\s*=\s*(\w+\.\d+)", lambda m: "id = " + targets.get(m[1], m[1]), option))
    options.append(native_option("auto_qol_hub_megastructures", "auto_qol_mega.1"))
    options.append(native_option("auto_qol_hub_starbase_clear", "auto_qol_starbase_clear.1"))
    rank = {key: index for index, key in enumerate(MODULE_ORDER)}
    options.sort(key=lambda option: rank[re.search(r'\bname\s*=\s*"([^"]+)"', option)[1]])
    # Keep the migration/repair behaviour of opening the old main menu.
    match = re.search(r"\bimmediate\s*=\s*\{", legacy)
    immediate = legacy[match.start():find_matching_brace(legacy, legacy.index("{", match.start())) + 1] if match else ""
    definitions = []
    content = text_box("hub_title", "auto_qol_hub_title", 22, 24, 786, 30, "malgun_goth_24")
    content += text_box("hub_construction", "auto_qol_hub_construction", 22, 96, 406)
    content += text_box("hub_governance", "auto_qol_hub_governance", 452, 96, 406)
    content += text_box("hub_settings", "auto_qol_hub_settings", 22, 402, 836)
    loc = {
        "title": "星政中枢",
        "note": "帝国控制台  /  总览     选择模块进入管理，设置与加成沿用当前存档。",
        "modules": "功能模块",
        "megastructures": "巨构工程署",
        "starbase_clear": "恒星基地清空",
        "desc": "选择模块进入管理。",
        "settings": "快捷开关",
        "construction": "§H建设与军备§!",
        "governance": "§H治理与飞升§!",
        "envoy_on": "£trigger_yes£ §G【已开启】§! 遭遇 AI 通讯",
        "envoy_off": "§L【已关闭】遭遇 AI 通讯§!",
        "pool_on": "£trigger_yes£ §G【已开启】§! 领袖池优化",
        "pool_off": "§L【已关闭】领袖池优化§!",
        "footer": "快捷开关点击立即生效。\\n候选裁剪、领袖池修复与内阁专注协议，可进入“内阁与领袖”管理。",
        "back": "返回星政中枢首页",
        "home": "返回星政中枢首页",
        "close": "关闭面板（Esc）",
        "prev": "← 上一页",
        "next": "下一页 →",
    }

    loc.update({f"summary_{i}": summary for i, (_, summary) in enumerate(CARDS)})

    def toggle(suffix, condition, effect, tooltip):
        name = "auto_qol_hub_" + suffix
        definitions.append(f'''{name} = {{
 potential = {{ from = {{ is_ai = no {condition} }} }}
 allow = {{ from = {{ is_ai = no {condition} }} }}
 effect = {{
  custom_tooltip = "{tooltip}"
  hidden_effect = {{ from = {{ {effect} }} }}
 }}
}}
''')
        return button(name, name, 22 if suffix.startswith("envoy") else 452, 436, 406, name)

    content += toggle("envoy_on", "has_country_flag = auto_envoy_enabled", "remove_country_flag = auto_envoy_enabled", "auto_qol_menu.toggle_envoy_tt")
    content += toggle("envoy_off", "NOT = { has_country_flag = auto_envoy_enabled }", "set_country_flag = auto_envoy_enabled country_event = { id = auto_envoy.100 }", "auto_qol_menu.toggle_envoy_tt")
    content += toggle("pool_on", "has_country_flag = leader_pool_opt_enabled", "remove_country_flag = leader_pool_opt_enabled auto_qol_repair_leader_pool = yes", "auto_qol_menu.toggle_leader_opt_tt")
    content += toggle("pool_off", "NOT = { has_country_flag = leader_pool_opt_enabled }", "set_country_flag = leader_pool_opt_enabled auto_qol_repair_leader_pool = yes auto_qol_trim_leader_pool_to_10 = yes", "auto_qol_menu.toggle_leader_opt_tt")
    gui = dashboard_shell("auto_qol_hub").replace("@CONTENT@", content)
    home_list_y = 124
    gui = gui.replace(f"x = 352 y = {DASHBOARD_LIST_Y}", f"x = 352 y = {home_list_y}")
    opening = '''# Generated by tools/build_hub_gui.py
namespace = auto_qol_hub
country_event = {
 id = auto_qol_hub.1
 diplomatic = yes
 custom_gui = "auto_qol_hub_window"
 custom_gui_option = "auto_qol_hub_option"
 title = "auto_qol_hub_modules"
 desc = "auto_qol_hub_desc"
 is_triggered_only = yes
 trigger = { is_ai = no }
'''
    opening += immediate + "\n" + "\n".join(options)
    closing = ' option = { name = "auto_qol.close_direct" default_hide_option = yes }\n}\n'
    opening += closing
    return {
        "interface/auto_qol_hub.gui": decorate_gui(transform_gui(gui, "auto_qol_hub", home_list_y, DASHBOARD_LIST_HEIGHT), home_list_y),
        "events/auto_qol_hub_gui_events.txt": decorate_events(transform_events(opening, "auto_qol_hub", "auto_qol_hub_native_page")),
        "common/button_effects/auto_qol_hub_buttons.txt": "\n".join(definitions),
        "localisation/simp_chinese/auto_qol_hub_gui_l_simp_chinese.yml": "l_simp_chinese:\n" + "".join(f' auto_qol_hub_{key}:0 "{value}"\n' for key, value in loc.items()),
    }


def build(root=ROOT):
    root = Path(root)
    ensure_router(root)
    for relative, content in generate(root).items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8-sig" if path.suffix == ".yml" else "utf-8")


if __name__ == "__main__":
    build()
    print("Generated central GUI dashboard and compatibility page.")

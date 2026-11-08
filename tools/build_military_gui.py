"""Generate the military/construction event GUI. No game installation required.

Uses the native diplomatic-event widget names and effectButtonType contract.
Buttons always execute in From (the player country), never the selected object.
"""
from pathlib import Path
from console_theme import chrome, panel

ROOT = Path(__file__).resolve().parents[1]
PREFIX = "auto_qol_military"
# 2026-11-07: user confirmed corrected window opens in 4.5.3 with a screenshot.
# Close/reopen persistence and other UI scales still need explicit verification.
GUI_ACCEPTED = True
ROWS = (
    ("navy_cap", "舰队容量", (500, 1000, 2500, 5000, 10000, 50000), ""),
    ("cmd_limit", "舰队指挥上限", (50, 100, 200, 500, 1000, 5000), ""),
    ("starbase_module_speed", "恒星基地建设速度", (50, 100, 200, 500, 1000, 2000), "%"),
    ("defense_platform_speed", "防御平台建造速度", (50, 100, 200, 500, 1000, 2000), "%"),
    ("army_recruit_speed", "陆军招募速度", (50, 100, 200, 500, 1000, 2000), "%"),
    ("ship_build_speed", "舰船建造速度", (50, 100, 200, 500, 1000, 2000), "%"),
    ("planet_construction", "星球额外同时施工数", (1, 2, 5, 10), ""),
    ("planet_build_speed", "星球建设速度", (50, 100, 200, 500, 1000, 2000), "%"),
    ("planet_jobs_speed", "星球岗位产出", (10, 25, 50, 100, 200, 1000), "%"),
    ("automated_ratio", "岗位自动化额外比例", (1, 5, 10, 25, 50, 100), "%"),
    ("automated_output", "自动化岗位产出（效率）", (10, 25, 50, 100, 200, 1000), "%"),
    ("mega_build_speed", "巨构建造速度", (50, 100, 200, 500, 1000, 2000), "%"),
    ("mega_construction", "巨构额外同时施工数", (1, 2, 5, 10), ""),
    ("mega_production", "巨构资源产出", (10, 25, 50, 100, 200, 1000), "%"),
)

# Native diplomatic event binding requires these named controls, even when unused.
# Keep unused controls outside the window; never override a vanilla GUI definition.
SHELL = '''guiTypes = {
 containerWindowType = {
  name = "auto_qol_military_option"
  size = { width = 290 height = 30 }
  buttonType = {
   name = "option_button"
   quadTextureSprite = "GFX_button_light"
   position = { x = 0 y = 0 }
   size = { x = 290 y = 28 }
   font = "cg_16b"
   text = "OPTION_TEXT"
  }
  overlappingElementsBoxType = { name = "trigger_icons" position = { x = -10000 y = -10000 } size = { x = 0 y = 0 } }
  overlappingElementsBoxType = { name = "effect_icons" position = { x = -10000 y = -10000 } size = { x = 0 y = 0 } }
 }
 containerWindowType = {
  name = "auto_qol_military_window"
  orientation = center
  origo = center
  moveable = yes
  size = { width = 1030 height = 720 }
  background = { name = "background" quadTextureSprite = "GFX_tile_large_bg" }
  buttonType = {
   name = "close"
   quadTextureSprite = "GFX_main_close_button"
   orientation = upper_right
   position = { x = -57 y = 14 }
   shortcut = "ESCAPE"
   clicksound = "back_click"
  }
  buttonType = { name = "focus_button" spriteType = "GFX_fleetview_focus" position = { x = -10000 y = -10000 } }
  buttonType = { name = "tts_button" spriteType = "GFX_button_tts_start" position = { x = -10000 y = -10000 } }
  instantTextBoxType = { name = "heading" font = "malgun_goth_24" position = { x = -10000 y = -10000 } }
  buttonType = { name = "alien_message_background" spriteType = "GFX_tiles_dark_area_cut_8" position = { x = -10000 y = -10000 } }
  # Native event code resets this text box's scroll position on opening.
  # Its scrollbar must exist even while the text box is offscreen.
  instantTextBoxType = {
   name = "alien_message"
   font = "cg_16b"
   position = { x = -10000 y = -10000 }
   maxWidth = 465
   maxHeight = 220
   format = left
   scrollbarType = "standardtext_slider"
  }
  buttonType = { name = "confirm_button" quadTextureSprite = "GFX_standard_button_142_34_button" position = { x = -10000 y = -10000 } }
  containerWindowType = {
   name = "portrait_background"
   position = { x = -10000 y = -10000 }
   iconType = { name = "event_picture" spriteType = "GFX_diplomacy_portrait_frame" }
   iconType = { name = "portrait" spriteType = "GFX_portrait_character" }
  }
  containerWindowType = {
   name = "portrait"
   position = { x = -10000 y = -10000 }
   iconType = { name = "portrait" spriteType = "GFX_portrait_gamesetup_mask" }
   iconType = { name = "black_frame" spriteType = "GFX_diplomacy_portrait_shadow_frame" }
   iconType = { name = "stripes_1" spriteType = "GFX_diplomacy_stripes_2" }
   iconType = { name = "city_frame" spriteType = "GFX_diplomacy_portrait_frame" }
  }
  iconType = { name = "empire_info_bg" spriteType = "GFX_diplomacy_dark_fade_bg" position = { x = -10000 y = -10000 } }
  instantTextBoxType = { name = "empire_name" font = "malgun_goth_24" position = { x = -10000 y = -10000 } }
  instantTextBoxType = { name = "empire_government_type" font = "cg_16b" position = { x = -10000 y = -10000 } }
  instantTextBoxType = { name = "empire_personality_type" font = "cg_16b" position = { x = -10000 y = -10000 } }
  overlappingElementsBoxType = { name = "empire_ethics_icons" position = { x = -10000 y = -10000 } }
  buttonType = { name = "empire_flag" quadTextureSprite = "GFX_empire_flag_128" position = { x = -10000 y = -10000 } }
  containerWindowType = {
   name = "leader_details"
   position = { x = -10000 y = -10000 }
   containerWindowType = { name = "leader_traits_box" }
   instantTextBoxType = { name = "empire_traits_label" font = "cg_16b" }
   instantTextBoxType = { name = "leader_traits_label" font = "cg_16b" }
   overlappingElementsBoxType = { name = "leader_traits" }
   instantTextBoxType = { name = "leader_name" font = "cg_16b" }
   instantTextBoxType = { name = "leader_species" font = "cg_16b" }
  }
  containerWindowType = {
   name = "opinion_window"
   position = { x = -10000 y = -10000 }
   background = { name = "opinion_bg" spriteType = "GFX_tiled_window_transparent" }
   iconType = { name = "their_opinion_icon" spriteType = "GFX_diplomacy_opinion" }
   instantTextBoxType = { name = "their_opinion" font = "cg_16b" }
  }
  containerWindowType = {
   name = "EVENT_DIPLO"
   position = { x = 0 y = 0 }
   instantTextBoxType = { name = "action_title" font = "malgun_goth_24" position = { x = -10000 y = -10000 } }
   instantTextBoxType = { name = "action_desc" font = "malgun_goth_24" position = { x = -10000 y = -10000 } }
   listBoxType = {
    name = "option_list"
    position = { x = 700 y = 630 }
    size = { x = 300 y = 70 }
    spacing = 2
    scrollbarType = "standardlistbox_slider"
    backGround = ""
    borderSize = { x = 0 y = 0 }
   }
  }
@CONTENT@
 }
}
'''


SHELL = chrome(SHELL)


def text_box(name, key, x, y, width, height=24, font="cg_16b"):
    return f'''  instantTextBoxType = {{
   name = "{name}"
   text = "{key}"
   font = "{font}"
   position = {{ x = {x} y = {y} }}
   maxWidth = {width}
   maxHeight = {height}
   alwaysTransparent = yes
  }}\n'''


def button(name, key, x, y, width=84, effect=None):
    # effectButton text resolves From variables, as in the installed numeric-panel UI.
    binding = f'   effect = "{effect}"\n' if effect else ''
    return f'''  effectButtonType = {{
   name = "{name}"
   buttonText = "{key}"
   buttonFont = "cg_16b"
   format = center
   position = {{ x = {x} y = {y} }}
   size = {{ x = {width} y = 25 }}
   quadTextureSprite = "GFX_button_light"
{binding}  }}\n'''


def generate():
    loc = {
        PREFIX + "_title": "星政中枢 · 军事与建设",
        PREFIX + "_desc": "调节军事与建设加成。",
        PREFIX + "_open": "军事与建设" if GUI_ACCEPTED else "军事与建设（旧版菜单）",
        PREFIX + "_note": "下方显示本工具的额外加成；点击立即应用，减至零为止。上排增加，下排减少。",
        PREFIX + "_footer": "星球建设含施工、清障与环境改造；巨构加成保留科技及独立数量限制。\\n不占通用施工名额的巨构不受名额加成影响；重置只移除本工具本项加成。",
        PREFIX + "_military_footer": "§Y已内置上限扩展：舰队容量 1000 万；单舰队指挥上限 100000。最终以实际加载的 Mod 为准。§!\\n本页“额外”为工具加成，超过上限后实际数值可能不再增加；重置仅移除本项加成。",
        PREFIX + "_automated_ratio_tt": "为允许自动化的原版岗位增加自动化比例，按百分点累加；工具额外比例限定 0～100。保留建筑等其他来源；实际自动劳力受岗位规则、现有岗位数与自动化滑条限制。自动化仍有能源维护费，重置只移除本工具的比例加成，不影响效率。",
        PREFIX + "_automated_output_tt": "增加原版自动劳动力效率，提高已有自动化岗位的产出；不授予自动化岗位或自动化覆盖率。与已有自动化效率加成叠加，实际变化以岗位明细为准；重置只移除本工具的加成。",
        PREFIX + "_mega_title": "星政中枢 · 巨构与资源",
        PREFIX + "_to_mega": "巨构与资源 →",
        PREFIX + "_planet_footer": "自动化比例与效率独立调节；自动化仍消耗能源，并受岗位规则及滑条限制。\\n重置只移除本工具本项加成；星球建设包括施工、清障与环境改造。",
        PREFIX + "_mega_production_tt": "增加巨构经济类别的资源产出，可与奇观拓展的通用产出修正叠加；不提高舰容等非资源效果，也不改变事件直接发放的资源。重置只移除本工具的产出加成。",
        PREFIX + "_reset": "重置本项",
        PREFIX + "_back": "返回星政中枢",
        PREFIX + "_close": "关闭面板（Esc）",
        PREFIX + "_planet_title": "星政中枢 · 星球与经济",
        PREFIX + "_to_planet": "星球与经济 →",
        PREFIX + "_to_military": "← 舰队与军事建设",
    }
    content = text_box("panel_title", PREFIX + "_title", 22, 15, 900, 30, "malgun_goth_24")
    planet_content = text_box("panel_title", PREFIX + "_planet_title", 22, 15, 900, 30, "malgun_goth_24")
    mega_content = text_box("panel_title", PREFIX + "_mega_title", 22, 15, 900, 30, "malgun_goth_24")
    for suffix, heading in (("military", "舰队编制与军事施工"), ("planet", "建设、岗位与自动化"), ("mega", "巨构施工与资源产出")):
        loc[PREFIX + "_section_" + suffix] = "§H" + heading + "§!"
    content += text_box("section", PREFIX + "_section_military", 22, 96, 980, 18)
    planet_content += text_box("section", PREFIX + "_section_planet", 22, 96, 980, 18)
    mega_content += text_box("section", PREFIX + "_section_mega", 22, 96, 980, 18)
    page_rows = {"military": 0, "planet": 0, "mega": 0}
    effects = ["# Generated by tools/build_military_gui.py; scope is always the player country.\n"]
    init = []

    def add_effect(name, body, tooltip=None):
        tt = f'  custom_tooltip = "{tooltip}"\n' if tooltip else ''
        effects.append(f'''{name} = {{
 potential = {{ from = {{ is_ai = no }} }}
 allow = {{ from = {{ is_ai = no }} }}
 effect = {{
{tt}  hidden_effect = {{
   from = {{
    auto_qol_military_prepare = yes
{body}
   }}
  }}
 }}
}}
''')

    for index, (key, title, steps, unit) in enumerate(ROWS):
        variable = "qol_custom_" + key
        apply = "auto_qol_reapply_" + key
        # Keep each page within six rows, with unchanged row spacing.
        page = "military" if index < 6 else "mega" if key.startswith("mega_") else "planet"
        y = 124 + page_rows[page] * 80
        page_rows[page] += 1
        tooltip = PREFIX + "_" + key + "_tt" if key in ("mega_production", "automated_output", "automated_ratio") else None
        specific = loc.get(tooltip, "")
        tooltip = PREFIX + "_" + key + "_tt"
        footer_key = {"military": "_military_footer", "planet": "_planet_footer", "mega": "_footer"}[page]
        loc[tooltip] = title + "\\n" + loc[PREFIX + "_note"] + "\\n" + loc[PREFIX + footer_key] + ("\\n" + specific if specific else "")
        row_content = panel("setting_" + key, 22, y - 8, 986, 74)
        loc[PREFIX + "_label_" + key] = title
        loc[PREFIX + "_value_" + key] = f"额外：§G+[From.{variable}]{unit}§!"
        row_content += text_box("label_" + key, PREFIX + "_label_" + key, 36, y, 234)
        row_content += button("value_" + key, PREFIX + "_value_" + key, 36, y + 30, 234)
        init.append(f''' if = {{
  limit = {{ NOT = {{ is_variable_set = {variable} }} }}
  set_variable = {{ which = {variable} value = 0 }}
 }}''')
        for col, amount in enumerate(steps):
            for op, sign, offset in (("add", "+", 0), ("sub", "-", 33)):
                name = f"{PREFIX}_{key}_{op}_{amount}"
                label = f"{PREFIX}_{op}_{amount}{'_pct' if unit else ''}"
                loc[label] = f"{sign}{amount}{unit}"
                row_content += button(name, label, 288 + col * 90, y + offset, effect=name)
                command = "change_variable" if op == "add" else "subtract_variable"
                body = f"    {command} = {{ which = {variable} value = {amount} }}\n"
                if op == "add" and key == "automated_ratio":
                    body += f"    if = {{ limit = {{ check_variable = {{ which = {variable} value > 100 }} }} set_variable = {{ which = {variable} value = 100 }} }}\n"
                if op == "sub":
                    body += f'''    if = {{
     limit = {{ check_variable = {{ which = {variable} value < 0 }} }}
     set_variable = {{ which = {variable} value = 0 }}
    }}\n'''
                body += f"    {apply} = yes"
                add_effect(name, body, tooltip)
        name = f"{PREFIX}_{key}_reset"
        row_content += button(name, PREFIX + "_reset", 846, y + 16, 150, name)
        add_effect(name, f"    set_variable = {{ which = {variable} value = 0 }}\n    {apply} = yes", tooltip)
        if page == "military":
            content += row_content
        elif page == "planet":
            planet_content += row_content
        else:
            mega_content += row_content

    prepare = "# Generated by tools/build_military_gui.py\nauto_qol_military_prepare = {\n" + "\n".join(init)
    prepare += "\n auto_qol_prepare_starbase_construction = yes\n auto_qol_reapply_mega_production = yes\n auto_qol_reapply_automated_output = yes\n auto_qol_reapply_automated_ratio = yes\n}\n"
    events = '''# Generated by tools/build_military_gui.py
namespace = auto_qol_military
country_event = {
 id = auto_qol_military.1
 diplomatic = yes
 custom_gui = "auto_qol_military_window"
 custom_gui_option = "auto_qol_military_option"
 title = "auto_qol_military_title"
 desc = "auto_qol_military_desc"
 is_triggered_only = yes
 trigger = { is_ai = no }
 immediate = { auto_qol_military_prepare = yes }
 option = {
  name = "auto_qol_military_to_planet"
  custom_gui = "auto_qol_military_footer_0"
  hidden_effect = { country_event = { id = auto_qol_military.3 } }
 }
 option = {
  name = "auto_qol_military_back"
  custom_gui = "auto_qol_military_footer_1"
  hidden_effect = { country_event = { id = auto_qol_menu.1 } }
 }
 option = { name = "auto_qol_military_close" custom_gui = "auto_qol_military_footer_2" default_hide_option = yes }
}
'''
    # Use native event options to close one page before opening the other.
    planet_event = events[events.index("country_event = {"):]
    planet_event = planet_event.replace("id = auto_qol_military.1", "id = auto_qol_military.3", 1)
    planet_event = planet_event.replace('custom_gui = "auto_qol_military_window"', 'custom_gui = "auto_qol_military_planet_window"')
    planet_event = planet_event.replace('custom_gui_option = "auto_qol_military_option"', 'custom_gui_option = "auto_qol_military_planet_option"')
    planet_event = planet_event.replace('title = "auto_qol_military_title"', 'title = "auto_qol_military_planet_title"')
    planet_event = planet_event.replace('name = "auto_qol_military_to_planet"', 'name = "auto_qol_military_to_mega"').replace("id = auto_qol_military.3 }", "id = auto_qol_military.4 }")
    mega_event = events[events.index("country_event = {"):]
    mega_event = mega_event.replace("id = auto_qol_military.1", "id = auto_qol_military.4", 1)
    mega_event = mega_event.replace('custom_gui = "auto_qol_military_window"', 'custom_gui = "auto_qol_military_mega_window"')
    mega_event = mega_event.replace('custom_gui_option = "auto_qol_military_option"', 'custom_gui_option = "auto_qol_military_mega_option"')
    mega_event = mega_event.replace('title = "auto_qol_military_title"', 'title = "auto_qol_military_mega_title"')
    mega_event = mega_event.replace('name = "auto_qol_military_to_planet"', 'name = "auto_qol_military_to_military"').replace("id = auto_qol_military.3 }", "id = auto_qol_military.1 }")
    events += planet_event + mega_event
    if not GUI_ACCEPTED:
        candidate = events.replace("namespace = auto_qol_military\n", "").replace(
            "id = auto_qol_military.1", "id = auto_qol_military.2"
        )
        events = '''# Generated by tools/build_military_gui.py
# Production entry stays on the legacy menu until the corrected GUI passes in-game acceptance.
namespace = auto_qol_military
country_event = {
 id = auto_qol_military.1
 hide_window = yes
 is_triggered_only = yes
 trigger = { is_ai = no }
 immediate = { country_event = { id = auto_qol_fleet_menu.1 } }
}
# Isolated acceptance event, with no entry from normal gameplay menus.
''' + candidate
    else:
        # Preserve the test command already supplied to users.
        events += '''
country_event = {
 id = auto_qol_military.2
 hide_window = yes
 is_triggered_only = yes
 trigger = { is_ai = no }
 immediate = { country_event = { id = auto_qol_military.1 } }
}
'''
    # Diplomatic event binding requires listBoxType specifically, not a smooth
    # list (4.5.3 logs "Could not find Listbox option_list" for the latter).
    # Native option-level templates position the three buttons in one row.
    military_shell = SHELL.replace("width = 290 height = 30", "width = 235 height = 34")
    military_shell = military_shell.replace("x = 290 y = 28", "x = 235 y = 32")
    military_shell = military_shell.replace("x = 700 y = 630", "x = 22 y = 668").replace("x = 300 y = 70", "x = 986 y = 38")
    military_shell = military_shell.replace('spacing = 2\n    scrollbarType = "standardlistbox_slider"', 'spacing = 0\n    scrollbarType = "standardlistbox_slider"')
    first = military_shell.replace("@CONTENT@", content)
    second = military_shell.replace("auto_qol_military_window", "auto_qol_military_planet_window").replace("auto_qol_military_option", "auto_qol_military_planet_option").replace("@CONTENT@", planet_content)
    third = military_shell.replace("auto_qol_military_window", "auto_qol_military_mega_window").replace("auto_qol_military_option", "auto_qol_military_mega_option").replace("@CONTENT@", mega_content)
    combined = first[:first.rfind("}")] + second[second.index("{") + 1:second.rfind("}")] + third[third.index("{") + 1:]
    templates = ""
    for slot in range(3):
        # One-pixel entries keep a nonempty native list; compensate their
        # accumulated height so every button remains exactly at footer y=668.
        templates += f'''
 containerWindowType = {{
  name = "auto_qol_military_footer_{slot}"
  position = {{ x = 0 y = 0 }}
  size = {{ width = 986 height = 1 }}
  moveable = no
  buttonType = {{
   name = "option_button"
   quadTextureSprite = "GFX_button_light"
   position = {{ x = {slot * 330} y = {-slot} }}
   size = {{ x = 300 y = 32 }}
   font = "cg_16b"
   text = "OPTION_TEXT"
  }}
  overlappingElementsBoxType = {{ name = "trigger_icons" position = {{ x = -10000 y = -10000 }} size = {{ x = 0 y = 0 }} }}
  overlappingElementsBoxType = {{ name = "effect_icons" position = {{ x = -10000 y = -10000 }} size = {{ x = 0 y = 0 }} }}
 }}
'''
    combined = combined[:combined.rfind("}")] + templates + "}\n"
    return {
        "interface/auto_qol_military.gui": combined,
        "common/button_effects/auto_qol_military_buttons.txt": "\n".join(effects),
        "common/scripted_effects/auto_qol_military_gui_effects.txt": prepare,
        "events/auto_qol_military_gui_events.txt": events,
        "localisation/simp_chinese/auto_qol_military_gui_l_simp_chinese.yml": "l_simp_chinese:\n" + "".join(f' {key}:0 "{value}"\n' for key, value in loc.items()),
    }


if __name__ == "__main__":
    for relative, content in generate().items():
        path = ROOT / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8-sig" if path.suffix == ".yml" else "utf-8")
    print("Generated military/construction GUI (14 rows, three pages).")

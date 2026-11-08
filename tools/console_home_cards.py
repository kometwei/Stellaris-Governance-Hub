"""Fixed dashboard cards use native option templates, as the existing footer does.

Conditional psionic states occupy the same card. One-pixel entries keep the
native list nonempty; accumulated height is subtracted from card coordinates.
Every click still consumes its event.
"""
from console_theme import panel
from native_dashboard_footer import blocks, top_blocks, option_name

# Keep source option order for native list flow; group their display separately.
POSITIONS = ((0, 0), (0, 1), (0, 2), (1, 0), (1, 1), (1, 2), (0, 3), (1, 3), (0, 4))

CARDS = (
    ("auto_qol_military_open", "舰队编制 · 军事施工 · 星球经济"),
    ("auto_qol_hub_megastructures", "预览费用，批量启动巨构的下一建设阶段"),
    ("auto_qol_hub_starbase_clear", "选择基地，按模块、建筑或全部进行清理"),
    ("auto_qol_council_gui_open", "职位指派 · 在任名册 · 领袖池管理"),
    ("auto_qol_menu.assimilation", "选择来源物种，管理人口及领袖同化"),
    ("auto_qol_menu.ascension_slots", "调整目标槽位，按需补齐缺额"),
    ("auto_qol_menu.planet_ascension_10", "将自有殖民地的飞升等级补齐至 10 级"),
    ("auto_qol_menu.psionic_bundle_ready", "满足灵能传统条件后解锁科技组合"),
    ("auto_qol_menu.tradition_menu", "打开开发版传统批量解锁工具"),
)


def decorate_events(script):
    slots = {key: i for i, (key, _) in enumerate(CARDS)}
    slots.update({"auto_qol_menu.psionic_bundle_complete": 7,
                  "auto_qol_menu.psionic_bundle_locked": 7})
    for event in list(blocks(script, "country_event")):
        updated = event
        for option in top_blocks(event, "option"):
            key = option_name(option)
            if key == "auto_qol_hub_home":
                updated = updated.replace(option, "", 1)
            if key == "auto_qol_hub_close":
                updated = updated.replace(option, option.replace('"auto_qol_hub_nav2_1"', '"auto_qol_hub_close_button"'), 1)
            if key in slots:
                tooltip = "" if "custom_tooltip" in option else f'\n custom_tooltip = "auto_qol_hub_summary_{slots[key]}"'
                updated = updated.replace(option, option[:option.index("{") + 1]
                    + f'\n custom_gui = "auto_qol_hub_card_{slots[key]}"'
                    + tooltip
                    + option[option.index("{") + 1:], 1)
        script = script.replace(event, updated, 1)
    return script


def decorate_gui(gui, list_y):
    # Home has a full-width workspace; descriptive sidebars belong to subpages.
    gui = gui.replace(panel("console_context", 12, 104, 320, 486), "")
    gui = gui.replace(panel("console_workspace", 342, 104, 676, 486), "")
    gui = gui.replace("width = 1030 height = 720", "width = 880 height = 560")
    gui = gui.replace(panel("console_header", 12, 8, 1006, 86), panel("console_header", 12, 8, 856, 64))
    gui = gui.replace(panel("console_footer", 12, 600, 1006, 108), panel("console_footer", 12, 488, 856, 60))
    gui = gui.replace("size = { x = 986 y = 584 }", "size = { x = 836 y = 424 }")
    gui = gui.replace('position = { x = 22 y = 112 }', 'position = { x = -10000 y = -10000 }')
    gui = gui.replace('position = { x = 352 y = 116 }', 'position = { x = -10000 y = -10000 }')
    templates = ""
    for index, _ in enumerate(CARDS):
        column, row = POSITIONS[index]
        x = column * 430
        # A list made entirely of zero-height entries did not render in the
        # user's 4.5.3 test, including its footer. Match the military footer's
        # positive-height contract and compensate preceding card entries.
        y = 136 + row * 50 - list_y - index
        templates += f''' containerWindowType = {{
  name = "auto_qol_hub_card_{index}"
  size = {{ width = 836 height = 1 }}
  position = {{ x = 0 y = 0 }}
  buttonType = {{
   name = "option_button"
   quadTextureSprite = "GFX_button_light"
   position = {{ x = {x} y = {y} }}
   size = {{ x = 406 y = 38 }}
   font = "cg_16b"
   text = "OPTION_TEXT"
  }}
  overlappingElementsBoxType = {{ name = "trigger_icons" position = {{ x = -10000 y = -10000 }} size = {{ x = 0 y = 0 }} }}
  overlappingElementsBoxType = {{ name = "effect_icons" position = {{ x = -10000 y = -10000 }} size = {{ x = 0 y = 0 }} }}
 }}
'''
    templates += f''' containerWindowType = {{
  name = "auto_qol_hub_close_button"
  size = {{ width = 836 height = 0 }}
  buttonType = {{
   name = "option_button"
   quadTextureSprite = "GFX_button_light"
   position = {{ x = 215 y = {504 - list_y} }}
   size = {{ x = 406 y = 32 }}
   font = "cg_16b"
   text = "OPTION_TEXT"
  }}
  overlappingElementsBoxType = {{ name = "trigger_icons" position = {{ x = -10000 y = -10000 }} size = {{ x = 0 y = 0 }} }}
  overlappingElementsBoxType = {{ name = "effect_icons" position = {{ x = -10000 y = -10000 }} size = {{ x = 0 y = 0 }} }}
 }}
'''
    return gui[:gui.rfind("}")] + templates + "}\n"

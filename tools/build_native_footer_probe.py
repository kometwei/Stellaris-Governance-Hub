"""Isolated native-option footer experiment. Never called by production builds.

The option-level custom_gui field is present in CWTools events.cwt and installed
mods use option templates whose buttons extend beyond their entry containers.
Zero-height navigation entries precede the body, keeping footer positions stable
while the body fits without scrolling. Hit testing and lifecycle still need QA.
"""
from pathlib import Path
import argparse

from build_council_gui import dashboard_shell, DASHBOARD_LIST_Y, DASHBOARD_LIST_HEIGHT
from build_military_gui import text_box

ROOT = Path(__file__).resolve().parents[1]
PREFIX = "auto_qol_native_footer_probe"


def generate():
    shell = dashboard_shell(PREFIX)
    # The native list must cover the full footer width; otherwise its clipping
    # rectangle would hide a navigation button extending left of the body column.
    shell = shell.replace("width = 630 height = 34", "width = 986 height = 34")
    shell = shell.replace("position = { x = 0 y = 0 }", "position = { x = 330 y = 0 }", 1)
    shell = shell.replace(f"x = 352 y = {DASHBOARD_LIST_Y}", f"x = 22 y = {DASHBOARD_LIST_Y}")
    shell = shell.replace(f"x = 650 y = {DASHBOARD_LIST_HEIGHT}", f"x = 986 y = {708 - DASHBOARD_LIST_Y}")
    shell = shell.replace('spacing = 2\n    scrollbarType = "standardlistbox_slider"', 'spacing = 0\n    scrollbarType = "standardlistbox_slider"')
    content = text_box("probe_header", PREFIX + "_header", 22, 15, 930, 30, "malgun_goth_24")
    content += text_box("probe_note", PREFIX + "_note", 22, 60, 980, 30)
    shell = shell.replace("@CONTENT@", content)
    templates = ""
    for slot, x in enumerate((0, 330, 660)):
        templates += f'''
 containerWindowType = {{
  name = "{PREFIX}_nav_{slot}"
  position = {{ x = 0 y = 0 }}
  size = {{ width = 986 height = 0 }}
  moveable = no
  buttonType = {{
   name = "option_button"
   quadTextureSprite = "GFX_button_light"
   position = {{ x = {x} y = {668 - DASHBOARD_LIST_Y} }}
   size = {{ x = 300 y = 32 }}
   font = "cg_16b"
   text = "OPTION_TEXT"
  }}
  overlappingElementsBoxType = {{ name = "trigger_icons" position = {{ x = -10000 y = -10000 }} size = {{ x = 0 y = 0 }} }}
  overlappingElementsBoxType = {{ name = "effect_icons" position = {{ x = -10000 y = -10000 }} size = {{ x = 0 y = 0 }} }}
 }}
'''
    gui = shell[:shell.rfind("}")] + templates + "}\n"
    script = f"namespace = {PREFIX}\n"
    for page, other in ((1, 2), (2, 1)):
        script += f'''
country_event = {{
 id = {PREFIX}.{page}
 diplomatic = yes
 custom_gui = "{PREFIX}_window"
 custom_gui_option = "{PREFIX}_option"
 title = "{PREFIX}_page_{page}"
 desc = "{PREFIX}_desc"
 is_triggered_only = yes
 trigger = {{ is_ai = no }}
 # All transitions are native option callbacks, never effectButton callbacks.
 option = {{
  name = "{PREFIX}_home"
  custom_gui = "{PREFIX}_nav_0"
  hidden_effect = {{ country_event = {{ id = {PREFIX}.1 }} }}
 }}
 option = {{
  name = "{PREFIX}_compat"
  custom_gui = "{PREFIX}_nav_1"
  hidden_effect = {{ country_event = {{ id = {PREFIX}.2 }} }}
 }}
 option = {{
  name = "{PREFIX}_close"
  custom_gui = "{PREFIX}_nav_2"
  default_hide_option = yes
 }}
 option = {{
  name = "{PREFIX}_body"
  hidden_effect = {{ country_event = {{ id = {PREFIX}.{other} }} }}
 }}
}}
'''
    loc = {
        "header": "单击原生底栏 · 独立验证",
        "note": "仅验证界面和窗口生命周期，不执行任命或修改帝国加成。",
        "page_1": "测试首页 A",
        "page_2": "测试兼容页 B",
        "desc": "请验证：\\n1. 底部三个按钮是否横向排列、均可单击。\\n2. 首页与兼容页往返多次。\\n3. 关闭后是否彻底消失，没有旧窗口残留。\\n4. 重新打开并测试 Esc 和右上角 X。\\n\\n本测试不从正式菜单触发。",
        "home": "返回测试首页",
        "compat": "打开测试兼容页",
        "close": "关闭测试（Esc）",
        "body": "正文选项：单击切换到另一页",
    }
    return {
        f"interface/{PREFIX}.gui": gui,
        f"events/{PREFIX}_events.txt": script,
        f"localisation/simp_chinese/{PREFIX}_l_simp_chinese.yml": "l_simp_chinese:\n" + "".join(f' {PREFIX}_{k}:0 "{v}"\n' for k, v in loc.items()),
    }


def build(root):
    root = Path(root).resolve()
    if ROOT != root and ROOT not in root.parents:
        raise ValueError("The isolated probe must stay within this repository")
    for relative, content in generate().items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8-sig" if path.suffix == ".yml" else "utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "scratch/native-footer-probe")
    args = parser.parse_args()
    build(args.output)
    print("Built isolated probe; console entry: event auto_qol_native_footer_probe.1")

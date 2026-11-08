"""Native GUI frontends for existing species assimilation and AP-slot workflows.

Backend event files and monthly hooks are preserved. The GUI copies only visible
steps with new IDs, retaining all conditions, confirmations and scoped targets.
"""
from pathlib import Path
import re

from build_council_gui import dashboard_shell, DASHBOARD_LIST_Y, DASHBOARD_LIST_HEIGHT
from build_military_gui import text_box
from native_dashboard_footer import blocks, transform_events, transform_gui

ROOT = Path(__file__).resolve().parents[1]
FEATURES = (
    ("assimilation", "物种同化", "选择来源物种后需确认启用；领袖同化有独立确认开关。"),
    ("ascension", "飞升槽位", "先调整目标，再补齐缺额；降低目标不收回槽位，飞升天赋自行选择。"),
)


def source_events(root, feature):
    return (Path(root) / f"events/auto_qol_{feature}_events.txt").read_text(encoding="utf-8-sig")


def clone_visible(root, feature):
    text = source_events(root, feature)
    stem = "auto_qol_" + feature
    target = stem + "_gui"
    originals = [event for event in blocks(text, "country_event") if re.search(r"(?m)^\s*title\s*=", event)]
    ids = {re.search(r"(?m)^\s*id\s*=\s*(\w+\.\d+)", event)[1] for event in originals}
    header = text[:text.index("country_event")].replace("namespace = " + stem, "namespace = " + target)
    # Script constants are file-local; keep an independent copy with this file's
    # profile-resolved target, without altering the existing backend constant.
    header = header.replace("@auto_qol_ascension_slot_target", "@auto_qol_ascension_gui_slot_target")
    for event in originals:
        event = re.sub(r"\bid\s*=\s*(\w+\.\d+)", lambda m: "id = " + (m[1].replace(stem + ".", target + ".", 1) if m[1] in ids else m[1]), event)
        event = event.replace("@auto_qol_ascension_slot_target", "@auto_qol_ascension_gui_slot_target")
        index = event.index("{") + 1
        event = event[:index] + f'\n diplomatic = yes\n custom_gui = "{target}_window"\n custom_gui_option = "{target}_option"\n' + event[index:]
        header += event + "\n"
    return header


def generate(root=ROOT):
    result = {}
    for feature, title, note in FEATURES:
        prefix = "auto_qol_" + feature + "_gui"
        shell = dashboard_shell(prefix).replace("maxHeight = 230", "maxHeight = 450")
        content = text_box("feature_header", prefix + "_header", 22, 15, 930, 30, "malgun_goth_24")
        content += text_box("feature_note", prefix + "_note", 22, 66, 980, 28)
        content += text_box("feature_footer", prefix + "_footer", 22, 606, 980, 48)
        loc = {
            "header": "星政中枢 · " + title,
            "note": "右侧单击操作；左侧查看当前状态与说明。",
            "footer": note,
            "home": "返回星政中枢首页",
            "close": "关闭面板（Esc）",
            "prev": "← 上一页",
            "next": "下一页 →",
        }
        result[f"interface/{prefix}.gui"] = transform_gui(shell.replace("@CONTENT@", content), prefix, DASHBOARD_LIST_Y, DASHBOARD_LIST_HEIGHT)
        result[f"events/{prefix}_events.txt"] = transform_events(clone_visible(root, feature), prefix, f"auto_qol_{feature}_native_page")
        result[f"localisation/simp_chinese/{prefix}_l_simp_chinese.yml"] = "l_simp_chinese:\n" + "".join(f' {prefix}_{k}:0 "{v}"\n' for k, v in loc.items())
    return result


def build(root=ROOT):
    root = Path(root)
    for relative, content in generate(root).items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8-sig" if path.suffix == ".yml" else "utf-8")


if __name__ == "__main__":
    build()
    print("Generated species assimilation and ascension-slot native GUIs.")

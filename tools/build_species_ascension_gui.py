"""Native GUI frontends for existing species assimilation and AP-slot workflows.

Backend event files and monthly hooks are preserved. The GUI copies only visible
steps with new IDs, retaining all conditions, confirmations and scoped targets.
"""
from pathlib import Path
import re

from build_council_gui import dashboard_shell, DASHBOARD_LIST_Y, DASHBOARD_LIST_HEIGHT
from build_military_gui import text_box
from native_dashboard_footer import blocks, top_blocks, option_name, transform_events, transform_gui

ROOT = Path(__file__).resolve().parents[1]
FEATURES = (
    ("assimilation", "物种同化", "选择来源物种后需确认启用；领袖同化有独立确认开关。"),
    ("ascension", "飞升槽位", "先调整目标，再补齐缺额；降低目标不收回槽位，飞升天赋自行选择。"),
)
DISPLAY_KEYS = {
    "auto_qol_assimilation.desc_selected": "auto_qol_assimilation_gui_status_selected",
    "auto_qol_assimilation.desc_empty": "auto_qol_assimilation_gui_status_empty",
    "auto_qol_assimilation.choose_tt": "auto_qol_assimilation_gui_choose_tt",
    "auto_qol_ascension.desc": "auto_qol_ascension_gui_status",
    "auto_qol_ascension.adjust_tt": "auto_qol_ascension_gui_adjust_tt",
    "auto_qol_ascension.unlock_tt": "auto_qol_ascension_gui_unlock_tt",
}


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
        if feature == "ascension":
            # The native footer already returns home. Removing the duplicate
            # body return keeps all five +/- tiers and fill on one page.
            for option in top_blocks(event, "option"):
                if option_name(option) == "auto_qol_ascension.back":
                    event = event.replace(option, "", 1)
        event = re.sub(r"\bid\s*=\s*(\w+\.\d+)", lambda m: "id = " + (m[1].replace(stem + ".", target + ".", 1) if m[1] in ids else m[1]), event)
        event = event.replace("@auto_qol_ascension_slot_target", "@auto_qol_ascension_gui_slot_target")
        # Shorten only presentation keys. Conditional descriptions, confirmation
        # text, targets, guards and all backend effects retain their structure.
        for source_key, display_key in DISPLAY_KEYS.items():
            event = event.replace('"' + source_key + '"', '"' + display_key + '"')
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
        loc = {
            "header": "星政中枢 · " + title,
            "note": "右侧单击操作；左侧查看当前状态与说明。",
            "footer": note,
            "home": "返回星政中枢首页",
            "close": "关闭面板（Esc）",
            "prev": "← 上一页",
            "next": "下一页 →",
        }
        if feature == "assimilation":
            loc.update({
                "status_selected": "同化来源：§H[event_target:auto_qol_assimilation_current.GetName]§!\\n目标：帝国主体物种",
                "status_empty": "尚未选择同化来源。",
                "choose_tt": "选择境内外族及其同族亚种，持续转化为帝国主体物种；只处理本帝国境内人口。每次记录一个来源，重新选择会替换原记录。确认后立即处理人口，此后每月补漏；领袖同化独立设置，默认关闭。暂停或停止不会还原已完成的转化。",
            })
        else:
            loc.update({
                "status": "已解锁：§Y[Root.auto_qol_ascension_current]§! 格\\n目标：§Y[Root.auto_qol_ascension_target]§! 格",
                "adjust_tt": "按 1、2、4、8、16 档位增减目标，再点击补齐生效。调整本身不解锁；目标保存在本帝国，范围 1～4096。降低目标不会收回槽位。请按槽位 Mod 提供的实际格数设置；本面板不会扫描槽位上限或扩展传统界面。",
                "unlock_tt": "仅补足目标以内尚未解锁的槽位；重复点击不叠加，降低目标不收回槽位。请先核对槽位 Mod 的实际格数。本功能不扩展传统界面，不自动选择天赋、完成传统或授予科技；天赋条件仍然生效。",
            })
        result[f"interface/{prefix}.gui"] = transform_gui(shell.replace("@CONTENT@", content), prefix, DASHBOARD_LIST_Y, DASHBOARD_LIST_HEIGHT)
        script = transform_events(clone_visible(root, feature), prefix, f"auto_qol_{feature}_native_page")
        result[f"events/{prefix}_events.txt"] = "\n".join(line.rstrip() for line in script.splitlines()) + "\n"
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

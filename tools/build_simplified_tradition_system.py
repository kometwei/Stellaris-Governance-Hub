import os, glob, re
from pathlib import Path
from collections import defaultdict

from paths import WORKSHOP_MOD_DIR, DOCS_DIR, EVENTS_DIR

workshop_dir = WORKSHOP_MOD_DIR
docs_dir = DOCS_DIR

blacklist = {
    'tr_tt_ultralimit_adopt', 'tr_tt_ultralimit_1', 'tr_tt_ultralimit_2',
    'tr_tt_ultralimit_3', 'tr_tt_ultralimit_4', 'tr_tt_ultralimit_5', 'tr_tt_ultralimit_finish',
    'tr_adaptability_homura', 'tr_adaptability_kyoko', 'tr_adaptability_madoka',
    'tr_adaptability_mami', 'tr_adaptability_sayaka'
}

mod_meta = {
    '2438313459': ('tidy', '更加整洁的传统 (Tidy Tradition)'),
    '1747099270': ('wg', '战舰少女R与苍青幻影 (Warship Girls R)'),
    '2409276081': ('patch', '通用游戏规则补丁 Patch'),
    '2982710154': ('hsr', '星穹铁道 (Honkai: Star Rail)'),
    '2748029219': ('mega', '巨型企业平衡调整 (Megacorp re-balance)'),
    '2955622956': ('mem', '更多随机事件 (More Events Mod)'),
    '727000451': ('giga', '更多巨构/其他传统'),
    '3397553525': ('misc1', '其他扩展传统 1'),
    '3250607992': ('misc2', '其他扩展传统 2'),
    '3120810990': ('misc3', '其他扩展传统 3')
}

# 1. 扫描所有 Mod 的安全传统
mod_nodes = defaultdict(list)
all_safe_nodes = []

for f in workshop_dir.glob('**/common/traditions/*.txt'):
    parts = f.parts
    mod_id = 'unknown'
    for i, p in enumerate(parts):
        if p == '281990' and i + 1 < len(parts):
            mod_id = parts[i+1]
            break
    c = f.read_text(encoding='utf-8', errors='ignore')
    for m in re.finditer(r'^\s*(tr_[a-zA-Z0-9_-]+)\s*=', c, re.MULTILINE):
        node = m.group(1)
        if node not in blacklist and node not in mod_nodes[mod_id]:
            mod_nodes[mod_id].append(node)
            if node not in all_safe_nodes:
                all_safe_nodes.append(node)

# 2. 从 dump_traditions 生成的 unlock_safe_only.txt 中提取纯通用无门槛传统
safe_only_file = docs_dir / "unlock_safe_only.txt"
universal_nodes = []
if safe_only_file.exists():
    for line in safe_only_file.read_text(encoding='utf-8', errors='ignore').splitlines():
        line = line.strip()
        if line.startswith('activate_tradition '):
            n = line.split()[1]
            if n not in blacklist and n not in universal_nodes:
                universal_nodes.append(n)
else:
    universal_nodes = [n for n in all_safe_nodes if 'tidy' in n or 'art' in n or 'change' in n]

print(f"Total safe nodes: {len(all_safe_nodes)}")
print(f"Total universal zero-condition nodes: {len(universal_nodes)}")

# 3. 生成折中精简版 tradition_unlock_events.txt
events_path = EVENTS_DIR / 'tradition_unlock_events.txt'
with open(events_path, 'w', encoding='utf-8') as f:
    f.write("namespace = tradition_unlock_menu\n")
    f.write("namespace = tradition_unlock\n\n")

    # 主菜单
    f.write("# ========================================================\n")
    f.write("# 折中精简版传统解锁助手主界面\n")
    f.write("# ========================================================\n")
    f.write("country_event = {\n")
    f.write("\tid = tradition_unlock_menu.1\n")
    f.write('\ttitle = "tradition_unlock_menu.1.name"\n')
    f.write('\tdesc = "tradition_unlock_menu.1.desc"\n')
    f.write("\tpicture = GFX_evt_giga_menu\n")
    f.write("\tis_triggered_only = yes\n\n")

    # 选项 1: 一键激活通用无门槛传统 (纯净普适包)
    f.write("\t# 1. 一键激活通用无门槛传统 (纯净普适包)\n")
    f.write("\toption = {\n")
    f.write('\t\tname = "tradition_unlock_menu.opt_universal"\n')
    f.write('\t\tcustom_tooltip = "tradition_unlock_menu.opt_universal_tt"\n')
    for n in universal_nodes:
        f.write(f"\t\tactivate_tradition = {n}\n")
    f.write("\t\tcountry_event = { id = tradition_unlock_menu.1 }\n")
    f.write("\t}\n\n")

    # 选项 2: 一键激活全部 Mod 安全传统
    f.write("\t# 2. 一键激活全部 Mod 安全传统 (501项)\n")
    f.write("\toption = {\n")
    f.write('\t\tname = "tradition_unlock_menu.opt_all_safe"\n')
    f.write('\t\tcustom_tooltip = "tradition_unlock_menu.opt_all_safe_tt"\n')
    for n in all_safe_nodes:
        f.write(f"\t\tactivate_tradition = {n}\n")
    f.write("\t\tcountry_event = { id = tradition_unlock_menu.1 }\n")
    f.write("\t}\n\n")

    # 选项 3: 进入按 Mod 来源分别激活子菜单
    f.write("\t# 3. 按 Mod 来源分别选择激活\n")
    f.write("\toption = {\n")
    f.write('\t\tname = "tradition_unlock_menu.opt_by_mod"\n')
    f.write('\t\tcustom_tooltip = "tradition_unlock_menu.opt_by_mod_tt"\n')
    f.write("\t\tcountry_event = { id = tradition_unlock_menu.2 }\n")
    f.write("\t}\n\n")

    # 选项 4: 返回主助手控制台
    f.write("\t# 返回主控制台\n")
    f.write("\toption = {\n")
    f.write('\t\tname = "tradition_unlock_menu.back"\n')
    f.write("\t\tcountry_event = { id = auto_qol_menu.1 }\n")
    f.write("\t}\n")
    f.write("}\n\n")

    # 子菜单：按 Mod 来源分别激活
    f.write("# ========================================================\n")
    f.write("# 按 Mod 来源独立激活子菜单\n")
    f.write("# ========================================================\n")
    f.write("country_event = {\n")
    f.write("\tid = tradition_unlock_menu.2\n")
    f.write('\ttitle = "tradition_unlock_menu.2.name"\n')
    f.write('\tdesc = "tradition_unlock_menu.2.desc"\n')
    f.write("\tpicture = GFX_evt_giga_menu\n")
    f.write("\tis_triggered_only = yes\n\n")

    for mod_id, (key, display_name) in mod_meta.items():
        nodes = mod_nodes.get(mod_id, [])
        if not nodes:
            continue
        f.write(f"\t# Mod: {display_name}\n")
        f.write("\toption = {\n")
        f.write(f'\t\tname = "tradition_unlock_mod_{key}"\n')
        f.write(f'\t\tcustom_tooltip = "tradition_unlock_mod_{key}_tt"\n')
        for n in nodes:
            f.write(f"\t\tactivate_tradition = {n}\n")
        f.write("\t\tcountry_event = { id = tradition_unlock_menu.2 }\n")
        f.write("\t}\n\n")

    f.write("\t# 返回上级菜单\n")
    f.write("\toption = {\n")
    f.write('\t\tname = "tradition_unlock_menu.back_to_tr_main"\n')
    f.write("\t\tcountry_event = { id = tradition_unlock_menu.1 }\n")
    f.write("\t}\n")
    f.write("}\n")

print("Simplified tradition events successfully generated!")

import os, glob, re
from pathlib import Path
from collections import defaultdict

from paths import GAME_INSTALL_DIR, WORKSHOP_MOD_DIR, DOCS_DIR, EVENTS_DIR

docs_dir = DOCS_DIR
vanilla_dir = GAME_INSTALL_DIR / "common" / "traditions"
workshop_dir = WORKSHOP_MOD_DIR

# 永久黑名单 (崩溃节点 + 领袖初始特质+1节点)
BLACKLIST = {
    'tr_tt_ultralimit_adopt', 'tr_tt_ultralimit_1', 'tr_tt_ultralimit_2',
    'tr_tt_ultralimit_3', 'tr_tt_ultralimit_4', 'tr_tt_ultralimit_5', 'tr_tt_ultralimit_finish',
    'tr_adaptability_homura', 'tr_adaptability_kyoko', 'tr_adaptability_madoka',
    'tr_adaptability_mami', 'tr_adaptability_sayaka',
    'tr_aptitude_finish'
}

# 1. 扫描所有传统并提取它们的条件倾向
tr_conditions = {} # node -> 'machine' | 'hive' | 'gestalt' | 'megacorp' | 'regular' | 'universal'

def analyze_node_condition(node_name, body):
    if 'is_machine_empire = yes' in body or 'has_authority = auth_machine_intelligence' in body or '_machine' in node_name:
        return 'machine'
    if 'is_hive_empire = yes' in body or 'is_hive_mind = yes' in body or 'has_authority = auth_hive_mind' in body or '_hive' in node_name:
        return 'hive'
    if 'is_gestalt = yes' in body or '_gestalt' in node_name:
        return 'gestalt'
    if 'is_megacorp = yes' in body or 'has_authority = auth_corporate' in body or '_corporate' in node_name or '_megacorp' in node_name:
        return 'megacorp'
    if 'is_regular_empire = yes' in body or 'is_gestalt = no' in body:
        return 'regular'
    return 'universal'

all_nodes_classified = defaultdict(list)

# 扫描原版
for f in sorted(vanilla_dir.glob('*.txt')):
    c = f.read_text(encoding='utf-8', errors='ignore')
    for m in re.finditer(r'(tr_[a-zA-Z0-9_-]+)\s*=\s*\{', c):
        tr_name = m.group(1)
        if tr_name in BLACKLIST:
            continue
        start = m.end(); cnt = 1; pos = start
        while pos < len(c) and cnt > 0:
            if c[pos] == '{': cnt += 1
            elif c[pos] == '}': cnt -= 1
            pos += 1
        body = c[start:pos-1]
        cond = analyze_node_condition(tr_name, body)
        all_nodes_classified[cond].append(tr_name)

# 扫描 Mod
for f in workshop_dir.glob('**/common/traditions/*.txt'):
    c = f.read_text(encoding='utf-8', errors='ignore')
    for m in re.finditer(r'(tr_[a-zA-Z0-9_-]+)\s*=\s*\{', c):
        tr_name = m.group(1)
        if tr_name in BLACKLIST:
            continue
        start = m.end(); cnt = 1; pos = start
        while pos < len(c) and cnt > 0:
            if c[pos] == '{': cnt += 1
            elif c[pos] == '}': cnt -= 1
            pos += 1
        body = c[start:pos-1]
        cond = analyze_node_condition(tr_name, body)
        if tr_name not in all_nodes_classified[cond]:
            all_nodes_classified[cond].append(tr_name)

print("Tradition classification breakdown:")
for cond, nodes in all_nodes_classified.items():
    print(f"  {cond}: {len(nodes)} nodes")

# 2. 生成带有精准智能条件守护与 hidden_effect 的 tradition_unlock_events.txt
events_path = EVENTS_DIR / 'tradition_unlock_events.txt'
with open(events_path, 'w', encoding='utf-8') as f:
    f.write("namespace = tradition_unlock_menu\n\n")

    f.write("# 智能条件匹配版传统解锁助手界面 (零卡顿、智能审计帝国类型、跳过领袖初始特质)\n")
    f.write("country_event = {\n")
    f.write("\tid = tradition_unlock_menu.1\n")
    f.write('\ttitle = "tradition_unlock_menu.1.name"\n')
    f.write('\tdesc = "tradition_unlock_menu.1.desc"\n')
    f.write("\tpicture = GFX_evt_diplomatic_relations\n")
    f.write("\tis_triggered_only = yes\n\n")

    # 选项 1: 智能条件审计激活 (根据当前国家属性动态激活匹配传统)
    f.write("\t# 1. 智能条件审计激活 (推荐：自动根据当前国家政体/思潮安全激活匹配传统)\n")
    f.write("\toption = {\n")
    f.write('\t\tname = "tradition_unlock_menu.opt_smart"\n')
    f.write('\t\tcustom_tooltip = "tradition_unlock_menu.opt_smart_tt"\n')
    f.write("\t\thidden_effect = {\n")
    
    # 纯普适传统 (直接安全激活)
    for n in all_nodes_classified['universal']:
        f.write(f"\t\t\tactivate_tradition = {n}\n")
    
    # 普通帝国分支
    f.write("\t\t\tif = {\n\t\t\t\tlimit = { is_regular_empire = yes }\n")
    for n in all_nodes_classified['regular']:
        f.write(f"\t\t\t\tactivate_tradition = {n}\n")
    f.write("\t\t\t}\n")

    # 巨型企业分支
    f.write("\t\t\tif = {\n\t\t\t\tlimit = { is_megacorp = yes }\n")
    for n in all_nodes_classified['megacorp']:
        f.write(f"\t\t\t\tactivate_tradition = {n}\n")
    f.write("\t\t\t}\n")

    # 机械帝国分支
    f.write("\t\t\tif = {\n\t\t\t\tlimit = { is_machine_empire = yes }\n")
    for n in all_nodes_classified['machine']:
        f.write(f"\t\t\t\tactivate_tradition = {n}\n")
    f.write("\t\t\t}\n")

    # 蜂巢思维分支
    f.write("\t\t\tif = {\n\t\t\t\tlimit = { is_hive_empire = yes }\n")
    for n in all_nodes_classified['hive']:
        f.write(f"\t\t\t\tactivate_tradition = {n}\n")
    f.write("\t\t\t}\n")

    # 格式塔通用分支
    f.write("\t\t\tif = {\n\t\t\t\tlimit = { is_gestalt = yes }\n")
    for n in all_nodes_classified['gestalt']:
        f.write(f"\t\t\t\tactivate_tradition = {n}\n")
    f.write("\t\t\t}\n")

    f.write("\t\t\tcountry_event = { id = tradition_unlock_menu.1 }\n")
    f.write("\t\t}\n")
    f.write("\t}\n\n")

    # 选项 2: 仅激活纯普适零门槛传统 (无论何种国家皆可点亮)
    f.write("\t# 2. 仅激活纯通用无门槛传统\n")
    f.write("\toption = {\n")
    f.write('\t\tname = "tradition_unlock_menu.opt_universal"\n')
    f.write('\t\tcustom_tooltip = "tradition_unlock_menu.opt_universal_tt"\n')
    f.write("\t\thidden_effect = {\n")
    for n in all_nodes_classified['universal']:
        f.write(f"\t\t\tactivate_tradition = {n}\n")
    f.write("\t\t\tcountry_event = { id = tradition_unlock_menu.1 }\n")
    f.write("\t\t}\n")
    f.write("\t}\n\n")

    # 选项 3: 返回主控制台
    f.write("\t# 返回主控制台\n")
    f.write("\toption = {\n")
    f.write('\t\tname = "tradition_unlock_menu.back"\n')
    f.write("\t\tcountry_event = { id = auto_qol_menu.1 }\n")
    f.write("\t}\n")
    f.write("}\n")

print(f"Generated smart conditioned {events_path} successfully!")

# 3. 同步生成安全的控制台脚本
# 仅普适脚本: unlock_safe_only.txt (仅包含 universal + regular)
lines_safe = [
    "# ==============================================================================",
    "# 纯净通用无门槛传统脚本 (严格符合常规普通帝国，绝不强塞蜂巢/机械专属)",
    "# 运行方式: 控制台输入: run unlock_safe_only.txt",
    "# ==============================================================================",
    ""
]
for n in all_nodes_classified['universal'] + all_nodes_classified['regular']:
    lines_safe.append(f"activate_tradition {n}")
(docs_dir / "unlock_safe_only.txt").write_text("\n".join(lines_safe) + "\n", encoding='utf-8')
print("Updated unlock_safe_only.txt successfully!")

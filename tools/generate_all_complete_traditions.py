import os, glob, re
from pathlib import Path
from collections import defaultdict

from paths import GAME_INSTALL_DIR, WORKSHOP_MOD_DIR, DOCS_DIR, EVENTS_DIR

docs_dir = DOCS_DIR
vanilla_dir = GAME_INSTALL_DIR / "common" / "traditions"
workshop_dir = WORKSHOP_MOD_DIR

# 1. 终极永久黑名单 (崩溃节点 + 领袖初始特质+1节点)
BLACKLIST = {
    # 导致 F2 除以零崩溃与进度条除以零崩溃的 12 个恶性缺陷节点
    'tr_tt_ultralimit_adopt', 'tr_tt_ultralimit_1', 'tr_tt_ultralimit_2',
    'tr_tt_ultralimit_3', 'tr_tt_ultralimit_4', 'tr_tt_ultralimit_5', 'tr_tt_ultralimit_finish',
    'tr_adaptability_homura', 'tr_adaptability_kyoko', 'tr_adaptability_madoka',
    'tr_adaptability_mami', 'tr_adaptability_sayaka',
    
    # 导致全银河领袖初始特质+1、全池领袖塞特质导致卡顿紊乱的恶性节点 (用户红框指出)
    'tr_aptitude_finish'
}

print("Scanning all traditions across Vanilla and all Workshop Mods...")

# 2. 扫描并自动检测任何带有 leader_initial_traits 的节点
def check_trait_modifiers(file_path):
    bad = set()
    try:
        content = file_path.read_text(encoding='utf-8', errors='ignore')
    except Exception:
        return bad
    if 'leader_initial_traits' in content or 'every_pool_leader' in content:
        for m in re.finditer(r'(tr_[a-zA-Z0-9_-]+)\s*=\s*\{', content):
            tr_name = m.group(1)
            start = m.end(); cnt = 1; pos = start
            while pos < len(content) and cnt > 0:
                if content[pos] == '{': cnt += 1
                elif content[pos] == '}': cnt -= 1
                pos += 1
            body = content[start:pos-1]
            if 'leader_initial_traits' in body or 'every_pool_leader' in body:
                bad.add(tr_name)
    return bad

for p in [vanilla_dir, workshop_dir]:
    for f in p.glob('**/*.txt'):
        if 'tradition' in str(f).lower():
            bads = check_trait_modifiers(f)
            for b in bads:
                if b not in BLACKLIST:
                    print(f"Auto-blacklisting leader initial trait node: {b} in {f.name}")
                    BLACKLIST.add(b)

print(f"Total blacklisted nodes (crash + initial trait): {len(BLACKLIST)}")

# 3. 提取原版官方传统节点 (包含外交 diplomacy, 敌意 enmity, 探索, 繁荣, 支配等)
vanilla_nodes = []
for f in sorted(vanilla_dir.glob('*.txt')):
    content = f.read_text(encoding='utf-8', errors='ignore')
    for m in re.finditer(r'^\s*(tr_[a-zA-Z0-9_-]+)\s*=', content, re.MULTILINE):
        node = m.group(1)
        if node not in BLACKLIST and node not in vanilla_nodes:
            vanilla_nodes.append(node)

print(f"Vanilla safe tradition nodes (including diplomacy & enmity): {len(vanilla_nodes)}")
assert 'tr_diplomacy_adopt' in vanilla_nodes, "tr_diplomacy_adopt missing!"
assert 'tr_enmity_adopt' in vanilla_nodes, "tr_enmity_adopt missing!"
assert 'tr_aptitude_finish' not in vanilla_nodes, "tr_aptitude_finish NOT blacklisted!"

# 4. 提取创意工坊所有 Mod 的安全传统节点
mod_nodes = []
for f in workshop_dir.glob('**/common/traditions/*.txt'):
    content = f.read_text(encoding='utf-8', errors='ignore')
    for m in re.finditer(r'^\s*(tr_[a-zA-Z0-9_-]+)\s*=', content, re.MULTILINE):
        node = m.group(1)
        if node not in BLACKLIST and node not in vanilla_nodes and node not in mod_nodes:
            mod_nodes.append(node)

print(f"Workshop mod safe tradition nodes: {len(mod_nodes)}")

# 5. 组合全部传统
all_complete_nodes = vanilla_nodes + mod_nodes
print(f"TOTAL COMPLETE TRADITION NODES: {len(all_complete_nodes)}")

# 6. 生成控制台脚本到 Documents 目录
# 6.1 unlock_all_mod_tr.txt (包含全部原版 + 全部 Mod，直接解决用户控制台没有外交敌意的问题)
script_all = docs_dir / "unlock_all_mod_tr.txt"
lines = [
    "# ==============================================================================",
    "# Stellaris 全传统终极解锁脚本 (原版 + 全部 Mod 完整合并版)",
    "# 运行方式: 进入游戏打开控制台 (按 ~ 键) 输入: run unlock_all_mod_tr.txt",
    "# 包含范围: 完整覆盖原版全部官方传统 (含外交、敌意、至高、探索等) + 全部 Mod 传统",
    "# 安全防御: 彻底跳过 12 个除以零恶性崩溃节点，并坚决排除 tr_aptitude_finish 等领袖初始特质+1节点！",
    f"# 共计包含: {len(all_complete_nodes)} 个节点",
    "# ==============================================================================",
    ""
]
for n in all_complete_nodes:
    lines.append(f"activate_tradition {n}")
script_all.write_text("\n".join(lines) + "\n", encoding='utf-8')
print(f"Successfully updated: {script_all}")

# 同步写入一份 unlock_all_traditions.txt (别名)
(docs_dir / "unlock_all_traditions.txt").write_text("\n".join(lines) + "\n", encoding='utf-8')

# 6.2 纯通用无门槛版 (严格无外部门槛，排除蜂巢/机械专属)
safe_only_file = docs_dir / "unlock_safe_only.txt"
safe_only_nodes = []
if safe_only_file.exists():
    for line in safe_only_file.read_text(encoding='utf-8', errors='ignore').splitlines():
        line = line.strip()
        if line.startswith('activate_tradition '):
            n = line.split()[1]
            if n not in BLACKLIST and n not in safe_only_nodes:
                safe_only_nodes.append(n)
# 将原版普通帝国适用的外交、敌意、探索、繁荣、支配、至高、和谐、不屈也安全纳入
for vn in vanilla_nodes:
    if not any(k in vn for k in ['hive', 'machine', 'gestalt', 'cloning', 'cybernetic', 'synthetic', 'psionic']):
        if vn not in safe_only_nodes:
            safe_only_nodes.append(vn)

lines_safe = [
    "# ==============================================================================",
    "# Stellaris 纯通用无门槛普适传统解锁脚本",
    "# 运行方式: 控制台输入: run unlock_safe_only.txt",
    "# 包含范围: 原版常规通用传统 (含外交、敌意等) + Mod 纯普适传统",
    "# 安全防御: 排除机械蜂巢格式塔专属、特定起源/政体限定与互斥飞升，彻底排除领袖初始特质+1！",
    f"# 共计包含: {len(safe_only_nodes)} 个安全通用节点",
    "# ==============================================================================",
    ""
]
for n in safe_only_nodes:
    lines_safe.append(f"activate_tradition {n}")
safe_only_file.write_text("\n".join(lines_safe) + "\n", encoding='utf-8')
print(f"Successfully updated: {safe_only_file}")

# 7. 更新游戏内精简版 tradition_unlock_events.txt
events_path = EVENTS_DIR / 'tradition_unlock_events.txt'
with open(events_path, 'w', encoding='utf-8') as f:
    f.write("namespace = tradition_unlock_menu\n")
    f.write("namespace = tradition_unlock\n\n")

    f.write("# 折中精简版传统解锁助手主界面 (包含原版外交、敌意等，排除崩溃与领袖初始特质+1)\n")
    f.write("country_event = {\n")
    f.write("\tid = tradition_unlock_menu.1\n")
    f.write('\ttitle = "tradition_unlock_menu.1.name"\n')
    f.write('\tdesc = "tradition_unlock_menu.1.desc"\n')
    f.write("\tpicture = GFX_evt_giga_menu\n")
    f.write("\tis_triggered_only = yes\n\n")

    # 1. 一键激活通用无门槛传统 (纯净普适包，含外交、敌意)
    f.write("\t# 1. 一键激活通用无门槛传统 (纯净普适包)\n")
    f.write("\toption = {\n")
    f.write('\t\tname = "tradition_unlock_menu.opt_universal"\n')
    f.write('\t\tcustom_tooltip = "tradition_unlock_menu.opt_universal_tt"\n')
    for n in safe_only_nodes:
        f.write(f"\t\tactivate_tradition = {n}\n")
    f.write("\t\tcountry_event = { id = tradition_unlock_menu.1 }\n")
    f.write("\t}\n\n")

    # 2. 一键激活全传统 (原版 + Mod 全量包，含外交、敌意，排除初始特质+1)
    f.write("\t# 2. 一键激活全部传统 (原版+Mod全量包)\n")
    f.write("\toption = {\n")
    f.write('\t\tname = "tradition_unlock_menu.opt_all_safe"\n')
    f.write('\t\tcustom_tooltip = "tradition_unlock_menu.opt_all_safe_tt"\n')
    for n in all_complete_nodes:
        f.write(f"\t\tactivate_tradition = {n}\n")
    f.write("\t\tcountry_event = { id = tradition_unlock_menu.1 }\n")
    f.write("\t}\n\n")

    # 3. 按 Mod 来源分别选择激活
    f.write("\t# 3. 按 Mod 来源分别选择激活\n")
    f.write("\toption = {\n")
    f.write('\t\tname = "tradition_unlock_menu.opt_by_mod"\n')
    f.write('\t\tcustom_tooltip = "tradition_unlock_menu.opt_by_mod_tt"\n')
    f.write("\t\tcountry_event = { id = tradition_unlock_menu.2 }\n")
    f.write("\t}\n\n")

    # 4. 返回主控制台
    f.write("\t# 返回主控制台\n")
    f.write("\toption = {\n")
    f.write('\t\tname = "tradition_unlock_menu.back"\n')
    f.write("\t\tcountry_event = { id = auto_qol_menu.1 }\n")
    f.write("\t}\n")
    f.write("}\n\n")

    # 子菜单：按 Mod 来源分别激活
    f.write("# 按 Mod 来源独立激活子菜单\n")
    f.write("country_event = {\n")
    f.write("\tid = tradition_unlock_menu.2\n")
    f.write('\ttitle = "tradition_unlock_menu.2.name"\n')
    f.write('\tdesc = "tradition_unlock_menu.2.desc"\n')
    f.write("\tpicture = GFX_evt_giga_menu\n")
    f.write("\tis_triggered_only = yes\n\n")

    # 原版官方传统选项 (含外交、敌意)
    f.write("\t# 【激活】原版官方传统全套 (含外交、敌意等，排除初始特质+1)\n")
    f.write("\toption = {\n")
    f.write('\t\tname = "tradition_unlock_mod_vanilla"\n')
    f.write('\t\tcustom_tooltip = "tradition_unlock_mod_vanilla_tt"\n')
    for n in vanilla_nodes:
        f.write(f"\t\tactivate_tradition = {n}\n")
    f.write("\t\tcountry_event = { id = tradition_unlock_menu.2 }\n")
    f.write("\t}\n\n")

    # 各 Mod 选项
    mod_meta = {
        '2438313459': ('tidy', '更加整洁的传统 (Tidy Tradition)'),
        '1747099270': ('wg', '战舰少女R与苍青幻影 (Warship Girls R)'),
        '2409276081': ('patch', '通用游戏规则补丁 Patch'),
        '2982710154': ('hsr', '星穹铁道 (Honkai: Star Rail)'),
        '2748029219': ('mega', '巨型企业平衡调整 (Megacorp re-balance)'),
        '2955622956': ('mem', '更多随机事件 (More Events Mod)'),
    }

    # 扫描 Mod 对应 nodes
    mod_nodes_dict = defaultdict(list)
    for f_mod in workshop_dir.glob('**/common/traditions/*.txt'):
        parts = f_mod.parts
        mod_id = 'unknown'
        for i, p in enumerate(parts):
            if p == '281990' and i + 1 < len(parts):
                mod_id = parts[i+1]
                break
        c_mod = f_mod.read_text(encoding='utf-8', errors='ignore')
        for m_node in re.finditer(r'^\s*(tr_[a-zA-Z0-9_-]+)\s*=', c_mod, re.MULTILINE):
            node_name = m_node.group(1)
            if node_name not in BLACKLIST and node_name not in mod_nodes_dict[mod_id]:
                mod_nodes_dict[mod_id].append(node_name)

    for mod_id, (key, display_name) in mod_meta.items():
        nodes = mod_nodes_dict.get(mod_id, [])
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

print(f"Updated {events_path} successfully!")

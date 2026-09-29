import os, re
from pathlib import Path

from paths import GAME_INSTALL_DIR, DOCS_DIR, EVENTS_DIR

docs_dir = DOCS_DIR
vanilla_dir = GAME_INSTALL_DIR / "common" / "traditions"

# 1. 提取原版纯正常规普通帝国适用的传统树 (90个节点)
regular_prefixes = [
    'tr_diplomacy_',   # 外交
    'tr_enmity_',      # 敌意
    'tr_discovery_',   # 探索
    'tr_expansion_',   # 扩张
    'tr_domination_',  # 支配
    'tr_prosperity_',  # 繁荣
    'tr_harmony_',     # 和谐
    'tr_supremacy_',   # 至高
    'tr_unyielding_',  # 不屈
    'tr_subterfuge_',  # 宿命/诡道
    'tr_statecraft_',  # 治国
    'tr_aptitude_',    # 天赋
    'tr_archivism_',   # 归档
]

# 严格黑名单
blacklist = {'tr_aptitude_finish'}

vanilla_regular_nodes = []
for f in sorted(vanilla_dir.glob('*.txt')):
    c = f.read_text(encoding='utf-8', errors='ignore')
    for m in re.finditer(r'^\s*(tr_[a-zA-Z0-9_-]+)\s*=', c, re.MULTILINE):
        node = m.group(1)
        if node in blacklist:
            continue
        if any(node.startswith(rt) for rt in regular_prefixes):
            if not any(k in node for k in ['hive', 'machine', 'gestalt', 'cloning', 'cybernetic', 'synthetic']):
                if node not in vanilla_regular_nodes:
                    vanilla_regular_nodes.append(node)

# 2. 提取《更加整洁的传统 (Tidy Tradition)》的 133 个纯净安全节点
tidy_file = docs_dir / "unlock_tidy_tradition.txt"
tidy_nodes = []
if tidy_file.exists():
    for line in tidy_file.read_text(encoding='utf-8', errors='ignore').splitlines():
        line = line.strip()
        if line.startswith('activate_tradition '):
            n = line.split()[1]
            if n not in tidy_nodes and n.startswith('tr_tt_') and 'ultralimit' not in n:
                tidy_nodes.append(n)

# 组合纯净普适节点
pure_safe_nodes = vanilla_regular_nodes + tidy_nodes
print(f"Total pure safe nodes: {len(pure_safe_nodes)} (Vanilla: {len(vanilla_regular_nodes)}, Tidy: {len(tidy_nodes)})")
assert 'tr_diplomacy_adopt' in pure_safe_nodes
assert 'tr_enmity_adopt' in pure_safe_nodes
assert not any('wg_' in n or 'sh_' in n for n in pure_safe_nodes), "Found warship girls or shenhai node!"

# 3. 写入 unlock_safe_only.txt
output_safe = docs_dir / "unlock_safe_only.txt"
lines = [
    "# ==============================================================================",
    "# 纯净通用无门槛传统脚本 (常规帝国专属)",
    "# 运行方式: 控制台输入: run unlock_safe_only.txt",
    "# 包含内容: 原版常规通用传统 (含外交、敌意等 90 节点) + 更加整洁的传统 (133 节点)",
    "# 绝对纯净: 零舰娘/深海、零星铁、零蜂巢/机械专属，并已彻底跳过领袖初始特质+1！",
    f"# 共计包含: {len(pure_safe_nodes)} 个节点",
    "# ==============================================================================",
    ""
]
for n in pure_safe_nodes:
    lines.append(f"activate_tradition {n}")

output_safe.write_text("\n".join(lines) + "\n", encoding='utf-8')
print(f"Successfully wrote pure clean: {output_safe}")

# 4. 更新游戏内 tradition_unlock_events.txt
events_path = EVENTS_DIR / 'tradition_unlock_events.txt'
with open(events_path, 'w', encoding='utf-8') as f:
    f.write("namespace = tradition_unlock_menu\n\n")

    f.write("# 纯净版传统解锁助手界面 (零卡顿、零错误)\n")
    f.write("country_event = {\n")
    f.write("\tid = tradition_unlock_menu.1\n")
    f.write('\ttitle = "tradition_unlock_menu.1.name"\n')
    f.write('\tdesc = "tradition_unlock_menu.1.desc"\n')
    f.write("\tpicture = GFX_evt_diplomatic_relations\n")
    f.write("\tis_triggered_only = yes\n\n")

    # 选项 1: 一键激活纯净通用传统 (原版外交敌意 + 更加整洁的传统)
    f.write("\t# 1. 一键激活纯净通用传统 (原版外交/敌意 + 更加整洁的传统)\n")
    f.write("\toption = {\n")
    f.write('\t\tname = "tradition_unlock_menu.opt_universal"\n')
    f.write('\t\tcustom_tooltip = "tradition_unlock_menu.opt_universal_tt"\n')
    f.write("\t\thidden_effect = {\n")
    for n in pure_safe_nodes:
        f.write(f"\t\t\tactivate_tradition = {n}\n")
    f.write("\t\t\tcountry_event = { id = tradition_unlock_menu.1 }\n")
    f.write("\t\t}\n")
    f.write("\t}\n\n")

    # 选项 2: 仅激活更加整洁的传统
    f.write("\t# 2. 仅激活更加整洁的传统\n")
    f.write("\toption = {\n")
    f.write('\t\tname = "tradition_unlock_mod_tidy"\n')
    f.write('\t\tcustom_tooltip = "tradition_unlock_mod_tidy_tt"\n')
    f.write("\t\thidden_effect = {\n")
    for n in tidy_nodes:
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

print(f"Successfully updated {events_path}!")

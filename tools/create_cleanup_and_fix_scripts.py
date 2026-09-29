import os, re
from pathlib import Path

from paths import GAME_INSTALL_DIR, DOCS_DIR, EVENTS_DIR

docs_dir = DOCS_DIR
vanilla_dir = GAME_INSTALL_DIR / "common" / "traditions"

# ==============================================================================
# 1. 生成紧急清毒脚本: fix_save_remove_bad_tr.txt
# 解决用户按 F2 闪退 (拔除存档残留的 tr_tt_ultralimit)，并卸载天赋与误加的舰娘传统
# ==============================================================================
cleanup_file = docs_dir / "fix_save_remove_bad_tr.txt"
cleanup_lines = [
    "# ==============================================================================",
    "# 存档毒素清理与修复脚本 (解决 F2 崩溃、拔除天赋与舰娘残留)",
    "# 运行方式: 进入游戏打开控制台 (按 ~ 键) 输入: run fix_save_remove_bad_tr.txt",
    "# ==============================================================================",
    "",
    "# 1. 彻底拔除导致 F2 除以零崩溃的极限传统 (tr_tt_ultralimit)",
    "remove_tradition tr_tt_ultralimit_adopt",
    "remove_tradition tr_tt_ultralimit_1",
    "remove_tradition tr_tt_ultralimit_2",
    "remove_tradition tr_tt_ultralimit_3",
    "remove_tradition tr_tt_ultralimit_4",
    "remove_tradition tr_tt_ultralimit_5",
    "remove_tradition tr_tt_ultralimit_finish",
    "",
    "# 2. 彻底拔除导致建造除以零崩溃的圆环传统",
    "remove_tradition tr_adaptability_homura",
    "remove_tradition tr_adaptability_kyoko",
    "remove_tradition tr_adaptability_madoka",
    "remove_tradition tr_adaptability_mami",
    "remove_tradition tr_adaptability_sayaka",
    "",
    "# 3. 彻底卸除天赋传统全套 (杜绝领袖初始特质+1与特质池污染)",
    "remove_tradition tr_aptitude_finish",
    "remove_tradition tr_aptitude_adopt",
    "remove_tradition tr_aptitude_the_empire_needs_you",
    "remove_tradition tr_aptitude_specialist_training",
    "remove_tradition tr_aptitude_psychological_profiling",
    "remove_tradition tr_aptitude_healthcare_program",
    "remove_tradition tr_aptitude_champions_of_the_empire",
    "",
    "# 4. 彻底拔除普通帝国身上误加的舰娘与深海专属传统",
    "remove_tradition tr_sh_icebreaking_adopt",
    "remove_tradition tr_sh_icebreaking_1",
    "remove_tradition tr_sh_icebreaking_2",
    "remove_tradition tr_sh_icebreaking_3",
    "remove_tradition tr_sh_icebreaking_4",
    "remove_tradition tr_sh_icebreaking_5",
    "remove_tradition tr_sh_icebreaking_finish",
    "remove_tradition tr_sh_silent_adopt",
    "remove_tradition tr_sh_silent_1",
    "remove_tradition tr_sh_silent_2",
    "remove_tradition tr_sh_silent_3",
    "remove_tradition tr_sh_silent_4",
    "remove_tradition tr_sh_silent_5",
    "remove_tradition tr_sh_silent_finish",
    "remove_tradition tr_wg_mist_adopt",
    "remove_tradition tr_wg_mist_1",
    "remove_tradition tr_wg_mist_2",
    "remove_tradition tr_wg_mist_3",
    "remove_tradition tr_wg_mist_4",
    "remove_tradition tr_wg_mist_5",
    "remove_tradition tr_wg_mist_finish",
    "remove_tradition tr_wg_projects_adopt",
    "remove_tradition tr_wg_projects_1",
    "remove_tradition tr_wg_projects_2",
    "remove_tradition tr_wg_projects_3",
    "remove_tradition tr_wg_projects_4",
    "remove_tradition tr_wg_projects_5",
    "remove_tradition tr_wg_projects_finish",
    "remove_tradition tr_wg_shop_adopt",
    "remove_tradition tr_wg_shop_1",
    "remove_tradition tr_wg_shop_2",
    "remove_tradition tr_wg_shop_3",
    "remove_tradition tr_wg_shop_4",
    "remove_tradition tr_wg_shop_5",
    "remove_tradition tr_wg_shop_finish",
    ""
]
cleanup_file.write_text("\n".join(cleanup_lines), encoding='utf-8')
print(f"Generated cleanup script: {cleanup_file}")


# ==============================================================================
# 2. 重新构建 100% 完美的 unlock_safe_only.txt
# - 补齐【适应】(tr_adaptability_*)
# - 彻底剔除【天赋】(tr_aptitude_*) 整个传统树！
# - 保留原版外交、敌意、探索、扩张、支配、繁荣、和谐、至高、不屈、诡道、治国、归档
# - 加上《更加整洁的传统》126 节点
# ==============================================================================
regular_prefixes = [
    'tr_mercantile_',   # 商业 (修复用户截图商业未采纳问题)
    'tr_politics_',      # 政治
    'tr_domestication_', # 驯化 (大档案)
    'tr_logistics_',     # 后勤
    'tr_diplomacy_',    # 外交
    'tr_enmity_',       # 敌意
    'tr_adaptability_', # 适应 (补齐！)
    'tr_discovery_',    # 探索
    'tr_expansion_',    # 扩张
    'tr_domination_',   # 支配
    'tr_prosperity_',   # 繁荣
    'tr_harmony_',      # 和谐
    'tr_supremacy_',    # 至高
    'tr_unyielding_',   # 不屈
    'tr_subterfuge_',   # 宿命/诡道
    'tr_statecraft_',   # 治国
    'tr_archivism_',    # 归档
]
# 彻底排除天赋整棵树！(tr_aptitude_)

vanilla_nodes = []
for f in sorted(vanilla_dir.glob('*.txt')):
    c = f.read_text(encoding='utf-8', errors='ignore')
    for m in re.finditer(r'^\s*(tr_[a-zA-Z0-9_-]+)\s*=', c, re.MULTILINE):
        node = m.group(1)
        if any(node.startswith(rt) for rt in regular_prefixes):
            if not any(k in node for k in ['hive', 'machine', 'gestalt', 'cloning', 'cybernetic', 'synthetic']):
                if node not in vanilla_nodes:
                    vanilla_nodes.append(node)

# 提取整洁传统的 126 节点
tidy_file = docs_dir / "unlock_tidy_tradition.txt"
tidy_nodes = []
if tidy_file.exists():
    for line in tidy_file.read_text(encoding='utf-8', errors='ignore').splitlines():
        line = line.strip()
        if line.startswith('activate_tradition '):
            n = line.split()[1]
            if n not in tidy_nodes and n.startswith('tr_tt_') and 'ultralimit' not in n:
                tidy_nodes.append(n)

pure_safe_nodes = vanilla_nodes + tidy_nodes
print(f"Total safe nodes: {len(pure_safe_nodes)} (Vanilla: {len(vanilla_nodes)}, Tidy: {len(tidy_nodes)})")
assert 'tr_adaptability_adopt' in pure_safe_nodes, "Adaptability adopt missing!"
assert 'tr_adaptability_finish' in pure_safe_nodes, "Adaptability finish missing!"
assert not any('aptitude' in n for n in pure_safe_nodes), "Aptitude found in pure safe nodes!"

output_safe = docs_dir / "unlock_safe_only.txt"
lines_safe = [
    "# ==============================================================================",
    "# 纯净通用无门槛传统脚本 (常规帝国专属)",
    "# 运行方式: 控制台输入: run unlock_safe_only.txt",
    "# 包含内容: 原版常规通用传统 (含适应、外交、敌意等 91 节点) + 更加整洁的传统 (126 节点)",
    "# 绝对纯净: 零舰娘/深海、零星铁、零蜂巢/机械专属，并已彻底排除天赋树(避免初始特质+1)！",
    f"# 共计包含: {len(pure_safe_nodes)} 个节点",
    "# ==============================================================================",
    ""
]
for n in pure_safe_nodes:
    lines_safe.append(f"activate_tradition {n}")

output_safe.write_text("\n".join(lines_safe) + "\n", encoding='utf-8')
print(f"Successfully generated clean: {output_safe}")

# ==============================================================================
# 3. 同步更新 events/tradition_unlock_events.txt
# ==============================================================================
events_path = EVENTS_DIR / 'tradition_unlock_events.txt'
with open(events_path, 'w', encoding='utf-8') as f:
    f.write("namespace = tradition_unlock_menu\n\n")

    f.write("# 纯净版传统解锁助手界面 (零卡顿、零错误、含适应、排除天赋与崩溃)\n")
    f.write("country_event = {\n")
    f.write("\tid = tradition_unlock_menu.1\n")
    f.write('\ttitle = "tradition_unlock_menu.1.name"\n')
    f.write('\tdesc = "tradition_unlock_menu.1.desc"\n')
    f.write("\tpicture = GFX_evt_diplomatic_relations\n")
    f.write("\tis_triggered_only = yes\n\n")

    # 选项 1: 一键激活纯净通用传统 (原版适应/外交/敌意 + 更加整洁的传统)
    f.write("\t# 1. 一键激活纯净通用传统 (原版适应/外交/敌意 + 更加整洁的传统)\n")
    f.write("\toption = {\n")
    f.write('\t\tname = "tradition_unlock_menu.opt_universal"\n')
    f.write('\t\tcustom_tooltip = "tradition_unlock_menu.opt_universal_tt"\n')
    f.write("\t\thidden_effect = {\n")
    for n in pure_safe_nodes:
        f.write(f"\t\t\tadd_tradition = {n}\n")
    f.write("\t\t\tcountry_event = { id = tradition_unlock_menu.1 }\n")
    f.write("\t\t}\n")
    f.write("\t}\n\n")

    # 选项 2: 仅激活更加整洁的传统
    f.write("\t# 2. 仅激活更加整洁的传统\n")
    f.write('\toption = {\n')
    f.write('\t\tname = "tradition_unlock_mod_tidy"\n')
    f.write('\t\tcustom_tooltip = "tradition_unlock_mod_tidy_tt"\n')
    f.write("\t\thidden_effect = {\n")
    for n in tidy_nodes:
        f.write(f"\t\t\tadd_tradition = {n}\n")
    f.write("\t\t\tcountry_event = { id = tradition_unlock_menu.1 }\n")
    f.write("\t\t}\n")
    f.write("\t}\n\n")

    # 选项 3: 返回主控制台
    f.write("\t# 返回主控制台\n")
    f.write('\toption = {\n')
    f.write('\t\tname = "tradition_unlock_menu.back"\n')
    f.write("\t\tcountry_event = { id = auto_qol_menu.1 }\n")
    f.write("\t}\n")
    f.write("}\n")

print(f"Updated {events_path} successfully!")

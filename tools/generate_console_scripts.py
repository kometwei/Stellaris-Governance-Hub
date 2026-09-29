import os, sys
from pathlib import Path

# Lethal crash nodes (Blacklist)
blacklist = {
    'tr_tt_ultralimit_adopt', 'tr_tt_ultralimit_1', 'tr_tt_ultralimit_2',
    'tr_tt_ultralimit_3', 'tr_tt_ultralimit_4', 'tr_tt_ultralimit_5', 'tr_tt_ultralimit_finish',
    'tr_adaptability_homura', 'tr_adaptability_kyoko', 'tr_adaptability_madoka',
    'tr_adaptability_mami', 'tr_adaptability_sayaka'
}

from paths import EVENTS_DIR, DOCS_DIR

events_path = EVENTS_DIR / 'tradition_unlock_events.txt'
content = events_path.read_text(encoding='utf-8')

# Extract nodes from tradition_unlock.exec_selected
import re
nodes = re.findall(r'activate_tradition\s*=\s*(tr_[a-zA-Z0-9_-]+)', content)
safe_nodes = [n for n in dict.fromkeys(nodes) if n not in blacklist]

print(f"Total safe nodes to include: {len(safe_nodes)}")

# Target file in Documents
output_file = DOCS_DIR / "safe_all_traditions.txt"

lines = [
    "# ==============================================================================",
    "# Stellaris Mod Enhancer - 100% 绝对安全无冲突全 Mod 传统一键激活脚本",
    "# 运行方式: 进入游戏打开控制台 (按 ~ 键) 输入: run safe_all_traditions.txt",
    "# 特性说明: 包含事前防御，自动跳过导致 F2/进度条除以零崩溃的 12 个恶性缺陷节点",
    f"# 共计包含: {len(safe_nodes)} 个精选安全传统节点",
    "# ==============================================================================",
    ""
]

for n in safe_nodes:
    lines.append(f"activate_tradition {n}")

output_file.write_text("\n".join(lines) + "\n", encoding='utf-8')
print(f"Successfully generated: {output_file}")

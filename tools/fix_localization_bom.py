import re
from pathlib import Path

loc_path = Path(__file__).resolve().parent.parent / "localisation" / "simp_chinese" / "auto_qol_l_simp_chinese.yml"
text = loc_path.read_text(encoding='utf-8-sig', errors='ignore')
while text.startswith('\ufeff'):
    text = text[1:]
text = text.lstrip()
if not text.startswith('l_simp_chinese:'):
    text = 'l_simp_chinese:\r\n' + text

# 检查法令 key 替换
fleet_edicts_keys = [
    ("auto_qol_naval_cap_add_1000", "扩展舰队容量 (+1000)", "调动帝国造船厂储备，直接增加 1000 点基础舰队容量。"),
    ("auto_qol_naval_cap_add_5000", "扩展舰队容量 (+5000)", "调动帝国造船厂储备，直接增加 5000 点基础舰队容量。"),
    ("auto_qol_naval_cap_add_10000", "扩展舰队容量 (+10000)", "调动帝国造船厂储备，直接增加 10000 点基础舰队容量。"),
    ("auto_qol_naval_cap_add_50000", "扩展舰队容量 (+50000)", "调动帝国造船厂储备，直接增加 50000 点基础舰队容量。"),
    ("auto_qol_naval_cap_mult_2", "倍增舰队容量 (x2)", "启用大规模后勤倍增算法，使帝国总舰队容量翻倍 (+100%)。"),
    ("auto_qol_naval_cap_mult_5", "倍增舰队容量 (x5)", "启用大规模后勤倍增算法，使帝国总舰队容量提升至 5 倍 (+400%)。"),
    ("auto_qol_naval_cap_mult_10", "倍增舰队容量 (x10)", "启用大规模后勤倍增算法，使帝国总舰队容量提升至 10 倍 (+900%)。"),
    ("auto_qol_cmd_limit_add_100", "扩展指挥上限 (+100)", "升级舰队神经网络中枢，直接增加单个舰队 100 点指挥上限。"),
    ("auto_qol_cmd_limit_add_500", "扩展指挥上限 (+500)", "升级舰队神经网络中枢，直接增加单个舰队 500 点指挥上限。"),
    ("auto_qol_cmd_limit_add_1000", "扩展指挥上限 (+1000)", "升级舰队神经网络中枢，直接增加单个舰队 1000 点指挥上限。"),
    ("auto_qol_cmd_limit_mult_2", "倍增指挥上限 (x2)", "重构集群协同协议，使单支舰队的指挥上限翻倍 (+100%)。"),
    ("auto_qol_cmd_limit_mult_5", "倍增指挥上限 (x5)", "重构集群协同协议，使单支舰队的指挥上限提升至 5 倍 (+400%)。"),
    ("auto_qol_cmd_limit_mult_10", "倍增指挥上限 (x10)", "重构集群协同协议，使单支舰队的指挥上限提升至 10 倍 (+900%)。"),
]

# 生成法令本地化文本块
edicts_loc_block = []
for k, title, desc in fleet_edicts_keys:
    edicts_loc_block.append(f' {k}:0 "{title}"')
    edicts_loc_block.append(f' edict_{k}:0 "{title}"')
    edicts_loc_block.append(f' {k}_desc:0 "{desc}"')
    edicts_loc_block.append(f' edict_{k}_desc:0 "{desc}"')

# 替换旧的法令段落
old_pat = re.compile(r'\s*edict_auto_qol_naval_cap_add_1000:0[\s\S]*?edict_auto_qol_cmd_limit_mult_10_desc:0[^\n]*\n')
if old_pat.search(text):
    text = old_pat.sub('\n' + '\n'.join(edicts_loc_block) + '\n\n', text)
else:
    # 插入到 auto_qol_council_menu 之前
    idx = text.find('auto_qol_council_menu.1.name:0')
    if idx != -1:
        text = text[:idx] + '\n'.join(edicts_loc_block) + '\n\n ' + text[idx:]

# 确保原版官方传统按钮本地化
if 'tradition_unlock_mod_vanilla:0' not in text:
    idx2 = text.find('tradition_unlock_mod_tidy:0')
    if idx2 != -1:
        v_loc = ' tradition_unlock_mod_vanilla:0 "【激活】原版官方传统全套 (含外交、敌意等，排除初始特质+1)"\n tradition_unlock_mod_vanilla_tt:0 "激活原版官方所有经典传统树（外交、敌意、探索、繁荣、至高、支配等），且已安全跳过导致领袖初始特质+1的天赋收官效果！"\n'
        text = text[:idx2] + v_loc + text[idx2:]

# 强制以 UTF-8 with BOM 写入
loc_path.write_text(text, encoding='utf-8-sig')
print("Successfully wrote auto_qol_l_simp_chinese.yml with UTF-8 BOM!")

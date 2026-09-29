import os, re
from pathlib import Path
from collections import defaultdict

from paths import COMMON_DIR, LOCALISATION_DIR, DOCS_DIR

def main():
    doc_dir = DOCS_DIR
    with open(doc_dir / 'unlock_all_mod_tr.txt', 'r', encoding='utf-8') as f:
        all_text = f.read()

    mod_keys = [
        ("1747099270", "战舰少女R与苍青幻影"),
        ("2409276081", "通用游戏规则补丁 Patch"),
        ("2438313459", "更加整洁的传统 (Tidy Tradition)"),
        ("2748029219", "缤纷多彩の银河"),
        ("2955622956", "(ANK)四大飞升不互斥"),
        ("2982710154", "崩坏：星穹铁道"),
        ("3120810990", "治愈强迫症-3 不再SL灵能科技"),
        ("3250607992", "圆环的庇护"),
        ("3397553525", "巨型企业平衡调整"),
        ("727000451", "更多随机事件 (More Events Mod)"),
        ("vanilla", "【原版群星】官方传统"),
    ]

    curr_mid = None
    mod_trs = defaultdict(lambda: defaultdict(list))

    for line in all_text.splitlines():
        m = re.search(r'# \[来源\].*?\(ID: (.*?)\)', line)
        if m:
            curr_mid = m.group(1)
            continue
        line_s = line.strip()
        tr = None
        if line_s.startswith('activate_tradition '):
            tr = line_s.split()[1]
            mod_trs[curr_mid]['universal'].append(tr)
        elif line_s.startswith('# activate_tradition '):
            parts = line_s.split()
            if len(parts) >= 3:
                tr = parts[2]
                conds = ''
                m = re.search(r'\[🔒需要外部条件:\s*(.*?)\]', line_s)
                if m:
                    conds = m.group(1)
                
                # Exclude internal dummy mechanic tokens
                if '隐藏内置传统' in conds:
                    continue
                
                if '机械限定' in conds or 'civic_machine_assimilator' in conds:
                    mod_trs[curr_mid]['machine'].append(tr)
                elif '格式塔限定' in conds:
                    mod_trs[curr_mid]['gestalt'].append(tr)
                elif 'auth_shenhai' in conds or 'ap_shenhai' in conds:
                    mod_trs[curr_mid]['auth_shenhai'].append(tr)
                elif 'auth_united_fleet' in conds:
                    mod_trs[curr_mid]['auth_united_fleet'].append(tr)
                elif 'auth_warshipgirls' in conds or 'ap_mist' in conds or 'ap_project_s' in conds:
                    mod_trs[curr_mid]['auth_warshipgirls'].append(tr)
                elif 'origin_mindwardens' in conds:
                    mod_trs[curr_mid]['origin_mindwardens'].append(tr)
                elif 'origin_StellaronHunter' in conds:
                    mod_trs[curr_mid]['origin_StellaronHunter'].append(tr)
                elif 'origin_luosi_star' in conds:
                    mod_trs[curr_mid]['origin_luosi_star'].append(tr)
                elif 'origin_Xianzhou' in conds:
                    mod_trs[curr_mid]['origin_Xianzhou'].append(tr)
                elif 'origin_endbringers' in conds:
                    mod_trs[curr_mid]['origin_endbringers'].append(tr)
                elif '限制灭世者:yes' in conds:
                    mod_trs[curr_mid]['homicidal'].append(tr)
                elif '限制灭世者:no' in conds:
                    mod_trs[curr_mid]['non_homicidal'].append(tr)
                elif '特殊帝国限定:no' in conds:
                    mod_trs[curr_mid]['standard_empire'].append(tr)
                else:
                    mod_trs[curr_mid]['universal'].append(tr)

    # 1. Generate button effects with smart authority/government conditions
    be_file = COMMON_DIR / 'button_effects' / 'auto_qol_tradition_button_effects.txt'
    with open(be_file, 'w', encoding='utf-8') as f:
        f.write("# 传统管理专属仪表盘按钮底层效果 (含政体自适应匹配)\n\n")
        
        # Dual-state toggle buttons for mod 1..11
        for i in range(1, 12):
            f.write(f"# Mod {i} ON button (checked -> click to uncheck)\n")
            f.write(f"auto_qol_btn_tr_mod_{i}_on = {{\n")
            f.write(f"\tpotential = {{ has_country_flag = qol_tr_sel_mod_{i} }}\n")
            f.write("\tallow = { always = yes }\n")
            f.write("\teffect = {\n")
            f.write(f"\t\tremove_country_flag = qol_tr_sel_mod_{i}\n")
            f.write("\t\tcountry_event = { id = auto_qol_tradition_gui.1 }\n")
            f.write("\t}\n}\n\n")

            f.write(f"# Mod {i} OFF button (unchecked -> click to check)\n")
            f.write(f"auto_qol_btn_tr_mod_{i}_off = {{\n")
            f.write(f"\tpotential = {{ NOT = {{ has_country_flag = qol_tr_sel_mod_{i} }} }}\n")
            f.write("\tallow = { always = yes }\n")
            f.write("\teffect = {\n")
            f.write(f"\t\tset_country_flag = qol_tr_sel_mod_{i}\n")
            f.write("\t\tcountry_event = { id = auto_qol_tradition_gui.1 }\n")
            f.write("\t}\n}\n\n")

        # Select all / Clear all
        f.write("auto_qol_btn_select_all_tr_mods = {\n")
        f.write("\tpotential = { always = yes }\n")
        f.write("\tallow = { always = yes }\n")
        f.write("\teffect = {\n")
        for i in range(1, 12):
            f.write(f"\t\tset_country_flag = qol_tr_sel_mod_{i}\n")
        f.write("\t\tcountry_event = { id = auto_qol_tradition_gui.1 }\n")
        f.write("\t}\n}\n\n")

        f.write("auto_qol_btn_clear_all_tr_mods = {\n")
        f.write("\tpotential = { always = yes }\n")
        f.write("\tallow = { always = yes }\n")
        f.write("\teffect = {\n")
        for i in range(1, 12):
            f.write(f"\t\tremove_country_flag = qol_tr_sel_mod_{i}\n")
        f.write("\t\tcountry_event = { id = auto_qol_tradition_gui.1 }\n")
        f.write("\t}\n}\n\n")

        # Execute safe traditions with intelligent government matching
        f.write("auto_qol_btn_exec_safe_traditions = {\n")
        f.write("\tpotential = { always = yes }\n")
        f.write("\tallow = { always = yes }\n")
        f.write("\teffect = {\n")
        
        for i, (mid, name) in enumerate(mod_keys, 1):
            d = mod_trs[mid]
            total_tr = sum(len(v) for v in d.values())
            f.write(f"\t\t# ========================================================\n")
            f.write(f"\t\t# Mod {i}: {name} (共 {total_tr} 条政体匹配传统)\n")
            f.write(f"\t\t# ========================================================\n")
            f.write(f"\t\tif = {{\n")
            f.write(f"\t\t\tlimit = {{ has_country_flag = qol_tr_sel_mod_{i} }}\n")

            # 1. Universal traditions (no restrictions)
            if d['universal']:
                f.write("\t\t\t# 通用传统 (所有国家均可激活)\n")
                for tr in d['universal']:
                    f.write(f"\t\t\tactivate_tradition = {tr}\n")

            # 2. Standard empire only (non-gestalt)
            if d['standard_empire'] or d['non_homicidal']:
                f.write("\t\t\t# 常规非格式塔帝国专属传统\n")
                f.write("\t\t\tif = {\n")
                f.write("\t\t\t\tlimit = { is_gestalt = no }\n")
                for tr in d['standard_empire']:
                    f.write(f"\t\t\t\tactivate_tradition = {tr}\n")
                if d['non_homicidal']:
                    f.write("\t\t\t\tif = {\n")
                    f.write("\t\t\t\t\tlimit = { is_homicidal = no }\n")
                    for tr in d['non_homicidal']:
                        f.write(f"\t\t\t\t\tactivate_tradition = {tr}\n")
                    f.write("\t\t\t\t}\n")
                f.write("\t\t\t}\n")

            # 3. Machine empire only
            if d['machine']:
                f.write("\t\t\t# 机械帝国专属传统\n")
                f.write("\t\t\tif = {\n")
                f.write("\t\t\t\tlimit = {\n")
                f.write("\t\t\t\t\tOR = {\n")
                f.write("\t\t\t\t\t\thas_authority = auth_machine_intelligence\n")
                f.write("\t\t\t\t\t\tis_synthetic_empire = yes\n")
                f.write("\t\t\t\t\t}\n")
                f.write("\t\t\t\t}\n")
                for tr in d['machine']:
                    f.write(f"\t\t\t\tactivate_tradition = {tr}\n")
                f.write("\t\t\t}\n")

            # 4. Gestalt general (Hive / Machine)
            if d['gestalt']:
                f.write("\t\t\t# 格式塔 (蜂巢/机械) 专属传统\n")
                f.write("\t\t\tif = {\n")
                f.write("\t\t\t\tlimit = { is_gestalt = yes }\n")
                for tr in d['gestalt']:
                    f.write(f"\t\t\t\tactivate_tradition = {tr}\n")
                f.write("\t\t\t}\n")

            # 5. Homicidal only (Fanatic Purifiers etc.)
            if d['homicidal']:
                f.write("\t\t\t# 灭世者专属传统\n")
                f.write("\t\t\tif = {\n")
                f.write("\t\t\t\tlimit = { is_homicidal = yes }\n")
                for tr in d['homicidal']:
                    f.write(f"\t\t\t\tactivate_tradition = {tr}\n")
                f.write("\t\t\t}\n")

            # 6. Mod-specific Authorities & Origins
            if d['auth_shenhai']:
                f.write("\t\t\t# 深海政体专属传统\n")
                f.write("\t\t\tif = {\n")
                f.write("\t\t\t\tlimit = { has_authority = auth_shenhai }\n")
                for tr in d['auth_shenhai']:
                    f.write(f"\t\t\t\tactivate_tradition = {tr}\n")
                f.write("\t\t\t}\n")

            if d['auth_united_fleet']:
                f.write("\t\t\t# 联合舰队政体专属传统\n")
                f.write("\t\t\tif = {\n")
                f.write("\t\t\t\tlimit = { has_authority = auth_united_fleet }\n")
                for tr in d['auth_united_fleet']:
                    f.write(f"\t\t\t\tactivate_tradition = {tr}\n")
                f.write("\t\t\t}\n")

            if d['auth_warshipgirls']:
                f.write("\t\t\t# 舰娘政体专属传统\n")
                f.write("\t\t\tif = {\n")
                f.write("\t\t\t\tlimit = { has_authority = auth_warshipgirls }\n")
                for tr in d['auth_warshipgirls']:
                    f.write(f"\t\t\t\tactivate_tradition = {tr}\n")
                f.write("\t\t\t}\n")

            # Origins
            for orig in ['origin_mindwardens', 'origin_StellaronHunter', 'origin_luosi_star', 'origin_Xianzhou', 'origin_endbringers']:
                if d[orig]:
                    f.write(f"\t\t\t# {orig} 起源专属传统\n")
                    f.write("\t\t\tif = {\n")
                    f.write(f"\t\t\t\tlimit = {{ has_origin = {orig} }}\n")
                    for tr in d[orig]:
                        f.write(f"\t\t\t\tactivate_tradition = {tr}\n")
                    f.write("\t\t\t}\n")

            f.write(f"\t\t}}\n\n")

        f.write("\t\tcountry_event = { id = auto_qol_tradition_gui.1 }\n")
        f.write("\t}\n}\n\n")

        # Close button
        f.write("auto_qol_btn_close_tradition_gui = {\n")
        f.write("\tpotential = { always = yes }\n")
        f.write("\tallow = { always = yes }\n")
        f.write("\teffect = {\n")
        f.write("\t\tcountry_event = { id = auto_qol_menu.1 }\n")
        f.write("\t}\n}\n")

    print("Written smart button effects to:", be_file)

    # 2. Update localisation file
    loc_file = LOCALISATION_DIR / 'auto_qol_l_simp_chinese.yml'
    with open(loc_file, 'r', encoding='utf-8-sig') as f:
        loc_text = f.read()

    # Rebuild tradition loc lines
    tr_locs = [
        ' auto_qol_tr.gui_title:0 "Mod 传统定制管理中心 (政体智能适配)"',
        ' auto_qol_tr.desc:0 "§E【政体自适应安全激活系统】§!\\n在此直接勾选需要激活传统的 Mod 来源。\\n系统将根据你当前帝国的§Y政体形态 (常规帝国/机械智能/蜂巢思维/Mod政体)§!自动精准匹配对应传统分支，§G彻底杜绝错配导致的 F2 外交闪退 (CTD)§!。\\n选定后点击下方§G【执行激活已选 Mod 传统】§!即可生效。"',
        ' auto_qol_tr.btn_select_all:0 "§Y⚡ 全部勾选§!"',
        ' auto_qol_tr.btn_clear_all:0 "§R✕ 全部取消§!"',
        ' auto_qol_tr.btn_exec:0 "§G▶ 执行激活已选 Mod 传统§!"',
        ' auto_qol_tr.btn_return:0 "§M◀ 保存并返回主菜单§!"',
    ]
    for i, (mid, name) in enumerate(mod_keys, 1):
        count = sum(len(v) for v in mod_trs[mid].values())
        tr_locs.append(f' auto_qol_tr.mod_{i}_off:0 "§g[  ]§! {name} §Y({count}条)§!"')
        tr_locs.append(f' auto_qol_tr.mod_{i}_on:0 "§G[✓]§! {name} §Y({count}条)§!"')

    new_addon = "\n" + "\n".join(tr_locs) + "\n"
    
    # Replace existing auto_qol_tr block if exists
    if "auto_qol_tr.gui_title" in loc_text:
        loc_text = re.sub(r'\n\s*auto_qol_tr\..*', '', loc_text)
    
    loc_text = loc_text.rstrip() + new_addon
    with open(loc_file, 'w', encoding='utf-8-sig') as f:
        f.write(loc_text)
    print("Updated localisation file!")

if __name__ == '__main__':
    main()

import re, sys
from pathlib import Path
from collections import defaultdict
sys.stdout.reconfigure(encoding='utf-8')

def extract_options(text):
    options = []
    idx = 0
    while True:
        m = re.search(r'\boption\s*=\s*\{', text[idx:])
        if not m:
            break
        start = idx + m.start()
        brace_start = text.find('{', start)
        brace_count = 1
        i = brace_start + 1
        while i < len(text) and brace_count > 0:
            if text[i] == '{':
                brace_count += 1
            elif text[i] == '}':
                brace_count -= 1
            i += 1
        if brace_count == 0:
            options.append(text[start:i].strip())
            idx = i
        else:
            break
    return options

from paths import LOCALISATION_DIR, EVENTS_DIR, MOD_ROOT

def build_system():
    # 1. Load localization file and extract tradition titles
    loc_path = LOCALISATION_DIR / 'auto_qol_l_simp_chinese.yml'
    loc_text = loc_path.read_text(encoding='utf-8-sig')

    nodes_info = {}
    for m in re.finditer(r'tr_node_o(?:n|ff)_(tr_[a-zA-Z0-9_-]+):0\s*"[^"]*?§!\s*(.*?)\s*\((tr_[a-zA-Z0-9_-]+)\)"', loc_text):
        node_id = m.group(1)
        title = m.group(2).strip()
        nodes_info[node_id] = title

    print(f"Loaded {len(nodes_info)} tradition titles from localization.")

    # 12 Lethal crash nodes (Blacklist)
    blacklist = {
        'tr_tt_ultralimit_adopt', 'tr_tt_ultralimit_1', 'tr_tt_ultralimit_2',
        'tr_tt_ultralimit_3', 'tr_tt_ultralimit_4', 'tr_tt_ultralimit_5', 'tr_tt_ultralimit_finish',
        'tr_adaptability_homura', 'tr_adaptability_kyoko', 'tr_adaptability_madoka',
        'tr_adaptability_mami', 'tr_adaptability_sayaka'
    }

    # 2. Build new localization lines for all 4 states of every node
    new_loc_lines = []
    
    # Header tooltips and buttons
    new_loc_lines.append(' # ===== 级联多选传统交互按钮与状态提示 =====')
    new_loc_lines.append(' tradition_all_select_all:0 "£trigger_yes£ §G【一键全选所有 Mod 全部安全传统】§!"')
    new_loc_lines.append(' tradition_all_select_all_tt:0 "§H一键全选§!\\n将当前检测到的所有 Mod 全部 501 个安全传统预选设为【准备激活】。\\n§G包含事前防御，自动跳过一切致命冲突传统。§!"')
    new_loc_lines.append(' tradition_all_clear_all:0 "£trigger_no£ §R【一键清空所有已勾选的传统】§!"')
    new_loc_lines.append(' tradition_all_clear_all_tt:0 "§H一键清空§!\\n取消所有 Mod 的预选，将所有传统重置为【未选择/跳过】状态。"')

    new_loc_lines.append(' tradition_mod_select_all:0 "£trigger_yes£ §G【全选此 Mod 全部安全传统】§!"')
    new_loc_lines.append(' tradition_mod_select_all_tt:0 "§H全选当前 Mod§!\\n将此 Mod 旗下的所有安全传统设为【准备激活】。"')
    new_loc_lines.append(' tradition_mod_clear_all:0 "£trigger_no£ §R【清空此 Mod 所有勾选】§!"')
    new_loc_lines.append(' tradition_mod_clear_all_tt:0 "§H清空当前 Mod§!\\n将此 Mod 旗下的所有传统设为【未选择/跳过】。"')

    new_loc_lines.append(' tradition_tree_select_all:0 "£trigger_yes£ §G【全选本树全部安全节点】§!"')
    new_loc_lines.append(' tradition_tree_select_all_tt:0 "§H全选本树§!\\n将本传统树所有安全节点设为【准备激活】。"')
    new_loc_lines.append(' tradition_tree_clear_all:0 "£trigger_no£ §R【清空本树所有勾选】§!"')
    new_loc_lines.append(' tradition_tree_clear_all_tt:0 "§H清空本树§!\\n将本传统树所有节点设为【未选择/跳过】。"')

    new_loc_lines.append(' tr_node_sel_on_tt:0 "§G[已勾选] 点击排除§!\\n当前状态：§G【准备激活】§!\\n点击将此节点设为【未选择/跳过】，批量激活时将不会激活该项。"')
    new_loc_lines.append(' tr_node_sel_off_tt:0 "§R[未勾选] 点击勾选§!\\n当前状态：§R【未选择/跳过】§!\\n点击将此节点设为【准备激活】，批量激活时将会激活该项。"')
    new_loc_lines.append(' tr_node_already_active_tt:0 "§H[已生效] 帝国已激活§!\\n当前状态：§H【帝国已生效】§!\\n该传统已经在帝国中生效运作，无需重复勾选。"')
    new_loc_lines.append(' tr_node_blocked_tt:0 "§R[安全保护] 强制跳过§!\\n当前状态：§R【安全强制跳过】§!\\n检测到该传统包含严重底层缺陷或时间溢出词条，助手已为您强制锁定跳过以确保游戏稳定。"')

    for nid, title in nodes_info.items():
        new_loc_lines.append(f' tr_node_sel_on_{nid}:0 "£trigger_yes£ §G【准备激活】§! {title} ({nid})"')
        new_loc_lines.append(f' tr_node_sel_off_{nid}:0 "£trigger_no£ §R【跳过/未选】§! {title} ({nid})"')
        new_loc_lines.append(f' tr_node_already_active_{nid}:0 "£trigger_yes£ §H【帝国已生效】§! {title} ({nid})"')
        new_loc_lines.append(f' tr_node_blocked_{nid}:0 "£trigger_no£ §R【安全强制跳过】§! {title} ({nid})"')

    # Replace / Append to localization
    # Strip any old tr_node_sel_... lines if already present
    loc_text_clean = re.sub(r'\s*tr_node_sel_[^\n]+', '', loc_text)
    loc_text_clean = re.sub(r'\s*tr_node_already_active_[^\n]+', '', loc_text_clean)
    loc_text_clean = re.sub(r'\s*tradition_all_select_all[^\n]+', '', loc_text_clean)
    loc_text_clean = re.sub(r'\s*tradition_all_clear_all[^\n]+', '', loc_text_clean)
    loc_text_clean = re.sub(r'\s*tradition_mod_select_all[^\n]+', '', loc_text_clean)
    loc_text_clean = re.sub(r'\s*tradition_mod_clear_all[^\n]+', '', loc_text_clean)
    loc_text_clean = re.sub(r'\s*tradition_tree_select_all[^\n]+', '', loc_text_clean)
    loc_text_clean = re.sub(r'\s*tradition_tree_clear_all[^\n]+', '', loc_text_clean)
    loc_text_clean = re.sub(r'\s*tr_node_sel_on_tt[^\n]+', '', loc_text_clean)
    loc_text_clean = re.sub(r'\s*tr_node_sel_off_tt[^\n]+', '', loc_text_clean)

    loc_path.write_text(loc_text_clean.rstrip() + "\n" + "\n".join(new_loc_lines) + "\n", encoding='utf-8-sig')
    print("Updated localization file with all 4 states!")

    # 3. Read events file from baseline git commit
    events_path = EVENTS_DIR / 'tradition_unlock_events.txt'
    try:
        import subprocess
        content = subprocess.check_output(['git', 'show', '06a8090:events/tradition_unlock_events.txt'], cwd=MOD_ROOT).decode('utf-8')
    except Exception:
        content = events_path.read_text(encoding='utf-8')

    # Parse trees
    tree_pattern = re.compile(r'((?:^|\n)country_event\s*=\s*\{\s*id\s*=\s*(tradition_cascade_tree\.\d+).*?)(?=\ncountry_event\s*=\s*\{|\Z)', re.DOTALL | re.MULTILINE)
    tree_nodes_map = {}

    def transform_tree(match):
        full_block = match.group(1).lstrip('\r\n')
        tree_id = match.group(2)

        # Extract all node IDs
        all_found_nodes = []
        for nm in re.finditer(r'(?:tr_sel_|tr_node_o(?:n|ff)_|tr_node_blocked_|tr_node_sel_o(?:n|ff)_|tr_node_already_active_)(tr_[a-zA-Z0-9_-]+)', full_block):
            n = nm.group(1)
            if n not in all_found_nodes:
                all_found_nodes.append(n)

        safe_nodes = [n for n in all_found_nodes if n not in blacklist]
        tree_nodes_map[tree_id] = safe_nodes

        first_opt_idx = full_block.find('option = {')
        if first_opt_idx == -1:
            return full_block

        header = full_block[:first_opt_idx].rstrip()

        back_match = re.search(r'name\s*=\s*"tradition_unlock_menu\.back".*?id\s*=\s*(tradition_cascade_mod\.\d+)', full_block, re.DOTALL)
        back_target = back_match.group(1) if back_match else "tradition_unlock_menu.1"

        new_opts = []

        # Batch buttons for tree
        if safe_nodes:
            set_all = "\n".join([f"\t\tset_country_flag = tr_sel_{sn}" for sn in safe_nodes])
            clr_all = "\n".join([f"\t\tremove_country_flag = tr_sel_{sn}" for sn in safe_nodes])
            new_opts.append(
                f"\t# 【全选本树全部安全节点】\n"
                f"\toption = {{\n"
                f'\t\tname = "tradition_tree_select_all"\n'
                f'\t\tcustom_tooltip = "tradition_tree_select_all_tt"\n'
                f"{set_all}\n"
                f"\t\tcountry_event = {{ id = {tree_id} }}\n"
                f"\t}}\n\n"
                f"\t# 【清空本树所有勾选】\n"
                f"\toption = {{\n"
                f'\t\tname = "tradition_tree_clear_all"\n'
                f'\t\tcustom_tooltip = "tradition_tree_clear_all_tt"\n'
                f"{clr_all}\n"
                f"\t\tcountry_event = {{ id = {tree_id} }}\n"
                f"\t}}"
            )

        # Individual nodes (4 states)
        for n in all_found_nodes:
            if n in blacklist:
                new_opts.append(
                    f"\t# 危险节点 (强制跳过)\n"
                    f"\toption = {{\n"
                    f'\t\tname = "tr_node_blocked_{n}"\n'
                    f'\t\tcustom_tooltip = "tr_node_blocked_tt"\n'
                    f"\t\tcountry_event = {{ id = {tree_id} }}\n"
                    f"\t}}"
                )
            else:
                new_opts.append(
                    f"\t# 节点 {n}: 帝国已生效\n"
                    f"\toption = {{\n"
                    f'\t\tname = "tr_node_already_active_{n}"\n'
                    f"\t\ttrigger = {{ has_tradition = {n} }}\n"
                    f'\t\tcustom_tooltip = "tr_node_already_active_tt"\n'
                    f"\t\tcountry_event = {{ id = {tree_id} }}\n"
                    f"\t}}\n"
                    f"\t# 节点 {n}: 准备激活 (已勾选，点击取消)\n"
                    f"\toption = {{\n"
                    f'\t\tname = "tr_node_sel_on_{n}"\n'
                    f"\t\ttrigger = {{\n"
                    f"\t\t\tNOT = {{ has_tradition = {n} }}\n"
                    f"\t\t\thas_country_flag = tr_sel_{n}\n"
                    f"\t\t}}\n"
                    f'\t\tcustom_tooltip = "tr_node_sel_on_tt"\n'
                    f"\t\tremove_country_flag = tr_sel_{n}\n"
                    f"\t\tcountry_event = {{ id = {tree_id} }}\n"
                    f"\t}}\n"
                    f"\t# 节点 {n}: 未选择/跳过 (未勾选，点击勾选)\n"
                    f"\toption = {{\n"
                    f'\t\tname = "tr_node_sel_off_{n}"\n'
                    f"\t\ttrigger = {{\n"
                    f"\t\t\tNOT = {{ has_tradition = {n} }}\n"
                    f"\t\t\tNOT = {{ has_country_flag = tr_sel_{n} }}\n"
                    f"\t\t}}\n"
                    f'\t\tcustom_tooltip = "tr_node_sel_off_tt"\n'
                    f"\t\tset_country_flag = tr_sel_{n}\n"
                    f"\t\tcountry_event = {{ id = {tree_id} }}\n"
                    f"\t}}"
                )

        new_opts.append(
            f"\t# 返回上级菜单\n"
            f"\toption = {{\n"
            f'\t\tname = "tradition_unlock_menu.back"\n'
            f"\t\tcountry_event = {{ id = {back_target} }}\n"
            f"\t}}"
        )

        prefix = "\n" if match.group(1).startswith("\n") else ""
        return prefix + header + "\n\n" + "\n\n".join(new_opts) + "\n}"

    content = tree_pattern.sub(transform_tree, content)
    print(f"Transformed {len(tree_nodes_map)} tree events.")

    # 4. Transform mod events: tradition_cascade_mod.X
    mod_pattern = re.compile(r'((?:^|\n)country_event\s*=\s*\{\s*id\s*=\s*(tradition_cascade_mod\.\d+).*?)(?=\ncountry_event\s*=\s*\{|\Z)', re.DOTALL | re.MULTILINE)

    def transform_mod(match):
        full_block = match.group(1).lstrip('\r\n')
        mod_id = match.group(2)

        called_trees = re.findall(r'id\s*=\s*(tradition_cascade_tree\.\d+)', full_block)
        mod_nodes = []
        for t in called_trees:
            for n in tree_nodes_map.get(t, []):
                if n not in mod_nodes and n not in blacklist:
                    mod_nodes.append(n)

        first_opt_idx = full_block.find('option = {')
        if first_opt_idx == -1:
            return match.group(0)

        header = full_block[:first_opt_idx].rstrip()

        # Extract only tree navigation buttons and back button
        clean_opts = []
        for opt_str in extract_options(full_block):
            if 'tradition_mod_unlock_all' not in opt_str and 'tradition_mod_select_all' not in opt_str and 'tradition_mod_clear_all' not in opt_str:
                clean_opts.append(f"\t{opt_str}")

        top_opts = []
        if mod_nodes:
            set_mod = "\n".join([f"\t\tset_country_flag = tr_sel_{mn}" for mn in mod_nodes])
            clr_mod = "\n".join([f"\t\tremove_country_flag = tr_sel_{mn}" for mn in mod_nodes])
            top_opts.append(
                f"\t# 【一键勾选此 Mod 全部安全传统】\n"
                f"\toption = {{\n"
                f'\t\tname = "tradition_mod_select_all"\n'
                f'\t\tcustom_tooltip = "tradition_mod_select_all_tt"\n'
                f"{set_mod}\n"
                f"\t\tcountry_event = {{ id = {mod_id} }}\n"
                f"\t}}\n\n"
                f"\t# 【清空此 Mod 所有勾选】\n"
                f"\toption = {{\n"
                f'\t\tname = "tradition_mod_clear_all"\n'
                f'\t\tcustom_tooltip = "tradition_mod_clear_all_tt"\n'
                f"{clr_mod}\n"
                f"\t\tcountry_event = {{ id = {mod_id} }}\n"
                f"\t}}"
            )

        prefix = "\n" if match.group(1).startswith("\n") else ""
        return prefix + header + "\n\n" + "\n\n".join(top_opts + clean_opts) + "\n}"

    content = mod_pattern.sub(transform_mod, content)
    print("Transformed mod events.")

    # 5. Transform tradition_unlock_menu.1 (Main Menu)
    # Collect all 501 safe nodes
    all_safe_nodes = sorted(list({n for nodes in tree_nodes_map.values() for n in nodes if n not in blacklist}))
    print(f"Total safe nodes across all mods: {len(all_safe_nodes)}")

    menu_match = re.search(r'((?:^|\n)country_event\s*=\s*\{\s*id\s*=\s*tradition_unlock_menu\.1\b.*?)(?=\ncountry_event\s*=\s*\{|\Z)', content, re.DOTALL | re.MULTILINE)
    if menu_match:
        menu_block = menu_match.group(1).lstrip('\r\n')
        
        # In menu header: immediate block should NOT select anything (DEFAULT NOT SELECTED!)
        clean_header = (
            "country_event = {\n"
            "\tid = tradition_unlock_menu.1\n"
            '\ttitle = "tradition_unlock_menu.1.name"\n'
            '\tdesc = "tradition_unlock_menu.1.desc"\n'
            "\tpicture = GFX_evt_giga_menu\n"
            "\tis_triggered_only = yes\n"
        )

        # Explicitly build all 11 Mod navigation options and back button
        clean_opts = []
        for i in range(1, 12):
            clean_opts.append(
                f"\toption = {{\n"
                f'\t\tname = "tradition_mod_btn_{i}"\n'
                f"\t\tcountry_event = {{ id = tradition_cascade_mod.{i} }}\n"
                f"\t}}"
            )
        clean_opts.append(
            f"\toption = {{\n"
            f'\t\tname = "tradition_unlock_menu.back"\n'
            f"\t\tcountry_event = {{ id = auto_qol_menu.1 }}\n"
            f"\t}}"
        )

        set_all_safe = "\n".join([f"\t\tset_country_flag = tr_sel_{sn}" for sn in all_safe_nodes])
        clr_all_safe = "\n".join([f"\t\tremove_country_flag = tr_sel_{sn}" for sn in all_safe_nodes])

        main_opts = [
            # 1. Execute
            f"\t# 【执行激活所有已勾选的传统】\n"
            f"\toption = {{\n"
            f'\t\tname = "tradition_unlock_menu.exec_selected"\n'
            f'\t\tcustom_tooltip = "tradition_unlock_menu.exec_selected_tt"\n'
            f"\t\tcountry_event = {{ id = tradition_unlock.exec_selected }}\n"
            f"\t\tcountry_event = {{ id = tradition_unlock_menu.1 }}\n"
            f"\t}}",

            # 2. Select All
            f"\t# 【一键勾选所有 Mod 全部安全传统】\n"
            f"\toption = {{\n"
            f'\t\tname = "tradition_all_select_all"\n'
            f'\t\tcustom_tooltip = "tradition_all_select_all_tt"\n'
            f"{set_all_safe}\n"
            f"\t\tcountry_event = {{ id = tradition_unlock_menu.1 }}\n"
            f"\t}}",

            # 3. Clear All
            f"\t# 【一键清空所有勾选】\n"
            f"\toption = {{\n"
            f'\t\tname = "tradition_all_clear_all"\n'
            f'\t\tcustom_tooltip = "tradition_all_clear_all_tt"\n'
            f"{clr_all_safe}\n"
            f"\t\tcountry_event = {{ id = tradition_unlock_menu.1 }}\n"
            f"\t}}"
        ]

        new_menu = "\n" + clean_header + "\n" + "\n\n".join(main_opts + clean_opts) + "\n}"
        content = content[:menu_match.start()] + new_menu + content[menu_match.end():]

    # 6. Rebuild tradition_unlock.exec_selected at the end of file
    exec_acts = []
    for n in all_safe_nodes:
        exec_acts.append(
            f"\t\tif = {{\n"
            f"\t\t\tlimit = {{\n"
            f"\t\t\t\thas_country_flag = tr_sel_{n}\n"
            f"\t\t\t\tNOT = {{ has_tradition = {n} }}\n"
            f"\t\t\t}}\n"
            f"\t\t\tactivate_tradition = {n}\n"
            f"\t\t\tremove_country_flag = tr_sel_{n}\n"
            f"\t\t}}"
        )

    exec_block = (
        "\ncountry_event = {\n"
        "\tid = tradition_unlock.exec_selected\n"
        "\thide_window = yes\n"
        "\tis_triggered_only = yes\n\n"
        "\timmediate = {\n"
        '\t\tlog = "[AUTO_QOL_TRADITION][BATCH_EXEC] Batch activated user-selected traditions for [Root.GetName]."\n'
        + "\n".join(exec_acts)
        + "\n\t}\n}\n"
    )

    exec_pattern = re.compile(r'((?:^|\n)country_event\s*=\s*\{\s*id\s*=\s*tradition_unlock\.exec_selected\b.*?)(?=\ncountry_event\s*=\s*\{|\Z)', re.DOTALL | re.MULTILINE)
    content = exec_pattern.sub(exec_block, content)
    events_path.write_text(content, encoding='utf-8')
    print("Successfully built complete fine-grained checkbox system!")

if __name__ == '__main__':
    build_system()

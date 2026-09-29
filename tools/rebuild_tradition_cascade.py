import re, sys
from pathlib import Path
from collections import defaultdict
from paths import EVENTS_DIR
sys.stdout.reconfigure(encoding='utf-8')

def rebuild():
    file_path = EVENTS_DIR / 'tradition_unlock_events.txt'
    content = file_path.read_text(encoding='utf-8')

    # Blacklist dangerous crash traditions:
    # 1. tr_tt_ultralimit causes pop political power = -10000 -> F2 INT_DIVIDE_BY_ZERO
    # 2. tr_adaptability_homura/kyoko/mami/madoka/sayaka causes building/shipyard build time mult = -5 to -10 -> progress bar INT_DIVIDE_BY_ZERO
    blacklist = {
        'tr_tt_ultralimit_adopt', 'tr_tt_ultralimit_1', 'tr_tt_ultralimit_2',
        'tr_tt_ultralimit_3', 'tr_tt_ultralimit_4', 'tr_tt_ultralimit_5', 'tr_tt_ultralimit_finish',
        'tr_adaptability_homura', 'tr_adaptability_kyoko', 'tr_adaptability_madoka',
        'tr_adaptability_mami', 'tr_adaptability_sayaka'
    }

    # 1. Transform tree events: tradition_cascade_tree.X
    tree_pattern = re.compile(r'(country_event\s*=\s*\{\s*id\s*=\s*(tradition_cascade_tree\.\d+).*?)(?=\ncountry_event\s*=\s*\{|\Z)', re.DOTALL)
    
    tree_nodes_map = {}

    def transform_tree(match):
        full_block = match.group(1)
        tree_id = match.group(2)

        # Extract all original node IDs from tr_sel_... or tr_node_on/off_...
        all_found_nodes = []
        for nm in re.finditer(r'(?:tr_sel_|tr_node_o(?:n|ff)_|tr_node_blocked_)(tr_[a-zA-Z0-9_-]+)', full_block):
            n = nm.group(1)
            if n not in all_found_nodes:
                all_found_nodes.append(n)

        safe_nodes = [n for n in all_found_nodes if n not in blacklist]
        tree_nodes_map[tree_id] = safe_nodes

        first_opt_idx = full_block.find('option = {')
        if first_opt_idx == -1:
            return full_block

        header = full_block[:first_opt_idx].rstrip()

        # Extract back target
        back_match = re.search(r'name\s*=\s*"tradition_unlock_menu\.back".*?id\s*=\s*(tradition_cascade_mod\.\d+)', full_block, re.DOTALL)
        back_target = back_match.group(1) if back_match else "tradition_unlock_menu.1"

        new_opts = []

        # Option 1: One-click unlock this whole tree (if safe nodes exist)
        has_blocked = any(n in blacklist for n in all_found_nodes)
        if safe_nodes:
            act_all_lines = "\n".join([f"\t\tactivate_tradition = {sn}" for sn in safe_nodes])
            safety_call = "\t\tcountry_event = { id = auto_qol_safety.1 }\n" if has_blocked else ""
            tree_unlock_block = (
                f"\t# 一键激活本树全部安全传统\n"
                f"\toption = {{\n"
                f'\t\tname = "tradition_tree_unlock_all"\n'
                f'\t\tcustom_tooltip = "tradition_tree_unlock_all_tt"\n'
                f'\t\tlog = "[AUTO_QOL_TRADITION][TREE_UNLOCK] Batch activated {len(safe_nodes)} traditions in tree {tree_id} for [Root.GetName]."\n'
                f"{act_all_lines}\n"
                f"{safety_call}"
                f"\t\tcountry_event = {{ id = {tree_id} }}\n"
                f"\t}}"
            )
            new_opts.append(tree_unlock_block)

        # Option 2: Individual nodes with live has_tradition check OR blacklist intercept
        for n in all_found_nodes:
            if n in blacklist:
                node_block = (
                    f"\t# 危险传统节点 (事前防御拦截)\n"
                    f"\toption = {{\n"
                    f'\t\tname = "tr_node_blocked_{n}"\n'
                    f'\t\tcustom_tooltip = "tr_node_blocked_tt"\n'
                    f'\t\tlog = "[AUTO_QOL_DEFENSE][MANUAL_BLOCKED] Attempted activation of dangerous tradition {n} in [Root.GetName] was INTERCEPTED."\n'
                    f"\t\tcountry_event = {{ id = auto_qol_safety.1 }}\n"
                    f"\t}}"
                )
            else:
                node_block = (
                    f"\t# 节点: {n}\n"
                    f"\toption = {{\n"
                    f'\t\tname = "tr_node_on_{n}"\n'
                    f"\t\ttrigger = {{ has_tradition = {n} }}\n"
                    f'\t\tcustom_tooltip = "tr_node_already_active_tt"\n'
                    f"\t}}\n"
                    f"\toption = {{\n"
                    f'\t\tname = "tr_node_off_{n}"\n'
                    f"\t\ttrigger = {{ NOT = {{ has_tradition = {n} }} }}\n"
                    f'\t\tlog = "[AUTO_QOL_TRADITION][ACTIVATE] Activated safe tradition {n} for [Root.GetName]."\n'
                    f"\t\tactivate_tradition = {n}\n"
                    f"\t\tcountry_event = {{ id = {tree_id} }}\n"
                    f"\t}}"
                )
            new_opts.append(node_block)

        # Back option
        new_opts.append(
            f"\t# 返回上级菜单\n"
            f"\toption = {{\n"
            f'\t\tname = "tradition_unlock_menu.back"\n'
            f"\t\tcountry_event = {{ id = {back_target} }}\n"
            f"\t}}"
        )

        return header + "\n\n" + "\n\n".join(new_opts) + "\n}"

    content = tree_pattern.sub(transform_tree, content)
    print(f"Transformed {len(tree_nodes_map)} tree events.")

    # 2. Transform mod events: tradition_cascade_mod.X
    mod_pattern = re.compile(r'(country_event\s*=\s*\{\s*id\s*=\s*(tradition_cascade_mod\.\d+).*?)(?=\ncountry_event\s*=\s*\{|\Z)', re.DOTALL)
    
    mod_nodes_map = defaultdict(list)

    def transform_mod(match):
        full_block = match.group(1)
        mod_id = match.group(2)

        # Find all trees referenced
        called_trees = re.findall(r'id\s*=\s*(tradition_cascade_tree\.\d+)', full_block)
        mod_nodes = []
        has_blocked = False
        for t in called_trees:
            for n in tree_nodes_map.get(t, []):
                if n not in mod_nodes and n not in blacklist:
                    mod_nodes.append(n)
            if 'tradition_cascade_tree.31' in t or 'tradition_cascade_tree.44' in t: # blocked trees
                has_blocked = True

        mod_nodes_map[mod_id] = mod_nodes

        first_opt_idx = full_block.find('option = {')
        if first_opt_idx == -1:
            return full_block

        header = full_block[:first_opt_idx].rstrip()
        
        # Extract existing tree buttons and back button from full_block
        # We strip any previous tradition_mod_unlock_all to avoid duplication
        clean_opts = []
        for opt_match in re.finditer(r'option\s*=\s*\{[^{}]*\}', full_block):
            opt_str = opt_match.group(0)
            if 'tradition_mod_unlock_all' not in opt_str:
                clean_opts.append(f"\t{opt_str}")

        # Add "Unlock all in mod" button as first option
        top_opts = []
        if mod_nodes:
            act_lines = "\n".join([f"\t\tactivate_tradition = {n}" for n in mod_nodes])
            log_mod = f'\t\tlog = "[AUTO_QOL_TRADITION][MOD_UNLOCK] Batch activated {len(mod_nodes)} safe traditions for mod {mod_id} in [Root.GetName]."\n'
            safety_call = "\t\tcountry_event = { id = auto_qol_safety.1 }\n" if has_blocked else ""
            top_opt = (
                f"\t# 一键激活此 Mod 拥有的全部安全传统\n"
                f"\toption = {{\n"
                f'\t\tname = "tradition_mod_unlock_all"\n'
                f'\t\tcustom_tooltip = "tradition_mod_unlock_all_tt"\n'
                f"{log_mod}"
                f"{act_lines}\n"
                f"{safety_call}"
                f"\t\tcountry_event = {{ id = {mod_id} }}\n"
                f"\t}}"
            )
            top_opts.append(top_opt)

        return header + "\n\n" + "\n\n".join(top_opts + clean_opts) + "\n}"

    content = mod_pattern.sub(transform_mod, content)
    print("Transformed mod events with one-click buttons.")

    # 3. In tradition_unlock_menu.1, add "Unlock all mods" at top of options (idempotently)
    menu_match = re.search(r'(country_event\s*=\s*\{\s*id\s*=\s*tradition_unlock_menu\.1.*?)(?=\ncountry_event\s*=\s*\{|\Z)', content, re.DOTALL)
    if menu_match:
        menu_block = menu_match.group(1)
        first_opt_idx = menu_block.find('option = {')
        header = menu_block[:first_opt_idx].rstrip()
        
        clean_opts = []
        for opt_match in re.finditer(r'option\s*=\s*\{[^{}]*\}', menu_block):
            opt_str = opt_match.group(0)
            if 'tradition_all_unlock_all' not in opt_str:
                clean_opts.append(f"\t{opt_str}")

        top_opt = (
            f"\t# 一键激活当前已安装 Mod 全部安全传统 (事前防御保护)\n"
            f"\toption = {{\n"
            f'\t\tname = "tradition_all_unlock_all"\n'
            f'\t\tcustom_tooltip = "tradition_all_unlock_all_tt"\n'
            f'\t\tlog = "[AUTO_QOL_DEFENSE][PRE_FLIGHT] Global 1-click batch activation initiated for [Root.GetName]. Skipping dangerous traditions."\n'
            f"\t\tcountry_event = {{ id = tradition_unlock.exec_selected }}\n"
            f"\t\tcountry_event = {{ id = auto_qol_safety.1 }}\n"
            f"\t\tcountry_event = {{ id = tradition_unlock_menu.1 }}\n"
            f"\t}}"
        )

        new_menu_block = header + "\n\n" + "\n\n".join([top_opt] + clean_opts) + "\n}"
        content = content[:menu_match.start()] + new_menu_block + content[menu_match.end():]

    # 4. In tradition_unlock.exec_selected (at end of file), activate all safe traditions
    all_safe_nodes = set()
    for nodes in tree_nodes_map.values():
        all_safe_nodes.update(nodes)

    exec_block = (
        "\ncountry_event = {\n"
        "\tid = tradition_unlock.exec_selected\n"
        "\thide_window = yes\n"
        "\tis_triggered_only = yes\n\n"
        "\timmediate = {\n"
        '\t\tlog = "[AUTO_QOL_DEFENSE][PRE_FLIGHT] Batch activated safe traditions for [Root.GetName]. Lethal nodes (tr_tt_ultralimit and madoka adjustments) bypassed."\n'
        + "\n".join([f"\t\tactivate_tradition = {n}" for n in sorted(all_safe_nodes)])
        + "\n\t}\n}\n"
    )
    # Replace the existing tradition_unlock.exec_selected at the end of the file
    content = re.sub(r'\ncountry_event\s*=\s*\{\s*\n\s*id\s*=\s*tradition_unlock\.exec_selected.*', exec_block, content, flags=re.DOTALL)

    # Clean up clr_country_flag -> remove_country_flag
    content = content.replace('clr_country_flag', 'remove_country_flag')

    file_path.write_text(content, encoding='utf-8')
    print(f"Successfully rebuilt tradition events! Total safe traditions: {len(all_safe_nodes)}")

if __name__ == '__main__':
    rebuild()

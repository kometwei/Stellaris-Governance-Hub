import re, os

from paths import EVENTS_DIR

def upgrade_traditions():
    file_path = EVENTS_DIR / 'tradition_unlock_events.txt'
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Parse all trees and their nodes
    tree_pattern = re.compile(r'(country_event\s*=\s*\{\s*id\s*=\s*(tradition_cascade_tree\.\d+).*?)(?=\ncountry_event\s*=\s*\{|\Z)', re.DOTALL)
    
    tree_to_nodes = {}
    
    def repl_tree(match):
        full_block = match.group(1)
        tree_id = match.group(2)
        
        # Find all nodes in this tree
        # Look for tr_sel_(tr_\w+)
        nodes = []
        for m in re.finditer(r'tr_sel_(tr_[a-zA-Z0-9_-]+)', full_block):
            node_id = m.group(1)
            if node_id not in nodes:
                nodes.append(node_id)
                
        tree_to_nodes[tree_id] = nodes
        
        # Rebuild options for this tree
        # Header part up to first option
        first_opt_idx = full_block.find('option = {')
        if first_opt_idx == -1:
            return full_block
            
        header = full_block[:first_opt_idx].rstrip()
        
        # New options
        new_opts = []
        
        # 1. Unlock all in tree
        if nodes:
            unlock_tree_lines = [f"\t\tactivate_tradition = {n}" for n in nodes]
            unlock_tree_str = "\n".join(unlock_tree_lines)
            new_opts.append(
                f"\t# ⚡ 一键激活本树全部传统\n"
                f"\toption = {{\n"
                f'\t\tname = "tradition_tree_unlock_all"\n'
                f'\t\tcustom_tooltip = "tradition_tree_unlock_all_tt"\n'
                f"{unlock_tree_str}\n"
                f"\t\tcountry_event = {{ id = {tree_id} }}\n"
                f"\t}}"
            )
            
        # 2. Individual node options with real has_tradition check
        for n in nodes:
            opt_block = (
                f"\toption = {{\n"
                f'\t\tname = "tr_node_on_{n}"\n'
                f"\t\ttrigger = {{ has_tradition = {n} }}\n"
                f"\t}}\n"
                f"\toption = {{\n"
                f'\t\tname = "tr_node_off_{n}"\n'
                f"\t\ttrigger = {{ NOT = {{ has_tradition = {n} }} }}\n"
                f"\t\tactivate_tradition = {n}\n"
                f"\t\tcountry_event = {{ id = {tree_id} }}\n"
                f"\t}}"
            )
            new_opts.append(opt_block)
            
        # 3. Back option
        # Check where the back option pointed
        back_match = re.search(r'name\s*=\s*"tradition_unlock_menu\.back".*?country_event\s*=\s*\{\s*id\s*=\s*(\w+\.\d+)\s*\}', full_block, re.DOTALL)
        back_target = back_match.group(1) if back_match else "tradition_unlock_menu.1"
        new_opts.append(
            f"\toption = {{\n"
            f'\t\tname = "tradition_unlock_menu.back"\n'
            f"\t\tcountry_event = {{ id = {back_target} }}\n"
            f"\t}}"
        )
        
        return header + "\n\n" + "\n\n".join(new_opts) + "\n}"

    content = tree_pattern.sub(repl_tree, content)
    
    # Now parse mod events (tradition_cascade_mod.X) and add "Unlock all in mod"
    mod_pattern = re.compile(r'(country_event\s*=\s*\{\s*id\s*=\s*(tradition_cascade_mod\.\d+).*?)(?=\ncountry_event\s*=\s*\{|\Z)', re.DOTALL)
    
    def repl_mod(match):
        full_block = match.group(1)
        mod_id = match.group(2)
        
        # Find all trees called from this mod
        called_trees = re.findall(r'id\s*=\s*(tradition_cascade_tree\.\d+)', full_block)
        mod_nodes = []
        for t in called_trees:
            for n in tree_to_nodes.get(t, []):
                if n not in mod_nodes:
                    mod_nodes.append(n)
                    
        first_opt_idx = full_block.find('option = {')
        if first_opt_idx == -1:
            return full_block
            
        header = full_block[:first_opt_idx].rstrip()
        rest = full_block[first_opt_idx:]
        
        if mod_nodes:
            unlock_mod_lines = [f"\t\tactivate_tradition = {n}" for n in mod_nodes]
            unlock_mod_str = "\n".join(unlock_mod_lines)
            top_opt = (
                f"\t# ⚡ 一键激活此 Mod 拥有的所有传统\n"
                f"\toption = {{\n"
                f'\t\tname = "tradition_mod_unlock_all"\n'
                f'\t\tcustom_tooltip = "tradition_mod_unlock_all_tt"\n'
                f"{unlock_mod_str}\n"
                f"\t\tcountry_event = {{ id = {mod_id} }}\n"
                f"\t}}\n\n"
            )
            return header + "\n\n" + top_opt + rest
        return full_block

    content = mod_pattern.sub(repl_mod, content)
    
    # Also clean up tradition_unlock_menu.1 immediate flags (no longer needed)
    # and add a top "Unlock all mods" button
    menu_match = re.search(r'(country_event\s*=\s*\{\s*id\s*=\s*tradition_unlock_menu\.1.*?\bis_triggered_only\s*=\s*yes\s*\n)(.*?)(\t# Mod:|\toption\s*=\s*\{)', content, re.DOTALL)
    if menu_match:
        top_part = menu_match.group(1)
        rest_part = menu_match.group(3)
        top_btn = (
            "\t# ⚡ 一键激活当前已安装 Mod 全部传统\n"
            "\toption = {\n"
            '\t\tname = "tradition_all_unlock_all"\n'
            '\t\tcustom_tooltip = "tradition_all_unlock_all_tt"\n'
            "\t\tcountry_event = { id = tradition_unlock.exec_selected }\n"
            "\t\tcountry_event = { id = tradition_unlock_menu.1 }\n"
            "\t}\n\n"
        )
        content = content[:menu_match.start()] + top_part + "\n" + top_btn + rest_part + content[menu_match.end():]

    # In tradition_unlock.exec_selected, make it directly activate all traditions unconditionally
    all_known_nodes = set()
    for nodes in tree_to_nodes.values():
        all_known_nodes.update(nodes)
        
    exec_block = (
        "country_event = {\n"
        "\tid = tradition_unlock.exec_selected\n"
        "\thide_window = yes\n"
        "\tis_triggered_only = yes\n\n"
        "\timmediate = {\n"
        + "\n".join([f"\t\tactivate_tradition = {n}" for n in sorted(all_known_nodes)])
        + "\n\t}\n}"
    )
    content = re.sub(r'country_event\s*=\s*\{\s*id\s*=\s*tradition_unlock\.exec_selected.*?\}', exec_block, content, flags=re.DOTALL)

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
        
    print(f"Successfully upgraded traditions! Total trees: {len(tree_to_nodes)}, Total nodes: {len(all_known_nodes)}")

if __name__ == '__main__':
    upgrade_traditions()

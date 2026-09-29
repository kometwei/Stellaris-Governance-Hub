import glob, re, os
from pathlib import Path
from paths import GAME_INSTALL_DIR, WORKSHOP_MOD_DIR, EVENTS_DIR

def build_council_system():
    files = []
    files.extend(glob.glob(str(GAME_INSTALL_DIR / "common" / "governments" / "councilors" / "*.txt")))
    files.extend(glob.glob(str(WORKSHOP_MOD_DIR / "**" / "common" / "governments" / "councilors" / "*.txt"), recursive=True))

    councilors = {}

    for f in files:
        try:
            with open(f, 'r', encoding='utf-8', errors='ignore') as fp:
                text = fp.read()
        except Exception:
            continue
        
        lines = [line.split('#')[0] for line in text.splitlines()]
        clean = '\n'.join(lines)

        for m in re.finditer(r'(\bcouncilor_\w+)\s*=\s*\{', clean):
            c_name = m.group(1)
            start_pos = m.end()
            depth = 1
            pos = start_pos
            while pos < len(clean) and depth > 0:
                if clean[pos] == '{':
                    depth += 1
                elif clean[pos] == '}':
                    depth -= 1
                pos += 1
            body = clean[start_pos:pos-1]

            if 'ruler' in c_name or c_name == 'councilor_name_key':
                continue

            civic = None
            cm = re.search(r'\bcivic\s*=\s*(\w+)', body)
            if cm:
                civic = cm.group(1)
            if not civic:
                hvc = re.search(r'has_valid_civic\s*=\s*(\w+)', body)
                if hvc:
                    civic = hvc.group(1)

            origin = None
            om = re.search(r'\borigin\s*=\s*(\w+)', body)
            if om:
                origin = om.group(1)
            if not origin:
                hvo = re.search(r'has_origin\s*=\s*(\w+)', body)
                if hvo:
                    origin = hvo.group(1)

            if c_name in ['councilor_research', 'councilor_defense', 'councilor_state']:
                councilors[c_name] = {
                    'name': c_name,
                    'type': 'core',
                    'cond': 'is_gestalt = no'
                }
            elif civic:
                if c_name not in councilors:
                    councilors[c_name] = {
                        'name': c_name,
                        'type': 'civic',
                        'cond': f'has_valid_civic = {civic}'
                    }
            elif origin:
                if c_name not in councilors:
                    councilors[c_name] = {
                        'name': c_name,
                        'type': 'origin',
                        'cond': f'has_origin = {origin}'
                    }

    # Ensure core 3 are first
    ordered_councilors = []
    for core_name in ['councilor_research', 'councilor_defense', 'councilor_state']:
        if core_name in councilors:
            ordered_councilors.append(councilors[core_name])

    for k, v in sorted(councilors.items()):
        if v['type'] != 'core':
            ordered_councilors.append(v)

    # Assign event IDs (1 to N)
    for idx, c in enumerate(ordered_councilors, start=1):
        c['idx'] = idx

    print(f"Total processed councilors: {len(ordered_councilors)}")

    out_file = str(EVENTS_DIR / 'auto_qol_council_events.txt')
    with open(out_file, 'w', encoding='utf-8') as ev:
        ev.write("namespace = auto_qol_council_menu\n")
        ev.write("namespace = auto_qol_council_pick\n")
        ev.write("namespace = auto_qol_council_pool\n\n")

        # ======================================================================
        # 1. 主内阁助手菜单 (智能仅展示当前帝国拥有的席位，告别 36 个 Mod 列表)
        # ======================================================================
        ev.write("# ========================================================\n")
        ev.write("# 帝国政务内阁辅助助手主界面 (智能感知当前帝国席位)\n")
        ev.write("# ========================================================\n")
        ev.write("country_event = {\n")
        ev.write("\tid = auto_qol_council_menu.1\n")
        ev.write('\ttitle = "auto_qol_council_menu.1.name"\n')
        ev.write('\tdesc = "auto_qol_council_menu.1.desc"\n')
        ev.write("\tpicture = GFX_evt_council\n")
        ev.write("\tis_triggered_only = yes\n\n")

        # 顶部工具
        ev.write("\t# 1. 一键解锁全部内阁槽位\n")
        ev.write("\toption = {\n")
        ev.write('\t\tname = "auto_qol_council_menu.unlock_all_slots"\n')
        ev.write('\t\tcustom_tooltip = "auto_qol_council_menu.unlock_all_slots_tt"\n')
        ev.write("\t\tunlock_council_slots = 1\n")
        ev.write("\t\tunlock_council_slots = 1\n")
        ev.write("\t\tunlock_council_slots = 1\n")
        ev.write("\t\thidden_effect = {\n")
        ev.write("\t\t\tcountry_event = { id = auto_qol_council_menu.1 }\n")
        ev.write("\t\t}\n")
        ev.write("\t}\n\n")

        # 核心三大席位
        for c in ordered_councilors:
            if c['type'] == 'core':
                ev.write(f"\t# 核心席位: {c['name']}\n")
                ev.write("\toption = {\n")
                ev.write(f'\t\tname = "{c["name"]}"\n')
                ev.write(f"\t\ttrigger = {{ {c['cond']} }}\n")
                ev.write(f"\t\tset_council_position_to_council = {c['name']}\n")
                ev.write(f"\t\thidden_effect = {{\n")
                ev.write(f"\t\t\tcountry_event = {{ id = auto_qol_council_pick.{c['idx']} }}\n")
                ev.write("\t\t}\n")
                ev.write("\t}\n\n")

        # 国策与起源专属席位 (严格限定当前帝国拥有此国策/起源)
        for c in ordered_councilors:
            if c['type'] != 'core':
                ev.write(f"\t# 专属席位: {c['name']}\n")
                ev.write("\toption = {\n")
                ev.write(f'\t\tname = "{c["name"]}"\n')
                ev.write(f"\t\ttrigger = {{ {c['cond']} }}\n")
                ev.write(f"\t\tset_council_position_to_council = {c['name']}\n")
                ev.write(f"\t\thidden_effect = {{\n")
                ev.write(f"\t\t\tcountry_event = {{ id = auto_qol_council_pick.{c['idx']} }}\n")
                ev.write("\t\t}\n")
                ev.write("\t}\n\n")

        # 底部功能与联动
        ev.write("\t# 启用内阁领袖专注协议\n")
        ev.write("\toption = {\n")
        ev.write('\t\tname = "auto_qol_council_menu.buff_council"\n')
        ev.write('\t\tcustom_tooltip = "auto_qol_council_menu.buff_council_tt"\n')
        ev.write("\t\tadd_modifier = {\n")
        ev.write("\t\t\tmodifier = auto_qol_council_buff\n")
        ev.write("\t\t\tdays = -1\n")
        ev.write("\t\t}\n")
        ev.write("\t\thidden_effect = {\n")
        ev.write("\t\t\tcountry_event = { id = auto_qol_council_menu.1 }\n")
        ev.write("\t\t}\n")
        ev.write("\t}\n\n")

        # 待选领袖招募池精简与大扫除
        ev.write("\t# 待选领袖招募池精简与大扫除\n")
        ev.write("\toption = {\n")
        ev.write('\t\tname = "auto_qol_council_menu.pool_mgr"\n')
        ev.write('\t\tcustom_tooltip = "auto_qol_council_menu.pool_mgr_tt"\n')
        ev.write("\t\thidden_effect = {\n")
        ev.write("\t\t\tcountry_event = { id = auto_qol_council_pool.1 }\n")
        ev.write("\t\t}\n")
        ev.write("\t}\n\n")

        ev.write("\t# 联动《更多内阁》领袖指派系统\n")
        ev.write("\toption = {\n")
        ev.write('\t\tname = "auto_qol_council_menu.open_more_council_assign"\n')
        ev.write('\t\tcustom_tooltip = "auto_qol_council_menu.open_more_council_assign_tt"\n')
        ev.write("\t\thidden_effect = {\n")
        ev.write("\t\t\tcountry_event = { id = b001_event_council_position.5000 }\n")
        ev.write("\t\t}\n")
        ev.write("\t}\n\n")

        ev.write("\t# 返回助手主控制台\n")
        ev.write("\toption = {\n")
        ev.write('\t\tname = "auto_qol_council_menu.back"\n')
        ev.write("\t\tcountry_event = { id = auto_qol_menu.1 }\n")
        ev.write("\t}\n")
        ev.write("}\n\n")

        # ======================================================================
        # 1.5 待选领袖池治理中枢 (一键清理闲散领袖 + 负向压制 Mod 恶性膨胀)
        # ======================================================================
        ev.write("# ========================================================\n")
        ev.write("# 待选领袖池治理中枢 (彻底解决多 Mod 待选池人满为患卡顿)\n")
        ev.write("# ========================================================\n")
        ev.write("country_event = {\n")
        ev.write("\tid = auto_qol_council_pool.1\n")
        ev.write('\ttitle = "auto_qol_council_pool.1.name"\n')
        ev.write('\tdesc = "auto_qol_council_pool.1.desc"\n')
        ev.write("\tpicture = GFX_evt_leader_recruitment\n")
        ev.write("\tis_triggered_only = yes\n\n")

        # 一键清退当前全部待选闲人并立即刷新
        ev.write("\toption = {\n")
        ev.write('\t\tname = "auto_qol_council_pool.clean"\n')
        ev.write('\t\tcustom_tooltip = "auto_qol_council_pool.clean_tt"\n')
        ev.write("\t\tevery_pool_leader = {\n")
        ev.write("\t\t\tkill_leader = { show_notification = no }\n")
        ev.write("\t\t}\n")
        ev.write("\t\trefresh_leader_pool = yes\n")
        ev.write("\t\thidden_effect = {\n")
        ev.write("\t\t\tcountry_event = { id = auto_qol_council_pool.1 }\n")
        ev.write("\t\t}\n")
        ev.write("\t}\n\n")

        # 启用待选池温和精简 (-5)
        ev.write("\toption = {\n")
        ev.write('\t\tname = "auto_qol_council_pool.clamp_5"\n')
        ev.write('\t\tcustom_tooltip = "auto_qol_council_pool.clamp_5_tt"\n')
        ev.write("\t\tremove_modifier = auto_qol_pool_clamp_5\n")
        ev.write("\t\tremove_modifier = auto_qol_pool_clamp_10\n")
        ev.write("\t\tremove_modifier = auto_qol_pool_clamp_20\n")
        ev.write("\t\tadd_modifier = { modifier = auto_qol_pool_clamp_5 days = -1 }\n")
        ev.write("\t\tevery_pool_leader = { kill_leader = { show_notification = no } }\n")
        ev.write("\t\trefresh_leader_pool = yes\n")
        ev.write("\t\thidden_effect = {\n")
        ev.write("\t\t\tcountry_event = { id = auto_qol_council_pool.1 }\n")
        ev.write("\t\t}\n")
        ev.write("\t}\n\n")

        # 启用待选池强力精简 (-10)
        ev.write("\toption = {\n")
        ev.write('\t\tname = "auto_qol_council_pool.clamp_10"\n')
        ev.write('\t\tcustom_tooltip = "auto_qol_council_pool.clamp_10_tt"\n')
        ev.write("\t\tremove_modifier = auto_qol_pool_clamp_5\n")
        ev.write("\t\tremove_modifier = auto_qol_pool_clamp_10\n")
        ev.write("\t\tremove_modifier = auto_qol_pool_clamp_20\n")
        ev.write("\t\tadd_modifier = { modifier = auto_qol_pool_clamp_10 days = -1 }\n")
        ev.write("\t\tevery_pool_leader = { kill_leader = { show_notification = no } }\n")
        ev.write("\t\trefresh_leader_pool = yes\n")
        ev.write("\t\thidden_effect = {\n")
        ev.write("\t\t\tcountry_event = { id = auto_qol_council_pool.1 }\n")
        ev.write("\t\t}\n")
        ev.write("\t}\n\n")

        # 启用待选池极限精简 (-20)
        ev.write("\toption = {\n")
        ev.write('\t\tname = "auto_qol_council_pool.clamp_20"\n')
        ev.write('\t\tcustom_tooltip = "auto_qol_council_pool.clamp_20_tt"\n')
        ev.write("\t\tremove_modifier = auto_qol_pool_clamp_5\n")
        ev.write("\t\tremove_modifier = auto_qol_pool_clamp_10\n")
        ev.write("\t\tremove_modifier = auto_qol_pool_clamp_20\n")
        ev.write("\t\tadd_modifier = { modifier = auto_qol_pool_clamp_20 days = -1 }\n")
        ev.write("\t\tevery_pool_leader = { kill_leader = { show_notification = no } }\n")
        ev.write("\t\trefresh_leader_pool = yes\n")
        ev.write("\t\thidden_effect = {\n")
        ev.write("\t\t\tcountry_event = { id = auto_qol_council_pool.1 }\n")
        ev.write("\t\t}\n")
        ev.write("\t}\n\n")

        # 关闭精简协议
        ev.write("\toption = {\n")
        ev.write('\t\tname = "auto_qol_council_pool.reset"\n')
        ev.write('\t\tcustom_tooltip = "auto_qol_council_pool.reset_tt"\n')
        ev.write("\t\tremove_modifier = auto_qol_pool_clamp_5\n")
        ev.write("\t\tremove_modifier = auto_qol_pool_clamp_10\n")
        ev.write("\t\tremove_modifier = auto_qol_pool_clamp_20\n")
        ev.write("\t\thidden_effect = {\n")
        ev.write("\t\t\tcountry_event = { id = auto_qol_council_pool.1 }\n")
        ev.write("\t\t}\n")
        ev.write("\t}\n\n")

        # 返回内阁主菜单
        ev.write("\toption = {\n")
        ev.write('\t\tname = "auto_qol_council_pool.back"\n')
        ev.write("\t\tcountry_event = { id = auto_qol_council_menu.1 }\n")
        ev.write("\t}\n")
        ev.write("}\n\n")

        # ======================================================================
        # 2. 为每个席位生成独立的手动挑选领袖事件 (完全手动挑选、带特质预览)
        # ======================================================================
        for c in ordered_councilors:
            pos_name = c['name']
            idx = c['idx']
            ev.write(f"# --------------------------------------------------------\n")
            ev.write(f"# 席位手动指派: {pos_name}\n")
            ev.write(f"# --------------------------------------------------------\n")
            ev.write("country_event = {\n")
            ev.write(f"\tid = auto_qol_council_pick.{idx}\n")
            ev.write(f'\ttitle = "{pos_name}"\n')
            ev.write('\tdesc = "auto_qol_council_pick_leader.1.desc"\n')
            ev.write("\tpicture = GFX_evt_leader_ruler\n")
            ev.write("\tis_triggered_only = yes\n\n")

            # 抓取 5 名本国未就任且未指挥舰队的空闲领袖
            ev.write("\timmediate = {\n")
            for i in range(1, 6):
                ev.write("\t\trandom_owned_leader = {\n")
                ev.write("\t\t\tlimit = {\n")
                ev.write("\t\t\t\tis_pool_leader = no\n")
                ev.write("\t\t\t\tNOR = {\n")
                ev.write("\t\t\t\t\tis_ruler = yes\n")
                ev.write("\t\t\t\t\tis_councilor = yes\n")
                ev.write("\t\t\t\t\texists = fleet\n")
                for j in range(1, i):
                    ev.write(f"\t\t\t\t\tis_same_value = event_target:qol_cand_{j}\n")
                ev.write("\t\t\t\t}\n")
                ev.write("\t\t\t}\n")
                ev.write(f"\t\t\tsave_event_target_as = qol_cand_{i}\n")
                ev.write("\t\t}\n")
            ev.write("\t}\n\n")

            # 5 个领袖指派选项 (附带特质浮窗)
            for i in range(1, 6):
                ev.write(f"\toption = {{\n")
                ev.write(f"\t\ttrigger = {{ exists = event_target:qol_cand_{i} }}\n")
                ev.write(f'\t\tname = "auto_qol_council.pick_cand_{i}"\n')
                ev.write(f'\t\tcustom_tooltip = "auto_qol_council.pick_cand_{i}_tt"\n')
                ev.write("\t\tevery_owned_leader = {\n")
                ev.write(f"\t\t\tlimit = {{ is_councilor_type = {pos_name} }}\n")
                ev.write("\t\t\tremove_council_position = yes\n")
                ev.write("\t\t}\n")
                ev.write(f"\t\tevent_target:qol_cand_{i} = {{\n")
                ev.write(f"\t\t\tset_council_position = {pos_name}\n")
                ev.write("\t\t}\n")
                ev.write("\t\thidden_effect = {\n")
                ev.write("\t\t\tcountry_event = { id = auto_qol_council_menu.1 }\n")
                ev.write("\t\t}\n")
                ev.write("\t}\n\n")

            # 换一批候选领袖 (重新抽取)
            ev.write("\toption = {\n")
            ev.write('\t\tname = "auto_qol_council.refresh_cands"\n')
            ev.write('\t\tcustom_tooltip = "auto_qol_council.refresh_cands_tt"\n')
            ev.write("\t\thidden_effect = {\n")
            ev.write(f"\t\t\tcountry_event = {{ id = auto_qol_council_pick.{idx} }}\n")
            ev.write("\t\t}\n")
            ev.write("\t}\n\n")

            # 仅部署席位，暂不派驻领袖
            ev.write("\toption = {\n")
            ev.write('\t\tname = "auto_qol_council.keep_vacant"\n')
            ev.write('\t\tcustom_tooltip = "auto_qol_council.keep_vacant_tt"\n')
            ev.write("\t\tcountry_event = { id = auto_qol_council_menu.1 }\n")
            ev.write("\t}\n\n")

            # 卸任解职该席位当前领袖
            ev.write("\toption = {\n")
            ev.write('\t\tname = "auto_qol_council.unassign_leader"\n')
            ev.write('\t\tcustom_tooltip = "auto_qol_council.unassign_leader_tt"\n')
            ev.write("\t\tevery_owned_leader = {\n")
            ev.write(f"\t\t\tlimit = {{ is_councilor_type = {pos_name} }}\n")
            ev.write("\t\t\tremove_council_position = yes\n")
            ev.write("\t\t}\n")
            ev.write("\t\tcountry_event = { id = auto_qol_council_menu.1 }\n")
            ev.write("\t}\n\n")

            # 返回内阁席位列表
            ev.write("\toption = {\n")
            ev.write('\t\tname = "auto_qol_council.back_to_positions"\n')
            ev.write("\t\tcountry_event = { id = auto_qol_council_menu.1 }\n")
            ev.write("\t}\n")
            ev.write("}\n\n")

    print(f"Council events successfully regenerated at: {out_file}")

if __name__ == '__main__':
    build_council_system()

import os
import re
from pathlib import Path
from collections import defaultdict

from paths import GAME_INSTALL_DIR, WORKSHOP_MOD_DIR, DOCS_DIR

DOCUMENTS_DIR = DOCS_DIR
OUTPUT_FILE = DOCUMENTS_DIR / "unlock_all_mod_tr.txt"
TIDY_OUTPUT_FILE = DOCUMENTS_DIR / "unlock_tidy_tradition.txt"
VANILLA_OUTPUT_FILE = DOCUMENTS_DIR / "unlock_vanilla_traditions.txt"
SAFE_OUTPUT_FILE = DOCUMENTS_DIR / "unlock_safe_only.txt"

# 匹配传统 ID 的正则（排除注释，捕获以 tr_ 开头的节点定义）
TRADITION_PATTERN = re.compile(r"^\s*(tr_[a-zA-Z0-9_-]+)\s*=", re.MULTILINE)
# 匹配 YML 本地化文本: key:0 "名称" 或 key: "名称"
LOC_PATTERN = re.compile(r'^\s*([a-zA-Z0-9_-]+):(?:\d+)?\s*"([^"\r\n]*)"', re.MULTILINE)

# 飞升路线关键词 (灵能、克隆、变异、纯净、模组、基因、机械、虚拟等)
ASCENSION_KEYWORDS = [
    "psionic", "cloning", "mutation", "purity", "modularity", 
    "genetic", "cybernetic", "synthetic", "virtuality"
]

# 核心排他性硬门槛关键词（飞升路线、起源限定、特殊政体/国策/科技、灭世者、格式塔/机械/蜂巢限定、特殊Mod帝国、隐藏内置）
HARD_RESTRICTION_KEYWORDS = [
    ("has_ascension_perk", "需要飞升"),
    ("has_origin", "需要起源"),
    ("has_authority", "需要政体"),
    ("has_technology", "需要科技"),
    ("has_valid_civic", "需要国策"),
    ("has_ethos", "需要思潮"),
    ("is_machine_empire = yes", "机械限定"),
    ("is_gestalt = yes", "格式塔限定"),
    ("is_hive_empire = yes", "蜂巢限定"),
    ("is_hive_mind = yes", "蜂巢限定"),
    ("is_homicidal", "限制灭世者"),
    ("has_policy_flag", "限制政策"),
    ("is_lust_empire", "特殊帝国限定"),
    ("is_pure_empire", "特殊帝国限定"),
    ("is_lbm_empire", "特殊帝国限定"),
    ("is_ten_empire", "特殊帝国限定"),
    ("is_entropy_drinkers_empire", "特殊帝国限定"),
    ("always = no", "隐藏内置传统"),
]

# 普通帝国基础属性标记（普通帝国常规传统，包含 is_regular_empire = yes, is_machine_empire = no, is_gestalt = no）
REGULAR_EMPIRE_FLAGS = [
    ("is_regular_empire = yes", "普通帝国"),
    ("is_machine_empire = no", "非机械帝国"),
    ("is_gestalt = no", "非格式塔"),
]

# 兼容旧列表供输出注释参考
EXTERNAL_CONDITION_KEYWORDS = HARD_RESTRICTION_KEYWORDS + REGULAR_EMPIRE_FLAGS

# Mod 英文/常用名称的中文对照词典
MOD_NAME_TRANSLATIONS = {
    "Tidy Tradition": "更加整洁的传统 (Tidy Tradition)",
    "Warship Girls R And MIST Species": "战舰少女R与苍青幻影 (Warship Girls R)",
    "Megacorp re-balance by IPC": "巨型企业平衡调整 (Megacorp re-balance)",
    "More Events Mod": "更多随机事件 (More Events Mod)",
    "! Universal Game Rules Patch": "通用游戏规则补丁 Patch",
    "Honkai: Star Rail": "星穹铁道 (Honkai: Star Rail)",
}

def get_tree_stem(tr_id):
    """根据节点 ID 提取所属传统树的干名 (e.g. tr_sh_icebreaking_1 -> tr_sh_icebreaking)"""
    stem = re.sub(r"(_adopt|_finish|_\d+|_swap.*)$", "", tr_id)
    return stem.replace("tradition_", "tr_")

def load_mod_metadata(mod_dir):
    """提取每个 Mod 文件夹 ID 对应的真实名称 (descriptor.mod) 并附带中文备注"""
    mod_titles = {"vanilla": "【原版群星】官方传统"}
    if not os.path.exists(mod_dir):
        return mod_titles

    for entry in os.listdir(mod_dir):
        mod_folder = os.path.join(mod_dir, entry)
        if os.path.isdir(mod_folder):
            desc_path = os.path.join(mod_folder, "descriptor.mod")
            raw_name = f"Mod_{entry}"
            if os.path.exists(desc_path):
                try:
                    with open(desc_path, "r", encoding="utf-8-sig", errors="ignore") as f:
                        content = f.read()
                        name_match = re.search(r'name\s*=\s*"([^"\r\n]+)"', content)
                        if name_match:
                            raw_name = name_match.group(1).strip()
                except Exception:
                    pass

            display_name = raw_name
            for eng_kw, cn_trans in MOD_NAME_TRANSLATIONS.items():
                if eng_kw in raw_name and eng_kw != raw_name:
                    display_name = raw_name.replace(eng_kw, cn_trans)
                    break
                elif eng_kw == raw_name:
                    display_name = cn_trans
                    break
                    
            mod_titles[entry] = display_name
    return mod_titles

def load_all_localizations(game_dir, mod_dir):
    """同时扫描原版游戏与 Mod 目录下的 YML 文本，建立 键ID -> 中文名称 映射字典"""
    loc_map = {}
    search_dirs = [
        os.path.join(game_dir, "localisation"),
        mod_dir
    ]
    for s_dir in search_dirs:
        if not os.path.exists(s_dir):
            continue
        for root, dirs, files in os.walk(s_dir):
            if "localisation" in root.lower() or "localization" in root.lower():
                for file in files:
                    if file.endswith(".yml"):
                        file_path = os.path.join(root, file)
                        is_chinese_file = any(kw in file.lower() for kw in ["chinese", "simp", "zh", "cn"])
                        try:
                            with open(file_path, "r", encoding="utf-8-sig", errors="ignore") as f:
                                content = f.read()
                                for key, val in LOC_PATTERN.findall(content):
                                    clean_val = re.sub(r"§[a-zA-Z0-9!]", "", val).strip()
                                    if clean_val:
                                        if key not in loc_map or is_chinese_file:
                                            loc_map[key] = clean_val
                        except Exception:
                            pass
    return loc_map

def parse_block_restrictions(text_block):
    """提取规则文本块中的硬限制条件（机械/格式塔/蜂巢限定、起源限定、飞升需求、特定政体等）"""
    ext_conds = []
    if "always = no" in text_block:
        ext_conds.append("隐藏内置传统")

    if re.search(r"\bis_machine_empire\s*=\s*yes\b", text_block):
        ext_conds.append("机械限定")
    if re.search(r"\bis_gestalt\s*=\s*yes\b", text_block):
        ext_conds.append("格式塔限定")
    if re.search(r"\bis_hive_(?:empire|mind)\s*=\s*yes\b", text_block):
        ext_conds.append("蜂巢限定")

    for key_pattern, label in [
        ("has_ascension_perk", "需要飞升"),
        ("has_origin", "需要起源"),
        ("has_authority", "需要政体"),
        ("has_technology", "需要科技"),
        ("has_valid_civic", "需要国策"),
        ("has_ethos", "需要思潮"),
        ("is_homicidal", "限制灭世者"),
        ("has_policy_flag", "限制政策"),
        ("is_lust_empire", "特殊帝国限定"),
        ("is_pure_empire", "特殊帝国限定"),
        ("is_lbm_empire", "特殊帝国限定"),
        ("is_ten_empire", "特殊帝国限定"),
        ("is_entropy_drinkers_empire", "特殊帝国限定"),
    ]:
        matches = re.findall(rf"{key_pattern}\s*=\s*([a-zA-Z0-9_-]+)", text_block)
        if matches:
            ext_conds.append(f"{label}:{matches[0]}")
        elif key_pattern in text_block and not re.search(rf"{key_pattern}\s*=\s*(?:no|false)\b", text_block):
            ext_conds.append(label)

    return ext_conds

def parse_tradition_category_file(content):
    """层级匹配解析 tradition_categories 内部的定义块"""
    categories = []
    lines = content.splitlines()
    current_cat = None
    brace_depth = 0
    block_lines = []
    for line in lines:
        line_clean = line.split('#')[0]
        cat_match = re.match(r'^\s*(tradition_[a-zA-Z0-9_-]+)\s*=\s*\{', line_clean)
        if cat_match and brace_depth == 0:
            current_cat = cat_match.group(1)
            block_lines = [line_clean]
            brace_depth += line_clean.count('{') - line_clean.count('}')
        elif current_cat:
            block_lines.append(line_clean)
            brace_depth += line_clean.count('{') - line_clean.count('}')
            if brace_depth <= 0:
                full_text = '\n'.join(block_lines)
                categories.append((current_cat, full_text))
                current_cat = None
                block_lines = []
                brace_depth = 0
    return categories

def scan_all_tradition_tree_categories(game_dir, mod_dir):
    """扫描原版与 Mod 的 common/tradition_categories 建立 节点ID -> 所属传统树ID 的对应关系，并解析 Category 级别的 potential 解锁限制"""
    node_to_category = {}
    category_to_nodes = defaultdict(list)
    category_potentials = defaultdict(list)

    search_dirs = [
        os.path.join(game_dir, "common", "tradition_categories"),
        mod_dir
    ]
    for s_dir in search_dirs:
        if not os.path.exists(s_dir):
            continue
        for root, dirs, files in os.walk(s_dir):
            if "tradition_categories" in root or "tradition_category" in root or root.endswith("tradition_categories"):
                for file in files:
                    if file.endswith(".txt"):
                        file_path = os.path.join(root, file)
                        try:
                            with open(file_path, "r", encoding="utf-8-sig", errors="ignore") as f:
                                content = f.read()
                                cats = parse_tradition_category_file(content)
                                for cat_key, block in cats:
                                    pot_match = re.search(r"potential\s*=\s*\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}", block)
                                    if pot_match:
                                        pot_raw = pot_match.group(1).strip()
                                        ext_conds = parse_block_restrictions(pot_raw)
                                        if ext_conds:
                                            for cond in ext_conds:
                                                if cond not in category_potentials[cat_key]:
                                                    category_potentials[cat_key].append(cond)

                                    tr_block = re.search(r"traditions\s*=\s*\{([^}]*)\}", block)
                                    if tr_block:
                                        node_ids = re.findall(r"tr_[a-zA-Z0-9_-]+", tr_block.group(1))
                                        if node_ids:
                                            base_stem = cat_key.replace("tradition_", "tr_")
                                            adopt_node = f"{base_stem}_adopt"
                                            finish_node = f"{base_stem}_finish"
                                            
                                            all_tree_nodes = set(node_ids)
                                            all_tree_nodes.add(adopt_node)
                                            all_tree_nodes.add(finish_node)
                                            
                                            for n in all_tree_nodes:
                                                node_to_category[n] = cat_key
                                                if n not in category_to_nodes[cat_key]:
                                                    category_to_nodes[cat_key].append(n)
                        except Exception:
                            pass
    return node_to_category, category_to_nodes, category_potentials

def scan_all_tradition_details(game_dir, mod_dir, node_to_category, category_potentials):
    """扫描原版与 Mod 传统节点和组，分析触发事件(on_enabled)与外部解锁门槛(possible)"""
    raw_details = {}
    tree_restricted_conditions = defaultdict(list)
    search_dirs = [
        os.path.join(game_dir, "common", "traditions"),
        mod_dir
    ]
    for s_dir in search_dirs:
        if not os.path.exists(s_dir):
            continue
        for root, dirs, files in os.walk(s_dir):
            if "common" in root and ("tradition" in root):
                for file in files:
                    if file.endswith(".txt"):
                        file_path = os.path.join(root, file)
                        try:
                            with open(file_path, "r", encoding="utf-8-sig", errors="ignore") as f:
                                content = f.read()
                                lines = content.splitlines()
                                current_tr = None
                                brace_depth = 0
                                block_text = []
                                for line in lines:
                                    line_clean = line.split("#")[0]
                                    tr_match = re.match(r"^\s*(tr_[a-zA-Z0-9_-]+|tradition_[a-zA-Z0-9_-]+)\s*=\s*\{", line_clean)
                                    if tr_match and brace_depth == 0:
                                        current_tr = tr_match.group(1)
                                        block_text = [line_clean]
                                        brace_depth += line_clean.count("{") - line_clean.count("}")
                                    elif current_tr:
                                        block_text.append(line_clean)
                                        brace_depth += line_clean.count("{") - line_clean.count("}")
                                        if brace_depth <= 0:
                                            full_block = "\n".join(block_text)
                                            
                                            events_found = re.findall(r"(?:country_event|planet_event|ship_event|fleet_event|fire_event)\s*=\s*(?:\{\s*id\s*=\s*([a-zA-Z0-9_\.-]+)|([a-zA-Z0-9_\.-]+))", full_block)
                                            has_on_enabled = "on_enabled" in full_block
                                            has_on_completed = "on_completed" in full_block
                                            
                                            ev_list = []
                                            for ev_tuple in events_found:
                                                ev_id = ev_tuple[0] or ev_tuple[1]
                                                if ev_id and ev_id not in ev_list:
                                                    ev_list.append(ev_id)
                                                    
                                            pos_match = re.search(r"possible\s*=\s*\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}", full_block)
                                            ext_conditions = []
                                            
                                            stem = get_tree_stem(current_tr)
                                            is_ascension_path = any(ak in current_tr.lower() for ak in ASCENSION_KEYWORDS) or any(ak in stem.lower() for ak in ASCENSION_KEYWORDS)
                                            if is_ascension_path:
                                                ext_conditions.append("需要飞升路线")
                                                
                                            if pos_match:
                                                pos_raw = pos_match.group(1).strip()
                                                node_conds = parse_block_restrictions(pos_raw)
                                                for c in node_conds:
                                                    if c not in ext_conditions:
                                                        ext_conditions.append(c)
                                                if not ext_conditions and "possible" in full_block and "has_tradition" not in pos_raw:
                                                    ext_conditions.append("有规则限制")
                                                    
                                            if ext_conditions:
                                                for cond in ext_conditions:
                                                    if cond not in tree_restricted_conditions[stem]:
                                                        tree_restricted_conditions[stem].append(cond)
                                                        
                                            raw_details[current_tr] = {
                                                "events": ev_list,
                                                "has_on_enabled": has_on_enabled,
                                                "has_on_completed": has_on_completed,
                                                "direct_ext_conditions": ext_conditions,
                                            }
                                            current_tr = None
                                            block_text = []
                                            brace_depth = 0
                        except Exception:
                            pass

    final_details = {}
    all_known_tr_ids = set(raw_details.keys()).union(set(node_to_category.keys()))

    for tr_id in all_known_tr_ids:
        info = raw_details.get(tr_id, {})
        stem = get_tree_stem(tr_id)
        inherited_conds = list(tree_restricted_conditions.get(stem, []))

        # 尝试通过所属 category 获取顶层限制
        cat_key = node_to_category.get(tr_id)
        if not cat_key:
            guessed = "tradition_" + stem.replace("tr_", "")
            cat_key = guessed

        if cat_key in category_potentials:
            for cond in category_potentials[cat_key]:
                if cond not in inherited_conds:
                    inherited_conds.append(cond)

        # 同时包含直接节点限制
        for cond in info.get("direct_ext_conditions", []):
            if cond not in inherited_conds:
                inherited_conds.append(cond)

        final_details[tr_id] = {
            "events": info.get("events", []),
            "has_on_enabled": info.get("has_on_enabled", False),
            "has_on_completed": info.get("has_on_completed", False),
            "ext_conditions": inherited_conds
        }
        
    return final_details

def get_tree_chinese_name(cat_key, loc_map):
    """根据 category 键值在本地化词典中寻找该传统树的中文名称"""
    if cat_key in loc_map:
        return loc_map[cat_key]
    title_key = f"{cat_key}_title"
    if title_key in loc_map:
        return loc_map[title_key]
    base_stem = cat_key.replace("tradition_", "tr_")
    adopt_key = f"{base_stem}_adopt"
    if adopt_key in loc_map:
        return loc_map[adopt_key]
    return cat_key

def write_tradition_group(f, tr_list, loc_map, details_map, node_to_category, safe_only=False, user_skip_nodes=None):
    """将传统列表按【传统树】分组格式化输出。支持用户手动指定跳过的具体节点"""
    if user_skip_nodes is None:
        user_skip_nodes = set()
        
    tree_groups = defaultdict(list)
    ungrouped = []
    
    for tr in tr_list:
        info = details_map.get(tr, {})
        if safe_only and info.get("ext_conditions"):
            continue

        cat_key = node_to_category.get(tr)
        if cat_key:
            tree_groups[cat_key].append(tr)
        else:
            prefix_match = re.match(r"^(tr_[a-zA-Z0-9]+?)(?:_\d|_adopt|_finish|_swap.*|$)", tr)
            if prefix_match:
                guessed_cat = "tradition_" + prefix_match.group(1).replace("tr_", "")
                tree_groups[guessed_cat].append(tr)
            else:
                ungrouped.append(tr)
                
    for cat_key in sorted(tree_groups.keys()):
        nodes = sorted(tree_groups[cat_key], key=lambda x: (
            0 if x.endswith("_adopt") else (2 if x.endswith("_finish") else 1), x
        ))
        if not nodes:
            continue
            
        tree_cn_name = get_tree_chinese_name(cat_key, loc_map)
        
        f.write(f"\n# ------------------------------------------------------------------------------\n")
        f.write(f"# 【传统树】{tree_cn_name} ({cat_key}) - 包含 {len(nodes)} 个节点\n")
        f.write(f"# ------------------------------------------------------------------------------\n")
        
        for tr in nodes:
            cn_name = loc_map.get(tr, "")
            info = details_map.get(tr, {})
            note_parts = []
            if cn_name:
                note_parts.append(cn_name)
            # 检测是否应当注释跳过该节点（用户规则跳过 或 带有外部门槛/飞升条件限制）
            ext_conds = info.get("ext_conditions", [])
            is_user_skipped = tr in user_skip_nodes
            should_comment = is_user_skipped or bool(ext_conds)
            prefix = "# " if should_comment else ""

            if ext_conds:
                note_parts.append(f"[🔒需要外部条件: {', '.join(ext_conds)}]")
            else:
                note_parts.append("[🟢无外部门槛]")
            events = info.get("events", [])
            if events:
                note_parts.append(f"[⚡触发事件: {', '.join(events)}]")
            elif info.get("has_on_enabled"):
                note_parts.append("[⚡包含开启脚本(on_enabled)]")
            elif info.get("has_on_completed"):
                note_parts.append("[⚡包含完成脚本(on_completed)]")
                
            if is_user_skipped:
                note_parts.append("[⛔用户规则跳过]")
            elif ext_conds:
                note_parts.append("[🔒存在限制条件已默认注释]")

            comment = " # " + " ".join(note_parts) if note_parts else ""
            f.write(f"{prefix}activate_tradition {tr}{comment}\n")

    if ungrouped:
        f.write(f"\n# ------------------------------------------------------------------------------\n")
        f.write(f"# 【独立/其他节点】 包含 {len(ungrouped)} 个节点\n")
        f.write(f"# ------------------------------------------------------------------------------\n")
        for tr in sorted(ungrouped):
            cn_name = loc_map.get(tr, "")
            info = details_map.get(tr, {})
            note_parts = []
            if cn_name:
                note_parts.append(cn_name)
            ext_conds = info.get("ext_conditions", [])
            is_user_skipped = tr in user_skip_nodes
            should_comment = is_user_skipped or bool(ext_conds)
            prefix = "# " if should_comment else ""

            if ext_conds:
                note_parts.append(f"[🔒需要外部条件: {', '.join(ext_conds)}]")
            else:
                note_parts.append("[🟢无外部门槛]")
            events = info.get("events", [])
            if events:
                note_parts.append(f"[⚡触发事件: {', '.join(events)}]")
            elif info.get("has_on_enabled"):
                note_parts.append("[⚡包含开启脚本(on_enabled)]")
            elif info.get("has_on_completed"):
                note_parts.append("[⚡包含完成脚本(on_completed)]")
                
            if is_user_skipped:
                note_parts.append("[⛔用户规则跳过]")
            elif ext_conds:
                note_parts.append("[🔒存在限制条件已默认注释]")

            comment = " # " + " ".join(note_parts) if note_parts else ""
            f.write(f"{prefix}activate_tradition {tr}{comment}\n")

def extract_mod_traditions():
    if not os.path.exists(WORKSHOP_MOD_DIR) and not os.path.exists(GAME_INSTALL_DIR):
        print(f"[错误] 未找到游戏与 Mod 路径")
        return

    print("[1/5] 正在解析原版与各 Mod 名称备注...")
    mod_titles = load_mod_metadata(WORKSHOP_MOD_DIR)

    print("[2/5] 正在全盘扫描原版与 Mod 的所有传统节点 ID...")
    mod_traditions_map = defaultdict(set)

    # 1. 扫描原版游戏
    vanilla_tr_dir = os.path.join(GAME_INSTALL_DIR, "common", "traditions")
    if os.path.exists(vanilla_tr_dir):
        for root, dirs, files in os.walk(vanilla_tr_dir):
            for file in files:
                if file.endswith(".txt"):
                    file_path = os.path.join(root, file)
                    try:
                        with open(file_path, "r", encoding="utf-8-sig", errors="ignore") as f:
                            content = f.read()
                            matches = TRADITION_PATTERN.findall(content)
                            for match in matches:
                                mod_traditions_map["vanilla"].add(match)
                    except Exception:
                        pass

    # 2. 扫描 Mod
    if os.path.exists(WORKSHOP_MOD_DIR):
        for root, dirs, files in os.walk(WORKSHOP_MOD_DIR):
            if "common" in root and "traditions" in root:
                rel_path = os.path.relpath(root, WORKSHOP_MOD_DIR)
                mod_folder_id = rel_path.split(os.sep)[0]
                for file in files:
                    if file.endswith(".txt"):
                        file_path = os.path.join(root, file)
                        try:
                            with open(file_path, "r", encoding="utf-8-sig", errors="ignore") as f:
                                content = f.read()
                                matches = TRADITION_PATTERN.findall(content)
                                for match in matches:
                                    mod_traditions_map[mod_folder_id].add(match)
                        except Exception:
                            pass

    total_traditions_count = sum(len(tr_set) for tr_set in mod_traditions_map.values())
    if total_traditions_count == 0:
        print("[提示] 未在目标路径下检索到任何以 tr_ 开头的传统 ID。")
        return

    print(f"[3/5] 正在扫描全盘汉化文本匹配中文名称...")
    loc_map = load_all_localizations(GAME_INSTALL_DIR, WORKSHOP_MOD_DIR)

    print(f"[4/5] 正在分析全盘传统树(Tradition Category)结构与归属及 Category 解锁限制...")
    node_to_category, category_to_nodes, category_potentials = scan_all_tradition_tree_categories(GAME_INSTALL_DIR, WORKSHOP_MOD_DIR)

    print(f"[5/5] 正在分析外部解锁门槛与飞升路线...")
    details_map = scan_all_tradition_details(GAME_INSTALL_DIR, WORKSHOP_MOD_DIR, node_to_category, category_potentials)

    DOCUMENTS_DIR.mkdir(parents=True, exist_ok=True)

    # 指定用户明确要求跳过的节点 (如天主教/天赋树中的健保计划与帝国先锋)
    user_skip_nodes = {
        "tr_aptitude_healthcare_program",
        "tr_aptitude_champions_of_the_empire",
        "tr_aptitude_champion_of_the_people"
    }

    # 1. 生成原版传统单独测试包 (unlock_vanilla_traditions.txt)
    if "vanilla" in mod_traditions_map:
        vanilla_tr_list = sorted(mod_traditions_map["vanilla"])
        with open(VANILLA_OUTPUT_FILE, "w", encoding="utf-8") as f:
            f.write("# ==============================================================================\n")
            f.write("# [原版传统独立测试包] 包含群星原版全部 234 个传统与变种节点\n")
            f.write("# 运行命令: run unlock_vanilla_traditions.txt\n")
            f.write("# 特点: 已包含所有变种节点，且自动跳过了健保计划与帝国先锋！\n")
            f.write("# ==============================================================================\n")

            write_tradition_group(f, vanilla_tr_list, loc_map, details_map, node_to_category, safe_only=False, user_skip_nodes=user_skip_nodes)

    # 2. 生成全激活指令包 (unlock_all_mod_tr.txt)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("# ==============================================================================\n")
        f.write("# 群星 原版与 Mod 传统全解锁指令包\n")
        f.write(f"# 总计分类: {len(mod_traditions_map)} 个 | 总计传统 ID: {total_traditions_count} 个\n")
        f.write("# ==============================================================================\n")

        for mod_folder_id in sorted(mod_traditions_map.keys()):
            mod_name = mod_titles.get(mod_folder_id, f"Mod_{mod_folder_id}")
            tr_list = sorted(mod_traditions_map[mod_folder_id])
            
            f.write(f"\n\n# {'='*78}\n")
            f.write(f"# [来源] {mod_name} (ID: {mod_folder_id}) - 包含 {len(tr_list)} 个传统节点\n")
            f.write(f"# {'='*78}\n")

            write_tradition_group(f, tr_list, loc_map, details_map, node_to_category, safe_only=False, user_skip_nodes=user_skip_nodes)

    # 3. 生成《更加整洁的传统 (Tidy Tradition)》的文本
    tidy_mod_id = "2438313459"
    if tidy_mod_id in mod_traditions_map:
        tidy_tr_list = sorted(mod_traditions_map[tidy_mod_id])
        with open(TIDY_OUTPUT_FILE, "w", encoding="utf-8") as f:
            f.write("# ==============================================================================\n")
            f.write("# [Mod 专属指令包] 更加整洁的传统 (Tidy Tradition)\n")
            f.write(f"# 总计传统 ID: {len(tidy_tr_list)} 个 | 运行命令: run unlock_tidy_tradition.txt\n")
            f.write("# ==============================================================================\n")

            write_tradition_group(f, tidy_tr_list, loc_map, details_map, node_to_category, safe_only=False, user_skip_nodes=user_skip_nodes)

    # 4. 生成【安全合规版】纯无外部门槛指令包 (unlock_safe_only.txt)
    safe_traditions_count = 0
    with open(SAFE_OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("# ==============================================================================\n")
        f.write("# 群星 原版与 Mod 严格安全版传统解锁包\n")
        f.write("# 运行方式: 进入游戏打开控制台输入: run unlock_safe_only.txt\n")
        f.write("# ==============================================================================\n")

        for mod_folder_id in sorted(mod_traditions_map.keys()):
            mod_name = mod_titles.get(mod_folder_id, f"Mod_{mod_folder_id}")
            tr_list = sorted(mod_traditions_map[mod_folder_id])
            
            safe_tr_list = [tr for tr in tr_list if not details_map.get(tr, {}).get("ext_conditions") and tr not in user_skip_nodes]
            if not safe_tr_list:
                continue
                
            safe_traditions_count += len(safe_tr_list)
            f.write(f"\n\n# {'='*78}\n")
            f.write(f"# [来源] {mod_name} (ID: {mod_folder_id}) - 包含 {len(safe_tr_list)} 个绝对安全节点\n")
            f.write(f"# {'='*78}\n")

            write_tradition_group(f, tr_list, loc_map, details_map, node_to_category, safe_only=True, user_skip_nodes=user_skip_nodes)

    print(f"\n[完成] 成功同时扫描【原版游戏】与【Mod】，共找到 {total_traditions_count} 个传统节点！")
    print(f"[1. 原版传统单独测试包] {VANILLA_OUTPUT_FILE}")
    print(f"[2. 更加整洁的传统单表] {TIDY_OUTPUT_FILE}")
    print(f"[3. 严格安全合规版] {SAFE_OUTPUT_FILE}")
    print(f"[4. 全激活总整合包] {OUTPUT_FILE}")

if __name__ == "__main__":
    extract_mod_traditions()
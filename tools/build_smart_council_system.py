# -*- coding: utf-8 -*-
"""
智能全自动内阁席位指派系统构建器 (安全无崩溃稳定版)
1. 彻底解决 EXCEPTION_INT_DIVIDE_BY_ZERO (0xC0000094) 闪退：
   - 彻底删除所有负数 `unlock_council_slots = -1`（底层不支持负数，会导致槽位计数下溢为0造成除零崩溃）。
   - 提供安全的槽位修复选项。
2. 降低席位底座克隆/多生风险（如两个同名席位）：
   - 先尝试把领袖放入已有空席；只有确认目标职务仍未任命时才扩槽和新增席位。
   - 用永久 Flag 保证由本 Mod 新增的每个席位最多扩槽一次。
   - 采用 `set_council_position_to_council` + `set_council_position = <pos_key>` 的原流程。
3. 严格仅索引当前正在生效的 Mod（通过读取 dlc_load.json）：
   - 仅载入玩家当前剧集真正启用的 Mod 席位，彻底根除“Failed to find CouncilPosition”报错。
4. 彻底杜绝领袖重复：
   - 临时 Flag 精准选拔，人数不足时多余选项严格隐藏。
"""

import os, re, json, shutil
from pathlib import Path
from paths import GAME_INSTALL_DIR, MOD_ROOT, WORKSHOP_MOD_DIR

# Keep the three single-class catalogues on one page (currently 24/37/48
# entries).  The much larger mixed catalogue is still split so the event UI
# never has to build all 100+ third-party options at once.
PAGE_SIZE = 50
ROSTER_PAGE_SIZE = 12
# Code-level display mode. Keep this false for the stable in-game flow:
# only seats that can actually be selected are shown. Set true and regenerate
# if you want unavailable seats to appear as disabled/grey options.
SHOW_UNAVAILABLE_SEATS = False
# Emergency-safe category menus: avoid evaluating many third-party council
# availability triggers directly on event option buttons during load/UI build.
FILTER_SEATS_ON_CATEGORY_PAGE = True

# UI Overhaul Dynamic intentionally removes vanilla's six-column cap from the
# council grid. That works for a normal council, but an extended council can
# make the engine's automatic spacing path divide by zero while opening the
# view. Generate a late-loading compatibility copy with a fixed six-column
# grid, allowing the taller UIOD view to wrap seats onto additional rows.
UI_OVERHAUL_DYNAMIC_WORKSHOP_ID = "1623423360"
COUNCIL_GRID_MAX_COLUMNS = 6

HSR_EXTRA_ORIGINS = [
    "origin_Astral_Express",
    "origin_StellaronHunter",
    "origin_Xianzhou",
    "origin_Herta_Space_Station",
    "origin_luosi_star",
    "origin_yaliluo",
]
HSR_EXTRA_AUTHORITIES = ["auth_lieshou", "auth_Astral_Express"]

def strip_comments(content):
    return "\n".join(line.split("#", 1)[0] for line in content.splitlines())

def find_matching_brace(text, open_index):
    depth = 0
    for i in range(open_index, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return i
    return -1

def extract_block_value(block, key):
    match = re.search(rf'\b{re.escape(key)}\s*=\s*\{{', block)
    if not match:
        return None
    open_index = block.find("{", match.start())
    close_index = find_matching_brace(block, open_index)
    if close_index < 0:
        return None
    return block[open_index + 1:close_index].strip()

def iter_named_blocks(text, name):
    pattern = re.compile(rf'\b{re.escape(name)}\s*=\s*\{{')
    for match in pattern.finditer(text):
        open_index = text.find("{", match.start())
        close_index = find_matching_brace(text, open_index)
        if close_index >= 0:
            yield text[open_index + 1:close_index]

def find_more_council_dir(active_mod_dirs=None):
    if active_mod_dirs is not None:
        for active_dir in active_mod_dirs:
            descriptor = active_dir / "descriptor.mod"
            descriptor_text = ""
            if descriptor.exists():
                descriptor_text = descriptor.read_text(
                    encoding="utf-8-sig", errors="ignore"
                )
            if (
                active_dir.name == "3205513494"
                or 'remote_file_id="3205513494"' in descriptor_text
                or 'name="MORE COUNCIL POSITION"' in descriptor_text
            ):
                return active_dir
        return None

    docs_dir = Path.home() / "Documents" / "Paradox Interactive" / "Stellaris"
    candidates = [
        docs_dir / "mod" / "ugc_3205513494.mod",
        WORKSHOP_MOD_DIR / "3205513494" / "descriptor.mod",
    ]
    for descriptor in candidates:
        if not descriptor.exists():
            continue
        try:
            text = descriptor.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        if "MORE COUNCIL POSITION" not in text and "3205513494" not in text:
            continue
        match = re.search(r'path\s*=\s*"([^"]+)"', text)
        if match:
            path = Path(match.group(1).replace("/", "\\"))
            if path.exists():
                return path
        if descriptor.parent.exists() and descriptor.parent.name == "3205513494":
            return descriptor.parent
    fallback = WORKSHOP_MOD_DIR / "3205513494"
    return fallback if fallback.exists() else None

def collect_more_council_triggers(active_mod_dirs=None):
    more_dir = find_more_council_dir(active_mod_dirs)
    if not more_dir:
        return {}
    triggers = {}
    events_dir = more_dir / "events"
    if not events_dir.exists():
        return triggers
    for path in events_dir.rglob("*.txt"):
        try:
            content = strip_comments(path.read_text(encoding="utf-8", errors="ignore"))
        except Exception:
            continue
        for option in iter_named_blocks(content, "option"):
            pos_match = re.search(r'\bset_council_position_to_council\s*=\s*(councilor_[a-zA-Z0-9_]+)', option)
            if not pos_match:
                continue
            trigger = extract_block_value(option, "trigger")
            if not trigger:
                continue
            pos_key = pos_match.group(1)
            triggers.setdefault(pos_key, trigger)
    return triggers

def apply_more_council_triggers(positions, more_triggers):
    for p in positions:
        trigger = more_triggers.get(p["key"])
        if trigger:
            p["more_trigger"] = trigger
            p["more_council_condition"] = True
    return positions

def get_active_mod_dirs():
    docs_dir = Path.home() / "Documents" / "Paradox Interactive" / "Stellaris"
    dlc_load_path = docs_dir / "dlc_load.json"
    active_dirs = []

    if dlc_load_path.exists():
        try:
            dlc_load = json.load(open(dlc_load_path, encoding="utf-8"))
            enabled = dlc_load.get("enabled_mods", [])
            for m in enabled:
                mod_path = docs_dir / m
                if mod_path.exists():
                    text = open(mod_path, encoding="utf-8", errors="ignore").read()
                    match = re.search(r'path\s*=\s*"([^"]+)"', text)
                    if match:
                        p = Path(match.group(1).replace("/", "\\"))
                        if p.exists():
                            active_dirs.append(p)
        except Exception as e:
            print("Error parsing dlc_load.json:", e)

    return active_dirs

def generate_council_ui_compat(active_mod_dirs, output_root=MOD_ROOT):
    source_path = None
    for active_dir in active_mod_dirs:
        candidate = active_dir / "interface" / "council_view.gui"
        if active_dir.name == UI_OVERHAUL_DYNAMIC_WORKSHOP_ID and candidate.exists():
            source_path = candidate
            break

    if source_path is None:
        vanilla_candidate = GAME_INSTALL_DIR / "interface" / "council_view.gui"
        if vanilla_candidate.exists():
            source_path = vanilla_candidate

    if source_path is None:
        raise FileNotFoundError("Could not locate an active or vanilla council_view.gui")

    content = source_path.read_text(encoding="utf-8-sig", errors="strict")
    name_match = re.search(r'\bname\s*=\s*"council_positions_grid"', content)
    if not name_match:
        raise ValueError(f"Council position grid not found in {source_path}")

    block_start = content.rfind("gridBoxType", 0, name_match.start())
    open_index = content.find("{", block_start)
    close_index = find_matching_brace(content, open_index)
    if block_start < 0 or open_index < 0 or close_index < 0:
        raise ValueError(f"Could not parse council position grid in {source_path}")

    block = content[block_start:close_index + 1]
    cap_pattern = re.compile(r'(?m)^(\s*)max_slots_horizontal\s*=\s*\d+\s*$')
    if cap_pattern.search(block):
        block = cap_pattern.sub(
            rf'\1max_slots_horizontal = {COUNCIL_GRID_MAX_COLUMNS}', block, count=1
        )
    else:
        format_match = re.search(r'(?m)^(\s*)format\s*=\s*UPPER_LEFT\s*$', block)
        if not format_match:
            raise ValueError(f"Council position grid format not found in {source_path}")
        indent = format_match.group(1)
        insertion = (
            format_match.group(0)
            + f"\n{indent}# Extended-council crash guard: use a stable fixed divisor and wrap rows."
            + f"\n{indent}max_slots_horizontal = {COUNCIL_GRID_MAX_COLUMNS}"
        )
        block = block[:format_match.start()] + insertion + block[format_match.end():]

    content = content[:block_start] + block + content[close_index + 1:]
    # UIOD currently contains one mixed leading indent (spaces before tabs).
    # Normalize it so generated compatibility files stay diff-clean.
    content = re.sub(
        r'(?m)^[ \t]+',
        lambda match: match.group(0).replace(" ", "")
        if "\t" in match.group(0) else match.group(0),
        content,
    )
    output_path = Path(output_root) / "interface" / "council_view.gui"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")
    return source_path, output_path

def get_loc_dict(active_mod_dirs):
    loc_dict = {}

    def scan_dir(target_dir):
        if not target_dir or not target_dir.exists():
            return
        for root, dirs, files in os.walk(target_dir):
            if "simp_chinese" in root.lower() or "chinese" in root.lower():
                for f in files:
                    if f.endswith(".yml"):
                        p = os.path.join(root, f)
                        try:
                            with open(p, "r", encoding="utf-8-sig", errors="ignore") as file:
                                for line in file:
                                    line = line.strip()
                                    if line.startswith("#") or ":" not in line:
                                        continue
                                    idx = line.find(":")
                                    k = line[:idx].strip()
                                    v = line[idx+1:].strip()
                                    if v.startswith(("0", "1", "2", "3")):
                                        v = v[1:].strip()
                                    if v.startswith('"') and v.endswith('"'):
                                        v = v[1:-1]
                                    if k and v:
                                        loc_dict[k] = v
                        except Exception:
                            pass

    scan_dir(GAME_INSTALL_DIR / "localisation")
    for ad in active_mod_dirs:
        scan_dir(ad / "localisation")

    return loc_dict

def collect_defined_symbols(active_mod_dirs):
    defined = set()
    scan_roots = [
        GAME_INSTALL_DIR / "common" / "governments" / "civics",
        GAME_INSTALL_DIR / "common" / "governments" / "authorities",
    ]
    for ad in active_mod_dirs:
        scan_roots.append(ad / "common" / "governments" / "civics")
        scan_roots.append(ad / "common" / "governments" / "authorities")

    for root in scan_roots:
        if not root.exists():
            continue
        for path in root.rglob("*.txt"):
            try:
                content = strip_comments(path.read_text(encoding="utf-8", errors="ignore"))
            except Exception:
                continue
            for match in re.finditer(r'\b(civic_[a-zA-Z0-9_]+|origin_[a-zA-Z0-9_]+|auth_[a-zA-Z0-9_]+)\s*=', content):
                defined.add(match.group(1))
    return defined

def collect_ruler_position_authorities(active_mod_dirs, loc_dict):
    authority_files = []
    vanilla_auth_dir = GAME_INSTALL_DIR / "common" / "governments" / "authorities"
    if vanilla_auth_dir.exists():
        authority_files.extend(vanilla_auth_dir.glob("*.txt"))

    for ad in active_mod_dirs:
        mod_auth_dir = ad / "common" / "governments" / "authorities"
        if mod_auth_dir.exists():
            authority_files.extend(mod_auth_dir.glob("*.txt"))

    authority_positions = {}
    for path in authority_files:
        try:
            content = strip_comments(path.read_text(encoding="utf-8", errors="ignore"))
        except Exception:
            continue

        for match in re.finditer(r'\b(auth_[a-zA-Z0-9_]+)\s*=\s*\{', content):
            authority = match.group(1)
            open_index = content.find("{", match.start())
            close_index = find_matching_brace(content, open_index)
            if close_index < 0:
                continue
            block = content[open_index + 1:close_index]
            pos_match = re.search(r'\bruler_council_position\s*=\s*(councilor_[a-zA-Z0-9_]+)', block)
            if not pos_match:
                continue
            pos_key = pos_match.group(1)
            authority_positions.setdefault(pos_key, []).append({
                "key": authority,
                "title": loc_dict.get(authority, authority),
            })

    return authority_positions

def scan_all_positions(active_mod_dirs, loc_dict):
    raw_positions = []
    ruler_authorities = collect_ruler_position_authorities(active_mod_dirs, loc_dict)

    VANILLA_RULERS = {
        "councilor_name_key",
        "councilor_ruler_democratic",
        "councilor_ruler_oligarchic",
        "councilor_ruler_dictatorial",
        "councilor_ruler_imperial",
        "councilor_ruler_hive_mind",
        "councilor_ruler_machine_intelligence",
        "councilor_ruler_corporate",
        "councilor_ruler_imperial_cyber",
        "councilor_ruler_imperial_synth",
        "councilor_ruler_imperial_transcendent",
    }

    councilor_files = []

    # 1. 本体目录
    vanilla_c_dir = GAME_INSTALL_DIR / "common" / "governments" / "councilors"
    if vanilla_c_dir.exists():
        for f in os.listdir(vanilla_c_dir):
            if f.endswith(".txt"):
                councilor_files.append((vanilla_c_dir / f, None))

    # 2. 仅扫描已启用的 Mod 目录
    for ad in active_mod_dirs:
        mod_c_dir = ad / "common" / "governments" / "councilors"
        if mod_c_dir.exists():
            for f in os.listdir(mod_c_dir):
                if f.endswith(".txt"):
                    councilor_files.append((mod_c_dir / f, ad))

    seen_keys = set()

    for path, source_dir in councilor_files:
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as file:
                content = strip_comments(file.read())
        except Exception:
            continue

        for m in re.finditer(r'\b(councilor_[a-zA-Z0-9_]+)\s*=\s*\{', content):
            key = m.group(1)
            open_index = content.find("{", m.start())
            close_index = find_matching_brace(content, open_index)
            if close_index < 0:
                continue
            body = content[open_index + 1:close_index]

            if key in VANILLA_RULERS or key in seen_keys:
                continue
            seen_keys.add(key)

            lclass = re.findall(r'leader_class\s*=\s*(?:\{([^}]+)\}|([a-zA-Z0-9_]+))', body)
            classes = []
            for c1, c2 in lclass:
                if c1: classes.extend(c1.split())
                if c2: classes.append(c2)
            classes = sorted(list(set(classes)))
            if not classes:
                classes = ["commander", "official", "scientist"]

            civic_m = re.search(r'civic\s*=\s*([a-zA-Z0-9_]+)', body)
            civic = civic_m.group(1) if civic_m else None

            possible = extract_block_value(body, "possible")

            title = loc_dict.get(key, key)
            if title == key or (title.startswith("$") and title.endswith("$")):
                continue
            civic_title = loc_dict.get(civic, "") if civic else ""

            raw_positions.append({
                "key": key,
                "classes": classes,
                "civic": civic,
                "ruler_authorities": ruler_authorities.get(key, []),
                "possible": possible,
                "title": title,
                "civic_title": civic_title,
                "file": path.name,
                "source_dir": str(source_dir) if source_dir else None,
            })

    return raw_positions

def organize_categories(positions):
    cat_scientist = {
        "cat_id": 20,
        "cat_tag": "scientist",
        "cat_name": "【科研类内阁席位】",
        "cat_desc": "专属于资深科研学者、深空探索先驱与科技创新领域的专家席位。",
        "positions": []
    }
    cat_commander = {
        "cat_id": 40,
        "cat_tag": "commander",
        "cat_name": "【军事类内阁席位】",
        "cat_desc": "专属于星际舰队统帅、战略要塞司令与征伐防务领域的军事席位。",
        "positions": []
    }
    cat_official = {
        "cat_id": 30,
        "cat_tag": "official",
        "cat_name": "【行政类内阁席位】",
        "cat_desc": "专属于商业巨擘、工业总管、政务首辅与星海外交领域的行政席位。",
        "positions": []
    }
    cat_multi = {
        "cat_id": 60,
        "cat_tag": "multi",
        "cat_name": "【通用类内阁席位】",
        "cat_desc": "支持多种领袖类型兼任的复合席位，涵盖猎手总管、大档案库典藏、宗教文化、星际神话等领域。",
        "positions": []
    }

    event_id_counter = 1000

    # 1. 科学家大类：严格区分游牧与常规
    cat_scientist["positions"].append({
        "id": 201,
        "key": "councilor_research_nomadic",
        "title": "科学专员 (游牧科研主管)",
        "classes": ["scientist"],
        "civic": None,
        "possible": "is_gestalt = no is_nomadic = yes",
        "desc": "全学科科研速度提升 (游牧帝国专属科研席位)"
    })
    cat_scientist["positions"].append({
        "id": 202,
        "key": "councilor_research",
        "title": "首席科学家 (常规科研主管)",
        "classes": ["scientist"],
        "civic": None,
        "possible": "is_gestalt = no is_nomadic = no",
        "desc": "全学科科研速度提升 (常规帝国核心科研席位)"
    })

    # 2. 指挥官大类：严格区分游牧与常规
    cat_commander["positions"].append({
        "id": 401,
        "key": "councilor_defense_nomadic",
        "title": "战术指挥官 (游牧防务主管)",
        "classes": ["commander"],
        "civic": None,
        "possible": "is_gestalt = no is_nomadic = yes",
        "desc": "全舰队维护费与极速加成 (游牧帝国专属防务席位)"
    })
    cat_commander["positions"].append({
        "id": 402,
        "key": "councilor_defense",
        "title": "防务总长 (常规防务统帅)",
        "classes": ["commander"],
        "civic": None,
        "possible": "is_gestalt = no is_nomadic = no",
        "desc": "舰队维护费与星港开销降低 (常规帝国核心防务席位)"
    })

    # 3. 官员大类：严格区分游牧与常规
    cat_official["positions"].append({
        "id": 301,
        "key": "councilor_state_nomadic",
        "title": "舰队大使 (游牧政务外交总管)",
        "classes": ["official"],
        "civic": None,
        "possible": "blocks_minister_of_state = no is_gestalt = no is_nomadic = yes",
        "desc": "凝聚力与外交网络效率加成 (游牧帝国专属政务席位)"
    })
    cat_official["positions"].append({
        "id": 302,
        "key": "councilor_state",
        "title": "国务大臣 (常规政务外交总管)",
        "classes": ["official"],
        "civic": None,
        "possible": "blocks_minister_of_state = no is_gestalt = no is_nomadic = no",
        "desc": "凝聚力产出与外交亲善关系提升 (常规帝国核心政务席位)"
    })

    already_added = {
        "councilor_research", "councilor_research_nomadic",
        "councilor_defense", "councilor_defense_nomadic",
        "councilor_state", "councilor_state_nomadic"
    }

    for p in positions:
        key = p["key"]
        if key in already_added:
            continue
        if (
            not p.get("more_trigger")
            and not p.get("civic")
            and not p.get("ruler_authorities")
            and not p.get("possible")
        ):
            continue
        already_added.add(key)

        classes = p["classes"]
        p_copy = dict(p)
        p_copy["id"] = event_id_counter
        event_id_counter += 1

        if p.get("more_council_condition"):
            p_copy["desc"] = "沿用《更多内阁》的席位显示条件"
        elif p.get("civic_title"):
            p_copy["desc"] = f"前置国民理念：【{p['civic_title']}】"
        elif p.get("ruler_authorities"):
            auth_names = " / ".join(a["title"] for a in p["ruler_authorities"])
            p_copy["desc"] = f"前置政体：【{auth_names}】"
        elif p.get("possible"):
            p_copy["desc"] = "前置特殊解锁条件"
        else:
            p_copy["desc"] = "通用专属内阁席位"

        if classes == ["scientist"]:
            cat_scientist["positions"].append(p_copy)
        elif classes == ["commander"]:
            cat_commander["positions"].append(p_copy)
        elif classes == ["official"]:
            cat_official["positions"].append(p_copy)
        else:
            cat_multi["positions"].append(p_copy)

    return [cat_scientist, cat_commander, cat_official, cat_multi]

def build_hsr_unlock_condition(civic, defined_symbols):
    # Keep council seat availability aligned with the vanilla picker.
    # Broadening one civic-bound HSR seat to every HSR origin/authority makes
    # many unrelated seats appear at once and can overload the event UI.
    if civic:
        return f"has_valid_civic = {civic}"
    return "always = no"

def append_unique_condition(conditions, condition):
    if not condition:
        return
    normalized = re.sub(r'\s+', ' ', condition).strip()
    if not normalized:
        return
    seen = {re.sub(r'\s+', ' ', c).strip() for c in conditions}
    if normalized not in seen and not any(normalized in existing for existing in seen):
        conditions.append(condition)

def strip_own_councilor_absence_guard(condition, pos_key):
    """Remove More Council's add-seat guard so existing empty seats remain assignable."""
    if not condition:
        return condition
    result = []
    cursor = 0
    pattern = re.compile(r'\bNOT\s*=\s*\{')
    for match in pattern.finditer(condition):
        open_index = condition.find("{", match.start())
        close_index = find_matching_brace(condition, open_index)
        if close_index < 0:
            continue
        block = condition[open_index + 1:close_index]
        has_own_councilor_guard = re.search(
            rf'\bhas_councilor\s*=\s*\{{[^{{}}]*\bCOUNCILOR\s*=\s*{re.escape(pos_key)}\b[^{{}}]*\}}',
            block,
            re.DOTALL,
        )
        if not has_own_councilor_guard:
            continue
        result.append(condition[cursor:match.start()])
        cursor = close_index + 1
    result.append(condition[cursor:])
    return "\n".join(line.rstrip() for line in "".join(result).splitlines() if line.strip()).strip()

def build_position_availability_conditions(pos, defined_symbols):
    conditions = []
    if pos.get("more_trigger"):
        append_unique_condition(conditions, strip_own_councilor_absence_guard(pos["more_trigger"], pos["key"]))
    elif pos.get("civic"):
        civ = pos["civic"]
        if any(k in pos.get("file", "").lower() for k in ["hunter", "hsr", "xianzhou", "herta", "ipc", "yaliluo"]) or "StellaronHunter" in civ:
            append_unique_condition(conditions, build_hsr_unlock_condition(civ, defined_symbols))
        else:
            append_unique_condition(conditions, f"has_valid_civic = {civ}")
    elif pos.get("ruler_authorities"):
        auth_checks = [f"has_authority = {a['key']}" for a in pos["ruler_authorities"]]
        if len(auth_checks) == 1:
            append_unique_condition(conditions, auth_checks[0])
        else:
            append_unique_condition(conditions, "OR = { " + " ".join(auth_checks) + " }")

    if pos.get("possible"):
        append_unique_condition(conditions, pos["possible"])

    # A filled seat must not be offered for another appointment.  Keep this
    # explicit even when MORE COUNCIL POSITION already supplies the same
    # absence guard, because some vanilla and third-party seats do not.
    append_unique_condition(
        conditions,
        f"NOT = {{ has_councilor = {{ COUNCILOR = {pos['key']} }} }}",
    )

    return conditions

def build_category_page_conditions(pos, defined_symbols):
    """Keep category pages aligned with seats the vanilla picker can select."""
    conditions = []
    if pos.get("more_trigger"):
        append_unique_condition(conditions, strip_own_councilor_absence_guard(pos["more_trigger"], pos["key"]))
    if pos.get("civic"):
        civ = pos["civic"]
        if any(k in pos.get("file", "").lower() for k in ["hunter", "hsr", "xianzhou", "herta", "ipc", "yaliluo"]) or "StellaronHunter" in civ:
            append_unique_condition(conditions, build_hsr_unlock_condition(civ, defined_symbols))
        else:
            append_unique_condition(conditions, f"has_valid_civic = {civ}")
    if pos.get("ruler_authorities"):
        auth_checks = [f"has_authority = {a['key']}" for a in pos["ruler_authorities"]]
        if len(auth_checks) == 1:
            append_unique_condition(conditions, auth_checks[0])
        else:
            append_unique_condition(conditions, "OR = { " + " ".join(auth_checks) + " }")
    if pos.get("possible"):
        append_unique_condition(conditions, pos["possible"])

    # Hide seats that already have an incumbent.  The candidate screen repeats
    # this check so a previously opened window cannot reassign the same seat.
    append_unique_condition(
        conditions,
        f"NOT = {{ has_councilor = {{ COUNCILOR = {pos['key']} }} }}",
    )

    return conditions

def indent_script(text, tabs):
    prefix = "\t" * tabs
    return "\n".join(prefix + line if line else line for line in text.splitlines())

def build_any_available_condition(positions, defined_symbols):
    """Return a country-scope trigger that is true when this page has a visible seat."""
    alternatives = []
    for pos in positions:
        conditions = build_category_page_conditions(pos, defined_symbols)
        body = "\n".join(indent_script(condition, 1) for condition in conditions)
        alternatives.append(f"AND = {{\n{body}\n}}")

    if not alternatives:
        return "always = no"
    if len(alternatives) == 1:
        return alternatives[0]
    return "OR = {\n" + "\n".join(indent_script(item, 1) for item in alternatives) + "\n}"

def build_page_route(page_indexes, pages, category_id, defined_symbols, fallback_event_id=None):
    """Route to the first non-empty page, skipping pages hidden by runtime filters."""
    route = []
    for route_index, page_index in enumerate(page_indexes):
        keyword = "if" if route_index == 0 else "else_if"
        event_id = category_id if page_index == 0 else category_id + page_index
        condition = build_any_available_condition(pages[page_index], defined_symbols)
        route.append(
            f"{keyword} = {{\n"
            f"\tlimit = {{\n{indent_script(condition, 2)}\n\t}}\n"
            f"\tcountry_event = {{ id = auto_qol_council_assign.{event_id} }}\n"
            f"}}"
        )

    if fallback_event_id is not None:
        route.append(
            "else = {\n"
            f"\tcountry_event = {{ id = auto_qol_council_assign.{fallback_event_id} }}\n"
            "}"
        )
    return "\n".join(route)

def generate_events(categories, defined_symbols):
    lines = []
    lines.append("namespace = auto_qol_council_assign\n")

    # 1. 顶层大类选择中枢
    lines.append("""# ========================================================
# 内阁席位点名指派中枢大厅 (四大领袖类型架构)
# ========================================================
country_event = {
\tid = auto_qol_council_assign.1
\ttitle = "auto_qol_council_assign.1.name"
\tdesc = "auto_qol_council_assign.1.desc"
\tpicture = GFX_evt_throne_room
\tis_triggered_only = yes
""")
    for cat in categories:
        cid = cat["cat_id"]
        ctag = cat["cat_tag"]
        positions = cat["positions"]
        pages = [positions[i:i + PAGE_SIZE] for i in range(0, len(positions), PAGE_SIZE)] or [[]]
        category_available = build_any_available_condition(positions, defined_symbols)
        category_route = build_page_route(range(len(pages)), pages, cid, defined_symbols)
        lines.append(f"""\toption = {{
\t\ttrigger = {{
{indent_script(category_available, 3)}
\t\t}}
\t\tname = "auto_qol_council_assign.cat_{ctag}"
{indent_script(category_route, 2)}
\t}}
""")
    # 查看名册、返回与离开。席位容量由任命流程自动管理。
    lines.append("""\toption = {
\t\tname = "auto_qol_council_assign.view_roster"
\t\tcountry_event = { id = auto_qol_council_assign.90 }
\t}

\toption = {
\t\tname = "auto_qol_council_assign.back_to_council_menu"
\t\tcountry_event = { id = auto_qol_council_menu.1 }
\t}

\toption = {
\t\tname = "auto_qol.close_direct"
\t}
}
""")

    # 2. 四大分类二级菜单：分页生成，避免事件窗口一次刷出上百个选项导致 UI/底层崩溃
    for cat in categories:
        cid = cat["cat_id"]
        positions = cat["positions"]
        pages = [positions[i:i + PAGE_SIZE] for i in range(0, len(positions), PAGE_SIZE)] or [[]]
        for page_index, page_positions in enumerate(pages):
            event_id = cid if page_index == 0 else cid + page_index
            lines.append(f"""# ========================================================
# 分类子菜单: {cat["cat_name"]} 第 {page_index + 1} 页
# ========================================================
country_event = {{
\tid = auto_qol_council_assign.{event_id}
\ttitle = "auto_qol_council_assign.{event_id}.name"
\tdesc = "auto_qol_council_assign.{event_id}.desc"
\tpicture = GFX_evt_throne_room
\tis_triggered_only = yes
""")
            for pos in page_positions:
                pos_id = pos["id"]
                pos_key = pos["key"]

                trigger_conditions = build_category_page_conditions(pos, defined_symbols)
                trigger_body = "\n\t\t\t".join(trigger_conditions)
                gate_keyword = "allow" if SHOW_UNAVAILABLE_SEATS else "trigger"
                gate_block = ""
                if FILTER_SEATS_ON_CATEGORY_PAGE:
                    gate_block = f"""\t\t{gate_keyword} = {{
\t\t\t{trigger_body}
\t\t}}
"""
                else:
                    gate_block = "\t\ttrigger = { always = yes }\n"
                lines.append(f"""\toption = {{
{gate_block}
\t\tname = "auto_qol_council_assign.{pos_key}.btn"
\t\tcustom_tooltip = "auto_qol_council_assign.{pos_key}.tt"
\t\tcountry_event = {{ id = auto_qol_council_assign.{pos_id} }}
\t}}
""")
            if page_index > 0:
                previous_pages = list(range(page_index - 1, -1, -1))
                previous_available = build_any_available_condition(
                    [pos for index in previous_pages for pos in pages[index]], defined_symbols
                )
                previous_route = build_page_route(previous_pages, pages, cid, defined_symbols)
                lines.append(f"""\toption = {{
\t\ttrigger = {{
{indent_script(previous_available, 3)}
\t\t}}
\t\tname = "auto_qol_council_assign.prev_page"
{indent_script(previous_route, 2)}
\t}}
""")
            if page_index < len(pages) - 1:
                following_pages = list(range(page_index + 1, len(pages)))
                following_available = build_any_available_condition(
                    [pos for index in following_pages for pos in pages[index]], defined_symbols
                )
                following_route = build_page_route(following_pages, pages, cid, defined_symbols)
                lines.append(f"""\toption = {{
\t\ttrigger = {{
{indent_script(following_available, 3)}
\t\t}}
\t\tname = "auto_qol_council_assign.next_page"
{indent_script(following_route, 2)}
\t}}
""")

            lines.append(f"""\toption = {{
\t\tname = "auto_qol_council_assign.back_to_assign_menu"
\t\tcountry_event = {{ id = auto_qol_council_assign.1 }}
\t}}

\toption = {{
\t\tname = "auto_qol.close_direct"
\t}}
}}
""")

    # 3. 候选人点名挑选菜单 (采用 Flag 机制杜绝残留与克隆)
    for cat in categories:
        cid = cat["cat_id"]
        for pos in cat["positions"]:
            pos_id = pos["id"]
            pos_key = pos["key"]
            pos_title = pos["title"]
            target_classes = pos["classes"]
            availability_conditions = build_position_availability_conditions(pos, defined_symbols)
            availability_option_body = "\n\t\t\t".join(availability_conditions)
            availability_not_body = "\n\t\t\t\t".join(availability_conditions)

            if len(target_classes) == 1:
                class_filter = f"leader_class = {target_classes[0]}"
            elif len(target_classes) > 1 and len(target_classes) < 3:
                inner = " ".join([f"leader_class = {c}" for c in target_classes])
                class_filter = f"OR = {{ {inner} }}"
            else:
                class_filter = ""

            lines.append(f"""# 候选人挑选: {pos_title} ({pos_key}) [ID: auto_qol_council_assign.{pos_id}]
country_event = {{
\tid = auto_qol_council_assign.{pos_id}
\ttitle = "auto_qol_council_assign.{pos_key}.pick_name"
\tdesc = "auto_qol_council_assign.pick_desc"
\tpicture = GFX_evt_throne_room
\tis_triggered_only = yes

\timmediate = {{
\t\tauto_qol_clear_council_candidate_flags = yes
\t\trandom_owned_leader = {{
\t\t\tlimit = {{
\t\t\t\tis_pool_leader = no
\t\t\t\tis_ruler = no
\t\t\t\tis_councilor = no
\t\t\t\tNOT = {{ exists = fleet }}
\t\t\t\t{class_filter}
\t\t\t}}
\t\t\tset_leader_flag = auto_qol_cand_flag_1
\t\t\tsave_event_target_as = auto_qol_cand_1
\t\t}}
\t\trandom_owned_leader = {{
\t\t\tlimit = {{
\t\t\t\tis_pool_leader = no
\t\t\t\tis_ruler = no
\t\t\t\tis_councilor = no
\t\t\t\tNOT = {{ exists = fleet }}
\t\t\t\tNOT = {{ has_leader_flag = auto_qol_cand_flag_1 }}
\t\t\t\t{class_filter}
\t\t\t}}
\t\t\tset_leader_flag = auto_qol_cand_flag_2
\t\t\tsave_event_target_as = auto_qol_cand_2
\t\t}}
\t\trandom_owned_leader = {{
\t\t\tlimit = {{
\t\t\t\tis_pool_leader = no
\t\t\t\tis_ruler = no
\t\t\t\tis_councilor = no
\t\t\t\tNOT = {{ exists = fleet }}
\t\t\t\tNOT = {{ has_leader_flag = auto_qol_cand_flag_1 }}
\t\t\t\tNOT = {{ has_leader_flag = auto_qol_cand_flag_2 }}
\t\t\t\t{class_filter}
\t\t\t}}
\t\t\tset_leader_flag = auto_qol_cand_flag_3
\t\t\tsave_event_target_as = auto_qol_cand_3
\t\t}}
\t\trandom_owned_leader = {{
\t\t\tlimit = {{
\t\t\t\tis_pool_leader = no
\t\t\t\tis_ruler = no
\t\t\t\tis_councilor = no
\t\t\t\tNOT = {{ exists = fleet }}
\t\t\t\tNOT = {{ has_leader_flag = auto_qol_cand_flag_1 }}
\t\t\t\tNOT = {{ has_leader_flag = auto_qol_cand_flag_2 }}
\t\t\t\tNOT = {{ has_leader_flag = auto_qol_cand_flag_3 }}
\t\t\t\t{class_filter}
\t\t\t}}
\t\t\tset_leader_flag = auto_qol_cand_flag_4
\t\t\tsave_event_target_as = auto_qol_cand_4
\t\t}}
\t}}
""")

            # 4 个任命选项 (严格依赖 Flag 存在；一步完成席位准备与领袖派驻)
            for c_idx in [1, 2, 3, 4]:
                lines.append(f"""\toption = {{
\t\ttrigger = {{
\t\t\tany_owned_leader = {{ has_leader_flag = auto_qol_cand_flag_{c_idx} }}
\t\t\t{availability_option_body}
\t\t}}
\t\tname = "auto_qol_assign.cand_{c_idx}"
\t\tevent_target:auto_qol_cand_{c_idx} = {{
\t\t\t# 优先复用原版 UI 或本 Mod 已经创建的空席位。
\t\t\tset_council_position = {pos_key}
\t\t}}
\t\tif = {{
\t\t\tlimit = {{
\t\t\t\tevent_target:auto_qol_cand_{c_idx} = {{
\t\t\t\t\tNOT = {{ is_councilor_type = {pos_key} }}
\t\t\t\t}}
\t\t\t}}
\t\t\tif = {{
\t\t\t\tlimit = {{ NOT = {{ has_country_flag = auto_qol_slot_{pos_key} }} }}
\t\t\t\tset_country_flag = auto_qol_slot_{pos_key}
\t\t\t\tunlock_council_slots = 1
\t\t\t\tset_council_position_to_council = {pos_key}
\t\t\t}}
\t\t\tevent_target:auto_qol_cand_{c_idx} = {{
\t\t\t\tset_council_position = {pos_key}
\t\t\t}}
\t\t}}
\t\tevent_target:auto_qol_cand_{c_idx} = {{
\t\t\tsave_event_target_as = auto_qol_last_assigned
\t\t}}
\t\tauto_qol_clear_council_candidate_flags = yes
\t\tcountry_event = {{ id = auto_qol_council_assign.99 }}
\t}}
""")
            # 若无可用候选人，呈现指引
            lines.append(f"""\toption = {{
\t\ttrigger = {{
\t\t\tOR = {{
\t\t\t\tNOT = {{ any_owned_leader = {{ has_leader_flag = auto_qol_cand_flag_1 }} }}
\t\t\t\tNOT = {{
\t\t\t\t{availability_not_body}
\t\t\t\t}}
\t\t\t}}
\t\t}}
\t\tname = "auto_qol_assign.no_candidate"
\t\tcountry_event = {{ id = auto_qol_council_assign.999 }}
\t}}
""")

            # 刷新、返回分类与关闭
            lines.append(f"""\t# 刷新换一批
\toption = {{
\t\ttrigger = {{ any_owned_leader = {{ has_leader_flag = auto_qol_cand_flag_1 }} }}
\t\tname = "auto_qol_assign.refresh"
\t\tcountry_event = {{ id = auto_qol_council_assign.{pos_id} }}
\t}}
\t# 返回分类子菜单
\toption = {{
\t\tname = "auto_qol_assign.back_to_cat"
\t\tcountry_event = {{ id = auto_qol_council_assign.{cid} }}
\t}}

\t# 离开并关闭界面 (支持右上角X与ESC)
\toption = {{
\t\tname = "auto_qol.close_direct"
\t}}
}}
""")

    # 4. 结算成功通知界面 (ID: auto_qol_council_assign.99)
    lines.append("""# ========================================================
# 席位任命成功通报界面
# ========================================================
country_event = {
\tid = auto_qol_council_assign.99
\ttitle = "auto_qol_council_assign.99.name"
\tdesc = "auto_qol_council_assign.99.desc"
\tpicture = GFX_evt_throne_room
\tis_triggered_only = yes

\toption = {
\t\tname = "auto_qol_council_assign.success.continue"
\t\tcountry_event = { id = auto_qol_council_assign.1 }
\t}

\toption = {
\t\tname = "auto_qol_council_assign.success.view_roster"
\t\tcountry_event = { id = auto_qol_council_assign.90 }
\t}

\toption = {
\t\tname = "auto_qol_council_assign.success.close"
\t\tdefault_hide_option = yes
\t}
}
""")

    # 5. 空闲领袖不足说明指引 (ID: auto_qol_council_assign.999)
    lines.append("""# ========================================================
# 暂无可用空闲领袖指引界面
# ========================================================
country_event = {
\tid = auto_qol_council_assign.999
\ttitle = "auto_qol_council_assign.999.name"
\tdesc = "auto_qol_council_assign.999.desc"
\tpicture = GFX_evt_throne_room
\tis_triggered_only = yes

\toption = {
\t\tname = "auto_qol_council_assign.back_to_assign_menu"
\t\tcountry_event = { id = auto_qol_council_assign.1 }
\t}

\toption = {
\t\tname = "auto_qol.close_direct"
\t}
}
""")

    # 6. 在任名册查阅界面 (ID: auto_qol_council_assign.90)
    lines.append("""# ========================================================
# 当前在任领袖名册展示界面
# ========================================================
country_event = {
\tid = auto_qol_council_assign.90
\ttitle = "auto_qol_council_assign.90.name"
\tdesc = "auto_qol_council_assign.90.desc"
\tpicture = GFX_evt_throne_room
\tis_triggered_only = yes

\timmediate = {
\t\tevery_owned_leader = {
""")
    for roster_index in range(1, ROSTER_PAGE_SIZE + 1):
        lines.append(f"\t\t\tremove_leader_flag = auto_qol_roster_flag_{roster_index}\n")
    lines.append("\t\t}\n")

    for roster_index in range(1, ROSTER_PAGE_SIZE + 1):
        lines.append("\t\trandom_owned_leader = {\n")
        lines.append("\t\t\tlimit = {\n")
        lines.append("\t\t\t\tis_councilor = yes\n")
        for previous_index in range(1, roster_index):
            lines.append(
                f"\t\t\t\tNOT = {{ has_leader_flag = auto_qol_roster_flag_{previous_index} }}\n"
            )
        lines.append("\t\t\t}\n")
        lines.append(f"\t\t\tset_leader_flag = auto_qol_roster_flag_{roster_index}\n")
        lines.append(f"\t\t\tsave_event_target_as = auto_qol_in_office_{roster_index}\n")
        lines.append("\t\t}\n")

    lines.append("\t}\n\n")
    for roster_index in range(1, ROSTER_PAGE_SIZE + 1):
        lines.append(f"""\toption = {{
\t\ttrigger = {{ any_owned_leader = {{ has_leader_flag = auto_qol_roster_flag_{roster_index} }} }}
\t\tname = "auto_qol_assign.roster_{roster_index}"
\t}}
""")

    lines.append("""
\toption = {
\t\tname = "auto_qol_assign.roster_refresh"
\t\tcountry_event = { id = auto_qol_council_assign.90 }
\t}

\toption = {
\t\tname = "auto_qol_council_assign.back_to_assign_menu"
\t\tcountry_event = { id = auto_qol_council_assign.1 }
\t}

\toption = {
\t\tname = "auto_qol.close_direct"
\t}
}
""")
    return "".join(lines)

def generate_loc(categories):
    loc = []
    seat_visibility_desc = (
        "仅显示当前可指派席位；不可用席位会变灰。"
        if FILTER_SEATS_ON_CATEGORY_PAGE and SHOW_UNAVAILABLE_SEATS else
        "仅显示当前可指派席位；按钮较多时可滚动查看。"
    )
    loc.append(' auto_qol_council_menu.manual_assign:0 "【政务内阁】核心席位手动点名指派中枢"')
    loc.append(' auto_qol_council_menu.manual_assign_tt:0 "§G点击进入内阁点名指派中枢§!\\n不受原版内阁大厅可视席位数量影响，可点名任命额外席位并使其后台效果正常生效。"')

    loc.append(' auto_qol_council_assign.1.name:0 "帝国政务内阁 · 席位点名指派中枢"')
    loc.append(' auto_qol_council_assign.1.desc:0 "§H欢迎使用内阁席位手动指派中枢§!\\n\\n原版内阁现可安全打开；受游戏界面限制，未显示的额外席位请在【在任名册】中查看。所有已任命席位的特质与帝国增益仍会在后台生效。\\n\\n§E请选择席位职能分类：§!"')
    loc.append(' auto_qol_council_assign.view_roster:0 "【在任名册】查阅当前后台已在任内阁领袖"')

    loc.append(' auto_qol_council_assign.back_to_council_menu:0 "返回助手内阁主控制台"')
    loc.append(' auto_qol_council_assign.back_to_assign_menu:0 "返回席位职能分类"')
    loc.append(' auto_qol_council_assign.back_to_cat:0 "返回当前分类"')
    loc.append(' auto_qol_assign.back_to_cat:0 "返回当前分类"')
    loc.append(' auto_qol_assign.refresh:0 "【换一批候选领袖 (随机刷新)】"')
    loc.append(' auto_qol.close_direct:0 "离开并关闭界面 (X / ESC)"')

    loc.append(' auto_qol_assign.no_candidate:0 "【暂无空闲可用领袖】点击查看原因与指引"')
    loc.append(' auto_qol_council_assign.999.name:0 "暂无可委派的空闲领袖"')
    loc.append(' auto_qol_council_assign.999.desc:0 "§H当前名下未检测到可派驻该职位的空闲领袖！§!\\n\\n§E排查建议：§!\\n1. §Y一人不可身兼数职§!：已经在其他内阁席位任职的领袖无法重复指派。\\n2. §Y下船要求§!：正在指挥科研船执行探索/考古，或正在率领作战舰队的领袖无法直接调入内阁。请先让其停止任务/右键下船。\\n3. §Y招募新人§!：若当前职业领袖已全部在职，请先前往领袖面板招募新的专家，随后即可在此处直接点名上岗！"')
    loc.append(' auto_qol_assign.cand_1:0 "任命：[auto_qol_cand_1.GetName] ([auto_qol_cand_1.GetClass])"')
    loc.append(' auto_qol_assign.cand_2:0 "任命：[auto_qol_cand_2.GetName] ([auto_qol_cand_2.GetClass])"')
    loc.append(' auto_qol_assign.cand_3:0 "任命：[auto_qol_cand_3.GetName] ([auto_qol_cand_3.GetClass])"')
    loc.append(' auto_qol_assign.cand_4:0 "任命：[auto_qol_cand_4.GetName] ([auto_qol_cand_4.GetClass])"')

    loc.append(' auto_qol_council_assign.pick_desc:0 "选择一名可用领袖即可完成派驻；可用【换一批候选领袖】刷新名单。\\n\\n§Y原版界面未显示的席位可在本 Mod 的【在任名册】查看。§!"')
    loc.append(' auto_qol_assign.pick_desc:0 "选择一名可用领袖即可完成派驻；可用【换一批候选领袖】刷新名单。\\n\\n§Y原版界面未显示的席位可在本 Mod 的【在任名册】查看。§!"')

    loc.append(' auto_qol_council_assign.99.name:0 "内阁席位任命成功！"')
    loc.append(' auto_qol_council_assign.99.desc:0 "§G任命已顺利完成！§!\\n\\n领袖 §H[auto_qol_last_assigned.GetName]§! 已经正式履职，其岗位增益会在后台生效。未显示的额外席位可在【在任名册】查看。"')
    loc.append(' auto_qol_council_assign.success.continue:0 "继续指派其他席位"')
    loc.append(' auto_qol_council_assign.success.view_roster:0 "查看当前已任职内阁名册"')
    loc.append(' auto_qol_council_assign.success.close:0 "完成并关闭"')

    loc.append(' auto_qol_council_assign.90.name:0 "帝国政务内阁 · 现任领袖名册"')
    loc.append(' auto_qol_council_assign.90.desc:0 "以下为当前正在帝国政务内阁中实际任职的领袖名册（无论原版 UI 是否能全部塞下，均在此实效运转）："')
    for roster_index in range(1, ROSTER_PAGE_SIZE + 1):
        loc.append(
            f' auto_qol_assign.roster_{roster_index}:0 "在任领袖：[auto_qol_in_office_{roster_index}.GetName] ([auto_qol_in_office_{roster_index}.GetClass])"'
        )
    loc.append(' auto_qol_assign.roster_refresh:0 "【换一批现任领袖】"')
    loc.append(' auto_qol_council_assign.next_page:0 "下一页席位"')
    loc.append(' auto_qol_council_assign.prev_page:0 "上一页席位"')

    for cat in categories:
        cid = cat["cat_id"]
        ctag = cat["cat_tag"]
        positions = cat["positions"]
        pages = [positions[i:i + PAGE_SIZE] for i in range(0, len(positions), PAGE_SIZE)] or [[]]
        loc.append(f' auto_qol_council_assign.cat_{ctag}:0 "{cat["cat_name"]}"')
        for page_index, page_positions in enumerate(pages):
            event_id = cid if page_index == 0 else cid + page_index
            page_suffix = "" if len(pages) == 1 else f" ({page_index + 1}/{len(pages)})"
            loc.append(f' auto_qol_council_assign.{event_id}.name:0 "{cat["cat_name"]}{page_suffix}"')
            loc.append(f' auto_qol_council_assign.{event_id}.desc:0 "{cat["cat_desc"]}\\n\\n§Y{seat_visibility_desc}§!"')
        for pos in positions:
            pos_key = pos["key"]
            pos_title = pos["title"]
            pos_desc = pos.get("desc", "")
            clean_title = pos_title.replace('"', "'")
            clean_desc = pos_desc.replace('"', "'")
            loc.append(f' auto_qol_council_assign.{pos_key}.btn:0 "派驻：{clean_title}"')
            loc.append(f' auto_qol_council_assign.{pos_key}.tt:0 "§H{clean_title}§!\\n{clean_desc}\\n\\n§G点击挑选领袖并派驻上任§!"')
            loc.append(f' auto_qol_council_assign.{pos_key}.pick_name:0 "任命席位：{clean_title}"')

    return "\n".join(loc)

def split_event_content_by_category(event_content, categories):
    root_ids = {1, 90, 98, 99, 999}
    category_ids = {cat["cat_tag"]: set() for cat in categories}

    for cat in categories:
        tag = cat["cat_tag"]
        cid = cat["cat_id"]
        pages = [cat["positions"][i:i + PAGE_SIZE] for i in range(0, len(cat["positions"]), PAGE_SIZE)] or [[]]
        for page_index in range(len(pages)):
            category_ids[tag].add(cid if page_index == 0 else cid + page_index)
        for pos in cat["positions"]:
            category_ids[tag].add(pos["id"])

    chunks_by_file = {
        "auto_qol_council_assign_root_events.txt": [],
        "auto_qol_council_assign_scientist_events.txt": [],
        "auto_qol_council_assign_commander_events.txt": [],
        "auto_qol_council_assign_official_events.txt": [],
        "auto_qol_council_assign_multi_events.txt": [],
    }

    cursor = event_content.find("country_event = {")
    while cursor >= 0:
        open_index = event_content.find("{", cursor)
        close_index = find_matching_brace(event_content, open_index)
        if close_index < 0:
            raise ValueError("Could not split generated events: unmatched country_event block")

        chunk_start = cursor
        marker = event_content.rfind("# ========================================================", 0, cursor)
        previous_close = event_content.rfind("\n}", 0, cursor)
        if marker > previous_close:
            chunk_start = marker

        chunk = event_content[chunk_start:close_index + 1].strip() + "\n"
        id_match = re.search(r'\bid\s*=\s*auto_qol_council_assign\.(\d+)', chunk)
        if not id_match:
            raise ValueError("Could not split generated events: country_event without auto_qol id")
        event_id = int(id_match.group(1))

        if event_id in root_ids:
            target = "auto_qol_council_assign_root_events.txt"
        else:
            target = None
            for tag, ids in category_ids.items():
                if event_id in ids:
                    target = f"auto_qol_council_assign_{tag}_events.txt"
                    break
            if target is None:
                raise ValueError(f"Could not split generated events: unknown event id {event_id}")

        chunks_by_file[target].append(chunk)
        cursor = event_content.find("country_event = {", close_index + 1)

    return {
        filename: "namespace = auto_qol_council_assign\n\n" + "\n".join(chunks)
        for filename, chunks in chunks_by_file.items()
    }

def main():
    print("1. Resolving active mods from dlc_load.json...")
    active_mod_dirs = get_active_mod_dirs()
    print(f"Resolved {len(active_mod_dirs)} active mod directories")

    print("2. Loading localization (Game + Active Mods)...")
    loc_dict = get_loc_dict(active_mod_dirs)
    print(f"Loaded {len(loc_dict)} localization keys")

    print("3. Scanning councilors from Game + Active Mods only...")
    positions = scan_all_positions(active_mod_dirs, loc_dict)
    print(f"Scanned {len(positions)} valid councilors from active mods")

    print("3.5. Importing seat availability triggers from MORE COUNCIL POSITION...")
    more_triggers = collect_more_council_triggers()
    if not more_triggers:
        print("MORE COUNCIL POSITION not found or no triggers imported; using built-in councilor conditions only")
    positions = apply_more_council_triggers(positions, more_triggers)
    matched_more = sum(1 for p in positions if p.get("more_trigger"))
    print(f"Imported {len(more_triggers)} MORE COUNCIL triggers, matched {matched_more} active councilors")

    print("4. Organizing into 4 leader categories...")
    categories = organize_categories(positions)
    for cat in categories:
        tag = cat['cat_tag']
        num = len(cat['positions'])
        print(f"  - Category [{tag}]: {num} positions")

    print("5. Resolving active civic/origin/authority symbols...")
    defined_symbols = collect_defined_symbols(active_mod_dirs)
    print(f"Resolved {len(defined_symbols)} active government symbols")

    print("6. Generating clean event scripts (comment-safe scan, one-step council appointment)...")
    event_content = generate_events(categories, defined_symbols)
    event_files = split_event_content_by_category(event_content, categories)

    print("7. Generating localization (pure Chinese, 0 raw newlines, UTF-8 BOM)...")
    loc_content = generate_loc(categories)

    mod_events_dir = MOD_ROOT / "events"
    mod_loc_dir = MOD_ROOT / "localisation" / "simp_chinese"
    mod_events_dir.mkdir(parents=True, exist_ok=True)
    mod_loc_dir.mkdir(parents=True, exist_ok=True)

    legacy_event_file = mod_events_dir / "auto_qol_council_assign_events.txt"
    loc_file = mod_loc_dir / "auto_qol_council_assign_l_simp_chinese.yml"

    if legacy_event_file.exists():
        legacy_event_file.unlink()
        print(f"Removed legacy monolithic event file: {legacy_event_file}")
    for filename, content in event_files.items():
        event_file = mod_events_dir / filename
        clean_content = "\n".join(line.rstrip() for line in content.splitlines()) + "\n"
        event_file.write_text(clean_content, encoding="utf-8")
        print(f"Updated {event_file}")
    loc_file.write_text("l_simp_chinese:\n" + loc_content + "\n", encoding="utf-8-sig")
    print(f"Updated {loc_file}")

    print("8. Generating safe multi-row council UI compatibility layer...")
    ui_source, ui_file = generate_council_ui_compat(active_mod_dirs)
    print(f"Generated {ui_file} from {ui_source}")

    release_dir = MOD_ROOT.parent / "Stellaris Mod Enhancer"
    if release_dir.exists():
        rel_events_dir = release_dir / "events"
        rel_loc_dir = release_dir / "localisation" / "simp_chinese"
        rel_events_dir.mkdir(parents=True, exist_ok=True)
        rel_loc_dir.mkdir(parents=True, exist_ok=True)

        legacy_release_event_file = rel_events_dir / "auto_qol_council_assign_events.txt"
        if legacy_release_event_file.exists():
            legacy_release_event_file.unlink()
            print(f"Removed legacy release event file: {legacy_release_event_file}")
        for filename in event_files:
            shutil.copy2(mod_events_dir / filename, rel_events_dir / filename)
        shutil.copy2(loc_file, rel_loc_dir / "auto_qol_council_assign_l_simp_chinese.yml")
        rel_interface_dir = release_dir / "interface"
        rel_interface_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ui_file, rel_interface_dir / "council_view.gui")
        print(f"Synced to release directory: {release_dir}")

    print("\n[SUCCESS] Clean council system generated successfully!")

if __name__ == "__main__":
    main()

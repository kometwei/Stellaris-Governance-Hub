"""Build a curated, one-stage vanilla megastructure office.

Source definitions are read at build time; no vanilla or third-party GUI is
overridden. Unknown/branched transitions are deliberately not inferred.
"""
from pathlib import Path
import hashlib
import json
import re

from paths import GAME_INSTALL_DIR
from build_smart_council_system import find_matching_brace
from native_dashboard_footer import top_blocks, body, transform_events, transform_gui
from build_council_gui import dashboard_shell, DASHBOARD_LIST_Y, DASHBOARD_LIST_HEIGHT
from build_military_gui import text_box

ROOT = Path(__file__).resolve().parents[1]
PREFIX = "auto_qol_mega"
# Explicit construction edges, never weapon activation, repair, hidden special
# rewards, or the science-nexus event-only fourth stage.
FAMILIES = (
    ("dyson_sphere", "戴森球", [(f"dyson_sphere_{i}", f"dyson_sphere_{i+1}") for i in range(4)]),
    ("think_tank", "科学枢纽", [(f"think_tank_{i}", f"think_tank_{i+1}") for i in range(3)]),
    ("spy_orb", "哨兵阵列", [(f"spy_orb_{i}", f"spy_orb_{i+1}") for i in range(4)]),
    ("matter_decompressor", "物质解压器", [(f"matter_decompressor_{i}", f"matter_decompressor_{i+1}") for i in range(4)]),
    ("strategic_coordination_center", "战略指挥中心", [(f"strategic_coordination_center_{i}", f"strategic_coordination_center_{i+1}") for i in range(3)]),
    ("mega_art_installation", "巨型艺术设施", [(f"mega_art_installation_{i}", f"mega_art_installation_{i+1}") for i in range(3)]),
    ("interstellar_assembly", "星际集会", [(f"interstellar_assembly_{i}", f"interstellar_assembly_{i+1}") for i in range(4)]),
    ("mega_shipyard", "巨型船坞", [(f"mega_shipyard_{i}", f"mega_shipyard_{i+1}") for i in range(3)]),
    ("quantum_catapult", "量子弹弓", [(f"quantum_catapult_{i}", f"quantum_catapult_{i+1}") for i in range(3)]),
    ("orbital_arc_furnace", "电弧熔炉", [(f"orbital_arc_furnace_{i}", f"orbital_arc_furnace_{i+1}") for i in range(1, 4)]),
    ("dyson_swarm", "戴森云", [(f"dyson_swarm_{i}", f"dyson_swarm_{i+1}") for i in range(1, 3)]),
    ("ring_world", "环世界", [("ring_world_1", "ring_world_2_intermediate"), ("ring_world_2", "ring_world_3_intermediate")]),
)


def field(block, key, default=""):
    """Read only a top-level scalar/list field, including bare-token lists."""
    pattern = re.compile(r'\b' + re.escape(key) + r'\s*=\s*')
    match = pattern.search(block)
    while match:
        before = block[:match.start()]
        if before.count("{") - before.count("}") == 1:
            start = match.end()
            if block[start] == "{":
                return block[start + 1:find_matching_brace(block, start)].strip()
            return re.match(r'"[^"\n]*"|[^\s{}]+', block[start:])[0].strip('"')
        match = pattern.search(block, match.end())
    return default


def load_definitions(game=GAME_INSTALL_DIR):
    definitions, origins, variables = {}, {}, {}
    for path in sorted((Path(game) / "common/scripted_variables").glob("*.txt")):
        variables.update(re.findall(r'(@\w+)\s*=\s*(-?[\d.]+)', path.read_text(encoding="utf-8-sig")))
    for path in sorted((Path(game) / "common/megastructures").glob("*.txt")):
        text = re.sub(r'#[^\n]*', '', path.read_text(encoding="utf-8-sig"))
        local_vars = dict(variables)
        local_vars.update(re.findall(r'(@\w+)\s*=\s*(-?[\d.]+)', text))
        cursor = 0
        while match := re.search(r'(?m)^\s*(\w+)\s*=\s*\{', text[cursor:]):
            start = cursor + match.start()
            opening = text.index("{", start)
            end = find_matching_brace(text, opening)
            if end < 0:
                raise ValueError(f"Unbalanced source: {path}")
            block = text[start:end + 1]
            block = re.sub(r'@\w+', lambda m: local_vars.get(m[0], m[0]), block)
            definitions[match[1]] = block
            origins[match[1]] = path
            cursor = end + 1
    return definitions, origins


RESOURCES = ("alloys", "unity", "food", "energy", "minerals", "minor_artifacts")


def var(action, name, value):
    return f'{action}_variable = {{ which = aqm_{name} value = {value} }}\n'


def override_symbols(active_dirs):
    result = set()
    for directory in active_dirs:
        for path in (Path(directory) / "common/megastructures").glob("*.txt"):
            text = re.sub(r'#[^\n]*', '', path.read_text(encoding="utf-8-sig"))
            result.update(re.findall(r'(?m)^\s*(\w+)\s*=\s*\{', text))
    return result


def curated_edges(definitions, overridden=()):
    edges, skipped = [], []
    for index, (family, title, pairs) in enumerate(FAMILIES, 1):
        for source, target in pairs:
            if source not in definitions or target not in definitions:
                raise ValueError(f"Missing reviewed vanilla stage: {source} -> {target}")
            block = definitions[target]
            successors = [key for key, value in definitions.items()
                          if source in field(value, "upgrade_from").split()]
            if successors != [target] or source in overridden or target in overridden:
                skipped.append((source, target))
                continue
            if field(block, "upgrade_desc") == "hide" or float(field(block, "build_time", "0")) <= 0:
                raise ValueError(f"Not an ordinary construction stage: {target}")
            edges.append((index, source, target, block))
    return edges, skipped


def remap_conditions(text, context):
    # Source potential/possible scopes are documented in the game's README.
    # Event ROOT stays the acting country throughout our synchronous operation.
    mapping = {"fromfrom": "event_target:aqm_structure",
               "from": "root" if context == "system" else "event_target:aqm_structure",
               "root": "event_target:aqm_system" if context == "system" else "root"}
    if re.search(r'\b(?:prev|fromfromfrom)\b', text, re.I):
        raise ValueError("Unreviewed relative scope in megastructure requirement")
    return re.sub(r'\b(fromfrom|from|root)\b', lambda m: mapping[m[0]], text)


def requirements(block):
    text = 'is_upgrading = no\ncan_be_upgraded = yes\nowner = { is_same_value = root }\n'
    country = remap_conditions(field(block, "potential"), "country")
    country += '\n' + '\n'.join('has_technology = ' + tech for tech in
                                re.findall(r'"([^"\n]+)"', field(block, "prerequisites")))
    if country.strip():
        text += 'root = { ' + country + ' }\n'
    possible = remap_conditions(field(block, "possible"), "system")
    if possible:
        text += 'solar_system = { ' + possible + ' }\n'
    return text


def cost_script(block):
    """Compile every conditional cost block, preserving duplicates and multipliers."""
    resources = next(top_blocks(block, "resources"), None)
    if resources is None or field(resources, "category") != "megastructures":
        raise ValueError("Unreviewed economic category")
    result = ''.join(var("set", "cost_" + resource, 0) for resource in RESOURCES)
    for cost in top_blocks(resources, "cost"):
        trigger = next(top_blocks(cost, "trigger"), None)
        plain = body(cost).replace(trigger, "") if trigger else body(cost)
        values = re.findall(r'(\w+)\s*=\s*(-?[\d.]+)', plain)
        if re.sub(r'(\w+)\s*=\s*(-?[\d.]+)', '', plain).strip():
            raise ValueError("Unsupported dynamic source cost: " + plain)
        multiplier = float(dict(values).get("mult", "1"))
        additions = ''
        for resource, amount in values:
            if resource == "mult":
                continue
            if resource not in RESOURCES:
                raise ValueError("Unsupported cost resource: " + resource)
            additions += var("change", "cost_" + resource, f'{float(amount) * multiplier:g}')
        result += ('if = { limit = { ' + body(trigger) + ' }\n' + additions + '}\n') if trigger else additions
    result += 'set_country_flag = aqm_price_supported\n'
    for resource in RESOURCES:
        # Economic parent/category and generic/resource modifiers are additive.
        result += var("set", "factor", 1)
        for modifier in ("country_cost_mult", f"country_{resource}_cost_mult",
                         "megastructures_cost_mult", f"megastructures_{resource}_cost_mult"):
            result += f'export_modifier_to_variable = {{ modifier = {modifier} variable = aqm_modifier }}\n'
            result += var("change", "factor", "aqm_modifier")
        # Extreme discounts can hit engine-specific cost floors. Fail closed
        # rather than guess a price below the reviewed -90% boundary.
        result += f'''if = {{
 limit = {{ check_variable = {{ which = aqm_cost_{resource} value > 0 }} check_variable = {{ which = aqm_factor value < 0.1 }} }}
 remove_country_flag = aqm_price_supported
}}
'''
        result += var("multiply", "cost_" + resource, "aqm_factor")
    return result


def generate(root=ROOT, game=GAME_INSTALL_DIR, active_dirs=()):
    definitions, origins = load_definitions(game)
    edges, skipped = curated_edges(definitions, override_symbols(active_dirs))
    base = re.search(r'\bMEGASTRUCTURE_BUILD_CAP_BASE\s*=\s*([\d.]+)',
                     (Path(game) / 'common/defines/00_defines.txt').read_text(encoding="utf-8-sig"))[1]
    # Honor playset cap overrides at build time, without changing any Defines.
    for directory in active_dirs:
        for path in sorted((Path(directory) / 'common/defines').glob('*.txt')):
            values = re.findall(r'\bMEGASTRUCTURE_BUILD_CAP_BASE\s*=\s*([\d.]+)',
                                re.sub(r'#[^\n]*', '', path.read_text(encoding="utf-8-sig")))
            if values:
                base = values[-1]
    # Any unknown Mod construction is conservatively counted against the cap.
    nonblocking = [key for key, block in definitions.items()
                   if field(block, 'construction_blocks_and_blocked_by', 'multi_stage_type') != 'multi_stage_type']
    cap_limit = 'NOR = { ' + ' '.join('is_megastructure_type = ' + key for key in nonblocking) + ' }'
    init = ''.join(var("set", name, 0) for name in ("found", "ready", "failed", "used", "price_skipped"))
    init += f'export_modifier_to_variable = {{ modifier = country_megastructure_build_cap_add variable = aqm_cap }}\n'
    init += var("change", "cap", base)
    init += 'floor_variable = aqm_cap\n'
    init += 'every_owned_megastructure = { limit = { is_upgrading = yes ' + cap_limit + ' } root = { ' + var("change", "used", 1) + ' } }\n'
    for resource in RESOURCES:
        init += f'export_resource_stockpile_to_variable = {{ resource = {resource} variable = aqm_budget_{resource} }}\n'
        init += var("set", "total_" + resource, 0)

    effects = '# Generated; country ROOT, synchronous, player-only.\n'
    # One dispatcher branch per existing object: even if the engine changes its
    # type immediately, an object can never pass through a second edge this run.
    dispatch = ''
    for number, (family_index, source, target, block) in enumerate(edges):
        selected = f'root = {{ OR = {{ check_variable = {{ which = aqm_family value = 0 }} check_variable = {{ which = aqm_family value = {family_index} }} }} }}'
        condition = 'is_megastructure_type = ' + source + '\n' + selected
        setup = 'save_event_target_as = aqm_structure\nsolar_system = { save_event_target_as = aqm_system }\n'
        setup += 'root = { ' + var("change", "found", 1) + ' }\n'
        pricing = 'root = { ' + cost_script(block) + '\nif = { limit = { NOT = { has_country_flag = aqm_price_supported } } ' + var('change', 'price_skipped', 1) + ' }\n }\n'
        is_multi = field(block, 'construction_blocks_and_blocked_by', 'multi_stage_type') == 'multi_stage_type'
        enough = 'root = { has_country_flag = aqm_price_supported\n'
        if is_multi:
            enough += 'check_variable = { which = aqm_used value < aqm_cap }\n'
        enough += ''.join(f'check_variable = {{ which = aqm_budget_{r} value >= aqm_cost_{r} }}\n' for r in RESOURCES) + '}\n'
        booked = var("change", "ready", 1)
        if is_multi:
            booked += var("change", "used", 1)
        for resource in RESOURCES:
            booked += var("subtract", "budget_" + resource, 'aqm_cost_' + resource)
            booked += var("change", "total_" + resource, 'aqm_cost_' + resource)
        # Only supplement costs after the native effect actually starts work.
        # Snapshot deltas prevent double charging if native behavior differs.
        snapshot = ''.join(f'export_resource_stockpile_to_variable = {{ resource = {r} variable = aqm_before_{r} }}\n' for r in RESOURCES)
        charge = ''
        for resource in RESOURCES:
            charge += f'export_resource_stockpile_to_variable = {{ resource = {resource} variable = aqm_after }}\n'
            charge += var("set", "paid", f'aqm_before_{resource}') + var("subtract", "paid", 'aqm_after')
            charge += var("set", "due", f'aqm_cost_{resource}') + var("subtract", "due", 'aqm_paid')
            charge += 'if = { limit = { check_variable = { which = aqm_due value > 0 } }\n'
            charge += f'add_resource = {{ {resource} = -1 mult = aqm_due }}\n}}\n'
        charge += booked
        # Refresh real budgets after each transaction; never use stale preview
        # balances to charge several objects in the same execution batch.
        charge += ''.join(f'export_resource_stockpile_to_variable = {{ resource = {r} variable = aqm_budget_{r} }}\n' for r in RESOURCES)
        execute = 'root = { ' + snapshot + ' }\n'
        execute += f'upgrade_megastructure_to = {target}\n'
        execute += 'if = { limit = { is_upgrading = yes } root = { ' + charge + ' } }\n'
        execute += 'else = { root = { ' + var("change", "failed", 1) + ' } }\n'
        work = 'if = { limit = { root = { has_country_flag = aqm_execute } }\n' + execute + '}\n'
        work += 'else = { root = { ' + booked + ' } }\n'
        dispatch += ('if' if number == 0 else 'else_if') + ' = { limit = { ' + condition + ' }\n' + setup
        dispatch += 'if = { limit = { ' + requirements(block) + ' }\n' + pricing
        dispatch += 'if = { limit = { ' + enough + ' }\n' + work + '}\n}\n}\n'
    effects += 'auto_qol_mega_scan = {\n if = { limit = { is_ai = no }\n' + init
    effects += 'every_owned_megastructure = {\n' + dispatch + '}\n'
    effects += 'remove_country_flag = aqm_price_supported\nremove_country_flag = aqm_execute\n}\n}\n'

    def option(name, effect, trigger=''):
        return f' option = {{ name = "{PREFIX}_{name}"\n custom_tooltip = "{PREFIX}_rules_tt"\n' + (f' trigger = {{ {trigger} }}\n' if trigger else '') + ' hidden_effect = { ' + effect + ' }\n }\n'

    def event(number, desc, immediate, options):
        return f'''country_event = {{
 id = {PREFIX}.{number}
 diplomatic = yes
 custom_gui = "{PREFIX}_window"
 custom_gui_option = "{PREFIX}_option"
 title = "{PREFIX}_title"
 desc = "{PREFIX}_{desc}"
 is_triggered_only = yes
 trigger = {{ is_ai = no }}
 immediate = {{ {immediate} }}
{options}
}}
'''

    options = option('all', var('set', 'family', 0) + f'country_event = {{ id = {PREFIX}.2 }}')
    loc = {
        'title': '星政中枢 · 巨构工程署',
        'note': '选择类型，预览后批量启动下一建设阶段。',
        'footer': '只处理自有普通巨构；每次每座至多升一级。星际大炮、特殊分支、废墟修复不参与。',
        'home': '返回星政中枢首页', 'close': '关闭面板（Esc）',
        'prev': '← 上一页', 'next': '下一页 →',
        'intro': '选择本批巨构类型。\\n\\n遵循资源、科技、阶段条件与并行施工额度。费用按构建时的原版定义和当前帝国成本修正计算。\\n\\n正在施工、特殊阶段和条件不足者跳过。不会新建巨构、立即完工或自动续建。成本降至原价 10% 以下的项目暂不代办。',
        'all': '全部支持类型：扫描并预览',
        'confirm': '确认：按当前资源批量启动下一阶段',
        'refresh': '重新扫描并预览', 'back': '重新选择巨构类型',
        'preview': '本批匹配 §Y[Root.aqm_found]§! 座建设阶段（含正在施工者）。\\n可开工 §G[Root.aqm_ready]§! 座（已考虑当前资源和并行额度）。\\n极端费用折扣跳过：[Root.aqm_price_skipped] 座。\\n\\n预计合计消耗：\\n£alloys£ [Root.aqm_total_alloys]　£unity£ [Root.aqm_total_unity]\\n£food£ [Root.aqm_total_food]　£energy£ [Root.aqm_total_energy]\\n£minerals£ [Root.aqm_total_minerals]　£minor_artifacts£ [Root.aqm_total_minor_artifacts]\\n\\n确认时重新检查；不足者跳过，遍历顺序由游戏决定。预览不扣资源、不下达命令。',
        'result': '本次成功启动 §G[Root.aqm_ready]§! 座，原生启动未成功 §Y[Root.aqm_failed]§! 座。\\n命中总数：[Root.aqm_found]；其余因资源、额度或条件不足跳过。\\n\\n成功启动项目的计算费用：\\n£alloys£ [Root.aqm_total_alloys]　£unity£ [Root.aqm_total_unity]\\n£food£ [Root.aqm_total_food]　£energy£ [Root.aqm_total_energy]\\n\\n已进入正常施工，不自动连续升级。',
    }
    loc['rules_tt'] = loc['footer'] + '\\n\\n' + loc['intro']
    loc['intro'] = '选择巨构类型。'
    for index, (family, title, _) in enumerate(FAMILIES, 1):
        options += option(family, var('set', 'family', index) + f'country_event = {{ id = {PREFIX}.2 }}')
        loc[family] = title + '：扫描并预览'
    script = 'namespace = ' + PREFIX + '\n'
    script += event(1, 'intro', '', options)
    back = option('back', f'country_event = {{ id = {PREFIX}.1 }}')
    refresh = option('refresh', f'country_event = {{ id = {PREFIX}.2 }}')
    script += event(2, 'preview', 'remove_country_flag = aqm_execute\nauto_qol_mega_scan = yes',
                    option('confirm', 'set_country_flag = aqm_execute\nauto_qol_mega_scan = yes\n' + f'country_event = {{ id = {PREFIX}.3 }}',
                           'check_variable = { which = aqm_ready value > 0 }') + refresh + back)
    script += event(3, 'result', '', refresh + back)
    content = text_box('mega_header', PREFIX + '_title', 22, 15, 930, 30, 'malgun_goth_24')
    shell = dashboard_shell(PREFIX).replace('maxHeight = 230', 'maxHeight = 450').replace('@CONTENT@', content)
    report = {'families': len(FAMILIES), 'edges': [[i, s, t] for i, s, t, _ in edges],
              'excluded_overrides_or_branches': skipped, 'base_build_cap': float(base),
              'sources': {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                          for path in sorted({origins[t] for _, _, t, _ in edges})}}
    return {
        'common/scripted_effects/auto_qol_megastructure_effects.txt': effects,
        'events/auto_qol_megastructure_gui_events.txt': transform_events(script, PREFIX, PREFIX + '_page'),
        'interface/auto_qol_megastructure.gui': transform_gui(shell, PREFIX, DASHBOARD_LIST_Y, DASHBOARD_LIST_HEIGHT),
        'localisation/simp_chinese/auto_qol_megastructure_l_simp_chinese.yml': 'l_simp_chinese:\n' + ''.join(f' {PREFIX}_{k}:0 "{v}"\n' for k, v in loc.items()),
        'megastructure-office-build.json': json.dumps(report, ensure_ascii=False, indent=2) + '\n',
    }


def build(root=ROOT, game=GAME_INSTALL_DIR, active_dirs=()):
    root = Path(root)
    for relative, content in generate(root, game, active_dirs).items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding='utf-8-sig' if path.suffix == '.yml' else 'utf-8')


if __name__ == '__main__':
    build()
    print('Generated vanilla megastructure office: preview and one-stage batch construction.')

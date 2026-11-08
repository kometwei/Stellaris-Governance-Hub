"""Generate a guarded, selected-starbase facility clearing workflow.

No slot counts, level changes, queues, resources, or replacement facilities are
written. Catalog counts are used to reject unknown facilities before removal.
"""
from pathlib import Path
import json
import re

from paths import GAME_INSTALL_DIR
from build_megastructure_office import field
from build_smart_council_system import find_matching_brace
from build_council_gui import dashboard_shell, DASHBOARD_LIST_Y, DASHBOARD_LIST_HEIGHT
from build_military_gui import text_box
from native_dashboard_footer import transform_events, transform_gui

ROOT = Path(__file__).resolve().parents[1]
PREFIX = 'auto_qol_starbase_clear'
PAGE_SIZE = 10
COUNT_LIMIT = 1024
SIZES = ('starbase_starport', 'starbase_starhold', 'starbase_starfortress', 'starbase_citadel')
FOLDERS = ('starbase_modules', 'starbase_buildings')
SHIPYARDS = ('shipyard', 'beastport', 'orbital_ring_shipyard', 'orbital_ring_beastport', 'arkship_beastport')


def hard_protection(block):
    return bool(field(block, 'empire_limit') or field(block, 'replaceable') or
                field(block, 'destroy_trigger') or
                re.search(r'\bstarbase_(module|building)_capacity_add\b', block) or
                re.search(r'\balways\s*=\s*no\b', field(block, 'potential')))


def forceable(folder, key, block):
    return bool((folder == 'starbase_modules' and key in SHIPYARDS) or
                re.search(r'\bstarbase_defense_platform_capacity_(add|mult)\b', block))


def catalog(directory, folder):
    result = {}
    inline_root = (Path(directory) / 'common/inline_scripts').resolve()

    def read_blocks(raw, stack=()):
        text = re.sub(r'#[^\n]*', '', raw)
        cursor = 0
        while match := re.search(r'(?m)^\s*(\w+)\s*=\s*\{', text[cursor:]):
            start = cursor + match.start()
            opening = text.index('{', start)
            end = find_matching_brace(text, opening)
            if end < 0:
                raise ValueError('Unbalanced facility definition')
            block = text[start:end + 1]
            if match[1] == 'inline_script':
                script = field(block, 'script')
                path = (inline_root / (script + '.txt')).resolve()
                if not script or inline_root not in path.parents or not path.is_file() or path in stack:
                    raise ValueError('Cannot resolve top-level facility inline_script: ' + script)
                expanded = path.read_text(encoding='utf-8-sig')
                for key, value in re.findall(r'(\w+)\s*=\s*("[^"\n]*"|[^\s{}]+)', block):
                    if key != 'script':
                        expanded = expanded.replace('$' + key + '$', value.strip('"'))
                # A missing top-level identifier parameter must not accidentally
                # turn a nested field into a facility definition.
                if re.search(r'(?m)^\s*[^\s{}=]*\$[^\n=]*=', expanded):
                    raise ValueError('Unresolved facility inline-script identifier: ' + script)
                read_blocks(expanded, (*stack, path))
            else:
                result[match[1]] = block
            cursor = end + 1

    for path in sorted((Path(directory) / 'common' / folder).glob('*.txt')):
        read_blocks(path.read_text(encoding='utf-8-sig'))
    return result


def reviewed_catalog(game=GAME_INSTALL_DIR, active_dirs=()):
    known, protected, excluded = {}, {}, {}
    for folder in FOLDERS:
        definitions = catalog(game, folder)
        excluded[folder] = set()
        for directory in active_dirs:
            excluded[folder].update(catalog(directory, folder))
            descriptor = Path(directory) / 'descriptor.mod'
            if descriptor.exists():
                text = re.sub(r'#[^\n]*', '', descriptor.read_text(encoding='utf-8-sig'))
                replacements = re.findall(r'\breplace_path\s*=\s*"([^"]+)"', text)
                if any(('common/' + folder).startswith(value.replace('\\', '/').rstrip('/')) for value in replacements):
                    excluded[folder].update(definitions)
        known[folder] = sorted(set(definitions) - excluded[folder])
        # Explicit limits are protected even if their current dynamic value
        # might be unlimited. Do not bypass custom removal/capacity behavior.
        protected[folder] = [key for key in known[folder] if
                             hard_protection(definitions[key]) or forceable(folder, key, definitions[key])]
    return known, protected, excluded


def variable(action, name, value):
    return f'{action}_variable = {{ which = aqsc_{name} value = {value} }}\n'


def count_facilities(kind, variable_name, include=False, facility=None):
    count = f'count_starbase_{kind} = {{ ' + (f'type = {facility} ' if facility else '')
    count += f'include_being_constructed = {"yes" if include else "no"} count > aqsc_{variable_name} }}'
    # Use documented count comparisons instead of assuming that a generic
    # trigger export understands count_* parameters. Bounds fail closed.
    return variable('set', variable_name, 0) + f'''while = {{
 limit = {{ check_variable = {{ which = aqsc_{variable_name} value < {COUNT_LIMIT} }} {count} }}
 {variable('change', variable_name, 1)}
}}
'''


def generate(root=ROOT, game=GAME_INSTALL_DIR, active_dirs=()):
    known, protected, excluded = reviewed_catalog(game, active_dirs)
    normal = 'OR = { ' + ' '.join('has_starbase_size = ' + size for size in SIZES) + ' }'
    triggers = f'{PREFIX}_normal = {{ {normal} }}\n'
    hard_checks, force_checks = [], []
    force_catalog = {}
    for folder in FOLDERS:
        definitions = catalog(game, folder)
        force_catalog[folder] = []
        for key in protected[folder]:
            check = f'has_starbase_{"module" if folder == FOLDERS[0] else "building"} = {key}'
            if hard_protection(definitions[key]):
                hard_checks.append(check)
            else:
                force_checks.append(check)
                force_catalog[folder].append(key)
    triggers += f'{PREFIX}_protected = {{ OR = {{\n'
    triggers += '\n'.join(hard_checks) + '\n'
    if force_checks:
        triggers += 'AND = { root = { NOT = { has_country_flag = aqsc_force } } OR = { ' + ' '.join(force_checks) + ' } }\n'
    if not hard_checks and not force_checks:
        triggers += 'always = no\n'
    triggers += '} }\n'
    # Native untyped counts can retain empty slots; reject Mod definitions
    # explicitly instead of treating every unrecognized slot as a facility.
    unknown_checks = []
    for folder in FOLDERS:
        mod_keys = set()
        for directory in active_dirs:
            mod_keys.update(catalog(directory, folder))
        singular = 'module' if folder == FOLDERS[0] else 'building'
        for key in sorted(mod_keys - set(known[folder])):
            unknown_checks += [f'has_starbase_{singular} = {key}', f'is_starbase_building_{singular} = {key}']
    triggers += f'{PREFIX}_unknown = {{ ' + ('OR = { ' + ' '.join(unknown_checks) + ' }' if unknown_checks else 'always = no') + ' }\n'

    measure = ''
    for kind in ('modules', 'buildings'):
        measure += count_facilities(kind, kind)
        measure += count_facilities(kind, kind + '_queued', True)
        measure += variable('set', 'known_' + kind, 0)
        measure += variable('set', 'known_' + kind + '_queued', 0)
        for key in known['starbase_' + kind]:
            measure += count_facilities(kind, 'type_count', facility=key)
            measure += variable('change', 'known_' + kind, 'aqsc_type_count')
            measure += count_facilities(kind, 'type_count_queued', include=True, facility=key)
            measure += variable('change', 'known_' + kind + '_queued', 'aqsc_type_count_queued')
        measure += 'root = { ' + variable('set', kind, f'prev.aqsc_known_{kind}')
        measure += variable('set', 'untyped_' + kind, f'prev.aqsc_{kind}')
        measure += variable('set', 'known_' + kind, f'prev.aqsc_known_{kind}')
        measure += variable('set', 'queued_' + kind, f'prev.aqsc_known_{kind}_queued') + ' }\n'
    # Audit never removes anything; all operations run it again immediately
    # before applying either remover. The other facility category protects the
    # whole station even for a modules-only/buildings-only request.
    audit = f'''{PREFIX}_audit = {{
 remove_country_flag = aqsc_ready
 {variable('set', 'reason', 1)}
 {variable('set', 'modules', 0)}
 {variable('set', 'buildings', 0)}
 if = {{
  limit = {{ exists = event_target:aqsc_selected event_target:aqsc_selected = {{ is_scope_type = starbase }} }}
  event_target:aqsc_selected = {{
   {measure}
   root = {{ {variable('set', 'reason', 0)} }}
   if = {{ limit = {{ OR = {{
    {PREFIX}_unknown = yes
    check_variable = {{ which = aqsc_known_modules value >= {COUNT_LIMIT} }}
    check_variable = {{ which = aqsc_known_buildings value >= {COUNT_LIMIT} }}
    check_variable = {{ which = aqsc_known_modules_queued value >= {COUNT_LIMIT} }}
    check_variable = {{ which = aqsc_known_buildings_queued value >= {COUNT_LIMIT} }}
    check_variable = {{ which = aqsc_modules value >= {COUNT_LIMIT} }}
    check_variable = {{ which = aqsc_buildings value >= {COUNT_LIMIT} }}
   }} }} root = {{ {variable('set', 'reason', 5)} }} }}
   if = {{ limit = {{ {PREFIX}_protected = yes }} root = {{ {variable('set', 'reason', 4)} }} }}
   if = {{ limit = {{ OR = {{
    fleet = {{ is_upgrading = yes }}
    NOT = {{ check_variable = {{ which = aqsc_known_modules value = aqsc_known_modules_queued }} }}
    NOT = {{ check_variable = {{ which = aqsc_known_buildings value = aqsc_known_buildings_queued }} }}
    check_variable = {{ which = aqsc_modules_queued value >= {COUNT_LIMIT} }}
    check_variable = {{ which = aqsc_buildings_queued value >= {COUNT_LIMIT} }}
   }} }} root = {{ {variable('set', 'reason', 3)} }} }}
   if = {{ limit = {{ OR = {{
    NOT = {{ {PREFIX}_normal = yes }}
    NOT = {{ owner = {{ is_same_value = root }} }}
    NOT = {{ controller = {{ is_same_value = root }} }}
    NOT = {{ exists = fleet }}
    fleet = {{ is_in_combat = yes }}
   }} }} root = {{ {variable('set', 'reason', 2)} }} }}
  }}
 }}
 if = {{ limit = {{ is_ai = no check_variable = {{ which = aqsc_reason value = 0 }} }} set_country_flag = aqsc_ready }}
 log = "AQSC AUDIT version=0.2.5 mode=\\\\[This.aqsc_mode] reason=\\\\[This.aqsc_reason] modules=\\\\[This.aqsc_modules] untyped_modules=\\\\[This.aqsc_untyped_modules] including_queued_modules=\\\\[This.aqsc_queued_modules] buildings=\\\\[This.aqsc_buildings] untyped_buildings=\\\\[This.aqsc_untyped_buildings] including_queued_buildings=\\\\[This.aqsc_queued_buildings]"
}}
'''
    effects = '# Generated; ROOT must be the acting player country.\n' + audit
    # The game's espionage_event_effects uses explicit module/building types.
    # Bound repetitions by the measured installed count: supports native
    # removal of one or all matching copies without relying on an empty block.
    for kind, singular in (('modules', 'module'),):
        effects += f'{PREFIX}_remove_{kind} = {{\n'
        effects += f'log = "AQSC REMOVE_BEGIN version=0.2.5 category={kind}"\n'
        for key in known['starbase_' + kind]:
            effects += f'if = {{ limit = {{ has_starbase_{singular} = {key} }}\n'
            effects += count_facilities(kind, 'remove_count', facility=key)
            removal = f'remove_starbase_module = {{ module = {key} }}'
            effects += f'while = {{ count = aqsc_remove_count\n if = {{ limit = {{ has_starbase_{singular} = {key} }} {removal} }}\n}}\n'
            effects += count_facilities(kind, 'type_after', facility=key)
            effects += 'root = { ' + variable('set', 'last_before', 'prev.aqsc_remove_count') + variable('set', 'last_after', 'prev.aqsc_type_after')
            effects += f'log = "AQSC REMOVE_TYPE version=0.2.5 category={kind} type={key} before=\\\\[This.aqsc_last_before] after=\\\\[This.aqsc_last_after]"\n}}\n}}\n'
        effects += '}\n'
    # Literal slot arguments follow 01_start_of_game_effects. Do not assume a
    # fixed four-slot base: only issue slots <= this target's audited count.
    # Keep slots in descending order, also safe if removal compacts a vector.
    effects += f'{PREFIX}_remove_buildings = {{\nlog = "AQSC REMOVE_BEGIN version=0.2.5 category=buildings method=slot"\n'
    for slot in reversed(range(1, COUNT_LIMIT)):
        effects += f'if = {{ limit = {{ check_variable = {{ which = aqsc_buildings value >= {slot} }} }} remove_starbase_building = {{ slot = {slot} }} log = "AQSC REMOVE_SLOT version=0.2.5 slot={slot}" }}\n'
    effects += '}\n'
    effects += f'''{PREFIX}_execute = {{
 remove_country_flag = aqsc_done
 {PREFIX}_audit = yes
 if = {{ limit = {{ is_ai = no has_country_flag = aqsc_ready
  OR = {{ check_variable = {{ which = aqsc_mode value = 1 }} check_variable = {{ which = aqsc_mode value = 2 }} check_variable = {{ which = aqsc_mode value = 3 }} }}
 }}
 event_target:aqsc_selected = {{
  if = {{ limit = {{ root = {{ OR = {{ check_variable = {{ which = aqsc_mode value = 1 }} check_variable = {{ which = aqsc_mode value = 3 }} }} }} }} {PREFIX}_remove_modules = yes }}
  if = {{ limit = {{ root = {{ OR = {{ check_variable = {{ which = aqsc_mode value = 2 }} check_variable = {{ which = aqsc_mode value = 3 }} }} }} }} {PREFIX}_remove_buildings = yes }}
 }}
 {PREFIX}_audit = yes
 if = {{ limit = {{ has_country_flag = aqsc_ready OR = {{
  AND = {{ check_variable = {{ which = aqsc_mode value = 1 }} check_variable = {{ which = aqsc_modules value = 0 }} }}
  AND = {{ check_variable = {{ which = aqsc_mode value = 2 }} check_variable = {{ which = aqsc_buildings value = 0 }} }}
  AND = {{ check_variable = {{ which = aqsc_mode value = 3 }} check_variable = {{ which = aqsc_modules value = 0 }} check_variable = {{ which = aqsc_buildings value = 0 }} }}
 }} }} set_country_flag = aqsc_done }}
 }}
}}
{PREFIX}_reset = {{
 remove_country_flag = aqsc_force
 every_owned_starbase = {{ remove_starbase_flag = aqsc_seen@root }}
}}
{PREFIX}_prepare = {{
'''
    for index in range(1, PAGE_SIZE + 1):
        effects += f'''remove_country_flag = aqsc_slot_{index}_valid
 random_owned_starbase = {{
  limit = {{ {PREFIX}_normal = yes NOT = {{ has_starbase_flag = aqsc_seen@root }} }}
  set_starbase_flag = aqsc_seen@root
  save_event_target_as = aqsc_slot_{index}
  root = {{ set_country_flag = aqsc_slot_{index}_valid }}
 }}
'''
    effects += '}\n'

    loc = {
        'title': '星政中枢 · 恒星基地清空', 'note': '先选择基地，再选择清空范围；操作前会再次检查保护条件。',
        'footer': '即时移除、不退款。强拆仅放宽防御容量设施及船坞／兽坞保护；换基地或重新进入时默认关闭。',
        'home': '返回星政中枢首页', 'close': '关闭面板（Esc）', 'prev': '← 上一页', 'next': '下一页 →',
        'picker': '选择一座自有普通恒星基地。每批最多十座，本轮不重复。\\n\\n选择后显示模块、建筑数量及是否允许清空。受保护基地可查看，但不能执行清空。',
        'more': '下一批基地', 'restart': '从头浏览基地', 'empty': '暂无其他普通基地，重新扫描',
        'choose': '重新选择基地', 'refresh': '刷新基地状态', 'modules': '清空全部模块…', 'buildings': '清空全部建筑…', 'both': '清空模块和建筑…',
        'confirm': '确认立即清空所选范围', 'cancel': '取消，返回基地详情',
        'force_on': '【强拆已开启】点击关闭',
        'force_off': '【强拆已关闭】允许拆除容量设施及船坞／兽坞',
        'detail': '目标：§Y[aqsc_selected.GetName]§!\\n现有模块：[Root.aqsc_modules]\\n现有建筑：[Root.aqsc_buildings]\\n\\n只有通过保护检查才显示清空选项。',
        'confirm_modules': '目标：§Y[aqsc_selected.GetName]§!\\n\\n即将移除该基地全部 §R[Root.aqsc_modules]§! 个模块，保留建筑。\\n\\n即时执行，不退还资源。基地等级与槽位配置不变。',
        'confirm_buildings': '目标：§Y[aqsc_selected.GetName]§!\\n\\n即将移除该基地全部 §R[Root.aqsc_buildings]§! 个建筑，保留模块。\\n\\n即时执行，不退还资源。基地等级与槽位配置不变。',
        'confirm_both': '目标：§Y[aqsc_selected.GetName]§!\\n\\n即将移除全部 §R[Root.aqsc_modules]§! 个模块和 §R[Root.aqsc_buildings]§! 个建筑。\\n\\n即时执行，不退还资源。基地等级与槽位配置不变。',
        'success': '已清空所选范围。\\n\\n目标：[aqsc_selected.GetName]\\n剩余模块：[Root.aqsc_modules]\\n剩余建筑：[Root.aqsc_buildings]\\n\\n未调整基地等级、槽位配置或资源。',
        'failed': '本次未能确认清空成功。基地条件可能已变化，或原生移除效果未达到目标；请返回详情刷新检查。',
        'reason_1': '目标已失效，请重新选择基地。',
        'reason_2': '已跳过：目标不是支持的自有普通基地、处于占领或交战状态。',
        'reason_3': '已跳过：检测到模块／建筑施工或排队，或基地正在升级。',
        'reason_4': '已跳过：含受保护设施。\\n\\n强拆开关仅放宽防御平台容量设施和船坞／兽坞；全国限量、特殊移除条件、隐藏设施及额外模块／建筑槽位设施仍然保留。',
        'reason_5': '已跳过：检测到本次播放集中的未适配／被 Mod 改写设施，或数量超过检查上限。\\n\\n已识别模块：[Root.aqsc_modules]\\n已识别建筑：[Root.aqsc_buildings]\\n\\n更改设施 Mod 后请重新生成本地版。',
    }
    loc['rules_tt'] = loc['footer'] + '\\n\\n' + loc['picker']
    loc['picker'] = '选择恒星基地。'
    loc['detail'] = loc['detail'].split('\\n\\n')[0]
    loc['force_off'] = '【已关闭】强拆'
    loc['force_on'] = '§R【已开启】强拆§!'
    loc['detail_force'] = loc['detail'] + '\\n\\n§R强拆已开启§!：允许拆除防御容量设施及船坞／兽坞，可能导致容量超限或影响造舰。'
    for key in ('modules', 'buildings', 'both'):
        loc['confirm_' + key + '_force'] = loc['confirm_' + key] + '\\n\\n§R强拆已开启：可能降低平台／离子炮容量或影响现有造舰订单。§! 本功能不主动拆除舰船、平台或取消订单；引擎后续处理尚待实测。'

    def option(key, effect, trigger=''):
        return f'option = {{ name = "{PREFIX}_{key}"\n custom_tooltip = "{PREFIX}_rules_tt"\n' + (f'trigger = {{ {trigger} }}\n' if trigger else '') + 'hidden_effect = { ' + effect + ' }\n}\n'

    def reason_desc():
        return ''.join(f'desc = {{ trigger = {{ check_variable = {{ which = aqsc_reason value = {n} }} }} text = "{PREFIX}_reason_{n}" }}\n' for n in range(1, 6))

    def event(number, desc, immediate, choices):
        return f'''country_event = {{
 id = {PREFIX}.{number}
 diplomatic = yes
 custom_gui = "{PREFIX}_window"
 custom_gui_option = "{PREFIX}_option"
 title = "{PREFIX}_title"
 {desc}
 is_triggered_only = yes
 trigger = {{ is_ai = no }}
 immediate = {{ {immediate} }}
 {choices}
}}
'''

    script = f'''namespace = {PREFIX}
country_event = {{
 id = {PREFIX}.1
 hide_window = yes
 is_triggered_only = yes
 trigger = {{ is_ai = no }}
 immediate = {{ {PREFIX}_reset = yes country_event = {{ id = {PREFIX}.10 }} }}
}}
'''
    choices = ''
    for index in range(1, PAGE_SIZE + 1):
        loc[f'slot_{index}'] = f'[aqsc_slot_{index}.GetName]'
        choices += option(f'slot_{index}', f'remove_country_flag = aqsc_force event_target:aqsc_slot_{index} = {{ save_event_target_as = aqsc_selected }} country_event = {{ id = {PREFIX}.2 }}',
                          f'has_country_flag = aqsc_slot_{index}_valid exists = event_target:aqsc_slot_{index}')
    unseen = f'any_owned_starbase = {{ {PREFIX}_normal = yes NOT = {{ has_starbase_flag = aqsc_seen@root }} }}'
    choices += option('more', f'country_event = {{ id = {PREFIX}.10 }}', unseen)
    choices += option('restart', f'country_event = {{ id = {PREFIX}.1 }}', f'NOT = {{ {unseen} }} has_country_flag = aqsc_slot_1_valid')
    choices += option('empty', f'country_event = {{ id = {PREFIX}.1 }}', 'NOT = { has_country_flag = aqsc_slot_1_valid }')
    script += event(10, f'desc = "{PREFIX}_picker"', f'{PREFIX}_prepare = yes', choices)
    back = option('choose', f'country_event = {{ id = {PREFIX}.1 }}')
    refresh = option('refresh', f'country_event = {{ id = {PREFIX}.2 }}')
    choices = ''
    for mode, key, condition in ((1, 'modules', 'aqsc_modules'), (2, 'buildings', 'aqsc_buildings'), (3, 'both', None)):
        condition = f'check_variable = {{ which = {condition} value > 0 }}' if condition else 'OR = { check_variable = { which = aqsc_modules value > 0 } check_variable = { which = aqsc_buildings value > 0 } }'
        choices += option(key, variable('set', 'mode', mode) + f'country_event = {{ id = {PREFIX}.3 }}', 'has_country_flag = aqsc_ready ' + condition)
    choices += option('force_off', f'set_country_flag = aqsc_force country_event = {{ id = {PREFIX}.2 }}', 'NOT = { has_country_flag = aqsc_force }')
    choices += option('force_on', f'remove_country_flag = aqsc_force country_event = {{ id = {PREFIX}.2 }}', 'has_country_flag = aqsc_force')
    detail = f'desc = {{ trigger = {{ check_variable = {{ which = aqsc_reason value = 0 }} NOT = {{ has_country_flag = aqsc_force }} }} text = "{PREFIX}_detail" }}\n'
    detail += f'desc = {{ trigger = {{ check_variable = {{ which = aqsc_reason value = 0 }} has_country_flag = aqsc_force }} text = "{PREFIX}_detail_force" }}\n' + reason_desc()
    script += event(2, detail, f'{PREFIX}_audit = yes', choices + refresh + back)
    confirmation = ''
    for n, key in ((1, 'modules'), (2, 'buildings'), (3, 'both')):
        for forced in (False, True):
            condition = 'has_country_flag = aqsc_force' if forced else 'NOT = { has_country_flag = aqsc_force }'
            suffix = '_force' if forced else ''
            confirmation += f'desc = {{ trigger = {{ has_country_flag = aqsc_ready check_variable = {{ which = aqsc_mode value = {n} }} {condition} }} text = "{PREFIX}_confirm_{key}{suffix}" }}\n'
    script += event(3, confirmation + reason_desc(), f'{PREFIX}_audit = yes',
                    option('confirm', f'{PREFIX}_execute = yes country_event = {{ id = {PREFIX}.4 }}', 'has_country_flag = aqsc_ready') + option('cancel', f'country_event = {{ id = {PREFIX}.2 }}'))
    result_desc = f'desc = {{ trigger = {{ has_country_flag = aqsc_done }} text = "{PREFIX}_success" }}\ndesc = {{ trigger = {{ NOT = {{ has_country_flag = aqsc_done }} }} text = "{PREFIX}_failed" }}'
    script += event(4, result_desc, '', refresh + back)
    content = text_box('clear_header', PREFIX + '_title', 22, 15, 930, 30, 'malgun_goth_24')
    shell = dashboard_shell(PREFIX).replace('maxHeight = 230', 'maxHeight = 450').replace('@CONTENT@', content)
    report = {'version': '0.2.5', 'known': known, 'protected': protected, 'forceable': force_catalog, 'excluded_mod_overrides': {k: sorted(v) for k, v in excluded.items()},
              'normal_ship_sizes': SIZES, 'count_limit': COUNT_LIMIT}
    return {
        'common/scripted_effects/auto_qol_starbase_clear_effects.txt': effects,
        'common/scripted_triggers/auto_qol_starbase_clear_triggers.txt': triggers,
        'events/auto_qol_starbase_clear_gui_events.txt': transform_events(script, PREFIX, PREFIX + '_page'),
        'interface/auto_qol_starbase_clear.gui': transform_gui(shell, PREFIX, DASHBOARD_LIST_Y, DASHBOARD_LIST_HEIGHT),
        'localisation/simp_chinese/auto_qol_starbase_clear_l_simp_chinese.yml': 'l_simp_chinese:\n' + ''.join(f' {PREFIX}_{k}:0 "{v}"\n' for k, v in loc.items()),
        'starbase-clear-build.json': json.dumps(report, ensure_ascii=False, indent=2) + '\n',
    }


def build(root=ROOT, game=GAME_INSTALL_DIR, active_dirs=()):
    for relative, content in generate(root, game, active_dirs).items():
        path = Path(root) / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding='utf-8-sig' if path.suffix == '.yml' else 'utf-8')


if __name__ == '__main__':
    build()
    print('Generated selected-starbase facility clearing workflow.')

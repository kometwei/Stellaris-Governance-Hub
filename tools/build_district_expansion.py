"""Build the free, permanent per-planet district expansion menu."""
from pathlib import Path
from build_council_gui import dashboard_shell
from build_military_gui import text_box

ROOT = Path(__file__).resolve().parents[1]
PREFIX = 'auto_qol_district_expansion'
TIERS = (1, 3, 5, 10, 30)


def build(root=ROOT):
    root = Path(root)
    files = {}
    files[f'common/decisions/{PREFIX}.txt'] = f'''{PREFIX} = {{
    owned_planets_only = yes
    enactment_time = 0
    potential = {{ is_colony = yes owner = {{ is_ai = no }} }}
    allow = {{ is_colony = yes owner = {{ is_ai = no }} }}
    effect = {{ planet_event = {{ id = {PREFIX}.1 }} }}
    ai_weight = {{ weight = 0 }}
}}
'''
    # Unsupported district types remain unavailable: no district definitions,
    # district sets or potential triggers are overridden.
    files[f'common/static_modifiers/{PREFIX}.txt'] = f'''{PREFIX}_bonus = {{
    planet_max_districts_add = 1
    district_mining_max_add = 1
    district_generator_max_add = 1
    district_farming_max_add = 1
}}
'''
    guard = f'''is_colony = yes
                exists = event_target:{PREFIX}_actor
                is_owned_by = event_target:{PREFIX}_actor
                owner = {{ is_ai = no }}'''
    events = f'''namespace = {PREFIX}
planet_event = {{
    id = {PREFIX}.1
    diplomatic = yes
    custom_gui = "{PREFIX}_window"
    custom_gui_option = "{PREFIX}_option"
    title = "{PREFIX}.title"
    desc = "{PREFIX}.desc"
    picture = GFX_evt_galactic_senate
    is_triggered_only = yes
    trigger = {{ is_colony = yes owner = {{ is_ai = no }} }}
    immediate = {{
        owner = {{ save_event_target_as = {PREFIX}_actor }}
        if = {{
            limit = {{ NOT = {{ is_variable_set = {PREFIX}_total }} }}
            set_variable = {{ which = {PREFIX}_total value = 0 }}
        }}
    }}
'''
    loc = {
        PREFIX: '区划扩容',
        PREFIX + '_desc': '打开本星球的区划扩容菜单，选择需要增加的区划容量。',
        PREFIX + '.title': '[Root.GetName]：区划扩容',
        PREFIX + '.desc': f'§H本星球累计扩容§!\\n§G＋[Root.{PREFIX}_total]§! £district£\\n\\n§H同步提升§!\\n总区划容量\\n£minerals£ 采矿区划上限\\n£energy£ 发电区划上限\\n£food£ 农业区划上限\\n\\n§L各类区划共享总容量。\\n仅原本允许的区划可建造。§!',
        PREFIX + '_bonus': '永久区划扩容',
        PREFIX + '_bonus_desc': '本工具提供的总区划容量与采矿、发电、农业上限加成。',
        PREFIX + '.close': '完成扩容 · 关闭',
        PREFIX + '_header': '星政中枢  /  行星工程',
        PREFIX + '_note': '区划扩容',
        PREFIX + '_footer': '选择右侧档位增加区划容量。各类区划仍共享总容量。',
    }
    for tier in TIERS:
        key = f'{PREFIX}.add_{tier}'
        label = {1: '精细调整', 3: '小幅扩建', 5: '常规扩建', 10: '大规模扩建', 30: '全面扩建'}[tier]
        loc[key] = f'§G＋{tier}§!    {label}'
        loc[key + '_tt'] = f'总区划容量 +{tier}；采矿、发电、农业区划上限各 +{tier}。仅原本允许的区划可建造；重复选择继续累加，无法撤销。'
        events += f'''    option = {{
        name = "{key}"
        custom_tooltip = "{key}_tt"
        allow = {{ {guard} }}
        hidden_effect = {{
            if = {{
                limit = {{ {guard} }}
                change_variable = {{ which = {PREFIX}_total value = {tier} }}
                remove_modifier = {PREFIX}_bonus
                add_modifier = {{ modifier = {PREFIX}_bonus days = -1 mult = {PREFIX}_total }}
                planet_event = {{ id = {PREFIX}.1 }}
            }}
        }}
    }}
'''
    # Native X/Esc resolve the event's default hide option; a GUI close control
    # alone is insufficient. Keep this option free of effects and reopening.
    events += f'    option = {{ name = "{PREFIX}.close" default_hide_option = yes }}\n}}\n'
    files[f'events/{PREFIX}_events.txt'] = events
    # Reuse the established native event shell and its required controls.
    # Every action remains a native event option, so each click consumes the
    # previous event before reopening; no effectButton spawns visible windows.
    shell = dashboard_shell(PREFIX).replace('maxHeight = 230', 'maxHeight = 450')
    shell = shell.replace('width = 630 height = 34', 'width = 630 height = 60')
    shell = shell.replace('size = { x = 630 y = 32 }', 'size = { x = 630 y = 48 }')
    shell = shell.replace('spacing = 2', 'spacing = 4')
    content = text_box('expansion_header', PREFIX + '_header', 22, 15, 930, 34, 'malgun_goth_24')
    content += text_box('expansion_note', PREFIX + '_note', 22, 66, 980, 30)
    content += text_box('expansion_footer', PREFIX + '_footer', 22, 624, 980, 60)
    files[f'interface/{PREFIX}.gui'] = shell.replace('@CONTENT@', content)
    files[f'localisation/simp_chinese/{PREFIX}_l_simp_chinese.yml'] = 'l_simp_chinese:\n' + ''.join(f' {key}:0 "{value}"\n' for key, value in loc.items())
    for relative, content in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding='utf-8-sig' if path.suffix == '.yml' else 'utf-8')
    return files


if __name__ == '__main__':
    build()

"""Strict execution/scope model for generated clearing guards and selection.

Does not replace testing native removal and construction-count semantics in game.
"""
import operator
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import build_starbase_clear as builder
from test_megastructure_office import parse, get


def base(modules=('anchorage',), buildings=('resource_silo',), **changes):
    result = dict(kind='starbase', size='starbase_citadel', vars={}, flags=set(),
                  modules=list(modules), buildings=list(buildings), queued_modules=[], queued_buildings=[],
                  fleet=dict(kind='fleet', upgrading=False, combat=False), foreign=False, occupied=False,
                  grade=4, module_slots=12, building_slots=8)
    result.update(changes)
    return result


class Runtime:
    def __init__(self, files, bases=(), ai=False):
        self.country = dict(kind='country', vars={}, flags=set(), ai=ai)
        self.foreign = dict(kind='country', vars={}, flags=set(), ai=True)
        self.bases = list(bases)
        for station in self.bases:
            if 'building_positions' not in station:
                station['building_positions'] = dict(enumerate(station['buildings'], 1))
        self.targets = {}
        self.effects = dict((k, v) for k, _, v in parse(files['common/scripted_effects/auto_qol_starbase_clear_effects.txt']))
        self.triggers = dict((k, v) for k, _, v in parse(files['common/scripted_triggers/auto_qol_starbase_clear_triggers.txt']))
        self.removals, self.events = [], []
        self.native_fail = False
        self.native_remove_all = False
        self.native_refuse = set()

    def number(self, text, current, previous=None):
        try:
            return float(text)
        except ValueError:
            if text.startswith('prev.'):
                assert previous is not None
                return previous.get('vars', {}).get(text[5:], 0)
            return current.get('vars', {}).get(text, 0)

    def scope(self, key, current):
        if key == 'root':
            return self.country
        if key == 'owner':
            return self.foreign if current.get('foreign') else self.country
        if key == 'controller':
            return self.foreign if current.get('foreign') or current.get('occupied') else self.country
        if key == 'fleet':
            return current.get('fleet')
        if key.startswith('event_target:'):
            return self.targets.get(key.split(':')[1])
        raise AssertionError('Unknown scope ' + key)

    def condition(self, rows, current, previous=None):
        for key, comparison, value in rows:
            if key in ('OR', 'NOR', 'NOT'):
                valid = any(self.condition([row], current, previous) for row in value)
                if key != 'OR':
                    valid = not valid
            elif key == 'AND':
                valid = self.condition(value, current, previous)
            elif key in ('root', 'owner', 'controller', 'fleet') or key.startswith('event_target:'):
                target = self.scope(key, current)
                valid = target is not None and self.condition(value, target, current)
            elif key == 'check_variable':
                left = current['vars'].get(get(value, 'which'), 0)
                _, comparison, right = next(row for row in value if row[0] == 'value')
                valid = self.compare(left, comparison, self.number(right, current, previous))
            elif key in ('count_starbase_modules', 'count_starbase_buildings'):
                assert current['kind'] == 'starbase', key
                kind = key.removeprefix('count_starbase_')
                kind_filter = next((v for k, _, v in value if k == 'type'), None)
                items = list(current[kind])
                if get(value, 'include_being_constructed') == 'yes':
                    items += current['queued_' + kind]
                count = sum(item == kind_filter for item in items) if kind_filter else current['module_slots' if kind == 'modules' else 'building_slots']
                _, comparison, expected = next(row for row in value if row[0] == 'count')
                valid = self.compare(count, comparison, self.number(expected, current, previous))
            elif key in ('has_starbase_module', 'has_starbase_building'):
                assert current['kind'] == 'starbase'
                valid = value in current['modules' if key.endswith('module') else 'buildings']
            elif key in ('is_starbase_building_module', 'is_starbase_building_building'):
                valid = value in current['queued_modules' if key.endswith('module') else 'queued_buildings']
            elif key == 'has_starbase_size':
                assert current['kind'] == 'starbase'
                valid = current['size'] == value
            elif key == 'is_same_value':
                valid = current is self.country
            elif key == 'is_scope_type':
                valid = current['kind'] == value
            elif key == 'exists':
                valid = self.scope(value, current) is not None
            elif key == 'is_ai':
                assert current['kind'] == 'country'
                valid = current['ai'] == (value == 'yes')
            elif key in ('is_upgrading', 'is_in_combat'):
                assert current['kind'] == 'fleet', 'Use fleet scope for ' + key
                valid = current['upgrading' if key == 'is_upgrading' else 'combat'] == (value == 'yes')
            elif key in ('has_country_flag', 'has_starbase_flag'):
                valid = value in current['flags']
            elif key == 'any_owned_starbase':
                valid = any(self.condition(value, target, current) for target in self.bases if not target['foreign'])
            elif key in self.triggers:
                valid = self.condition(self.triggers[key], current, previous) == (value == 'yes')
            elif key == 'always':
                valid = value == 'yes'
            else:
                raise AssertionError('Unknown condition ' + key)
            if not valid:
                return False
        return True

    @staticmethod
    def compare(left, comparison, right):
        return {'=': operator.eq, '>': operator.gt, '<': operator.lt,
                '>=': operator.ge, '<=': operator.le}[comparison](left, right)

    def run(self, rows, current=None, previous=None):
        current = self.country if current is None else current
        branch = None
        for key, _, value in rows:
            if key in ('if', 'else_if', 'else'):
                if key == 'if':
                    branch = False
                if not branch and (key == 'else' or self.condition(get(value, 'limit'), current, previous)):
                    self.run([row for row in value if row[0] != 'limit'], current, previous)
                    branch = True
                continue
            branch = None
            if key == 'while':
                if any(k == 'count' for k, _, _ in value):
                    count = int(self.number(get(value, 'count'), current, previous))
                    assert 0 <= count <= builder.COUNT_LIMIT
                    for _ in range(count):
                        self.run([row for row in value if row[0] != 'count'], current, previous)
                    continue
                iterations = 0
                while self.condition(get(value, 'limit'), current, previous):
                    self.run([row for row in value if row[0] != 'limit'], current, previous)
                    iterations += 1
                    assert iterations <= builder.COUNT_LIMIT
            elif key in ('root', 'owner', 'controller', 'fleet') or key.startswith('event_target:'):
                target = self.scope(key, current)
                if target is not None:
                    self.run(value, target, current)
            elif key in ('set_variable', 'change_variable'):
                name = get(value, 'which')
                amount = self.number(get(value, 'value'), current, previous)
                current['vars'][name] = amount if key == 'set_variable' else current['vars'].get(name, 0) + amount
            elif key in ('set_country_flag', 'remove_country_flag', 'set_starbase_flag', 'remove_starbase_flag'):
                assert current['kind'] == ('country' if 'country' in key else 'starbase')
                (current['flags'].add if key.startswith('set') else current['flags'].discard)(value)
            elif key == 'save_event_target_as':
                self.targets[value] = current
            elif key in ('random_owned_starbase', 'every_owned_starbase'):
                assert current is self.country
                guard = next((v for k, _, v in value if k == 'limit'), [])
                matches = [b for b in self.bases if not b['foreign'] and self.condition(guard, b, current)]
                for target in matches[:1] if key.startswith('random') else matches:
                    self.run([row for row in value if row[0] != 'limit'], target, current)
            elif key in ('remove_starbase_module', 'remove_starbase_building'):
                assert current['kind'] == 'starbase' and not current['foreign'] and not current['occupied']
                kind = 'modules' if key.endswith('module') else 'buildings'
                singular = 'module' if kind == 'modules' else 'building'
                if kind == 'buildings':
                    slot = int(get(value, 'slot'))
                    assert 1 <= slot <= current['building_slots']
                    facility = current['building_positions'].get(slot)
                    self.removals.append((self.bases.index(current), kind))
                    if not self.native_fail and facility not in self.native_refuse:
                        current['building_positions'].pop(slot, None)
                        current['buildings'] = list(current['building_positions'].values())
                    continue
                assert len(value) == 1 and value[0][0] == singular, 'Require an explicit facility type'
                facility = get(value, singular)
                self.removals.append((self.bases.index(current), kind))
                if not self.native_fail and facility not in self.native_refuse:
                    if self.native_remove_all:
                        current[kind] = [item for item in current[kind] if item != facility]
                    elif facility in current[kind]:
                        current[kind].remove(facility)
            elif key == 'remove_random_starbase_building':
                assert current['kind'] == 'starbase' and not current['foreign'] and not current['occupied']
                self.assert_building_filter(value)
                facility = get(value, 'type')
                self.removals.append((self.bases.index(current), 'buildings'))
                if not self.native_fail and facility not in self.native_refuse and facility in current['buildings']:
                    current['buildings'].remove(facility)
            elif key == 'country_event':
                self.events.append(get(value, 'id'))
            elif key == 'log':
                pass
            elif key in self.effects:
                self.run(self.effects[key], current, previous)
            else:
                raise AssertionError('Unknown effect ' + key)

    @staticmethod
    def assert_building_filter(rows):
        assert get(rows, 'count') == '1'
        assert get(rows, 'type') not in ('all', 'any', '')

    def audit(self, target=None):
        if target is not None:
            self.targets['aqsc_selected'] = target
        self.run(self.effects[builder.PREFIX + '_audit'])
        return 'aqsc_ready' in self.country['flags']

    def execute(self, mode):
        self.country['vars']['aqsc_mode'] = mode
        self.run(self.effects[builder.PREFIX + '_execute'])


class ClearingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod_fixture = TemporaryDirectory(dir=builder.ROOT / 'scratch')
        root = Path(cls.mod_fixture.name)
        for kind, keys in (('modules', ('mod_module', 'unknown_mod_module')), ('buildings', ('mod_building',))):
            folder = root / 'common' / ('starbase_' + kind)
            folder.mkdir(parents=True)
            (folder / 'test.txt').write_text('\n'.join(key + ' = { }' for key in keys), encoding='utf-8')
        cls.files = builder.generate(active_dirs=[root])

    @classmethod
    def tearDownClass(cls):
        cls.mod_fixture.cleanup()

    def runtime(self, *args, **kwargs):
        return Runtime(self.files, *args, **kwargs)

    def test_all_three_operations_preserve_grade_slots_and_other_base(self):
        for mode in (1, 2, 3):
            with self.subTest(mode=mode):
                selected = base(modules=('anchorage', 'anchorage', 'trading_hub'))
                other = base()
                runtime = self.runtime([selected, other])
                self.assertTrue(runtime.audit(selected))
                runtime.execute(mode)
                self.assertEqual(selected['modules'], [] if mode in (1, 3) else ['anchorage', 'anchorage', 'trading_hub'])
                self.assertEqual(selected['buildings'], [] if mode in (2, 3) else ['resource_silo'])
                self.assertEqual((selected['grade'], selected['module_slots'], selected['building_slots']), (4, 12, 8))
                self.assertEqual(other['modules'], ['anchorage'])
                self.assertEqual(other['buildings'], ['resource_silo'])
                self.assertIn('aqsc_done', runtime.country['flags'])

    def test_audit_never_removes_and_counts_duplicates(self):
        selected = base(modules=('anchorage',) * 20)
        runtime = self.runtime([selected])
        runtime.audit(selected)
        self.assertEqual(runtime.country['vars']['aqsc_modules'], 20)
        self.assertEqual(runtime.removals, [])

    def test_missing_destroyed_foreign_occupied_special_and_combat_targets(self):
        invalid = [base(foreign=True), base(occupied=True), base(size='starbase_outpost'),
                   base(size='mod_starbase'), base(fleet=dict(kind='fleet', upgrading=False, combat=True))]
        for selected in invalid:
            runtime = self.runtime([selected])
            self.assertFalse(runtime.audit(selected))
            runtime.execute(3)
            self.assertEqual(runtime.removals, [])
        runtime = self.runtime()
        self.assertFalse(runtime.audit())
        runtime.execute(3)
        self.assertEqual(runtime.removals, [])

    def test_each_construction_category_blocks_all_modes(self):
        cases = [base(queued_modules=['anchorage']), base(queued_buildings=['resource_silo']),
                 base(queued_modules=['unknown_mod_module']),
                 base(fleet=dict(kind='fleet', upgrading=True, combat=False))]
        for selected in cases:
            for mode in (1, 2, 3):
                runtime = self.runtime([selected])
                self.assertFalse(runtime.audit(selected))
                self.assertEqual(runtime.country['vars']['aqsc_reason'], 5 if 'unknown_mod_module' in selected['queued_modules'] else 3)
                runtime.execute(mode)
                self.assertEqual(runtime.removals, [])

    def test_unique_building_protects_whole_base_even_modules_only(self):
        for mode in (1, 2, 3):
            selected = base(buildings=('resource_silo', 'recruitment_office'))
            runtime = self.runtime([selected])
            self.assertFalse(runtime.audit(selected))
            runtime.execute(mode)
            self.assertEqual(runtime.removals, [])
            self.assertEqual(runtime.country['vars']['aqsc_reason'], 4)

    def test_unknown_mod_facility_in_either_category_protects_whole_base(self):
        for selected in (base(modules=('mod_module',)), base(buildings=('mod_building',))):
            runtime = self.runtime([selected])
            self.assertFalse(runtime.audit(selected))
            self.assertEqual(runtime.country['vars']['aqsc_reason'], 5)
            runtime.execute(1)
            self.assertEqual(runtime.removals, [])

    def test_guard_rechecks_selection_after_confirmation(self):
        for change in ('unique', 'queue', 'foreign', 'occupied', 'unknown', 'destroyed'):
            with self.subTest(change=change):
                selected = base()
                runtime = self.runtime([selected])
                self.assertTrue(runtime.audit(selected))
                if change == 'unique': selected['buildings'].append('recruitment_office')
                elif change == 'queue': selected['queued_modules'].append('anchorage')
                elif change == 'unknown': selected['modules'].append('mod_module')
                elif change == 'destroyed': runtime.targets.clear()
                else: selected[change] = True
                runtime.execute(3)
                self.assertEqual(runtime.removals, [])
                self.assertNotIn('aqsc_done', runtime.country['flags'])

    def test_shipyards_and_beastports_are_conservatively_protected(self):
        for kind in ('shipyard', 'beastport'):
            selected = base(modules=(kind,))
            runtime = self.runtime([selected])
            self.assertFalse(runtime.audit(selected))
            runtime.execute(3)
            self.assertEqual(runtime.removals, [])

    def test_defense_capacity_sources_protect_whole_base_for_every_mode(self):
        known, protected, _ = builder.reviewed_catalog()
        cases = []
        for folder, kind in (('starbase_modules', 'modules'), ('starbase_buildings', 'buildings')):
            definitions = builder.catalog(builder.GAME_INSTALL_DIR, folder)
            import re
            for key in known[folder]:
                if re.search(r'\bstarbase_defense_platform_capacity_(?:add|mult)\b', definitions[key]):
                    self.assertIn(key, protected[folder])
                    cases.append((kind, key))
        self.assertTrue(cases)
        for kind, key in cases:
            for mode in (1, 2, 3):
                with self.subTest(facility=key, mode=mode):
                    selected = base(**{kind: [key]})
                    runtime = self.runtime([selected])
                    self.assertFalse(runtime.audit(selected))
                    self.assertEqual(runtime.country['vars']['aqsc_reason'], 4)
                    runtime.execute(mode)
                    self.assertEqual(runtime.removals, [])

    def test_native_failure_is_not_reported_as_success(self):
        selected = base()
        runtime = self.runtime([selected])
        runtime.audit(selected)
        runtime.native_fail = True
        runtime.execute(3)
        self.assertNotIn('aqsc_done', runtime.country['flags'])

    def test_force_allows_shipyards_beastports_and_defense_capacity_sources(self):
        import json
        report = json.loads(self.files['starbase-clear-build.json'])
        cases = [(('modules' if folder == 'starbase_modules' else 'buildings'), key)
                 for folder, keys in report['forceable'].items() for key in keys]
        self.assertIn(('modules', 'shipyard'), cases)
        self.assertIn(('modules', 'beastport'), cases)
        for kind, key in cases:
            selected = base(**{kind: [key]})
            runtime = self.runtime([selected])
            self.assertFalse(runtime.audit(selected))
            runtime.country['flags'].add('aqsc_force')
            self.assertTrue(runtime.audit())
            runtime.execute(3)
            self.assertEqual((selected['modules'], selected['buildings']), ([], []))
            self.assertIn('aqsc_done', runtime.country['flags'])

    def test_force_does_not_bypass_unique_unknown_queue_owner_or_combat(self):
        cases = [base(buildings=('recruitment_office',)), base(modules=('mod_module',)),
                 base(queued_modules=['anchorage']), base(queued_buildings=['resource_silo']),
                 base(foreign=True), base(occupied=True), base(size='mod_base'),
                 base(fleet=dict(kind='fleet', upgrading=True, combat=False)),
                 base(fleet=dict(kind='fleet', upgrading=False, combat=True))]
        for selected in cases:
            runtime = self.runtime([selected])
            runtime.country['flags'].add('aqsc_force')
            self.assertFalse(runtime.audit(selected))
            runtime.execute(3)
            self.assertEqual(runtime.removals, [])

    def test_disabling_force_before_execution_reinstates_protection(self):
        selected = base(modules=('shipyard',))
        runtime = self.runtime([selected])
        runtime.country['flags'].add('aqsc_force')
        self.assertTrue(runtime.audit(selected))
        runtime.country['flags'].discard('aqsc_force')
        runtime.execute(3)
        self.assertEqual(runtime.removals, [])

    def test_force_resets_on_restart_and_target_change(self):
        runtime = self.runtime([base()])
        runtime.country['flags'].add('aqsc_force')
        runtime.run(runtime.effects[builder.PREFIX + '_reset'])
        self.assertNotIn('aqsc_force', runtime.country['flags'])
        events = parse(self.files['events/auto_qol_starbase_clear_gui_events.txt'])
        for _, _, event in (row for row in events if row[0] == 'country_event'):
            for key, _, choice in event:
                if key == 'option' and get(choice, 'name').startswith(builder.PREFIX + '_slot_'):
                    hidden = get(choice, 'hidden_effect')
                    self.assertEqual(hidden[0], ('remove_country_flag', '=', 'aqsc_force'))

    def test_repeated_execution_is_idempotent_and_invalid_mode_does_nothing(self):
        selected = base()
        runtime = self.runtime([selected])
        runtime.audit(selected)
        runtime.execute(99)
        self.assertEqual(runtime.removals, [])
        runtime.execute(3)
        runtime.execute(3)
        self.assertEqual((selected['modules'], selected['buildings']), ([], []))

    def test_ai_cannot_clear(self):
        selected = base()
        runtime = self.runtime([selected], ai=True)
        self.assertFalse(runtime.audit(selected))
        runtime.execute(3)
        self.assertEqual(runtime.removals, [])

    def test_bounded_counts_fail_closed(self):
        selected = base(modules=('anchorage',) * builder.COUNT_LIMIT)
        runtime = self.runtime([selected])
        self.assertFalse(runtime.audit(selected))
        runtime.execute(3)
        self.assertEqual(runtime.removals, [])

    def test_picker_pages_do_not_repeat_and_reset_recovers_all(self):
        stations = [base() for _ in range(23)]
        runtime = self.runtime(stations)
        prepare = runtime.effects[builder.PREFIX + '_prepare']
        pages = []
        for _ in range(3):
            runtime.run(prepare)
            page = [id(runtime.targets[f'aqsc_slot_{n}']) for n in range(1, 11)
                    if f'aqsc_slot_{n}_valid' in runtime.country['flags']]
            pages.append(page)
        self.assertEqual(list(map(len, pages)), [10, 10, 3])
        flat = sum(pages, [])
        self.assertEqual(len(set(flat)), 23)
        runtime.run(runtime.effects[builder.PREFIX + '_reset'])
        runtime.run(prepare)
        self.assertEqual(id(runtime.targets['aqsc_slot_1']), id(stations[0]))

    def test_ten_bases_and_batch_navigation_share_one_native_page(self):
        events = {get(v, 'id'): v for k, _, v in parse(self.files['events/auto_qol_starbase_clear_gui_events.txt']) if k == 'country_event'}
        pages = [event for event in events.values() if any(k == 'option' and get(v, 'name') == builder.PREFIX + '_slot_10' for k, _, v in event)]
        self.assertEqual(len(pages), 1)
        names = {get(v, 'name') for k, _, v in pages[0] if k == 'option'}
        for suffix in ('more', 'restart', 'empty', 'home', 'close'):
            self.assertIn(builder.PREFIX + '_' + suffix, names)
        self.assertNotIn(builder.PREFIX + '_prev', names)
        self.assertNotIn(builder.PREFIX + '_next', names)
        self.assertEqual(sum(bool(__import__('re').fullmatch(builder.PREFIX + r'_slot_\d+', name)) for name in names), 10)

    def test_local_build_excludes_mod_overrides_and_replace_path(self):
        with TemporaryDirectory(dir=builder.ROOT / 'scratch') as directory:
            root = Path(directory)
            modules = root / 'common/starbase_modules'
            modules.mkdir(parents=True)
            (modules / 'override.txt').write_text('anchorage = { }\nmod_new = { }', encoding='utf-8')
            files = builder.generate(active_dirs=[root])
            runtime = Runtime(files, [base()])
            self.assertFalse(runtime.audit(runtime.bases[0]))
            self.assertEqual(runtime.country['vars']['aqsc_reason'], 5)
            (root / 'descriptor.mod').write_text('replace_path="common/starbase_buildings"', encoding='utf-8')
            known, _, _ = builder.reviewed_catalog(active_dirs=[root])
            self.assertEqual(known['starbase_buildings'], [])

    def test_native_navigation_localization_and_no_unrelated_mutations(self):
        effects = self.files['common/scripted_effects/auto_qol_starbase_clear_effects.txt']
        for forbidden in ('set_starbase_size', 'set_starbase_module', 'set_starbase_building',
                          'add_resource', 'set_resource', 'add_modifier', 'on_monthly', 'remove_all_ships'):
            self.assertNotIn(forbidden, effects)
        events = self.files['events/auto_qol_starbase_clear_gui_events.txt']
        self.assertIn('id = auto_qol_menu.1', events)
        self.assertIn('auto_qol_starbase_clear_confirm', events)
        gui = self.files['interface/auto_qol_starbase_clear.gui']
        self.assertIn('scrollbarType = "standardlistbox_slider"', gui)
        self.assertNotIn('effectButtonType', gui)
        self.assertNotIn('smoothListBoxType', gui)
        for key, _, event in parse(events):
            if key == 'country_event':
                self.assertEqual(get(event, 'trigger'), [('is_ai', '=', 'no')])

    def test_frontend_pick_cancel_and_confirm_execute_the_selected_target(self):
        stations = [base(), base(modules=('trading_hub',))]
        runtime = self.runtime(stations)
        events = {get(v, 'id'): v for k, _, v in parse(self.files['events/auto_qol_starbase_clear_gui_events.txt']) if k == 'country_event'}

        def enter(event_id):
            for _ in range(12):
                event = events[event_id]
                self.assertTrue(runtime.condition(get(event, 'trigger'), runtime.country))
                immediate = next((v for k, _, v in event if k == 'immediate'), [])
                runtime.run(immediate)
                if any(k == 'hide_window' and v == 'yes' for k, _, v in event):
                    event_id = runtime.events.pop()
                else:
                    return event
            self.fail('Event routing loop')

        def click(event, key):
            selected = next(v for k, _, v in event if k == 'option' and get(v, 'name') == builder.PREFIX + '_' + key)
            guard = next((v for k, _, v in selected if k == 'trigger'), [])
            self.assertTrue(runtime.condition(guard, runtime.country))
            runtime.run(get(selected, 'hidden_effect'))
            return enter(runtime.events.pop())

        picker = enter(builder.PREFIX + '.1')
        detail = click(picker, 'slot_2')
        self.assertIs(runtime.targets['aqsc_selected'], stations[1])
        confirmation = click(detail, 'both')
        self.assertEqual(runtime.removals, [])
        detail = click(confirmation, 'cancel')
        self.assertEqual(runtime.removals, [])
        confirmation = click(detail, 'modules')
        click(confirmation, 'confirm')
        self.assertEqual(stations[0]['modules'], ['anchorage'])
        self.assertEqual(stations[1]['modules'], [])
        self.assertEqual(stations[1]['buildings'], ['resource_silo'])
        self.assertIn('aqsc_done', runtime.country['flags'])
        detail = enter(builder.PREFIX + '.2')
        detail = click(detail, 'force_off')
        self.assertIn('aqsc_force', runtime.country['flags'])
        detail = click(detail, 'force_on')
        self.assertNotIn('aqsc_force', runtime.country['flags'])
        detail = click(detail, 'force_off')
        picker = click(detail, 'choose')
        self.assertNotIn('aqsc_force', runtime.country['flags'])

    def test_repeatable_build_and_single_bom(self):
        with TemporaryDirectory(dir=builder.ROOT / 'scratch') as directory:
            root = Path(directory)
            builder.build(root, active_dirs=[Path(self.mod_fixture.name)])
            first = {key: (root / key).read_bytes() for key in self.files}
            builder.build(root, active_dirs=[Path(self.mod_fixture.name)])
            self.assertEqual(first, {key: (root / key).read_bytes() for key in self.files})
            loc = first['localisation/simp_chinese/auto_qol_starbase_clear_l_simp_chinese.yml']
            self.assertTrue(loc.startswith(b'\xef\xbb\xbf'))
            self.assertFalse(loc.startswith(b'\xef\xbb\xbf' * 2))

    def test_inline_script_is_expanded_instead_of_becoming_a_facility(self):
        for folder, example in (('starbase_modules', 'waystation_voidlure_tiyanki'),
                                ('starbase_buildings', 'voidlure_tiyanki')):
            definitions = builder.catalog(builder.GAME_INSTALL_DIR, folder)
            self.assertNotIn('inline_script', definitions)
            self.assertIn(example, definitions)
        effects = self.files['common/scripted_effects/auto_qol_starbase_clear_effects.txt']
        self.assertNotIn('type = inline_script', effects)
        self.assertIn('type = voidlure_tiyanki', effects)

    def test_explicit_removal_supports_one_or_all_copies_per_native_call(self):
        for all_copies in (False, True):
            selected = base(modules=('anchorage',) * 6 + ('trading_hub',) * 2)
            runtime = self.runtime([selected])
            runtime.native_remove_all = all_copies
            runtime.audit(selected)
            runtime.execute(1)
            self.assertEqual(selected['modules'], [])
            self.assertEqual(selected['buildings'], ['resource_silo'])
            self.assertIn('aqsc_done', runtime.country['flags'])

    def test_clear_modules_then_buildings_with_empty_slots_not_unknown(self):
        selected = base(modules=('anchorage',) * 6, buildings=('resource_silo', 'crew_quarters'),
                        module_slots=6, building_slots=4)
        runtime = self.runtime([selected])
        self.assertTrue(runtime.audit(selected))
        runtime.execute(1)
        self.assertIn('aqsc_done', runtime.country['flags'])
        self.assertEqual((selected['modules'], selected['module_slots']), ([], 6))
        self.assertTrue(runtime.audit())
        self.assertEqual(runtime.country['vars']['aqsc_modules'], 0)
        runtime.execute(2)
        self.assertEqual((selected['buildings'], selected['building_slots']), ([], 4))
        self.assertIn('aqsc_done', runtime.country['flags'])

    def test_buildings_only_on_base_with_already_empty_modules(self):
        selected = base(modules=(), buildings=('resource_silo',), module_slots=6, building_slots=4)
        runtime = self.runtime([selected])
        self.assertTrue(runtime.audit(selected))
        runtime.execute(2)
        self.assertEqual(selected['buildings'], [])
        self.assertIn('aqsc_done', runtime.country['flags'])

    def test_native_shipyard_refusal_is_respected_under_force(self):
        selected = base(modules=('shipyard', 'anchorage'))
        runtime = self.runtime([selected])
        runtime.country['flags'].add('aqsc_force')
        runtime.native_refuse.add('shipyard')
        self.assertTrue(runtime.audit(selected))
        runtime.execute(1)
        self.assertEqual(selected['modules'], ['shipyard'])
        self.assertEqual(selected['buildings'], ['resource_silo'])
        self.assertNotIn('aqsc_done', runtime.country['flags'])

    def test_scripted_effect_logs_escape_localization_commands(self):
        import re
        effects = self.files['common/scripted_effects/auto_qol_starbase_clear_effects.txt']
        self.assertNotRegex(effects, r'(?<!\\)\[This\.')
        self.assertIn('version=0.2.5', effects)
        self.assertNotIn('remove_starbase_module = { }', effects)
        self.assertNotIn('remove_starbase_building = { }', effects)

    def test_building_path_uses_slots_and_logs_branches(self):
        effects = self.files['common/scripted_effects/auto_qol_starbase_clear_effects.txt']
        self.assertIn('remove_starbase_building = { slot = 1 }', effects)
        self.assertIn('remove_starbase_building = { slot = 12 }', effects)
        self.assertNotIn('remove_random_starbase_building =', effects)
        self.assertIn('remove_starbase_module = { module = anchorage }', effects)
        self.assertIn('category=buildings', effects)
        selected = base(modules=('anchorage',), buildings=('resource_silo', 'crew_quarters', 'hydroponics_bay'))
        runtime = self.runtime([selected])
        runtime.audit(selected)
        runtime.execute(2)
        self.assertEqual(selected['modules'], ['anchorage'])
        self.assertEqual(selected['buildings'], [])

    def test_building_slots_with_holes_and_extra_capacity_are_all_cleared(self):
        selected = base(modules=(), buildings=('crew_quarters', 'resource_silo'), building_slots=12,
                        building_positions={2: 'crew_quarters', 12: 'resource_silo'})
        runtime = self.runtime([selected])
        runtime.audit(selected)
        runtime.execute(2)
        self.assertEqual(selected['buildings'], [])
        self.assertEqual(selected['building_slots'], 12)
        self.assertIn('aqsc_done', runtime.country['flags'])

    def test_inline_fixture_parameters_recursion_and_nested_fields(self):
        with TemporaryDirectory(dir=builder.ROOT / 'scratch') as directory:
            root = Path(directory)
            folder = root / 'common/starbase_modules'
            folder.mkdir(parents=True)
            inline = root / 'common/inline_scripts'
            inline.mkdir()
            (folder / 'test.txt').write_text('inline_script = { script = fixture ID = example }', encoding='utf-8')
            (inline / 'fixture.txt').write_text('$ID$ = { potential = { always = yes } }', encoding='utf-8')
            self.assertEqual(list(builder.catalog(root, 'starbase_modules')), ['example'])
            (inline / 'fixture.txt').write_text('inline_script = { script = fixture }', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'Cannot resolve'):
                builder.catalog(root, 'starbase_modules')


if __name__ == '__main__':
    unittest.main()

"""Execute generated office scripts in a strict scope/transaction model.

This checks our orchestration, not the game's undocumented upgrade behavior.
Native fees, callbacks and rendering still need in-game acceptance.
"""
import operator
import math
import re
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import build_megastructure_office as office


def parse(text):
    tokens = re.findall(r'"[^"\n]*"|>=|<=|!=|[{}=<>]|[^\s{}=<>]+', re.sub(r'#[^\n]*', '', text))
    index = 0

    def rows():
        nonlocal index
        result = []
        while index < len(tokens) and tokens[index] != '}':
            key, comparison = tokens[index:index + 2]
            if comparison not in ('=', '>=', '<=', '>', '<', '!='):
                raise AssertionError((key, comparison))
            index += 2
            if tokens[index] == '{':
                index += 1
                value = rows()
                assert tokens[index] == '}'
                index += 1
            else:
                value = tokens[index].strip('"')
                index += 1
            result.append((key, comparison, value))
        return result
    result = rows()
    assert index == len(tokens)
    return result


def get(rows, key):
    return next(value for name, _, value in rows if name == key)


def mega(kind='think_tank_0', **changes):
    result = dict(kind=kind, upgrading=False, allowed=True, foreign=False,
                  system=dict(planets=[], star_flags=set(), arc=False))
    result.update(changes)
    return result


class Runtime:
    def __init__(self, script, structures=(), stock=None, mods=None, bio=False, ai=False):
        self.definitions = {key: value for key, _, value in parse(script)}
        self.country = dict(vars={'aqm_family': 0}, flags=set(),
                            stock=dict.fromkeys(office.RESOURCES, 1000000),
                            mods=dict(mods or {}), bio=bio, ai=ai)
        self.country['stock'].update(stock or {})
        self.structures = list(structures)
        self.targets, self.orders = {}, []
        self.missing_tech = set()
        self.native_fee = False
        self.native_fail = False

    def number(self, value, scope):
        try:
            return float(value)
        except ValueError:
            return scope.get('vars', {}).get(value, 0)

    def scope(self, key, current):
        if key == 'root':
            return self.country
        if key == 'owner':
            return {} if current.get('foreign') else self.country
        if key == 'solar_system':
            return current.get('system', current)
        if key.startswith('event_target:'):
            return self.targets[key.split(':')[1]]
        raise AssertionError('Unknown scope: ' + key)

    def condition(self, rows, current):
        for key, comparison, value in rows:
            if key in ('fail_text',):
                continue
            if key in ('AND', 'custom_tooltip'):
                valid = self.condition(value, current)
            elif key in ('OR', 'NOR'):
                valid = any(self.condition([row], current) for row in value)
                if key == 'NOR':
                    valid = not valid
            elif key == 'NOT':
                valid = not any(self.condition([row], current) for row in value)
            elif key == 'if':
                valid = not self.condition(get(value, 'limit'), current) or self.condition([row for row in value if row[0] != 'limit'], current)
            elif key in ('root', 'owner', 'solar_system') or key.startswith('event_target:'):
                valid = self.condition(value, self.scope(key, current))
            elif key == 'check_variable':
                left = current['vars'].get(get(value, 'which'), 0)
                _, comparison, right = next(row for row in value if row[0] == 'value')
                compare = {'=': operator.eq, '>': operator.gt, '<': operator.lt,
                           '>=': operator.ge, '<=': operator.le}[comparison]
                valid = compare(left, self.number(right, current))
            elif key == 'is_megastructure_type':
                valid = current['kind'] == value
            elif key in ('is_upgrading', 'can_be_upgraded'):
                valid = current['upgrading' if key == 'is_upgrading' else 'allowed'] == (value == 'yes')
            elif key == 'is_ai':
                valid = current['ai'] == (value == 'yes')
            elif key == 'is_same_value':
                valid = current is self.country
            elif key == 'has_country_flag':
                valid = value in current['flags']
            elif key == 'has_technology':
                valid = value not in self.missing_tech
            elif key == 'country_uses_bio_ships':
                valid = current['bio'] == (value == 'yes')
            elif key == 'always':
                valid = value == 'yes'
            elif key == 'system_has_arc_furnace':
                valid = current['arc'] == (value == 'yes')
            elif key == 'has_star_flag':
                valid = value in current['star_flags']
            elif key == 'any_system_planet':
                valid = any(self.condition(value, planet) for planet in current['planets'])
            elif key == 'has_policy_flag':
                valid = True
            elif key == 'has_relic':
                valid = False
            else:
                raise AssertionError('Unknown condition: ' + key)
            if not valid:
                return False
        return True

    def run(self, rows, current=None):
        current = self.country if current is None else current
        previous_branch = None
        for key, _, value in rows:
            if key in ('if', 'else_if', 'else'):
                if key == 'if':
                    previous_branch = False
                if previous_branch:
                    continue
                if key == 'else' or self.condition(get(value, 'limit'), current):
                    self.run([row for row in value if row[0] != 'limit'], current)
                    previous_branch = True
                continue
            previous_branch = None
            if key in ('root', 'owner', 'solar_system') or key.startswith('event_target:'):
                self.run(value, self.scope(key, current))
            elif key == 'every_owned_megastructure':
                assert current is self.country
                for structure in self.structures:
                    if structure['foreign']:
                        continue
                    if any(row[0] == 'limit' for row in value) and not self.condition(get(value, 'limit'), structure):
                        continue
                    self.run([row for row in value if row[0] != 'limit'], structure)
            elif key.endswith('_variable') and key.split('_')[0] in ('set', 'change', 'subtract', 'multiply'):
                name = get(value, 'which')
                amount = self.number(get(value, 'value'), current)
                before = current['vars'].get(name, 0)
                current['vars'][name] = {'set': lambda: amount, 'change': lambda: before + amount,
                                         'subtract': lambda: before - amount, 'multiply': lambda: before * amount}[key.split('_')[0]]()
            elif key == 'export_modifier_to_variable':
                current['vars'][get(value, 'variable')] = current['mods'].get(get(value, 'modifier'), 0)
            elif key == 'floor_variable':
                current['vars'][value] = math.floor(current['vars'][value])
            elif key == 'export_resource_stockpile_to_variable':
                current['vars'][get(value, 'variable')] = current['stock'][get(value, 'resource')]
            elif key in ('set_country_flag', 'remove_country_flag'):
                assert current is self.country
                (current['flags'].add if key.startswith('set') else current['flags'].discard)(value)
            elif key == 'save_event_target_as':
                self.targets[value] = current
            elif key == 'upgrade_megastructure_to':
                assert current is not self.country
                if not self.native_fail:
                    self.orders.append((current['kind'], value))
                    current['kind'], current['upgrading'] = value, True
                    if self.native_fee:
                        for resource in office.RESOURCES:
                            self.country['stock'][resource] -= self.country['vars']['aqm_cost_' + resource]
            elif key == 'add_resource':
                multiplier = self.number(next((v for k, _, v in value if k == 'mult'), '1'), current)
                for resource, _, amount in value:
                    if resource != 'mult':
                        current['stock'][resource] += self.number(amount, current) * multiplier
            elif key in self.definitions:
                self.run(self.definitions[key], current)
            else:
                raise AssertionError('Unknown effect: ' + key)

    def scan(self, execute=False):
        if execute:
            self.country['flags'].add('aqm_execute')
        self.run(self.definitions['auto_qol_mega_scan'])
        return self.country['vars']


class OfficeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.files = office.generate()
        cls.script = cls.files['common/scripted_effects/auto_qol_megastructure_effects.txt']
        cls.sources, _ = office.load_definitions()

    def runtime(self, *args, **kwargs):
        return Runtime(self.script, *args, **kwargs)

    def test_preview_reserves_budget_and_cap_without_mutation(self):
        structures = [mega(), mega()]
        runtime = self.runtime(structures)
        before = dict(runtime.country['stock'])
        values = runtime.scan()
        self.assertEqual(values['aqm_found'], 2)
        self.assertEqual(values['aqm_ready'], 1)
        self.assertEqual(values['aqm_total_alloys'], 15000)
        self.assertEqual(runtime.country['stock'], before)
        self.assertEqual(runtime.orders, [])

    def test_batch_starts_one_stage_per_object_and_charges_exactly_once(self):
        runtime = self.runtime([mega(), mega()], mods={'country_megastructure_build_cap_add': 1})
        values = runtime.scan(True)
        self.assertEqual(runtime.orders, [('think_tank_0', 'think_tank_1')] * 2)
        self.assertEqual(values['aqm_ready'], 2)
        self.assertEqual(runtime.country['stock']['alloys'], 970000)
        self.assertEqual(runtime.country['stock']['unity'], 990000)
        runtime.scan(True)
        self.assertEqual(len(runtime.orders), 2)

    def test_insufficient_budget_skips_later_items_and_keeps_balances_nonnegative(self):
        runtime = self.runtime([mega(), mega()], stock={'alloys': 20000}, mods={'country_megastructure_build_cap_add': 5})
        self.assertEqual(runtime.scan(True)['aqm_ready'], 1)
        self.assertEqual(runtime.country['stock']['alloys'], 5000)

    def test_confirmation_rechecks_resources_and_caps(self):
        runtime = self.runtime([mega()])
        self.assertEqual(runtime.scan()['aqm_ready'], 1)
        runtime.country['stock']['alloys'] = 1
        self.assertEqual(runtime.scan(True)['aqm_ready'], 0)
        self.assertEqual(runtime.orders, [])

    def test_failed_native_start_never_charges_or_claims_success(self):
        runtime = self.runtime([mega()])
        runtime.native_fail = True
        before = dict(runtime.country['stock'])
        values = runtime.scan(True)
        self.assertEqual((values['aqm_ready'], values['aqm_failed']), (0, 1))
        self.assertEqual(runtime.country['stock'], before)

    def test_native_payment_is_not_charged_twice(self):
        runtime = self.runtime([mega()])
        runtime.native_fee = True
        runtime.scan(True)
        self.assertEqual(runtime.country['stock']['alloys'], 985000)

    def test_active_foreign_finished_weapon_event_and_ruins_are_skipped(self):
        runtime = self.runtime([mega(upgrading=True), mega(foreign=True), mega('think_tank_3'),
                                mega('think_tank_ruined'), mega('dyson_gun_0'), mega('dyson_gun_3'),
                                mega('AOW_MEGA_starfall_spear_standby')])
        self.assertEqual(runtime.scan(True)['aqm_ready'], 0)
        self.assertEqual(runtime.orders, [])
        self.assertNotIn('upgrade_megastructure_to = think_tank_4', self.script)
        self.assertNotIn('upgrade_megastructure_to = dyson_gun', self.script)
        self.assertNotIn('finish_upgrade', self.script)

    def test_technology_ownership_and_native_eligibility_are_required(self):
        for change in ({'allowed': False}, {'foreign': True}):
            self.assertEqual(self.runtime([mega(**change)]).scan(True)['aqm_ready'], 0)
        runtime = self.runtime([mega()])
        runtime.missing_tech.add('tech_science_nexus')
        self.assertEqual(runtime.scan(True)['aqm_ready'], 0)

    def test_normal_cost_discounts_and_biological_costs(self):
        runtime = self.runtime([mega()], bio=True, mods={'megastructures_cost_mult': -0.2})
        values = runtime.scan(True)
        self.assertEqual(values['aqm_total_alloys'], 6000)
        self.assertEqual(values['aqm_total_food'], 21000)
        self.assertEqual(values['aqm_total_unity'], 4000)
        self.assertEqual(runtime.country['stock']['food'], 979000)

    def test_extreme_unreviewed_cost_floor_is_skipped(self):
        runtime = self.runtime([mega()], mods={'megastructures_cost_mult': -1})
        self.assertEqual(runtime.scan(True)['aqm_ready'], 0)
        self.assertEqual(runtime.orders, [])
        self.assertEqual(runtime.country['vars']['aqm_price_skipped'], 1)

    def test_nonblocking_projects_do_not_use_or_consume_multistage_cap(self):
        runtime = self.runtime([mega(upgrading=True), mega('dyson_swarm_1'), mega('dyson_swarm_1')])
        self.assertEqual(runtime.scan(True)['aqm_ready'], 2)
        self.assertEqual(runtime.orders, [('dyson_swarm_1', 'dyson_swarm_2')] * 2)

    def test_selected_type_only(self):
        runtime = self.runtime([mega(), mega('dyson_swarm_1')])
        runtime.country['vars']['aqm_family'] = 11
        runtime.scan(True)
        self.assertEqual(runtime.orders, [('dyson_swarm_1', 'dyson_swarm_2')])

    def test_ai_guard(self):
        runtime = self.runtime([mega()], ai=True)
        runtime.scan(True)
        self.assertEqual(runtime.orders, [])

    def test_every_curated_edge_and_source_conditions_compile(self):
        for index, source, target, block in office.curated_edges(self.sources)[0]:
            with self.subTest(source=source):
                runtime = self.runtime([mega(source)])
                runtime.scan(True)
                self.assertEqual(runtime.orders, [(source, target)])

    def test_native_source_duplicates_and_multipliers_are_preserved(self):
        runtime = self.runtime([mega('dyson_sphere_0')])
        self.assertEqual(runtime.scan()['aqm_total_alloys'], 20000)
        self.assertEqual(office.field(self.sources['think_tank_4'], 'potential'), 'always = no')

    def test_new_branch_or_mod_override_disables_edge(self):
        definitions = dict(self.sources)
        definitions['test_weapon'] = 'test_weapon = { upgrade_from = { think_tank_0 } }'
        edges, skipped = office.curated_edges(definitions)
        self.assertIn(('think_tank_0', 'think_tank_1'), skipped)
        self.assertNotIn('think_tank_0', [s for _, s, _, _ in edges])
        edges, skipped = office.curated_edges(self.sources, {'think_tank_1'})
        self.assertIn(('think_tank_0', 'think_tank_1'), skipped)
        self.assertIn(('think_tank_1', 'think_tank_2'), skipped)

    def test_generated_files_native_navigation_localization_and_build_repeatability(self):
        gui = self.files['interface/auto_qol_megastructure.gui']
        self.assertIn('scrollbarType = "standardlistbox_slider"', gui)
        self.assertNotIn('effectButtonType', gui)
        self.assertNotIn('smoothListBoxType', gui)
        events = self.files['events/auto_qol_megastructure_gui_events.txt']
        self.assertIn('id = auto_qol_menu.1', events)
        self.assertIn('auto_qol_mega_page.2', events)
        self.assertIn('set_country_flag = aqm_execute', events)
        with TemporaryDirectory(dir=office.ROOT / 'scratch') as directory:
            root = Path(directory)
            office.build(root)
            before = {key: (root / key).read_bytes() for key in self.files}
            office.build(root)
            self.assertEqual(before, {key: (root / key).read_bytes() for key in self.files})
            loc = before['localisation/simp_chinese/auto_qol_megastructure_l_simp_chinese.yml']
            self.assertTrue(loc.startswith(b'\xef\xbb\xbf'))
            self.assertFalse(loc.startswith(b'\xef\xbb\xbf' * 2))


if __name__ == '__main__':
    unittest.main()

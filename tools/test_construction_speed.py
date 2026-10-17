"""Regression checks for menu effects and migration; game engine validation is separate."""
import re
import unittest
from pathlib import Path
from build_smart_council_system import find_matching_brace, strip_comments

MOD_ROOT = Path(__file__).resolve().parents[1]


def parse(text):
    tokens = re.findall(r'"[^"\n]*"|[{}=<>]|[^\s{}=<>]+', strip_comments(text))
    def walk(index):
        rows = []
        while index < len(tokens) and tokens[index] != '}':
            key, operator = tokens[index:index + 2]
            index += 2
            if tokens[index] == '{':
                value, index = walk(index + 1)
            else:
                value = tokens[index].strip('"')
                index += 1
            rows.append((key, operator, value))
        return rows, index + 1
    return walk(0)[0]


def named(text, marker):
    start = text.index('{', text.index(marker))
    return parse(text[start + 1:find_matching_brace(text, start)])


class Runtime:
    def __init__(self, effects, static, variables=None, flags=None):
        self.effects, self.static = effects, static
        self.variables = dict(variables or {})
        self.flags = set(flags or ())
        self.modifiers = {'unrelated': {'bonus': 17}}
        self.events = []

    def number(self, value):
        try:
            return float(value)
        except ValueError:
            return self.variables.get(value, 0)

    def condition(self, rows):
        for key, operator, value in rows:
            if key == 'NOT' and self.condition(value):
                return False
            if key == 'is_variable_set' and value not in self.variables:
                return False
            if key == 'has_country_flag' and value not in self.flags:
                return False
            if key == 'check_variable':
                variable = next(v for k, o, v in value if k == 'which')
                _, comparison, target = next(row for row in value if row[0] == 'value')
                current = self.variables.get(variable, 0)
                if not (current > self.number(target) if comparison == '>' else current < self.number(target)):
                    return False
        return True

    def run(self, rows):
        for key, operator, value in rows:
            if key in ('name', 'trigger', 'default_hide_option'):
                continue
            if key in ('hidden_effect', 'immediate'):
                self.run(value)
            elif key == 'if':
                if self.condition(next(v for k, o, v in value if k == 'limit')):
                    self.run([row for row in value if row[0] != 'limit'])
            elif key in ('set_variable', 'change_variable', 'subtract_variable'):
                args = {k:v for k,o,v in value}
                variable, amount = args['which'], self.number(args['value'])
                self.variables[variable] = amount if key == 'set_variable' else self.variables.get(variable, 0) + amount * (1 if key == 'change_variable' else -1)
            elif key == 'set_country_flag':
                self.flags.add(value)
            elif key == 'remove_modifier':
                self.modifiers.pop(value, None)
            elif key == 'add_modifier':
                args = {k:v for k,o,v in value}
                unit = named(self.static, args['modifier'] + ' = {')
                self.modifiers[args['modifier']] = {k:float(v) * self.number(args['multiplier']) for k,o,v in unit}
            elif key == 'country_event':
                self.events.append(next(v for k,o,v in value if k == 'id'))
            elif key.startswith('auto_qol_'):
                self.run(named(self.effects, key + ' = {'))
            else:
                raise AssertionError('Unhandled effect: ' + key)


class ConstructionSpeedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.events = (MOD_ROOT / 'events/auto_qol_fleet_events.txt').read_text(encoding='utf-8-sig')
        cls.effects = (MOD_ROOT / 'common/scripted_effects/auto_qol_fleet_scripted_effects.txt').read_text(encoding='utf-8-sig')
        cls.static = (MOD_ROOT / 'common/static_modifiers/auto_qol_static_modifiers.txt').read_text(encoding='utf-8-sig')

    def runtime(self, module=0, upgrade=0):
        return Runtime(self.effects, self.static, {'qol_custom_starbase_module_speed':module, 'qol_custom_starbase_upgrade_speed':upgrade})

    def menu(self, feature):
        return named(self.events, 'country_event = {\n\tid = auto_qol_' + feature + '_menu.1\n')

    def option(self, feature, action):
        return next(rows for k,o,rows in self.menu(feature) if k == 'option' and ('name', '=', 'auto_qol_' + feature + '_speed.' + action) in rows)

    def prepare(self, runtime):
        runtime.run(named(self.effects, 'auto_qol_prepare_starbase_construction = {'))

    def test_migrate_max_and_remove_old_bonus(self):
        for module, upgrade in [(0,0), (100,500), (500,100), (200,200), (0,1000)]:
            with self.subTest(module=module, upgrade=upgrade):
                runtime = self.runtime(module, upgrade)
                runtime.modifiers['qol_custom_starbase_upgrade_speed_modifier'] = {'starbase_upgrade_speed_mult':upgrade / 100}
                self.prepare(runtime)
                self.assertEqual(runtime.variables['qol_custom_starbase_module_speed'], max(module, upgrade))
                self.assertEqual(runtime.variables['qol_custom_starbase_upgrade_speed'], 0)
                self.assertNotIn('qol_custom_starbase_upgrade_speed_modifier', runtime.modifiers)
                expected = {key:max(module, upgrade)/100 for key in ('starbase_module_build_speed_mult', 'starbase_building_build_speed_mult', 'starbase_upgrade_speed_mult')}
                self.assertEqual(runtime.modifiers.get('qol_custom_starbase_module_speed_modifier', {}), expected if max(module,upgrade) else {})

    def test_new_save_and_repeat_open_preserves_reset(self):
        runtime = Runtime(self.effects, self.static)
        self.prepare(runtime)
        self.assertEqual(runtime.variables['qol_custom_starbase_module_speed'], 0)
        runtime = self.runtime(100,500)
        self.prepare(runtime)
        runtime.run(self.option('starbase_module','reset'))
        self.prepare(runtime)
        self.assertEqual(runtime.variables['qol_custom_starbase_module_speed'], 0)
        self.assertNotIn('qol_custom_starbase_module_speed_modifier', runtime.modifiers)

    def test_parent_and_legacy_menu_migrate(self):
        for menu in ('fleet','starbase_module','starbase_upgrade'):
            runtime = self.runtime(50,200)
            runtime.run(next(v for k,o,v in self.menu(menu) if k == 'immediate'))
            self.assertEqual(runtime.variables['qol_custom_starbase_module_speed'], 200)
        self.assertIn('auto_qol_starbase_module_menu.1', runtime.events)
        self.assertNotIn('name = "auto_qol_fleet_menu.go_starbase_upgrade_speed"', self.events)

    def test_all_speed_steps_and_independent_reset(self):
        for feature in ('starbase_module','defense_platform','army_recruit','ship_build','planet_build'):
            for amount in (50,100,200,500,1000):
                runtime = self.runtime()
                self.prepare(runtime)
                runtime.run(self.option(feature, 'add_' + str(amount)))
                variable = 'qol_custom_' + feature + '_speed'
                self.assertEqual(runtime.variables[variable], amount)
                runtime.run(self.option(feature,'sub_1000'))
                self.assertEqual(runtime.variables[variable], 0)
                self.assertEqual(runtime.modifiers['unrelated'], {'bonus':17})
                runtime.run(self.option(feature,'add_1000'))
                runtime.run(self.option(feature,'reset'))
                self.assertEqual(runtime.variables[variable], 0)

    def test_defense_bonus_covers_station_class_without_double_counting(self):
        runtime = self.runtime()
        runtime.modifiers['external_station_bonus'] = {'shipclass_military_station_build_speed_mult':0.2}
        runtime.variables['qol_custom_defense_platform_speed'] = 2000
        # Reapply an existing save value using the expanded modifier definition.
        runtime.run(named(self.effects, 'auto_qol_reapply_defense_platform_speed = {'))
        own = 'qol_custom_defense_platform_speed_modifier'
        self.assertEqual(runtime.modifiers[own], {'shipclass_military_station_build_speed_mult':20})
        runtime.run(self.option('defense_platform', 'sub_1000'))
        self.assertEqual(runtime.modifiers[own], {'shipclass_military_station_build_speed_mult':10})
        runtime.run(self.option('defense_platform', 'reset'))
        self.assertNotIn(own, runtime.modifiers)
        self.assertEqual(runtime.modifiers['external_station_bonus'], {'shipclass_military_station_build_speed_mult':0.2})

    def test_planet_economy_menus_preserve_saves_and_are_player_only(self):
        for feature in ('planet_build', 'planet_jobs'):
            menu = self.menu(feature)
            self.assertIn(('trigger', '=', [('is_ai', '=', 'no')]), menu)
            init = next(v for k,o,v in menu if k == 'immediate')
            runtime = Runtime(self.effects, self.static)
            runtime.run(init)
            variable = 'qol_custom_' + feature + '_speed'
            self.assertEqual(runtime.variables[variable], 0)
            runtime.variables[variable] = 37
            runtime.run(init)
            self.assertEqual(runtime.variables[variable], 37)

    def test_planet_combined_speed_and_jobs_output_are_independent(self):
        for amount in (10,25,50,100,200):
            runtime = self.runtime()
            runtime.modifiers['external'] = {'planet_jobs_produces_mult':0.2}
            runtime.run(self.option('planet_build','add_200'))
            runtime.run(self.option('planet_jobs','add_' + str(amount)))
            build = 'qol_custom_planet_build_speed_modifier'
            jobs = 'qol_custom_planet_jobs_speed_modifier'
            self.assertEqual(runtime.modifiers[build], {
                'planet_building_build_speed_mult':2,
                'planet_clear_blocker_speed_mult':2,
                'terraform_speed_mult':2,
            })
            self.assertEqual(runtime.modifiers[jobs], {'planet_jobs_produces_mult':amount/100})
            runtime.run(self.option('planet_jobs','sub_200'))
            self.assertEqual(runtime.variables['qol_custom_planet_jobs_speed'], 0)
            self.assertNotIn(jobs, runtime.modifiers)
            runtime.run(self.option('planet_jobs','add_25'))
            runtime.run(self.option('planet_build','reset'))
            self.assertNotIn(build, runtime.modifiers)
            self.assertEqual(runtime.modifiers[jobs], {'planet_jobs_produces_mult':0.25})
            runtime.run(self.option('planet_jobs','reset'))
            self.assertEqual(runtime.modifiers['external'], {'planet_jobs_produces_mult':0.2})
            self.assertEqual(runtime.modifiers['unrelated'], {'bonus':17})


    def planet_option(self, action):
        return next(rows for k,o,rows in self.menu('planet_construction') if k == 'option' and ('name', '=', 'auto_qol_planet_construction.' + action) in rows)

    def test_planet_capacity_initialization_and_saved_value(self):
        menu = self.menu('planet_construction')
        self.assertIn(('trigger', '=', [('is_ai', '=', 'no')]), menu)
        init = next(v for k,o,v in menu if k == 'immediate')
        runtime = Runtime(self.effects, self.static)
        runtime.run(init)
        self.assertEqual(runtime.variables['qol_custom_planet_construction'], 0)
        runtime.variables['qol_custom_planet_construction'] = 5
        runtime.run(init)
        self.assertEqual(runtime.variables['qol_custom_planet_construction'], 5)

    def test_planet_capacity_steps_stack_and_preserve_other_sources(self):
        for amount in (1,2,5):
            with self.subTest(amount=amount):
                runtime = self.runtime(module=73)
                runtime.modifiers['external_technology'] = {'planet_building_capacity_add':2}
                runtime.variables['qol_custom_planet_construction'] = 0
                runtime.run(self.planet_option('add_' + str(amount)))
                self.assertEqual(runtime.variables['qol_custom_planet_construction'], amount)
                own = 'qol_custom_planet_construction_modifier'
                self.assertEqual(runtime.modifiers[own], {'planet_building_capacity_add':amount})
                runtime.run(self.planet_option('add_1'))
                total = 1 + sum(mod.get('planet_building_capacity_add',0) for mod in runtime.modifiers.values())
                self.assertEqual(total, 1 + 2 + amount + 1)
                runtime.run(self.planet_option('sub_5'))
                self.assertEqual(runtime.variables['qol_custom_planet_construction'], max(0,amount + 1 - 5))
                runtime.run(self.planet_option('reset'))
                self.assertNotIn(own, runtime.modifiers)
                self.assertEqual(runtime.modifiers['external_technology'], {'planet_building_capacity_add':2})
                self.assertEqual(runtime.variables['qol_custom_starbase_module_speed'], 73)
                self.assertEqual(runtime.modifiers['unrelated'], {'bonus':17})


if __name__ == '__main__':
    unittest.main()

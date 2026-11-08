"""Execute emitted candidate scripts to check coverage, wraparound and filtering.

This small script interpreter is not a replacement for a game-engine UI check.
"""
import random
import unittest
from pathlib import Path

import build_smart_council_system as council
from test_construction_speed import named, parse


ROOT = Path(__file__).resolve().parents[1]


def value(rows, key):
    return next(v for k, _, v in rows if k == key)


class Leader:
    def __init__(self, index, **attrs):
        self.index = index
        self.flags = set()
        self.attrs = dict(is_pool_leader='no', is_ruler='no', is_councilor='no',
                          leader_class='scientist', fleet=False)
        self.attrs.update(attrs)


class Runtime:
    def __init__(self, leaders, effects, seed=0):
        self.leaders = leaders
        self.effects = effects
        self.targets = {}
        self.random = random.Random(seed)

    def condition(self, rows, leader=None):
        def check(key, arg):
            if key == 'NOT':
                return not self.condition(arg, leader)
            if key == 'OR':
                return any(self.condition([row], leader) for row in arg)
            if key == 'any_owned_leader':
                return any(self.condition(arg, item) for item in self.leaders)
            if key == 'has_leader_flag':
                return arg in leader.flags
            if key == 'exists':
                return bool(leader.attrs[arg])
            if key in leader.attrs:
                return leader.attrs[key] == arg
            raise AssertionError(key)
        return all(check(key, arg) for key, _, arg in rows)

    def run(self, rows, leader=None):
        for key, _, arg in rows:
            if key == 'if':
                if self.condition(value(arg, 'limit'), leader):
                    self.run([row for row in arg if row[0] != 'limit'], leader)
            elif key in ('every_owned_leader', 'random_owned_leader'):
                conditions = next((v for k, _, v in arg if k == 'limit'), [])
                selected = [item for item in self.leaders if self.condition(conditions, item)]
                if key == 'random_owned_leader':
                    selected = [self.random.choice(selected)] if selected else []
                for item in selected:
                    self.run([row for row in arg if row[0] != 'limit'], item)
            elif key == 'set_leader_flag':
                leader.flags.add(arg)
            elif key == 'remove_leader_flag':
                leader.flags.discard(arg)
            elif key == 'save_event_target_as':
                self.targets[arg] = leader
            elif key == 'auto_qol_clear_council_candidate_flags':
                self.run(named(self.effects, key + ' = {'))
            else:
                raise AssertionError(key)

    def page(self, key='councilor_test', class_filter='leader_class = scientist'):
        self.run(named(council.generate_candidate_immediate(key, class_filter), 'immediate = {'))
        # Visibility must depend on fresh flags, even if old event targets remain.
        return [self.targets[f'auto_qol_cand_{i}'].index for i in range(1, 11)
                if any(f'auto_qol_cand_flag_{i}' in item.flags for item in self.leaders)]

    def navigation(self, key='councilor_test', class_filter='leader_class = scientist'):
        options = parse(council.generate_candidate_navigation(201, key, class_filter))
        return [value(arg, 'name') for _, _, arg in options
                if self.condition(value(arg, 'trigger'))]


class CandidateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.effects = (ROOT / 'common/scripted_effects/auto_qol_council_scripted_effects.txt').read_text(encoding='utf-8')

    def runtime(self, count, seed=0):
        return Runtime([Leader(i) for i in range(count)], self.effects, seed)

    def test_complete_cycles_and_partial_last_page(self):
        for count in (0, 1, 7, 8, 9, 10, 11, 19, 20, 21, 65):
            for seed in range(10):
                with self.subTest(count=count, seed=seed):
                    runtime = self.runtime(count, seed)
                    for _ in range(3):
                        seen = []
                        for offset in range(0, max(count, 1), 10):
                            page = runtime.page()
                            self.assertEqual(len(page), min(10, count - offset))
                            self.assertTrue(set(page).isdisjoint(seen))
                            seen.extend(page)
                            expected = [] if not count else [
                                'auto_qol_assign.refresh' if len(seen) < count else 'auto_qol_assign.restart']
                            self.assertEqual(runtime.navigation(), expected)
                        self.assertEqual(set(seen), set(range(count)))

    def test_eligibility_changes_and_new_leaders(self):
        runtime = self.runtime(11)
        first = runtime.page()
        remaining = next(item for item in runtime.leaders if item.index not in first)
        remaining.attrs['fleet'] = True
        self.assertEqual(runtime.navigation(), ['auto_qol_assign.restart'])
        # Newly eligible leaders must be shown before any already viewed leader.
        remaining.attrs['fleet'] = False
        runtime.leaders.append(Leader(11))
        self.assertEqual(set(runtime.page()), {remaining.index, 11})
        self.assertEqual(runtime.navigation(), ['auto_qol_assign.restart'])

    def test_separate_seat_history(self):
        runtime = self.runtime(18)
        first = runtime.page('seat_a')
        self.assertEqual(len(runtime.page('seat_b')), 10)
        self.assertTrue(set(runtime.page('seat_a')).isdisjoint(first))

    def test_filtering_and_country_isolation(self):
        for class_filter, classes in (
            ('leader_class = scientist', {'scientist'}),
            ('OR = { leader_class = scientist leader_class = official }', {'scientist', 'official'}),
            ('', {'scientist', 'official', 'commander'}),
        ):
            leaders = [Leader(0), Leader(1, leader_class='official'), Leader(2, leader_class='commander'),
                       Leader(3, is_pool_leader='yes'), Leader(4, is_ruler='yes'),
                       Leader(5, is_councilor='yes'), Leader(6, fleet=True)]
            runtime = Runtime(leaders, self.effects)
            expected = {item.index for item in leaders[:3] if item.attrs['leader_class'] in classes}
            self.assertEqual(set(runtime.page(class_filter=class_filter)), expected)
        first, second = self.runtime(22), self.runtime(22)
        first.page()
        first.page()
        self.assertEqual(len(second.page()), 10)
        self.assertEqual(len(first.page()), 2)

    def test_shipped_menus_match_generator_and_have_ten_options(self):
        for root in (ROOT, ROOT.parent / 'Stellaris Mod Enhancer'):
            count = 0
            for path in (root / 'events').glob('auto_qol_council_assign_*_events.txt'):
                for key, _, event in parse(path.read_text(encoding='utf-8')):
                    if key != 'country_event':
                        continue
                    title = value(event, 'title')
                    if not title.endswith('.pick_name'):
                        continue
                    count += 1
                    pos_key = title.split('.')[1]
                    immediate = value(event, 'immediate')
                    draw = next(arg for k, _, arg in immediate if k == 'random_owned_leader')
                    conditions = value(draw, 'limit')
                    classes = [v for k, _, v in conditions if k == 'leader_class']
                    or_classes = [v for k, _, v in conditions if k == 'OR']
                    class_filter = f'leader_class = {classes[0]}' if classes else ''
                    if or_classes:
                        class_filter = 'OR = { ' + ' '.join(f'{k} = {v}' for k, _, v in or_classes[0]) + ' }'
                    self.assertEqual(immediate, named(council.generate_candidate_immediate(pos_key, class_filter), 'immediate = {'))
                    options = [arg for k, _, arg in event if k == 'option']
                    candidates = [value(arg, 'name') for arg in options if value(arg, 'name').startswith('auto_qol_assign.cand_')]
                    self.assertEqual(candidates, [f'auto_qol_assign.cand_{i}' for i in range(1, 11)])
                    for index in range(1, 11):
                        option = next(arg for arg in options if value(arg, 'name') == f'auto_qol_assign.cand_{index}')
                        self.assertEqual(value(option, 'country_event'), [('id', '=', 'auto_qol_council_assign.99')])
                        self.assertIn((f'event_target:auto_qol_cand_{index}', '=', [('set_council_position', '=', pos_key)]), option)
                        trigger = value(option, 'trigger')
                        self.assertIn(('any_owned_leader', '=', [('has_leader_flag', '=', f'auto_qol_cand_flag_{index}')]), trigger)
                    nav = [row for row in event if row[0] == 'option' and value(row[2], 'name') in ('auto_qol_assign.refresh', 'auto_qol_assign.restart')]
                    pos_id = int(value(event, 'id').split('.')[1])
                    self.assertEqual(nav, parse(council.generate_candidate_navigation(pos_id, pos_key, class_filter)))
            self.assertGreater(count, 0)
            loc_path = root / 'localisation/simp_chinese/auto_qol_council_assign_l_simp_chinese.yml'
            loc = loc_path.read_text(encoding='utf-8-sig')
            self.assertTrue(loc_path.read_bytes().startswith(b'\xef\xbb\xbf'))
            self.assertNotIn('随机刷新', loc)
            for index in range(1, 11):
                self.assertIn(f'auto_qol_assign.cand_{index}:0', loc)
            cleanup = named((root / 'common/scripted_effects/auto_qol_council_scripted_effects.txt').read_text(encoding='utf-8'), 'auto_qol_clear_council_candidate_flags = {')
            self.assertEqual({v for k, _, v in value(cleanup, 'every_owned_leader') if k == 'remove_leader_flag'},
                             {f'auto_qol_cand_flag_{index}' for index in range(1, 11)})

    def test_newly_generated_menu(self):
        categories = [{'cat_id': 20, 'cat_tag': 'scientist', 'cat_name': 'Test', 'cat_desc': 'Test',
                       'positions': [{'id': 201, 'key': 'councilor_test', 'title': 'Test', 'classes': ['scientist']}]}]
        script = council.generate_events(categories, {})
        events = [arg for key, _, arg in parse(script) if key == 'country_event']
        picker = next(event for event in events if value(event, 'id') == 'auto_qol_council_assign.201')
        names = [value(arg, 'name') for key, _, arg in picker if key == 'option']
        self.assertEqual(len([name for name in names if name.startswith('auto_qol_assign.cand_')]), 10)
        self.assertIn('auto_qol_assign.restart', names)
        # Ten candidates plus one of next/restart and back fit the 12-row body.
        # Do not add an extra layout page just for mutually exclusive options.
        from native_dashboard_footer import transform_events
        transformed = parse(transform_events(script, "fixture_footer", "fixture_layout"))
        emitted = {value(arg, 'id'): arg for key, _, arg in transformed if key == 'country_event'}
        def page_routes(rows):
            found = set()
            for key, _, arg in rows:
                if key == 'country_event' and value(arg, 'id').startswith('fixture_layout.'):
                    found.add(value(arg, 'id'))
                elif isinstance(arg, list):
                    found.update(page_routes(arg))
            return found
        self.assertEqual(len(page_routes(value(emitted['auto_qol_council_assign.201'], 'immediate'))), 1)


if __name__ == '__main__':
    unittest.main()

"""Exercise emitted pool scripts; engine refill timing still needs in-game QA."""
import unittest
from pathlib import Path

from test_construction_speed import parse

ROOT = Path(__file__).resolve().parents[1]


class Pool:
    def __init__(self, effects, size, penalties=(), enabled=True):
        self.effects = effects
        self.size = size
        self.penalties = set(penalties)
        self.enabled = enabled
        self.refreshes = 0
        self.pending = []
        self.kills = 0

    def condition(self, rows):
        def check(key, op, arg):
            if key == 'OR':
                return any(self.condition([row]) for row in arg)
            if key == 'has_modifier':
                return arg in self.penalties
            if key == 'count_pool_leader':
                _, comparison, count = next(row for row in arg if row[0] == 'count')
                return self.size > int(count) if comparison == '>' else self.size == int(count)
            if key == 'always':
                return arg == 'yes'
            raise AssertionError((key, op, arg))
        return all(check(*row) for row in rows)

    def run(self, rows):
        for key, _, arg in rows:
            if key in self.effects:
                self.run(self.effects[key])
            elif key in ('if', 'while'):
                limit = next(v for k, _, v in arg if k == 'limit')
                body = [row for row in arg if row[0] != 'limit']
                budget = self.size + 2
                while self.condition(limit):
                    self.run(body)
                    budget -= 1
                    assert budget > 0, 'non-terminating trim'
                    if key == 'if':
                        break
            elif key == 'random_pool_leader':
                assert self.size > 0
                self.run([row for row in arg if row[0] != 'limit'])
            elif key == 'kill_leader':
                self.size -= 1
                self.kills += 1
            elif key == 'remove_modifier':
                self.penalties.discard(arg)
            elif key == 'refresh_leader_pool':
                assert not self.penalties, 'refresh attempted before removing size penalties'
                self.refreshes += 1
                # Simulate engine refill without destroying existing candidates.
                self.size = max(self.size, 9)
            elif key == 'country_event':
                self.pending.append(next(v for k, _, v in arg if k == 'id'))
            else:
                raise AssertionError(key)


class LeaderPoolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.effects = dict((k, v) for k, _, v in parse(
            (ROOT / 'common/scripted_effects/auto_qol_leader_pool_scripted_effects.txt').read_text(encoding="utf-8-sig")))

    def test_trim_boundary_and_large_modded_pool(self):
        for size in (0, 1, 3, 9, 10, 11, 60, 200):
            with self.subTest(size=size):
                pool = Pool(self.effects, size)
                pool.run(self.effects['auto_qol_trim_leader_pool_to_10'])
                self.assertEqual(pool.size, min(size, 10))
                self.assertEqual(pool.kills, max(size - 10, 0))

    def test_empty_pool_repair_and_idempotence(self):
        pool = Pool(self.effects, 0, enabled=False)
        pool.run(self.effects['auto_qol_repair_leader_pool'])
        self.assertEqual(pool.size, 9)
        pool.run(self.effects['auto_qol_repair_leader_pool'])
        self.assertEqual(pool.refreshes, 1)
        self.assertEqual(pool.kills, 0)

    def test_each_legacy_penalty_removed_before_refresh(self):
        for level in (5, 10, 20):
            for size in (0, 4, 60):
                with self.subTest(level=level, size=size):
                    pool = Pool(self.effects, size, [f'auto_qol_pool_clamp_{level}'])
                    pool.run(self.effects['auto_qol_repair_leader_pool'])
                    self.assertFalse(pool.penalties)
                    self.assertEqual(pool.refreshes, 1)
                    self.assertEqual(pool.kills, 0)

    def test_healthy_pool_is_not_refreshed(self):
        pool = Pool(self.effects, 5)
        pool.run(self.effects['auto_qol_repair_leader_pool'])
        self.assertEqual((pool.size, pool.refreshes, pool.kills), (5, 0, 0))

    def test_runtime_and_release_have_no_clear_all_or_negative_penalty(self):
        for root in (ROOT, ROOT.parent / 'Stellaris Mod Enhancer'):
            events = (root / 'events/auto_qol_council_events.txt').read_text(encoding="utf-8-sig")
            self.assertNotIn('every_pool_leader', events)
            self.assertNotIn('auto_qol_council_pool.clamp_', events)
            static = (root / 'common/static_modifiers/auto_qol_static_modifiers.txt').read_text(encoding="utf-8-sig")
            self.assertNotIn('country_leader_pool_size = -', static)
            menu = (root / 'events/auto_qol_menu_events.txt').read_text(encoding="utf-8-sig")
            self.assertEqual(menu.count('auto_qol_repair_leader_pool = yes'), 2)

    def test_legacy_generator_template_matches_runtime(self):
        template = (ROOT / 'tools/templates/leader_pool_events.txt').read_text(encoding="utf-8-sig")
        runtime = (ROOT / 'events/auto_qol_council_events.txt').read_text(encoding="utf-8-sig")
        for _, _, event in parse(template):
            event_id = next(v for k, _, v in event if k == 'id')
            emitted = next(v for k, _, v in parse(runtime)
                           if k == 'country_event' and ('id', '=', event_id) in v)
            self.assertEqual(event, emitted)


if __name__ == '__main__':
    unittest.main()

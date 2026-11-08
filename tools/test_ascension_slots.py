"""Execute the actual unlock option against unlocked/spent-slot scenarios."""
import unittest
from test_construction_speed import MOD_ROOT, named


class Empire:
    def __init__(self, slots, granted=0, ai=False, target=256):
        self.base = slots - granted
        self.bonus = granted
        self.ai = ai
        self.variables = {'auto_qol_ascension_granted': granted}
        if target is not None:
            self.variables['auto_qol_ascension_target'] = target

    def number(self, value):
        if value == '@auto_qol_ascension_slot_target':
            return 256
        if value == 'trigger:num_ascension_perk_slots':
            return self.base + self.bonus
        try:
            return float(value)
        except ValueError:
            return self.variables.get(value, 0)

    def condition(self, rows):
        for key, op, value in rows:
            if key == 'NOT':
                if self.condition(value):
                    return False
            elif key == 'is_variable_set':
                if value not in self.variables:
                    return False
            elif key == 'check_variable':
                variable = next(v for k, o, v in value if k == 'which')
                _, comparison, target = next(row for row in value if row[0] == 'value')
                current, target = self.variables.get(variable, 0), self.number(target)
                if not (current > target if comparison == '>' else current < target):
                    return False
            elif key == 'is_ai':
                if self.ai != (value == 'yes'):
                    return False
            elif key == 'num_ascension_perk_slots':
                slots, target = self.base + self.bonus, self.number(value)
                if not (slots < target if op == '<' else slots >= target):
                    return False
            else:
                raise AssertionError(key)
        return True

    def run(self, rows):
        for key, op, value in rows:
            if key == 'if':
                if self.condition(next(v for k, o, v in value if k == 'limit')):
                    self.run([r for r in value if r[0] != 'limit'])
            elif key in ('set_variable', 'subtract_variable', 'change_variable'):
                args = {k: v for k, o, v in value}
                var, amount = args['which'], self.number(args['value'])
                if key == 'set_variable':
                    self.variables[var] = amount
                else:
                    self.variables[var] = self.variables.get(var, 0) + amount * (-1 if key == 'subtract_variable' else 1)
            elif key == 'remove_modifier':
                self.bonus = 0
            elif key == 'add_modifier':
                self.bonus = self.number(next(v for k, o, v in value if k == 'multiplier'))
            elif key != 'country_event':
                raise AssertionError(key)


class UnlockTests(unittest.TestCase):
    def test_fill_only_missing_slots_and_repeat(self):
        text = (MOD_ROOT / 'events/auto_qol_ascension_events.txt').read_text(encoding='utf-8-sig')
        effect = named(text[text.index('name = "auto_qol_ascension.unlock"'):], 'hidden_effect = {')
        for target in (1, 8, 9, 16, 24, 256, 4096):
            for initial in (0, 1, 7, 8, 24, 100, 255, 256, 300):
                for granted in (0, min(initial, 5)):
                    empire = Empire(initial, granted, target=target)
                    empire.run(effect)
                    self.assertEqual(empire.base + empire.bonus, max(initial, target))
                    bonus = empire.bonus
                    empire.run(effect)
                    self.assertEqual(empire.bonus, bonus)


    def test_adjust_target_without_granting_and_clamp_to_one(self):
        text = (MOD_ROOT / 'events/auto_qol_ascension_events.txt').read_text(encoding='utf-8-sig')
        setup = named(text, 'immediate = {')
        def action(name):
            return named(text[text.index(f'name = "auto_qol_ascension.{name}"'):], 'hidden_effect = {')
        empire = Empire(4, target=8)
        for expected in (1, 1):
            empire.run(action('decrease'))
            empire.run(setup)
            self.assertEqual(empire.variables['auto_qol_ascension_target'], expected)
            self.assertEqual(empire.base + empire.bonus, 4)
        empire.run(action('increase'))
        empire.run(setup)  # reopening must not reset the chosen target
        self.assertEqual(empire.variables['auto_qol_ascension_target'], 9)
        self.assertEqual(empire.base + empire.bonus, 4)
        empire.run(action('unlock'))
        self.assertEqual(empire.base + empire.bonus, 9)
        empire.run(action('decrease'))
        empire.run(action('unlock'))
        self.assertEqual(empire.base + empire.bonus, 9)
        empire.variables['auto_qol_ascension_target'] = 4093
        empire.run(action('increase'))
        self.assertEqual(empire.variables['auto_qol_ascension_target'], 4096)
        empire.run(action('increase'))
        self.assertEqual(empire.variables['auto_qol_ascension_target'], 4096)

    def test_fine_adjustment_reaches_every_target_without_unlocking(self):
        text = (MOD_ROOT / 'events/auto_qol_ascension_events.txt').read_text(encoding='utf-8-sig')
        def action(name):
            return named(text[text.index(f'name = "auto_qol_ascension.{name}"'):], 'hidden_effect = {')
        minus, plus = action('decrease_one'), action('increase_one')
        empire = Empire(4, target=1)
        empire.run(minus)
        self.assertEqual(empire.variables['auto_qol_ascension_target'], 1)
        for target in range(2, 4097):
            empire.run(plus)
            self.assertEqual(empire.variables['auto_qol_ascension_target'], target)
            self.assertEqual(empire.base + empire.bonus, 4)
        empire.run(plus)
        self.assertEqual(empire.variables['auto_qol_ascension_target'], 4096)
        for target in range(4095, 0, -1):
            empire.run(minus)
            self.assertEqual(empire.variables['auto_qol_ascension_target'], target)
        empire.variables['auto_qol_ascension_target'] = 8
        empire.run(action('decrease'))
        empire.run(action('increase'))
        empire.run(minus)  # 8 -> 1 -> 9 -> 8
        self.assertEqual(empire.variables['auto_qol_ascension_target'], 8)
        self.assertEqual(empire.base + empire.bonus, 4)

    def test_initialization_and_old_save_target_are_preserved(self):
        text = (MOD_ROOT / 'events/auto_qol_ascension_events.txt').read_text(encoding='utf-8-sig')
        setup = named(text, 'immediate = {')
        for before, after in ((None, 256), (1, 1), (16, 16), (0, 1), (5000, 4096)):
            empire = Empire(3, target=before)
            empire.run(setup)
            self.assertEqual(empire.variables['auto_qol_ascension_target'], after)
            self.assertEqual(empire.base + empire.bonus, 3)


    def test_ai_execution_is_blocked(self):
        text = (MOD_ROOT / 'events/auto_qol_ascension_events.txt').read_text(encoding='utf-8-sig')
        empire = Empire(3, ai=True)
        empire.run(named(text[text.index('name = "auto_qol_ascension.unlock"'):], 'hidden_effect = {'))
        self.assertEqual(empire.base + empire.bonus, 3)


if __name__ == '__main__':
    unittest.main()

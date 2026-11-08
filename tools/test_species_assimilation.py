"""Execute the shipped script against migration, multiplayer and leader scenarios.

This interpreter covers only the used script subset, not engine portrait behavior.
"""
import unittest
from types import SimpleNamespace as Obj
from test_construction_speed import MOD_ROOT, parse


def field(rows, key):
    return next(value for name, _, value in rows if name == key)


def species(family):
    return Obj(family=family, flags=set(), sapient=True)


def person(kind, **overrides):
    values = dict(species=kind, flags=set(), event=False, tier='leader_tier_default',
                  node=False, chosen=False, name='Existing', portrait='custom', level=7)
    values.update(overrides)
    return Obj(**values)


class Runtime:
    effects = dict((key, value) for key, _, value in parse(
        (MOD_ROOT / 'common/scripted_effects/auto_qol_assimilation_effects.txt').read_text()))
    triggers = dict((key, value) for key, _, value in parse(
        (MOD_ROOT / 'common/scripted_triggers/auto_qol_assimilation_triggers.txt').read_text()))
    events = {
        field(rows, 'id'): rows for key, _, rows in parse(
            (MOD_ROOT / 'events/auto_qol_assimilation_events.txt').read_text())
        if key == 'country_event'
    }

    def __init__(self, main=None, ai=False):
        self.country = Obj(species=main or species('main'), ai=ai, flags=set(),
                           pops=[], leaders=[], pool=[])
        self.local, self.global_targets = {}, {}

    def resolve(self, value, current):
        if value == 'root':
            return self.country
        if value == 'species':
            return getattr(current, 'species', None)
        if value.startswith('event_target:'):
            name = value.removeprefix('event_target:')
            return (self.global_targets if '@root' in name else self.local).get(name)
        raise AssertionError('Unknown reference: ' + value)

    def owned_species(self):
        found = []
        for pop in self.country.pops:
            if pop.species not in found:
                found.append(pop.species)
        return found

    def condition(self, rows, current):
        for key, _, value in rows:
            if key == 'NOT':
                result = not self.condition(value, current)
            elif key == 'exists':
                result = self.resolve(value, current) is not None
            elif key == 'is_ai':
                result = current.ai == (value == 'yes')
            elif key in ('has_country_flag', 'has_species_flag', 'has_leader_flag'):
                result = value in current.flags
            elif key == 'is_same_species':
                target = self.resolve(value, current)
                source = getattr(current, 'species', current)
                target = getattr(target, 'species', target)
                result = target is not None and source.family == target.family
            elif key == 'is_same_value':
                result = current is self.resolve(value, current)
            elif key in ('is_event_leader', 'is_gestalt_node',
                         'has_any_chosen_one_leader_trait', 'is_sapient'):
                attr = dict(is_event_leader='event', is_gestalt_node='node',
                            has_any_chosen_one_leader_trait='chosen', is_sapient='sapient')[key]
                result = getattr(current, attr) == (value == 'yes')
            elif key == 'is_leader_tier':
                result = current.tier == value
            elif key == 'any_owned_species':
                result = any(self.condition(value, item) for item in self.owned_species())
            elif key in self.triggers:
                result = self.condition(self.triggers[key], current) == (value == 'yes')
            else:
                raise AssertionError('Unknown condition: ' + key)
            if not result:
                return False
        return True

    def run(self, rows, current=None):
        current = current or self.country
        for key, _, value in rows:
            if key == 'limit':
                continue
            if key == 'if':
                if self.condition(field(value, 'limit'), current):
                    self.run(value, current)
            elif key in self.effects:
                self.run(self.effects[key], current)
            elif key in ('hidden_effect', 'immediate'):
                self.run(value, current)
            elif key == 'species':
                self.run(value, current.species)
            elif key == 'root':
                self.run(value, self.country)
            elif key.startswith('event_target:'):
                target = self.resolve(key, current)
                if target is not None:
                    self.run(value, target)
            elif key in ('set_country_flag', 'set_species_flag'):
                current.flags.add(value)
            elif key in ('remove_country_flag', 'remove_species_flag'):
                current.flags.discard(value)
            elif key == 'save_event_target_as':
                self.local[value] = current
            elif key == 'save_global_event_target_as':
                self.global_targets[value] = current
            elif key == 'clear_global_event_target':
                self.global_targets.pop(value, None)
            elif key == 'change_species':
                current.species = self.resolve(value, current)
            elif key in ('every_owned_leader', 'every_pool_leader', 'every_owned_pop_group',
                         'every_owned_species', 'random_owned_species'):
                objects = {
                    'every_owned_leader': self.country.leaders,
                    'every_pool_leader': self.country.pool,
                    'every_owned_pop_group': self.country.pops,
                    'every_owned_species': self.owned_species(),
                    'random_owned_species': self.owned_species(),
                }[key]
                limits = next((v for k, _, v in value if k == 'limit'), [])
                matching = [obj for obj in objects if self.condition(limits, obj)]
                for obj in matching[:1] if key == 'random_owned_species' else matching:
                    self.run(value, obj)
            elif key != 'country_event':
                raise AssertionError('Unknown effect: ' + key)

    def option(self, event, name):
        rows = next(value for key, _, value in self.events[event]
                    if key == 'option' and field(value, 'name') == name)
        guard = next((v for k, _, v in rows if k == 'trigger'), [])
        if self.condition(guard, self.country):
            self.run(field(rows, 'hidden_effect'))

    def select(self, source):
        self.local['auto_qol_assimilation_candidate'] = source
        self.option('auto_qol_assimilation.3', 'auto_qol_assimilation.confirm')

    def pulse(self):
        event = self.events['auto_qol_assimilation.100']
        if self.condition(field(event, 'trigger'), self.country):
            self.run(field(event, 'immediate'))


class AssimilationTests(unittest.TestCase):
    def test_release_keeps_both_conditional_descriptions(self):
        from build_release_profiles import collect_localisation_references
        references = collect_localisation_references(MOD_ROOT)
        self.assertTrue({'auto_qol_assimilation.desc_selected',
                         'auto_qol_assimilation.desc_empty'} <= references)

    def test_migration_subspecies_and_source_survives_empty_empire(self):
        run = Runtime()
        source, other = species('alien'), species('other')
        run.country.pops = [person(source), person(other)]
        run.select(source)
        self.assertIs(run.country.pops[0].species, run.country.species)
        self.assertIs(run.country.pops[1].species, other)
        run.local.clear()  # A fresh monthly event has no old menu event targets.
        run.country.pops.append(person(species('alien')))
        run.pulse()
        self.assertIs(run.country.pops[-1].species, run.country.species)
        run.pulse()  # Idempotent.

    def test_players_and_ai_are_isolated(self):
        source = species('alien')
        first, second, ai = Runtime(), Runtime(), Runtime(ai=True)
        for run in (first, second, ai):
            run.country.pops = [person(source)]
        first.select(source)
        second.pulse()
        ai.select(source)
        ai.pulse()
        self.assertIs(second.country.pops[0].species, source)
        self.assertIs(ai.country.pops[0].species, source)
        second.select(source)
        self.assertIs(second.country.pops[0].species, second.country.species)

    def test_pause_resume_replace_clear_and_new_primary_template(self):
        run = Runtime()
        source, replacement = species('alien'), species('replacement')
        run.country.pops = [person(source)]
        run.select(source)
        run.option('auto_qol_assimilation.1', 'auto_qol_assimilation.pause')
        migrant = person(source)
        run.country.pops.append(migrant)
        run.pulse()
        self.assertIs(migrant.species, source)
        run.country.species = species('new_primary')
        run.option('auto_qol_assimilation.1', 'auto_qol_assimilation.resume')
        self.assertIs(migrant.species, run.country.species)
        run.country.pops.append(person(replacement))
        run.select(replacement)
        late = person(source)
        run.country.pops.append(late)
        run.pulse()
        self.assertIs(late.species, source)
        run.option('auto_qol_assimilation.1', 'auto_qol_assimilation.clear')
        late.species = replacement
        run.pulse()
        self.assertIs(late.species, replacement)

    def test_leader_default_off_filters_pool_and_no_recreation(self):
        run, source = Runtime(), species('alien')
        ordinary, pooled = person(source), person(source)
        protected = [person(source, **overrides) for overrides in (
            {'event': True}, {'tier': 'leader_tier_legendary'},
            {'tier': 'leader_tier_renowned'}, {'node': True}, {'chosen': True},
            {'flags': {'auto_qol_assimilation_protected'}}, {'flags': {'renowned_leader'}})]
        run.country.leaders = [ordinary, *protected]
        run.country.pool = [pooled]
        run.country.pops = [person(source)]
        run.select(source)
        self.assertIs(ordinary.species, source)
        run.option('auto_qol_assimilation.4', 'auto_qol_assimilation.enable_leaders')
        for leader in (ordinary, pooled):
            self.assertIs(leader.species, run.country.species)
            self.assertEqual((leader.name, leader.portrait, leader.level), ('Existing', 'custom', 7))
        self.assertTrue(all(leader.species is source for leader in protected))
        run.option('auto_qol_assimilation.1', 'auto_qol_assimilation.leaders_on')
        future = person(source)
        run.country.leaders.append(future)
        run.pulse()
        self.assertIs(future.species, source)

    def test_picker_pagination_stale_slots_and_main_species_guard(self):
        run = Runtime()
        candidates = [species(str(index)) for index in range(9)]
        run.country.pops = [person(run.country.species), *map(person, candidates)]
        run.run(run.effects['auto_qol_assimilation_prepare_page'])
        first_page = [run.local[f'auto_qol_assimilation_slot_{i}'] for i in range(1, 7)]
        self.assertEqual(len({id(item) for item in first_page}), 6)
        run.run(run.effects['auto_qol_assimilation_prepare_page'])
        valid = [i for i in range(1, 7)
                 if f'auto_qol_assimilation_slot_{i}_valid' in run.country.flags]
        self.assertEqual(valid, [1, 2, 3])
        self.assertFalse(any(run.local[f'auto_qol_assimilation_slot_{i}'] in first_page for i in valid))
        run.run(run.effects['auto_qol_assimilation_reset_picker'])
        run.run(run.effects['auto_qol_assimilation_prepare_page'])
        self.assertEqual(len([flag for flag in run.country.flags if flag.endswith('_valid')]), 6)
        run.select(run.country.species)
        self.assertNotIn('auto_qol_assimilation_enabled', run.country.flags)


if __name__ == '__main__':
    unittest.main()

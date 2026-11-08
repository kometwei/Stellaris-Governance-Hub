"""Check release wiring, menu guards and cumulative expansion behavior."""
import re
import tempfile
from pathlib import Path
from build_district_expansion import build, PREFIX, TIERS, ROOT
from build_smart_council_system import find_matching_brace
from native_dashboard_footer import top_blocks


def test():
    scratch = ROOT / 'scratch'
    scratch.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=scratch) as directory:
        files = build(directory)
        assert build(directory) == files
        for relative, text in files.items():
            if relative.endswith('.txt'):
                for match in re.finditer(r'\{', text):
                    assert find_matching_brace(text, match.start()) >= 0, relative
        decisions = files[f'common/decisions/{PREFIX}.txt']
        assert decisions.count('owned_planets_only = yes') == 1
        assert 'enactment_time = 0' in decisions
        events = files[f'events/{PREFIX}_events.txt']
        assert events.count('is_owned_by = event_target:') == len(TIERS) * 2
        assert events.count('days = -1') == len(TIERS)
        gui = files[f'interface/{PREFIX}.gui']
        assert f'custom_gui = "{PREFIX}_window"' in events
        assert f'custom_gui_option = "{PREFIX}_option"' in events
        assert 'effectButtonType' not in gui
        assert 'standardtext_slider' in gui and 'standardlistbox_slider' in gui
        assert 'name = "close"' in gui and 'shortcut = "ESCAPE"' in gui
        options = list(top_blocks(events[events.index('planet_event = {'):], 'option'))
        closing = [option for option in options if 'default_hide_option = yes' in option]
        assert len(closing) == 1
        assert f'name = "{PREFIX}.close"' in closing[0]
        assert 'effect' not in closing[0] and 'planet_event' not in closing[0]
        assert '@CONTENT@' not in gui
        # Six rows (five tiers and close) fit above the footer without overlap.
        assert 184 + 6 * (60 + 4) < 624
        assert 'resources =' not in decisions + events
        assert 'add_resource' not in events
        assert 'subtract_variable' not in events
        assert 'planet_jobs_produces_mult' not in ''.join(files.values())
        modifier = files[f'common/static_modifiers/{PREFIX}.txt']
        for key in ('planet_max_districts_add', 'district_mining_max_add',
                    'district_generator_max_add', 'district_farming_max_add'):
            assert f'{key} = 1' in modifier
        # Model the actual change_variable/remove/add sequence, starting both
        # with a new colony and an existing saved cumulative modifier.
        for initial in (0, 23):
            total = initial
            for tier in (3, 3, 1, 30, 5, 10):
                block = events.split(f'name = "{PREFIX}.add_{tier}"', 1)[1]
                delta = int(re.search(r'change_variable = \{ which = \w+ value = (\d+)', block)[1])
                total += delta
                assert f'mult = {PREFIX}_total' in block
            assert total == initial + 52
        for path in Path(directory).rglob('*.yml'):
            assert path.read_bytes().startswith(b'\xef\xbb\xbf')
        refs = re.findall(r'(?:name|title|desc|custom_tooltip) = "([\w.]+)"', events)
        loc = files[f'localisation/simp_chinese/{PREFIX}_l_simp_chinese.yml']
        assert all(f' {key}:0 ' in loc for key in refs)
        wiring = (ROOT / 'tools/build_release_profiles.py').read_text(encoding='utf-8')
        assert 'build_district_expansion(output_root)' in wiring
    print('District expansion checks passed (static and cumulative model; engine QA pending).')


if __name__ == '__main__':
    test()

"""Resolve the existing AP slot cap without overriding any game Defines."""
import re
from pathlib import Path

from paths import GAME_INSTALL_DIR

TARGET = re.compile(r'(?m)^@auto_qol_ascension_slot_target = \d+$')


def resolve_slot_cap(mod_dirs=()):
    # Same-path files are replaced by later mods; distinct files load by name.
    files = {}
    for root in (GAME_INSTALL_DIR, *mod_dirs):
        for path in (Path(root) / 'common/defines').glob('*.txt'):
            files[path.name] = path
    cap = None
    for name in sorted(files):
        text = files[name].read_text(encoding='utf-8-sig')
        text = re.sub(r'#[^\n]*', '', text)
        for match in re.finditer(r'\bASCENSION_PERKS_SLOTS\s*=\s*(\d+)', text):
            cap = int(match[1])
    if cap is None or not 1 <= cap <= 4096:
        raise ValueError(f'Unrecognized existing ascension slot cap: {cap}')
    return cap


def configure_slot_cap(output_root, mod_dirs=()):
    cap = resolve_slot_cap(mod_dirs)
    path = Path(output_root) / 'events/auto_qol_ascension_events.txt'
    text, count = TARGET.subn(f'@auto_qol_ascension_slot_target = {cap}', path.read_text(encoding='utf-8-sig'))
    if count != 1:
        raise ValueError('Expected exactly one ascension slot target')
    path.write_text(text, encoding='utf-8')
    return cap

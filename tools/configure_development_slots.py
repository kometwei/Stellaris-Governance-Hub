"""Refresh the development AP default from the currently enabled playset."""
import argparse
from pathlib import Path
import shutil

from ascension_slots import configure_slot_cap
from build_release_profiles import get_active_mod_records, is_enhancer_record
from build_species_ascension_gui import build

ROOT = Path(__file__).resolve().parents[1]


def refresh(install=False):
    active_dirs = [
        Path(record['mod_path']) for record in get_active_mod_records()
        if not is_enhancer_record(record)
    ]
    cap = configure_slot_cap(ROOT, active_dirs)
    build(ROOT)
    if install:
        destination = ROOT.parent / 'Stellaris Mod Enhancer'
        if not (destination / 'descriptor.mod').is_file():
            raise FileNotFoundError(f'Development installation not found: {destination}')
        for filename in ('auto_qol_ascension_events.txt', 'auto_qol_ascension_gui_events.txt'):
            shutil.copy2(ROOT / 'events' / filename, destination / 'events' / filename)
    return cap


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--install', action='store_true', help='Also update the installed development copy.')
    args = parser.parse_args()
    cap = refresh(args.install)
    print(f'Development ascension slot cap: {cap}; initial target: {max(1, cap // 2)}')

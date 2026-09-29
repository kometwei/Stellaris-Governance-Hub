import os, re
from pathlib import Path
from paths import GAME_INSTALL_DIR, WORKSHOP_MOD_DIR

for p in [GAME_INSTALL_DIR / 'localisation' / 'simp_chinese', WORKSHOP_MOD_DIR]:
    for f in p.glob('**/*simp_chinese*.yml'):
        try:
            with open(f, 'r', encoding='utf-8-sig', errors='ignore') as fp:
                for line in fp:
                    if '敌意' in line and ('tradition' in line or 'tr_' in line):
                        print(f.name, ':', line.strip())
        except Exception:
            pass

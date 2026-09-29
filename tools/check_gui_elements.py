import re
from pathlib import Path
from paths import WORKSHOP_MOD_DIR

p = WORKSHOP_MOD_DIR / '1747099270' / 'interface' / 'wsg_dialogue.gui'
if p.exists():
    text = p.read_text(encoding='utf-8')
    idx = text.find('ALL OF THIS IS HIDDEN OR DISPLACED')
    if idx != -1:
        print(text[idx:idx+2500])
else:
    print(f"File not found: {p}")

import re, sys
from pathlib import Path
from paths import LOCALISATION_DIR
sys.stdout.reconfigure(encoding='utf-8')

loc_path = LOCALISATION_DIR / 'auto_qol_l_simp_chinese.yml'
text = loc_path.read_text(encoding='utf-8')

for m in re.finditer(r'(tr_node_o\w+:[0-9]\s*"[^"]+")', text):
    print(m.group(1))
    if 'tr_sh_icebreaking_3' in m.group(1):
        break

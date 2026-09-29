import os, re
from pathlib import Path
from paths import WORKSHOP_MOD_DIR

for root, dirs, files in os.walk(WORKSHOP_MOD_DIR):
    if 'descriptor.mod' in files:
        p = os.path.join(root, 'descriptor.mod')
        try:
            with open(p, 'r', encoding='utf-8', errors='ignore') as f:
                c = f.read()
                m = re.search(r'name\s*=\s*"([^"]+)"', c)
                if m:
                    name = m.group(1)
                    if 'council' in name.lower() or '内阁' in name or '职位' in name:
                        print(os.path.basename(root), ':', name)
        except Exception:
            pass

import glob, re
from paths import GAME_INSTALL_DIR

buttons = set()
for f in glob.glob(str(GAME_INSTALL_DIR / 'interface' / '*.gfx')):
    with open(f, 'r', encoding='utf-8', errors='ignore') as fp:
        t = fp.read()
    for m in re.finditer(r'name\s*=\s*"(GFX_\w*button\w*)"', t):
        buttons.add(m.group(1))

for b in sorted(buttons):
    if any(k in b for k in ['200', '240', '250', '265', 'large', '300', '350', '400', '450', '460', '500']):
        print(b)

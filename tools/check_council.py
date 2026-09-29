import zipfile, re, sys
from pathlib import Path
from paths import DOCS_DIR

save_path = None
if len(sys.argv) > 1:
    save_path = Path(sys.argv[1])
else:
    saves = list((DOCS_DIR / "save games").glob("**/*.sav"))
    if saves:
        save_path = max(saves, key=lambda f: f.stat().st_mtime)

if not save_path or not save_path.exists():
    print("No save games found in Stellaris documents directory.")
    sys.exit(0)

print(f"Inspecting save game: {save_path.name}")
with zipfile.ZipFile(save_path, 'r') as z:
    with z.open('gamestate') as f:
        content = f.read().decode('utf-8', errors='ignore')

# Find player
pm = re.search(r'player=\{\s*name=\"[^\"]*\"\s*country=(\d+)', content)
if pm:
    pid = pm.group(1)
    print(f"Player country ID: {pid}")
    # find that country definition
    cm = re.search(r'\n\t' + pid + r'=\{(.*?)\n\t\d+=\{', content, re.DOTALL)
    if cm:
        ctext = cm.group(1)
        # find positions
        pos = re.findall(r'position=\"?([a-zA-Z0-9_]+)\"?', ctext)
        print("Positions:", set(pos))
        # check council
        for line in ctext.splitlines():
            if 'council' in line or 'civic' in line:
                print(line.strip())

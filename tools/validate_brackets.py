import glob, sys

def check_brackets(file_path):
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    
    clean = []
    in_string = False
    for line in content.splitlines():
        line_clean = ''
        i = 0
        while i < len(line):
            ch = line[i]
            if ch == '"':
                in_string = not in_string
            elif ch == '#' and not in_string:
                break
            if not in_string:
                line_clean += ch
            i += 1
        clean.append(line_clean)
    
    clean_str = '\n'.join(clean)
    opens = clean_str.count('{')
    closes = clean_str.count('}')
    if opens != closes:
        return f"{file_path}: Brackets mismatch! {{ = {opens}, }} = {closes}"
    return None

from paths import MOD_ROOT

errors = []
for ext in ['**/*.txt', '**/*.gui']:
    for f in glob.glob(str(MOD_ROOT / ext), recursive=True):
        if 'workshop' in f or '.git' in f or 'tools' in f: 
            continue
        err = check_brackets(f)
        if err:
            errors.append(err)

if errors:
    print('FOUND ERRORS:')
    for e in errors:
        print(e)
    sys.exit(1)
else:
    print('ALL .txt AND .gui FILES HAVE PERFECT BRACKET BALANCES!')

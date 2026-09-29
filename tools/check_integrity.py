import os, glob

print("Checking YAML files...")
for yml in glob.glob('localisation/**/*.yml', recursive=True):
    with open(yml, 'rb') as f:
        b = f.read(6)
        if not b.startswith(b'\xef\xbb\xbf'):
            print(f'Missing BOM: {yml}')
        elif b.startswith(b'\xef\xbb\xbf\xef\xbb\xbf'):
            print(f'Double BOM: {yml}')
    with open(yml, 'r', encoding='utf-8-sig') as f:
        lines = f.readlines()
        if not lines or not lines[0].strip().startswith('l_simp_chinese:'):
            print(f'First line issue: {yml}')

print("Checking TXT brackets...")
files = glob.glob('events/**/*.txt', recursive=True) + glob.glob('common/**/*.txt', recursive=True)
for txt in files:
    with open(txt, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
        opens = content.count('{')
        closes = content.count('}')
        if opens != closes:
            print(f'Bracket mismatch in {txt}: opens={opens}, closes={closes}')

print("All integrity checks completed!")

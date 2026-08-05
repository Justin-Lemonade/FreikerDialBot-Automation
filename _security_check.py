import re, os

files_to_check = [
    'ai_parser.py',
    'tests/test_ai_parser.py',
    'BACKLOG.md',
    'PROJECT_STATUS.md',
]

patterns = {
    'OpenAI API key (sk-)': r'sk-[a-zA-Z0-9]{20,}',
    'GitHub token (ghp_)': r'ghp_[a-zA-Z0-9]{36,}',
    'JWT token': r'eyJ[a-zA-Z0-9_-]+\.eyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+',
}

all_clean = True
for f in files_to_check:
    if not os.path.exists(f):
        print(f'  SKIP: {f} (not found)')
        continue
    content = open(f, 'r', encoding='utf-8').read()
    found = False
    for name, pattern in patterns.items():
        matches = re.findall(pattern, content)
        if matches:
            print(f'  WARNING: {f} contains possible {name}: {matches[:3]}')
            found = True
            all_clean = False
    if not found:
        print(f'  OK: {f} - no secrets found')

print()
if all_clean:
    print('SECURITY CHECK PASSED: No secrets found in any changed files.')
else:
    print('SECURITY CHECK FAILED: Secrets found! Review above.')

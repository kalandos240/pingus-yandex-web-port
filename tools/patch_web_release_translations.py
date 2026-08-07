from pathlib import Path
import ast
import re
from web_ru_release_fixes import WEB_RU_RELEASE_FIXES

p = Path('data/po/ru.po')
text = p.read_text(encoding='utf-8')


def po_quote(value: str) -> str:
    return value.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')


def po_value(lines, key):
    for i, line in enumerate(lines):
        if line.startswith(key + ' '):
            parts = [line[len(key) + 1:]]
            j = i + 1
            while j < len(lines) and lines[j].startswith('"'):
                parts.append(lines[j])
                j += 1
            try:
                return ''.join(ast.literal_eval(part) for part in parts)
            except Exception:
                return None
    return None

blocks = re.split(r'\n\s*\n', text)
found = set()
for i, block in enumerate(blocks):
    lines = block.splitlines()
    msgid = po_value(lines, 'msgid')
    if not msgid:
        continue
    key = msgid.strip()
    if key not in WEB_RU_RELEASE_FIXES:
        continue
    found.add(key)
    start = next(j for j, line in enumerate(lines) if line.startswith('msgstr '))
    end = start + 1
    while end < len(lines) and lines[end].startswith('"'):
        end += 1
    lines[start:end] = ['msgstr "' + po_quote(WEB_RU_RELEASE_FIXES[key]) + '"']
    blocks[i] = '\n'.join(lines)

text = '\n\n'.join(blocks).rstrip() + '\n'
for key, translated in WEB_RU_RELEASE_FIXES.items():
    if key in found:
        continue
    text += '\nmsgid "' + po_quote(key) + '"\nmsgstr "' + po_quote(translated) + '"\n'

p.write_text(text, encoding='utf-8')
print(f'Web RU: applied {len(WEB_RU_RELEASE_FIXES)} final shipped-data translations')

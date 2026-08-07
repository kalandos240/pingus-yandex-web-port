from pathlib import Path
import ast
import re

po_path = Path('data/po/ru.po')
ru_text = po_path.read_text(encoding='utf-8')


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

translations = {}
for block in re.split(r'\n\s*\n', ru_text):
    lines = block.splitlines()
    msgid = po_value(lines, 'msgid')
    msgstr = po_value(lines, 'msgstr')
    if msgid:
        translations[msgid.strip()] = (msgstr or '').strip()

# These are the actual string-bearing fields that the runtime translates and
# displays to a player. This audit deliberately reads the shipped 0.7.6 data,
# not PO reference comments, so strings missing from the historical POT/PO are
# caught as well.
checks = []
patterns = {
    'data/levels': ('levelname', 'description'),
    'data/levelsets': ('title', 'description'),
    'data/stories': ('title', 'text'),
}
for root, keys in patterns.items():
    for path in Path(root).rglob('*'):
        if not path.is_file():
            continue
        text = path.read_text(encoding='utf-8', errors='replace')
        for key in keys:
            for match in re.finditer(r'\(' + re.escape(key) + r'\s+"((?:\\.|[^"\\])*)"\)', text):
                raw = bytes(match.group(1), 'utf-8').decode('unicode_escape') if '\\' in match.group(1) else match.group(1)
                raw = raw.strip()
                if raw:
                    checks.append((raw, f'{path}:{key}'))

# Worldmap head metadata plus story-dot labels are visible, while graph/object
# internal names are not.
for path in Path('data/worldmaps').rglob('*.worldmap'):
    text = path.read_text(encoding='utf-8', errors='replace')
    head = re.search(r'\(head\s+(.*?)\)\s*\(intro-story', text, re.S)
    if head:
        for key in ('name', 'description'):
            m = re.search(r'\(' + key + r'\s+"((?:\\.|[^"\\])*)"\)', head.group(1))
            if m:
                checks.append((m.group(1).strip(), f'{path}:head/{key}'))
    for block in re.finditer(r'\(storydot\s+(.*?)(?=\n\s*\((?:storydot|leveldot)|\n\s*\)\s*\(edges)', text, re.S):
        m = re.search(r'\(name\s+"((?:\\.|[^"\\])*)"\)', block.group(1))
        if m:
            checks.append((m.group(1).strip(), f'{path}:storydot/name'))

missing = []
for text, origin in checks:
    if not translations.get(text):
        missing.append((text, origin))

# Deduplicate while keeping one useful origin.
uniq = {}
for text, origin in missing:
    uniq.setdefault(text, origin)

print(f'ACTUAL_VISIBLE_STRINGS={len(set(text for text, _ in checks))}')
print(f'UNTRANSLATED_ACTUAL_VISIBLE={len(uniq)}')
for text, origin in sorted(uniq.items()):
    print(f'UNTRANSLATED_ACTUAL: {text.replace(chr(10), "\\n")} || {origin}')
if uniq:
    raise SystemExit('actual shipped player-facing data still contains untranslated strings')

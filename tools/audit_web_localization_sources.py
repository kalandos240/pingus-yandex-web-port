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


def quoted_fields(text, keys):
    for key in keys:
        for match in re.finditer(r'\(' + re.escape(key) + r'\s+"((?:\\.|[^"\\])*)"\)', text):
            raw = match.group(1).replace('\\n', '\n').replace('\\"', '"').strip()
            if raw:
                yield key, raw

checks = []
visible_level_files = set()

# Only non-developer levelsets are exposed by LevelMenu. Audit their own labels
# and collect exactly the levels a normal Yandex player can open.
for path in Path('data/levelsets').glob('*.levelset'):
    text = path.read_text(encoding='utf-8', errors='replace')
    if re.search(r'\(developer-only\s+#t\)', text):
        continue
    for key, raw in quoted_fields(text, ('title', 'description')):
        checks.append((raw, f'{path}:{key}'))
    for m in re.finditer(r'\(filename\s+"([^"]+)"\)', text):
        visible_level_files.add(m.group(1).strip())

# Tutorial Island is entered through Story/worldmap rather than LevelMenu.
tutorial_map = Path('data/worldmaps/tutorial.worldmap')
wm = tutorial_map.read_text(encoding='utf-8', errors='replace')
for m in re.finditer(r'\(levelname\s+"([^"]+)"\)', wm):
    visible_level_files.add(m.group(1).strip())

# Audit actual title/description strings for those playable levels only.
for name in sorted(visible_level_files):
    candidates = [Path('data/levels') / (name + '.pingus'), Path('data/levels') / name]
    path = next((p for p in candidates if p.is_file()), None)
    if path is None:
        # Some old levelset entries already include extensions/alternate paths;
        # this is a data validity issue, not a localization string.
        continue
    text = path.read_text(encoding='utf-8', errors='replace')
    for key, raw in quoted_fields(text, ('levelname', 'description')):
        checks.append((raw, f'{path}:{key}'))

# Both tutorial stories are reachable. Their title/text fields are translated
# by WorldmapStory at runtime.
for path in (Path('data/stories/tutorial_intro.story'), Path('data/stories/tutorial_outro.story')):
    text = path.read_text(encoding='utf-8', errors='replace')
    for key, raw in quoted_fields(text, ('title', 'text')):
        checks.append((raw, f'{path}:{key}'))

# Tutorial map head and story-dot names are visible. Do not audit graph/object
# IDs or author/email metadata because they are not drawn to the player.
head = re.search(r'\(head\s+(.*?)\)\s*\(intro-story', wm, re.S)
if head:
    for key, raw in quoted_fields(head.group(1), ('name', 'description')):
        checks.append((raw, f'{tutorial_map}:head/{key}'))
for raw in ('Continue Journey', 'Watch Intro'):
    if raw in wm:
        checks.append((raw, f'{tutorial_map}:storydot/name'))

uniq_missing = {}
for text, origin in checks:
    if not translations.get(text):
        uniq_missing.setdefault(text, origin)

print(f'RELEASE_VISIBLE_LEVELS={len(visible_level_files)}')
print(f'ACTUAL_VISIBLE_STRINGS={len(set(text for text, _ in checks))}')
print(f'UNTRANSLATED_ACTUAL_VISIBLE={len(uniq_missing)}')
for text, origin in sorted(uniq_missing.items()):
    print(f'UNTRANSLATED_ACTUAL: {text.replace(chr(10), "\\n")} || {origin}')
if uniq_missing:
    raise SystemExit('releasable player-facing data still contains untranslated strings')

from pathlib import Path
import re

# Static release audit for Yandex requirements 3.4.2/3.4.4/3.4.5, 3.5 and
# 8.2.4. Check only content a normal non-developer player can reach: public
# levelsets, their levels, Tutorial Story/worldmap text and high-risk visible
# asset references. Hidden developer packs and source comments are excluded.

RISK_PATTERNS = {
    'esoterics': re.compile(r'\b(?:astrolog(?:y|er|ical)|horoscope|fortune[- ]?tell|tarot|divination|séance|seance|witch|witchcraft|wizard|wizardry|sorcer(?:y|er)|magic|magical|curse|cursed|occult|voodoo|pentagram)\b', re.I),
    'politics-war': re.compile(r'\b(?:politic(?:s|al)|president|government|parliament|election|military|army|soldier|war|warfare|invasion)\b', re.I),
    'religion': re.compile(r'\b(?:god|holy|christmas|xmas|jesus|christ|christian|church|bible|priest|pope|religion|religious|angel|mosque|islam|allah|quran|satan|devil|heaven|hell|pray|prayer|bless(?:ed|ing)?|armageddon)\b', re.I),
    'third-party-reference': re.compile(r'\b(?:indiana\s+jones|dr\.?\s+jones|super\s+mario|pac-?man|sonic\s+the\s+hedgehog|lemmings)\b', re.I),
    'profanity': re.compile(r'\b(?:fuck|fucking|shit|bitch|cunt|motherfucker)\b', re.I),
}

# File paths are not player-facing, but some names identify visual assets that
# are themselves likely prohibited. Generic legacy folders such as
# ground/halloween are not rejected here because their reachable assets were
# visually reviewed as plain trees/ground/signs; explicit symbols are rejected.
VISUAL_RISK = re.compile(
    r'(?i)(?:xmas|christmas|church|crucifix|cross(?:[-_/]|$)|pentagram|witch|wizard|tarot|occult|satan|devil|demon|holy|angel)'
)


def quoted_fields(text, keys):
    for key in keys:
        for match in re.finditer(r'\(' + re.escape(key) + r'\s+"((?:\\.|[^"\\])*)"\)', text):
            value = match.group(1).replace('\\n', '\n').replace('\\"', '"').strip()
            if value:
                yield key, value

visible_level_files = set()
checks = []
visual_refs = []
for path in Path('data/levelsets').glob('*.levelset'):
    text = path.read_text(encoding='utf-8', errors='replace')
    if re.search(r'\(developer-only\s+#t\)', text):
        continue
    for key, value in quoted_fields(text, ('title', 'description')):
        checks.append((value, f'{path}:{key}'))
    for match in re.finditer(r'\(filename\s+"([^"]+)"\)', text):
        visible_level_files.add(match.group(1).strip())

tutorial_map = Path('data/worldmaps/tutorial.worldmap')
wm = tutorial_map.read_text(encoding='utf-8', errors='replace')
for match in re.finditer(r'\(levelname\s+"([^"]+)"\)', wm):
    visible_level_files.add(match.group(1).strip())
head = re.search(r'\(head\s+(.*?)\)\s*\(intro-story', wm, re.S)
if head:
    for key, value in quoted_fields(head.group(1), ('name', 'description')):
        checks.append((value, f'{tutorial_map}:head/{key}'))
for value in ('Continue Journey', 'Watch Intro'):
    if value in wm:
        checks.append((value, f'{tutorial_map}:storydot/name'))

missing_levels = []
for name in sorted(visible_level_files):
    candidates = [Path('data/levels') / (name + '.pingus'), Path('data/levels') / name]
    path = next((p for p in candidates if p.is_file()), None)
    if path is None:
        missing_levels.append(name)
        continue
    text = path.read_text(encoding='utf-8', errors='replace')
    for key, value in quoted_fields(text, ('levelname', 'description')):
        checks.append((value, f'{path}:{key}'))
    for key, value in quoted_fields(text, ('image',)):
        visual_refs.append((value, f'{path}:{key}'))

for path in (Path('data/stories/tutorial_intro.story'), Path('data/stories/tutorial_outro.story')):
    text = path.read_text(encoding='utf-8', errors='replace')
    for key, value in quoted_fields(text, ('title', 'text')):
        checks.append((value, f'{path}:{key}'))

hits = []
for value, origin in checks:
    for category, pattern in RISK_PATTERNS.items():
        match = pattern.search(value)
        if match:
            hits.append((category, match.group(0), value, origin))
for value, origin in visual_refs:
    match = VISUAL_RISK.search(value)
    if match:
        hits.append(('visual-reference', match.group(0), value, origin))

print(f'YANDEX_CONTENT_VISIBLE_LEVELS={len(visible_level_files)}')
print(f'YANDEX_CONTENT_MISSING_LEVEL_FILES={len(missing_levels)}')
for name in missing_levels:
    print(f'YANDEX_CONTENT_MISSING_LEVEL: {name}')
print(f'YANDEX_CONTENT_TEXTS_CHECKED={len(checks)}')
print(f'YANDEX_CONTENT_VISUAL_REFS_CHECKED={len(visual_refs)}')
print(f'YANDEX_CONTENT_RISK_HITS={len(hits)}')
for category, token, value, origin in hits:
    printable = value.replace('\n', '\\n')
    print(f'YANDEX_CONTENT_RISK: {category} token={token!r} text={printable!r} origin={origin}')
if missing_levels:
    raise SystemExit('public Yandex release references missing level files')
if hits:
    raise SystemExit('reachable player-facing content contains Yandex policy risk references')

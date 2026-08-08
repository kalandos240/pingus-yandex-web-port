from pathlib import Path
import re

# Static release audit for Yandex requirements 3.4.2/3.4.4/3.4.5 and 8.2.4.
# Check only text that a normal non-developer player can actually reach: public
# levelsets, their level names/descriptions, and Tutorial Story/worldmap text.
# Hidden developer packs and source comments are deliberately excluded.

RISK_PATTERNS = {
    'esoterics': re.compile(r'\b(?:astrolog(?:y|er|ical)|horoscope|fortune[- ]?tell|tarot|divination|séance|seance)\b', re.I),
    'politics-war': re.compile(r'\b(?:politic(?:s|al)|president|government|parliament|election|military|army|soldier|war|warfare|invasion)\b', re.I),
    'religion': re.compile(r'\b(?:christmas|xmas|jesus|christ|christian|church|bible|priest|pope|religion|religious|mosque|islam|allah|quran|satan|devil|heaven|hell)\b', re.I),
    'profanity': re.compile(r'\b(?:fuck|fucking|shit|bitch|cunt|motherfucker)\b', re.I),
}


def quoted_fields(text, keys):
    for key in keys:
        for match in re.finditer(r'\(' + re.escape(key) + r'\s+"((?:\\.|[^"\\])*)"\)', text):
            value = match.group(1).replace('\\n', '\n').replace('\\"', '"').strip()
            if value:
                yield key, value

visible_level_files = set()
checks = []
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

for name in sorted(visible_level_files):
    candidates = [Path('data/levels') / (name + '.pingus'), Path('data/levels') / name]
    path = next((p for p in candidates if p.is_file()), None)
    if path is None:
        continue
    text = path.read_text(encoding='utf-8', errors='replace')
    for key, value in quoted_fields(text, ('levelname', 'description')):
        checks.append((value, f'{path}:{key}'))

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

print(f'YANDEX_CONTENT_VISIBLE_LEVELS={len(visible_level_files)}')
print(f'YANDEX_CONTENT_TEXTS_CHECKED={len(checks)}')
print(f'YANDEX_CONTENT_RISK_HITS={len(hits)}')
for category, token, value, origin in hits:
    printable = value.replace('\n', '\\n')
    print(f'YANDEX_CONTENT_RISK: {category} token={token!r} text={printable!r} origin={origin}')
if hits:
    raise SystemExit('reachable player-facing text contains Yandex content-policy risk terms')

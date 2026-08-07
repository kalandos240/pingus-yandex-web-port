from pathlib import Path
import ast
import re
import urllib.request

from web_ru_full import WEB_RU_FULL, WEB_RU_CUSTOM

# Yandex Games release policy for this port: the platform locale selects either
# Russian or English. English is Pingus' source language and does not need a .po
# file, so keep only ru.po in the embedded translation directory.
po_dir = Path('data/po')
if not po_dir.is_dir():
    raise SystemExit('Pingus po directory not found')

# Pingus 0.7.6 shipped with an unfinished 2011 Russian catalog. The upstream
# Pingus repository later completed many translations without changing the
# underlying 0.7.6 gameplay strings. Pin that catalog to a specific upstream
# commit so this Web build is reproducible rather than following moving master.
RU_UPSTREAM_COMMIT = '11a27787d0655d9f9de63b814c97385fa7b45a7a'
RU_URL = f'https://raw.githubusercontent.com/Pingus/pingus/{RU_UPSTREAM_COMMIT}/data/po/ru.po'
try:
    with urllib.request.urlopen(RU_URL, timeout=30) as response:
        ru_text = response.read().decode('utf-8')
except Exception as error:
    raise SystemExit(f'failed to download pinned upstream ru.po: {error}')
if 'Language: ru' not in ru_text or 'msgid "Story"' not in ru_text:
    raise SystemExit('downloaded ru.po did not look like the expected Russian Pingus catalog')

# Player-facing Web overrides. Some fill still-empty upstream entries; a few
# deliberately shorten translations so they fit the original fixed-size UI.
WEB_RU = {
    'Levelsets': 'Уровни',
    'Option Menu': 'Настройки',
    'Master Volume:': 'Общая:',
    'Sound Volume:': 'Звуки:',
    'Music Volume:': 'Музыка:',
    'Play': 'Играть',
    'Back': 'Назад',
    'Give up': 'Сдаться',
    'Number of Pingus:': 'Всего пингусов:',
    'Number to Save:': 'Нужно спасти:',
    'Under Construction': 'В разработке',
    'Untested, unpolished and broken levels': 'Непроверенные и незавершённые уровни',
    'Show Ending?': 'Показать финал?',
    'Basher': 'Проходчик',
    'Blocker': 'Блокировщик',
    'Bomber': 'Подрывник',
    'Bridger': 'Мостостроитель',
    'Exiter': 'Выходящий',
    'Faller': 'Падающий',
    'Floater': 'Парашютист',
    'Laserkill': 'Лазер',
    'Slider': 'Скользящий',
    'Smashed': 'Разбившийся',
    'Splashed': 'Утонувший',
    'Teleported': 'Телепортирован',
    'Waiter': 'Ожидающий',
    'Walker': 'Идущий',
    'Released:%3d/%d   Out:%3d   Saved:%3d/%d': 'Вышло:%3d/%d   Идут:%3d   Спасено:%3d/%d',
}
WEB_RU.update(WEB_RU_FULL)


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
            value = ''
            for part in parts:
                try:
                    value += ast.literal_eval(part)
                except Exception:
                    return None
            return value
    return None


def replace_msgstr(block, translated):
    lines = block.splitlines()
    start = next((i for i, line in enumerate(lines) if line.startswith('msgstr ')), None)
    if start is None:
        raise SystemExit('PO block has no msgstr')
    end = start + 1
    while end < len(lines) and lines[end].startswith('"'):
        end += 1
    lines[start:end] = ['msgstr "' + po_quote(translated) + '"']
    return '\n'.join(lines)

# Rewrite both single-line and multiline PO entries. Match after strip() so old
# level files with harmless trailing spaces do not lose their translations.
blocks = re.split(r'\n\s*\n', ru_text)
matched = set()
for i, block in enumerate(blocks):
    lines = block.splitlines()
    msgid = po_value(lines, 'msgid')
    if not msgid:
        continue
    key = msgid.strip()
    if key in WEB_RU:
        blocks[i] = replace_msgstr(block, WEB_RU[key])
        matched.add(key)

missing_overrides = sorted(set(WEB_RU) - matched)
if missing_overrides:
    raise SystemExit('Russian override msgids missing from pinned catalog: ' + repr(missing_overrides))
ru_text = '\n\n'.join(blocks).rstrip() + '\n'

# Web-only cleanup changes two English source labels to versions without author
# names. They do not exist in the historical PO, so append explicit RU entries.
for msgid, msgstr in WEB_RU_CUSTOM.items():
    ru_text += '\nmsgid "' + po_quote(msgid) + '"\nmsgstr "' + po_quote(msgstr) + '"\n'

# Audit all player-facing PO entries. This intentionally excludes editor,
# command-line/debug and screenshot diagnostics that are not reachable in the
# Yandex build. A blank Russian translation here is a release blocker.
PLAYER_REFS = (
    'src/pingus/screens/',
    'src/pingus/worldmap/',
    'src/pingus/action_name.cpp',
    'src/pingus/components/',
    'src/pingus/game_time.cpp',
    'data/levels/',
    'data/levelsets/',
    'data/stories/',
    'data/worldmaps/',
)
missing = []
for block in re.split(r'\n\s*\n', ru_text):
    lines = block.splitlines()
    refs = ' '.join(line[2:].strip() for line in lines if line.startswith('#:'))
    if not refs or not any(prefix in refs for prefix in PLAYER_REFS):
        continue
    msgid = po_value(lines, 'msgid')
    msgstr = po_value(lines, 'msgstr')
    if msgid and msgstr == '':
        missing.append((msgid, refs))

if missing:
    print(f'UNTRANSLATED_PLAYER_FACING={len(missing)}')
    for msgid, refs in missing:
        printable = msgid.replace('\n', '\\n')
        print(f'UNTRANSLATED: {printable} || {refs}')
    raise SystemExit('player-facing Russian catalog still contains untranslated strings')
print('UNTRANSLATED_PLAYER_FACING=0')

(po_dir / 'ru.po').write_text(ru_text, encoding='utf-8')

removed = []
for po in po_dir.glob('*.po'):
    if po.name != 'ru.po':
        po.unlink()
        removed.append(po.name)

# A language chosen in an older desktop-style Web build can be stored in
# ~/.pingus/config. On Web, always re-derive the final dictionary language from
# the ru/en locale supplied by the browser shell/Yandex SDK.
p = Path('src/pingus/pingus_main.cpp')
s = p.read_text(encoding='utf-8')
old = '''  // Misc\n  if (options.language.is_set())\n    dictionary_manager.set_language(tinygettext::Language::from_name(options.language.get()));'''
new = '''  // Misc\n#ifdef __EMSCRIPTEN__\n  dictionary_manager.set_language(tinygettext::Language::from_env(System::get_language()));\n#else\n  if (options.language.is_set())\n    dictionary_manager.set_language(tinygettext::Language::from_name(options.language.get()));\n#endif'''
if s.count(old) != 1:
    raise SystemExit('PingusMain language override anchor missing or duplicated')
s = s.replace(old, new, 1)
p.write_text(s, encoding='utf-8')

p = Path('src/pingus/config_manager.cpp')
s = p.read_text(encoding='utf-8')
old = '''  if (opts.language.is_set())\n    set_language(tinygettext::Language::from_env(opts.language.get()));'''
new = '''#ifdef __EMSCRIPTEN__\n  set_language(tinygettext::Language::from_env(System::get_language()));\n#else\n  if (opts.language.is_set())\n    set_language(tinygettext::Language::from_env(opts.language.get()));\n#endif'''
if s.count(old) != 1:
    raise SystemExit('ConfigManager language override anchor missing or duplicated')
s = s.replace(old, new, 1)
p.write_text(s, encoding='utf-8')

remaining = sorted(x.name for x in po_dir.glob('*.po'))
if remaining != ['ru.po']:
    raise SystemExit(f'unexpected Web translation set: {remaining}')
print(
    f'Web translations: ru + built-in English; '
    f'pinned ru={RU_UPSTREAM_COMMIT[:8]}; removed {len(removed)} other .po files'
)

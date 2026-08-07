from pathlib import Path
import re
import urllib.request

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

# Fill a small number of still-empty, player-facing strings in that upstream
# catalog. This avoids visibly mixed English/Russian UI in the Yandex build.
# Only strings present in original Pingus 0.7.6 are touched.
WEB_RU = {
    'Option Menu': 'Настройки',
    'Play': 'Играть',
    'Back': 'Назад',
    'Give up': 'Сдаться',
    'Number of Pingus: ': 'Всего пингусов: ',
    'Number to Save: ': 'Нужно спасти: ',
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

def po_quote(value: str) -> str:
    return value.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')

for msgid, translated in WEB_RU.items():
    pattern = re.compile(
        r'(?m)^msgid "' + re.escape(po_quote(msgid)) + r'"\nmsgstr ""$',
    )
    ru_text, count = pattern.subn(
        'msgid "' + po_quote(msgid) + '"\nmsgstr "' + po_quote(translated) + '"',
        ru_text,
        count=1,
    )
    # Some strings may already be translated upstream; that is fine. But if
    # the msgid is absent entirely, fail because the pinned catalog changed.
    if count == 0 and f'msgid "{po_quote(msgid)}"' not in ru_text:
        raise SystemExit(f'expected Russian catalog msgid missing: {msgid!r}')

(po_dir / 'ru.po').write_text(ru_text, encoding='utf-8')

removed = []
for po in po_dir.glob('*.po'):
    if po.name != 'ru.po':
        po.unlink()
        removed.append(po.name)

# A language chosen in an older desktop-style Web build can be stored in
# ~/.pingus/config. Pingus reads that file after selecting LANG from the
# environment, and both PingusMain::apply_args() and ConfigManager::apply()
# would otherwise overwrite the Yandex locale with that stale value. On Web,
# always re-derive the dictionary language from LANG/LC_ALL instead.
p = Path('src/pingus/pingus_main.cpp')
s = p.read_text(encoding='utf-8')
old = '''  // Misc\n  if (options.language.is_set())\n    dictionary_manager.set_language(tinygettext::Language::from_name(options.language.get()));'''
new = '''  // Misc\n#ifdef __EMSCRIPTEN__\n  // The browser shell normalizes the platform locale to ru/en and sets LANG\n  // before main(). Ignore a stale language saved by older Web builds.\n  dictionary_manager.set_language(tinygettext::Language::from_env(System::get_language()));\n#else\n  if (options.language.is_set())\n    dictionary_manager.set_language(tinygettext::Language::from_name(options.language.get()));\n#endif'''
if s.count(old) != 1:
    raise SystemExit('PingusMain language override anchor missing or duplicated')
s = s.replace(old, new, 1)
p.write_text(s, encoding='utf-8')

p = Path('src/pingus/config_manager.cpp')
s = p.read_text(encoding='utf-8')
old = '''  if (opts.language.is_set())\n    set_language(tinygettext::Language::from_env(opts.language.get()));'''
new = '''#ifdef __EMSCRIPTEN__\n  // ConfigManager::apply() runs after PingusMain::apply_args(). Clamp the final\n  // language here as well so a legacy config can never override Yandex ru/en.\n  set_language(tinygettext::Language::from_env(System::get_language()));\n#else\n  if (opts.language.is_set())\n    set_language(tinygettext::Language::from_env(opts.language.get()));\n#endif'''
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

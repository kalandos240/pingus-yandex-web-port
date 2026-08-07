from pathlib import Path

# Yandex Games release policy for this port: the platform locale selects either
# Russian or English. English is Pingus' source language and does not need a .po
# file, so keep only ru.po in the embedded translation directory. This also
# prevents the desktop Options menu/config from exposing dozens of irrelevant
# locales in the browser build.
po_dir = Path('data/po')
if not po_dir.is_dir():
    raise SystemExit('Pingus po directory not found')

removed = []
for po in po_dir.glob('*.po'):
    if po.name != 'ru.po':
        po.unlink()
        removed.append(po.name)

if not (po_dir / 'ru.po').is_file():
    raise SystemExit('Russian translation ru.po is missing')

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
print(f'Web translations: ru + built-in English; removed {len(removed)} other .po files')

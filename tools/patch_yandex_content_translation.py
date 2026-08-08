from pathlib import Path

po = Path('data/po/ru.po')
if not po.is_file():
    raise SystemExit('Russian Web PO is missing')
text = po.read_text(encoding='utf-8')

entries = {
    "Miner's Dream": "Мечта шахтёра",
    "The more levels you master, the more difficult they will get, but don't panic, as this one is still pretty easy. Just use the stuff that you've learned in the previous levels and you shouldn't have many problems. If you think you've reached a situation from which you can no longer solve the level, double click the restart button at the lower right.":
        "Чем дальше, тем сложнее уровни, но этот всё ещё довольно простой. Используйте уже изученные способности. Если уровень оказался в безвыходном состоянии, дважды нажмите кнопку перезапуска справа внизу и начните заново.",
}


def po_quote(value: str) -> str:
    return value.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')

added = 0
for source, translated in entries.items():
    marker = 'msgid "' + po_quote(source) + '"'
    if marker in text:
        continue
    text = text.rstrip() + '\n\n# Web/Yandex-safe player-facing wording.\n' \
        + marker + '\nmsgstr "' + po_quote(translated) + '"\n'
    added += 1

po.write_text(text, encoding='utf-8')
print(f'Web RU: added {added} Yandex-safe translation entries')

from pathlib import Path

po = Path('data/po/ru.po')
if not po.is_file():
    raise SystemExit('Russian Web PO is missing')
text = po.read_text(encoding='utf-8')
msgid = 'msgid "Miner\'s Dream"'
if msgid not in text:
    text = text.rstrip() + '\n\n# Web/Yandex-safe title replacing the original "Miner\'s heaven".\n' \
        + msgid + '\nmsgstr "Мечта шахтёра"\n'
    po.write_text(text, encoding='utf-8')
print("Web RU: added Yandex-safe translation for 'Miner's Dream'")

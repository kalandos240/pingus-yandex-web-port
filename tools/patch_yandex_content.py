from pathlib import Path

# Yandex Games requirement 3.4.5 disallows references to religion and religious
# attributes. Pingus 0.7.6 ships one optional public bonus levelset titled
# "Xmas 2011" whose description says "Merry Christmas and a Happy New Year".
# It is not part of the main story and removing only its levelset descriptor
# keeps those bonus levels unreachable from the release UI while preserving the
# original core campaign and all browser-port mechanics.
xmas = Path('data/levelsets/xmas2011.levelset')
if not xmas.is_file():
    raise SystemExit('expected Pingus 0.7.6 Xmas levelset is missing')
text = xmas.read_text(encoding='utf-8')
if '(title "Xmas 2011")' not in text or '(developer-only #f)' not in text:
    raise SystemExit('unexpected Xmas levelset metadata; review content filter')
xmas.unlink()
print('Yandex content: removed public Xmas 2011 bonus levelset (religious-reference risk)')

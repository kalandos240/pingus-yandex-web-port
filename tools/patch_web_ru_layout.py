from pathlib import Path
import re

# Some correct Russian translations are much wider than the original English
# labels and collide with the right-side completion column in the fixed-size
# 2007 levelset UI. Keep the meaning but use compact Web wording.
p = Path('data/po/ru.po')
s = p.read_text(encoding='utf-8')

replacements = {
    'Merry Christmas and a Happy New Year': 'Праздничные уровни',
}

for msgid, msgstr in replacements.items():
    qid = re.escape(msgid.replace('"', '\\"'))
    pattern = re.compile(
        r'(?m)^(msgid "' + qid + r'"\nmsgstr ")[^"]*(")$'
    )
    s, count = pattern.subn(r'\1' + msgstr + r'\2', s, count=1)
    if count != 1:
        raise SystemExit(f'RU compact-layout translation entry missing: {msgid!r}')

p.write_text(s, encoding='utf-8')
print('Web RU layout: compact levelset labels applied')

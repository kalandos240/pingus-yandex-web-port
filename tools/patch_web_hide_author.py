from pathlib import Path
import re

# Keep GPL attribution in the distributed legal files, but do not expose
# author names/e-mail addresses in the player-facing Yandex Games UI.
p = Path('src/pingus/screens/start_screen.cpp')
s = p.read_text(encoding='utf-8')
old = '''  gc.print_center(Fonts::chalk_small, \n                  Vector2i(gc.get_width()/2,\n                           gc.get_height()/2 + 215),\n                  _("Author: ") + plf.get_author());\n'''
new = '''#ifndef __EMSCRIPTEN__\n  gc.print_center(Fonts::chalk_small,\n                  Vector2i(gc.get_width()/2,\n                           gc.get_height()/2 + 215),\n                  _("Author: ") + plf.get_author());\n#endif\n'''
if s.count(old) != 1:
    raise SystemExit('start-screen author UI anchor missing or duplicated')
s = s.replace(old, new, 1)
p.write_text(s, encoding='utf-8')

# A couple of original levelset labels themselves contain creator names, so
# removing the separate Author row is not enough. Strip those suffixes from the
# Web data as well. The original metadata remains available in AUTHORS/source.
replacements = {
    Path('data/levelsets/alien.levelset'): (
        '(title "Alien by Josh Dye")',
        '(title "Alien")',
    ),
    Path('data/levelsets/mysteryisland.levelset'): (
        '(description "Marooned on an Uncharted Isle [by Lachlan McCubbin]")',
        '(description "Marooned on an Uncharted Isle")',
    ),
}
for path, (old_text, new_text) in replacements.items():
    text = path.read_text(encoding='utf-8')
    if text.count(old_text) != 1:
        raise SystemExit(f'author-bearing levelset label missing: {path}')
    path.write_text(text.replace(old_text, new_text, 1), encoding='utf-8')

# One complete upstream translation is too wide for the original fixed 2007
# LevelMenu row and collides with its right-side statistics. Keep the same
# meaning in a compact Web-only form.
po = Path('data/po/ru.po')
text = po.read_text(encoding='utf-8')
pattern = re.compile(
    r'(?m)^(msgid "Merry Christmas and a Happy New Year"\nmsgstr ")[^"]*(")$'
)
text, count = pattern.subn(r'\1Праздничные уровни\2', text, count=1)
if count != 1:
    raise SystemExit('compact Xmas levelset RU translation anchor missing')
po.write_text(text, encoding='utf-8')

print('Web UI: visible author/contact metadata removed; legal attribution retained in distribution files')
print('Web RU layout: long levelset labels compacted for fixed UI')

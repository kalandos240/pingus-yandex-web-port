from pathlib import Path

# The original level metadata contains author names/e-mail addresses. Keep the
# metadata and GPL attribution in the distributed files, but do not expose
# personal author/contact strings in the player-facing Yandex Games UI.
p = Path('src/pingus/screens/start_screen.cpp')
s = p.read_text(encoding='utf-8')
old = '''  gc.print_center(Fonts::chalk_small, \n                  Vector2i(gc.get_width()/2,\n                           gc.get_height()/2 + 215),\n                  _("Author: ") + plf.get_author());\n'''
new = '''#ifndef __EMSCRIPTEN__\n  gc.print_center(Fonts::chalk_small,\n                  Vector2i(gc.get_width()/2,\n                           gc.get_height()/2 + 215),\n                  _("Author: ") + plf.get_author());\n#endif\n'''
if s.count(old) != 1:
    raise SystemExit('start-screen author UI anchor missing or duplicated')
s = s.replace(old, new, 1)
p.write_text(s, encoding='utf-8')

print('Web UI: level author/contact metadata hidden from StartScreen')

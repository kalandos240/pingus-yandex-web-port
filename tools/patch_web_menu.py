from pathlib import Path
import re

p = Path('src/pingus/screens/pingus_menu.cpp')
s = p.read_text(encoding='utf-8')

# The desktop level editor is intentionally omitted from the browser target.
# Do not leave dead Editor/Exit actions in the Yandex Games release. Center
# Story in the top row and keep Levelsets/Options below it.
s, n_start = re.subn(
    r'start_button = new MenuButton\(this, Vector2i\(size_\.width/2 - 125,\n\s*size_\.height/2 - 20\),',
    'start_button = new MenuButton(this, Vector2i(size_.width/2,\n                                               size_.height/2 - 20),',
    s,
    count=1,
)

s, n_editor_ctor = re.subn(
    r'\n  editor_button = new MenuButton\(this, Vector2i\(size_\.width/2 \+ 125,\n'
    r'\s*size_\.height/2 - 20\),\n'
    r'\s*_\("Editor"\),\n'
    r'\s*_\("\.\.:: Create your own levels ::\.\."\)\);\n',
    '\n  editor_button = 0;\n',
    s,
    count=1,
)

s, n_quit_ctor = re.subn(
    r'\n  quit_button = new MenuButton\(this, Vector2i\(size_\.width/2,\s*\n'
    r'\s*size_\.height/2 \+ 120\),\s*\n'
    r'\s*_\("Exit"\),\s*\n'
    r'\s*_\("\.\.:: Bye, bye ::\.\."\)\);\n',
    '\n  quit_button = 0;\n',
    s,
    count=1,
)

for line, label in [
    ('  gui_manager->add(editor_button);\n', 'editor'),
    ('  gui_manager->add(quit_button);\n', 'quit'),
]:
    if line not in s:
        raise SystemExit(f'web menu {label} add patch mismatch')
    s = s.replace(line, '', 1)

s, n_editor_click = re.subn(
    r'\n  else if \(button == editor_button\)\n  \{\n    do_edit\(\);\n  \}',
    '',
    s,
    count=1,
)
s, n_quit_click = re.subn(
    r'\n  else if \(button == quit_button\)\n  \{\n    do_quit\(\);\n  \}',
    '',
    s,
    count=1,
)

if (n_start, n_editor_ctor, n_quit_ctor, n_editor_click, n_quit_click) != (1, 1, 1, 1, 1):
    raise SystemExit(
        'web menu patch mismatch '
        f'{(n_start, n_editor_ctor, n_quit_ctor, n_editor_click, n_quit_click)}'
    )

# Browser players do not need desktop grab/F-key help. Keep the release clean;
# full copyright/license text remains in COPYING/AUTHORS/README in the ZIP.
old_help = '  help = _("..:: Ctrl-g: mouse grab   ::   F10: fps counter   ::   F11: fullscreen   ::   F12: screenshot ::..");'
new_help = '''#ifdef __EMSCRIPTEN__
  help.clear();
#else
  help = _("..:: Ctrl-g: mouse grab   ::   F10: fps counter   ::   F11: fullscreen   ::   F12: screenshot ::..");
#endif'''
if s.count(old_help) != 1:
    raise SystemExit('web menu desktop-help anchor missing or duplicated')
s = s.replace(old_help, new_help, 1)

# Match the complete desktop-only legal/hotkey footer by its stable first and
# last calls instead of exact whitespace. This source has changed indentation
# between historic Pingus snapshots, while the semantics stayed the same.
footer_re = re.compile(
    r'(?P<footer>  gc\.print_left\(Fonts::pingus_small, Vector2i\(gc\.get_width\(\)/2 - 400 \+ 25, gc\.get_height\(\)-140\),.*?'
    r'  gc\.print_center\(Fonts::pingus_small,\s*\n\s*Vector2i\(gc\.get_width\(\) / 2,\s*\n\s*gc\.get_height\(\) - Fonts::pingus_small\.get_height\(\) - 8\),\s*\n\s*help\);)',
    re.DOTALL,
)
m = footer_re.search(s)
if not m:
    raise SystemExit('web menu footer structure not found')
s = s[:m.start()] + '#ifndef __EMSCRIPTEN__\n' + m.group('footer') + '\n#endif' + s[m.end():]

# The removed buttons are null on Web. The original resize() still dereferenced
# them, which could crash after a browser resize/orientation change.
for pattern, label in [
    (r'\n\s*editor_button->set_pos\(size\.width/2 \+ 125,\s*\n\s*size\.height/2 - 20\);\s*', 'editor'),
    (r'\n\s*quit_button->set_pos\(size\.width/2,\s*\n\s*size\.height/2 \+ 120\);\s*', 'quit'),
]:
    s, count = re.subn(pattern, '\n', s, count=1)
    if count != 1:
        raise SystemExit(f'web menu dead {label} resize anchor missing or duplicated')

p.write_text(s, encoding='utf-8')

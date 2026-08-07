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
old_help = '''  help = _("..:: Ctrl-g: mouse grab   ::   F10: fps counter   ::   F11: fullscreen   ::   F12: screenshot ::..");'''
new_help = '''#ifdef __EMSCRIPTEN__\n  help.clear();\n#else\n  help = _("..:: Ctrl-g: mouse grab   ::   F10: fps counter   ::   F11: fullscreen   ::   F12: screenshot ::..");\n#endif'''
if s.count(old_help) != 1:
    raise SystemExit('web menu desktop-help anchor missing or duplicated')
s = s.replace(old_help, new_help, 1)

old_footer = '''  gc.print_left(Fonts::pingus_small, Vector2i(gc.get_width()/2 - 400 + 25, gc.get_height()-140),\n                "Pingus "VERSION" - Copyright (C) 1998-2011 Ingo Ruhnke <grumbel@gmail.com>\\n"\n                "See the file AUTHORS for a complete list of contributors.\\n"\n                "Pingus comes with ABSOLUTELY NO WARRANTY. This is free software, and you are\\n"\n                "welcome to redistribute it under certain conditions; see the file COPYING for details.\\n");\n\n  gc.draw_fillrect(Rect(0,\n                        Display::get_height () - 26,\n                        Display::get_width (),\n                        Display::get_height ()),\n                   Color(0, 0, 0, 255));\n\n  gc.print_center(Fonts::pingus_small, \n                  Vector2i(gc.get_width() / 2,\n                           gc.get_height() - Fonts::pingus_small.get_height() - 8),\n                  help);'''
new_footer = '''#ifndef __EMSCRIPTEN__\n  gc.print_left(Fonts::pingus_small, Vector2i(gc.get_width()/2 - 400 + 25, gc.get_height()-140),\n                "Pingus "VERSION" - Copyright (C) 1998-2011 Ingo Ruhnke <grumbel@gmail.com>\\n"\n                "See the file AUTHORS for a complete list of contributors.\\n"\n                "Pingus comes with ABSOLUTELY NO WARRANTY. This is free software, and you are\\n"\n                "welcome to redistribute it under certain conditions; see the file COPYING for details.\\n");\n\n  gc.draw_fillrect(Rect(0,\n                        Display::get_height () - 26,\n                        Display::get_width (),\n                        Display::get_height ()),\n                   Color(0, 0, 0, 255));\n\n  gc.print_center(Fonts::pingus_small, \n                  Vector2i(gc.get_width() / 2,\n                           gc.get_height() - Fonts::pingus_small.get_height() - 8),\n                  help);\n#endif'''
if s.count(old_footer) != 1:
    raise SystemExit('web menu footer anchor missing or duplicated')
s = s.replace(old_footer, new_footer, 1)

# The removed buttons are null on Web. The original resize() still dereferenced
# them, which could crash after a browser resize/orientation change.
for dead_resize in [
    '''  editor_button->set_pos(size.width/2 + 125,\n                         size.height/2 - 20);\n    \n''',
    '''  quit_button->set_pos(size.width/2, \n                       size.height/2 + 120);\n''',
]:
    if s.count(dead_resize) != 1:
        raise SystemExit('web menu dead resize anchor missing or duplicated')
    s = s.replace(dead_resize, '', 1)

p.write_text(s, encoding='utf-8')

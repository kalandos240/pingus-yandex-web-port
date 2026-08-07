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

p.write_text(s, encoding='utf-8')

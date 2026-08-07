from pathlib import Path
import re

p = Path('src/pingus/screens/pingus_menu.cpp')
s = p.read_text(encoding='utf-8')

# The desktop level editor is intentionally omitted from the browser target.
# Do not leave a dead Editor button in the Yandex Games release. Center Story
# in the vacated top row and keep Levelsets/Options below it.
s, n_start = re.subn(
    r'start_button = new MenuButton\(this, Vector2i\(size_\.width/2 - 125,\n\s*size_\.height/2 - 20\),',
    'start_button = new MenuButton(this, Vector2i(size_.width/2,\n                                               size_.height/2 - 20),',
    s,
    count=1,
)

s, n_ctor = re.subn(
    r'\n  editor_button = new MenuButton\(this, Vector2i\(size_\.width/2 \+ 125,\n'
    r'\s*size_\.height/2 - 20\),\n'
    r'\s*_\("Editor"\),\n'
    r'\s*_\("\.\.:: Create your own levels ::\.\."\)\);\n',
    '\n  editor_button = 0;\n',
    s,
    count=1,
)

if '  gui_manager->add(editor_button);\n' not in s:
    raise SystemExit('web menu editor add patch mismatch')
s = s.replace('  gui_manager->add(editor_button);\n', '', 1)

s, n_click = re.subn(
    r'\n  else if \(button == editor_button\)\n  \{\n    do_edit\(\);\n  \}',
    '',
    s,
    count=1,
)

if (n_start, n_ctor, n_click) != (1, 1, 1):
    raise SystemExit(f'web menu patch mismatch {(n_start, n_ctor, n_click)}')

p.write_text(s, encoding='utf-8')

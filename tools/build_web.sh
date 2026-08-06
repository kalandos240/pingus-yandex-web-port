#!/usr/bin/env bash
set -euo pipefail

mkdir -p ../dist

python3 - <<'PY'
from pathlib import Path
import re

path = Path('src/pingus/pingus_main.cpp')
source = path.read_text(encoding='utf-8')

source = source.replace(
    '#include "editor/editor_level.hpp"\n#include "editor/editor_screen.hpp"\n',
    ''
)

source, editor_option_count = re.subn(
    r'\n  argp\.add_group\("Editor Options:"\);\n'
    r'  argp\.add_option\(\'e\', "editor", "",\n'
    r'                  _\("Loads the level editor"\)\);\n',
    '\n',
    source,
    count=1,
)

source, editor_case_count = re.subn(
    r"\n      case 'e': // -e, --editor\n"
    r"        cmd_options\.editor\.set\(true\);\n"
    r"        break;\n",
    '\n',
    source,
    count=1,
)

source, editor_start_count = re.subn(
    r'  if \(cmd_options\.editor\.is_set\(\) && cmd_options\.editor\.get\(\)\)\n'
    r'  \{ // Editor\n'
    r'.*?'
    r'  \}\n'
    r'  else if \(cmd_options\.rest\.is_set\(\)\)',
    '  if (cmd_options.rest.is_set())',
    source,
    count=1,
    flags=re.DOTALL,
)

if editor_option_count != 1 or editor_case_count != 1 or editor_start_count != 1:
    raise SystemExit(
        f'Pingus editor patch mismatch: option={editor_option_count}, '
        f'case={editor_case_count}, start={editor_start_count}'
    )

path.write_text(source, encoding='utf-8')
PY

mapfile -t SOURCES < <(
  find external/tinygettext/tinygettext src -type f -name '*.cpp' \
    ! -path 'src/editor/*' \
    ! -path '*/opengl/*' \
    ! -path '*/evdev/*' \
    ! -path '*/xinput/*' \
    ! -path '*/wiimote/*' \
    -print | sort
)

printf 'Compiling %s original C++ source files (level editor omitted from browser build)\n' "${#SOURCES[@]}"

em++ "${SOURCES[@]}" \
  -I. -Isrc -Iexternal/tinygettext \
  -std=c++11 -O1 \
  -DVERSION='"0.7.6-web"' \
  -DHAVE_ICONV_CONST=1 -DICONV_CONST= \
  -sUSE_SDL=1 \
  -sUSE_SDL_IMAGE=1 \
  -sUSE_SDL_MIXER=1 \
  -sUSE_LIBPNG=1 \
  -sALLOW_MEMORY_GROWTH=1 \
  -sASSERTIONS=1 \
  -sEXIT_RUNTIME=0 \
  --preload-file data@/data \
  -o ../dist/index.html

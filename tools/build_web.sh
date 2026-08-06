#!/usr/bin/env bash
set -euo pipefail

mkdir -p ../dist

# Boost usage in Pingus 0.7.6 is header-only for the browser target. Copy the
# host package into the project include tree so Clang does not see host libc.
rm -rf external/boost
cp -a /usr/include/boost external/boost

python3 - <<'PY'
from pathlib import Path
import re

# The browser build does not ship the desktop level editor. Removing its
# command-line entry points also avoids the obsolete Boost.Signals dependency.
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
    '\n', source, count=1,
)
source, editor_case_count = re.subn(
    r"\n      case 'e': // -e, --editor\n"
    r"        cmd_options\.editor\.set\(true\);\n"
    r"        break;\n",
    '\n', source, count=1,
)
source, editor_start_count = re.subn(
    r'  if \(cmd_options\.editor\.is_set\(\) && cmd_options\.editor\.get\(\)\)\n'
    r'  \{ // Editor\n.*?  \}\n'
    r'  else if \(cmd_options\.rest\.is_set\(\)\)',
    '  if (cmd_options.rest.is_set())', source, count=1, flags=re.DOTALL,
)
if (editor_option_count, editor_case_count, editor_start_count) != (1, 1, 1):
    raise SystemExit(
        f'Pingus editor patch mismatch: option={editor_option_count}, '
        f'case={editor_case_count}, start={editor_start_count}'
    )
path.write_text(source, encoding='utf-8')

# The original SCons build supplied the exception helper globally. Add it only
# to Pingus translation units that use the helper, avoiding macro collisions
# with tinygettext's own log macros.
for path in Path('src').rglob('*.cpp'):
    source = path.read_text(encoding='utf-8')
    if ('raise_exception(' in source or 'raise_error(' in source) and \
       'util/raise_exception.hpp' not in source:
        match = re.search(r'^#include ', source, flags=re.MULTILINE)
        if not match:
            raise SystemExit(f'No include location in {path}')
        source = source[:match.start()] + '#include "util/raise_exception.hpp"\n\n' + source[match.start():]
        path.write_text(source, encoding='utf-8')

# Emscripten's SDL 1 compatibility layer stores colour-key and alpha state on
# SDL_Surface rather than exposing the removed SDL_PixelFormat fields.
path = Path('src/engine/display/blitter.cpp')
source = path.read_text(encoding='utf-8')
replacements = {
    '    ckey = surface->format->colorkey;':
        '    ckey = 0;\n    SDL_GetColorKey(surface, &ckey);',
    '  if (surface->flags & SDL_SRCALPHA)\n    SDL_SetAlpha(new_surface, SDL_SRCALPHA, surface->format->alpha);':
        '  if (surface->flags & SDL_SRCALPHA)\n  {\n    Uint8 alpha = SDL_ALPHA_OPAQUE;\n    SDL_GetSurfaceAlphaMod(surface, &alpha);\n    SDL_SetAlpha(new_surface, SDL_SRCALPHA, alpha);\n  }',
    '  if (surface->flags & SDL_SRCCOLORKEY)\n    SDL_SetColorKey(new_surface, SDL_SRCCOLORKEY, surface->format->colorkey);':
        '  if (surface->flags & SDL_SRCCOLORKEY)\n  {\n    Uint32 color_key = 0;\n    SDL_GetColorKey(surface, &color_key);\n    SDL_SetColorKey(new_surface, SDL_SRCCOLORKEY, color_key);\n  }',
}
for old, new in replacements.items():
    if old not in source:
        raise SystemExit(f'Pingus SDL blitter patch mismatch: {old!r}')
    source = source.replace(old, new, 1)
path.write_text(source, encoding='utf-8')

# Apply the same SDL state-access conversion in Surface, where 0.7.6 reads
# colour-key and alpha values directly from SDL_PixelFormat.
path = Path('src/engine/display/surface.cpp')
source = path.read_text(encoding='utf-8')
replacements = {
    '          if (impl->surface->flags & SDL_SRCCOLORKEY &&\n              pixel == impl->surface->format->colorkey)':
        '          Uint32 color_key = 0;\n          if (SDL_GetColorKey(impl->surface, &color_key) == 0 &&\n              pixel == color_key)',
    '    Uint8 alpha = impl->surface->format->alpha;':
        '    Uint8 alpha = SDL_ALPHA_OPAQUE;\n    SDL_GetSurfaceAlphaMod(impl->surface, &alpha);',
    '  if (impl->surface->flags & SDL_SRCCOLORKEY)\n    out << "Colorkey: " << static_cast<int>(impl->surface->format->colorkey) << std::endl;':
        '  if (impl->surface->flags & SDL_SRCCOLORKEY)\n  {\n    Uint32 color_key = 0;\n    SDL_GetColorKey(impl->surface, &color_key);\n    out << "Colorkey: " << static_cast<int>(color_key) << std::endl;\n  }',
    '  if (impl->surface->flags & SDL_SRCALPHA)\n    out << "Alpha: " << static_cast<int>(impl->surface->format->alpha) << std::endl;':
        '  if (impl->surface->flags & SDL_SRCALPHA)\n  {\n    Uint8 alpha = SDL_ALPHA_OPAQUE;\n    SDL_GetSurfaceAlphaMod(impl->surface, &alpha);\n    out << "Alpha: " << static_cast<int>(alpha) << std::endl;\n  }',
}
for old, new in replacements.items():
    if old not in source:
        raise SystemExit(f'Pingus SDL surface patch mismatch: {old!r}')
    source = source.replace(old, new, 1)
path.write_text(source, encoding='utf-8')

# Emscripten's SDL headers use the canonical SDL_Keysym type name.
path = Path('src/engine/input/event.hpp')
source = path.read_text(encoding='utf-8')
old = '  SDL_keysym keysym;'
new = '  SDL_Keysym keysym;'
if old not in source:
    raise SystemExit('Pingus SDL keysym patch mismatch')
path.write_text(source.replace(old, new, 1), encoding='utf-8')
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
  -I. -Isrc -Iexternal -Iexternal/tinygettext \
  -std=c++11 -O1 -fexceptions \
  -DVERSION='"0.7.6-web"' \
  -DHAVE_ICONV_CONST=1 -DICONV_CONST= \
  -sUSE_SDL=1 \
  -sUSE_SDL_IMAGE=1 \
  -sUSE_SDL_MIXER=1 \
  -sUSE_LIBPNG=1 \
  -sDISABLE_EXCEPTION_CATCHING=0 \
  -sFORCE_FILESYSTEM=1 \
  -sALLOW_MEMORY_GROWTH=1 \
  -sASSERTIONS=1 \
  -sEXIT_RUNTIME=0 \
  --preload-file data@/data \
  -o ../dist/index.html

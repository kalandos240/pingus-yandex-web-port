#!/usr/bin/env bash
set -euo pipefail

mkdir -p ../dist
rm -rf ../dist/* external/boost
cp -a /usr/include/boost external/boost

python3 - <<'PY'
from pathlib import Path
import re

# Modern Boost / SDL naming compatibility.
for p in list(Path('src').rglob('*.hpp')) + list(Path('src').rglob('*.cpp')):
    s = p.read_text(encoding='utf-8')
    n = s.replace('<boost/signal.hpp>', '<boost/signals2/signal.hpp>')
    n = n.replace('<boost/signals.hpp>', '<boost/signals2.hpp>')
    n = n.replace('boost::signal<', 'boost::signals2::signal<')
    n = n.replace('boost::signals::', 'boost::signals2::')
    n = re.sub(r'Uint8\s*\*\s*(\w+)\s*=\s*SDL_GetKeyState\(NULL\);',
               r'const Uint8* \1 = SDL_GetKeyboardState(NULL);', n)
    n = re.sub(r'"([^"\n]*)"VERSION', r'"\1" VERSION', n)
    if n != s:
        p.write_text(n, encoding='utf-8')

# Browser build omits the desktop level editor command-line branch.
p = Path('src/pingus/pingus_main.cpp')
s = p.read_text(encoding='utf-8')
s = s.replace('#include "editor/editor_level.hpp"\n#include "editor/editor_screen.hpp"\n', '')
s, a = re.subn(r'\n  argp\.add_group\("Editor Options:"\);\n  argp\.add_option\(\'e\', "editor", "",\n                  _\("Loads the level editor"\)\);\n', '\n', s, count=1)
s, b = re.subn(r"\n      case 'e': // -e, --editor\n        cmd_options\.editor\.set\(true\);\n        break;\n", '\n', s, count=1)
s, c = re.subn(r'  if \(cmd_options\.editor\.is_set\(\) && cmd_options\.editor\.get\(\)\)\n  \{ // Editor\n.*?  \}\n  else if \(cmd_options\.rest\.is_set\(\)', '  if (cmd_options.rest.is_set())', s, count=1, flags=re.DOTALL)
if (a,b,c) != (1,1,1):
    raise SystemExit(f'editor main patch mismatch {(a,b,c)}')
s = s.replace('if (cmd_options.rest.is_set()))', 'if (cmd_options.rest.is_set())')
p.write_text(s, encoding='utf-8')

# The main menu also references the editor. Keep the original menu layout but make
# the editor entry inert so the browser build does not require editor object files.
p = Path('src/pingus/screens/pingus_menu.cpp')
s = p.read_text(encoding='utf-8')
s = s.replace('#include "editor/editor_screen.hpp"\n', '')
s, n = re.subn(r'void PingusMenu::do_edit\(\)\n\{.*?\n\}',
               'void PingusMenu::do_edit()\n{\n  // Level editor is intentionally unavailable in the WebAssembly build.\n}',
               s, count=1, flags=re.DOTALL)
if n != 1:
    raise SystemExit('editor menu patch mismatch')
p.write_text(s, encoding='utf-8')

# Bring old exception helpers into translation units that call them directly.
for p in Path('src').rglob('*.cpp'):
    s = p.read_text(encoding='utf-8')
    if ('raise_exception(' in s or 'raise_error(' in s) and 'util/raise_exception.hpp' not in s:
        m = re.search(r'^#include ', s, flags=re.MULTILINE)
        if not m:
            raise SystemExit(f'no include anchor in {p}')
        p.write_text(s[:m.start()] + '#include "util/raise_exception.hpp"\n\n' + s[m.start():], encoding='utf-8')

# Small source-level compatibility fixes already confirmed by previous CI passes.
def rw(path, old, new):
    p = Path(path); s = p.read_text(encoding='utf-8'); p.write_text(s.replace(old, new), encoding='utf-8')

rw('src/engine/input/event.hpp', '  SDL_keysym keysym;', '  SDL_Keysym keysym;')
rw('src/engine/input/sdl_driver.cpp', '    char* key_name = SDL_GetKeyName(static_cast<SDLKey>(i));', '    const char* key_name = SDL_GetKeyName(static_cast<SDLKey>(i));')
rw('src/lisp/getters.hpp', '  const Lisp* el = lisp->get_list_elem(1);', '  const Lisp* el = lisp->get_list_elem(1).get();')

# Emscripten's SDL1 shim exposes SDL surface metadata through helper functions.
p = Path('src/engine/display/blitter.cpp')
s = p.read_text(encoding='utf-8')
s = s.replace('    ckey = surface->format->colorkey;',
              '    if (SDL_GetColorKey(surface, &ckey) != 0) ckey = 0;')
s = s.replace('  if (surface->flags & SDL_SRCALPHA)\n    SDL_SetAlpha(new_surface, SDL_SRCALPHA, surface->format->alpha);',
              '  if (surface->flags & SDL_SRCALPHA)\n  {\n    Uint8 surface_alpha = 255;\n    SDL_GetSurfaceAlphaMod(surface, &surface_alpha);\n    SDL_SetAlpha(new_surface, SDL_SRCALPHA, surface_alpha);\n  }')
s = s.replace('  if (surface->flags & SDL_SRCCOLORKEY)\n    SDL_SetColorKey(new_surface, SDL_SRCCOLORKEY, surface->format->colorkey);',
              '  if (surface->flags & SDL_SRCCOLORKEY)\n  {\n    Uint32 surface_colorkey = 0;\n    if (SDL_GetColorKey(surface, &surface_colorkey) == 0)\n      SDL_SetColorKey(new_surface, SDL_SRCCOLORKEY, surface_colorkey);\n  }')
if 'surface->format->colorkey' in s or 'surface->format->alpha' in s:
    raise SystemExit('SDL blitter metadata patch incomplete')
p.write_text(s, encoding='utf-8')

# surface.cpp contains the same removed SDL_PixelFormat members in four places.
# Replace them with helper APIs and verify that no stale member access remains.
p = Path('src/engine/display/surface.cpp')
s = p.read_text(encoding='utf-8')
s, n1 = re.subn(
    r'if\s*\(impl->surface->flags\s*&\s*SDL_SRCCOLORKEY\s*&&\s*pixel\s*==\s*impl->surface->format->colorkey\)',
    'Uint32 surface_colorkey = 0;\n          if (SDL_GetColorKey(impl->surface, &surface_colorkey) == 0 &&\n              pixel == surface_colorkey)',
    s, count=1, flags=re.MULTILINE)
s, n2 = re.subn(
    r'Uint8\s+alpha\s*=\s*impl->surface->format->alpha\s*;',
    'Uint8 alpha = 255;\n    SDL_GetSurfaceAlphaMod(impl->surface, &alpha);',
    s, count=1)
s, n3 = re.subn(
    r'out\s*<<\s*"Colorkey: "\s*<<\s*static_cast<int>\(impl->surface->format->colorkey\)\s*<<\s*std::endl\s*;',
    '{ Uint32 surface_colorkey = 0; SDL_GetColorKey(impl->surface, &surface_colorkey); out << "Colorkey: " << static_cast<int>(surface_colorkey) << std::endl; }',
    s, count=1)
s, n4 = re.subn(
    r'out\s*<<\s*"Alpha: "\s*<<\s*static_cast<int>\(impl->surface->format->alpha\)\s*<<\s*std::endl\s*;',
    '{ Uint8 surface_alpha = 255; SDL_GetSurfaceAlphaMod(impl->surface, &surface_alpha); out << "Alpha: " << static_cast<int>(surface_alpha) << std::endl; }',
    s, count=1)
if (n1, n2, n3, n4) != (1, 1, 1, 1):
    raise SystemExit(f'SDL surface.cpp patch mismatch {(n1,n2,n3,n4)}')
if 'format->colorkey' in s or 'format->alpha' in s:
    raise SystemExit('SDL surface.cpp metadata patch incomplete')
p.write_text(s, encoding='utf-8')

# The SDL1 JavaScript shim keeps per-surface alpha in SDL.surfaces rather than
# in SDL_PixelFormat. Color-keying is explicitly a no-op in Emscripten's SDL1
# backend, therefore the getter correctly reports that no color key is active.
Path('src/web_sdl_compat.cpp').write_text(r'''#include <SDL.h>
#include <emscripten.h>
extern "C" int SDL_GetColorKey(SDL_Surface* surface, Uint32* key)
{
  if (!surface || !key) return -1;
  *key = 0;
  return -1;
}
extern "C" int SDL_GetSurfaceAlphaMod(SDL_Surface* surface, Uint8* alpha)
{
  if (!surface || !alpha) return -1;
  int value = EM_ASM_INT({
    var s = SDL.surfaces[$0];
    return s && typeof s.alpha === 'number' ? s.alpha : 255;
  }, surface);
  *alpha = static_cast<Uint8>(value);
  return 0;
}
extern "C" SDL_Surface* SDL_DisplayFormat(SDL_Surface* surface)
{
  if (!surface) return 0;
  return SDL_ConvertSurface(surface, surface->format, surface->flags);
}
''', encoding='utf-8')

# Yield while hidden and notify the Yandex shell when the first frame is ready.
p = Path('src/engine/screen/screen_manager.cpp')
s = p.read_text(encoding='utf-8')
if '#include <emscripten.h>' not in s:
    s = s.replace('#include <iostream>\n', '#include <iostream>\n\n#ifdef __EMSCRIPTEN__\n#include <emscripten.h>\n#endif\n', 1)
s = s.replace('  while (!screens.empty())\n  {\n    events.clear();', '''  while (!screens.empty())
  {
#ifdef __EMSCRIPTEN__
    if (EM_ASM_INT({ return document.hidden ? 1 : 0; }))
    {
      emscripten_sleep(100);
      last_ticks = SDL_GetTicks();
      continue;
    }
#endif
    events.clear();''', 1)
s = s.replace('  Display::flip_display();\n}', '''  Display::flip_display();
#ifdef __EMSCRIPTEN__
  static bool game_ready_sent = false;
  if (!game_ready_sent)
  {
    game_ready_sent = true;
    EM_ASM({ if (typeof window.pingusMarkReady === 'function') window.pingusMarkReady(); });
  }
#endif
}''', 1)
s = s.replace('  }\n}\n \nvoid\nScreenManager::update', '''  }
#ifdef __EMSCRIPTEN__
  EM_ASM({ if (typeof window.pingusSaveNow === 'function') window.pingusSaveNow(); });
#endif
}
 
void
ScreenManager::update''', 1)
p.write_text(s, encoding='utf-8')
PY

mapfile -t SOURCES < <(find external/tinygettext/tinygettext src -type f -name '*.cpp' \
  ! -path 'src/editor/*' ! -path '*/opengl/*' ! -path '*/evdev/*' \
  ! -path '*/xinput/*' ! -path '*/wiimote/*' -print | sort)
(( ${#SOURCES[@]} >= 200 )) || { echo "Unexpectedly small source set" >&2; exit 1; }
printf 'Compiling %s original C++ source files (desktop editor omitted)\n' "${#SOURCES[@]}"

em++ "${SOURCES[@]}" \
  -I. -Isrc -Iexternal -Iexternal/tinygettext \
  -std=c++11 -O1 -fexceptions -Wno-invalid-source-encoding \
  -DVERSION='"0.7.6-web"' -DHAVE_ICONV_CONST=1 -DICONV_CONST= \
  -sUSE_SDL=1 -sUSE_SDL_IMAGE=1 -sUSE_SDL_MIXER=1 \
  -sUSE_LIBPNG=1 -sUSE_OGG=1 -sUSE_VORBIS=1 \
  -sDISABLE_EXCEPTION_CATCHING=0 -sFORCE_FILESYSTEM=1 \
  -sASYNCIFY=1 -sASYNCIFY_STACK_SIZE=65536 \
  -sINITIAL_MEMORY=67108864 -sALLOW_MEMORY_GROWTH=1 -sMAXIMUM_MEMORY=1073741824 \
  -sASSERTIONS=1 -sERROR_ON_UNDEFINED_SYMBOLS=1 -sEXIT_RUNTIME=0 -sENVIRONMENT=web \
  -lidbfs.js --shell-file ../web/shell.html --preload-file data@/data \
  -o ../dist/index.html

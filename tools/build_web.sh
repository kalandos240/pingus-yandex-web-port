#!/usr/bin/env bash
set -euo pipefail

mkdir -p ../dist
rm -rf ../dist/* external/boost
cp -a /usr/include/boost external/boost

python3 - <<'PY'
from pathlib import Path
import re

def rw(path, fn):
    p = Path(path)
    s = p.read_text(encoding='utf-8')
    n = fn(s)
    if n != s:
        p.write_text(n, encoding='utf-8')

# Modern Boost / SDL compatibility fixes used by the original Pingus 0.7.6 code.
for p in list(Path('src').rglob('*.hpp')) + list(Path('src').rglob('*.cpp')):
    s = p.read_text(encoding='utf-8')
    n = s.replace('<boost/signal.hpp>', '<boost/signals2/signal.hpp>')
    n = n.replace('<boost/signals.hpp>', '<boost/signals2.hpp>')
    n = n.replace('boost::signal<', 'boost::signals2::signal<')
    n = n.replace('boost::signals::', 'boost::signals2::')
    n = re.sub(r'Uint8\s*\*\s*(\w+)\s*=\s*SDL_GetKeyState\(NULL\);',
               r'const Uint8* \1 = SDL_GetKeyboardState(NULL);', n)
    if n != s:
        p.write_text(n, encoding='utf-8')

# Browser build omits the desktop level editor.
p = Path('src/pingus/pingus_main.cpp')
s = p.read_text(encoding='utf-8')
s = s.replace('#include "editor/editor_level.hpp"\n#include "editor/editor_screen.hpp"\n', '')
s, a = re.subn(r'\n  argp\.add_group\("Editor Options:"\);\n  argp\.add_option\(\'e\', "editor", "",\n                  _\("Loads the level editor"\)\);\n', '\n', s, count=1)
s, b = re.subn(r"\n      case 'e': // -e, --editor\n        cmd_options\.editor\.set\(true\);\n        break;\n", '\n', s, count=1)
s, c = re.subn(r'  if \(cmd_options\.editor\.is_set\(\) && cmd_options\.editor\.get\(\)\)\n  \{ // Editor\n.*?  \}\n  else if \(cmd_options\.rest\.is_set\(\)', '  if (cmd_options.rest.is_set())', s, count=1, flags=re.DOTALL)
if (a,b,c) != (1,1,1): raise SystemExit(f'editor patch mismatch {(a,b,c)}')
p.write_text(s, encoding='utf-8')

# Bring the old exception helpers into translation units that call them directly.
for p in Path('src').rglob('*.cpp'):
    s = p.read_text(encoding='utf-8')
    if ('raise_exception(' in s or 'raise_error(' in s) and 'util/raise_exception.hpp' not in s:
        m = re.search(r'^#include ', s, flags=re.MULTILINE)
        if not m: raise SystemExit(f'no include anchor in {p}')
        p.write_text(s[:m.start()] + '#include "util/raise_exception.hpp"\n\n' + s[m.start():], encoding='utf-8')

rw('src/engine/display/blitter.cpp', lambda s: s
   .replace('    ckey = surface->format->colorkey;', '    ckey = 0;\n    SDL_GetColorKey(surface, &ckey);')
   .replace('  if (surface->flags & SDL_SRCALPHA)\n    SDL_SetAlpha(new_surface, SDL_SRCALPHA, surface->format->alpha);',
            '  if (surface->flags & SDL_SRCALPHA)\n  {\n    Uint8 alpha = SDL_ALPHA_OPAQUE;\n    SDL_GetSurfaceAlphaMod(surface, &alpha);\n    SDL_SetAlpha(new_surface, SDL_SRCALPHA, alpha);\n  }')
   .replace('  if (surface->flags & SDL_SRCCOLORKEY)\n    SDL_SetColorKey(new_surface, SDL_SRCCOLORKEY, surface->format->colorkey);',
            '  if (surface->flags & SDL_SRCCOLORKEY)\n  {\n    Uint32 color_key = 0;\n    SDL_GetColorKey(surface, &color_key);\n    SDL_SetColorKey(new_surface, SDL_SRCCOLORKEY, color_key);\n  }'))

rw('src/engine/display/surface.cpp', lambda s: s
   .replace('          if (impl->surface->flags & SDL_SRCCOLORKEY &&\n              pixel == impl->surface->format->colorkey)',
            '          Uint32 color_key = 0;\n          if (SDL_GetColorKey(impl->surface, &color_key) == 0 &&\n              pixel == color_key)')
   .replace('    Uint8 alpha = impl->surface->format->alpha;', '    Uint8 alpha = SDL_ALPHA_OPAQUE;\n    SDL_GetSurfaceAlphaMod(impl->surface, &alpha);')
   .replace('  if (impl->surface->flags & SDL_SRCCOLORKEY)\n    out << "Colorkey: " << static_cast<int>(impl->surface->format->colorkey) << std::endl;',
            '  if (impl->surface->flags & SDL_SRCCOLORKEY)\n  {\n    Uint32 color_key = 0;\n    SDL_GetColorKey(impl->surface, &color_key);\n    out << "Colorkey: " << static_cast<int>(color_key) << std::endl;\n  }')
   .replace('  if (impl->surface->flags & SDL_SRCALPHA)\n    out << "Alpha: " << static_cast<int>(impl->surface->format->alpha) << std::endl;',
            '  if (impl->surface->flags & SDL_SRCALPHA)\n  {\n    Uint8 alpha = SDL_ALPHA_OPAQUE;\n    SDL_GetSurfaceAlphaMod(impl->surface, &alpha);\n    out << "Alpha: " << static_cast<int>(alpha) << std::endl;\n  }'))

rw('src/pingus/collision_mask.cpp', lambda s: s.replace(
    '          if (source[y*pitch + x] == sdl_surface->format->colorkey)',
    '          Uint32 color_key = 0;\n          SDL_GetColorKey(sdl_surface, &color_key);\n          if (source[y*pitch + x] == color_key)'))

rw('src/pingus/ground_map.cpp', lambda s: s.replace(
    '    Uint32 colorkey = sprovider.get_surface()->format->colorkey;',
    '    Uint32 colorkey = 0;\n    SDL_GetColorKey(sprovider.get_surface(), &colorkey);'))

rw('src/engine/input/event.hpp', lambda s: s.replace('  SDL_keysym keysym;', '  SDL_Keysym keysym;'))
rw('src/engine/input/sdl_driver.cpp', lambda s: s.replace('    char* key_name = SDL_GetKeyName(static_cast<SDLKey>(i));', '    const char* key_name = SDL_GetKeyName(static_cast<SDLKey>(i));'))
rw('src/lisp/getters.hpp', lambda s: s.replace('  const Lisp* el = lisp->get_list_elem(1);', '  const Lisp* el = lisp->get_list_elem(1).get();'))

# Yield the main loop in hidden tabs and call the Yandex shell hooks after first frame / exit.
p = Path('src/engine/screen/screen_manager.cpp')
s = p.read_text(encoding='utf-8')
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

mapfile -t SOURCES < <(find external/tinygettext/tinygettext src -type f -name '*.cpp' ! -path 'src/editor/*' ! -path '*/opengl/*' ! -path '*/evdev/*' ! -path '*/xinput/*' ! -path '*/wiimote/*' -print | sort)
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

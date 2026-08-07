from pathlib import Path
import re

# Emscripten's SDL1 compatibility layer does not expose desktop SDL key names
# consistently through SDL_GetKeyName(). Avoid probing the whole legacy key
# table in the browser and bind exactly the names used by Pingus' default
# controller file to the canonical SDL key constants.
p = Path('src/engine/input/sdl_driver.cpp')
s = p.read_text(encoding='utf-8')
pattern = re.compile(
    r'''  for \(int i = 0; i < SDLK_LAST; \+\+i\)\s*\n'''
    r'''  \{\s*\n'''
    r'''    const char\* key_name = SDL_GetKeyName\(static_cast<SDLKey>\(i\)\);\s*\n'''
    r'''    string2key\[key_name\] = static_cast<SDLKey>\(i\);\s*\n'''
    r'''\s*'''
    r'''    // FIXME: Make the keynames somewhere user visible so that users can use them\s*\n'''
    r'''    log_debug\("Key: '" << key_name << "'"\);\s*\n'''
    r'''  \}''',
    re.MULTILINE,
)
replacement = r'''#ifdef __EMSCRIPTEN__
  string2key["up"] = SDLK_UP;
  string2key["down"] = SDLK_DOWN;
  string2key["left"] = SDLK_LEFT;
  string2key["right"] = SDLK_RIGHT;
  string2key["p"] = SDLK_p;
  string2key["f"] = SDLK_f;
  string2key["space"] = SDLK_SPACE;
  string2key["s"] = SDLK_s;
  string2key["a"] = SDLK_a;
  string2key["escape"] = SDLK_ESCAPE;
  string2key["tab"] = SDLK_TAB;
  string2key["1"] = SDLK_1;
  string2key["2"] = SDLK_2;
  string2key["3"] = SDLK_3;
  string2key["4"] = SDLK_4;
  string2key["5"] = SDLK_5;
  string2key["6"] = SDLK_6;
  string2key["7"] = SDLK_7;
  string2key["8"] = SDLK_8;
  string2key["9"] = SDLK_9;
  string2key["0"] = SDLK_0;
#else
  for (int i = 0; i < SDLK_LAST; ++i)
  {
    const char* key_name = SDL_GetKeyName(static_cast<SDLKey>(i));
    string2key[key_name] = static_cast<SDLKey>(i);

    // FIXME: Make the keynames somewhere user visible so that users can use them
    log_debug("Key: '" << key_name << "'");
  }
#endif'''
s, count = pattern.subn(replacement, s, count=1)
if count != 1:
    raise SystemExit('browser SDL key-map patch mismatch')
p.write_text(s, encoding='utf-8')

# Browser audio APIs cannot decode Impulse Tracker / XM / S3M / MOD files.
# The build converts tracker modules to OGG while preserving the music. Point
# the original play_music calls at the converted file only in Emscripten builds.
p = Path('src/engine/sound/sound.cpp')
s = p.read_text(encoding='utf-8')
needle = '  sound->real_play_music(g_path_manager.complete ("music/" + name), volume, loop);'
replacement = r'''#ifdef __EMSCRIPTEN__
  std::string web_name = name;
  const std::string::size_type dot = web_name.rfind('.');
  if (dot != std::string::npos)
  {
    const std::string ext = web_name.substr(dot);
    if (ext == ".it" || ext == ".xm" || ext == ".s3m" || ext == ".mod")
      web_name.replace(dot, std::string::npos, ".ogg");
  }
  sound->real_play_music(g_path_manager.complete ("music/" + web_name), volume, loop);
#else
  sound->real_play_music(g_path_manager.complete ("music/" + name), volume, loop);
#endif'''
if s.count(needle) != 1:
    raise SystemExit('browser music redirect patch mismatch')
s = s.replace(needle, replacement, 1)
p.write_text(s, encoding='utf-8')

# Pingus writes save/stat files atomically through mkstemp() and then chmods
# them using a mode derived from umask(). Emscripten's umask compatibility can
# yield zero permission bits here, creating a file that exists but cannot be
# read back on the next launch. Use an explicit private read/write mode in the
# browser build while preserving the original desktop behavior elsewhere.
# Also request an IDBFS sync immediately after a successful browser write, so a
# just-finished level is not dependent on the 15-second autosave interval.
p = Path('src/util/system.cpp')
s = p.read_text(encoding='utf-8')
include_anchor = '#include "util/system.hpp"\n'
include_replacement = '''#include "util/system.hpp"\n\n#ifdef __EMSCRIPTEN__\n#  include <emscripten.h>\n#endif\n'''
if s.count(include_anchor) != 1:
    raise SystemExit('browser system include anchor missing or duplicated')
s = s.replace(include_anchor, include_replacement, 1)

needle = '  if (chmod(filename.c_str(), ~old_mask & 0666) < 0)'
replacement = r'''#ifdef __EMSCRIPTEN__
  if (chmod(filename.c_str(), S_IRUSR | S_IWUSR) < 0)
#else
  if (chmod(filename.c_str(), ~old_mask & 0666) < 0)
#endif'''
if s.count(needle) != 1:
    raise SystemExit('browser save-file permission patch mismatch')
s = s.replace(needle, replacement, 1)

save_tail = r'''#ifdef __EMSCRIPTEN__
  if (chmod(filename.c_str(), S_IRUSR | S_IWUSR) < 0)
#else
  if (chmod(filename.c_str(), ~old_mask & 0666) < 0)
#endif
  {
    raise_exception(std::runtime_error, tmpfile.get() << ": " << strerror(errno));
  }
#endif
}'''
save_tail_replacement = r'''#ifdef __EMSCRIPTEN__
  if (chmod(filename.c_str(), S_IRUSR | S_IWUSR) < 0)
#else
  if (chmod(filename.c_str(), ~old_mask & 0666) < 0)
#endif
  {
    raise_exception(std::runtime_error, tmpfile.get() << ": " << strerror(errno));
  }
#endif

#ifdef __EMSCRIPTEN__
  EM_ASM({
    if (typeof window.pingusSaveNow === 'function') window.pingusSaveNow();
  });
#endif
}'''
if s.count(save_tail) != 1:
    raise SystemExit('browser immediate-save anchor missing or duplicated')
s = s.replace(save_tail, save_tail_replacement, 1)
p.write_text(s, encoding='utf-8')

# Pingus' SDL1 renderer and collision system perform frequent getImageData()
# reads from many browser canvases. Tell Chromium to create those 2D contexts
# for frequent pixel readback; this avoids repeated GPU-to-CPU fallback work
# and the associated Canvas2D warning flood while preserving all context opts.
p = Path('../web/shell.html')
s = p.read_text(encoding='utf-8')
needle = '''    (() => {\n      const loading = document.getElementById('loading');'''
replacement = '''    (() => {\n      const nativeCanvasGetContext = HTMLCanvasElement.prototype.getContext;\n      HTMLCanvasElement.prototype.getContext = function(type, options) {\n        if (type === '2d') {\n          const readbackOptions = options && typeof options === 'object'\n            ? { ...options, willReadFrequently: true }\n            : { willReadFrequently: true };\n          return nativeCanvasGetContext.call(this, type, readbackOptions);\n        }\n        return nativeCanvasGetContext.apply(this, arguments);\n      };\n\n      const loading = document.getElementById('loading');'''
if s.count(needle) != 1:
    raise SystemExit('browser canvas readback patch mismatch')
s = s.replace(needle, replacement, 1)
p.write_text(s, encoding='utf-8')

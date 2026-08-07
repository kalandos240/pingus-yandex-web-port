from pathlib import Path
import re

# Emscripten's SDL1 compatibility layer does not expose desktop SDL key names
# consistently through SDL_GetKeyName().  Avoid probing the whole legacy key
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
# The build converts tracker modules to OGG while preserving the music.  Point
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

from pathlib import Path

# Keep browser gameplay pause state aligned with the existing audio pause.
# Pingus' web loop already stops while document.hidden, but a Yandex overlay,
# browser focus change, or window switch can blur the game while the document
# remains visible. In that case audio paused but the simulation kept running.
# Expose one browser-side predicate and make the C++ frame loop use it.

shell_path = Path('../web/shell.html')
shell = shell_path.read_text(encoding='utf-8')
shell_anchor = '''      let autosaveTimer = 0;\n\n      const text = {'''
shell_patch = '''      let autosaveTimer = 0;\n\n      // Before the first rendered frame we must not gate startup on focus: an\n      // embedded Yandex iframe may not own focus yet. After the game is ready,\n      // losing focus pauses both the native simulation and audio until focus\n      // returns. document.hidden remains an unconditional pause condition.\n      window.pingusPagePaused = () =>\n        document.hidden || (gameReadySent && !document.hasFocus());\n\n      const text = {'''
if shell.count(shell_anchor) != 1:
    raise SystemExit('focus-pause shell anchor missing or duplicated')
shell = shell.replace(shell_anchor, shell_patch, 1)
shell_path.write_text(shell, encoding='utf-8')

screen_path = Path('src/engine/screen/screen_manager.cpp')
screen = screen_path.read_text(encoding='utf-8')
old = '''#ifdef __EMSCRIPTEN__\n    if (EM_ASM_INT({ return document.hidden ? 1 : 0; }))\n    {\n      emscripten_sleep(100);\n      last_ticks = SDL_GetTicks();\n      continue;\n    }\n#endif'''
new = '''#ifdef __EMSCRIPTEN__\n    if (EM_ASM_INT({\n          if (typeof window.pingusPagePaused === 'function')\n            return window.pingusPagePaused() ? 1 : 0;\n          return document.hidden ? 1 : 0;\n        }))\n    {\n      emscripten_sleep(100);\n      last_ticks = SDL_GetTicks();\n      continue;\n    }\n#endif'''
if screen.count(old) != 1:
    raise SystemExit('focus-pause screen loop anchor missing or duplicated')
screen = screen.replace(old, new, 1)
screen_path.write_text(screen, encoding='utf-8')

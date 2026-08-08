from pathlib import Path

# Yandex fullscreen ads are shown in an iframe overlay. After the overlay closes,
# browsers do not reliably return document.hasFocus() to the game iframe even
# though the game is visible and interactive again. The previous Web pause
# predicate therefore kept the native Emscripten loop asleep forever after an
# ad on some Yandex/Firefox combinations.
#
# Yandex already provides game_api_pause/game_api_resume for platform overlays,
# and fullscreen-ad callbacks explicitly pause/resume the wrapper as a fallback.
# For the simulation loop, only those platform signals plus document.hidden are
# authoritative. Browser focus is not.

shell_path = Path('../web/shell.html')
shell = shell_path.read_text(encoding='utf-8')

old = '''      window.pingusPagePaused = () =>
        platformPaused || document.hidden || (gameReadySent && !document.hasFocus());'''
new = '''      window.pingusPagePaused = () =>
        platformPaused || document.hidden;'''
if shell.count(old) != 1:
    raise SystemExit('Yandex ad-resume pause predicate anchor missing or duplicated')
shell = shell.replace(old, new, 1)

# A blur/focus transition is not an application pause for an embedded Yandex
# game. Keep visibilitychange for real tab/background transitions; Yandex SDK
# events handle ads, purchases and other platform overlays.
old_events = '''      document.addEventListener('visibilitychange', syncPagePause);
      window.addEventListener('blur', syncPagePause);
      window.addEventListener('focus', syncPagePause);'''
new_events = '''      document.addEventListener('visibilitychange', syncPagePause);'''
if shell.count(old_events) != 1:
    raise SystemExit('Yandex ad-resume focus event anchor missing or duplicated')
shell = shell.replace(old_events, new_events, 1)

shell_path.write_text(shell, encoding='utf-8')
print('Yandex ad resume: removed iframe focus from native pause gate')

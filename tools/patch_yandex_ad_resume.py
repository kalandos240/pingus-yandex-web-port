from pathlib import Path

# Yandex fullscreen ads are shown in an iframe overlay. After the overlay closes,
# browsers do not reliably return document.hasFocus() to the game iframe even
# though the game is visible and interactive again. Therefore browser focus must
# NOT gate the native Emscripten simulation loop: Yandex game_api_pause/resume
# plus document.hidden are authoritative for gameplay.
#
# Audio is different. Requirement 1.3 requires game sound to stop when the game
# loses focus. Keep blur/focus as an audio-only guard so tab/window focus changes
# cannot leak sound, while a stale iframe focus state can never freeze gameplay.

shell_path = Path('../web/shell.html')
shell = shell_path.read_text(encoding='utf-8')

old = '''      window.pingusPagePaused = () =>
        platformPaused || document.hidden || (gameReadySent && !document.hasFocus());'''
new = '''      window.pingusPagePaused = () =>
        platformPaused || document.hidden;'''
if shell.count(old) != 1:
    raise SystemExit('Yandex ad-resume pause predicate anchor missing or duplicated')
shell = shell.replace(old, new, 1)

# Blur/focus must not feed the native gameplay pause predicate, otherwise a
# Yandex iframe can remain permanently paused after an overlay. They still
# control audio directly. On focus, only resume if the authoritative Yandex /
# visibility pause state permits it.
old_events = '''      document.addEventListener('visibilitychange', syncPagePause);
      window.addEventListener('blur', syncPagePause);
      window.addEventListener('focus', syncPagePause);'''
new_events = '''      document.addEventListener('visibilitychange', syncPagePause);
      window.addEventListener('blur', () => setAudioPaused(true));
      window.addEventListener('focus', () => setAudioPaused(window.pingusPagePaused()));'''
if shell.count(old_events) != 1:
    raise SystemExit('Yandex ad-resume focus event anchor missing or duplicated')
shell = shell.replace(old_events, new_events, 1)

shell_path.write_text(shell, encoding='utf-8')
print('Yandex ad resume: gameplay ignores iframe focus; audio still mutes on blur')

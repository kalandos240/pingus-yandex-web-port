from pathlib import Path

# Keep browser gameplay pause state aligned with audio pause.
# Pingus' web loop already stops while document.hidden, but a Yandex overlay,
# browser focus change, or window switch can blur the game while the document
# remains visible. In that case the native simulation used to keep running.
# Emscripten SDL_mixer can also use HTMLAudioElement objects independently of
# its AudioContext, so pausing only the context is not sufficient.

shell_path = Path('../web/shell.html')
shell = shell_path.read_text(encoding='utf-8')

shell_anchor = '''      let autosaveTimer = 0;\n\n      const text = {'''
shell_patch = '''      let autosaveTimer = 0;\n\n      // Before the first rendered frame we must not gate startup on focus: an\n      // embedded Yandex iframe may not own focus yet. After the game is ready,\n      // losing focus pauses both the native simulation and audio until focus\n      // returns. document.hidden remains an unconditional pause condition.\n      window.pingusPagePaused = () =>\n        document.hidden || (gameReadySent && !document.hasFocus());\n\n      // CI launches the real packaged page with ?pingus-smoke=1. In that mode\n      // report the first rendered frame (or a startup failure) back to its\n      // local HTTP server. Normal Yandex launches never perform these requests.\n      const pingusSmokeMode = new URLSearchParams(location.search).get('pingus-smoke') === '1';\n      const pingusSmokeSignal = (kind, detail = '') => {\n        if (!pingusSmokeMode) return;\n        const suffix = detail ? `?detail=${encodeURIComponent(String(detail).slice(0, 300))}` : '';\n        fetch(`/__pingus_${kind}__${suffix}`, { cache: 'no-store' }).catch(() => {});\n      };\n\n      const text = {'''
if shell.count(shell_anchor) != 1:
    raise SystemExit('focus-pause shell anchor missing or duplicated')
shell = shell.replace(shell_anchor, shell_patch, 1)

old_audio = '''      const setAudioPaused = (paused) => {\n        const audioContext = getAudioContext();\n        if (!audioContext) return;\n        const action = paused ? audioContext.suspend?.() : audioContext.resume?.();\n        action?.catch?.(() => {});\n      };'''
new_audio = '''      const setAudioPaused = (paused) => {\n        const audioContext = getAudioContext();\n        if (audioContext) {\n          const action = paused ? audioContext.suspend?.() : audioContext.resume?.();\n          action?.catch?.(() => {});\n        }\n\n        // SDL1_mixer in Emscripten may play OGG music/channels through regular\n        // HTMLAudioElement objects, not through the AudioContext above. Pause\n        // only media that was actually playing, then resume exactly those.\n        const media = [];\n        const music = window.SDL?.music?.audio;\n        if (music) media.push(music);\n        const channels = window.SDL?.channels;\n        if (Array.isArray(channels)) {\n          for (const channel of channels) {\n            if (channel?.audio) media.push(channel.audio);\n          }\n        }\n        for (const audio of new Set(media)) {\n          if (paused) {\n            if (!audio.paused) {\n              audio.__pingusResumeAfterPause = true;\n              audio.pause();\n            }\n          } else if (audio.__pingusResumeAfterPause) {\n            audio.__pingusResumeAfterPause = false;\n            const play = audio.play?.();\n            play?.catch?.(() => {});\n          }\n        }\n      };'''
if shell.count(old_audio) != 1:
    raise SystemExit('SDL mixer audio-pause anchor missing or duplicated')
shell = shell.replace(old_audio, new_audio, 1)

old_events = '''      document.addEventListener('visibilitychange', () => {\n        const paused = document.hidden;\n        setAudioPaused(paused);\n        if (paused) window.pingusSaveNow();\n      });\n      window.addEventListener('blur', () => setAudioPaused(true));\n      window.addEventListener('focus', () => setAudioPaused(false));'''
new_events = '''      const syncPagePause = () => {\n        const paused = window.pingusPagePaused();\n        setAudioPaused(paused);\n        if (paused) window.pingusSaveNow();\n      };\n      document.addEventListener('visibilitychange', syncPagePause);\n      window.addEventListener('blur', syncPagePause);\n      window.addEventListener('focus', syncPagePause);'''
if shell.count(old_events) != 1:
    raise SystemExit('focus-pause event anchor missing or duplicated')
shell = shell.replace(old_events, new_events, 1)

old_error = '''      const setLoadingError = (message) => {\n        loading.hidden = false;\n        status.textContent = message || text[uiLanguage].failed;\n        progress.removeAttribute('value');\n      };'''
new_error = '''      const setLoadingError = (message) => {\n        const errorText = message || text[uiLanguage].failed;\n        document.documentElement.dataset.pingusError = errorText;\n        pingusSmokeSignal('error', errorText);\n        loading.hidden = false;\n        status.textContent = errorText;\n        progress.removeAttribute('value');\n      };'''
if shell.count(old_error) != 1:
    raise SystemExit('runtime error marker anchor missing or duplicated')
shell = shell.replace(old_error, new_error, 1)

old_ready = '''      window.pingusMarkReady = async () => {\n        if (gameReadySent) return;\n        gameReadySent = true;\n        fitCanvas();'''
new_ready = '''      window.pingusMarkReady = async () => {\n        if (gameReadySent) return;\n        gameReadySent = true;\n        document.documentElement.dataset.pingusReady = '1';\n        pingusSmokeSignal('ready');\n        fitCanvas();'''
if shell.count(old_ready) != 1:
    raise SystemExit('runtime ready marker anchor missing or duplicated')
shell = shell.replace(old_ready, new_ready, 1)

shell_path.write_text(shell, encoding='utf-8')

screen_path = Path('src/engine/screen/screen_manager.cpp')
screen = screen_path.read_text(encoding='utf-8')
old = '''#ifdef __EMSCRIPTEN__\n    if (EM_ASM_INT({ return document.hidden ? 1 : 0; }))\n    {\n      emscripten_sleep(100);\n      last_ticks = SDL_GetTicks();\n      continue;\n    }\n#endif'''
new = '''#ifdef __EMSCRIPTEN__\n    if (EM_ASM_INT({\n          if (typeof window.pingusPagePaused === 'function')\n            return window.pingusPagePaused() ? 1 : 0;\n          return document.hidden ? 1 : 0;\n        }))\n    {\n      emscripten_sleep(100);\n      last_ticks = SDL_GetTicks();\n      continue;\n    }\n#endif'''
if screen.count(old) != 1:
    raise SystemExit('focus-pause screen loop anchor missing or duplicated')
screen = screen.replace(old, new, 1)
screen_path.write_text(screen, encoding='utf-8')

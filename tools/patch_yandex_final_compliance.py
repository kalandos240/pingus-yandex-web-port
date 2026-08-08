from pathlib import Path

# Final Yandex lifecycle hardening. This patch runs after the base advertising,
# pause/resume and GameplayAPI patches have been applied to the downloaded
# Pingus 0.7.6 source and browser shell.
#
# It addresses moderation-sensitive details:
#   1) GameplayAPI must be STOPPED during platform pauses/ads/tab backgrounding,
#      then restored only if a playable level is still active.
#   2) progress must be flushed to IDBFS immediately after SavegameManager stores
#      a completed/attempted level, instead of waiting for the 15 s safety timer.
#   3) audio unlock must never accidentally resume sound while Yandex says the
#      game is paused.
#   4) legacy desktop hotkeys such as F5/F11/F12/Alt+Enter/Ctrl+O/Ctrl+G must not
#      be implemented by the game in the browser, because they overlap standard
#      browser/OS commands.

shell_path = Path('../web/shell.html')
shell = shell_path.read_text(encoding='utf-8')

old_gameplay = r'''      let gameplayDesiredActive = false;
      let gameplayStateInitialized = false;
      let gameplaySyncVersion = 0;

      window.pingusSetGameplayActive = (active) => {
        const desired = Boolean(active);
        if (gameplayStateInitialized && gameplayDesiredActive === desired) return;

        gameplayStateInitialized = true;
        gameplayDesiredActive = desired;
        const version = ++gameplaySyncVersion;

        (async () => {
          const ysdk = await window.yandexSDKPromise;
          if (version !== gameplaySyncVersion) return;

          const gameplay = ysdk?.features?.GameplayAPI;
          if (!gameplay) return;

          try {
            if (gameplayDesiredActive) gameplay.start();
            else gameplay.stop();
          } catch (error) {
            console.warn('Yandex GameplayAPI state update failed:', error);
          }
        })().catch((error) => {
          console.warn('Yandex GameplayAPI synchronization failed:', error);
        });
      };
'''

new_gameplay = r'''      let gameplayDesiredActive = false;
      let gameplayStateInitialized = false;
      let gameplayLastSentActive = null;
      let gameplaySyncVersion = 0;

      const syncGameplayAPI = () => {
        if (!gameplayStateInitialized) return;
        const effectiveActive = gameplayDesiredActive && !window.pingusPagePaused();
        if (gameplayLastSentActive === effectiveActive) return;

        const version = ++gameplaySyncVersion;
        (async () => {
          const ysdk = await window.yandexSDKPromise;
          if (version !== gameplaySyncVersion) return;

          const gameplay = ysdk?.features?.GameplayAPI;
          if (!gameplay) return;

          try {
            if (effectiveActive) gameplay.start();
            else gameplay.stop();
            if (version === gameplaySyncVersion)
              gameplayLastSentActive = effectiveActive;
          } catch (error) {
            console.warn('Yandex GameplayAPI state update failed:', error);
          }
        })().catch((error) => {
          console.warn('Yandex GameplayAPI synchronization failed:', error);
        });
      };
      window.pingusSyncGameplayAPI = syncGameplayAPI;

      window.pingusSetGameplayActive = (active) => {
        const desired = Boolean(active);
        if (!gameplayStateInitialized || gameplayDesiredActive !== desired) {
          gameplayStateInitialized = true;
          gameplayDesiredActive = desired;
        }
        syncGameplayAPI();
      };
'''

if shell.count(old_gameplay) != 1:
    raise SystemExit('final compliance: GameplayAPI wrapper anchor missing or duplicated')
shell = shell.replace(old_gameplay, new_gameplay, 1)

old_platform = r'''      window.pingusSetPlatformPaused = (paused) => {
        platformPaused = Boolean(paused);
        if (typeof window.pingusSyncPagePause === 'function')
          window.pingusSyncPagePause();
      };'''
new_platform = r'''      window.pingusSetPlatformPaused = (paused) => {
        platformPaused = Boolean(paused);
        if (typeof window.pingusSyncPagePause === 'function')
          window.pingusSyncPagePause();
        if (typeof window.pingusSyncGameplayAPI === 'function')
          window.pingusSyncGameplayAPI();
      };'''
if shell.count(old_platform) != 1:
    raise SystemExit('final compliance: platform pause anchor missing or duplicated')
shell = shell.replace(old_platform, new_platform, 1)

old_sync = r'''      const syncPagePause = () => {
        const paused = window.pingusPagePaused();
        setAudioPaused(paused);
        if (paused) window.pingusSaveNow();
      };'''
new_sync = r'''      const syncPagePause = () => {
        const paused = window.pingusPagePaused();
        setAudioPaused(paused);
        if (paused) window.pingusSaveNow();
        if (typeof window.pingusSyncGameplayAPI === 'function')
          window.pingusSyncGameplayAPI();
      };'''
if shell.count(old_sync) != 1:
    raise SystemExit('final compliance: visibility pause anchor missing or duplicated')
shell = shell.replace(old_sync, new_sync, 1)

old_unlock = "      const unlockAudio = () => setAudioPaused(false);"
new_unlock = "      const unlockAudio = () => setAudioPaused(window.pingusPagePaused());"
if shell.count(old_unlock) != 1:
    raise SystemExit('final compliance: audio unlock anchor missing or duplicated')
shell = shell.replace(old_unlock, new_unlock, 1)

# showFullscreenAdv documents onOpen/onClose/onError. Do not ship an extra
# callback key from older examples/plugins when strict SDK usage is required.
onoffline = r'''                  onOffline: () => {
                    window.pingusSetPlatformPaused?.(false);
                    finish();
                  }
'''
if onoffline in shell:
    # Remove the preceding comma from onError's closing brace after removal.
    shell = shell.replace(r'''                  },
''' + onoffline, r'''                  }
''', 1)

shell_path.write_text(shell, encoding='utf-8')

# SavegameManager::store() has already written the updated progression to the
# Emscripten filesystem. Flush it to IndexedDB immediately so a reload right
# after the level ends cannot lose progress.
game_path = Path('src/pingus/screens/game_session.cpp')
game = game_path.read_text(encoding='utf-8')
save_anchor = '''      SavegameManager::instance()->store(savegame);\n    }'''
save_replacement = '''      SavegameManager::instance()->store(savegame);\n#ifdef __EMSCRIPTEN__\n      EM_ASM({\n        if (typeof window.pingusSaveNow === 'function')\n          window.pingusSaveNow();\n      });\n#endif\n    }'''
if 'window.pingusSaveNow' not in game:
    if game.count(save_anchor) != 1:
        raise SystemExit('final compliance: immediate save anchor missing or duplicated')
    game = game.replace(save_anchor, save_replacement, 1)

game_path.write_text(game, encoding='utf-8')

# Pingus' original desktop build contains global shortcuts for browser/OS keys:
# F5 opens Options, F11 toggles fullscreen, F12 saves a screenshot, Alt+Enter
# toggles fullscreen and Ctrl+O/Ctrl+G/Ctrl+M have application actions. Those
# are useful on native desktop but conflict with browser/OS commands and should
# not be game controls in the Yandex Web target.
# patch_pingus.py runs before this script and modernizes SDL_GetKeyState to
# SDL_GetKeyboardState, so match that already-patched source form.
global_path = Path('src/pingus/global_event.cpp')
global_event = global_path.read_text(encoding='utf-8')
hotkey_anchor = '''void\nGlobalEvent::on_button_press(const SDL_KeyboardEvent& event)\n{\n  const Uint8* keystate = SDL_GetKeyboardState(NULL);'''
hotkey_replacement = '''void\nGlobalEvent::on_button_press(const SDL_KeyboardEvent& event)\n{\n#ifdef __EMSCRIPTEN__\n  (void)event;\n  return;\n#else\n  const Uint8* keystate = SDL_GetKeyboardState(NULL);'''
if 'Yandex Web intentionally leaves browser/OS hotkeys to the browser' not in global_event:
    if global_event.count(hotkey_anchor) != 1:
        raise SystemExit('final compliance: global hotkey start anchor missing or duplicated')
    global_event = global_event.replace(hotkey_anchor, hotkey_replacement, 1)
    end_anchor = '''    default:\n      // console << "GlobalEvent: Unknown key pressed: " << key.id;\n      break;\n  }\n}'''
    end_replacement = '''    default:\n      // console << "GlobalEvent: Unknown key pressed: " << key.id;\n      break;\n  }\n#endif // __EMSCRIPTEN__ - Yandex Web intentionally leaves browser/OS hotkeys to the browser\n}'''
    if global_event.count(end_anchor) != 1:
        raise SystemExit('final compliance: global hotkey end anchor missing or duplicated')
    global_event = global_event.replace(end_anchor, end_replacement, 1)

global_path.write_text(global_event, encoding='utf-8')
print('Yandex final compliance: GameplayAPI sync + immediate saves + browser-safe hotkeys')

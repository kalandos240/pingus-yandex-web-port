from pathlib import Path

# Final Yandex lifecycle hardening. This patch runs after the base advertising,
# pause/resume and GameplayAPI patches have been applied.
#
# Important: current Yandex SDK documentation states that game_api_pause and
# game_api_resume are already coordinated with GameplayAPI.stop()/start().
# Therefore this patch intentionally does NOT send extra GameplayAPI calls from
# platform pause handlers. Native Pingus state owns start/stop for level/menu/
# internal pause transitions; Yandex owns the temporary platform transitions.
#
# Remaining moderation-sensitive details handled here:
#   1) flush completed-level progress to IDBFS immediately;
#   2) never unlock/resume audio while the platform/page is paused;
#   3) use only documented showFullscreenAdv callbacks;
#   4) disable legacy desktop hotkeys that collide with browser/OS commands.

shell_path = Path('../web/shell.html')
shell = shell_path.read_text(encoding='utf-8')

# A first pointer/key gesture is used to unlock browser audio. If a startup ad
# or another platform pause is active, do not let that gesture resume sound.
old_unlock = "      const unlockAudio = () => setAudioPaused(false);"
new_unlock = "      const unlockAudio = () => setAudioPaused(window.pingusPagePaused());"
if shell.count(old_unlock) != 1:
    raise SystemExit('final compliance: audio unlock anchor missing or duplicated')
shell = shell.replace(old_unlock, new_unlock, 1)

# showFullscreenAdv currently documents onOpen/onClose/onError. Remove an older
# compatibility callback key so SDK usage matches the public signature exactly.
onoffline = r'''                  onOffline: () => {
                    window.pingusSetPlatformPaused?.(false);
                    finish();
                  }
'''
if onoffline in shell:
    shell = shell.replace(r'''                  },
''' + onoffline, r'''                  }
''', 1)

shell_path.write_text(shell, encoding='utf-8')

# SavegameManager::store() has already written the updated progression to the
# Emscripten filesystem. Flush it to IndexedDB immediately so refreshing right
# after the result screen cannot lose the completed level/progress.
game_path = Path('src/pingus/screens/game_session.cpp')
game = game_path.read_text(encoding='utf-8')
save_anchor = '''      SavegameManager::instance()->store(savegame);\n    }'''
save_replacement = '''      SavegameManager::instance()->store(savegame);\n#ifdef __EMSCRIPTEN__\n      EM_ASM({\n        if (typeof window.pingusSaveNow === 'function')\n          window.pingusSaveNow();\n      });\n#endif\n    }'''
if 'window.pingusSaveNow' not in game:
    if game.count(save_anchor) != 1:
        raise SystemExit('final compliance: immediate save anchor missing or duplicated')
    game = game.replace(save_anchor, save_replacement, 1)
game_path.write_text(game, encoding='utf-8')

# Pingus' original desktop executable defines app actions on F5, F10, F11,
# F12, Alt+Enter, Ctrl+O, Ctrl+G, Ctrl+M, etc. In a browser these overlap
# standard browser/OS commands (Yandex requirement 1.6.2.6). Keep game/session
# controls elsewhere in Pingus, but leave these global desktop shortcuts to the
# browser in the Web target.
global_path = Path('src/pingus/global_event.cpp')
global_event = global_path.read_text(encoding='utf-8')
# patch_pingus.py runs earlier and modernizes SDL_GetKeyState to this form.
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

print('Yandex final compliance: immediate saves + documented ads + browser-safe hotkeys')

from pathlib import Path

# Mark only the actual playable level as Yandex GameplayAPI activity.
# Menus/result screens stay stopped, and Pingus' own pause button updates the
# gameplay marker immediately. Platform interruptions (ads, tab switches,
# purchase overlays) remain handled by game_api_pause/game_api_resume, which
# Yandex documents as already coordinated with GameplayAPI.

# Browser-side wrapper: keep only the latest requested native state while the
# SDK is still initializing, suppress duplicate start/stop calls, and never let
# an unavailable SDK break the game.
shell_path = Path('../web/shell.html')
shell = shell_path.read_text(encoding='utf-8')

sdk_anchor = '      window.yandexSDKPromise = (async () => {\n'
if shell.count(sdk_anchor) != 1:
    raise SystemExit('GameplayAPI SDK anchor missing or duplicated')

gameplay_code = r'''      let gameplayDesiredActive = false;
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

if 'window.pingusSetGameplayActive = (active) =>' not in shell:
    shell = shell.replace(sdk_anchor, gameplay_code + sdk_anchor, 1)

shell_path.write_text(shell, encoding='utf-8')

# Native lifecycle: GameSession exists only while an actual level is running.
# Start on level startup, stop on level completion/failure before replacing the
# screen, and mirror Pingus' own pause/resume state. ResultScreen and all menus
# therefore remain outside gameplay by construction.
game_path = Path('src/pingus/screens/game_session.cpp')
game = game_path.read_text(encoding='utf-8')

include_anchor = '#include "pingus/screens/game_session.hpp"\n'
include_replacement = '''#include "pingus/screens/game_session.hpp"\n\n#ifdef __EMSCRIPTEN__\n#  include <emscripten.h>\n#endif\n'''
if '<emscripten.h>' not in game:
    if game.count(include_anchor) != 1:
        raise SystemExit('GameplayAPI GameSession include anchor missing or duplicated')
    game = game.replace(include_anchor, include_replacement, 1)

finish_anchor = '''  if (server->is_finished())\n  {\n    PinguHolder* pingu_holder = server->get_world()->get_pingus();'''
finish_replacement = '''  if (server->is_finished())\n  {\n#ifdef __EMSCRIPTEN__\n    // The level has ended before ResultScreen/menu navigation begins.\n    EM_ASM({\n      if (typeof window.pingusSetGameplayActive === 'function')\n        window.pingusSetGameplayActive(false);\n    });\n#endif\n\n    PinguHolder* pingu_holder = server->get_world()->get_pingus();'''
if 'The level has ended before ResultScreen/menu navigation begins.' not in game:
    if game.count(finish_anchor) != 1:
        raise SystemExit('GameplayAPI level-finish anchor missing or duplicated')
    game = game.replace(finish_anchor, finish_replacement, 1)

startup_anchor = '''void\nGameSession::on_startup ()\n{\n  is_finished = false;'''
startup_replacement = '''void\nGameSession::on_startup ()\n{\n  is_finished = false;\n\n#ifdef __EMSCRIPTEN__\n  // A playable level is now active. This is the only screen that starts\n  // GameplayAPI; menus and result screens never do.\n  EM_ASM({\n    if (typeof window.pingusSetGameplayActive === 'function')\n      window.pingusSetGameplayActive(true);\n  });\n#endif'''
if 'A playable level is now active.' not in game:
    if game.count(startup_anchor) != 1:
        raise SystemExit('GameplayAPI level-start anchor missing or duplicated')
    game = game.replace(startup_anchor, startup_replacement, 1)

pause_anchor = '''void\nGameSession::set_pause(bool value)\n{\n  pause = value;\n  if (pause)\n  {\n    fast_forward = false;\n  }\n}'''
pause_replacement = '''void\nGameSession::set_pause(bool value)\n{\n  pause = value;\n  if (pause)\n  {\n    fast_forward = false;\n  }\n\n#ifdef __EMSCRIPTEN__\n  // Pingus' own pause button is an application-level pause, so it must be\n  // reflected explicitly in GameplayAPI. Platform pauses are handled by the\n  // existing game_api_pause/game_api_resume integration instead.\n  if (pause)\n  {\n    EM_ASM({\n      if (typeof window.pingusSetGameplayActive === 'function')\n        window.pingusSetGameplayActive(false);\n    });\n  }\n  else\n  {\n    EM_ASM({\n      if (typeof window.pingusSetGameplayActive === 'function')\n        window.pingusSetGameplayActive(true);\n    });\n  }\n#endif\n}'''
if 'Pingus\' own pause button is an application-level pause' not in game:
    if game.count(pause_anchor) != 1:
        raise SystemExit('GameplayAPI pause anchor missing or duplicated')
    game = game.replace(pause_anchor, pause_replacement, 1)

# Defensive synchronization for any code path that directly enables fast
# forward and clears pause without going through set_pause(false).
fast_anchor = '''  if (fast_forward)\n  {\n    pause = false;\n  }'''
fast_replacement = '''  if (fast_forward)\n  {\n    pause = false;\n#ifdef __EMSCRIPTEN__\n    EM_ASM({\n      if (typeof window.pingusSetGameplayActive === 'function')\n        window.pingusSetGameplayActive(true);\n    });\n#endif\n  }'''
if game.count(fast_anchor) != 1:
    raise SystemExit('GameplayAPI fast-forward anchor missing or duplicated')
game = game.replace(fast_anchor, fast_replacement, 1)

game_path.write_text(game, encoding='utf-8')

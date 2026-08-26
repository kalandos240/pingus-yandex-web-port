from pathlib import Path

# Yandex moderation requires fullscreen ads in real-time games to appear at a
# natural transition initiated by the player. Do not show an ad automatically
# when ResultScreen opens. Instead, request it only when the player clicks a
# result-screen action (continue, give up, or retry), immediately before the
# corresponding screen transition. Browser-side code enforces a 90-second
# minimum interval between requests.
p = Path('src/pingus/screens/result_screen.cpp')
s = p.read_text(encoding='utf-8')

include_anchor = '#include "pingus/screens/result_screen.hpp"\n'
include_replacement = '''#include "pingus/screens/result_screen.hpp"\n\n#ifdef __EMSCRIPTEN__\n#  include <emscripten.h>\n#endif\n'''
if '<emscripten.h>' not in s:
    if s.count(include_anchor) != 1:
        raise SystemExit('Yandex ad ResultScreen include anchor missing or duplicated')
    s = s.replace(include_anchor, include_replacement, 1)

helper_anchor = 'class ResultScreenComponent : public GUI::Component\n'
helper = '''#ifdef __EMSCRIPTEN__\nstatic void request_yandex_interstitial_after_result_action()\n{\n  EM_ASM({\n    if (typeof window.pingusShowInterstitialAfterResultAction === 'function')\n      window.pingusShowInterstitialAfterResultAction();\n  });\n}\n#else\nstatic void request_yandex_interstitial_after_result_action() {}\n#endif\n\n'''
if 'request_yandex_interstitial_after_result_action()' not in s:
    if s.count(helper_anchor) != 1:
        raise SystemExit('Yandex ad ResultScreen helper anchor missing or duplicated')
    s = s.replace(helper_anchor, helper + helper_anchor, 1)

replacements = [
    (
        '''  void on_click() {\n    parent->close_screen();\n    Sound::PingusSound::play_sound("yipee");\n  }''',
        '''  void on_click() {\n    request_yandex_interstitial_after_result_action();\n    parent->close_screen();\n    Sound::PingusSound::play_sound("yipee");\n  }'''
    ),
    (
        '''  void on_click() {\n    parent->close_screen();\n  }''',
        '''  void on_click() {\n    request_yandex_interstitial_after_result_action();\n    parent->close_screen();\n  }'''
    ),
    (
        '''  void on_click()\n  {\n    parent->retry_level();\n  }''',
        '''  void on_click()\n  {\n    request_yandex_interstitial_after_result_action();\n    parent->retry_level();\n  }'''
    ),
]
for old, new in replacements:
    if new not in s:
        if s.count(old) != 1:
            raise SystemExit('Yandex ad result-action anchor missing or duplicated')
        s = s.replace(old, new, 1)

p.write_text(s, encoding='utf-8')

# Add the browser-side cooldown and Yandex SDK call. This patch runs before CSP
# post-processing; postprocess_csp.py later moves this bootstrap into
# bootstrap.js, so the final archive still contains no inline JavaScript.
p = Path('../web/shell.html')
s = p.read_text(encoding='utf-8')

state_anchor = '      let autosaveTimer = 0;\n'
state_replacement = '''      let autosaveTimer = 0;\n      const INTERSTITIAL_MIN_INTERVAL_MS = 90000;\n      let interstitialInProgress = false;\n      let lastInterstitialAt = performance.now();\n'''
if 'const INTERSTITIAL_MIN_INTERVAL_MS = 90000;' not in s:
    if 'INTERSTITIAL_MIN_INTERVAL_MS' in s:
        import re
        s, count = re.subn(
            r'const INTERSTITIAL_MIN_INTERVAL_MS = \d+;',
            'const INTERSTITIAL_MIN_INTERVAL_MS = 90000;',
            s,
            count=1,
        )
        if count != 1:
            raise SystemExit('Yandex ad cooldown constant missing or duplicated')
    else:
        if s.count(state_anchor) != 1:
            raise SystemExit('Yandex ad shell state anchor missing or duplicated')
        s = s.replace(state_anchor, state_replacement, 1)

sdk_anchor = '''      window.yandexSDKPromise = (async () => {\n        try {\n          if (typeof YaGames === 'undefined') return null;\n          const ysdk = await YaGames.init();\n          window.ysdk = ysdk;'''
if sdk_anchor not in s:
    raise SystemExit('Yandex SDK shell anchor missing')

ad_code = r'''

      // Called only after the player explicitly clicks a result-screen action.
      // This makes the fullscreen ad part of a natural transition rather than
      // an automatic interruption. The first request is delayed for at least
      // 90 seconds after page load, and subsequent requests use the same
      // minimum interval.
      window.pingusShowInterstitialAfterResultAction = () => {
        if (interstitialInProgress) return;

        const now = performance.now();
        if (now - lastInterstitialAt < INTERSTITIAL_MIN_INTERVAL_MS) return;

        lastInterstitialAt = now;
        interstitialInProgress = true;

        (async () => {
          const ysdk = await window.yandexSDKPromise;
          if (typeof ysdk?.adv?.showFullscreenAdv !== 'function') return;

          await new Promise((resolve) => {
            let settled = false;
            const finish = () => {
              if (settled) return;
              settled = true;
              resolve();
            };

            try {
              ysdk.adv.showFullscreenAdv({
                callbacks: {
                  onOpen: () => {
                    window.pingusSetPlatformPaused?.(true);
                    window.pingusSaveNow?.();
                  },
                  onClose: () => {
                    window.pingusSetPlatformPaused?.(false);
                    finish();
                  },
                  onError: (error) => {
                    console.warn('Yandex fullscreen ad failed:', error);
                    window.pingusSetPlatformPaused?.(false);
                    finish();
                  },
                  onOffline: () => {
                    window.pingusSetPlatformPaused?.(false);
                    finish();
                  }
                }
              });
            } catch (error) {
              console.warn('Yandex fullscreen ad request failed:', error);
              window.pingusSetPlatformPaused?.(false);
              finish();
            }
          });
        })().catch((error) => {
          console.warn('Yandex fullscreen ad flow failed:', error);
          window.pingusSetPlatformPaused?.(false);
        }).finally(() => {
          interstitialInProgress = false;
        });
      };
'''

if 'window.pingusShowInterstitialAfterResultAction = () =>' not in s:
    s = s.replace('      window.yandexSDKPromise = (async () => {', ad_code + '\n      window.yandexSDKPromise = (async () => {', 1)

p.write_text(s, encoding='utf-8')

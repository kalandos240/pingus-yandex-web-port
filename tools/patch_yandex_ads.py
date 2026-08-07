from pathlib import Path

# Fullscreen Yandex ads are requested only from ResultScreen::on_startup(),
# i.e. after a level has already ended. There is intentionally no timer that
# can fire during active gameplay. JavaScript enforces a two-minute minimum
# interval between ad requests.
p = Path('src/pingus/screens/result_screen.cpp')
s = p.read_text(encoding='utf-8')

include_anchor = '#include "pingus/screens/result_screen.hpp"\n'
include_replacement = '''#include "pingus/screens/result_screen.hpp"\n\n#ifdef __EMSCRIPTEN__\n#  include <emscripten.h>\n#endif\n'''
if '<emscripten.h>' not in s:
    if s.count(include_anchor) != 1:
        raise SystemExit('Yandex ad ResultScreen include anchor missing or duplicated')
    s = s.replace(include_anchor, include_replacement, 1)

startup_tail = '''  else\n  {\n    Sound::PingusSound::play_music("pingus-2.it", 1.f, false);\n  }\n}'''
startup_replacement = '''  else\n  {\n    Sound::PingusSound::play_music("pingus-2.it", 1.f, false);\n  }\n\n#ifdef __EMSCRIPTEN__\n  // The result screen means gameplay has already ended. Requesting the ad\n  // here guarantees that the ad timer can never interrupt an active level.\n  EM_ASM({\n    if (typeof window.pingusShowInterstitialAfterLevel === 'function')\n      window.pingusShowInterstitialAfterLevel();\n  });\n#endif\n}'''
if 'pingusShowInterstitialAfterLevel' not in s:
    if s.count(startup_tail) != 1:
        raise SystemExit('Yandex ad ResultScreen startup anchor missing or duplicated')
    s = s.replace(startup_tail, startup_replacement, 1)

p.write_text(s, encoding='utf-8')

# Add the browser-side two-minute cooldown and Yandex SDK call. This patch runs
# before CSP post-processing; postprocess_csp.py later moves this bootstrap into
# bootstrap.js, so the final archive still contains no inline JavaScript.
p = Path('../web/shell.html')
s = p.read_text(encoding='utf-8')

state_anchor = '      let autosaveTimer = 0;\n'
state_replacement = '''      let autosaveTimer = 0;\n      const INTERSTITIAL_MIN_INTERVAL_MS = 120000;\n      let interstitialInProgress = false;\n      let lastInterstitialAt = performance.now();\n'''
if 'INTERSTITIAL_MIN_INTERVAL_MS' not in s:
    if s.count(state_anchor) != 1:
        raise SystemExit('Yandex ad shell state anchor missing or duplicated')
    s = s.replace(state_anchor, state_replacement, 1)

sdk_anchor = '''      window.yandexSDKPromise = (async () => {\n        try {\n          if (typeof YaGames === 'undefined') return null;\n          const ysdk = await YaGames.init();\n          window.ysdk = ysdk;'''
if sdk_anchor not in s:
    raise SystemExit('Yandex SDK shell anchor missing')

ad_code = r'''

      // Called only by the native ResultScreen after a level ends. The elapsed
      // time is checked here instead of using setInterval(), so a fullscreen ad
      // can never appear in the middle of gameplay. The first request is also
      // delayed until at least two minutes after the page was opened.
      window.pingusShowInterstitialAfterLevel = () => {
        if (interstitialInProgress) return;

        const now = performance.now();
        if (now - lastInterstitialAt < INTERSTITIAL_MIN_INTERVAL_MS) return;

        // Count attempts as part of the cooldown too. This avoids repeatedly
        // hammering the SDK on every short level when ads are unavailable.
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

if 'window.pingusShowInterstitialAfterLevel = () =>' not in s:
    # Place the ad function immediately before SDK initialization. It can safely
    # await yandexSDKPromise later when ResultScreen invokes it.
    s = s.replace('      window.yandexSDKPromise = (async () => {', ad_code + '\n      window.yandexSDKPromise = (async () => {', 1)

p.write_text(s, encoding='utf-8')

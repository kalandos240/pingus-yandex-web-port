from pathlib import Path

# Yandex moderation requirement 4.4: fullscreen ads must follow a deliberate
# user action in a logical pause. ResultScreen is already outside gameplay, so
# use its Continue/Retry/Give up (and equivalent keyboard) actions as the ad
# trigger. Never request an interstitial automatically from on_startup().
p = Path('src/pingus/screens/result_screen.cpp')
s = p.read_text(encoding='utf-8')

include_anchor = '#include "pingus/screens/result_screen.hpp"\n'
include_replacement = '''#include "pingus/screens/result_screen.hpp"\n\n#ifdef __EMSCRIPTEN__\n#  include <emscripten.h>\n#  include <stdint.h>\n#endif\n'''
if '<emscripten.h>' not in s:
    if s.count(include_anchor) != 1:
        raise SystemExit('Yandex ad ResultScreen include anchor missing or duplicated')
    s = s.replace(include_anchor, include_replacement, 1)

# The JavaScript ad flow keeps ResultScreen alive while the platform overlay is
# open and calls this exported continuation only after onClose/onError. The
# guard prevents the continuation from requesting another ad recursively.
class_anchor = 'class ResultScreenComponent : public GUI::Component\n'
bridge_code = r'''#ifdef __EMSCRIPTEN__
static bool g_yandex_result_ad_continuation = false;

extern "C" EMSCRIPTEN_KEEPALIVE void
pingus_result_continue_after_ad(ResultScreen* screen, int retry)
{
  if (!screen)
    return;

  g_yandex_result_ad_continuation = true;
  if (retry)
    screen->retry_level();
  else
    screen->close_screen();
  g_yandex_result_ad_continuation = false;
}

static bool
pingus_request_result_interstitial(ResultScreen* screen, bool retry)
{
  if (g_yandex_result_ad_continuation)
    return false;

  return EM_ASM_INT({
    if (typeof window.pingusShowInterstitialFromUserAction !== 'function')
      return 0;
    return window.pingusShowInterstitialFromUserAction($0, $1) ? 1 : 0;
  }, static_cast<int>(reinterpret_cast<intptr_t>(screen)), retry ? 1 : 0) != 0;
}
#endif

'''
if 'pingus_result_continue_after_ad' not in s:
    if s.count(class_anchor) != 1:
        raise SystemExit('Yandex ad ResultScreen class anchor missing or duplicated')
    s = s.replace(class_anchor, bridge_code + class_anchor, 1)

retry_anchor = '''void\nResultScreen::retry_level()\n{\n  ScreenManager::instance()->replace_screen(std::make_shared<GameSession>(result.plf, true));\n}'''
retry_replacement = '''void\nResultScreen::retry_level()\n{\n#ifdef __EMSCRIPTEN__\n  // Retry is a deliberate user action on the result screen. If an ad starts,\n  // keep this screen in place until the ad callback continues the action.\n  if (pingus_request_result_interstitial(this, true))\n    return;\n#endif\n  ScreenManager::instance()->replace_screen(std::make_shared<GameSession>(result.plf, true));\n}'''
if 'Retry is a deliberate user action on the result screen.' not in s:
    if s.count(retry_anchor) != 1:
        raise SystemExit('Yandex ad ResultScreen retry anchor missing or duplicated')
    s = s.replace(retry_anchor, retry_replacement, 1)

close_anchor = '''void\nResultScreen::close_screen()\n{\n  ScreenManager::instance()->pop_screen();\n}'''
close_replacement = '''void\nResultScreen::close_screen()\n{\n#ifdef __EMSCRIPTEN__\n  // Continue/Give up/Escape are deliberate result-screen actions. This makes\n  // the interstitial predictable and compliant with Yandex requirement 4.4.\n  if (pingus_request_result_interstitial(this, false))\n    return;\n#endif\n  ScreenManager::instance()->pop_screen();\n}'''
if 'Continue/Give up/Escape are deliberate result-screen actions.' not in s:
    if s.count(close_anchor) != 1:
        raise SystemExit('Yandex ad ResultScreen close anchor missing or duplicated')
    s = s.replace(close_anchor, close_replacement, 1)

# Guard against regression to the rejected automatic-ad behavior.
if 'pingusShowInterstitialAfterLevel' in s:
    raise SystemExit('automatic ResultScreen startup ad call is still present')

p.write_text(s, encoding='utf-8')

# Browser side: the ad request itself is made synchronously from the native
# click/key handler while the Yandex SDK instance is already available. There
# is no timer-driven ad and no await before showFullscreenAdv(), so the request
# remains directly tied to the user's action. A two-minute cooldown limits
# frequency; when no ad is eligible, native navigation continues immediately.
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

      // Called synchronously from a ResultScreen user action. Return true only
      // when an interstitial has actually been started and native navigation
      // must wait for its callback. No automatic/timer-based ad path exists.
      window.pingusShowInterstitialFromUserAction = (screenPtr, retry) => {
        if (interstitialInProgress) return true;

        const ysdk = window.ysdk;
        if (typeof ysdk?.adv?.showFullscreenAdv !== 'function') return false;

        const now = performance.now();
        if (now - lastInterstitialAt < INTERSTITIAL_MIN_INTERVAL_MS) return false;

        const continueNative = () => {
          const fn = window.Module?._pingus_result_continue_after_ad;
          if (typeof fn !== 'function') {
            console.error('Pingus result-screen ad continuation is unavailable');
            return;
          }
          // Avoid re-entering native GUI code from inside the SDK callback.
          window.setTimeout(() => fn(screenPtr, retry ? 1 : 0), 0);
        };

        let settled = false;
        const finish = () => {
          if (settled) return;
          settled = true;
          interstitialInProgress = false;
          window.pingusSetPlatformPaused?.(false);
          continueNative();
        };

        try {
          interstitialInProgress = true;
          lastInterstitialAt = now;
          ysdk.adv.showFullscreenAdv({
            callbacks: {
              onOpen: () => {
                window.pingusSetPlatformPaused?.(true);
                window.pingusSaveNow?.();
              },
              onClose: finish,
              onError: (error) => {
                console.warn('Yandex fullscreen ad failed:', error);
                finish();
              }
            }
          });
          return true;
        } catch (error) {
          console.warn('Yandex fullscreen ad request failed:', error);
          interstitialInProgress = false;
          window.pingusSetPlatformPaused?.(false);
          return false;
        }
      };
'''

if 'window.pingusShowInterstitialFromUserAction = (screenPtr, retry) =>' not in s:
    if 'window.pingusShowInterstitialAfterLevel = () =>' in s:
        raise SystemExit('legacy automatic interstitial function still present in shell')
    s = s.replace('      window.yandexSDKPromise = (async () => {', ad_code + '\n      window.yandexSDKPromise = (async () => {', 1)

p.write_text(s, encoding='utf-8')

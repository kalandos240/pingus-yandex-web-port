from pathlib import Path

# YaGames.init() can resolve before Emscripten has created its ENV object.
# Keep the selected language in JS and apply it again from preRun, where ENV
# definitely exists and main() has not started yet. When the Yandex SDK is
# available it is also the sole source of the startup language: navigator is
# used only as a genuine SDK-failure fallback, never before the SDK responds.

p = Path('../web/shell.html')
s = p.read_text(encoding='utf-8')

# Avoid flashing an English/Russian loading word before Yandex tells us the
# actual locale. The title and progress bar are language-neutral; applyLanguage
# replaces this ellipsis as soon as YaGames.init() resolves.
old_status = '<div id="loading-status">Loading…</div>'
new_status = '<div id="loading-status">…</div>'
if s.count(old_status) != 1:
    raise SystemExit('Yandex neutral loading-status anchor missing or duplicated')
s = s.replace(old_status, new_status, 1)

old_apply = '''      const applyLanguage = (value) => {\n        uiLanguage = normalizeLanguage(value);\n        document.documentElement.lang = uiLanguage;\n        if (!gameReadySent) status.textContent = text[uiLanguage].loading;\n        try {\n          const locale = uiLanguage === 'ru' ? 'ru_RU.UTF-8' : 'en_US.UTF-8';\n          ENV.LANG = locale;\n          ENV.LC_ALL = locale;\n        } catch (_) {}\n      };'''
new_apply = '''      const applyEnvironmentLocale = () => {\n        if (typeof ENV === 'undefined') return false;\n        const locale = uiLanguage === 'ru' ? 'ru_RU.UTF-8' : 'en_US.UTF-8';\n        ENV.LANG = locale;\n        ENV.LC_ALL = locale;\n        return true;\n      };\n\n      const applyLanguage = (value) => {\n        uiLanguage = normalizeLanguage(value);\n        document.documentElement.lang = uiLanguage;\n        if (!gameReadySent) status.textContent = text[uiLanguage].loading;\n        // This succeeds if Emscripten is already initialized. If the SDK wins\n        // the startup race, preRun below repeats it at the guaranteed-safe time.\n        applyEnvironmentLocale();\n      };\n      window.pingusApplyEnvironmentLocale = applyEnvironmentLocale;'''
if s.count(old_apply) != 1:
    raise SystemExit('Yandex locale applyLanguage anchor missing or duplicated')
s = s.replace(old_apply, new_apply, 1)

old_missing_sdk = "          if (typeof YaGames === 'undefined') return null;"
new_missing_sdk = "          if (typeof YaGames === 'undefined') {\n            applyLanguage(navigator.language);\n            return null;\n          }"
if s.count(old_missing_sdk) != 1:
    raise SystemExit('Yandex missing-SDK language fallback anchor missing or duplicated')
s = s.replace(old_missing_sdk, new_missing_sdk, 1)

old_catch = '''        } catch (error) {\n          console.warn('Yandex Games SDK initialization failed:', error);\n          return null;\n        }'''
new_catch = '''        } catch (error) {\n          console.warn('Yandex Games SDK initialization failed:', error);\n          // Browser locale is only a fallback when the platform SDK itself\n          // failed. It must not race the authoritative environment.i18n.lang.\n          applyLanguage(navigator.language);\n          return null;\n        }'''
if s.count(old_catch) != 1:
    raise SystemExit('Yandex SDK failure fallback anchor missing or duplicated')
s = s.replace(old_catch, new_catch, 1)

# The old shell eagerly applied navigator.language before YaGames.init(). That
# could briefly show the wrong loading language and, in a tight startup race,
# seed tinygettext with the wrong locale. Remove that eager application.
old_eager = '      applyLanguage(navigator.language);\n\n      window.Module = {'
new_eager = '''      // Keep the pre-SDK loading UI language-neutral. Yandex\n      // environment.i18n.lang is applied above as soon as the SDK resolves.\n\n      window.Module = {'''
if s.count(old_eager) != 1:
    raise SystemExit('Yandex eager navigator language anchor missing or duplicated')
s = s.replace(old_eager, new_eager, 1)

old_wait = '''          addRunDependency('pingus-locale');\n          Promise.race([\n            window.yandexSDKPromise,\n            new Promise((resolve) => window.setTimeout(() => resolve(null), 4000))\n          ]).finally(() => removeRunDependency('pingus-locale'));'''
new_wait = '''          addRunDependency('pingus-locale');\n          Promise.race([\n            window.yandexSDKPromise,\n            new Promise((resolve) => window.setTimeout(() => {\n              // If an SDK response never arrives, only then use navigator as\n              // a last-resort locale so the game cannot wait forever.\n              applyLanguage(navigator.language);\n              resolve(null);\n            }, 4000))\n          ]).finally(() => {\n            // ENV exists in preRun and main() has not started yet. Re-apply the\n            // language selected by Yandex (or the true fallback above) so\n            // tinygettext sees the correct locale on first initialization.\n            window.pingusApplyEnvironmentLocale();\n            removeRunDependency('pingus-locale');\n          });'''
if s.count(old_wait) != 1:
    raise SystemExit('Yandex locale preRun anchor missing or duplicated')
s = s.replace(old_wait, new_wait, 1)

p.write_text(s, encoding='utf-8')

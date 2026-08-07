from pathlib import Path

# YaGames.init() can resolve before Emscripten has created its ENV object.
# The shell used to update only its own text in that race: applyLanguage()
# attempted ENV.LANG/LC_ALL, caught ReferenceError, and never retried before
# Pingus initialized tinygettext. Keep the selected language in JS and apply it
# again from preRun, where ENV definitely exists and main() has not started yet.

p = Path('../web/shell.html')
s = p.read_text(encoding='utf-8')

old_apply = '''      const applyLanguage = (value) => {\n        uiLanguage = normalizeLanguage(value);\n        document.documentElement.lang = uiLanguage;\n        if (!gameReadySent) status.textContent = text[uiLanguage].loading;\n        try {\n          const locale = uiLanguage === 'ru' ? 'ru_RU.UTF-8' : 'en_US.UTF-8';\n          ENV.LANG = locale;\n          ENV.LC_ALL = locale;\n        } catch (_) {}\n      };'''
new_apply = '''      const applyEnvironmentLocale = () => {\n        if (typeof ENV === 'undefined') return false;\n        const locale = uiLanguage === 'ru' ? 'ru_RU.UTF-8' : 'en_US.UTF-8';\n        ENV.LANG = locale;\n        ENV.LC_ALL = locale;\n        return true;\n      };\n\n      const applyLanguage = (value) => {\n        uiLanguage = normalizeLanguage(value);\n        document.documentElement.lang = uiLanguage;\n        if (!gameReadySent) status.textContent = text[uiLanguage].loading;\n        // This succeeds if Emscripten is already initialized. If the SDK wins\n        // the startup race, preRun below repeats it at the guaranteed-safe time.\n        applyEnvironmentLocale();\n      };\n      window.pingusApplyEnvironmentLocale = applyEnvironmentLocale;'''
if s.count(old_apply) != 1:
    raise SystemExit('Yandex locale applyLanguage anchor missing or duplicated')
s = s.replace(old_apply, new_apply, 1)

old_wait = '''          addRunDependency('pingus-locale');\n          Promise.race([\n            window.yandexSDKPromise,\n            new Promise((resolve) => window.setTimeout(() => resolve(null), 4000))\n          ]).finally(() => removeRunDependency('pingus-locale'));'''
new_wait = '''          addRunDependency('pingus-locale');\n          Promise.race([\n            window.yandexSDKPromise,\n            new Promise((resolve) => window.setTimeout(() => resolve(null), 4000))\n          ]).finally(() => {\n            // ENV exists in preRun and main() has not started yet. Re-apply the\n            // language selected by Yandex (or navigator fallback) so tinygettext\n            // sees the correct locale on its first initialization.\n            window.pingusApplyEnvironmentLocale();\n            removeRunDependency('pingus-locale');\n          });'''
if s.count(old_wait) != 1:
    raise SystemExit('Yandex locale preRun anchor missing or duplicated')
s = s.replace(old_wait, new_wait, 1)

p.write_text(s, encoding='utf-8')

from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: post_harden_audio_resume.py ADAPTER_JS')

path = Path(sys.argv[1])
if not path.is_file():
    raise SystemExit(f'Playgama adapter missing: {path}')
s = path.read_text(encoding='utf-8')

anchor = '''        trackedAudioContexts.add(context);\n        if (!platformAudioEnabled || pauseReasons.size || document.hidden) {\n          queueMicrotask(() => context.suspend?.().catch?.(() => {}));\n        }\n        return context;'''
replacement = '''        trackedAudioContexts.add(context);\n        // SDL/OpenAL may call resume() after the context was constructed. Guard\n        // that late resume too, otherwise a reload while Playgama remains muted\n        // can become audible again after our initial suspend.\n        const nativeResume = context.resume?.bind(context);\n        if (nativeResume) {\n          try {\n            Object.defineProperty(context, 'resume', {\n              configurable: true,\n              value: (...resumeArgs) => {\n                if (!platformAudioEnabled || pauseReasons.size || document.hidden)\n                  return Promise.resolve();\n                return nativeResume(...resumeArgs);\n              }\n            });\n          } catch (_) {}\n        }\n        if (!platformAudioEnabled || pauseReasons.size || document.hidden) {\n          queueMicrotask(() => context.suspend?.().catch?.(() => {}));\n        }\n        return context;'''

if s.count(anchor) != 1:
    raise SystemExit('late AudioContext resume anchor missing or duplicated')
s = s.replace(anchor, replacement, 1)
path.write_text(s, encoding='utf-8')
print('Playgama audio hardening: late AudioContext.resume() remains blocked while muted/paused')

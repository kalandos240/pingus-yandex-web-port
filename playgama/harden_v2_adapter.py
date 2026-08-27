from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: harden_v2_adapter.py DIST_DIR_OR_ADAPTER_JS')

arg = Path(sys.argv[1])
path = arg if arg.is_file() or arg.suffix == '.js' else arg / 'playgama-yandex-compat.js'
if not path.is_file():
    raise SystemExit(f'Playgama adapter not found: {path}')
s = path.read_text(encoding='utf-8')

old = '''  const setPauseReason = (reason, active) => {\n    const wasPaused = pauseReasons.size > 0;\n    if (active) pauseReasons.add(reason); else pauseReasons.delete(reason);\n    const isPaused = pauseReasons.size > 0;\n    if (wasPaused !== isPaused) emitPauseState();\n  };'''
new = '''  const setPauseReason = (reason, active) => {\n    const wasPaused = pauseReasons.size > 0;\n    if (active) pauseReasons.add(reason); else pauseReasons.delete(reason);\n    const isPaused = pauseReasons.size > 0;\n    if (wasPaused !== isPaused) {\n      // A Playgama QA/platform pause may arrive while the game is still\n      // booting. Remember it immediately and mute audio, but never freeze the\n      // Emscripten loop before Pingus has produced its first ready frame.\n      if (gameReadySent) emitPauseState();\n      else if (isPaused) pauseTrackedAudio();\n    }\n  };'''
if s.count(old) != 1:
    raise SystemExit('pause gate anchor missing or duplicated')
s = s.replace(old, new, 1)

count = s.count('bridge.advertisement?.setMinimumDelayBetweenInterstitial?.(120);')
if count != 1:
    raise SystemExit('interstitial delay anchor missing or duplicated')
s = s.replace(
    'bridge.advertisement?.setMinimumDelayBetweenInterstitial?.(120);',
    'bridge.advertisement?.setMinimumDelayBetweenInterstitial?.(90);',
    1,
)

old = '''    // v2 storage automatically uses platform cloud storage when available and\n    // falls back to local storage otherwise. No v1 storage-type argument is used.\n    try {\n      const markerKey = '__playgama_bridge_port_v2';\n      await bridge.storage.get(markerKey).catch(() => undefined);\n      await bridge.storage.set(markerKey, { version: 2, updatedAt: Date.now() });\n    } catch (error) {\n      console.info('[Playgama] storage unavailable; native/local persistence remains available.', error);\n    }'''
new = '''    // Probe v2 storage in the background. Storage health must never gate the\n    // first frame; the production Pingus cloud layer already has bounded\n    // timeouts and keeps IDBFS as a local fallback.\n    Promise.resolve().then(async () => {\n      const markerKey = '__playgama_bridge_port_v2';\n      await bridge.storage.get(markerKey).catch(() => undefined);\n      await bridge.storage.set(markerKey, { version: 2, updatedAt: Date.now() });\n    }).catch((error) => {\n      console.info('[Playgama] storage unavailable; native/local persistence remains available.', error);\n    });'''
if s.count(old) != 1:
    raise SystemExit('storage probe anchor missing or duplicated')
s = s.replace(old, new, 1)

old = '''          ready() {\n            if (gameReadySent) return Promise.resolve(false);\n            gameReadySent = true;\n            return sendPlatformMessage(bridge, bridge.PLATFORM_MESSAGE?.GAME_READY || 'game_ready').then(() => true);\n          }'''
new = '''          ready() {\n            if (gameReadySent) return Promise.resolve(false);\n            gameReadySent = true;\n            // Apply any pause that arrived during startup only after Pingus has\n            // already produced its first frame and hidden the loading screen.\n            if (pauseReasons.size) queueMicrotask(emitPauseState);\n            return sendPlatformMessage(bridge, bridge.PLATFORM_MESSAGE?.GAME_READY || 'game_ready').then(() => true);\n          }'''
if s.count(old) != 1:
    raise SystemExit('game_ready pause flush anchor missing or duplicated')
s = s.replace(old, new, 1)

path.write_text(s, encoding='utf-8')
print('Playgama v2 adapter hardened: pre-ready pause gated, storage probe non-blocking, 90s ad interval')

from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: harden_v2_adapter.py DIST_DIR_OR_ADAPTER_JS')

arg = Path(sys.argv[1])
path = arg if arg.is_file() or arg.suffix == '.js' else arg / 'playgama-yandex-compat.js'
if not path.is_file():
    raise SystemExit(f'Playgama adapter not found: {path}')
s = path.read_text(encoding='utf-8')

# Keep separate notions of "Pingus asked to report ready" and "a real painted
# frame has been observed". Playgama's QA UI may keep platform pause active
# while it asks a manual question; propagating that pause before the first
# painted frame can freeze Emscripten on an all-white canvas.
old = '''  let gameReadySent = false;\n  let gameplayStarted = false;\n  let platformAudioEnabled = true;'''
new = '''  let gameReadySent = false;\n  let gameReadyRequested = false;\n  let runtimePauseEnabled = false;\n  let gameplayStarted = false;\n  let platformAudioEnabled = true;\n  const deferredMedia = new Set();'''
if s.count(old) != 1:
    raise SystemExit('startup state anchor missing or duplicated')
s = s.replace(old, new, 1)

# Audio can be created after bridge.initialize(). If Playgama is already muted
# at that point, newly-created contexts must start suspended instead of briefly
# becoming audible after a reload.
old = '''        const context = Reflect.construct(target, args, newTarget === WrappedAudioContext ? target : newTarget);\n        trackedAudioContexts.add(context);\n        return context;'''
new = '''        const context = Reflect.construct(target, args, newTarget === WrappedAudioContext ? target : newTarget);\n        trackedAudioContexts.add(context);\n        if (!platformAudioEnabled || pauseReasons.size || document.hidden) {\n          queueMicrotask(() => context.suspend?.().catch?.(() => {}));\n        }\n        return context;'''
if s.count(old) != 1:
    raise SystemExit('AudioContext constructor anchor missing or duplicated')
s = s.replace(old, new, 1)

# SDL_mixer also creates detached HTMLAudioElement instances. querySelectorAll
# cannot see those, so guard HTMLMediaElement.play() itself while the platform
# is muted/paused and replay only media whose play was explicitly deferred.
anchor = '''  const pauseTrackedAudio = () => {'''
media_guard = '''  const NativeMediaPlay = window.HTMLMediaElement?.prototype?.play;\n  if (NativeMediaPlay && !NativeMediaPlay.__playgamaMuteGuard) {\n    const guardedMediaPlay = function(...args) {\n      if (!platformAudioEnabled || pauseReasons.size || document.hidden) {\n        deferredMedia.add(this);\n        try { this.pause?.(); } catch (_) {}\n        return Promise.resolve();\n      }\n      return NativeMediaPlay.apply(this, args);\n    };\n    guardedMediaPlay.__playgamaMuteGuard = true;\n    guardedMediaPlay.__playgamaNativePlay = NativeMediaPlay;\n    window.HTMLMediaElement.prototype.play = guardedMediaPlay;\n  }\n\n  const knownMedia = () => {\n    const media = new Set(document.querySelectorAll('audio,video'));\n    const music = window.SDL?.music?.audio;\n    if (music) media.add(music);\n    const channels = window.SDL?.channels;\n    if (Array.isArray(channels)) {\n      for (const channel of channels) if (channel?.audio) media.add(channel.audio);\n    }\n    return media;\n  };\n\n  const pauseTrackedAudio = () => {'''
if s.count(anchor) != 1:
    raise SystemExit('media guard insertion anchor missing or duplicated')
s = s.replace(anchor, media_guard, 1)

old = '''    document.querySelectorAll('audio,video').forEach((media) => {\n      if (!media.paused) {\n        pausedMedia.add(media);\n        try { media.pause(); } catch (_) {}\n      }\n    });'''
new = '''    knownMedia().forEach((media) => {\n      if (!media.paused) {\n        pausedMedia.add(media);\n        try { media.pause(); } catch (_) {}\n      }\n    });'''
if s.count(old) != 1:
    raise SystemExit('pause media anchor missing or duplicated')
s = s.replace(old, new, 1)

old = '''    Array.from(pausedMedia).forEach((media) => {\n      pausedMedia.delete(media);\n      try { media.play?.().catch?.(() => {}); } catch (_) {}\n    });'''
new = '''    const toResume = new Set([...pausedMedia, ...deferredMedia]);\n    pausedMedia.clear();\n    deferredMedia.clear();\n    toResume.forEach((media) => {\n      try {\n        const nativePlay = window.HTMLMediaElement?.prototype?.play?.__playgamaNativePlay;\n        const result = nativePlay ? nativePlay.call(media) : media.play?.();\n        result?.catch?.(() => {});\n      } catch (_) {}\n    });'''
if s.count(old) != 1:
    raise SystemExit('resume media anchor missing or duplicated')
s = s.replace(old, new, 1)

# A runtime pause is allowed only after a non-white gameplay frame was sampled.
# Before that, remember the state and mute audio, but keep Emscripten advancing.
old = '''  const setPauseReason = (reason, active) => {\n    const wasPaused = pauseReasons.size > 0;\n    if (active) pauseReasons.add(reason); else pauseReasons.delete(reason);\n    const isPaused = pauseReasons.size > 0;\n    if (wasPaused !== isPaused) emitPauseState();\n  };'''
new = '''  const setPauseReason = (reason, active) => {\n    const wasPaused = pauseReasons.size > 0;\n    if (active) pauseReasons.add(reason); else pauseReasons.delete(reason);\n    const isPaused = pauseReasons.size > 0;\n    if (wasPaused !== isPaused) {\n      if (runtimePauseEnabled) emitPauseState();\n      else if (isPaused) pauseTrackedAudio();\n    }\n  };\n\n  const canvasHasPaintedFrame = () => {\n    const canvas = document.getElementById('canvas');\n    if (!canvas || canvas.width < 8 || canvas.height < 8) return false;\n    try {\n      const ctx = canvas.getContext('2d', { willReadFrequently: true });\n      if (!ctx) return false;\n      const data = ctx.getImageData(0, 0, canvas.width, canvas.height).data;\n      const xStep = Math.max(1, Math.floor(canvas.width / 24));\n      const yStep = Math.max(1, Math.floor(canvas.height / 18));\n      let nonWhite = 0;\n      for (let y = Math.floor(yStep / 2); y < canvas.height; y += yStep) {\n        for (let x = Math.floor(xStep / 2); x < canvas.width; x += xStep) {\n          const i = (y * canvas.width + x) * 4;\n          if (data[i + 3] > 16 && (data[i] < 245 || data[i + 1] < 245 || data[i + 2] < 245)) {\n            if (++nonWhite >= 8) return true;\n          }\n        }\n      }\n    } catch (_) {}\n    return false;\n  };\n\n  const waitForPaintedFrame = () => new Promise((resolve) => {\n    const started = performance.now();\n    const inspect = () => {\n      if (canvasHasPaintedFrame()) {\n        resolve(true);\n        return;\n      }\n      // Do not let a canvas readback quirk permanently block game_ready. Eight\n      // seconds is far beyond the normal Pingus first-frame time while still\n      // keeping startup bounded for the platform.\n      if (performance.now() - started >= 8000) {\n        console.warn('[Playgama] painted-frame gate timed out; releasing startup defensively');\n        resolve(false);\n        return;\n      }\n      requestAnimationFrame(inspect);\n    };\n    requestAnimationFrame(() => requestAnimationFrame(inspect));\n  });'''
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

# Read both platform states at startup. Some Playgama checks intentionally
# reload while muted/paused and do not need to emit a fresh event afterwards.
old = '''    platformAudioEnabled = bridge.platform?.isAudioEnabled !== false;\n    if (!platformAudioEnabled) pauseTrackedAudio();\n\n    try {'''
new = '''    platformAudioEnabled = bridge.platform?.isAudioEnabled !== false;\n    if (!platformAudioEnabled) pauseTrackedAudio();\n    setPauseReason('platform', bridge.platform?.isPaused === true);\n\n    try {'''
if s.count(old) != 1:
    raise SystemExit('initial platform state anchor missing or duplicated')
s = s.replace(old, new, 1)

old = '''    // v2 storage automatically uses platform cloud storage when available and\n    // falls back to local storage otherwise. No v1 storage-type argument is used.\n    try {\n      const markerKey = '__playgama_bridge_port_v2';\n      await bridge.storage.get(markerKey).catch(() => undefined);\n      await bridge.storage.set(markerKey, { version: 2, updatedAt: Date.now() });\n    } catch (error) {\n      console.info('[Playgama] storage unavailable; native/local persistence remains available.', error);\n    }'''
new = '''    // Probe v2 storage in the background. Storage health must never gate the\n    // first frame; the production Pingus cloud layer has its own fallback.\n    Promise.resolve().then(async () => {\n      const markerKey = '__playgama_bridge_port_v2';\n      await bridge.storage.get(markerKey).catch(() => undefined);\n      await bridge.storage.set(markerKey, { version: 2, updatedAt: Date.now() });\n    }).catch((error) => {\n      console.info('[Playgama] storage unavailable; native/local persistence remains available.', error);\n    });'''
if s.count(old) != 1:
    raise SystemExit('storage probe anchor missing or duplicated')
s = s.replace(old, new, 1)

# LoadingAPI.ready is requested by Pingus after native initialization, but the
# platform message and any queued pause are released only after the canvas is
# actually painted. This matches what Playgama's manual QA question displays.
old = '''          ready() {\n            if (gameReadySent) return Promise.resolve(false);\n            gameReadySent = true;\n            return sendPlatformMessage(bridge, bridge.PLATFORM_MESSAGE?.GAME_READY || 'game_ready').then(() => true);\n          }'''
new = '''          ready() {\n            if (gameReadyRequested) return Promise.resolve(false);\n            gameReadyRequested = true;\n            return waitForPaintedFrame().then(async () => {\n              runtimePauseEnabled = true;\n              gameReadySent = true;\n              const sent = await sendPlatformMessage(bridge, bridge.PLATFORM_MESSAGE?.GAME_READY || 'game_ready');\n              if (pauseReasons.size) queueMicrotask(emitPauseState);\n              return sent !== false;\n            });\n          }'''
if s.count(old) != 1:
    raise SystemExit('game_ready painted-frame anchor missing or duplicated')
s = s.replace(old, new, 1)

# Track the initial browser visibility in addition to future events.
old = '''  document.addEventListener('visibilitychange', () => {\n    setPauseReason('document-hidden', document.hidden);\n  });'''
new = '''  setPauseReason('document-hidden', document.hidden);\n  document.addEventListener('visibilitychange', () => {\n    setPauseReason('document-hidden', document.hidden);\n  });'''
if s.count(old) != 1:
    raise SystemExit('document visibility anchor missing or duplicated')
s = s.replace(old, new, 1)

path.write_text(s, encoding='utf-8')
print('Playgama v2 adapter hardened: painted-frame pause gate, startup mute persistence, initial platform state, 90s ads')

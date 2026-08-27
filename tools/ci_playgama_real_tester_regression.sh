#!/usr/bin/env bash
set -euxo pipefail

# Main multilingual CI already built dist/. Apply the final audio-resume guard
# to the exact adapter that will ship, then reproduce the Playgama tester state:
# language switch/reload while the platform is both paused and muted.
python3 playgama/post_harden_audio_resume.py dist/playgama-yandex-compat.js
node --check dist/playgama-yandex-compat.js

grep -q 'canvasHasPaintedFrame' dist/playgama-yandex-compat.js
grep -q 'runtimePauseEnabled' dist/playgama-yandex-compat.js
grep -q 'isAudioEnabled !== false' dist/playgama-yandex-compat.js
grep -q "isPaused === true" dist/playgama-yandex-compat.js
grep -q '__playgamaMuteGuard' dist/playgama-yandex-compat.js
grep -q 'late resume' dist/playgama-yandex-compat.js

python3 - <<'PY'
from pathlib import Path
html = Path('dist/index.html').read_text(encoding='utf-8')
remote = 'https://bridge.playgama.com/v2/stable/playgama-bridge.js'
if html.count(remote) != 1:
    raise SystemExit('Playgama Bridge v2 script anchor missing')

for lang in ('en', 'ru'):
    Path(f'dist/real-qa-{lang}.html').write_text(
        html.replace(remote, f'real-qa-bridge-{lang}.js'), encoding='utf-8'
    )
    js = r'''(() => {
  const LANG = __LANG__;
  const listeners = new Map();
  const storage = new Map();
  const on = (name, cb) => {
    const list = listeners.get(name) || [];
    list.push(cb);
    listeners.set(name, list);
    // Reproduce the real tester: state is already active when the game reloads,
    // and the subscription may synchronously reveal it during initialization.
    if (name === 'pause_state_changed') cb(true);
    if (name === 'audio_state_changed') cb(false);
  };
  const off = (name, cb) => listeners.set(name, (listeners.get(name) || []).filter(x => x !== cb));
  const signal = (name) => fetch('/__realqa_' + LANG + '_' + name + '__').catch(() => {});
  const nonWhiteCanvas = () => {
    const canvas = document.getElementById('canvas');
    try {
      const ctx = canvas?.getContext('2d', { willReadFrequently: true });
      const data = ctx?.getImageData(0, 0, canvas.width, canvas.height).data;
      if (!data) return false;
      let nonWhite = 0;
      for (let i = 0; i < data.length; i += 6000) {
        if (data[i + 3] > 16 && (data[i] < 245 || data[i + 1] < 245 || data[i + 2] < 245)) {
          if (++nonWhite >= 8) return true;
        }
      }
    } catch (_) {}
    return false;
  };
  const inspectMutedState = async () => {
    // A detached HTMLAudioElement is exactly the class SDL_mixer uses. When the
    // platform is muted its play() must be intercepted instead of going native.
    const probe = document.createElement('audio');
    try {
      await probe.play();
      signal('media_guard_ok');
    } catch (_) {
      signal('media_guard_bad');
    }

    let running = false;
    const context = window.SDL?.audioContext || window.SDL2?.audioContext || window.AL?.currentContext?.audioCtx || null;
    if (context?.state === 'running') running = true;
    const media = [];
    if (window.SDL?.music?.audio) media.push(window.SDL.music.audio);
    if (Array.isArray(window.SDL?.channels)) {
      for (const channel of window.SDL.channels) if (channel?.audio) media.push(channel.audio);
    }
    if (media.some(audio => audio && !audio.paused)) running = true;
    signal(running ? 'audio_bad' : 'audio_silent');
  };

  window.bridge = {
    version: '2.1.0',
    EVENT_NAME: {
      PAUSE_STATE_CHANGED: 'pause_state_changed',
      AUDIO_STATE_CHANGED: 'audio_state_changed',
      INTERSTITIAL_STATE_CHANGED: 'interstitial_state_changed',
      REWARDED_STATE_CHANGED: 'rewarded_state_changed'
    },
    INTERSTITIAL_STATE: { OPENED: 'opened', CLOSED: 'closed', FAILED: 'failed' },
    REWARDED_STATE: { OPENED: 'opened', REWARDED: 'rewarded', CLOSED: 'closed', FAILED: 'failed' },
    PLATFORM_MESSAGE: { GAME_READY: 'game_ready', GAMEPLAY_STARTED: 'gameplay_started', GAMEPLAY_STOPPED: 'gameplay_stopped' },
    async initialize() {},
    platform: {
      language: LANG,
      id: 'playgama-real-qa',
      isAudioEnabled: false,
      isPaused: true,
      on,
      off,
      async sendMessage(message) {
        if (message !== 'game_ready') return;
        // The adapter must not report game_ready until a real frame exists.
        signal(nonWhiteCanvas() ? 'frame_ok' : 'frame_white');
        signal(document.documentElement.lang === LANG ? 'lang_ok' : 'lang_bad');

        const phaseKey = 'playgama-realqa-' + LANG + '-phase';
        const phase = sessionStorage.getItem(phaseKey) || 'first';
        if (phase === 'first') {
          sessionStorage.setItem(phaseKey, 'reload');
          signal('first_ready');
          setTimeout(() => location.reload(), 250);
          return;
        }

        sessionStorage.removeItem(phaseKey);
        signal('reload_ready');
        setTimeout(async () => {
          signal(nonWhiteCanvas() ? 'reload_frame_ok' : 'reload_frame_white');
          signal(window.pingusPagePaused?.() ? 'pause_applied' : 'pause_missing');
          await inspectMutedState();
        }, 500);
      }
    },
    storage: {
      async get(key) { return storage.get(String(key)); },
      async set(key, value) { storage.set(String(key), value); }
    },
    advertisement: {
      isInterstitialSupported: true,
      isRewardedSupported: false,
      on,
      off,
      setMinimumDelayBetweenInterstitial() {},
      showInterstitial() {},
      showRewarded() {}
    }
  };
})();'''.replace('__LANG__', repr(lang))
    Path(f'dist/real-qa-bridge-{lang}.js').write_text(js, encoding='utf-8')
PY

node --check dist/real-qa-bridge-en.js
node --check dist/real-qa-bridge-ru.js

browser_bin="$(command -v google-chrome || command -v google-chrome-stable || command -v chromium || command -v chromium-browser)"
: > real-qa-http.txt
python3 -m http.server 4188 --bind 127.0.0.1 --directory dist > real-qa-http.txt 2>&1 &
server_pid=$!
chrome_pid=''
cleanup() {
  if [ -n "$chrome_pid" ]; then kill "$chrome_pid" 2>/dev/null || true; fi
  kill "$server_pid" 2>/dev/null || true
}
trap cleanup EXIT
for _ in $(seq 1 50); do curl -fsS http://127.0.0.1:4188/real-qa-en.html >/dev/null && break || sleep 0.1; done

for lang in en ru; do
  rm -rf ".chrome-realqa-${lang}"
  "$browser_bin" --headless=new --no-sandbox --disable-dev-shm-usage --disable-gpu \
    --autoplay-policy=no-user-gesture-required --user-data-dir="$PWD/.chrome-realqa-${lang}" \
    "http://127.0.0.1:4188/real-qa-${lang}.html?pingus-smoke=1" \
    > "real-qa-${lang}-stdout.txt" 2> "real-qa-${lang}-chrome.txt" &
  chrome_pid=$!
  result=timeout
  for _ in $(seq 1 120); do
    if grep -q "GET /__realqa_${lang}_frame_white__" real-qa-http.txt \
      || grep -q "GET /__realqa_${lang}_reload_frame_white__" real-qa-http.txt \
      || grep -q "GET /__realqa_${lang}_lang_bad__" real-qa-http.txt \
      || grep -q "GET /__realqa_${lang}_audio_bad__" real-qa-http.txt \
      || grep -q "GET /__realqa_${lang}_media_guard_bad__" real-qa-http.txt; then
      result=runtime-error
      break
    fi
    if grep -q "GET /__realqa_${lang}_first_ready__" real-qa-http.txt \
      && grep -q "GET /__realqa_${lang}_reload_ready__" real-qa-http.txt \
      && grep -q "GET /__realqa_${lang}_frame_ok__" real-qa-http.txt \
      && grep -q "GET /__realqa_${lang}_reload_frame_ok__" real-qa-http.txt \
      && grep -q "GET /__realqa_${lang}_lang_ok__" real-qa-http.txt \
      && grep -q "GET /__realqa_${lang}_pause_applied__" real-qa-http.txt \
      && grep -q "GET /__realqa_${lang}_media_guard_ok__" real-qa-http.txt \
      && grep -q "GET /__realqa_${lang}_audio_silent__" real-qa-http.txt; then
      result=success
      break
    fi
    if ! kill -0 "$chrome_pid" 2>/dev/null; then result=browser-exited; break; fi
    sleep 0.5
  done
  test "$result" = success || {
    tail -250 "real-qa-${lang}-chrome.txt"
    tail -220 real-qa-http.txt
    exit 1
  }
  kill "$chrome_pid" 2>/dev/null || true
  wait "$chrome_pid" 2>/dev/null || true
  chrome_pid=''
done

rm -f dist/real-qa-en.html dist/real-qa-ru.html dist/real-qa-bridge-en.js dist/real-qa-bridge-ru.js
rm -f pingus-playgama-multilingual.zip playgama-multilingual-sha256.txt
(cd dist && zip -9 -X -r ../pingus-playgama-multilingual.zip .)
unzip -t pingus-playgama-multilingual.zip
zipinfo -1 pingus-playgama-multilingual.zip | grep -qx 'index.html'
zipinfo -1 pingus-playgama-multilingual.zip | grep -qx 'playgama-bridge-config.json'
! zipinfo -1 pingus-playgama-multilingual.zip | grep -qE 'real-qa|qa-|persistence-smoke'
sha256sum pingus-playgama-multilingual.zip | tee playgama-multilingual-sha256.txt

echo 'Playgama real-tester regression: EN/RU reload while paused+muted stays painted and silent'

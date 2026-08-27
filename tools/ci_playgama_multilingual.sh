#!/usr/bin/env bash
set -euxo pipefail

ROOT="$PWD"

sudo apt-get update
sudo apt-get install -y --no-install-recommends \
  bzip2 ca-certificates curl git libboost-dev python3 python3-pil \
  fonts-dejavu-core xz-utils zip ffmpeg

git clone --depth 1 https://github.com/emscripten-core/emsdk.git .emsdk
./.emsdk/emsdk install 3.1.64
./.emsdk/emsdk activate 3.1.64
source ./.emsdk/emsdk_env.sh
em++ --version

curl -L --fail --retry 3 --retry-all-errors \
  https://deb.debian.org/debian/pool/main/p/pingus/pingus_0.7.6.orig.tar.bz2 \
  -o pingus.tar.bz2
tar -xjf pingus.tar.bz2
mv pingus-0.7.6 pingus-src

(
  cd pingus-src
  bash ../tools/build_playgama_web.sh 2>&1 | tee ../playgama-multilingual-build.log
)

# The exact regression reported by Playgama: English must keep original artwork,
# while Russian is a separate descriptor selected only by the runtime language.
grep -q '../tutorial_layer0.jpg' pingus-src/data/images/worldmaps/tutorial/layer0.sprite
! grep -q '../tutorial_layer0_ru.png' pingus-src/data/images/worldmaps/tutorial/layer0.sprite
grep -q '../tutorial_layer0_ru.png' pingus-src/data/images/worldmaps/tutorial/layer0_ru.sprite
test -s pingus-src/data/images/worldmaps/tutorial_layer0.jpg
test -s pingus-src/data/images/worldmaps/tutorial_layer0_ru.png
grep -q 'dictionary_manager.get_language().get_language() == "ru"' pingus-src/src/engine/display/sprite.cpp
grep -q 'worldmaps/tutorial/layer0_ru' pingus-src/src/engine/display/sprite.cpp
grep -q 'groundpieces/ground/signposts/danger_ru' pingus-src/src/engine/display/sprite.cpp
grep -q 'exits/ice2_ru' pingus-src/src/engine/display/sprite.cpp

python3 playgama/package_playgama.py dist \
  --adapter playgama/playgama-yandex-compat.js \
  --config playgama/playgama-bridge-config.json
python3 playgama/harden_v2_adapter.py dist/playgama-yandex-compat.js

# Current Playgama packaging requirements and known moderation failure modes.
test -s dist/index.html
test -s dist/pingus.js
test -s dist/bootstrap.js
test -s dist/pingus.css
test -s dist/playgama-bridge-config.json
grep -q 'https://bridge.playgama.com/v2/stable/playgama-bridge.js' dist/index.html
! grep -q 'bridge.playgama.com/v1/' dist/index.html
grep -q 'playgama-yandex-compat.js' dist/index.html
node --check dist/playgama-yandex-compat.js
node --check dist/bootstrap.js
python3 - <<'PY'
import json
from pathlib import Path
cfg=json.loads(Path('dist/playgama-bridge-config.json').read_text())
assert cfg['disableLoadingLogo'] is True
assert cfg['showFullLoadingLogo'] is False
assert cfg['advertisement']['minimumDelayBetweenInterstitial'] == 90
assert cfg['advertisement']['initialInterstitialDelay'] == 90
assert cfg['advertisement']['interstitial']['disable'] is False
assert cfg['advertisement']['rewarded']['disable'] is True
assert cfg['advertisement']['banner']['disable'] is True
assert cfg['device']['supportedOrientations'] == ['landscape']
assert cfg['game']['adaptToSafeArea'] is True
PY
invalid_names=$(find dist -type f -printf '%P\n' | LC_ALL=C grep -E '[[:space:]]|[^ -~]' || true)
test -z "$invalid_names"
test "$(du -sb dist | cut -f1)" -lt 300000000
! grep -R -E 'googletagmanager|google-analytics|gtag\(' dist/index.html dist/bootstrap.js dist/playgama-yandex-compat.js

# Build two local Bridge 2.1 QA pages. In addition to language + game_ready,
# sample the rendered world-map region so a future EN/RU texture regression is
# visible to CI rather than only to Playgama's tester.
python3 - <<'PY'
from pathlib import Path
html=Path('dist/index.html').read_text()
remote='https://bridge.playgama.com/v2/stable/playgama-bridge.js'
for lang in ('en','ru'):
    Path(f'dist/qa-{lang}.html').write_text(html.replace(remote, f'playgama-bridge-qa-{lang}.js'))
    js='''(() => {
  const LANG = __LANG__;
  const listeners = new Map();
  const on=(n,cb)=>{const a=listeners.get(n)||[];a.push(cb);listeners.set(n,a);};
  const off=(n,cb)=>listeners.set(n,(listeners.get(n)||[]).filter(x=>x!==cb));
  const storage=new Map();
  const inspectFrame=()=>{
    const canvas=document.getElementById('canvas');
    let ok=false, hash=2166136261>>>0;
    try {
      const ctx=canvas?.getContext('2d');
      const w=Math.min(500,canvas?.width||0);
      const h=Math.min(220,Math.max(0,(canvas?.height||0)-120));
      const data=(w>0&&h>0)?ctx?.getImageData(40,120,w,h).data:null;
      if(data){
        let white=0,sampled=0;
        for(let i=0;i<data.length;i+=64){
          sampled++;
          if(data[i]>245&&data[i+1]>245&&data[i+2]>245&&data[i+3]>245) white++;
          hash=Math.imul((hash^data[i]^data[i+1]^data[i+2]^data[i+3])>>>0,16777619)>>>0;
        }
        ok=sampled>0&&white/sampled<0.95;
      }
    } catch (_) {}
    fetch('/__qa_'+LANG+'_frame_'+(ok?'ok':'bad')+'__').catch(()=>{});
    fetch('/__qa_'+LANG+'_crop_'+hash.toString(16)+'__').catch(()=>{});
  };
  window.bridge={
    version:'2.1.0',
    EVENT_NAME:{PAUSE_STATE_CHANGED:'pause_state_changed',AUDIO_STATE_CHANGED:'audio_state_changed',INTERSTITIAL_STATE_CHANGED:'interstitial_state_changed',REWARDED_STATE_CHANGED:'rewarded_state_changed'},
    INTERSTITIAL_STATE:{OPENED:'opened',CLOSED:'closed',FAILED:'failed'},
    REWARDED_STATE:{OPENED:'opened',REWARDED:'rewarded',CLOSED:'closed',FAILED:'failed'},
    PLATFORM_MESSAGE:{GAME_READY:'game_ready',GAMEPLAY_STARTED:'gameplay_started',GAMEPLAY_STOPPED:'gameplay_stopped'},
    async initialize(){},
    platform:{language:LANG,id:'qa',isAudioEnabled:true,isPaused:false,on,off,async sendMessage(m){if(m==='game_ready'){fetch('/__qa_'+LANG+'_ready__').catch(()=>{});fetch('/__qa_'+LANG+'_lang_'+document.documentElement.lang+'__').catch(()=>{});setTimeout(inspectFrame,250);}}},
    storage:{async get(k){return storage.get(String(k));},async set(k,v){storage.set(String(k),v);}},
    advertisement:{isInterstitialSupported:true,isRewardedSupported:false,on,off,setMinimumDelayBetweenInterstitial(){},showInterstitial(){},showRewarded(){}}
  };
})();'''.replace('__LANG__', repr(lang))
    Path(f'dist/playgama-bridge-qa-{lang}.js').write_text(js)
PY
node --check dist/playgama-bridge-qa-en.js
node --check dist/playgama-bridge-qa-ru.js

browser_bin="$(command -v google-chrome || command -v google-chrome-stable || command -v chromium)"
: > locale-http.txt
python3 -m http.server 4180 --bind 127.0.0.1 --directory dist > locale-http.txt 2>&1 &
server_pid=$!
chrome_pid=''
cleanup(){ if [ -n "$chrome_pid" ]; then kill "$chrome_pid" 2>/dev/null || true; fi; kill "$server_pid" 2>/dev/null || true; }
trap cleanup EXIT
for _ in $(seq 1 50); do curl -fsS http://127.0.0.1:4180/qa-en.html >/dev/null && break || sleep 0.1; done

for lang in en ru; do
  rm -rf ".chrome-qa-${lang}"
  "$browser_bin" --headless=new --no-sandbox --disable-dev-shm-usage --disable-gpu \
    --autoplay-policy=no-user-gesture-required --user-data-dir="$PWD/.chrome-qa-${lang}" \
    "http://127.0.0.1:4180/qa-${lang}.html?pingus-smoke=1" \
    > "qa-${lang}-stdout.txt" 2> "qa-${lang}-chrome.txt" &
  chrome_pid=$!
  result=timeout
  for _ in $(seq 1 100); do
    if grep -q 'GET /__pingus_error__' locale-http.txt; then result=runtime-error; break; fi
    if grep -q "GET /__qa_${lang}_ready__" locale-http.txt \
      && grep -q "GET /__qa_${lang}_lang_${lang}__" locale-http.txt \
      && grep -q "GET /__qa_${lang}_frame_ok__" locale-http.txt; then
      result=success
      break
    fi
    if ! kill -0 "$chrome_pid" 2>/dev/null; then result=browser-exited; break; fi
    sleep 0.5
  done
  test "$result" = success || { tail -200 "qa-${lang}-chrome.txt"; tail -150 locale-http.txt; exit 1; }
  kill "$chrome_pid" 2>/dev/null || true
  wait "$chrome_pid" 2>/dev/null || true
  chrome_pid=''
done

en_hash=$(grep -oE '/__qa_en_crop_[0-9a-f]+__' locale-http.txt | tail -1 | sed -E 's#.*_crop_([0-9a-f]+)__#\1#')
ru_hash=$(grep -oE '/__qa_ru_crop_[0-9a-f]+__' locale-http.txt | tail -1 | sed -E 's#.*_crop_([0-9a-f]+)__#\1#')
test -n "$en_hash"
test -n "$ru_hash"
test "$en_hash" != "$ru_hash"
echo "Rendered language crop hashes: en=$en_hash ru=$ru_hash"

# Re-test Pingus' own persistent profile after the new multilingual rebuild.
python3 tools/make_persistence_smoke.py dist/qa-en.html dist/persistence-smoke.html
rm -rf .chrome-persistence
: > persistence-http.txt
python3 -m http.server 4181 --bind 127.0.0.1 --directory dist > persistence-http.txt 2>&1 &
persist_server=$!
for _ in $(seq 1 50); do curl -fsS http://127.0.0.1:4181/persistence-smoke.html >/dev/null && break || sleep 0.1; done
"$browser_bin" --headless=new --no-sandbox --disable-dev-shm-usage --disable-gpu \
  --autoplay-policy=no-user-gesture-required --user-data-dir="$PWD/.chrome-persistence" \
  'http://127.0.0.1:4181/persistence-smoke.html?pingus-persistence-smoke=1' \
  > persistence-stdout.txt 2> persistence-chrome.txt &
chrome_pid=$!
result=timeout
for _ in $(seq 1 240); do
  if grep -q 'GET /__pingus_persist_success__' persistence-http.txt; then result=success; break; fi
  if grep -q 'GET /__pingus_persist_error__' persistence-http.txt; then result=runtime-error; break; fi
  if ! kill -0 "$chrome_pid" 2>/dev/null; then result=browser-exited; break; fi
  sleep 0.5
done
test "$result" = success || { tail -200 persistence-chrome.txt; tail -150 persistence-http.txt; exit 1; }
kill "$chrome_pid" 2>/dev/null || true
wait "$chrome_pid" 2>/dev/null || true
chrome_pid=''
kill "$persist_server" 2>/dev/null || true

rm -f dist/qa-en.html dist/qa-ru.html dist/playgama-bridge-qa-en.js dist/playgama-bridge-qa-ru.js dist/persistence-smoke.html
(cd dist && zip -9 -X -r ../pingus-playgama-multilingual.zip .)
unzip -t pingus-playgama-multilingual.zip
zipinfo -1 pingus-playgama-multilingual.zip | grep -qx 'index.html'
zipinfo -1 pingus-playgama-multilingual.zip | grep -qx 'playgama-bridge-config.json'
! zipinfo -1 pingus-playgama-multilingual.zip | grep -qE 'qa-|persistence-smoke'
sha256sum pingus-playgama-multilingual.zip | tee playgama-multilingual-sha256.txt
ls -lh pingus-playgama-multilingual.zip

#!/usr/bin/env bash
set -euo pipefail

mkdir -p ../dist
rm -rf ../dist/* external/boost
cp -a /usr/include/boost external/boost
python3 ../tools/patch_pingus.py
python3 ../tools/patch_browser_runtime.py
python3 ../tools/patch_focus_pause.py
python3 ../tools/patch_yandex_ads.py
python3 ../tools/patch_yandex_ad_resume.py
python3 ../tools/patch_yandex_gameplay.py
python3 ../tools/patch_yandex_final_compliance.py
python3 ../tools/patch_yandex_content.py
python3 ../tools/patch_yandex_locale.py
python3 ../tools/patch_web_localization.py
python3 ../tools/patch_yandex_content_translation.py
python3 ../tools/patch_web_po_dedupe.py
python3 ../tools/patch_web_hide_author.py
python3 ../tools/audit_web_localization_sources.py
python3 ../tools/audit_yandex_content.py
python3 ../tools/patch_web_performance.py
python3 ../tools/patch_web_many_pingus.py
python3 ../tools/patch_web_smallmap_fast.py
python3 ../tools/patch_web_worldmap_ux.py

# Web uses a fixed 800x600 framebuffer. Freeze every rear SurfaceBackground to
# one viewport-sized frame: no parallax, no autonomous scrolling and no tiling.
python3 ../tools/patch_web_background_seams.py
grep -q 'one fixed 800x600 frame' ../tools/patch_web_background_seams.py
grep -q 'Vector2i(-offset.x, -offset.y)' src/pingus/worldobjs/surface_background.cpp

if ! python3 -c 'from PIL import Image, ImageDraw, ImageFont' >/dev/null 2>&1 || \
   [ ! -f /usr/share/fonts/truetype/dejavu/DejaVuSans.ttf ]; then
  echo 'Installing Web Cyrillic font generation dependencies'
  sudo apt-get update
  sudo apt-get install -y --no-install-recommends fonts-dejavu-core python3-pil
fi
python3 ../tools/patch_yandex_exit_localization.py
python3 ../tools/patch_force_tutorial_worldmap_ru.py
test -s data/images/exits/ice2_ru.png
test -s data/images/exits/sortie_anim_ru.png
test -s data/images/traps/laser_exit_ru.png
test -s data/images/worldmaps/tutorial_layer0_ru.png
grep -q '../tutorial_layer0_ru.png' data/images/worldmaps/tutorial/layer0.sprite
! grep -q '../tutorial_layer0.jpg' data/images/worldmaps/tutorial/layer0.sprite
grep -q 'yandex_localized_sprite_name' src/engine/display/sprite.cpp
python3 ../tools/patch_web_visual_localization.py
test -s data/images/groundpieces/ground/signposts/danger_ru.png
test -s data/images/groundpieces/ground/penguinworld/penguinworld_ru.png
test -s data/images/core/misc/404_ru.png
grep -q 'dictionary_manager.get_language().get_language() == "ru"' src/engine/display/sprite.cpp
python3 ../tools/patch_web_fonts.py

python3 ../tools/patch_touch_input.py
python3 ../tools/patch_web_menu.py
python3 ../tools/patch_web_options.py
python3 ../tools/patch_web_audio_channels.py
python3 ../tools/patch_sdl_framebuffer.py
python3 ../tools/patch_groundmap_erase.py
python3 ../tools/patch_web_backdrop.py
python3 ../tools/patch_yandex_cloud_saves.py

mapfile -d '' TRACKER_MUSIC < <(find data/music -maxdepth 1 -type f \
  \( -iname '*.it' -o -iname '*.xm' -o -iname '*.s3m' -o -iname '*.mod' \) -print0)
if (( ${#TRACKER_MUSIC[@]} > 0 )); then
  if ! command -v ffmpeg >/dev/null 2>&1; then
    echo 'Installing ffmpeg for Pingus tracker-music conversion'
    sudo apt-get update
    sudo apt-get install -y --no-install-recommends ffmpeg
  fi
  printf 'Converting %s original tracker music files to browser-decodable OGG\n' "${#TRACKER_MUSIC[@]}"
  for track in "${TRACKER_MUSIC[@]}"; do
    output="${track%.*}.ogg"
    printf '  %s -> %s\n' "$track" "$output"
    ffmpeg -hide_banner -nostdin -loglevel error -y -i "$track" \
      -map_metadata -1 -vn -c:a libvorbis -q:a 4 "$output"
    test -s "$output"
  done
  rm -f "${TRACKER_MUSIC[@]}"
fi

mapfile -t SOURCES < <(find external/tinygettext/tinygettext src -type f -name '*.cpp' \
  ! -path 'src/editor/*' ! -path '*/opengl/*' ! -path '*/evdev/*' \
  ! -path '*/xinput/*' ! -path '*/wiimote/*' -print | sort)
(( ${#SOURCES[@]} >= 200 )) || { echo "Unexpectedly small source set" >&2; exit 1; }
printf 'Compiling %s original C++ source files (desktop editor omitted)\n' "${#SOURCES[@]}"

em++ "${SOURCES[@]}" \
  -I. -Isrc -Iexternal -Iexternal/tinygettext \
  -std=c++11 -O2 -fexceptions -Wno-invalid-source-encoding \
  -DVERSION='"0.7.6-web"' -DHAVE_ICONV_CONST=1 -DICONV_CONST= \
  -sUSE_SDL=1 -sUSE_SDL_IMAGE=1 -sUSE_SDL_MIXER=1 \
  -sSTB_IMAGE=1 -sUSE_LIBPNG=1 -sUSE_OGG=1 -sUSE_VORBIS=1 \
  -sDISABLE_EXCEPTION_CATCHING=0 -sFORCE_FILESYSTEM=1 \
  -sASYNCIFY=1 -sASYNCIFY_STACK_SIZE=65536 \
  -sINITIAL_MEMORY=67108864 -sALLOW_MEMORY_GROWTH=1 -sMAXIMUM_MEMORY=1073741824 \
  -sASSERTIONS=0 -sERROR_ON_UNDEFINED_SYMBOLS=1 -sEXIT_RUNTIME=0 -sENVIRONMENT=web \
  -sSINGLE_FILE=1 -lidbfs.js --embed-file data@/data \
  -o ../dist/pingus.js

python3 - <<'PY'
from pathlib import Path
shell_path = Path('../web/shell.html')
out_path = Path('../dist/index.html')
shell = shell_path.read_text(encoding='utf-8')
marker = '{{{ SCRIPT }}}'
if shell.count(marker) != 1:
    raise SystemExit('shell.html SCRIPT marker missing or duplicated')
shell = shell.replace('<title>Pingus</title>', '<title>Pingus</title>\n  <link rel="icon" href="data:,">', 1)
shell = shell.replace('      window.Module = {\n        canvas,', '      window.Module = {\n        canvas,\n        noAudioDecoding: true,', 1)
prerun = """        preRun: [() => {\n          try { FS.mkdir('/home'); } catch (_) {}"""
prerun_guard = """        preRun: [() => {\n          // Guard legacy Pingus saves against Emscripten chmod(..., 0).\n          if (!FS.__pingusChmodPatched) {\n            const nativeChmod = FS.chmod.bind(FS);\n            FS.chmod = (path, mode) => {\n              const name = String(path || '');\n              if (name.startsWith('/home/web_user/') && (mode & 0o777) === 0) mode = 0o600;\n              return nativeChmod(path, mode);\n            };\n            FS.__pingusChmodPatched = true;\n          }\n          try { FS.mkdir('/home'); } catch (_) {}"""
if prerun not in shell:
    raise SystemExit('shell preRun anchor missing')
shell = shell.replace(prerun, prerun_guard, 1)
shell = shell.replace(marker, '<script src="pingus.js"></script>')
out_path.write_text(shell, encoding='utf-8')
PY

# Externalize generated bootstrap/style and remove inline event handlers.
python3 ../tools/postprocess_csp.py

# Ship GPL corresponding source before the platform-specific runtime postprocess;
# the bundle already includes the complete tools/web directories, including the
# Playgama adapter and Bridge config used below.
python3 ../tools/package_gpl_source.py

test -s ../dist/index.html
test -s ../dist/bootstrap.js
test -s ../dist/pingus.css
test -s ../dist/pingus.js
test -s ../dist/PINGUS-CORRESPONDING-SOURCE.tar.gz
grep -q 'GameplayAPI' ../dist/bootstrap.js
grep -q 'pingusSetGameplayActive' ../dist/pingus.js
grep -q 'PINGUS_CLOUD_KEY' ../dist/bootstrap.js
grep -q 'player.getData' ../dist/bootstrap.js
grep -q 'player.setData' ../dist/bootstrap.js
grep -q 'pingus-static-shell-backdrop' ../dist/pingus.css
if grep -Eq 'id="backdrop"|drawBackdrop|backdropContext|backdropLoop' ../dist/index.html ../dist/bootstrap.js ../dist/pingus.css; then
  echo 'Retired live-copy backdrop is still present' >&2
  exit 1
fi
grep -q 'pingusShowInterstitialAfterResultAction' ../dist/bootstrap.js
grep -q 'INTERSTITIAL_MIN_INTERVAL_MS = 90000' ../dist/bootstrap.js
if grep -q 'pingusShowInterstitialAfterLevel' ../dist/bootstrap.js; then
  echo 'Legacy automatic post-level interstitial hook is still present' >&2
  exit 1
fi
node --check ../dist/bootstrap.js
if find ../dist -maxdepth 1 -type f \( -name '*.wasm' -o -name '*.data' \) | grep -q .; then
  echo 'Unexpected external wasm/data payload in dist' >&2
  exit 1
fi

# This branch is a Playgama distribution. Transform only the platform-facing
# browser layer after the proven game/WebAssembly build has passed its base
# assertions. The native Pingus/gameplay fixes remain identical to Yandex.
if [ -f ../web/playgama-bridge-config.json ]; then
  python3 ../tools/postprocess_playgama.py
  test -s ../dist/playgama-bridge-config.json
  grep -q 'bridge.playgama.com/v1/stable/playgama-bridge.js' ../dist/index.html
  grep -q 'bridge.initialize()' ../dist/bootstrap.js
  grep -q "sendMessage?.('game_ready')" ../dist/bootstrap.js
  grep -q 'pg.storage.get(PINGUS_CLOUD_KEY)' ../dist/bootstrap.js
  grep -q "showInterstitial('level_complete')" ../dist/bootstrap.js
  grep -q 'INTERSTITIAL_MIN_INTERVAL_MS = 60000' ../dist/bootstrap.js
  if grep -Eq 'src="/sdk.js"|YaGames|showFullscreenAdv|window\.yandexSDKPromise' ../dist/index.html ../dist/bootstrap.js; then
    echo 'Yandex SDK/runtime marker leaked into Playgama dist' >&2
    exit 1
  fi
  node --check ../dist/bootstrap.js
  printf 'Playgama distribution validation passed\n'
fi

printf 'Self-contained browser runtime created:\n'
find ../dist -maxdepth 1 -type f -printf '  %f %s bytes\n' | sort

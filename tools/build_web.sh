#!/usr/bin/env bash
set -euo pipefail

mkdir -p ../dist
rm -rf ../dist/* external/boost
cp -a /usr/include/boost external/boost
python3 ../tools/patch_pingus.py

mapfile -t SOURCES < <(find external/tinygettext/tinygettext src -type f -name '*.cpp' \
  ! -path 'src/editor/*' ! -path '*/opengl/*' ! -path '*/evdev/*' \
  ! -path '*/xinput/*' ! -path '*/wiimote/*' -print | sort)
(( ${#SOURCES[@]} >= 200 )) || { echo "Unexpectedly small source set" >&2; exit 1; }
printf 'Compiling %s original C++ source files (desktop editor omitted)\n' "${#SOURCES[@]}"

# Build a self-contained runtime JS. The old preload-file build generated
# index.data and index.wasm which had to be fetched separately at runtime.
# The WebAssembly binary and virtual filesystem payload are embedded into
# pingus.js so the browser never has to fetch those secondary resources.
# STB_IMAGE is required because SDL1 IMG_Load otherwise expects browser-side
# preloaded images; Pingus loads its PNG assets synchronously from the VFS.
em++ "${SOURCES[@]}" \
  -I. -Isrc -Iexternal -Iexternal/tinygettext \
  -std=c++11 -O1 -fexceptions -Wno-invalid-source-encoding \
  -DVERSION='"0.7.6-web"' -DHAVE_ICONV_CONST=1 -DICONV_CONST= \
  -sUSE_SDL=1 -sUSE_SDL_IMAGE=1 -sUSE_SDL_MIXER=1 \
  -sSTB_IMAGE=1 -sUSE_LIBPNG=1 -sUSE_OGG=1 -sUSE_VORBIS=1 \
  -sDISABLE_EXCEPTION_CATCHING=0 -sFORCE_FILESYSTEM=1 \
  -sASYNCIFY=1 -sASYNCIFY_STACK_SIZE=65536 \
  -sINITIAL_MEMORY=67108864 -sALLOW_MEMORY_GROWTH=1 -sMAXIMUM_MEMORY=1073741824 \
  -sASSERTIONS=1 -sERROR_ON_UNDEFINED_SYMBOLS=1 -sEXIT_RUNTIME=0 -sENVIRONMENT=web \
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
shell = shell.replace(marker, '<script src="pingus.js"></script>')
out_path.write_text(shell, encoding='utf-8')
PY

# Compatibility placeholders for older CI attempts. They are deliberately not
# referenced by index.html and are removed from the final user-facing ZIP.
printf '// unused compatibility placeholder; runtime is pingus.js\n' > ../dist/index.js
printf 'unused\n' > ../dist/index.wasm
printf 'unused\n' > ../dist/index.data

test -s ../dist/index.html
test -s ../dist/pingus.js
printf 'Self-contained browser runtime created:\n'
find ../dist -maxdepth 1 -type f -printf '  %f %s bytes\n' | sort

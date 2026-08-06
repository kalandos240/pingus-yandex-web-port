#!/usr/bin/env bash
set -euo pipefail

mkdir -p ../dist

mapfile -t SOURCES < <(
  find external/tinygettext/tinygettext src -type f -name '*.cpp' \
    ! -path '*/opengl/*' \
    ! -path '*/evdev/*' \
    ! -path '*/xinput/*' \
    ! -path '*/wiimote/*' \
    -print | sort
)

printf 'Compiling %s original C++ source files\n' "${#SOURCES[@]}"

em++ "${SOURCES[@]}" \
  -I. -Isrc -Iexternal/tinygettext \
  -std=c++11 -O1 \
  -fexceptions \
  -DVERSION='"0.7.6-web"' \
  -DHAVE_SDL=1 \
  -sUSE_SDL=1 \
  -sUSE_SDL_IMAGE=1 \
  -sUSE_SDL_MIXER=1 \
  -sUSE_LIBPNG=1 \
  -sDISABLE_EXCEPTION_CATCHING=0 \
  -sALLOW_MEMORY_GROWTH=1 \
  -sASSERTIONS=1 \
  -sEXIT_RUNTIME=0 \
  -sFORCE_FILESYSTEM=1 \
  --preload-file data@/data \
  -o ../dist/index.html

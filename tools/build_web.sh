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
  -DVERSION='"0.7.6-web"' \
  -DHAVE_ICONV_CONST=1 -DICONV_CONST= \
  -sUSE_SDL=1 \
  -sUSE_SDL_IMAGE=1 \
  -sUSE_SDL_MIXER=1 \
  -sUSE_LIBPNG=1 \
  -sALLOW_MEMORY_GROWTH=1 \
  -sASSERTIONS=1 \
  -sEXIT_RUNTIME=0 \
  --preload-file data@/data \
  -o ../dist/index.html

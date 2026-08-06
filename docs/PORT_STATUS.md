# Pingus Web Port Status

This branch contains the active Emscripten/WebAssembly port of the original Pingus 0.7.6 source for Yandex Games.

## Current build target

- Original Pingus gameplay and bundled data
- SDL 1 compatibility through Emscripten
- Browser frame loop through Asyncify
- IDBFS save persistence
- Yandex Games SDK loading and `LoadingAPI.ready()` after the first rendered frame
- Responsive canvas without page scrolling
- Final package: `pingus-yandex-web.zip`

## Next CI result

The workflow must either produce the complete browser package (`index.html`, JavaScript, WebAssembly and data files) or publish the next compiler/linker error as an artifact. A release is not considered ready until the generated ZIP is tested in a browser.

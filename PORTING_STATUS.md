# Pingus WebAssembly port status

This repository builds the original GPL-licensed Pingus 0.7.6 source with Emscripten.

Current browser-port changes:

- removes the desktop-only level editor from the web target;
- adapts the SDL surface colour-key and alpha APIs used by the 0.7.6 renderer;
- enables C++ exceptions required by the original game;
- enables Asyncify so the original SDL loop can yield to the browser;
- preloads the original `data/` directory into the virtual filesystem;
- packages a successful build as `pingus-yandex-web.zip`.

The final release is not considered ready until the original menu, levels, actions, sound, browser persistence, Yandex Games lifecycle integration, and unpacked size have all been verified.

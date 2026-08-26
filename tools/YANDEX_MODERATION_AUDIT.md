# Yandex Games moderation audit

This file is the release checklist for the Web/Yandex build. A release ZIP should not be submitted to moderation unless the automated build and the checks below pass.

## 8.2.3 — Russian player-facing graphics

Russian locale must use Russian artwork for every original player-facing exit image that contains baked English `EXIT`/`Exit` text.

Expected localized exit resources (16):

- `exits/crystal`
- `exits/desert`
- `exits/desert_tut`
- `exits/easter`
- `exits/forest`
- `exits/halloween`
- `exits/ice2`
- `exits/industrial`
- `exits/mud`
- `exits/ordina`
- `exits/pwexit`
- `exits/sortie`
- `exits/sortie_anim`
- `exits/stone`
- `exits/sweetexit`
- `exits/xmas`

Additional localized baked-text resources:

- `traps/laser_exit` — `EXIT` becomes `ВЫХОД`.
- `worldmaps/tutorial/layer0` — `Tutorial Island` becomes `Учебный остров`.

Text-free exits intentionally remain unchanged:

- `exits/ice`
- `exits/space`

Implementation requirements:

- English source artwork must remain available for English locale.
- Russian artwork must be selected only when `System::get_language() == "ru"`.
- Level `.pingus` descriptors must not be rewritten for localization.
- Exit collision masks and world-object logic must continue using the original resource descriptors.
- The localization build patch must fail when an exit resource referenced by any shipped source level is not classified.

## 4.4 — fullscreen interstitial advertising

- No fullscreen ad may open automatically when gameplay or the result screen starts.
- A fullscreen ad request is allowed only after an explicit result-screen action by the player (continue, retry, or leave).
- `INTERSTITIAL_MIN_INTERVAL_MS` must be exactly `90000` (90 seconds / 1 minute 30 seconds).
- The first eligible interstitial is also delayed by at least 90 seconds from page startup.
- Passing the 90-second threshold alone must never trigger an ad during gameplay; the request waits for the next eligible player action.
- The legacy automatic `pingusShowInterstitialAfterLevel` hook must not exist in the release build.

## Release gate

Before handing a ZIP to Yandex moderation, confirm all of the following:

1. WebAssembly compilation succeeds from pristine Pingus 0.7.6 source plus repository patches.
2. Localized assets are generated successfully and the complete exit-resource audit passes.
3. Final `bootstrap.js` contains `pingusShowInterstitialAfterResultAction` and `INTERSTITIAL_MIN_INTERVAL_MS = 90000`.
4. Final `bootstrap.js` does not contain `pingusShowInterstitialAfterLevel`.
5. Browser startup smoke test succeeds.
6. Persistent-save smoke test succeeds.
7. The Yandex ZIP artifact passes `unzip -t` and contains `index.html`, `pingus.js`, license files and corresponding source bundle.

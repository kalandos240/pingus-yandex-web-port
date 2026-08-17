#!/usr/bin/env python3
"""Convert a pinned, already-tested Pingus browser build into a Playgama package."""
from pathlib import Path
import argparse
import re
import shutil

BRIDGE_URL = "https://bridge.playgama.com/v2/stable/playgama-bridge.js"
BRIDGE = f'<script src="{BRIDGE_URL}"></script>'
ADAPTER = '<script src="playgama-yandex-compat.js"></script>'
VIEWPORT_MARKER = 'Playgama full-viewport background fix v3'
VIEWPORT_CSS = r'''

/* Playgama full-viewport background fix v3
   Presentation only. The tested Pingus runtime and native 4:3 canvas are never
   modified, stretched or cropped. Only the otherwise-unused viewport area is
   painted with a full-bleed icy scene so square/wide/tall containers have no
   dark letterbox bars. */
html,
body,
#game-shell {
  background-color: #7fc1dc !important;
  background-image:
    radial-gradient(ellipse at 12% 108%, rgba(249,253,255,.99) 0 18%, rgba(214,238,248,.92) 19% 29%, transparent 45%),
    radial-gradient(ellipse at 88% 105%, rgba(246,252,255,.98) 0 16%, rgba(199,230,243,.86) 17% 29%, transparent 46%),
    radial-gradient(ellipse at 50% -18%, rgba(248,253,255,.98) 0 14%, rgba(204,237,248,.84) 27%, transparent 58%),
    linear-gradient(180deg, #a6e0f2 0%, #78c1dd 35%, #4c91b1 67%, #dceff7 100%) !important;
  background-repeat: no-repeat !important;
  background-size: cover !important;
  background-position: center !important;
}

#game-shell {
  isolation: isolate;
}

/* The old mirrored backdrop could resemble letterbox bars to the Playgama QA
   scale test. Disable only that decorative layer; gameplay remains untouched. */
#backdrop,
#backdrop-overlay {
  display: none !important;
}

#canvas {
  position: relative;
  z-index: 1;
}

#loading {
  z-index: 2;
}
'''

NOTICE = f"""Playgama integration
====================

Active SDK: Playgama Bridge JS Core v2 stable
{BRIDGE_URL}

The package keeps the already-tested Pingus runtime byte-for-byte unchanged.
Only index.html SDK wiring, the Playgama compatibility adapter/config, and CSS
presentation are added. Rewarded ads are disabled because Pingus has no rewarded
mechanic. Interstitial ads and Playgama storage remain enabled.

Bridge configuration: playgama-bridge-config.json
Viewport: native 4:3 gameplay stays fully visible and centered; unused viewport
space is painted by CSS so square/wide/tall Playgama containers have no bars.
"""


def patch_html(html: str) -> str:
    html = re.sub(
        r'<script\s+src=["\']https://bridge\.playgama\.com/v1/(?:stable|latest)/playgama-bridge\.js["\']\s*></script>',
        BRIDGE,
        html,
        flags=re.I,
    )
    if BRIDGE_URL in html and 'playgama-yandex-compat.js' in html:
        return html
    direct_sdk = re.compile(r'<script\s+src=(?:["\']?/sdk\.js["\']?|/sdk\.js)\s*></script>', re.I)
    if direct_sdk.search(html):
        return direct_sdk.sub(BRIDGE + ADAPTER, html, count=1)
    yandex_bootstrap = '<script src="yandex-bootstrap.js"></script>'
    if yandex_bootstrap in html:
        return html.replace(yandex_bootstrap, BRIDGE + ADAPTER + yandex_bootstrap, 1)
    gamedata = '<script src="gamedata.js" charset="utf-8"></script>'
    if gamedata in html:
        return html.replace(gamedata, BRIDGE + '\n  ' + ADAPTER + '\n  ' + gamedata, 1)
    raise SystemExit('Could not find a supported SDK/runtime insertion point in index.html')


def patch_pingus_viewport(dist: Path) -> None:
    css_path = dist / 'pingus.css'
    if not css_path.is_file():
        raise SystemExit('pingus.css is missing from the Playgama package')

    css = css_path.read_text(encoding='utf-8')
    css = re.sub(
        r'\n/\* Playgama full-viewport background fix(?: v\d+)?[\s\S]*\Z',
        '',
        css,
        count=1,
    )
    css += VIEWPORT_CSS
    css_path.write_text(css, encoding='utf-8')


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('dist', type=Path)
    ap.add_argument('--adapter', type=Path, required=True)
    ap.add_argument('--config', type=Path, required=True)
    args = ap.parse_args()

    dist = args.dist.resolve()
    index = dist / 'index.html'
    if not index.is_file():
        raise SystemExit('index.html must be in package root')

    html = patch_html(index.read_text(encoding='utf-8'))
    if re.search(r'<script\s+src=(?:["\']?/sdk\.js["\']?|/sdk\.js)', html, re.I):
        raise SystemExit('Direct /sdk.js reference remains in Playgama index.html')
    if 'bridge.playgama.com/v1/' in html:
        raise SystemExit('Legacy Playgama Bridge v1 reference remains in Playgama index.html')
    if BRIDGE not in html or ADAPTER not in html:
        raise SystemExit('Playgama Bridge v2 bootstrap was not installed')
    index.write_text(html, encoding='utf-8')

    patch_pingus_viewport(dist)
    shutil.copy2(args.adapter, dist / 'playgama-yandex-compat.js')
    shutil.copy2(args.config, dist / 'playgama-bridge-config.json')
    (dist / 'PLAYGAMA-INTEGRATION.txt').write_text(NOTICE, encoding='utf-8')

    bad = []
    total = 0
    for path in dist.rglob('*'):
        if not path.is_file():
            continue
        rel = path.relative_to(dist).as_posix()
        total += path.stat().st_size
        if ' ' in rel or any(ord(ch) > 127 for ch in rel):
            bad.append(rel)
    if bad:
        raise SystemExit(f'Invalid Playgama archive paths: {bad}')
    if total >= 300_000_000:
        raise SystemExit(f'Playgama package exceeds 300 MB unpacked: {total}')

    print(f'Playgama Bridge v2 package prepared: {dist}')
    print(f'Unpacked bytes: {total}')


if __name__ == '__main__':
    main()

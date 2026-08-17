#!/usr/bin/env python3
"""Convert an already-built browser/Yandex dist directory into a Playgama package."""
from pathlib import Path
import argparse
import re
import shutil

BRIDGE_URL = "https://bridge.playgama.com/v2/stable/playgama-bridge.js"
BRIDGE = f'<script src="{BRIDGE_URL}"></script>'
ADAPTER = '<script src="playgama-yandex-compat.js"></script>'
VIEWPORT_MARKER = 'Playgama full-viewport background fix v2'
VIEWPORT_CSS = r'''

/* Playgama full-viewport background fix v2
   IMPORTANT: this is presentation-only. Pingus keeps its original runtime and
   native 4:3 canvas behavior. The surrounding viewport is painted so square,
   wide and tall QA containers never expose dark letterbox bars. */
html,
body,
#game-shell {
  background-color: #6aa8c5 !important;
  background-image:
    radial-gradient(ellipse at 50% -10%, rgba(242,252,255,.98) 0%, rgba(192,231,246,.78) 24%, rgba(106,168,197,.18) 55%, transparent 72%),
    radial-gradient(ellipse at 18% 94%, rgba(239,249,253,.96) 0%, rgba(201,232,243,.70) 24%, transparent 52%),
    radial-gradient(ellipse at 82% 102%, rgba(226,244,250,.92) 0%, rgba(179,218,234,.62) 25%, transparent 53%),
    linear-gradient(180deg, #90d2e9 0%, #67b0cf 36%, #397797 68%, #dceff6 100%) !important;
  background-repeat: no-repeat !important;
  background-size: cover !important;
  background-position: center !important;
}

#game-shell {
  isolation: isolate;
}

/* Once Pingus has rendered, its existing backdrop canvas mirrors the game.
   Brighten that layer so the 4:3 extensions look like part of the scene rather
   than opaque bars. No bootstrap/runtime JavaScript is modified. */
#backdrop {
  z-index: 0;
  opacity: .90 !important;
  filter: blur(24px) saturate(1.05) brightness(1.03) !important;
  transform: scale(1.16) !important;
}

#backdrop-overlay {
  z-index: 0;
  background:
    radial-gradient(circle at center, rgba(16,37,56,0) 0%, rgba(16,37,56,.03) 68%, rgba(8,20,30,.12) 100%),
    linear-gradient(180deg, rgba(255,255,255,.04), rgba(10,28,40,.04)) !important;
}

#canvas { z-index: 1; }
#loading { z-index: 2; }
'''

NOTICE = f"""Playgama integration
====================

Active SDK: Playgama Bridge JS Core v2 stable
{BRIDGE_URL}

The package keeps the port's already-tested game-side Yandex-style calls behind
playgama-yandex-compat.js. That facade maps language, lifecycle, ads, pause/resume
and Player data to Playgama Bridge v2. The Playgama package does not load /sdk.js.

Bridge configuration: playgama-bridge-config.json
Viewport: Pingus runtime is left byte-for-byte unchanged. Only CSS presentation
fills unused square/wide/tall viewport space with an icy responsive backdrop.
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
    # A package is always rebuilt from the clean Yandex release. This removal is
    # defensive for local re-runs of the converter on an already patched folder.
    css = re.sub(
        r'\n/\* Playgama full-viewport background fix(?: v2)?[\s\S]*\Z',
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

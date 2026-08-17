#!/usr/bin/env python3
"""Convert an already-built browser/Yandex dist directory into a Playgama package."""
from pathlib import Path
import argparse
import re
import shutil

BRIDGE_URL = "https://bridge.playgama.com/v2/stable/playgama-bridge.js"
BRIDGE = f'<script src="{BRIDGE_URL}"></script>'
ADAPTER = '<script src="playgama-yandex-compat.js"></script>'
VIEWPORT_MARKER = 'Playgama full-viewport background fix'
VIEWPORT_CSS = r'''

/* Playgama full-viewport background fix
   Keep Pingus' native 4:3 canvas completely visible and centered. The unused
   part of square/wide/tall viewports is a scenic full-bleed background rather
   than letterbox bars, which is required by Playgama scale certification. */
#game-shell {
  isolation: isolate;
  background:
    radial-gradient(ellipse at 50% -12%, rgba(255,255,255,.86) 0%, rgba(205,238,250,.54) 27%, transparent 54%),
    radial-gradient(ellipse at 50% 112%, rgba(244,251,254,.98) 0%, rgba(179,220,236,.56) 35%, transparent 60%),
    linear-gradient(180deg, #8bd0ea 0%, #58a0c1 38%, #2d6789 65%, #d8edf5 100%) !important;
}
#backdrop {
  z-index: 0;
  opacity: .96 !important;
  filter: blur(18px) saturate(1.08) brightness(.94) !important;
  transform: scale(1.14) !important;
}
#backdrop-overlay {
  z-index: 0;
  background:
    radial-gradient(circle at center, rgba(16,37,56,0) 0%, rgba(16,37,56,.03) 64%, rgba(7,15,24,.15) 100%),
    linear-gradient(180deg, rgba(255,255,255,.03), rgba(8,18,29,.06)) !important;
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
Viewport: native 4:3 gameplay stays fully visible; surrounding viewport is filled
with a scenic responsive backdrop for square/wide/tall Playgama containers.
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
    bootstrap_path = dist / 'bootstrap.js'
    if not css_path.is_file() or not bootstrap_path.is_file():
        raise SystemExit('Pingus viewport files are missing from the Playgama package')

    css = css_path.read_text(encoding='utf-8')
    if VIEWPORT_MARKER not in css:
        css += VIEWPORT_CSS
        css_path.write_text(css, encoding='utf-8')

    bootstrap = bootstrap_path.read_text(encoding='utf-8')
    old_guard = 'if (!backdropContext || !gameReadySent || !canvas.width || !canvas.height) return;'
    new_guard = 'if (!backdropContext || !canvas.width || !canvas.height) return;'
    if old_guard in bootstrap:
        bootstrap = bootstrap.replace(old_guard, new_guard, 1)
    elif new_guard not in bootstrap:
        raise SystemExit('Could not patch Pingus backdrop readiness guard')

    ready_old = 'fitCanvas();\n        loading.hidden = true;'
    ready_new = 'fitCanvas();\n        drawBackdrop();\n        loading.hidden = true;'
    if ready_old in bootstrap:
        bootstrap = bootstrap.replace(ready_old, ready_new, 1)
    elif ready_new not in bootstrap:
        raise SystemExit('Could not install immediate Pingus backdrop refresh')

    bootstrap_path.write_text(bootstrap, encoding='utf-8')


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

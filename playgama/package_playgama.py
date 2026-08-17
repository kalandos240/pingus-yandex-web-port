#!/usr/bin/env python3
"""Convert an already-built browser/Yandex dist directory into a Playgama package."""
from pathlib import Path
import argparse
import re
import shutil

BRIDGE = '<script src="https://bridge.playgama.com/v1/stable/playgama-bridge.js"></script>'
ADAPTER = '<script src="playgama-yandex-compat.js"></script>'
NOTICE = """Playgama integration
====================

Active SDK: Playgama Bridge JS Core v1 stable
https://bridge.playgama.com/v1/stable/playgama-bridge.js

The package keeps the port's already-tested game-side Yandex-style calls behind
playgama-yandex-compat.js. That facade maps language, lifecycle, ads, pause/resume
and Player data to Playgama Bridge. The Playgama package does not load /sdk.js.

Bridge configuration: playgama-bridge-config.json
"""


def patch_html(html: str) -> str:
    if 'bridge.playgama.com/v1/stable/playgama-bridge.js' in html:
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
    if BRIDGE not in html or ADAPTER not in html:
        raise SystemExit('Playgama Bridge bootstrap was not installed')
    index.write_text(html, encoding='utf-8')

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

    print(f'Playgama package prepared: {dist}')
    print(f'Unpacked bytes: {total}')


if __name__ == '__main__':
    main()

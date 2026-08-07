from pathlib import Path
import re

# Yandex Games injects a nonce-based CSP into hosted archive games. When a
# nonce/hash source is present, browsers ignore 'unsafe-inline', so ordinary
# inline scripts and inline event handlers in our index are blocked. Keep the
# existing shell patch pipeline intact, then externalize the final generated
# bootstrap/CSS here after all Web patches have been applied.
index_path = Path('../dist/index.html')
js_path = Path('../dist/bootstrap.js')
css_path = Path('../dist/pingus.css')
runtime_path = Path('../dist/pingus.js')

html = index_path.read_text(encoding='utf-8')

style_re = re.compile(r'\n?\s*<style>(.*?)</style>', re.S)
styles = style_re.findall(html)
if len(styles) != 1:
    raise SystemExit(f'expected exactly one inline style block, found {len(styles)}')
css = styles[0].strip() + '\n'
html = style_re.sub('\n  <link rel="stylesheet" href="pingus.css">', html, count=1)

# Match a script tag that has no src attribute. The SDK and pingus runtime are
# already external scripts and must remain untouched.
script_re = re.compile(r'\n?\s*<script(?![^>]*\bsrc\s*=)[^>]*>(.*?)</script>', re.S | re.I)
scripts = script_re.findall(html)
if len(scripts) != 1:
    raise SystemExit(f'expected exactly one inline script block, found {len(scripts)}')
bootstrap = scripts[0].strip() + '\n'

# The old canvas oncontextmenu attribute is an inline JS event handler and is
# blocked by the same CSP. Convert it to a normal listener in bootstrap.js.
old_canvas = '<canvas id="canvas" tabindex="0" oncontextmenu="event.preventDefault()"></canvas>'
new_canvas = '<canvas id="canvas" tabindex="0"></canvas>'
if html.count(old_canvas) != 1:
    raise SystemExit('canvas inline contextmenu handler anchor missing')
html = html.replace(old_canvas, new_canvas, 1)

canvas_anchor = "      const canvas = document.getElementById('canvas');\n"
canvas_listener = canvas_anchor + "      canvas.addEventListener('contextmenu', (event) => event.preventDefault());\n"
if bootstrap.count(canvas_anchor) != 1:
    raise SystemExit('bootstrap canvas anchor missing or duplicated')
bootstrap = bootstrap.replace(canvas_anchor, canvas_listener, 1)

html = script_re.sub('\n  <script src="bootstrap.js"></script>', html, count=1)

# A data: favicon is unnecessary and can produce an unrelated CSP resource
# warning because Yandex's default-src is intentionally restrictive.
html = html.replace('  <link rel="icon" href="data:,">\n', '')

# Release gate: no executable inline script blocks or inline JS handlers remain.
if script_re.search(html):
    raise SystemExit('inline script remained after CSP externalization')
if re.search(r'\son[a-zA-Z]+\s*=', html):
    raise SystemExit('inline event handler remained after CSP externalization')

css_path.write_text(css, encoding='utf-8')
js_path.write_text(bootstrap, encoding='utf-8')
index_path.write_text(html, encoding='utf-8')

# Emscripten SDL1 emits this warning once for the exact compatibility copy that
# Pingus intentionally relies on for mutable software surfaces. The copy must
# stay, but the warning itself is misleading/noisy in Yandex DevTools.
runtime = runtime_path.read_text(encoding='utf-8')
warning = 'warnOnce("WARNING: copying canvas data to memory for compatibility");'
if warning not in runtime:
    raise SystemExit('expected SDL1 canvas compatibility warning call not found')
runtime = runtime.replace(warning, '0;', 1)
runtime_path.write_text(runtime, encoding='utf-8')

print('CSP: inline bootstrap/style/event handler externalized')
print('CSP: index.html contains external scripts only')
print('SDL1: expected canvas compatibility warning suppressed; copy behavior retained')

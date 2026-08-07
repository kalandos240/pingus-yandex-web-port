from pathlib import Path

# Keep Pingus' original 4:3 framebuffer undistorted while making the browser
# viewport look intentional on widescreen/landscape displays. The side fill is
# a low-resolution, blurred copy of the real game frame. It is deliberately
# capped at 384 px internally and refreshed only ~6 fps so the decorative
# backdrop does not compete with the software-rendered game for CPU/GPU time.
p = Path('../web/shell.html')
s = p.read_text(encoding='utf-8')

html_anchor = '''  <main id="game-shell">\n    <canvas id="canvas" tabindex="0" oncontextmenu="event.preventDefault()"></canvas>'''
html_replacement = '''  <main id="game-shell">\n    <canvas id="backdrop" aria-hidden="true"></canvas>\n    <div id="backdrop-overlay" aria-hidden="true"></div>\n    <canvas id="canvas" tabindex="0" oncontextmenu="event.preventDefault()"></canvas>'''
if s.count(html_anchor) != 1:
    raise SystemExit('backdrop HTML anchor missing or duplicated')
s = s.replace(html_anchor, html_replacement, 1)

css_anchor = '''    #game-shell { position: fixed; inset: 0; display: grid; place-items: center; background: #102538; }\n    #canvas { display: block; outline: 0; background: #000; image-rendering: auto; }'''
css_replacement = '''    #game-shell {\n      position: fixed; inset: 0; display: grid; place-items: center; overflow: hidden;\n      background:\n        radial-gradient(circle at top, rgba(76, 121, 155, .35), transparent 42%),\n        linear-gradient(180deg, #173b56 0%, #0d2031 100%);\n    }\n    #backdrop {\n      position: absolute; inset: -4vmax; width: calc(100% + 8vmax); height: calc(100% + 8vmax);\n      display: block; pointer-events: none; opacity: .55;\n      filter: blur(22px) saturate(.92) brightness(.72);\n      transform: scale(1.08); transform-origin: center; image-rendering: auto;\n    }\n    #backdrop-overlay {\n      position: absolute; inset: 0; pointer-events: none;\n      background:\n        radial-gradient(circle at center, rgba(16,37,56,0) 0%, rgba(16,37,56,.16) 54%, rgba(7,15,24,.55) 100%),\n        linear-gradient(180deg, rgba(8,18,29,.08), rgba(8,18,29,.35));\n    }\n    #canvas {\n      position: relative; z-index: 1; display: block; outline: 0; background: #000; image-rendering: auto;\n      box-shadow: 0 14px 42px rgba(0,0,0,.38), 0 0 0 1px rgba(255,255,255,.06);\n    }'''
if s.count(css_anchor) != 1:
    raise SystemExit('backdrop CSS anchor missing or duplicated')
s = s.replace(css_anchor, css_replacement, 1)

js_anchor = '''      const progress = document.getElementById('progress');\n      const canvas = document.getElementById('canvas');'''
js_replacement = '''      const progress = document.getElementById('progress');\n      const backdrop = document.getElementById('backdrop');\n      const backdropContext = backdrop.getContext('2d', { alpha: false });\n      const canvas = document.getElementById('canvas');'''
if s.count(js_anchor) != 1:
    raise SystemExit('backdrop JS element anchor missing or duplicated')
s = s.replace(js_anchor, js_replacement, 1)

fit_anchor = '''      const fitCanvas = () => {\n        const logicalWidth = Math.max(1, canvas.width || 800);\n        const logicalHeight = Math.max(1, canvas.height || 600);\n        const scale = Math.min(window.innerWidth / logicalWidth, window.innerHeight / logicalHeight);\n        canvas.style.width = `${Math.max(1, Math.floor(logicalWidth * scale))}px`;\n        canvas.style.height = `${Math.max(1, Math.floor(logicalHeight * scale))}px`;\n      };\n      window.addEventListener('resize', fitCanvas, { passive: true });\n      new MutationObserver(fitCanvas).observe(canvas, { attributes: true, attributeFilter: ['width', 'height'] });\n      fitCanvas();'''
fit_replacement = '''      const fitCanvas = () => {\n        const logicalWidth = Math.max(1, canvas.width || 800);\n        const logicalHeight = Math.max(1, canvas.height || 600);\n        const scale = Math.min(window.innerWidth / logicalWidth, window.innerHeight / logicalHeight);\n        canvas.style.width = `${Math.max(1, Math.floor(logicalWidth * scale))}px`;\n        canvas.style.height = `${Math.max(1, Math.floor(logicalHeight * scale))}px`;\n      };\n\n      const fitBackdrop = () => {\n        const aspect = Math.max(0.25, window.innerWidth / Math.max(1, window.innerHeight));\n        const width = Math.min(384, Math.max(160, Math.round(220 * aspect)));\n        const height = Math.min(384, Math.max(120, Math.round(width / aspect)));\n        if (backdrop.width !== width || backdrop.height !== height) {\n          backdrop.width = width;\n          backdrop.height = height;\n        }\n      };\n\n      let lastBackdropFrameAt = 0;\n      const drawBackdrop = (timestamp = 0) => {\n        if (!backdropContext || !gameReadySent || !canvas.width || !canvas.height) return;\n        if (timestamp && timestamp - lastBackdropFrameAt < 160) return;\n        lastBackdropFrameAt = timestamp || performance.now();\n        fitBackdrop();\n\n        const bw = backdrop.width;\n        const bh = backdrop.height;\n        const scale = Math.max(bw / canvas.width, bh / canvas.height);\n        const dw = Math.ceil(canvas.width * scale);\n        const dh = Math.ceil(canvas.height * scale);\n        const dx = Math.floor((bw - dw) / 2);\n        const dy = Math.floor((bh - dh) / 2);\n        backdropContext.clearRect(0, 0, bw, bh);\n        backdropContext.drawImage(canvas, dx, dy, dw, dh);\n      };\n\n      const backdropLoop = (timestamp) => {\n        drawBackdrop(timestamp);\n        requestAnimationFrame(backdropLoop);\n      };\n\n      const syncShellLayout = () => {\n        fitCanvas();\n        fitBackdrop();\n        drawBackdrop();\n      };\n      window.addEventListener('resize', syncShellLayout, { passive: true });\n      new MutationObserver(syncShellLayout).observe(canvas, { attributes: true, attributeFilter: ['width', 'height'] });\n      syncShellLayout();\n      requestAnimationFrame(backdropLoop);'''
if s.count(fit_anchor) != 1:
    raise SystemExit('backdrop fitCanvas anchor missing or duplicated')
s = s.replace(fit_anchor, fit_replacement, 1)

p.write_text(s, encoding='utf-8')

from pathlib import Path

# Keep the 4:3 Pingus framebuffer undistorted on widescreen displays, but do not
# mirror/blur live game frames behind it. The old live backdrop made background
# defects appear twice, lagged behind the game at ~6 fps, and produced a moving
# smeared rectangle around every level. Use one stable neutral shell background
# for the entire game instead.
p = Path('../web/shell.html')
s = p.read_text(encoding='utf-8')

old = '''    #game-shell { position: fixed; inset: 0; display: grid; place-items: center; background: #102538; }\n    #canvas { display: block; outline: 0; background: #000; image-rendering: auto; }'''
new = '''    /* pingus-static-shell-backdrop: stable outside the 4:3 framebuffer */\n    #game-shell {\n      position: fixed; inset: 0; display: grid; place-items: center; overflow: hidden;\n      background:\n        radial-gradient(ellipse at 50% 20%, rgba(66, 106, 137, .32) 0%, rgba(24, 55, 78, .16) 38%, transparent 66%),\n        linear-gradient(180deg, #173b56 0%, #102b40 44%, #0b1c2a 100%);\n    }\n    #canvas {\n      position: relative; display: block; outline: 0; background: #000; image-rendering: auto;\n      box-shadow: 0 14px 42px rgba(0,0,0,.38), 0 0 0 1px rgba(255,255,255,.06);\n    }'''
if new not in s:
    if s.count(old) != 1:
        raise SystemExit('static Web backdrop CSS anchor missing or duplicated')
    s = s.replace(old, new, 1)

# A production shell must not contain the retired live-copy backdrop machinery.
for forbidden in ('id="backdrop"', 'backdropContext', 'drawBackdrop', 'backdropLoop'):
    if forbidden in s:
        raise SystemExit(f'static Web backdrop: retired live backdrop remains: {forbidden}')

p.write_text(s, encoding='utf-8')
print('Web backdrop: stable non-animated widescreen shell background enabled')

from pathlib import Path
import re

HPP = Path('src/pingus/worldobjs/surface_background.hpp')
CPP = Path('src/pingus/worldobjs/surface_background.cpp')
LEVELS = Path('data/levels')

# Global Web fix for repeated SurfaceBackground objects.
#
# Pingus 0.7.6 repeats arbitrary background photographs/textures edge-to-edge.
# Many were never authored as exact periodic textures. The defect is visible as
# large rectangular seams while a parallax layer moves. Fix the renderer once,
# for every level and every SurfaceBackground resource, by mirror-tiling repeated
# axes. Mirrored neighbours share the exact same edge pixels, including animated
# sprite backgrounds, so no per-level asset whitelist is required.
#
# Important: a mirrored texture has a 2-tile period. Carry mirror parity through
# start-position normalization and wrap scrolling at 2*width/height; otherwise a
# tile could abruptly switch orientation when its moving boundary crosses zero.

h = HPP.read_text(encoding='utf-8')
old = '''  /** Background image */\n  Sprite bg_sprite;\n\n  /** The horizontal scrolling speed in pixels per tick */'''
new = '''  /** Background image plus Web mirror variants used for seamless repetition. */\n  Sprite bg_sprite;\n  Sprite bg_sprite_hflip;\n  Sprite bg_sprite_vflip;\n  Sprite bg_sprite_hvflip;\n  bool mirror_tile_x;\n  bool mirror_tile_y;\n\n  /** The horizontal scrolling speed in pixels per tick */'''
if new not in h:
    if h.count(old) != 1:
        raise SystemExit('Web background seams: header sprite anchor missing or duplicated')
    h = h.replace(old, new, 1)
HPP.write_text(h, encoding='utf-8')

s = CPP.read_text(encoding='utf-8')
old = '''  keep_aspect(false),\n  bg_sprite(),\n  scroll_ox(0),'''
new = '''  keep_aspect(false),\n  bg_sprite(),\n  bg_sprite_hflip(),\n  bg_sprite_vflip(),\n  bg_sprite_hvflip(),\n  mirror_tile_x(false),\n  mirror_tile_y(false),\n  scroll_ox(0),'''
if new not in s:
    if s.count(old) != 1:
        raise SystemExit('Web background seams: initializer anchor missing or duplicated')
    s = s.replace(old, new, 1)

old = '''    bg_sprite = Sprite(desc);\n  }\n  else\n  {'''
new = '''    bg_sprite = Sprite(desc);\n#ifdef __EMSCRIPTEN__\n    // Non-stretched Sprite backgrounds repeat in both axes. Build all mirrored\n    // variants from the same descriptor so animated backgrounds stay in sync.\n    bg_sprite_hflip = Sprite(*Resource::load_sprite_desc(desc.res_name),\n                             ResourceModifier::ROT0FLIP);\n    bg_sprite_vflip = Sprite(*Resource::load_sprite_desc(desc.res_name),\n                             ResourceModifier::ROT180FLIP);\n    bg_sprite_hvflip = Sprite(*Resource::load_sprite_desc(desc.res_name),\n                              ResourceModifier::ROT180);\n    mirror_tile_x = true;\n    mirror_tile_y = true;\n#endif\n  }\n  else\n  {'''
if new not in s:
    if s.count(old) != 1:
        raise SystemExit('Web background seams: descriptor Sprite anchor missing or duplicated')
    s = s.replace(old, new, 1)

old = '''    bg_sprite = Sprite(surface);\n  }\n}'''
new = '''    bg_sprite = Sprite(surface);\n#ifdef __EMSCRIPTEN__\n    // Stretching consumes an axis completely. Mirror only axes that the draw\n    // loop will still repeat, preserving the original stretched composition.\n    mirror_tile_x = !stretch_x;\n    mirror_tile_y = !stretch_y;\n    if (mirror_tile_x)\n      bg_sprite_hflip = Sprite(surface.mod(ResourceModifier::ROT0FLIP));\n    if (mirror_tile_y)\n      bg_sprite_vflip = Sprite(surface.mod(ResourceModifier::ROT180FLIP));\n    if (mirror_tile_x && mirror_tile_y)\n      bg_sprite_hvflip = Sprite(surface.mod(ResourceModifier::ROT180));\n#endif\n  }\n}'''
if new not in s:
    if s.count(old) != 1:
        raise SystemExit('Web background seams: Surface Sprite anchor missing or duplicated')
    s = s.replace(old, new, 1)

old = '''  bg_sprite.update();\n\n  if (!bg_sprite || globals::static_graphics)'''
new = '''  bg_sprite.update();\n#ifdef __EMSCRIPTEN__\n  if (mirror_tile_x) bg_sprite_hflip.update();\n  if (mirror_tile_y) bg_sprite_vflip.update();\n  if (mirror_tile_x && mirror_tile_y) bg_sprite_hvflip.update();\n#endif\n\n  if (!bg_sprite || globals::static_graphics)'''
if new not in s:
    if s.count(old) != 1:
        raise SystemExit('Web background seams: update anchor missing or duplicated')
    s = s.replace(old, new, 1)

# A mirrored sequence repeats only after two tiles. Preserve that phase when an
# animated/scrolling background accumulator wraps.
old = '''  if (scroll_x) \n  {\n    scroll_ox += scroll_x;\n\n    if (scroll_ox > bg_sprite.get_width())\n      scroll_ox -= static_cast<float>(bg_sprite.get_width());\n    else if (-scroll_ox > bg_sprite.get_width())\n      scroll_ox += static_cast<float>(bg_sprite.get_width());\n  }\n\n  if (scroll_y) \n  {\n    scroll_oy += scroll_y;\n\n    if (scroll_oy > bg_sprite.get_height())\n      scroll_oy -= static_cast<float>(bg_sprite.get_height());\n    else if (-scroll_oy > bg_sprite.get_height())\n      scroll_oy += static_cast<float>(bg_sprite.get_height());\n  }'''
new = '''  if (scroll_x)\n  {\n    scroll_ox += scroll_x;\n#ifdef __EMSCRIPTEN__\n    const float wrap_x = static_cast<float>(bg_sprite.get_width() * (mirror_tile_x ? 2 : 1));\n#else\n    const float wrap_x = static_cast<float>(bg_sprite.get_width());\n#endif\n    while (scroll_ox > wrap_x) scroll_ox -= wrap_x;\n    while (-scroll_ox > wrap_x) scroll_ox += wrap_x;\n  }\n\n  if (scroll_y)\n  {\n    scroll_oy += scroll_y;\n#ifdef __EMSCRIPTEN__\n    const float wrap_y = static_cast<float>(bg_sprite.get_height() * (mirror_tile_y ? 2 : 1));\n#else\n    const float wrap_y = static_cast<float>(bg_sprite.get_height());\n#endif\n    while (scroll_oy > wrap_y) scroll_oy -= wrap_y;\n    while (-scroll_oy > wrap_y) scroll_oy += wrap_y;\n  }'''
if new not in s:
    if s.count(old) != 1:
        raise SystemExit('Web background seams: scroll wrap anchor missing or duplicated')
    s = s.replace(old, new, 1)

# Normalize the first drawn tile to the viewport while carrying how many full
# tile-width shifts were applied. That shift determines the first tile's mirror
# parity and prevents a moving tile from changing orientation at x/y == 0.
old = '''  if (start_x > 0)\n    start_x = (start_x % bg_sprite.get_width()) - bg_sprite.get_width();\n\n  if (start_y > 0)\n    start_y = (start_y % bg_sprite.get_height()) - bg_sprite.get_height();'''
new = '''#ifdef __EMSCRIPTEN__\n  bool first_flip_x = false;\n  bool first_flip_y = false;\n\n  if (mirror_tile_x)\n  {\n    const int width = bg_sprite.get_width();\n    int tile_shift = 0;\n    if (start_x > 0)\n    {\n      tile_shift = -((start_x + width - 1) / width);\n      start_x += tile_shift * width;\n    }\n    else if (start_x <= -width)\n    {\n      tile_shift = (-start_x) / width;\n      start_x += tile_shift * width;\n    }\n    first_flip_x = ((tile_shift % 2) != 0);\n  }\n  else if (start_x > 0)\n  {\n    start_x = (start_x % bg_sprite.get_width()) - bg_sprite.get_width();\n  }\n\n  if (mirror_tile_y)\n  {\n    const int height = bg_sprite.get_height();\n    int tile_shift = 0;\n    if (start_y > 0)\n    {\n      tile_shift = -((start_y + height - 1) / height);\n      start_y += tile_shift * height;\n    }\n    else if (start_y <= -height)\n    {\n      tile_shift = (-start_y) / height;\n      start_y += tile_shift * height;\n    }\n    first_flip_y = ((tile_shift % 2) != 0);\n  }\n  else if (start_y > 0)\n  {\n    start_y = (start_y % bg_sprite.get_height()) - bg_sprite.get_height();\n  }\n#else\n  if (start_x > 0)\n    start_x = (start_x % bg_sprite.get_width()) - bg_sprite.get_width();\n\n  if (start_y > 0)\n    start_y = (start_y % bg_sprite.get_height()) - bg_sprite.get_height();\n#endif'''
if new not in s:
    if s.count(old) != 1:
        raise SystemExit('Web background seams: start phase anchor missing or duplicated')
    s = s.replace(old, new, 1)

old = '''  for(int y = start_y;\n      y < world->get_height();\n      y += bg_sprite.get_height())\n  {\n    for(int x = start_x;\n        x < world->get_width();\n        x += bg_sprite.get_width())'''
new = '''  int tile_row = 0;\n  for(int y = start_y;\n      y < world->get_height();\n      y += bg_sprite.get_height(), ++tile_row)\n  {\n    int tile_col = 0;\n    for(int x = start_x;\n        x < world->get_width();\n        x += bg_sprite.get_width(), ++tile_col)'''
if new not in s:
    if s.count(old) != 1:
        raise SystemExit('Web background seams: tile loop anchor missing or duplicated')
    s = s.replace(old, new, 1)

old = '''      gc.color().draw(bg_sprite, Vector2i(x - offset.x, y - offset.y), pos.z);'''
new = '''#ifdef __EMSCRIPTEN__\n      const bool flip_x = mirror_tile_x && (first_flip_x != ((tile_col % 2) != 0));\n      const bool flip_y = mirror_tile_y && (first_flip_y != ((tile_row % 2) != 0));\n      if (flip_x && flip_y)\n        gc.color().draw(bg_sprite_hvflip, Vector2i(x - offset.x, y - offset.y), pos.z);\n      else if (flip_x)\n        gc.color().draw(bg_sprite_hflip, Vector2i(x - offset.x, y - offset.y), pos.z);\n      else if (flip_y)\n        gc.color().draw(bg_sprite_vflip, Vector2i(x - offset.x, y - offset.y), pos.z);\n      else\n        gc.color().draw(bg_sprite, Vector2i(x - offset.x, y - offset.y), pos.z);\n#else\n      gc.color().draw(bg_sprite, Vector2i(x - offset.x, y - offset.y), pos.z);\n#endif'''
if new not in s:
    if s.count(old) != 1:
        raise SystemExit('Web background seams: draw anchor missing or duplicated')
    s = s.replace(old, new, 1)
CPP.write_text(s, encoding='utf-8')

# Whole-game audit. Count every SurfaceBackground, including WIP/test levels,
# and classify repeat axes. Nothing is rewritten at level-data level: the engine
# fix automatically covers current and future background resources.
def balanced_end(text, start):
    depth = 0
    in_string = False
    escaped = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escaped:
                escaped = False
            elif ch == '\\':
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
            if depth == 0:
                return i + 1
    raise SystemExit('Web background seams: malformed surface-background block')

total = repeat_x = repeat_y = repeat_both = 0
resources = set()
for path in sorted(LEVELS.rglob('*.pingus')):
    text = path.read_text(encoding='utf-8', errors='strict')
    pos = 0
    while True:
        start = text.find('(surface-background', pos)
        if start < 0:
            break
        end = balanced_end(text, start)
        block = text[start:end]
        total += 1
        mx = re.search(r'\(image\s+"([^"]+)"\)', block)
        if mx:
            resources.add(mx.group(1))
        sx = '(stretch-x #t)' in block
        sy = '(stretch-y #t)' in block
        if not sx:
            repeat_x += 1
        if not sy:
            repeat_y += 1
        if not sx and not sy:
            repeat_both += 1
        pos = end

if total < 200 or len(resources) < 25:
    raise SystemExit(f'Web background seams: unexpectedly small whole-game audit: {total} objects, {len(resources)} resources')

patched_cpp = CPP.read_text(encoding='utf-8')
for marker in (
    'mirror_tile_x', 'mirror_tile_y',
    'ResourceModifier::ROT0FLIP', 'ResourceModifier::ROT180FLIP',
    'const float wrap_x', 'const float wrap_y',
    'first_flip_x', 'first_flip_y', 'tile_col', 'tile_row',
    'const bool flip_x', 'const bool flip_y',
):
    if marker not in patched_cpp:
        raise SystemExit(f'Web background seams: renderer marker missing: {marker}')

print(
    'Web background seams: stable global mirror-tiling renderer enabled; '
    f'{total} SurfaceBackground object(s), {len(resources)} resource type(s), '
    f'{repeat_x} repeating X, {repeat_y} repeating Y, {repeat_both} repeating both audited'
)

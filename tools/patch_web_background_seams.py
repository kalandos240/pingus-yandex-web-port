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

old = '''      gc.color().draw(bg_sprite, Vector2i(x - offset.x, y - offset.y), pos.z);'''
new = '''#ifdef __EMSCRIPTEN__\n      // Choose parity from the tile's absolute grid coordinate rather than from\n      // loop counters. The mirrored pattern therefore remains stable while the\n      // camera/parallax origin crosses a tile boundary.\n      const int tile_x = (x >= 0) ? (x / bg_sprite.get_width())\n                                  : -(((-x) + bg_sprite.get_width() - 1) / bg_sprite.get_width());\n      const int tile_y = (y >= 0) ? (y / bg_sprite.get_height())\n                                  : -(((-y) + bg_sprite.get_height() - 1) / bg_sprite.get_height());\n      const bool flip_x = mirror_tile_x && ((tile_x % 2) != 0);\n      const bool flip_y = mirror_tile_y && ((tile_y % 2) != 0);\n      if (flip_x && flip_y)\n        gc.color().draw(bg_sprite_hvflip, Vector2i(x - offset.x, y - offset.y), pos.z);\n      else if (flip_x)\n        gc.color().draw(bg_sprite_hflip, Vector2i(x - offset.x, y - offset.y), pos.z);\n      else if (flip_y)\n        gc.color().draw(bg_sprite_vflip, Vector2i(x - offset.x, y - offset.y), pos.z);\n      else\n        gc.color().draw(bg_sprite, Vector2i(x - offset.x, y - offset.y), pos.z);\n#else\n      gc.color().draw(bg_sprite, Vector2i(x - offset.x, y - offset.y), pos.z);\n#endif'''
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
        if not sx: repeat_x += 1
        if not sy: repeat_y += 1
        if not sx and not sy: repeat_both += 1
        pos = end

if total < 200 or len(resources) < 25:
    raise SystemExit(f'Web background seams: unexpectedly small whole-game audit: {total} objects, {len(resources)} resources')

patched_cpp = CPP.read_text(encoding='utf-8')
for marker in ('mirror_tile_x', 'mirror_tile_y', 'ResourceModifier::ROT0FLIP',
               'ResourceModifier::ROT180FLIP', 'const bool flip_x', 'const bool flip_y'):
    if marker not in patched_cpp:
        raise SystemExit(f'Web background seams: renderer marker missing: {marker}')

print(
    'Web background seams: global mirror-tiling renderer enabled; '
    f'{total} SurfaceBackground object(s), {len(resources)} resource type(s), '
    f'{repeat_x} repeating X, {repeat_y} repeating Y, {repeat_both} repeating both audited'
)

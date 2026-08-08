from pathlib import Path

# Pingus 0.7.6 repeats small surface backgrounds (clouds, sky, etc.) directly.
# Many of those old textures were never perfectly edge-matched, so on the
# browser's software renderer the tile boundaries become very obvious as
# vertical/horizontal seams. Canvas filtering cannot fix an actual mismatch in
# the source tile.
#
# For the Web build, turn every *static*, non-stretched SurfaceBackground into a
# 2x2 mirrored tile:
#
#   original | horizontal mirror
#   --------- + -----------------
#   vertical | 180-degree mirror
#
# Adjacent edges are then pixel-identical by construction. Repeating that 2x2
# texture also remains seamless at its outer edges. Animated backgrounds are
# left untouched so their frame animation is preserved.

path = Path('src/pingus/worldobjs/surface_background.cpp')
s = path.read_text(encoding='utf-8')

include_anchor = '#include "engine/display/scene_context.hpp"\n'
include_patch = '''#include "engine/display/scene_context.hpp"\n\n#ifdef __EMSCRIPTEN__\n#  include "engine/display/sprite_description.hpp"\n#endif\n'''
if 'sprite_description.hpp' not in s:
    if s.count(include_anchor) != 1:
        raise SystemExit('surface background include anchor missing or duplicated')
    s = s.replace(include_anchor, include_patch, 1)

branch_old = '''  if (!stretch_x && !stretch_y && color.a == 0)\n  {\n    // FIXME: would be nice to allow surface manipulation with\n    // animated sprites, but it's not that easy to do\n    bg_sprite = Sprite(desc);\n  }\n  else\n  {\n    Surface surface = Resource::load_surface(desc);'''
branch_new = '''  bool use_surface = stretch_x || stretch_y || color.a != 0;\n\n#ifdef __EMSCRIPTEN__\n  // Static tiled backgrounds can be converted to a seamless mirrored surface.\n  // Preserve the original Sprite path only for genuinely animated backgrounds.\n  SpriteDescription* sprite_desc = Resource::load_sprite_desc(desc.res_name);\n  const bool animated_background =\n    sprite_desc && sprite_desc->array != Size(1, 1);\n  if (!animated_background)\n    use_surface = true;\n#endif\n\n  if (!use_surface)\n  {\n    // Keep animated sprites animated.\n    bg_sprite = Sprite(desc);\n  }\n  else\n  {\n    Surface surface = Resource::load_surface(desc);'''
if 'animated_background' not in s:
    if s.count(branch_old) != 1:
        raise SystemExit('surface background constructor branch anchor missing or duplicated')
    s = s.replace(branch_old, branch_new, 1)

sprite_anchor = '''\n    bg_sprite = Sprite(surface);\n  }\n}'''
seam_patch = '''\n#ifdef __EMSCRIPTEN__\n    if (!stretch_x && !stretch_y && surface &&\n        surface.get_width() > 1 && surface.get_height() > 1)\n    {\n      // Mirroring guarantees exact edge continuity even for legacy textures\n      // whose opposite sides were painted differently. This removes the\n      // checkerboard-like sky seams globally without changing level geometry.\n      Surface tile = surface.convert_to_rgba();\n      const int tile_w = tile.get_width();\n      const int tile_h = tile.get_height();\n\n      Surface seamless(tile_w * 2, tile_h * 2);\n      Surface flip_x = tile.mod(ResourceModifier::ROT0FLIP);\n      Surface flip_y = tile.mod(ResourceModifier::ROT180FLIP);\n      Surface flip_xy = tile.mod(ResourceModifier::ROT180);\n\n      seamless.blit(tile,    0,      0);\n      seamless.blit(flip_x, tile_w,  0);\n      seamless.blit(flip_y, 0,      tile_h);\n      seamless.blit(flip_xy, tile_w, tile_h);\n      surface = seamless;\n    }\n#endif\n\n    bg_sprite = Sprite(surface);\n  }\n}'''
if 'Mirroring guarantees exact edge continuity' not in s:
    if s.count(sprite_anchor) != 1:
        raise SystemExit('surface background sprite anchor missing or duplicated')
    s = s.replace(sprite_anchor, seam_patch, 1)

path.write_text(s, encoding='utf-8')
print('Web background seams: static tiled SurfaceBackgrounds use mirrored 2x2 textures')

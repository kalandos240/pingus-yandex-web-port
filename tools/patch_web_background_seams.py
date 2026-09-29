from pathlib import Path
import re

CPP = Path('src/pingus/worldobjs/surface_background.cpp')
LEVELS = Path('data/levels')

# Yandex Web: make every rear SurfaceBackground fully static.
#
# The original desktop renderer combines parallax, autonomous scrolling and
# edge-to-edge repetition. Many Pingus 0.7.6 background images were not authored
# as seamless textures, so moving/tiled backgrounds expose rectangular seams in
# the browser. For the fixed 800x600 Web framebuffer, the robust solution is to
# render exactly one viewport-sized background frame, pinned to screen space.
# There is no repetition, parallax, animation or scroll, therefore no moving
# tile boundary can ever become visible.

s = CPP.read_text(encoding='utf-8')

settings_anchor = '''  reader.read_bool("keep-aspect", keep_aspect);\n\n  if (!stretch_x && !stretch_y && color.a == 0)'''
settings_patch = '''  reader.read_bool("keep-aspect", keep_aspect);\n\n#ifdef __EMSCRIPTEN__\n  // Yandex browser build: rear backgrounds are deliberately static. Force the\n  // Surface path so the image can be resized to the 800x600 framebuffer once,\n  // disable parallax and autonomous scrolling, and never repeat it on screen.\n  para_x = 0.0f;\n  para_y = 0.0f;\n  scroll_x = 0.0f;\n  scroll_y = 0.0f;\n  stretch_x = true;\n  stretch_y = true;\n  keep_aspect = false;\n#endif\n\n  if (!stretch_x && !stretch_y && color.a == 0)'''
if settings_patch not in s:
    if s.count(settings_anchor) != 1:
        raise SystemExit('Web static background: constructor settings anchor missing or duplicated')
    s = s.replace(settings_anchor, settings_patch, 1)

scale_anchor = '''    if (stretch_x && stretch_y)\n    {\n      surface = surface.scale(world->get_width(), world->get_height());\n    }'''
scale_patch = '''    if (stretch_x && stretch_y)\n    {\n#ifdef __EMSCRIPTEN__\n      // The Web framebuffer is intentionally fixed at 800x600 by the earlier\n      // performance patch. Scale to that viewport, not to the (often much\n      // larger) scrollable level dimensions.\n      surface = surface.scale(globals::default_screen_width,\n                              globals::default_screen_height);\n#else\n      surface = surface.scale(world->get_width(), world->get_height());\n#endif\n    }'''
if scale_patch not in s:
    if s.count(scale_anchor) != 1:
        raise SystemExit('Web static background: stretch scaling anchor missing or duplicated')
    s = s.replace(scale_anchor, scale_patch, 1)

update_anchor = '''void\nSurfaceBackground::update()\n{\n  bg_sprite.update();'''
update_patch = '''void\nSurfaceBackground::update()\n{\n#ifdef __EMSCRIPTEN__\n  // Keep the first frame forever. Scroll offsets were disabled in the\n  // constructor, and animated background sprites must not advance either.\n  return;\n#endif\n  bg_sprite.update();'''
if update_patch not in s:
    if s.count(update_anchor) != 1:
        raise SystemExit('Web static background: update anchor missing or duplicated')
    s = s.replace(update_anchor, update_patch, 1)

draw_anchor = '''  offset.x -= gc.color().get_rect().left;\n  offset.y -= gc.color().get_rect().top;\n\n  int start_x = static_cast<int>((static_cast<float>(offset.x) * para_x) + scroll_ox);'''
draw_patch = '''  offset.x -= gc.color().get_rect().left;\n  offset.y -= gc.color().get_rect().top;\n\n#ifdef __EMSCRIPTEN__\n  // Draw exactly one viewport-sized frame in screen space. Subtracting the\n  // current world-to-screen offset cancels the camera transform, so the image\n  // stays fixed while the level moves underneath it. No tiling means no seam.\n  gc.color().draw(bg_sprite, Vector2i(-offset.x, -offset.y), pos.z);\n  return;\n#endif\n\n  int start_x = static_cast<int>((static_cast<float>(offset.x) * para_x) + scroll_ox);'''
if draw_patch not in s:
    if s.count(draw_anchor) != 1:
        raise SystemExit('Web static background: draw anchor missing or duplicated')
    s = s.replace(draw_anchor, draw_patch, 1)

CPP.write_text(s, encoding='utf-8')

# Whole shipped-data audit. We keep this broad so any later level addition is
# automatically covered by the renderer-level policy rather than a texture list.
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
    raise SystemExit('Web static background: malformed surface-background block')

total = 0
resources = set()
scrolling = 0
parallax = 0
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
        if re.search(r'\(scroll-[xy]\s+[-+0-9.]', block):
            scrolling += 1
        if re.search(r'\(para-[xy]\s+[-+0-9.]', block):
            parallax += 1
        pos = end

if total < 200 or len(resources) < 25:
    raise SystemExit(f'Web static background: unexpectedly small audit: {total} objects, {len(resources)} resources')

patched = CPP.read_text(encoding='utf-8')
for marker in (
    'para_x = 0.0f;',
    'scroll_x = 0.0f;',
    'surface.scale(globals::default_screen_width',
    'gc.color().draw(bg_sprite, Vector2i(-offset.x, -offset.y), pos.z);',
    '// Keep the first frame forever.',
):
    if marker not in patched:
        raise SystemExit(f'Web static background: renderer marker missing: {marker}')

print(
    'Web static backgrounds: one fixed 800x600 frame per SurfaceBackground; '
    f'{total} object(s), {len(resources)} resource type(s), '
    f'{scrolling} source scrolling block(s), {parallax} source parallax block(s) audited'
)

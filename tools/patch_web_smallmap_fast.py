from pathlib import Path

# In Emscripten SDL1, Framebuffer::draw_line() calls SDL_LockSurface(screen).
# SDL_LockSurface then performs ctx.getImageData() over the entire 800x600
# framebuffer. Pingus uses one tiny line per active pingu on the minimap, so
# crowd size accidentally multiplied full-screen readbacks every frame.
# Opaque SDL_FillRect is rendered directly by Canvas2D and needs no readback.
p = Path('src/pingus/components/smallmap.cpp')
s = p.read_text(encoding='utf-8')

old_frame = '  gc.draw_rect(view_rect, Color(0, 255, 0));\n'
new_frame = '''#ifdef __EMSCRIPTEN__
  // Four 1px opaque fills render the viewport outline without locking and
  // reading the full screen surface.
  if (view_rect.get_width() > 0 && view_rect.get_height() > 0)
  {
    gc.draw_fillrect(Rect(view_rect.left, view_rect.top,
                          view_rect.right, view_rect.top + 1), Color(0, 255, 0));
    gc.draw_fillrect(Rect(view_rect.left, view_rect.bottom - 1,
                          view_rect.right, view_rect.bottom), Color(0, 255, 0));
    gc.draw_fillrect(Rect(view_rect.left, view_rect.top,
                          view_rect.left + 1, view_rect.bottom), Color(0, 255, 0));
    gc.draw_fillrect(Rect(view_rect.right - 1, view_rect.top,
                          view_rect.right, view_rect.bottom), Color(0, 255, 0));
  }
#else
  gc.draw_rect(view_rect, Color(0, 255, 0));
#endif
'''
if s.count(old_frame) != 1:
    raise SystemExit('SmallMap view-rect anchor missing or duplicated')
s = s.replace(old_frame, new_frame, 1)

old_marker = '    gc.draw_line(Vector2i(x, y), Vector2i(x, y-2), Color(255, 255, 0));\n'
new_marker = '''#ifdef __EMSCRIPTEN__
    gc.draw_fillrect(Rect(x, y - 2, x + 1, y + 1), Color(255, 255, 0));
#else
    gc.draw_line(Vector2i(x, y), Vector2i(x, y-2), Color(255, 255, 0));
#endif
'''
if s.count(old_marker) != 1:
    raise SystemExit('SmallMap pingu marker anchor missing or duplicated')
s = s.replace(old_marker, new_marker, 1)
p.write_text(s, encoding='utf-8')

print('Web SmallMap: pingu markers and viewport frame use no-readback fills')

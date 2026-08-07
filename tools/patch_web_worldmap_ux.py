from pathlib import Path

# Allow manual panning of the Tutorial Island/worldmap. Native Pingus always
# centers the camera on the walking pingu, which makes a large 1920x1200 map
# awkward to inspect in a browser. In Web, right-drag pans with a mouse and the
# existing touch adapter maps a finger swipe to the same secondary-drag stream.
p = Path('src/pingus/worldmap/worldmap.hpp')
s = p.read_text(encoding='utf-8')
s = s.replace('''  int mouse_x;\n  int mouse_y;\n''', '''  int mouse_x;\n  int mouse_y;\n#ifdef __EMSCRIPTEN__\n  Vector2i camera_offset;\n#endif\n''', 1)
s = s.replace('''  void on_secondary_button_press(int x, int y);\n  void on_pointer_move(int x, int y);\n''', '''  void on_secondary_button_press(int x, int y);\n  void on_pointer_move(int x, int y);\n#ifdef __EMSCRIPTEN__\n  void pan_camera(int dx, int dy);\n  void reset_camera();\n#endif\n''', 1)
p.write_text(s, encoding='utf-8')

p = Path('src/pingus/worldmap/worldmap.cpp')
s = p.read_text(encoding='utf-8')
s = s.replace('''  mouse_x(0),\n  mouse_y(0)\n{''', '''  mouse_x(0),\n  mouse_y(0)\n#ifdef __EMSCRIPTEN__\n  , camera_offset(0, 0)\n#endif\n{''', 1)
s = s.replace('''  Vector2i pingu_pos(static_cast<int>(pingus->get_pos().x), \n                     static_cast<int>(pingus->get_pos().y));\n''', '''  Vector2i pingu_pos(static_cast<int>(pingus->get_pos().x),\n                     static_cast<int>(pingus->get_pos().y));\n#ifdef __EMSCRIPTEN__\n  const Vector2i follow_pos = pingu_pos;\n  pingu_pos += camera_offset;\n#endif\n''', 1)
s = s.replace('''  gc_state.set_size(gc.get_width(), gc.get_height());\n  gc_state.set_pos(Vector2i(pingu_pos.x, pingu_pos.y));\n''', '''#ifdef __EMSCRIPTEN__\n  // Keep accumulated manual pan bounded even when the pingu is near an edge.\n  camera_offset = pingu_pos - follow_pos;\n#endif\n  gc_state.set_size(gc.get_width(), gc.get_height());\n  gc_state.set_pos(Vector2i(pingu_pos.x, pingu_pos.y));\n''', 1)
# Resume normal pingu-follow once the player chooses a destination node.
s = s.replace('''        else\n        {\n          StatManager::instance()->set_string(worldmap.get_short_name() + "-current-node", dot->get_name());\n        }''', '''        else\n        {\n#ifdef __EMSCRIPTEN__\n          reset_camera();\n#endif\n          StatManager::instance()->set_string(worldmap.get_short_name() + "-current-node", dot->get_name());\n        }''', 1)
insert = '''\n#ifdef __EMSCRIPTEN__\nvoid\nWorldmap::pan_camera(int dx, int dy)\n{\n  camera_offset += Vector2i(dx, dy);\n}\n\nvoid\nWorldmap::reset_camera()\n{\n  camera_offset = Vector2i(0, 0);\n}\n#endif\n\n'''
anchor = 'void\nWorldmap::on_secondary_button_press(int x, int y)\n'
if anchor not in s:
    raise SystemExit('worldmap pan insertion anchor missing')
s = s.replace(anchor, insert + anchor, 1)
p.write_text(s, encoding='utf-8')

p = Path('src/pingus/worldmap/worldmap_component.hpp')
s = p.read_text(encoding='utf-8')
s = s.replace('''  bool m_fast_forward;\n''', '''  bool m_fast_forward;\n#ifdef __EMSCRIPTEN__\n  bool m_map_dragging;\n  int m_drag_x;\n  int m_drag_y;\n#endif\n''', 1)
s = s.replace('''  void on_secondary_button_press (int x, int y);\n  void on_pointer_move(int x, int y);\n''', '''  void on_secondary_button_press (int x, int y);\n  void on_secondary_button_release (int x, int y);\n  void on_pointer_move(int x, int y);\n''', 1)
p.write_text(s, encoding='utf-8')

p = Path('src/pingus/worldmap/worldmap_component.cpp')
s = p.read_text(encoding='utf-8')
s = s.replace('''  worldmap_screen(worldmap_screen_),\n  m_fast_forward(false)\n{''', '''  worldmap_screen(worldmap_screen_),\n  m_fast_forward(false)\n#ifdef __EMSCRIPTEN__\n  , m_map_dragging(false), m_drag_x(0), m_drag_y(0)\n#endif\n{''', 1)
s = s.replace('''void\nWorldmapComponent::on_pointer_move (int x, int y)\n{\n  Rect cliprect = worldmap_screen->get_trans_rect();\n  worldmap_screen->get_worldmap()->on_pointer_move(x - cliprect.left,\n                                                   y - cliprect.top);\n}\n\nvoid\nWorldmapComponent::on_secondary_button_press (int x, int y)\n{\n  Rect cliprect = worldmap_screen->get_trans_rect();\n  worldmap_screen->get_worldmap()->on_secondary_button_press(x - cliprect.left,\n                                                             y - cliprect.top);\n}\n''', '''void\nWorldmapComponent::on_pointer_move (int x, int y)\n{\n#ifdef __EMSCRIPTEN__\n  if (m_map_dragging)\n  {\n    worldmap_screen->get_worldmap()->pan_camera(m_drag_x - x, m_drag_y - y);\n    m_drag_x = x;\n    m_drag_y = y;\n  }\n#endif\n  Rect cliprect = worldmap_screen->get_trans_rect();\n  worldmap_screen->get_worldmap()->on_pointer_move(x - cliprect.left,\n                                                   y - cliprect.top);\n}\n\nvoid\nWorldmapComponent::on_secondary_button_press (int x, int y)\n{\n#ifdef __EMSCRIPTEN__\n  m_map_dragging = true;\n  m_drag_x = x;\n  m_drag_y = y;\n#else\n  Rect cliprect = worldmap_screen->get_trans_rect();\n  worldmap_screen->get_worldmap()->on_secondary_button_press(x - cliprect.left,\n                                                             y - cliprect.top);\n#endif\n}\n\nvoid\nWorldmapComponent::on_secondary_button_release (int, int)\n{\n#ifdef __EMSCRIPTEN__\n  m_map_dragging = false;\n#endif\n}\n''', 1)
p.write_text(s, encoding='utf-8')

# Protect fixed-size menu layouts from long localized strings. Wrap list
# descriptions inside the left text column instead of letting them collide with
# completion statistics, and wrap the selected levelset description as well.
p = Path('src/pingus/screens/level_menu.cpp')
s = p.read_text(encoding='utf-8')
inc = '#include "pingus/gettext.h"\n'
if inc in s and '#include "pingus/string_format.hpp"' not in s:
    s = s.replace(inc, inc + '#include "pingus/string_format.hpp"\n', 1)
s = s.replace('''      gc.print_left(Fonts::chalk_small,  Vector2i(list_rect.left + 105, 40 + y), _(levelset->get_description()));''', '''      gc.print_left(Fonts::chalk_small, Vector2i(list_rect.left + 105, 40 + y),\n                    StringFormat::break_line(_(levelset->get_description()), 330, Fonts::chalk_small));''', 1)
s = s.replace('''    gc.print_center(Fonts::chalk_normal,  Vector2i(rect.get_width()/2, 62), _(levelset->get_description()));''', '''    gc.print_center(Fonts::chalk_normal, Vector2i(rect.get_width()/2, 62),\n                    StringFormat::break_line(_(levelset->get_description()), 520, Fonts::chalk_normal));''', 1)
p.write_text(s, encoding='utf-8')

# The start-screen description used a fixed 600px line width. Keep a safe
# margin on any logical viewport so translated text cannot escape the screen.
p = Path('src/pingus/screens/start_screen.cpp')
s = p.read_text(encoding='utf-8')
s = s.replace('''                format_description(800 - 200));''', '''                format_description(Math::min(600, gc.get_width() - 100)));''', 1)
p.write_text(s, encoding='utf-8')

print('Web worldmap UX: swipe/right-drag panning + localized text wrapping enabled')

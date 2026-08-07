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
s = s.replace('''    gc.print_center(Fonts::chalk_large, Vector2i(rect.get_width()/2, 10), _(levelset->get_title()));\n    gc.print_center(Fonts::chalk_normal,  Vector2i(rect.get_width()/2, 62), _(levelset->get_description()));''', '''    const std::string levelset_title = _(levelset->get_title());\n    if (Fonts::chalk_large.get_width(levelset_title) <= rect.get_width() - 80)\n      gc.print_center(Fonts::chalk_large, Vector2i(rect.get_width()/2, 10), levelset_title);\n    else\n      gc.print_center(Fonts::chalk_normal, Vector2i(rect.get_width()/2, 18), levelset_title);\n    gc.print_center(Fonts::chalk_normal, Vector2i(rect.get_width()/2, 62),\n                    StringFormat::break_line(_(levelset->get_description()), 520, Fonts::chalk_normal));''', 1)
p.write_text(s, encoding='utf-8')

# The start-screen description used a fixed 600px line width. Keep a safe
# margin and use a smaller title font when a Russian title is too wide.
p = Path('src/pingus/screens/start_screen.cpp')
s = p.read_text(encoding='utf-8')
old_title = '''  gc.print_center(Fonts::chalk_large,\n                  Vector2i(gc.get_width() /2,\n                           gc.get_height()/2 - 230),\n                  _(plf.get_levelname()));'''
new_title = '''  const std::string level_title = _(plf.get_levelname());\n  if (Fonts::chalk_large.get_width(level_title) <= gc.get_width() - 100)\n    gc.print_center(Fonts::chalk_large,\n                    Vector2i(gc.get_width()/2, gc.get_height()/2 - 230),\n                    level_title);\n  else\n    gc.print_center(Fonts::chalk_normal,\n                    Vector2i(gc.get_width()/2, gc.get_height()/2 - 220),\n                    level_title);'''
if s.count(old_title) != 1:
    raise SystemExit('start-screen title fit anchor missing')
s = s.replace(old_title, new_title, 1)
s = s.replace('''                format_description(800 - 200));''', '''                format_description(gc.get_width() > 700 ? 600 : gc.get_width() - 100));''', 1)
p.write_text(s, encoding='utf-8')

# Result messages can also be much wider in Russian than in English. Wrap the
# complete localized message, and shrink an over-wide level title.
p = Path('src/pingus/screens/result_screen.cpp')
s = p.read_text(encoding='utf-8')
inc = '#include "pingus/screens/game_session.hpp"\n'
if inc in s and '#include "pingus/string_format.hpp"' not in s:
    s = s.replace(inc, inc + '#include "pingus/string_format.hpp"\n', 1)
old_title = '''  gc.print_center(Fonts::chalk_large, \n                  Vector2i(gc.get_width()/2, \n                           Display::get_height()/2 - 200),\n                  _(result.plf.get_levelname()));'''
new_title = '''  const std::string result_title = _(result.plf.get_levelname());\n  if (Fonts::chalk_large.get_width(result_title) <= gc.get_width() - 100)\n    gc.print_center(Fonts::chalk_large,\n                    Vector2i(gc.get_width()/2, Display::get_height()/2 - 200),\n                    result_title);\n  else\n    gc.print_center(Fonts::chalk_normal,\n                    Vector2i(gc.get_width()/2, Display::get_height()/2 - 190),\n                    result_title);'''
if s.count(old_title) != 1:
    raise SystemExit('result title fit anchor missing')
s = s.replace(old_title, new_title, 1)
old = '''  gc.print_center(Fonts::chalk_normal, Vector2i(gc.get_width()/2, gc.get_height()/2 - 70), message);'''
new = '''  message = StringFormat::break_line(message, 520, Fonts::chalk_normal);\n  gc.print_center(Fonts::chalk_normal, Vector2i(gc.get_width()/2, gc.get_height()/2 - 70), message);'''
if s.count(old) != 1:
    raise SystemExit('result message wrap anchor missing')
s = s.replace(old, new, 1)
p.write_text(s, encoding='utf-8')

print('Web worldmap UX: swipe/right-drag panning + localized text wrapping/fitting enabled')

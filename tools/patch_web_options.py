from pathlib import Path

p = Path('src/pingus/screens/option_menu.cpp')
s = p.read_text(encoding='utf-8')

start = s.find('  ChoiceBox* resolution_box = new ChoiceBox(Rect());\n')
end = s.find('  /*\n    defaults_label', start)
if start < 0 or end < 0:
    raise SystemExit('OptionMenu constructor block anchor missing')

web_block = r'''#ifdef __EMSCRIPTEN__
  // Browser/Yandex build: resolution, renderer, fullscreen, mouse grab,
  // software cursor, FPS and manual language selection are desktop concerns.
  // Keep only controls that are meaningful to a Web player.
  master_volume_box = new SliderBox(Rect(), 25);
  sound_volume_box  = new SliderBox(Rect(), 25);
  music_volume_box  = new SliderBox(Rect(), 25);

  master_volume_box->set_value(config_manager.get_master_volume());
  sound_volume_box->set_value(config_manager.get_sound_volume());
  music_volume_box->set_value(config_manager.get_music_volume());

  C(master_volume_box->on_change.connect(std::bind(&OptionMenu::on_master_volume_change, this, std::placeholders::_1)));
  C(sound_volume_box->on_change.connect(std::bind(&OptionMenu::on_sound_volume_change, this, std::placeholders::_1)));
  C(music_volume_box->on_change.connect(std::bind(&OptionMenu::on_music_volume_change, this, std::placeholders::_1)));

  x_pos = 0;
  y_pos = 0;
  add_item(_("Master Volume:"), master_volume_box);
  add_item(_("Sound Volume:"), sound_volume_box);
  add_item(_("Music Volume:"), music_volume_box);
#else
'''
web_block += s[start:end]
web_block += '#endif\n\n'
s = s[:start] + web_block + s[end:]

# Center the three Web sliders on the blackboard instead of leaving them in
# the old desktop two-column grid.
old_rect = '''  Rect rect(Vector2i(80 + x_offset + x_pos * 320, \n                     140 + y_offset + y_pos * 32),\n            Size(320, 32));'''
new_rect = '''#ifdef __EMSCRIPTEN__\n  Rect rect(Vector2i(240 + x_offset,\n                     220 + y_offset + y_pos * 44),\n            Size(320, 32));\n#else\n  Rect rect(Vector2i(80 + x_offset + x_pos * 320, \n                     140 + y_offset + y_pos * 32),\n            Size(320, 32));\n#endif'''
if s.count(old_rect) != 1:
    raise SystemExit('OptionMenu add_item layout anchor missing or duplicated')
s = s.replace(old_rect, new_rect, 1)

# The restart warning existed because renderer/resolution/language could require
# a desktop restart. None of the remaining Web sliders require it.
old_note = '''  gc.print_left(Fonts::chalk_normal, \n                Vector2i(gc.get_width()/2 - 320, gc.get_height()/2 + 200),\n                _("Some options require a restart of the game to take effect."));'''
new_note = '''#ifndef __EMSCRIPTEN__\n  gc.print_left(Fonts::chalk_normal, \n                Vector2i(gc.get_width()/2 - 320, gc.get_height()/2 + 200),\n                _("Some options require a restart of the game to take effect."));\n#endif'''
if s.count(old_note) != 1:
    raise SystemExit('OptionMenu restart-note anchor missing or duplicated')
s = s.replace(old_note, new_note, 1)

p.write_text(s, encoding='utf-8')

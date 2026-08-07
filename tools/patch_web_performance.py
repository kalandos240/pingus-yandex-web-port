from pathlib import Path

# Browser rendering always uses Pingus' original 800x600 logical framebuffer.
# CSS scales that framebuffer to the browser viewport. Older Web builds exposed
# desktop resolution/fullscreen settings and stored them in ~/.pingus/config;
# a saved 1920x1200 value makes the software SDL renderer process 4.8x as many
# pixels every frame and is a major source of stutter.
p = Path('src/pingus/pingus_main.cpp')
s = p.read_text(encoding='utf-8')
old = '''    // init the display
    FramebufferType fbtype = SDL_FRAMEBUFFER; 
    if (cmd_options.framebuffer_type.is_set())
    {
      fbtype = cmd_options.framebuffer_type.get();
    }

    bool fullscreen = cmd_options.fullscreen.is_set() ? cmd_options.fullscreen.get() : false;
    bool resizable  = cmd_options.resizable.is_set()  ? cmd_options.resizable.get()  : true;

    Size screen_size(800, 600);
    if (fullscreen)
    {
      if (cmd_options.fullscreen_resolution.is_set())
      {
        screen_size = cmd_options.fullscreen_resolution.get();
      }
    }
    else
    {
      if (cmd_options.geometry.is_set())
      {
        screen_size = cmd_options.geometry.get();
      }
    }
'''
new = '''    // init the display
#ifdef __EMSCRIPTEN__
    // Keep one small, deterministic logical framebuffer in WebAssembly and let
    // the HTML shell scale it to the actual device. Never reuse desktop video
    // settings from old persistent configs.
    FramebufferType fbtype = SDL_FRAMEBUFFER;
    bool fullscreen = false;
    bool resizable = false;
    Size screen_size(800, 600);
    globals::desired_fps = 40.0f;
    globals::software_cursor = false;
#else
    FramebufferType fbtype = SDL_FRAMEBUFFER; 
    if (cmd_options.framebuffer_type.is_set())
    {
      fbtype = cmd_options.framebuffer_type.get();
    }

    bool fullscreen = cmd_options.fullscreen.is_set() ? cmd_options.fullscreen.get() : false;
    bool resizable  = cmd_options.resizable.is_set()  ? cmd_options.resizable.get()  : true;

    Size screen_size(800, 600);
    if (fullscreen)
    {
      if (cmd_options.fullscreen_resolution.is_set())
      {
        screen_size = cmd_options.fullscreen_resolution.get();
      }
    }
    else
    {
      if (cmd_options.geometry.is_set())
      {
        screen_size = cmd_options.geometry.get();
      }
    }
#endif
'''
if s.count(old) != 1:
    raise SystemExit('web fixed-framebuffer anchor missing or duplicated')
s = s.replace(old, new, 1)
p.write_text(s, encoding='utf-8')

# Do not let legacy desktop settings reconfigure the already-created browser
# display after startup. Audio settings and ru/en language still apply.
p = Path('src/pingus/config_manager.cpp')
s = p.read_text(encoding='utf-8')
old = '''  if (m_opts.framebuffer_type.is_set())
    set_renderer(m_opts.framebuffer_type.get());
  else
    set_renderer(SDL_FRAMEBUFFER);

  if (opts.master_volume.is_set())'''
new = '''#ifdef __EMSCRIPTEN__
  set_renderer(SDL_FRAMEBUFFER);
#else
  if (m_opts.framebuffer_type.is_set())
    set_renderer(m_opts.framebuffer_type.get());
  else
    set_renderer(SDL_FRAMEBUFFER);
#endif

  if (opts.master_volume.is_set())'''
if s.count(old) != 1:
    raise SystemExit('renderer config clamp anchor missing')
s = s.replace(old, new, 1)

old = '''  if (opts.fullscreen_resolution.is_set())
    set_fullscreen_resolution(opts.fullscreen_resolution.get());

  if (opts.fullscreen.is_set())
    set_fullscreen(opts.fullscreen.get());

  if (opts.resizable.is_set())
    set_resizable(opts.resizable.get());

  if (opts.mouse_grab.is_set())
    set_mouse_grab(opts.mouse_grab.get());

  if (opts.print_fps.is_set())
    set_print_fps(opts.print_fps.get());

  if (opts.software_cursor.is_set())
    set_software_cursor(opts.software_cursor.get());
'''
new = '''#ifndef __EMSCRIPTEN__
  if (opts.fullscreen_resolution.is_set())
    set_fullscreen_resolution(opts.fullscreen_resolution.get());

  if (opts.fullscreen.is_set())
    set_fullscreen(opts.fullscreen.get());

  if (opts.resizable.is_set())
    set_resizable(opts.resizable.get());

  if (opts.mouse_grab.is_set())
    set_mouse_grab(opts.mouse_grab.get());

  if (opts.print_fps.is_set())
    set_print_fps(opts.print_fps.get());

  if (opts.software_cursor.is_set())
    set_software_cursor(opts.software_cursor.get());
#else
  // Browser fullscreen/size is owned by CSS/Yandex, not native SDL settings.
  globals::print_fps = false;
  globals::software_cursor = false;
#endif
'''
if s.count(old) != 1:
    raise SystemExit('desktop option clamp anchor missing')
s = s.replace(old, new, 1)
p.write_text(s, encoding='utf-8')

print('Web performance: fixed 800x600 framebuffer and ignored stale desktop video config')

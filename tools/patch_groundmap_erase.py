from pathlib import Path

# Pingus 0.7.6 expects the visual erase mask passed to GroundMap to be an
# 8-bit paletted SDL surface. The browser build uses Emscripten's STB image
# decoder so those PNGs arrive as 32-bit RGBA instead. The original function
# rejects that surface before touching the tile pixels, while CollisionMask
# already supports 32-bit alpha. Result: Basher/Digger-style actions update
# collision but leave the old terrain visible. Preserve the legacy 8-bit path
# and add an Emscripten-only RGBA-alpha path for the visual GroundMap.

p = Path('src/pingus/ground_map.cpp')
s = p.read_text(encoding='utf-8')

old_depth = '''  if (sprovider.get_surface()->format->BitsPerPixel != 8)\n  {\n    log_error("Image has wrong color depth: " \n              << static_cast<int>(sprovider.get_surface()->format->BitsPerPixel));\n    return;\n  }'''
new_depth = '''#ifdef __EMSCRIPTEN__\n  const int source_bpp = sprovider.get_surface()->format->BitsPerPixel;\n  if (source_bpp != 8 && source_bpp != 32)\n  {\n    log_error("Image has wrong color depth: "\n              << static_cast<int>(source_bpp));\n    return;\n  }\n#else\n  if (sprovider.get_surface()->format->BitsPerPixel != 8)\n  {\n    log_error("Image has wrong color depth: " \n              << static_cast<int>(sprovider.get_surface()->format->BitsPerPixel));\n    return;\n  }\n#endif'''
if s.count(old_depth) != 1:
    raise SystemExit('GroundMap erase depth anchor missing or duplicated')
s = s.replace(old_depth, new_depth, 1)

old_branch = '''  if (sprovider.get_surface()->flags & SDL_SRCCOLORKEY)\n  {\n    Uint32 colorkey = 0;\n    SDL_GetColorKey(sprovider.get_surface(), &colorkey);\n\n    for (int y = start_y; y < end_y; ++y)\n    {\n      Uint8* tptr = target_buf + tpitch*(y+y_pos) + 4*(x_pos + start_x);\n      Uint8* sptr = source_buf + spitch*y + start_x;\n\n      for (int x = start_x; x < end_x; ++x)\n      { \n        if (*sptr != colorkey && colmap->getpixel(real_x_arg+x, real_y_arg+y) != Groundtype::GP_SOLID)\n        {\n          tptr[3] = 0;\n        }\n\n        tptr += 4;\n        sptr += 1;\n      }\n    }\n  }\n  else\n  {\n    for (int y = start_y; y < end_y; ++y)\n    {\n      Uint8* tptr = target_buf + tpitch*(y+y_pos) + 4*(x_pos + start_x);\n      Uint8* sptr = source_buf + spitch*y + start_x;\n\n      for (int x = start_x; x < end_x; ++x)\n      { \n        if (colmap->getpixel(real_x_arg+x, real_y_arg+y) != Groundtype::GP_SOLID)\n        {\n          tptr[3] = 0;\n        }\n              \n        tptr += 4;\n        sptr += 1;\n      }\n    }\n  }'''
new_branch = '''#ifdef __EMSCRIPTEN__\n  if (sprovider.get_surface()->format->BitsPerPixel == 32)\n  {\n    // Match CollisionMask::init_colmap(): only fully opaque pixels belong to\n    // the 32-bit mask. This keeps the rendered hole aligned with collision.\n    for (int y = start_y; y < end_y; ++y)\n    {\n      Uint8* tptr = target_buf + tpitch*(y+y_pos) + 4*(x_pos + start_x);\n      Uint8* sptr = source_buf + spitch*y + 4*start_x;\n\n      for (int x = start_x; x < end_x; ++x)\n      {\n        if (sptr[3] == 255 &&\n            colmap->getpixel(real_x_arg+x, real_y_arg+y) != Groundtype::GP_SOLID)\n        {\n          tptr[3] = 0;\n        }\n\n        tptr += 4;\n        sptr += 4;\n      }\n    }\n  }\n  else\n#endif\n  if (sprovider.get_surface()->flags & SDL_SRCCOLORKEY)\n  {\n    Uint32 colorkey = 0;\n    SDL_GetColorKey(sprovider.get_surface(), &colorkey);\n\n    for (int y = start_y; y < end_y; ++y)\n    {\n      Uint8* tptr = target_buf + tpitch*(y+y_pos) + 4*(x_pos + start_x);\n      Uint8* sptr = source_buf + spitch*y + start_x;\n\n      for (int x = start_x; x < end_x; ++x)\n      { \n        if (*sptr != colorkey && colmap->getpixel(real_x_arg+x, real_y_arg+y) != Groundtype::GP_SOLID)\n        {\n          tptr[3] = 0;\n        }\n\n        tptr += 4;\n        sptr += 1;\n      }\n    }\n  }\n  else\n  {\n    for (int y = start_y; y < end_y; ++y)\n    {\n      Uint8* tptr = target_buf + tpitch*(y+y_pos) + 4*(x_pos + start_x);\n      Uint8* sptr = source_buf + spitch*y + start_x;\n\n      for (int x = start_x; x < end_x; ++x)\n      { \n        if (colmap->getpixel(real_x_arg+x, real_y_arg+y) != Groundtype::GP_SOLID)\n        {\n          tptr[3] = 0;\n        }\n              \n        tptr += 4;\n        sptr += 1;\n      }\n    }\n  }'''
if s.count(old_branch) != 1:
    raise SystemExit('GroundMap erase pixel branch anchor missing or duplicated')
s = s.replace(old_branch, new_branch, 1)

p.write_text(s, encoding='utf-8')

from pathlib import Path

p = Path('src/engine/display/sdl_framebuffer_surface_impl.cpp')
s = p.read_text(encoding='utf-8')

old = '''SDLFramebufferSurfaceImpl::SDLFramebufferSurfaceImpl(SDL_Surface* src) :
  surface()
{
  if (src->format->Amask != 0 || (src->flags & SDL_SRCCOLORKEY))
    surface = SDL_DisplayFormatAlpha(src);
  else
    surface = SDL_DisplayFormat(src);
}
'''

new = '''SDLFramebufferSurfaceImpl::SDLFramebufferSurfaceImpl(SDL_Surface* src) :
  surface()
{
#ifdef __EMSCRIPTEN__
  // Emscripten's SDL1 SDL_DisplayFormatAlpha() path copies the backing canvas,
  // while Pingus' dynamic GroundMap tiles are modified through their pixel
  // buffer.  On the web target that produced transparent framebuffer copies:
  // collision/minimap data was present, but terrain disappeared on screen.
  // Copy the actual SDL pixel buffer and let SDL_UnlockSurface upload it to
  // the destination canvas instead.
  if (!src)
    return;

  Uint32 flags = SDL_SWSURFACE;
  if (src->flags & SDL_SRCALPHA)
    flags |= SDL_SRCALPHA;
  if (src->flags & SDL_SRCCOLORKEY)
    flags |= SDL_SRCCOLORKEY;

  surface = SDL_CreateRGBSurface(flags,
                                 src->w, src->h,
                                 src->format->BitsPerPixel,
                                 src->format->Rmask,
                                 src->format->Gmask,
                                 src->format->Bmask,
                                 src->format->Amask);
  if (!surface)
    return;

  if (src->format->palette && surface->format->palette)
  {
    SDL_SetPalette(surface, SDL_LOGPAL | SDL_PHYSPAL,
                   src->format->palette->colors,
                   0, src->format->palette->ncolors);
  }

  SDL_LockSurface(src);
  SDL_LockSurface(surface);
  const int bytes_per_row = src->pitch < surface->pitch ? src->pitch : surface->pitch;
  for (int y = 0; y < src->h; ++y)
  {
    memcpy(static_cast<Uint8*>(surface->pixels) + y * surface->pitch,
           static_cast<Uint8*>(src->pixels) + y * src->pitch,
           bytes_per_row);
  }
  SDL_UnlockSurface(surface);
  SDL_UnlockSurface(src);
#else
  if (src->format->Amask != 0 || (src->flags & SDL_SRCCOLORKEY))
    surface = SDL_DisplayFormatAlpha(src);
  else
    surface = SDL_DisplayFormat(src);
#endif
}
'''

if old not in s:
    raise SystemExit('SDL framebuffer constructor patch anchor missing')

p.write_text(s.replace(old, new, 1), encoding='utf-8')

from pathlib import Path

p = Path('src/engine/display/sdl_framebuffer_surface_impl.cpp')
s = p.read_text(encoding='utf-8')

include_anchor = '#include "engine/display/sdl_framebuffer_surface_impl.hpp"\n'
include_patch = '''#include "engine/display/sdl_framebuffer_surface_impl.hpp"

#ifdef __EMSCRIPTEN__
#include <emscripten.h>
#endif
'''
if include_anchor not in s:
    raise SystemExit('SDL framebuffer include patch anchor missing')
s = s.replace(include_anchor, include_patch, 1)

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
  // SDL_DisplayFormatAlpha() in Emscripten can lose pixels from Pingus'
  // dynamically assembled GroundMap tile canvases. Create an owning SDL
  // surface and copy the browser canvas directly, which is the authoritative
  // image after SDL_BlitSurface() composed each terrain tile.
  if (!src)
    return;

  Uint32 flags = SDL_SWSURFACE;
  if (src->flags & SDL_SRCALPHA)
    flags |= SDL_SRCALPHA;

  surface = SDL_CreateRGBSurface(flags,
                                 src->w, src->h,
                                 32,
#if SDL_BYTEORDER == SDL_BIG_ENDIAN
                                 0xff000000, 0x00ff0000, 0x0000ff00, 0x000000ff
#else
                                 0x000000ff, 0x0000ff00, 0x00ff0000, 0xff000000
#endif
                                 );
  if (!surface)
    return;

  EM_ASM({
    var src = SDL.surfaces[$0];
    var dst = SDL.surfaces[$1];
    if (src && dst && src.canvas && dst.ctx) {
      dst.ctx.save();
      dst.ctx.globalAlpha = 1;
      dst.ctx.globalCompositeOperation = 'copy';
      dst.ctx.drawImage(src.canvas, 0, 0);
      dst.ctx.restore();
      dst.source = 'pingus:framebuffer-copy';
    }
  }, src, surface);
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

# Desktop SDL ignores dstrect.w/h for SDL_BlitSurface(), so Pingus 0.7.6
# leaves them at zero. Emscripten's SDL1 compatibility layer incorrectly uses
# those fields when a clip rect is active. SceneContext always enables a clip
# rect, which made every terrain/world sprite blit intersect as a 0x0 rect.
p = Path('src/engine/display/sdl_framebuffer.cpp')
s = p.read_text(encoding='utf-8')

old_full = '''  dstrect.x = static_cast<Sint16>(pos.x);
  dstrect.y = static_cast<Sint16>(pos.y);
  dstrect.w = 0;
  dstrect.h = 0;  

  SDL_BlitSurface(src, NULL, screen, &dstrect);'''
new_full = '''  dstrect.x = static_cast<Sint16>(pos.x);
  dstrect.y = static_cast<Sint16>(pos.y);
#ifdef __EMSCRIPTEN__
  dstrect.w = static_cast<Uint16>(src->w);
  dstrect.h = static_cast<Uint16>(src->h);
#else
  dstrect.w = 0;
  dstrect.h = 0;
#endif

  SDL_BlitSurface(src, NULL, screen, &dstrect);'''
if s.count(old_full) != 1:
    raise SystemExit('full SDL blit patch anchor missing')
s = s.replace(old_full, new_full, 1)

old_crop = '''  dstrect.x = static_cast<Sint16>(pos.x);
  dstrect.y = static_cast<Sint16>(pos.y);
  dstrect.w = 0;
  dstrect.h = 0;  

  SDL_Rect sdlsrcrect;
  sdlsrcrect.x = static_cast<Sint16>(srcrect.left);
  sdlsrcrect.y = static_cast<Sint16>(srcrect.top);
  sdlsrcrect.w = static_cast<Uint16>(srcrect.get_width());
  sdlsrcrect.h = static_cast<Uint16>(srcrect.get_height());

  SDL_BlitSurface(src, &sdlsrcrect, screen, &dstrect);'''
new_crop = '''  dstrect.x = static_cast<Sint16>(pos.x);
  dstrect.y = static_cast<Sint16>(pos.y);

  SDL_Rect sdlsrcrect;
  sdlsrcrect.x = static_cast<Sint16>(srcrect.left);
  sdlsrcrect.y = static_cast<Sint16>(srcrect.top);
  sdlsrcrect.w = static_cast<Uint16>(srcrect.get_width());
  sdlsrcrect.h = static_cast<Uint16>(srcrect.get_height());
#ifdef __EMSCRIPTEN__
  dstrect.w = sdlsrcrect.w;
  dstrect.h = sdlsrcrect.h;
#else
  dstrect.w = 0;
  dstrect.h = 0;
#endif

  SDL_BlitSurface(src, &sdlsrcrect, screen, &dstrect);'''
if s.count(old_crop) != 1:
    raise SystemExit('cropped SDL blit patch anchor missing')
s = s.replace(old_crop, new_crop, 1)

p.write_text(s, encoding='utf-8')

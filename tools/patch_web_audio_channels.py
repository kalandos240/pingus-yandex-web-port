from pathlib import Path

# Emscripten SDL_mixer's HTMLAudio backend can leave a channel occupied when a
# short sound's play() promise is rejected/paused by browser autoplay or an
# overlay transition. Native SDL_mixer reuses completed channels, but in that
# browser edge case onended never fires and eventually every one of the default
# 32 channels stays occupied, producing "All 32 channels in use!" repeatedly.
p = Path('src/engine/sound/sound_real.cpp')
s = p.read_text(encoding='utf-8')

include_anchor = '#include <SDL.h>\n'
include_replacement = '''#include <SDL.h>\n#ifdef __EMSCRIPTEN__\n#  include <emscripten.h>\n#endif\n'''
if s.count(include_anchor) != 1:
    raise SystemExit('sound_real SDL include anchor missing or duplicated')
s = s.replace(include_anchor, include_replacement, 1)

open_anchor = '''  if (Mix_OpenAudio(44100, MIX_DEFAULT_FORMAT, 2, 4096) == -1)\n  {\n    raise_exception(std::runtime_error, "Unable to initialize SDL_Mixer: " << Mix_GetError());\n  }\n'''
open_replacement = open_anchor + '''#ifdef __EMSCRIPTEN__\n  // Give effect-heavy levels more headroom while keeping a finite cap.\n  Mix_AllocateChannels(64);\n#endif\n'''
if s.count(open_anchor) != 1:
    raise SystemExit('sound_real Mix_OpenAudio anchor missing or duplicated')
s = s.replace(open_anchor, open_replacement, 1)

play_anchor = '''    int channel = Mix_PlayChannel(-1, chunk, 0);\n'''
play_replacement = '''#ifdef __EMSCRIPTEN__\n    // Reclaim stale HTMLAudio-backed SDL_mixer channels. A failed/blocked\n    // HTMLMediaElement.play() can otherwise leave channelInfo.audio assigned\n    // forever because no ended event will arrive. Do not interrupt sounds that\n    // are genuinely still playing. If all 64 channels are really active, drop\n    // this one effect silently instead of spamming the console every frame.\n    const int web_channel_available = EM_ASM_INT({\n      if (typeof SDL === 'undefined' || !SDL.channels) return 1;\n      const first = SDL.channelMinimumNumber || 0;\n      const count = SDL.numChannels || SDL.channels.length;\n      let free = false;\n      for (let i = first; i < count; ++i) {\n        const channel = SDL.channels[i];\n        if (!channel) continue;\n        const audio = channel.audio;\n        if (audio && (audio.ended || audio.error || audio.paused)) {\n          channel.audio = null;\n        }\n        if (!channel.audio) free = true;\n      }\n      return free ? 1 : 0;\n    });\n    if (!web_channel_available)\n      return;\n#endif\n\n    int channel = Mix_PlayChannel(-1, chunk, 0);\n'''
if s.count(play_anchor) != 1:
    raise SystemExit('sound_real Mix_PlayChannel anchor missing or duplicated')
s = s.replace(play_anchor, play_replacement, 1)

p.write_text(s, encoding='utf-8')
print('Web audio: 64 SDL_mixer channels + stale HTMLAudio reclamation enabled')

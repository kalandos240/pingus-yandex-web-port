from pathlib import Path

# Pingus 0.7.6 splits GroundMap graphics into 32x32 tiles. That is useful for
# old native SDL, but Emscripten's SDL1 compatibility turns every tile into a
# separate browser canvas/sprite operation. An 800x600 view can therefore
# submit ~500 terrain sprites every rendered frame. Keep collision pixels and
# world coordinates untouched, but batch the *visual* GroundMap into 128x128
# tiles on Web (~35-50 visible tiles instead of hundreds).
p = Path('src/pingus/ground_map.cpp')
s = p.read_text(encoding='utf-8')

include_anchor = '#include "util/log.hpp"\n'
helper = '''#include "util/log.hpp"\n\nnamespace\n{\ninline int groundmap_tile_size()\n{\n#ifdef __EMSCRIPTEN__\n  return 128;\n#else\n  return globals::tile_size;\n#endif\n}\n}\n'''
if s.count(include_anchor) != 1:
    raise SystemExit('GroundMap include anchor missing or duplicated')
s = s.replace(include_anchor, helper, 1)

count = s.count('globals::tile_size')
if count < 10:
    raise SystemExit(f'Unexpected GroundMap tile-size usage count: {count}')
s = s.replace('globals::tile_size', 'groundmap_tile_size()')

# The helper itself was also rewritten by the broad replacement above; restore
# its desktop return value.
s = s.replace('return groundmap_tile_size();\n#endif', 'return globals::tile_size;\n#endif', 1)

if 'globals::tile_size' not in s:
    raise SystemExit('GroundMap helper desktop fallback missing')

p.write_text(s, encoding='utf-8')
print('Web GroundMap: 128x128 visual tiles enabled (collision map unchanged)')

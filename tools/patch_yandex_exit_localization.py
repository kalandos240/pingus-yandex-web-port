from pathlib import Path
import io
import re

from PIL import Image

DATA_IMAGES = Path('data/images')
LEVELS_ROOT = Path('data/levels')
SPRITE_CPP = Path('src/engine/display/sprite.cpp')
ATLAS_DIR = Path('../assets')
ATLAS_GLOB = 'yandex_ru_texture_patch_atlas.png.part*'
TEXT_FREE_EXITS = {'exits/ice', 'exits/space'}

# Each record maps the English source image to a Russian-only output image.
# bbox is where the original English lettering lives; atlas is the matching
# localized crop inside assets/yandex_ru_texture_patch_atlas.png.
PATCHES = [
    ('exits/crystal', 'exits/crystal.png', 'exits/crystal_ru.png', (54, 42, 108, 69), (0, 0, 54, 27), False),
    ('exits/desert', 'exits/desertexit.png', 'exits/desertexit_ru.png', (50, 42, 101, 65), (56, 0, 107, 23), False),
    ('exits/desert_tut', 'exits/desert_tut.png', 'exits/desert_tut_ru.png', (23, 20, 91, 54), (109, 0, 177, 34), False),
    ('exits/easter', 'exits/easter.png', 'exits/easter_ru.png', (16, 34, 70, 62), (179, 0, 233, 28), False),
    ('exits/forest', 'exits/forest.png', 'exits/forest_ru.png', (31, 14, 88, 40), (235, 0, 292, 26), False),
    ('exits/halloween', 'exits/halloween.png', 'exits/halloween_ru.png', (44, 19, 67, 75), (294, 0, 317, 56), False),
    ('exits/ice2', 'exits/ice2.png', 'exits/ice2_ru.png', (19, 35, 67, 57), (319, 0, 367, 22), False),
    ('exits/industrial', 'exits/industrial.png', 'exits/industrial_ru.png', (50, 53, 102, 78), (369, 0, 421, 25), False),
    ('exits/mud', 'exits/mud.png', 'exits/mud_ru.png', (52, 14, 100, 37), (423, 0, 471, 23), False),
    ('exits/ordina', 'exits/ordina.png', 'exits/ordina_ru.png', (32, 8, 87, 33), (473, 0, 528, 25), False),
    ('exits/pwexit', 'exits/pwexit.png', 'exits/pwexit_ru.png', (0, 0, 80, 38), (530, 0, 610, 38), False),
    ('exits/sortie', 'exits/sortie.png', 'exits/sortie_ru.png', (17, 3, 64, 25), (612, 0, 659, 22), False),
    ('exits/sortie_anim', 'exits/sortie_anim.png', 'exits/sortie_anim_ru.png', (17, 3, 844, 25), (0, 58, 827, 80), False),
    ('exits/stone', 'exits/stone.png', 'exits/stone_ru.png', (14, 13, 63, 37), (829, 58, 878, 82), False),
    ('exits/sweetexit', 'exits/sweetexit.png', 'exits/sweetexit_ru.png', (65, 48, 116, 72), (880, 58, 931, 82), False),
    ('exits/xmas', 'exits/xmas.png', 'exits/xmas_ru.png', (41, 39, 102, 71), (933, 58, 994, 90), False),
    ('traps/laser_exit', 'traps/laser_exit.png', 'traps/laser_exit_ru.png', (14, 13, 438, 37), (0, 92, 424, 116), False),
    ('worldmaps/tutorial/layer0', 'worldmaps/tutorial_layer0.jpg', 'worldmaps/tutorial_layer0_ru.png', (650, 285, 935, 355), (426, 92, 711, 162), True),
]

atlas_parts = sorted(ATLAS_DIR.glob(ATLAS_GLOB))
if not atlas_parts:
    raise SystemExit('Yandex RU texture patch atlas parts are missing')
atlas = Image.open(io.BytesIO(b''.join(p.read_bytes() for p in atlas_parts))).convert('RGBA')
localized_resources = {}
text_bearing_exits = set()
expected_images = []

for resource, source_rel, target_rel, bbox, atlas_box, is_tutorial in PATCHES:
    source_path = DATA_IMAGES / source_rel
    target_path = DATA_IMAGES / target_rel
    if not source_path.is_file():
        raise SystemExit(f'Yandex RU texture source missing: {source_path}')
    image = Image.open(source_path).convert('RGBA')
    crop = atlas.crop(atlas_box)
    if (bbox[2] - bbox[0], bbox[3] - bbox[1]) != crop.size:
        raise SystemExit(f'Yandex RU texture crop size mismatch: {resource}')
    image.paste(crop, (bbox[0], bbox[1]))
    target_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(target_path, format='PNG', optimize=True)
    expected_images.append(target_path)

    if is_tutorial:
        source_sprite = DATA_IMAGES / 'worldmaps/tutorial/layer0.sprite'
        target_sprite = DATA_IMAGES / 'worldmaps/tutorial/layer0_ru.sprite'
        text = source_sprite.read_text(encoding='utf-8')
        if text.count('../tutorial_layer0.jpg') != 1:
            raise SystemExit('Yandex RU tutorial sprite anchor missing or duplicated')
        target_sprite.write_text(
            text.replace('../tutorial_layer0.jpg', '../tutorial_layer0_ru.png', 1),
            encoding='utf-8',
        )
        localized_resources[resource] = 'worldmaps/tutorial/layer0_ru'
        continue

    if resource.startswith('exits/'):
        text_bearing_exits.add(resource)

    # Most resources have explicit .sprite descriptors. exits/pwexit is a bare
    # PNG and ResourceManager discovers the localized PNG automatically.
    source_sprite = DATA_IMAGES / f'{resource}.sprite'
    if source_sprite.is_file():
        target_sprite = DATA_IMAGES / f'{resource}_ru.sprite'
        text = source_sprite.read_text(encoding='utf-8')
        match = re.search(r'\(image\s+"([^"]+)"\)', text)
        if not match:
            raise SystemExit(f'Yandex RU sprite image entry missing: {source_sprite}')
        replacement = Path(target_rel).name
        text = text[:match.start(1)] + replacement + text[match.end(1):]
        target_sprite.write_text(text, encoding='utf-8')
    localized_resources[resource] = resource + '_ru'

# Audit every level. We do not rewrite .pingus files: collision masks continue
# to use the original resource descriptor, so localization cannot alter level
# geometry or exit behavior.
exit_pattern = re.compile(r'\(image\s+"(exits/[^"]+)"\)')
referenced_exits = set()
for path in sorted(LEVELS_ROOT.rglob('*.pingus')):
    referenced_exits.update(exit_pattern.findall(path.read_text(encoding='utf-8')))
known_exits = text_bearing_exits | TEXT_FREE_EXITS
unknown = sorted(referenced_exits - known_exits)
if unknown:
    raise SystemExit('Yandex RU exit audit found unclassified resource(s): ' + ', '.join(unknown))
missing = sorted(text_bearing_exits - referenced_exits)
if missing:
    raise SystemExit('Yandex RU exit audit expected unreferenced resource(s): ' + ', '.join(missing))

# Redirect Sprite visuals only for ru. CollisionMask and world-object logic keep
# the original descriptor/resource name.
s = SPRITE_CPP.read_text(encoding='utf-8')
include_anchor = '#include "util/log.hpp"\n'
if '#include "util/system.hpp"' not in s:
    if s.count(include_anchor) != 1:
        raise SystemExit('Yandex RU Sprite include anchor missing or duplicated')
    s = s.replace(include_anchor, include_anchor + '#include "util/system.hpp"\n', 1)

if 'yandex_localized_sprite_name' not in s:
    helper_anchor = 'Sprite::Sprite() :\n'
    if s.count(helper_anchor) != 1:
        raise SystemExit('Yandex RU Sprite helper anchor missing or duplicated')
    mapping_lines = '\n'.join(
        f'    if (name == "{source}") return "{target}";'
        for source, target in sorted(localized_resources.items())
    )
    helper = f'''namespace
{{
std::string yandex_localized_sprite_name(const std::string& name)
{{
#ifdef __EMSCRIPTEN__
  if (System::get_language() == "ru")
  {{
{mapping_lines}
  }}
#endif
  return name;
}}
}} // namespace

'''
    s = s.replace(helper_anchor, helper + helper_anchor, 1)

old = '  SpriteDescription* desc = Resource::load_sprite_desc(name);\n'
new = ('  const std::string localized_name = yandex_localized_sprite_name(name);\n'
       '  SpriteDescription* desc = Resource::load_sprite_desc(localized_name);\n')
if new not in s:
    if s.count(old) != 1:
        raise SystemExit('Yandex RU Sprite string constructor anchor missing or duplicated')
    s = s.replace(old, new, 1)

old = '  SpriteDescription* desc = Resource::load_sprite_desc(res_desc.res_name);\n'
new = ('  const std::string localized_name = yandex_localized_sprite_name(res_desc.res_name);\n'
       '  SpriteDescription* desc = Resource::load_sprite_desc(localized_name);\n')
if new not in s:
    if s.count(old) != 1:
        raise SystemExit('Yandex RU Sprite ResDescriptor anchor missing or duplicated')
    s = s.replace(old, new, 1)
SPRITE_CPP.write_text(s, encoding='utf-8')

missing_outputs = [str(p) for p in expected_images if not p.is_file() or p.stat().st_size == 0]
if missing_outputs:
    raise SystemExit('Yandex RU localized output missing: ' + ', '.join(missing_outputs))

print(
    'Yandex RU texture localization: '
    f'{len(text_bearing_exits)} EXIT textures + laser exit + tutorial map installed; '
    f'{len(referenced_exits)} exit resource types audited; level descriptors unchanged'
)

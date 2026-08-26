from pathlib import Path
import base64
import hashlib
import io
import re
import statistics

from PIL import Image, ImageDraw, ImageFont, ImageFilter

DATA_IMAGES = Path('data/images')
LEVELS_ROOT = Path('data/levels')
SPRITE_CPP = Path('src/engine/display/sprite.cpp')
ATLAS_DIR = Path('../assets')
ATLAS_B64_GLOB = 'yandex_ru_texture_patch_atlas.b64part*'
ATLAS_SHA256 = '9d6449ef12730ecab33a8e4a0758e32eaab5c83e97175eff22560360fa4c0549'
TUTORIAL_SIGN_BOX = (780, 330, 1220, 480)
TUTORIAL_SIGN_TEXT = 'Учебный остров'
TUTORIAL_SIGN_FONT = Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')
ATLAS_PART_SHA256 = [
    '9aee882d6f473479761a6da627a2f42b029ac4e6f30271063e7943bf6bc27f32',
    'bf17bac8516f3d850c57fd7b9af9a2d80f5f991d121142266390043a942c41e6',
    '9e772c5c5e68c7c58ddaeddd4e86a560cb6f1f03bdd231639a79e14a639c465d',
    'c143a6ab1639ae2de87ae4141f702240f9cd9f881b5180214875bcc8159e4083',
    '85f9e9d9ed0627140a300b677fc70eb575cffd60c618600f65bca7e5c5bd0739',
    'c79bfbaa944e86df1c5e5257e1f725706fa32392400541cd1fbe19e0bcdecd9d',
    'da1884f20c759a3c7dbc2805499e81f021568dd3795d6059a721de0c39943c75',
    '6443c376b02c8f2c65f4356ab4e538a4723d2d7fcfcafd3483bbdd6c01c87790',
    'ce148e90e66754590d2f961d31c3963b580e0c4533a2999887453a073ef7ebb8',
    '7b5a7febd807cd8a0d66061b577a91c68b611d0acedb1618852f660a970b87b7',
    '61ace04eb5d1a9ef50fbbe33e082490bdf12a3ae6cac947eb76f47c85fbbbc3f',
    '91fe2e30298ff260f59bb98dc9785fcd8e0f9c87732094e8eeab824a1bee83fc',
    'b26cbb4c74445adeff6af503cc9f409c4fa86d6982cda1fe4a6a19835f3f55f8',
]
TEXT_FREE_EXITS = {'exits/ice', 'exits/space'}

# Each record maps the English source image to a Russian-only output image.
# bbox is where the original English lettering lives; atlas is the matching
# localized crop inside the verified texture-patch atlas.
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
]

atlas_parts = sorted(ATLAS_DIR.glob(ATLAS_B64_GLOB))
if len(atlas_parts) != len(ATLAS_PART_SHA256):
    raise SystemExit(
        f'Yandex RU texture atlas chunk count mismatch: expected {len(ATLAS_PART_SHA256)}, got {len(atlas_parts)}'
    )
encoded_parts = []
for index, (path, expected_hash) in enumerate(zip(atlas_parts, ATLAS_PART_SHA256)):
    text = path.read_text(encoding='ascii').strip()
    actual_hash = hashlib.sha256(text.encode('ascii')).hexdigest()
    if actual_hash != expected_hash:
        raise SystemExit(
            f'Yandex RU texture atlas chunk {index:02d} checksum mismatch: '
            f'expected {expected_hash}, got {actual_hash}'
        )
    encoded_parts.append(text)
try:
    atlas_bytes = base64.b64decode(''.join(encoded_parts), validate=True)
except Exception as error:
    raise SystemExit(f'Yandex RU texture patch atlas base64 is invalid: {error}')
actual_sha256 = hashlib.sha256(atlas_bytes).hexdigest()
if actual_sha256 != ATLAS_SHA256:
    raise SystemExit(
        'Yandex RU texture patch atlas checksum mismatch: '
        f'expected {ATLAS_SHA256}, got {actual_sha256}'
    )
try:
    atlas = Image.open(io.BytesIO(atlas_bytes)).convert('RGBA')
    atlas.load()
except Exception as error:
    raise SystemExit(f'Yandex RU texture patch atlas image is invalid: {error}')
if atlas.size != (1024, 162):
    raise SystemExit(f'Yandex RU texture patch atlas has unexpected size: {atlas.size}')

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

# The old atlas patch for the tutorial map targeted the wrong coordinates and
# left "Tutorial Island" untouched. Rebuild the whole 440x150 sign region from
# the original art: remove the English lettering using a robust per-row estimate
# of the wood colour, preserve the sign outline/posts/snow, then draw the Russian
# label at the exact real sign location. This is deterministic and needs no
# opaque binary replacement image.
worldmap_source = DATA_IMAGES / 'worldmaps/tutorial_layer0.jpg'
worldmap_target = DATA_IMAGES / 'worldmaps/tutorial_layer0_ru.png'
worldmap_image = Image.open(worldmap_source).convert('RGB')
if worldmap_image.size != (1920, 1200):
    raise SystemExit(f'Yandex RU tutorial map has unexpected size: {worldmap_image.size}')
if not TUTORIAL_SIGN_FONT.is_file():
    raise SystemExit(f'Yandex RU tutorial sign font source missing: {TUTORIAL_SIGN_FONT}')

sign = worldmap_image.crop(TUTORIAL_SIGN_BOX)
source_sign = sign.copy()
source_px = source_sign.load()
output_px = sign.load()
# Local coordinates of the wooden sign face. The border, posts and surrounding
# snow remain pixel-for-pixel from the original artwork.
left, top, right, bottom = 57, 43, 381, 93
for y in range(top, bottom):
    samples = []
    for x in range(55, 383):
        red, green, blue = source_px[x, y]
        # Green English lettering is rejected; the median therefore follows the
        # underlying brown board rather than being pulled toward the text.
        if green <= red + 10 and 40 < red < 190 and 25 < green < 150:
            samples.append((red, green, blue))
    if not samples:
        raise SystemExit(f'Yandex RU tutorial sign could not estimate wood row {y}')
    base = tuple(int(statistics.median(channel)) for channel in zip(*samples))
    base_luma = sum(base) // 3
    for x in range(left, right):
        red, green, blue = source_px[x, y]
        luma = (red + green + blue) // 3
        delta = max(-7, min(7, (luma - base_luma) // 8))
        output_px[x, y] = tuple(max(0, min(255, value + delta)) for value in base)

# Suppress JPEG/text remnants without touching the carved frame.
cleaned = sign.crop((left, top, right, bottom)).filter(ImageFilter.GaussianBlur(1.2))
sign.paste(cleaned, (left, top))
draw = ImageDraw.Draw(sign)
font = None
for size in range(38, 15, -1):
    candidate = ImageFont.truetype(str(TUTORIAL_SIGN_FONT), size)
    bounds = draw.textbbox((0, 0), TUTORIAL_SIGN_TEXT, font=candidate, stroke_width=2)
    if bounds[2] - bounds[0] <= 315 and bounds[3] - bounds[1] <= 44:
        font = candidate
        break
if font is None:
    raise SystemExit('Yandex RU tutorial sign text does not fit')
bounds = draw.textbbox((0, 0), TUTORIAL_SIGN_TEXT, font=font, stroke_width=2)
text_width = bounds[2] - bounds[0]
text_height = bounds[3] - bounds[1]
x = (sign.width - text_width) // 2 - bounds[0]
y = 50 + (43 - text_height) // 2 - bounds[1]
# Two passes preserve the hand-painted green-on-wood contrast at game scale.
draw.text((x + 1, y + 2), TUTORIAL_SIGN_TEXT, font=font,
          fill=(21, 65, 30), stroke_width=3, stroke_fill=(38, 54, 25))
draw.text((x, y), TUTORIAL_SIGN_TEXT, font=font,
          fill=(42, 160, 73), stroke_width=1, stroke_fill=(18, 78, 36))
worldmap_image.paste(sign, TUTORIAL_SIGN_BOX[:2])
worldmap_image.save(worldmap_target, format='PNG', optimize=True)
expected_images.append(worldmap_target)
source_sprite = DATA_IMAGES / 'worldmaps/tutorial/layer0.sprite'
target_sprite = DATA_IMAGES / 'worldmaps/tutorial/layer0_ru.sprite'
text = source_sprite.read_text(encoding='utf-8')
if text.count('../tutorial_layer0.jpg') != 1:
    raise SystemExit('Yandex RU tutorial sprite anchor missing or duplicated')
target_sprite.write_text(text.replace('../tutorial_layer0.jpg', '../tutorial_layer0_ru.png', 1), encoding='utf-8')
localized_resources['worldmaps/tutorial/layer0'] = 'worldmaps/tutorial/layer0_ru'

# Additional baked-text resources are generated later by
# patch_web_visual_localization.py. Register their RU names here so Sprite uses
# one locale decision for all graphical text.
localized_resources.update({
    'groundpieces/ground/signposts/danger': 'groundpieces/ground/signposts/danger_ru',
    'groundpieces/ground/penguinworld/penguinworld': 'groundpieces/ground/penguinworld/penguinworld_ru',
    'core/misc/loading': 'core/misc/loading_ru',
    'core/misc/unplayable': 'core/misc/unplayable_ru',
    'core/misc/unplayable2': 'core/misc/unplayable2_ru',
    'core/misc/404sprite': 'core/misc/404sprite_ru',
    'game/loading': 'game/loading_ru',
    'game/404': 'game/404_ru',
})

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
if '#include "tinygettext/dictionary_manager.hpp"' not in s:
    if s.count(include_anchor) != 1:
        raise SystemExit('Yandex RU Sprite include anchor missing or duplicated')
    s = s.replace(include_anchor, '#include "tinygettext/dictionary_manager.hpp"\n' + include_anchor, 1)

if 'extern tinygettext::DictionaryManager dictionary_manager;' not in s:
    extern_anchor = '#include "util/log.hpp"\n\n'
    if s.count(extern_anchor) != 1:
        raise SystemExit('Yandex RU Sprite extern anchor missing or duplicated')
    s = s.replace(extern_anchor, extern_anchor + 'extern tinygettext::DictionaryManager dictionary_manager;\n\n', 1)

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
  if (dictionary_manager.get_language().get_language() == "ru")
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
old_404 = '    desc_.filename = Pathname("images/core/misc/404.png", Pathname::DATA_PATH);\n'
new_404 = ('    desc_.filename = Pathname(dictionary_manager.get_language().get_language() == "ru" ? '
           '"images/core/misc/404_ru.png" : "images/core/misc/404.png", Pathname::DATA_PATH);\n')
if old_404 in s:
    if s.count(old_404) != 2:
        raise SystemExit('Yandex RU 404 fallback anchor count changed')
    s = s.replace(old_404, new_404)
SPRITE_CPP.write_text(s, encoding='utf-8')

missing_outputs = [str(p) for p in expected_images if not p.is_file() or p.stat().st_size == 0]
if missing_outputs:
    raise SystemExit('Yandex RU localized output missing: ' + ', '.join(missing_outputs))

print(
    'Yandex RU texture localization: '
    f'{len(text_bearing_exits)} EXIT textures + laser exit + verified tutorial map installed; '
    f'{len(referenced_exits)} exit resource types audited; level descriptors unchanged'
)

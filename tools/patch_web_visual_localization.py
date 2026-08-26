from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import re

DATA = Path('data')
IMAGES = DATA / 'images'
LEVELS = DATA / 'levels'
SPRITE_CPP = Path('src/engine/display/sprite.cpp')
FONT_BOLD = Path('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf')
FONT_SERIF = Path('/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf')

for font in (FONT_BOLD, FONT_SERIF):
    if not font.is_file():
        raise SystemExit(f'Web visual localization: font source missing: {font}')


def fit_font(text, max_width, max_height, start=48, minimum=7, serif=False):
    probe = ImageDraw.Draw(Image.new('L', (4, 4), 0))
    font_path = FONT_SERIF if serif else FONT_BOLD
    for size in range(start, minimum - 1, -1):
        font = ImageFont.truetype(str(font_path), size)
        stroke = max(1, size // 18)
        method = probe.multiline_textbbox if '\n' in text else probe.textbbox
        kwargs = {'font': font, 'stroke_width': stroke}
        if '\n' in text:
            kwargs.update(spacing=0, align='center')
        box = method((0, 0), text, **kwargs)
        if box[2] - box[0] <= max_width and box[3] - box[1] <= max_height:
            return font
    raise SystemExit(f'Web visual localization: cannot fit text {text!r}')


def centered_text(draw, box, text, font, fill, stroke_fill, stroke_width):
    left, top, right, bottom = box
    if '\n' in text:
        bbox = draw.multiline_textbbox((0, 0), text, font=font, stroke_width=stroke_width,
                                       spacing=0, align='center')
    else:
        bbox = draw.textbbox((0, 0), text, font=font, stroke_width=stroke_width)
    width = bbox[2] - bbox[0]
    height = bbox[3] - bbox[1]
    x = left + (right - left - width) // 2 - bbox[0]
    y = top + (bottom - top - height) // 2 - bbox[1]
    if '\n' in text:
        draw.multiline_text((x, y), text, font=font, fill=fill,
                            stroke_fill=stroke_fill, stroke_width=stroke_width,
                            spacing=0, align='center')
    else:
        draw.text((x, y), text, font=font, fill=fill,
                  stroke_fill=stroke_fill, stroke_width=stroke_width)


# 1) "Danger" groundpiece. Keep the transparent footprint and dimensions, but
# replace the baked English word with a compact Russian warning sign.
danger_src = IMAGES / 'groundpieces/ground/signposts/danger.png'
danger_ru = IMAGES / 'groundpieces/ground/signposts/danger_ru.png'
with Image.open(danger_src) as source:
    if source.size != (215, 121):
        raise SystemExit(f'Web visual localization: unexpected Danger sign size {source.size}')
canvas = Image.new('RGBA', (215, 121), (0, 0, 0, 0))
draw = ImageDraw.Draw(canvas)
draw.polygon([(107, 5), (8, 110), (206, 110)], fill=(202, 18, 14, 246), outline=(52, 0, 0, 255))
draw.polygon([(107, 18), (29, 101), (185, 101)], fill=(255, 220, 34, 250), outline=(110, 30, 0, 255))
font = fit_font('ОПАСНО', 142, 35, start=35)
centered_text(draw, (36, 43, 179, 81), 'ОПАСНО', font,
              (178, 4, 4, 255), (255, 250, 210, 255), 2)
draw.rectangle((103, 81, 111, 93), fill=(74, 10, 2, 255))
draw.ellipse((103, 96, 111, 104), fill=(74, 10, 2, 255))
danger_ru.parent.mkdir(parents=True, exist_ok=True)
canvas.save(danger_ru, format='PNG', optimize=True)

# 2) Hidden/WIP "Penguin World" artwork. It is not in the public campaign now,
# but the whole shipped game data must still not switch back to English if a
# developer/WIP level becomes reachable later.
penguin_src = IMAGES / 'groundpieces/ground/penguinworld/penguinworld.png'
penguin_ru = IMAGES / 'groundpieces/ground/penguinworld/penguinworld_ru.png'
with Image.open(penguin_src) as source:
    size = source.size
if size != (709, 128):
    raise SystemExit(f'Web visual localization: unexpected Penguin World size {size}')
penguin = Image.new('RGBA', size, (0, 0, 0, 0))
pd = ImageDraw.Draw(penguin)
text = 'Мир пингвинов'
font = fit_font(text, 680, 104, start=78, serif=True)
# A light/dark double stroke approximates the original raised metallic title.
centered_text(pd, (8, 5, 701, 121), text, font,
              (194, 194, 194, 255), (36, 36, 36, 255), 5)
centered_text(pd, (6, 3, 699, 119), text, font,
              (218, 218, 218, 255), (245, 245, 245, 220), 1)
penguin.save(penguin_ru, format='PNG', optimize=True)

# 3) Legacy fallback/status artwork. Generate RU siblings rather than replacing
# English originals so English locale remains correct.
def render_status(target, size, text, background, fill, max_width, max_height, start):
    image = Image.new('RGBA', size, background)
    d = ImageDraw.Draw(image)
    font = fit_font(text, max_width, max_height, start=start)
    centered_text(d, (0, 0, size[0], size[1]), text, font, fill, (0, 0, 0, 255), 2)
    image.save(target, format='PNG', optimize=True)

render_status(IMAGES / 'core/misc/loading_ru.png', (175, 66), 'Загрузка…',
              (0, 0, 0, 0), (35, 235, 55, 255), 165, 52, 34)
render_status(IMAGES / 'core/misc/404_ru.png', (64, 64), '404\nНЕТ\nФАЙЛА',
              (0, 0, 0, 255), (255, 255, 255, 255), 58, 57, 17)
render_status(IMAGES / 'core/misc/unplayable_ru.png', (582, 48), 'Уровень недоступен',
              (0, 0, 0, 0), (255, 255, 255, 255), 560, 40, 34)
render_status(IMAGES / 'core/misc/unplayable2_ru.png', (255, 22), 'Уровень недоступен',
              (0, 0, 0, 0), (255, 255, 255, 255), 249, 20, 18)

# Resource aliases used by older game sprites.
(IMAGES / 'game/loading_ru.sprite').write_text(
    '(pingus-sprite\n  (image "/images/core/misc/loading_ru.png"))\n', encoding='utf-8')
(IMAGES / 'game/404_ru.sprite').write_text(
    '(pingus-sprite\n  (image "/images/core/misc/404_ru.png"))\n', encoding='utf-8')
(IMAGES / 'core/misc/404sprite_ru.sprite').write_text(
    '(pingus-sprite\n  (image "404_ru.png"))\n', encoding='utf-8')

# Whole-data audit: inspect every level, including WIP/test content, not only the
# current public campaign. The known baked-English resources must all have RU
# mappings in Sprite, so adding/re-enabling a level cannot silently regress.
all_level_refs = set()
for path in sorted(LEVELS.rglob('*.pingus')):
    all_level_refs.update(re.findall(r'\(image\s+"([^"]+)"\)',
                                     path.read_text(encoding='utf-8', errors='replace')))
worldmap_refs = set()
for path in sorted((DATA / 'worldmaps').rglob('*.worldmap')):
    worldmap_refs.update(re.findall(r'\(image\s+"([^"]+)"\)',
                                    path.read_text(encoding='utf-8', errors='replace')))

known_baked_english = {
    'groundpieces/ground/signposts/danger': 'groundpieces/ground/signposts/danger_ru',
    'groundpieces/ground/penguinworld/penguinworld': 'groundpieces/ground/penguinworld/penguinworld_ru',
    'core/misc/loading': 'core/misc/loading_ru',
    'core/misc/unplayable': 'core/misc/unplayable_ru',
    'core/misc/unplayable2': 'core/misc/unplayable2_ru',
    'core/misc/404sprite': 'core/misc/404sprite_ru',
    'game/loading': 'game/loading_ru',
    'game/404': 'game/404_ru',
}

sprite_text = SPRITE_CPP.read_text(encoding='utf-8')
if 'dictionary_manager.get_language().get_language() == "ru"' not in sprite_text:
    raise SystemExit('Web visual localization: Sprite artwork language is not tied to tinygettext')
for source, target in sorted(known_baked_english.items()):
    expected = f'if (name == "{source}") return "{target}";'
    if expected not in sprite_text:
        raise SystemExit(f'Web visual localization: RU mapping missing for {source}')

# Direct 404 fallback bypasses ResourceManager and therefore has its own source
# assertion in sprite.cpp.
if 'images/core/misc/404_ru.png' not in sprite_text:
    raise SystemExit('Web visual localization: direct 404 fallback is not localized')

expected_files = [
    danger_ru,
    penguin_ru,
    IMAGES / 'core/misc/loading_ru.png',
    IMAGES / 'core/misc/404_ru.png',
    IMAGES / 'core/misc/unplayable_ru.png',
    IMAGES / 'core/misc/unplayable2_ru.png',
    IMAGES / 'game/loading_ru.sprite',
    IMAGES / 'game/404_ru.sprite',
    IMAGES / 'core/misc/404sprite_ru.sprite',
]
for path in expected_files:
    if not path.is_file() or path.stat().st_size == 0:
        raise SystemExit(f'Web visual localization: localized output missing: {path}')

# The player-facing text-bearing exit set + tutorial map are verified by the
# preceding exit-localization patch. Make that dependency explicit here.
for path in [
    IMAGES / 'worldmaps/tutorial_layer0_ru.png',
    IMAGES / 'exits/ice2_ru.png',
    IMAGES / 'exits/desertexit_ru.png',
    IMAGES / 'traps/laser_exit_ru.png',
]:
    if not path.is_file() or path.stat().st_size == 0:
        raise SystemExit(f'Web visual localization: preceding RU texture output missing: {path}')

print(
    'Web visual localization: all known baked-English gameplay/status art has RU variants; '
    f'{len(all_level_refs)} unique image refs across every level + {len(worldmap_refs)} worldmap refs audited'
)

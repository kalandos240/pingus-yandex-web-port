from collections import Counter
from pathlib import Path
import re

from PIL import Image, ImageDraw, ImageFont

# Several original Pingus bitmap atlases were generated with different Unicode
# subsets. In particular, the 16/20px UI fonts used by results/options/menu do
# not contain the complete Russian alphabet, so tinygettext returns correct
# UTF-8 Russian strings but FontImpl silently skips the missing glyphs.
# Append a small Cyrillic fallback atlas to each user-facing font. Existing
# glyphs stay first and therefore keep the original Pingus artwork/style.

TTF_CANDIDATES = [
    Path('/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed.ttf'),
    Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'),
]
ttf_path = next((p for p in TTF_CANDIDATES if p.is_file()), None)
if ttf_path is None:
    raise SystemExit('DejaVu Sans font is required for Web Cyrillic fallback')

RUSSIAN = [0x0401] + list(range(0x0410, 0x0450)) + [0x0451, 0x2116]
FONT_SPECS = [
    ('chalk-16px', 16, False),
    ('chalk-20px', 20, False),
    ('chalk-40px', 40, False),
    ('pingus-small-20px', 20, True),
]


def source_color(font_file: Path, pingus_green: bool):
    """Approximate the existing bitmap color so fallback glyphs blend in."""
    text = font_file.read_text(encoding='utf-8')
    match = re.search(r'\(filename\s+"([^"]+\.png)"\)', text)
    if not match:
        return (126, 205, 76, 255) if pingus_green else (238, 238, 238, 255)
    image_path = Path('data') / match.group(1)
    try:
        rgba = Image.open(image_path).convert('RGBA')
    except Exception:
        return (126, 205, 76, 255) if pingus_green else (238, 238, 238, 255)

    pixels = []
    for r, g, b, a in rgba.getdata():
        if a >= 220:
            if pingus_green and r + g + b < 100:
                continue
            pixels.append((r, g, b))
    if not pixels:
        return (126, 205, 76, 255) if pingus_green else (238, 238, 238, 255)

    common = Counter(pixels).most_common(40)
    if pingus_green:
        rgb = max((c for c, _ in common), key=lambda c: (c[1] - max(c[0], c[2]), c[1]))
    else:
        rgb = max((c for c, _ in common), key=lambda c: sum(c))
    return (*rgb, 255)


def append_fallback(name: str, size: int, pingus_green: bool):
    font_file = Path('data/images/fonts') / f'{name}.font'
    if not font_file.is_file():
        raise SystemExit(f'font description missing: {font_file}')

    text = font_file.read_text(encoding='utf-8')
    existing = {int(x) for x in re.findall(r'\(unicode\s+(\d+)\)', text)}
    missing = [cp for cp in RUSSIAN if cp not in existing]
    if not missing:
        print(f'{name}: Russian glyphs already complete')
        return

    pil_font = ImageFont.truetype(str(ttf_path), size=size)
    fill = source_color(font_file, pingus_green)
    stroke_width = 1 if pingus_green else 0
    stroke_fill = (8, 16, 8, 255) if pingus_green else None

    glyphs = []
    padding = 2
    max_width = 1024 if size >= 32 else 512
    x = padding
    y = padding
    row_h = 0

    for cp in missing:
        ch = chr(cp)
        bbox = pil_font.getbbox(ch, anchor='ls', stroke_width=stroke_width)
        if bbox is None:
            continue
        left, top, right, bottom = [int(v) for v in bbox]
        w = max(1, right - left)
        h = max(1, bottom - top)
        advance = max(1, int(round(pil_font.getlength(ch))))
        if x + w + padding > max_width:
            x = padding
            y += row_h + padding
            row_h = 0
        glyphs.append({
            'cp': cp,
            'left': left,
            'top': top,
            'w': w,
            'h': h,
            'advance': advance,
            'x': x,
            'y': y,
            'ch': ch,
        })
        x += w + padding
        row_h = max(row_h, h)

    if not glyphs:
        raise SystemExit(f'{name}: no Cyrillic glyphs generated')

    atlas_h = y + row_h + padding
    atlas = Image.new('RGBA', (max_width, atlas_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(atlas)
    for g in glyphs:
        anchor_x = g['x'] - g['left']
        anchor_y = g['y'] - g['top']
        kwargs = dict(font=pil_font, fill=fill, anchor='ls')
        if stroke_width:
            kwargs.update(stroke_width=stroke_width, stroke_fill=stroke_fill)
        draw.text((anchor_x, anchor_y), g['ch'], **kwargs)

    atlas_name = f'{name}-ru-web.png'
    atlas_path = Path('data/images/fonts') / atlas_name
    atlas.save(atlas_path, optimize=True)

    lines = [
        '  (image',
        f'   (filename "images/fonts/{atlas_name}")',
        '   (glyphs',
    ]
    for g in glyphs:
        lines.append(
            f"    (glyph (unicode {g['cp']}) "
            f"(offset {g['left']} {g['top']}) "
            f"(advance {g['advance']}) "
            f"(rect {g['x']} {g['y']} {g['x'] + g['w']} {g['y'] + g['h']}))"
        )
    lines += ['    ))']
    block = '\n'.join(lines) + '\n'

    # Original font files differ only in whitespace before the EOF comment.
    # Insert the new image immediately before the final close of (images ...),
    # accepting either one or multiple blank lines.
    closing = re.compile(r'(?P<close>  \)\)\n\s*;; EOF ;;\s*)$')
    match = closing.search(text)
    if not match:
        raise SystemExit(f'{name}: font images closing structure not found')
    text = text[:match.start()] + block + match.group('close')
    font_file.write_text(text, encoding='utf-8')

    final_codes = {int(x) for x in re.findall(r'\(unicode\s+(\d+)\)', text)}
    still_missing = [cp for cp in RUSSIAN if cp not in final_codes]
    if still_missing:
        raise SystemExit(f'{name}: Cyrillic glyph validation failed: {still_missing}')
    print(f'{name}: appended {len(glyphs)} Russian fallback glyphs -> {atlas_name}')


for spec in FONT_SPECS:
    append_fallback(*spec)

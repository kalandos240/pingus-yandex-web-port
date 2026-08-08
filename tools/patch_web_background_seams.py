from pathlib import Path
import importlib
import math
import os
import re
import subprocess
import sys

try:
    from PIL import Image
except ModuleNotFoundError:
    # This patch currently runs before the shared Web-font dependency block.
    # Install Pillow once, then restart this script so the same deterministic
    # texture conversion can run without changing the rest of the build order.
    subprocess.run(['sudo', 'apt-get', 'update'], check=True)
    subprocess.run([
        'sudo', 'apt-get', 'install', '-y', '--no-install-recommends', 'python3-pil'
    ], check=True)
    importlib.invalidate_caches()
    os.execv(sys.executable, [sys.executable, __file__])

# Pingus 0.7.6 repeats small SurfaceBackground images. Several legacy sky/cloud
# textures were painted as ordinary images rather than truly tileable textures,
# so opposite edges do not match and the browser shows obvious rectangular
# seams. The previous Web fix mirrored tiles; that removed pixel jumps but made
# visible mirror axes, which still looked like seams.
#
# Instead, make the *source background textures themselves* periodic. Only image
# resources referenced by surface-background objects are touched. A cosine
# feather blends each pair of opposite edges over a narrow strip, making the
# first/last pixels identical while leaving the interior and original level
# geometry untouched. Pingus can then use its normal SurfaceBackground tiling.

LEVEL_ROOT = Path('data/levels')
IMAGE_ROOT = Path('data/images')


def extract_balanced(text, start):
    depth = 0
    in_string = False
    escaped = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escaped:
                escaped = False
            elif ch == '\\':
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    return text[start:]


def background_resources():
    names = set()
    marker = '(surface-background'
    for level in LEVEL_ROOT.rglob('*.pingus'):
        text = level.read_text(encoding='utf-8', errors='ignore')
        pos = 0
        while True:
            start = text.find(marker, pos)
            if start < 0:
                break
            block = extract_balanced(text, start)
            match = re.search(r'\(image\s+"([^"]+)"\)', block)
            if match:
                names.add(match.group(1))
            pos = start + len(block)
    return sorted(names)


def resolve_image(resource):
    base = IMAGE_ROOT / resource
    for suffix in ('.png', '.jpg', '.jpeg'):
        candidate = Path(str(base) + suffix)
        if candidate.is_file():
            return candidate

    sprite = Path(str(base) + '.sprite')
    if sprite.is_file():
        text = sprite.read_text(encoding='utf-8', errors='ignore')
        # SpriteDescription files store the image path as a quoted PNG/JPG.
        for quoted in re.findall(r'"([^"]+\.(?:png|jpg|jpeg))"', text, flags=re.I):
            candidate = (sprite.parent / quoted).resolve()
            try:
                candidate.relative_to(Path.cwd().resolve())
            except ValueError:
                continue
            if candidate.is_file():
                return candidate
    return None


def blend_tuple(a, b, weight):
    # Move both samples toward their average; at weight=1 they become exactly
    # equal, at weight=0 they remain unchanged.
    avg = tuple((x + y) * 0.5 for x, y in zip(a, b))
    left = tuple(int(round(x * (1.0 - weight) + m * weight)) for x, m in zip(a, avg))
    right = tuple(int(round(y * (1.0 - weight) + m * weight)) for y, m in zip(b, avg))
    return left, right


def make_periodic(path):
    with Image.open(path) as source:
        original_mode = source.mode
        has_alpha = 'A' in source.getbands()
        image = source.convert('RGBA' if has_alpha else 'RGB')

    width, height = image.size
    if width < 8 or height < 8:
        return False

    pixels = image.load()
    # Wide enough to hide the old mismatch on cloudy gradients, but never so
    # wide that the center of the artwork is altered.
    band = max(12, min(width, height) // 10)
    band = min(band, width // 3, height // 3)

    # Left/right feather. Cosine easing has zero slope at both ends, avoiding a
    # new visible band where the correction fades out.
    for d in range(band):
        weight = 0.5 * (1.0 + math.cos(math.pi * d / max(1, band - 1)))
        x0 = d
        x1 = width - 1 - d
        for y in range(height):
            a, b = pixels[x0, y], pixels[x1, y]
            pixels[x0, y], pixels[x1, y] = blend_tuple(a, b, weight)

    # Top/bottom feather. Running this second preserves the already-equal
    # left/right boundary because corresponding edge pixels receive the same
    # correction.
    for d in range(band):
        weight = 0.5 * (1.0 + math.cos(math.pi * d / max(1, band - 1)))
        y0 = d
        y1 = height - 1 - d
        for x in range(width):
            a, b = pixels[x, y0], pixels[x, y1]
            pixels[x, y0], pixels[x, y1] = blend_tuple(a, b, weight)

    # Enforce exact final equality after integer rounding.
    for y in range(height):
        avg = tuple((a + b) // 2 for a, b in zip(pixels[0, y], pixels[width - 1, y]))
        pixels[0, y] = avg
        pixels[width - 1, y] = avg
    for x in range(width):
        avg = tuple((a + b) // 2 for a, b in zip(pixels[x, 0], pixels[x, height - 1]))
        pixels[x, 0] = avg
        pixels[x, height - 1] = avg

    if original_mode not in ('RGB', 'RGBA'):
        image = image.convert(original_mode)

    suffix = path.suffix.lower()
    if suffix in ('.jpg', '.jpeg'):
        image.convert('RGB').save(path, quality=95, subsampling=0, optimize=True)
    else:
        image.save(path, optimize=True)
    return True


resources = background_resources()
processed = []
missing = []
seen_paths = set()
for resource in resources:
    path = resolve_image(resource)
    if path is None:
        missing.append(resource)
        continue
    key = path.resolve()
    if key in seen_paths:
        continue
    seen_paths.add(key)
    if make_periodic(path):
        processed.append((resource, path.as_posix()))

if not processed:
    raise SystemExit('Web background seams: no SurfaceBackground images were processed')

print(f'Web background seams: feathered {len(processed)} unique background texture(s)')
for resource, path in processed:
    print(f'  {resource} -> {path}')
if missing:
    print(f'Web background seams: {len(missing)} unresolved resource(s) left unchanged')

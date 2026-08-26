from pathlib import Path

# Yandex Games content rules disallow esoterics/fortune-telling (3.4.2) and
# references to religion/religious attributes (3.4.5). Pingus 0.7.6 contains
# optional public holiday bonus packs that are not part of the core campaign:
# - Xmas 2011 explicitly says Merry Christmas;
# - Halloween 2007 includes witches/wizardry/curses in reachable descriptions;
# - Halloween 2011 is another public Halloween bonus pack.
# Hide only their levelset descriptors so those bonus levels are unreachable
# from the release UI while the original core campaign remains intact.
public_bonus_packs = {
    'xmas2011.levelset': 'Xmas 2011',
    'halloween.levelset': 'Halloween 2007',
    'halloween2011.levelset': 'Halloween 2011',
}
for filename, title in public_bonus_packs.items():
    path = Path('data/levelsets') / filename
    if not path.is_file():
        raise SystemExit(f'expected Pingus 0.7.6 public bonus levelset is missing: {filename}')
    text = path.read_text(encoding='utf-8')
    if f'(title "{title}")' not in text:
        raise SystemExit(f'unexpected metadata in {filename}; review Yandex content filter')
    path.unlink()
    print(f'Yandex content: removed public {title} bonus levelset')

# One public Desert level is an explicit Indiana Jones / Last Crusade parody and
# its visible clue repeats "God" several times. Besides being a direct
# religious reference, it is an unnecessary third-party-character/IP risk for
# requirement 3.5. Remove just this level from the public Desert list; the rest
# of the original Desert campaign remains available.
desert_set = Path('data/levelsets/desert.levelset')
desert_text = desert_set.read_text(encoding='utf-8')
indiana_line = '  (level (filename "desert/indiana-yingwan"))\n'
if desert_text.count(indiana_line) != 1:
    raise SystemExit('Indiana-style Desert levelset entry missing or duplicated')
desert_set.write_text(desert_text.replace(indiana_line, '', 1), encoding='utf-8')

# Do not merely hide this unsafe level from the menu. It also contains a baked
# English DODGE clue assembled from smallD/smallO/smallD/smallG/smallE hotspot
# rasters. Since the level is intentionally excluded from the Yandex product,
# remove the level file and its four now-unreferenced letter assets from shipped
# data as well. This makes the release-data audit honest: disabled content cannot
# leak English or prohibited references through a future developer entry point.
indiana_level = Path('data/levels/desert/indiana-yingwan.pingus')
if not indiana_level.is_file():
    raise SystemExit('Indiana-style Desert level file missing before release removal')
indiana_level_text = indiana_level.read_text(encoding='utf-8')
for resource in ('smallD', 'smallE', 'smallG', 'smallO'):
    marker = f'hotspots/desert/{resource}'
    if marker not in indiana_level_text:
        raise SystemExit(f'expected baked-English Indiana marker missing: {marker}')
indiana_level.unlink()
for filename in ('smallD.png', 'smallE.png', 'smallG.png', 'smallO.png'):
    asset = Path('data/images/hotspots/desert') / filename
    if not asset.is_file():
        raise SystemExit(f'expected Indiana letter asset missing: {asset}')
    asset.unlink()
print('Yandex content: removed Indiana level data + baked English DODGE letter assets from shipped data')

# Several core Tutorial Island levels reuse a decorated Christmas-tree terrain
# asset. The object is actual ground, so deleting it could alter level geometry.
# Swap it for the similarly sized neutral snowman ground asset instead. This
# preserves a collidable object at the same coordinates without a holiday/
# religious visual reference.
for filename in (
    'data/levels/tutorial/miner-tutorial2-grumbel.pingus',
    'data/levels/tutorial/snow17-grumbel.pingus',
    'data/levels/tutorial/solid-tutorial-grumbel.pingus',
):
    path = Path(filename)
    text = path.read_text(encoding='utf-8')
    old = 'groundpieces/ground/snow/xmas-tree'
    count = text.count(old)
    if count < 1:
        raise SystemExit(f'expected decorated tree reference missing: {filename}')
    path.write_text(text.replace(old, 'groundpieces/ground/snow/snowman'), encoding='utf-8')
    print(f'Yandex content: replaced {count} decorated Christmas-tree terrain object(s) in {filename}')

# One core tutorial title says "Miner's heaven". Even though the phrase is
# idiomatic, "heaven" is an avoidable religious reference under the platform's
# broad rule. Keep the level and gameplay unchanged; only use a neutral title.
miner = Path('data/levels/tutorial/miner-tutorial2-grumbel.pingus')
text = miner.read_text(encoding='utf-8')
old = '(levelname "Miner\'s heaven")'
new = '(levelname "Miner\'s Dream")'
if text.count(old) != 1:
    raise SystemExit('Miner tutorial title anchor missing or duplicated')
miner.write_text(text.replace(old, new, 1), encoding='utf-8')
print("Yandex content: renamed core tutorial title 'Miner\'s heaven' -> 'Miner\'s Dream'")

# Another core tutorial description uses the biblical term "armageddon" for
# Pingus' restart/finish button. The mechanic and button stay untouched; only
# player-facing wording is made neutral for the Yandex release.
snow9 = Path('data/levels/tutorial/snow9-grumbel.pingus')
text = snow9.read_text(encoding='utf-8')
old_description = (
    "The more levels you master, the more difficult they will get, but don't panic, as this one is still pretty easy. "
    "Just use the stuff that you've learned in the previous levels and you shouldn't have many problems. "
    "If you think you've reached a situation from which you can no longer solve the level, double click the armageddon button at the lower right. "
)
new_description = (
    "The more levels you master, the more difficult they will get, but don't panic, as this one is still pretty easy. "
    "Just use the stuff that you've learned in the previous levels and you shouldn't have many problems. "
    "If you think you've reached a situation from which you can no longer solve the level, double click the restart button at the lower right. "
)
if text.count(old_description) != 1:
    raise SystemExit('tutorial restart-description anchor missing or duplicated')
snow9.write_text(text.replace(old_description, new_description, 1), encoding='utf-8')
print("Yandex content: replaced player-facing 'armageddon button' wording with 'restart button'")

# Requirement 8.2.1 applies to player-facing English too. Fix the clearest
# spelling/grammar errors in reachable legacy level descriptions without
# changing mechanics or objectives. Russian equivalents are supplied by the
# companion Web translation patch.
text_fixes = {
    Path('data/levels/desert/desert5-tflavel.pingus'): (
        'but unfortunatley a large tree root blocks their path...',
        'but unfortunately a large tree root blocks their path...'),
    Path('data/levels/desert/desert-crawl-timpany.pingus'): (
        'create a save passage for all the Pingus',
        'create a safe passage for all the Pingus'),
    Path('data/levels/tutorial/bomber-tutorial2-grumbel.pingus'): (
        'by actually self- destructing.',
        'by actually self-destructing.'),
    Path('data/levels/factorycampaign/factory_campaign2.pingus'): (
        'Pingus are leaving South Pole and moving North.',
        'Pingus are leaving the South Pole and moving North.'),
    Path('data/levels/factorycampaign/factory_campaign4.pingus'): (
        'It looks you have encountered serious difficulties.',
        'It looks like you have encountered serious difficulties.'),
    Path('data/levels/factorycampaign/factory_campaign7.pingus'): (
        'Pingus are entering oasis.',
        'Pingus are entering an oasis.'),
    Path('data/levels/desert/desert6-grumbel.pingus'): (
        '(levelname "A bit to the right a bit to left")',
        '(levelname "A bit to the right, a bit to the left")'),
    Path('data/levels/desert/desert5.pingus'): (
        'separated from the exit by large abyss.',
        'separated from the exit by a large abyss.'),
}
for path, (old_text, new_text) in text_fixes.items():
    text = path.read_text(encoding='utf-8')
    if text.count(old_text) != 1:
        raise SystemExit(f'English text-quality anchor missing or duplicated: {path} :: {old_text}')
    path.write_text(text.replace(old_text, new_text, 1), encoding='utf-8')
print(f'Yandex text quality: corrected {len(text_fixes)} reachable English spelling/grammar issues')

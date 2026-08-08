from pathlib import Path

# Yandex Games content rules disallow esoterics/fortune-telling (3.4.2) and
# references to religion/religious attributes (3.4.5). Pingus 0.7.6 contains
# optional public holiday bonus packs that are not part of the core campaign:
# - Xmas 2011 explicitly says Merry Christmas;
# - Halloween 2007 includes witches/wizardry/curses in reachable descriptions;
# - Halloween 2011 is another public Halloween bonus pack.
# Hide only their levelset descriptors so the bonus levels are unreachable from
# the release UI while the original core campaign remains intact.
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

# One core tutorial title says "Miner's heaven". Even though the phrase is
# idiomatic, "heaven" is an avoidable religious reference under the platform's
# broad rule. Keep the level and gameplay unchanged; only use a neutral title.
miner = Path('data/levels/tutorial/miner-tutorial2-grumbel.pingus')
if not miner.is_file():
    raise SystemExit('expected tutorial miner level is missing')
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
if not snow9.is_file():
    raise SystemExit('expected tutorial snow9 level is missing')
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

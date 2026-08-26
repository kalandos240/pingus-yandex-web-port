from pathlib import Path

# Yandex Games requirement 8.2.3 requires player-facing content to match the
# selected localization. Pingus' ice exit has the English word "EXIT" baked
# directly into the image, so gettext/ru.po cannot translate it. For the Web
# build, replace references to that artwork with the text-free stone exit. The
# object remains a normal Pingus exit; only its visual resource changes.
levels_root = Path('data/levels')
old = '"exits/ice"'
new = '"exits/stone"'

changed_files = 0
replacements = 0
for path in sorted(levels_root.rglob('*.pingus')):
    source = path.read_text(encoding='utf-8')
    count = source.count(old)
    if not count:
        continue
    path.write_text(source.replace(old, new), encoding='utf-8')
    changed_files += 1
    replacements += count

if replacements == 0:
    raise SystemExit('Yandex exit localization: no exits/ice references found')

remaining = []
for path in sorted(levels_root.rglob('*.pingus')):
    if old in path.read_text(encoding='utf-8'):
        remaining.append(str(path))

if remaining:
    raise SystemExit('Yandex exit localization left untranslated ice exits: ' + ', '.join(remaining))

print(
    f'Yandex exit localization: replaced {replacements} ice exit reference(s) '
    f'in {changed_files} level file(s)'
)

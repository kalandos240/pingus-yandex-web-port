from pathlib import Path
import ast
import re

# tinygettext warns when the same msgid occurs more than once with different
# Russian translations. The pinned upstream ru.po contains at least one legacy
# duplicate level-description entry. GNU gettext tooling normally rejects or
# resolves such catalogs, but tinygettext loads both and logs a runtime
# "collision in add_translation" warning in the browser console.
#
# Keep the first non-empty translation for each exact msgid and remove later
# duplicate blocks. This is Web-only catalog hygiene; it does not change the
# English source strings or any level data.

po = Path('data/po/ru.po')
text = po.read_text(encoding='utf-8')


def po_value(lines, key):
    for i, line in enumerate(lines):
        if line.startswith(key + ' '):
            parts = [line[len(key) + 1:]]
            j = i + 1
            while j < len(lines) and lines[j].startswith('"'):
                parts.append(lines[j])
                j += 1
            value = ''
            for part in parts:
                try:
                    value += ast.literal_eval(part)
                except Exception:
                    return None
            return value
    return None


blocks = re.split(r'\n\s*\n', text.strip())
kept = []
seen = {}
removed = []

for block in blocks:
    lines = block.splitlines()
    msgid = po_value(lines, 'msgid')
    if msgid is None or msgid == '':
        kept.append(block)
        continue

    msgstr = po_value(lines, 'msgstr')
    if msgid not in seen:
        seen[msgid] = (len(kept), msgstr or '')
        kept.append(block)
        continue

    previous_index, previous_translation = seen[msgid]
    current_translation = msgstr or ''

    # If the first copy is untranslated but a later duplicate has a real
    # translation, keep the useful later block in the original position.
    if not previous_translation and current_translation:
        kept[previous_index] = block
        seen[msgid] = (previous_index, current_translation)
        removed.append((msgid, previous_translation, current_translation, 'replaced-empty-first'))
    else:
        removed.append((msgid, previous_translation, current_translation, 'kept-first'))

# Verify the resulting catalog is collision-free by exact msgid.
final_seen = set()
for block in kept:
    msgid = po_value(block.splitlines(), 'msgid')
    if not msgid:
        continue
    if msgid in final_seen:
        raise SystemExit(f'PO dedupe failed for msgid: {msgid!r}')
    final_seen.add(msgid)

po.write_text('\n\n'.join(kept).rstrip() + '\n', encoding='utf-8')
print(f'Web RU PO: removed {len(removed)} duplicate msgid block(s)')
for msgid, old, new, action in removed:
    printable = msgid.replace('\n', '\\n')
    print(f'  {action}: {printable!r}')

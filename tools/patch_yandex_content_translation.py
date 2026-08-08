from pathlib import Path
import re

po = Path('data/po/ru.po')
if not po.is_file():
    raise SystemExit('Russian Web PO is missing')
text = po.read_text(encoding='utf-8')


def po_quote(value: str) -> str:
    return value.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')


def current_field(path: str, field: str) -> str:
    source = Path(path).read_text(encoding='utf-8')
    match = re.search(r'\(' + re.escape(field) + r'\s+"((?:\\.|[^"\\])*)"\)', source, re.S)
    if not match:
        raise SystemExit(f'missing {field} in {path}')
    return match.group(1).replace('\\n', '\n').replace('\\"', '"')

# Derive each msgid from the already-patched shipped data. This avoids old
# Pingus whitespace quirks while guaranteeing every Web-only English correction
# has an exact Russian counterpart.
specs = [
    ('data/levels/tutorial/miner-tutorial2-grumbel.pingus', 'levelname', 'Мечта шахтёра'),
    ('data/levels/tutorial/snow9-grumbel.pingus', 'description',
     'Чем дальше, тем сложнее уровни, но этот всё ещё довольно простой. Используйте уже изученные способности. Если уровень оказался в безвыходном состоянии, дважды нажмите кнопку перезапуска справа внизу и начните заново.'),
    ('data/levels/desert/desert5-tflavel.pingus', 'description',
     'Глубоко под пирамидой пингусы попали в небольшую подземную комнату, но путь им преграждает большой корень дерева...'),
    ('data/levels/desert/desert-crawl-timpany.pingus', 'description',
     'Путь к выходу заблокирован, а множество небольших тоннелей ведут в разные стороны. Будьте осторожны: некоторые из них заканчиваются смертельной ловушкой. Найдите способ создать безопасный проход и довести всех пингусов до выхода.'),
    ('data/levels/tutorial/bomber-tutorial2-grumbel.pingus', 'description',
     'Иногда других способов нет, и приходится прокладывать путь взрывом. Пингус может самоуничтожиться, чтобы разрушить землю. Он погибнет, но иногда приходится пожертвовать несколькими пингусами, чтобы спасти остальных.'),
    ('data/levels/factorycampaign/factory_campaign2.pingus', 'description',
     'Пингусы покидают Южный полюс и движутся на север. Помогите им!'),
    ('data/levels/factorycampaign/factory_campaign4.pingus', 'description',
     'Похоже, вы столкнулись с серьёзными трудностями. Но не паникуйте: пингусы ждут ваших приказов и рассчитывают на вас. Подсказка: шахтёры, копатели и проходчики здесь очень важны!'),
    ('data/levels/factorycampaign/factory_campaign7.pingus', 'description',
     'В прошлый раз было легко. Теперь будет немного сложнее. Пингусы входят в оазис. Остерегайтесь воды.'),
    ('data/levels/desert/desert6-grumbel.pingus', 'levelname', 'Немного вправо, немного влево'),
    ('data/levels/desert/desert5.pingus', 'description',
     'Пингусов отделяет от выхода большая пропасть. Простого моста недостаточно, чтобы безопасно их провести, если только вы не найдёте правильное место. Сможете обнаружить эту точку?'),
]

added = 0
for path, field, translated in specs:
    source = current_field(path, field)
    marker = 'msgid "' + po_quote(source) + '"'
    if marker in text:
        continue
    text = text.rstrip() + '\n\n# Web/Yandex-safe player-facing wording.\n' \
        + marker + '\nmsgstr "' + po_quote(translated) + '"\n'
    added += 1

po.write_text(text, encoding='utf-8')
print(f'Web RU: added {added} Yandex-safe translation entries')

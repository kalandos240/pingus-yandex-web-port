from pathlib import Path

sprite = Path('data/images/worldmaps/tutorial/layer0.sprite')
localized = Path('data/images/worldmaps/tutorial_layer0_ru.png')
english_image = '../tutorial_layer0.jpg'
russian_image = '../tutorial_layer0_ru.png'

if not localized.is_file() or localized.stat().st_size == 0:
    raise SystemExit('Yandex RU tutorial map: localized PNG is missing')

text = sprite.read_text(encoding='utf-8')
if russian_image not in text:
    if text.count(english_image) != 1:
        raise SystemExit('Yandex RU tutorial map: original sprite image anchor missing or duplicated')
    text = text.replace(english_image, russian_image, 1)
    sprite.write_text(text, encoding='utf-8')

verified = sprite.read_text(encoding='utf-8')
if verified.count(russian_image) != 1 or english_image in verified:
    raise SystemExit('Yandex RU tutorial map: layer0.sprite still resolves to English artwork')

print('Yandex RU tutorial map: layer0.sprite hard-wired to tutorial_layer0_ru.png')

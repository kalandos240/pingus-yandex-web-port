#!/usr/bin/env bash
set -euo pipefail

# Build the same verified Web port as Yandex, but keep the original English
# Tutorial Island descriptor intact. patch_yandex_exit_localization.py already
# creates worldmaps/tutorial/layer0_ru.sprite and patches Sprite so only ru
# resolves to the localized resource. Yandex later hard-wires ru because its
# catalog build is Russian-only; Playgama must remain multilingual.
python3 - <<'PY'
from pathlib import Path

source = Path('../tools/build_web.sh').read_text(encoding='utf-8')
old = '''python3 ../tools/patch_yandex_exit_localization.py
python3 ../tools/patch_force_tutorial_worldmap_ru.py
test -s data/images/exits/ice2_ru.png
test -s data/images/exits/sortie_anim_ru.png
test -s data/images/traps/laser_exit_ru.png
test -s data/images/worldmaps/tutorial_layer0_ru.png
grep -q '../tutorial_layer0_ru.png' data/images/worldmaps/tutorial/layer0.sprite
! grep -q '../tutorial_layer0.jpg' data/images/worldmaps/tutorial/layer0.sprite
grep -q 'yandex_localized_sprite_name' src/engine/display/sprite.cpp
'''
new = '''python3 ../tools/patch_yandex_exit_localization.py
test -s data/images/exits/ice2_ru.png
test -s data/images/exits/sortie_anim_ru.png
test -s data/images/traps/laser_exit_ru.png
test -s data/images/worldmaps/tutorial_layer0_ru.png
test -s data/images/worldmaps/tutorial/layer0_ru.sprite
# Playgama is multilingual: English keeps the original world-map art while
# Russian is selected dynamically by yandex_localized_sprite_name() from the
# same dictionary language that drives the UI.
grep -q '../tutorial_layer0.jpg' data/images/worldmaps/tutorial/layer0.sprite
! grep -q '../tutorial_layer0_ru.png' data/images/worldmaps/tutorial/layer0.sprite
grep -q '../tutorial_layer0_ru.png' data/images/worldmaps/tutorial/layer0_ru.sprite
grep -q 'yandex_localized_sprite_name' src/engine/display/sprite.cpp
grep -q 'worldmaps/tutorial/layer0_ru' src/engine/display/sprite.cpp
'''
if source.count(old) != 1:
    raise SystemExit('Playgama build: Yandex hard-wired tutorial block changed')
source = source.replace(old, new, 1)
# Keep source-offer wording platform-neutral in this build's bundled source.
source = source.replace('Pingus 0.7.6 WebAssembly port for Yandex Games.',
                        'Pingus 0.7.6 WebAssembly port for Playgama.', 1)
Path('/tmp/build_playgama_web.generated.sh').write_text(source, encoding='utf-8')
PY

bash /tmp/build_playgama_web.generated.sh

# Block the exact regression seen in Playgama QA: the shipped base descriptor
# must not be hard-wired to Russian.
test -s ../dist/pingus.js
grep -q 'dictionary_manager.get_language().get_language() == "ru"' src/engine/display/sprite.cpp
grep -q '../tutorial_layer0.jpg' data/images/worldmaps/tutorial/layer0.sprite
! grep -q '../tutorial_layer0_ru.png' data/images/worldmaps/tutorial/layer0.sprite

echo 'Playgama multilingual world map: EN original + RU localized selector installed'

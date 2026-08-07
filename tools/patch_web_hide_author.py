from pathlib import Path
import re

# Apply the last shipped-data translation fixes before the actual-data audit.
# Importing this build helper updates data/po/ru.po in place.
import patch_web_release_translations  # noqa: F401

# Keep GPL attribution in the distributed legal files, but do not expose
# author names/e-mail addresses in the player-facing Yandex Games UI.
p = Path('src/pingus/screens/start_screen.cpp')
s = p.read_text(encoding='utf-8')
old = '''  gc.print_center(Fonts::chalk_small, \n                  Vector2i(gc.get_width()/2,\n                           gc.get_height()/2 + 215),\n                  _("Author: ") + plf.get_author());\n'''
new = '''#ifndef __EMSCRIPTEN__\n  gc.print_center(Fonts::chalk_small,\n                  Vector2i(gc.get_width()/2,\n                           gc.get_height()/2 + 215),\n                  _("Author: ") + plf.get_author());\n#endif\n'''
if s.count(old) != 1:
    raise SystemExit('start-screen author UI anchor missing or duplicated')
s = s.replace(old, new, 1)
p.write_text(s, encoding='utf-8')

# A couple of original levelset labels themselves contain creator names, so
# removing the separate Author row is not enough. Strip those suffixes from the
# Web data as well. The original metadata remains available in AUTHORS/source.
replacements = {
    Path('data/levelsets/alien.levelset'): (
        '(title "Alien by Josh Dye")',
        '(title "Alien")',
    ),
    Path('data/levelsets/mysteryisland.levelset'): (
        '(description "Marooned on an Uncharted Isle [by Lachlan McCubbin]")',
        '(description "Marooned on an Uncharted Isle")',
    ),
}
for path, (old_text, new_text) in replacements.items():
    text = path.read_text(encoding='utf-8')
    if text.count(old_text) != 1:
        raise SystemExit(f'author-bearing levelset label missing: {path}')
    path.write_text(text.replace(old_text, new_text, 1), encoding='utf-8')

# Make the end of Tutorial Island an obvious continuation point. The original
# label "Watch Ending" looks like a credits/ending shortcut and does not tell a
# browser player where the rest of the game lives.
worldmap = Path('data/worldmaps/tutorial.worldmap')
wm = worldmap.read_text(encoding='utf-8')
if wm.count('(name "Watch Ending")') != 1:
    raise SystemExit('tutorial ending story-dot anchor missing')
wm = wm.replace('(name "Watch Ending")', '(name "Continue Journey")', 1)
worldmap.write_text(wm, encoding='utf-8')

# The Tutorial Island ending marks its final story as credits=true. Native
# Pingus then replaces the story with credits/pingus.credits. In the Yandex
# build, send the player directly to the other levelsets/campaigns instead.
p = Path('src/pingus/screens/story_screen.cpp')
s = p.read_text(encoding='utf-8')
include_anchor = '#include "pingus/screens/story_screen.hpp"\n'
if include_anchor not in s:
    raise SystemExit('story screen include anchor missing')
s = s.replace(include_anchor, include_anchor + '#include "pingus/screens/level_menu.hpp"\n', 1)
old = '''      if (m_credits)\n      {\n        ScreenManager::instance()->replace_screen\n          (std::make_shared<Credits>(Pathname("credits/pingus.credits", Pathname::DATA_PATH)));\n      }\n      else\n      {\n        ScreenManager::instance()->pop_screen();\n      }'''
new = '''      if (m_credits)\n      {\n#ifdef __EMSCRIPTEN__\n        // Tutorial complete: continue into the rest of the original levelsets\n        // instead of opening contributor credits or leaving the player unsure.\n        ScreenManager::instance()->replace_screen(std::make_shared<LevelMenu>());\n#else\n        ScreenManager::instance()->replace_screen\n          (std::make_shared<Credits>(Pathname("credits/pingus.credits", Pathname::DATA_PATH)));\n#endif\n      }\n      else\n      {\n        ScreenManager::instance()->pop_screen();\n      }'''
if s.count(old) != 1:
    raise SystemExit('story credits transition anchor missing or duplicated')
s = s.replace(old, new, 1)
p.write_text(s, encoding='utf-8')

# One complete upstream translation is too wide for the original fixed 2007
# LevelMenu row and collides with the right-side statistics. Keep the same
# meaning in a compact Web-only form and add the Web-only continuation label.
po = Path('data/po/ru.po')
text = po.read_text(encoding='utf-8')
pattern = re.compile(
    r'(?m)^(msgid "Merry Christmas and a Happy New Year"\nmsgstr ")[^"]*(")$'
)
text, count = pattern.subn(r'\1Праздничные уровни\2', text, count=1)
if count != 1:
    raise SystemExit('compact Xmas levelset RU translation anchor missing')
if 'msgid "Continue Journey"' not in text:
    text += '\nmsgid "Continue Journey"\nmsgstr "Продолжить путешествие"\n'
po.write_text(text, encoding='utf-8')

print('Web UI: visible author/contact metadata removed; legal files retained')
print('Tutorial completion: ending now continues directly to other levelsets')
print('Web RU layout: long levelset labels compacted for fixed UI')

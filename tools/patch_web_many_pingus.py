from pathlib import Path

# Pingus 0.7.6 tries to compensate a slow rendered frame by running every
# missing fixed simulation step on the next rendered frame. With many active
# pingus in the single-threaded browser target that becomes a feedback loop:
# slow frame -> more catch-up updates -> even slower frame -> still more
# catch-up updates. Desktop keeps the original behavior; Web bounds the amount
# of catch-up work and drops excessive backlog instead of freezing the UI.
p = Path('src/pingus/screens/game_session.cpp')
s = p.read_text(encoding='utf-8')
old = '''    int world_updates = 0;

    while ((world_updates+1)*update_time <= time_passed)
    {
      if (!pause || single_step)
      {
        single_step = false;

        if (fast_forward)
        {
          for (int i = 0; i < globals::fast_forward_time_scale; ++i)
            server->update();
        }
        else
        {
          server->update();
        }
      }

      world_updates++;
    }
    // save how far behind is the world compared to the actual time
    // so that we can account for that while updating in the next frame
    world_delay = time_passed - (world_updates*update_time);
'''
new = '''    int world_updates = 0;

#ifdef __EMSCRIPTEN__
    // Never let a slow browser frame cause an unbounded catch-up spiral.
    // Three 20 ms fixed steps are enough to absorb ordinary jitter. Fast
    // forward already performs four server updates per fixed step, so two
    // outer steps still allow up to eight simulation updates per frame.
    const int max_world_updates = fast_forward ? 2 : 3;
#endif

    while ((world_updates+1)*update_time <= time_passed)
    {
#ifdef __EMSCRIPTEN__
      if (world_updates >= max_world_updates)
        break;
#endif
      if (!pause || single_step)
      {
        single_step = false;

        if (fast_forward)
        {
          for (int i = 0; i < globals::fast_forward_time_scale; ++i)
            server->update();
        }
        else
        {
          server->update();
        }
      }

      world_updates++;
    }
    // save how far behind is the world compared to the actual time
    // so that we can account for that while updating in the next frame
#ifdef __EMSCRIPTEN__
    // If the cap was reached, discard old backlog. The game may briefly run
    // in slow motion on a severely overloaded device, but it immediately
    // recovers instead of locking the browser in a catch-up loop.
    world_delay = time_passed - (world_updates*update_time);
    if (world_delay >= update_time)
      world_delay = update_time - 1;
#else
    world_delay = time_passed - (world_updates*update_time);
#endif
'''
if s.count(old) != 1:
    raise SystemExit('GameSession catch-up patch anchor missing or duplicated')
s = s.replace(old, new, 1)
p.write_text(s, encoding='utf-8')

# Rendering every active pingu even when it is far outside the camera creates
# useless SpriteDrawingRequests, sorting work and SDL blits on large levels.
# Cull only in the Web target and keep a generous margin for animation frames.
p = Path('src/pingus/pingu_holder.cpp')
s = p.read_text(encoding='utf-8')
inc = '#include "pingus/pingu_holder.hpp"\n\n'
if inc not in s:
    raise SystemExit('PinguHolder include anchor missing')
s = s.replace(inc, inc + '#include "engine/display/scene_context.hpp"\n', 1)
old = '''void
PinguHolder::draw (SceneContext& gc)
{
  // Draw all walkers
  for(std::list<Pingu*>::iterator pingu = pingus.begin();
      pingu != pingus.end();
      ++pingu)
  {
    if ((*pingu)->get_action() == ActionName::WALKER)
      (*pingu)->draw (gc);
  }

  // Draw all non-walkers, so that they are easier spotable

  // FIXME: This might be usefull, but looks kind of ugly in the game
  // FIXME: Bridgers where walkers walk behind are an example of
  // FIMME: uglyness. Either we rip this code out again or fix the
  // FIXME: bridger so that it looks higher and better with walkers
  // FIXME: behind him.
  for(std::list<Pingu*>::iterator pingu = pingus.begin();
      pingu != pingus.end();
      ++pingu)
  {
    if ((*pingu)->get_action() != ActionName::WALKER)
      (*pingu)->draw (gc);
  }
}
'''
new = '''void
PinguHolder::draw (SceneContext& gc)
{
#ifdef __EMSCRIPTEN__
  const Rect visible = gc.color().get_world_clip_rect();
  const int margin = 64;
  const auto is_visible = [&](Pingu* pingu) {
    const Vector3f pos = pingu->get_center_pos();
    return pos.x >= visible.left - margin && pos.x <= visible.right + margin &&
           pos.y >= visible.top  - margin && pos.y <= visible.bottom + margin;
  };
#endif

  // Draw all walkers
  for(std::list<Pingu*>::iterator pingu = pingus.begin();
      pingu != pingus.end();
      ++pingu)
  {
#ifdef __EMSCRIPTEN__
    if (!is_visible(*pingu))
      continue;
#endif
    if ((*pingu)->get_action() == ActionName::WALKER)
      (*pingu)->draw (gc);
  }

  // Draw all non-walkers, so that they are easier spotable

  // FIXME: This might be usefull, but looks kind of ugly in the game
  // FIXME: Bridgers where walkers walk behind are an example of
  // FIMME: uglyness. Either we rip this code out again or fix the
  // FIXME: bridger so that it looks higher and better with walkers
  // FIXME: behind him.
  for(std::list<Pingu*>::iterator pingu = pingus.begin();
      pingu != pingus.end();
      ++pingu)
  {
#ifdef __EMSCRIPTEN__
    if (!is_visible(*pingu))
      continue;
#endif
    if ((*pingu)->get_action() != ActionName::WALKER)
      (*pingu)->draw (gc);
  }
}
'''
if s.count(old) != 1:
    raise SystemExit('PinguHolder draw patch anchor missing or duplicated')
s = s.replace(old, new, 1)
p.write_text(s, encoding='utf-8')

# A minimap line is a separate heap-allocated DrawingRequest. Drawing hundreds
# of identical one-pixel markers is not useful at 175x100 resolution. Preserve
# every marker for normal levels and sample the swarm only above 50 active
# pingus, keeping at most ~50 representative markers in Web.
p = Path('src/pingus/components/smallmap.cpp')
s = p.read_text(encoding='utf-8')
old = '''  // Draw Pingus
  PinguHolder* pingus = world->get_pingus();
  for(PinguIter i = pingus->begin(); i != pingus->end(); ++i)
  {
    int x = static_cast<int>(static_cast<float>(rect.left) + ((*i)->get_x() * static_cast<float>(rect.get_width()) 
                                                              / static_cast<float>(world->get_width())));
    int y = static_cast<int>(static_cast<float>(rect.top)  + ((*i)->get_y() * static_cast<float>(rect.get_height()) 
                                                              / static_cast<float>(world->get_height())));

    gc.draw_line(Vector2i(x, y), Vector2i(x, y-2), Color(255, 255, 0));
  }
'''
new = '''  // Draw Pingus
  PinguHolder* pingus = world->get_pingus();
#ifdef __EMSCRIPTEN__
  const unsigned int marker_stride = pingus->size() > 50
    ? static_cast<unsigned int>((pingus->size() + 49) / 50)
    : 1u;
  unsigned int marker_index = 0;
#endif
  for(PinguIter i = pingus->begin(); i != pingus->end(); ++i)
  {
#ifdef __EMSCRIPTEN__
    if ((marker_index++ % marker_stride) != 0)
      continue;
#endif
    int x = static_cast<int>(static_cast<float>(rect.left) + ((*i)->get_x() * static_cast<float>(rect.get_width()) 
                                                              / static_cast<float>(world->get_width())));
    int y = static_cast<int>(static_cast<float>(rect.top)  + ((*i)->get_y() * static_cast<float>(rect.get_height()) 
                                                              / static_cast<float>(world->get_height())));

    gc.draw_line(Vector2i(x, y), Vector2i(x, y-2), Color(255, 255, 0));
  }
'''
if s.count(old) != 1:
    raise SystemExit('SmallMap pingu marker patch anchor missing or duplicated')
s = s.replace(old, new, 1)
p.write_text(s, encoding='utf-8')

# The browser target uses a software SDL framebuffer. 30 rendered frames per
# second substantially lowers full-frame canvas work while the fixed 20 ms
# simulation ticks remain unchanged.
p = Path('src/pingus/pingus_main.cpp')
s = p.read_text(encoding='utf-8')
old = '    globals::desired_fps = 40.0f;\n'
new = '    globals::desired_fps = 30.0f;\n'
if s.count(old) != 1:
    raise SystemExit('Web desired FPS anchor missing or duplicated')
s = s.replace(old, new, 1)
p.write_text(s, encoding='utf-8')

print('Web many-pingu performance: bounded catch-up, offscreen culling, minimap sampling, 30 fps rendering')

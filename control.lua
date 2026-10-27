-- Lily's Thermal Beam turret -- the beam itself.
--
-- The turret prototype is an ordinary ammo turret with a beam attack, so the engine
-- still does the aiming, the rotating head, the ammo feed and the beam's own cold
-- contact hit. Everything that makes a melta a melta lives here:
--
--   * charge     -- intensity ramps up while the turret keeps firing, decays when it stops
--   * pierce     -- one pulse cuts every body on the beam axis, each body behind the
--                   first taking pierce_falloff of the last one's damage
--   * fuel       -- the engine drinks melta-fuel from the pipe; a hot beam drinks more
--   * visuals    -- a sharp line core inside a wide additive glow, a muzzle blast, an
--                   impact flare and a clean fade-out (see the visuals section)
--
-- Numbers live in constants.lua.

local C = require("constants")

local TURRET = C.turret

-- fuel gate: any fluid in constants.lua that this install actually has. Uses the
-- prototypes table so a fuel belonging to an absent mod is simply skipped.
-- fuels listed in constants.lua that this install actually has; cache once, the
-- runtime prototype table is `prototypes.fluid` (there is no game.fluid_prototypes)
local available_fuels
local function fuels_here()
  if not available_fuels then
    available_fuels = {}
    for _, fuel in ipairs(C.fuels) do
      if prototypes.fluid[fuel.name] then
        available_fuels[#available_fuels + 1] = fuel
      end
    end
  end
  return available_fuels
end

local function has_fuel(turret)
  for _, fuel in ipairs(fuels_here()) do
    if turret.get_fluid_count(fuel.name) > 0 then
      return true
    end
  end
  return false
end

-- Which fuel is burning decides both how hard the beam hits and what colour it is.
-- The engine's own fluids[].damage_modifier only scales its invisible 1-damage stream,
-- so the real beam damage and colour are applied here. Highest modifier present wins.
local DEFAULT_PROFILE =
{
  damage_modifier = 1,
  core = {r = 1.00, g = 0.88, b = 0.60},
  sheath = {r = 1.00, g = 0.42, b = 0.10}
}

-- WHICH fuel is burning -- not which fuel is in the pipe.
--
-- A fluid turret holds TWO fluid boxes (measured on 2.1.23, docs/verification/
-- fluid-buffer.md): the piped one that `fluid_box` describes, and the internal buffer the
-- turret actually shoots from (`fluid_buffer_size`). `get_fluid_count`/`get_fluid_contents`
-- report the SUM of both, so "the fuel present with the highest damage_modifier" can pick
-- the fluid that is only waiting in the pipe while the buffer still holds the previous
-- one -- which is exactly the reported symptom: the lance coloured like the pipe, not like
-- the buffer. Nothing in the API reads a single box, so the turret watches its own
-- consumption instead: `sample_fuel` runs once per pulse and remembers the fluid whose
-- amount FELL, i.e. the one the shot just burnt. `fuel_profile` prefers that fluid, and
-- only falls back to "the most plentiful one" when nothing has burnt yet.
local function sample_fuel(turret, state)
  local current = state.fuel_now or {}
  local previous = state.fuel_prev or {}
  local burnt, burnt_drop = nil, 0
  local biggest, biggest_amount = nil, 0
  for _, fuel in ipairs(fuels_here()) do
    local amount = turret.get_fluid_count(fuel.name)
    current[fuel.name] = amount
    if amount > 0 then
      if amount > biggest_amount then
        biggest, biggest_amount = fuel, amount
      end
      local drop = (previous[fuel.name] or 0) - amount
      if drop > burnt_drop then
        burnt, burnt_drop = fuel, drop
      end
    end
  end
  state.fuel_prev, state.fuel_now = current, previous
  local chosen = burnt or biggest
  state.burn_fuel = chosen and chosen.name or nil
end

-- The answer cannot change inside one tick, and this is called from the damage path, the
-- draw path, the mouth glow, the wind-up and the gauge, so it is cached per tick: four
-- engine reads per turret per tick instead of four per call.
local function fuel_profile(turret, state)
  local now = game.tick
  if state and state.profile_tick == now then
    return state.profile_cached
  end
  local burn = state and state.burn_fuel
  local best, best_amount = nil, 0
  for _, fuel in ipairs(fuels_here()) do
    local amount = turret.get_fluid_count(fuel.name)
    if amount > 0 then
      if burn == fuel.name then
        return fuel
      end
      if amount > best_amount then
        best, best_amount = fuel, amount
      end
    end
  end
  local chosen = best or DEFAULT_PROFILE
  if state then
    state.profile_tick = now
    state.profile_cached = chosen
  end
  return chosen
end

-- one entry per placed melta turret, keyed by unit_number:
--   entity, charge (0..1), pulse_at, debt, objs, beam, beam_end, last_muzzle
local turrets
-- beams whose turret is already gone: frozen geometry + their own objects, drawn
-- until they have faded out (see retire_beam / fade_beam)
local fades

--------------------------------------------------------------- research -----

-- What research gives the melta, and why the script has to read it itself.
--
-- A turret's damage normally scales because the ENGINE multiplies its ammo's
-- damage, and its rate because the engine multiplies its cooldown. Neither can
-- happen here: the melta's damage is dealt by this file (`victim.damage`) and
-- its pulse clock is this file's `state.pulse_at`, so both are invisible to the
-- engine's modifiers. Left alone, the turret is the only one in the game that
-- stops growing the moment it is built -- it sat at 240/420 dps while a gun
-- turret went 240 -> 1320.
--
-- So the two dips a gun turret gets are read here and applied in the same
-- places the engine would have applied them:
--
--   * damage -- summed `ammo-damage` modifiers for C.research_damage_ammo
--     (the flamethrower's `refined-flammables` line), applied ONCE per pulse
--     and then compounded by C.research_damage_exponent. Each researched
--     technology contributes its modifier exactly once: the `level` field on
--     `refined-flammables-2` is the tier number (2), not a stacking count, and
--     multiplying by it triple-counts the ladder (measured -- it is what made
--     the first pass of this change reach +240 % instead of +120 %).
--   * rate -- summed `gun-speed` modifiers for C.research_rate_ammo. The melta
--     owns its ammo category, and data-updates.lua copies each
--     `weapon-shooting-speed` level's bullet modifier onto that category, so
--     the same research the gun turret line uses also shows up in the tech
--     tooltip as "melta firing speed". The pulse interval is divided by the
--     bonus, i.e. the turret really fires faster (and drinks fluid faster).
--     Measured on 2.1.23, a gun turret's rate is exactly this: cooldown 6 at
--     +0 %, 5 at +10 %, 4 at +50 %, 3 at +80 % -- one application, no more.
--
-- Both are cached per force and thrown away when research finishes: a scan of
-- ~200 technologies per pulse per turret would be the single most expensive
-- thing in the mod.

-- The bonus is read from the ENGINE, not summed by hand.
--
-- Up to 0.6.0 this walked `force.technologies` and added each technology's `ammo-damage`
-- modifier ONCE. That is wrong for the infinite tier: `refined-flammables-7` is
-- `max_level = "infinite"` and pays +0.2 PER LEVEL, so ten extra levels of fire damage
-- contributed 0.2 instead of 2.0 -- the turret looked researched and fought like it was
-- not. Measured in docs/verification/research-scaling.md.
--
-- `LuaForce.get_ammo_damage_modifier`, `get_gun_speed_modifier` and
-- `get_turret_attack_modifier` return exactly what the engine would apply to a turret of
-- its own, infinite levels included, so they are the only source now. One call each, and
-- only when the cache is cold (research finishing throws the cache away).
--
-- ONE dip, not two. The vanilla fire line gives the flamethrower an `ammo-damage` AND a
-- `turret-attack` effect with the same modifiers -- that is where a turret's double dip
-- comes from -- and data-updates now mirrors the `turret-attack` half onto this turret so
-- that it appears in the technology at all. Taking the LARGER of the two counts every
-- researched level exactly once; squaring it as well is what
-- `C.research_damage_exponent` is for, so that stays the single dial.
local DAMAGE_LIST = C.research_damage_ammo or {}
local RATE_LIST = C.research_rate_ammo or {}

-- best value the engine reports for any key in `list`, guarded: a modded force without
-- the category (or an older API) must not kill the tick handler.
--
-- The getters take exactly ONE argument -- `force.get_ammo_damage_modifier("flamethrower")`,
-- not `(force, "flamethrower")`; passing self as well is an argument-count error, and a
-- guarded read that swallows that error returns 0 and silently turns research off
-- entirely. Measured both call forms in docs/verification/research-scaling.md.
local function best_modifier(force, method, list)
  local getter = force[method]
  if not getter then
    return 0
  end
  local best = 0
  for _, key in ipairs(list) do
    local ok, value = pcall(getter, key)
    if ok and type(value) == "number" and value > best then
      best = value
    end
  end
  return best
end

-- The bonus is cached per force for a second, not forever: research is not the only thing
-- that can move these numbers (another mod's script can set a force modifier, which raises
-- no event this mod can hear -- on_technology_effects_reset cannot even be raised from
-- script), so the cache expires on its own instead of waiting for an event that may never
-- come. Four engine reads per force per second is free next to a per-pulse scan of every
-- technology.
local BONUS_REFRESH_TICKS = 60

local function research_bonus(force)
  storage.bonus_cache = storage.bonus_cache or {}
  local cached = storage.bonus_cache[force.index]
  local now = game.tick
  if cached and now < cached.until_tick then
    return cached
  end

  local ammo = best_modifier(force, "get_ammo_damage_modifier", DAMAGE_LIST)
  local turret_attack = best_modifier(force, "get_turret_attack_modifier", {C.turret})
  local damage = ammo > turret_attack and ammo or turret_attack
  local rate = best_modifier(force, "get_gun_speed_modifier", RATE_LIST)

  cached =
  {
    damage = damage * (C.research_damage_scale or 0),
    rate = (C.research_rate and rate) or 0,
    until_tick = now + BONUS_REFRESH_TICKS
  }
  storage.bonus_cache[force.index] = cached
  return cached
end

local function damage_multiplier(turret)
  local bonus = research_bonus(turret.force).damage
  if bonus < 0 then
    bonus = 0
  end
  local exponent = C.research_damage_exponent or 1
  if exponent ~= 1 then
    return (1 + bonus) ^ exponent
  end
  return 1 + bonus
end

-- ticks between pulses after the firing-speed line, floored at C.cooldown_min
local function pulse_interval(turret)
  local rate = research_bonus(turret.force).rate
  if rate < 0 then
    rate = 0
  end
  local interval = C.cooldown / (1 + rate)
  local floor = C.cooldown_min or 1
  if interval < floor then
    interval = floor
  end
  return interval
end

----------------------------------------------------------- flat armour -----

-- "Ignore flat armour, respect percentage resistance", done where the damage is
-- dealt because the engine offers no such flag: it always resolves a hit as
-- `max(0, amount - decrease) * (1 - percent / 100)`. Handing it
-- `amount + decrease` for that damage type cancels the subtraction exactly and
-- leaves the percentage doing its job. Only POSITIVE `decrease` is compensated:
-- a negative one means "takes extra damage", and adding it would turn that bonus
-- into a penalty. Vanilla big/huge asteroids carry POSITIVE physical flat armour
-- (2000/3000), so their slice is compensated like any other armoured body.
--
-- The table is built per prototype (every biter of a tier shares one) and cached
-- by name; entity prototypes do not change during a game.
local flat_armor_cache

local function flat_armor(victim, damage_type)
  local prototype = victim.prototype
  if not prototype then
    return 0
  end
  flat_armor_cache = flat_armor_cache or {}
  local by_type = flat_armor_cache[prototype.name]
  if not by_type then
    by_type = {}
    local resistances = prototype.resistances
    if resistances then
      for key, resistance in pairs(resistances) do
        if type(resistance) == "table" then
          -- dictionary form is keyed by damage type; the array form carries
          -- `type` on each entry. Accept both rather than depend on which one
          -- this engine build hands back.
          local name = resistance.type
          if type(name) ~= "string" then
            name = type(key) == "string" and key or nil
          end
          if name then
            local decrease = resistance.decrease or 0
            by_type[name] = decrease > 0 and decrease or 0
          end
        end
      end
    end
    flat_armor_cache[prototype.name] = by_type
  end
  return by_type[damage_type] or 0
end

---------------------------------------------------------------- helpers ------

local function normalize(dx, dy)
  local length = math.sqrt(dx * dx + dy * dy)
  if length < 0.0001 then
    return 0, 0, 0
  end
  return dx / length, dy / length, length
end

local function lerp(from, to, ratio)
  return from + (to - from) * ratio
end

local function beam_color(style, charge, profile)
  local base = (style.tier == "core") and profile.core or profile.sheath
  return
  {
    r = base.r,
    g = base.g,
    b = base.b,
    a = lerp(style.alpha_cold, style.alpha_hot, charge)
  }
end

----------------------------------------------------------- quality range -----

-- Range scales with quality through the engine itself: every quality prototype has a
-- `range_multiplier` (normal 1.0 ... legendary 1.5 on 2.1.23) and the engine applies it
-- to a turret's `attack_parameters.range`, so acquisition AND firing already reach
-- further for a better melta -- measured on 2.1.23: with the base at 12 a legendary
-- turret acquired and burned fluid at 19 tiles while a normal one stopped at 13.
-- What the engine does not do is clamp it, and the *drawn beam* has to match the real
-- reach or the lance is a lie (a 12-tile line while the turret burns a target at 19).
-- So: read the same multiplier, multiply the base, clamp to C.range_max (vanilla
-- legendary, 16 * 1.5 = 24). Guarded rather than assumed -- `quality` answers "normal"
-- on entities that do not support it, and an older API could lack range_multiplier;
-- a nil there would otherwise kill the whole tick handler.
local function range_for(entity)
  local quality = entity and entity.valid and entity.quality or nil
  local multiplier = quality and quality.range_multiplier or 1
  if type(multiplier) ~= "number" then
    multiplier = 1
  end
  local range = C.range * multiplier
  if range > C.range_max then
    range = C.range_max
  end
  return range
end

-- Nearest live enemy military target inside `range`. Used when the engine hands this
-- turret a target it cannot actually reach: a neighbour's `call_for_help_radius` (40
-- tiles on the melta) ignores range, so a turret can end up aiming at a biter 19 tiles
-- out with a 16-tile beam. Replacing that with the nearest reachable body keeps the
-- turret useful. "Inside" follows the engine's own rule: it measures to the target's
-- bounding box, not its centre (a biter spawner 17 tiles away with a 4-tile body is in
-- range of a 16-tile turret), so this does too -- otherwise the turret would aim at and
-- burn fluid on a body it never damages.
local function target_half_extent(target)
  local box = target.bounding_box
  if not box then
    return 0
  end
  return math.max(box.right_bottom.x - box.left_top.x, box.right_bottom.y - box.left_top.y) * 0.5
end

local function in_reach(turret, target, range)
  if not target or not target.valid then
    return false
  end
  local dx = target.position.x - turret.position.x
  local dy = target.position.y - turret.position.y
  return math.sqrt(dx * dx + dy * dy) <= range + target_half_extent(target)
end

local function nearest_enemy(turret, range)
  local best, best_distance = nil, nil
  local candidates = turret.surface.find_entities_filtered
  {
    position = turret.position,
    radius = range + 2,
    is_military_target = true
  }
  for _, candidate in pairs(candidates) do
    if candidate.valid and candidate ~= turret and candidate.health and candidate.health > 0
       and candidate.force and turret.force.is_enemy(candidate.force) then
      local vx = candidate.position.x - turret.position.x
      local vy = candidate.position.y - turret.position.y
      local distance = vx * vx + vy * vy
      if in_reach(turret, candidate, range)
         and (not best_distance or distance < best_distance) then
        best, best_distance = candidate, distance
      end
    end
  end
  return best
end

---------------------------------------------------------------- aiming --------

-- The head is turned by the engine at the prototype's `rotation_speed` and it only
-- fires once the head is on the target; the script has to agree with that or the beam
-- appears while the barrel is still swinging. `LuaEntity::orientation` is the weapon's
-- own smooth orientation (0 = north, 0.25 = east), so the script can ask "is the
-- barrel pointing at the target yet" instead of assuming it.
local TILT = math.rad(C.camera_tilt_deg)
local COS_TILT = math.cos(TILT)              -- 0.629: ground foreshortening on screen
local MUZZLE_LIFT = math.sin(TILT) * C.muzzle_height  -- 0.561: a raised point sits this
                                             -- much further "up" (north) the screen
-- Lua 5.2 has math.atan2, 5.3 folds it into math.atan(y, x)
local atan2 = math.atan2 or math.atan

-- Where the beam starts, in world tiles. The muzzle is 1.512 tiles along the barrel
-- and 0.72 tiles up in the air; because the head sprite is a pitched-camera render,
-- the ground point that *looks* like the mouth is not position + forward * length:
--   * the forward reach is foreshortened by cos(tilt) on the screen's vertical axis
--     (unchanged on the horizontal one), and
--   * the raised muzzle appears sin(tilt) * height further up the screen, i.e. north.
-- Verified against Blender's own camera projection for all 64 directions
-- (graphics/_blender/muzzle_marker.py: agreement < 0.001 tiles).
-- The mouth also moves with the ART: both sprites are drawn C.sprite_shift further down
-- the screen (the turret stands on its own tile, see constants.lua), and the beam has to
-- leave the mouth the player can see, not the one the model would have had.
local function muzzle_point(turret, ux, uy)
  return
  {
    x = turret.position.x + C.muzzle_forward * ux + C.sprite_shift[1],
    y = turret.position.y + COS_TILT * C.muzzle_forward * uy - MUZZLE_LIFT + C.sprite_shift[2]
  }
end

-- facing of the head as a world unit vector (orientation 0 = north, clockwise)
local function facing(orientation)
  local turn = orientation * 2 * math.pi
  return math.sin(turn), -math.cos(turn)
end

-- signed angle from the head's facing to the target, in turns (-0.5 .. 0.5)
local function aim_error(orientation, dx, dy)
  local wanted = atan2(dx, -dy) / (2 * math.pi)
  return (orientation - wanted + 0.5) % 1 - 0.5
end

local function destroy_object(id)
  if not id then
    return
  end
  local object = rendering.get_object_by_id(id)
  if object and object.valid then
    object.destroy()
  end
end

-- Which fuel colour a layer uses. `pulse` (which colours its flares from the same
-- profile) is defined above the visuals section, so this lives here with the other
-- helpers rather than next to the drawing code it serves.
local TIER = {r = 0, g = 0, b = 0}

local function tier_color(tier, charge, profile)
  local base = (tier == "core") and profile.core or profile.sheath
  TIER.r, TIER.g, TIER.b = base.r, base.g, base.b
  return TIER
end

-- Every beam owns exactly this set of render objects. Built once, here, so destroying
-- a beam never has to build a list.
local BEAM_KEYS = {"cone", "muzzle", "impact", "tip", "spray"}
for index = 1, #C.beam_glow do
  BEAM_KEYS[#BEAM_KEYS + 1] = "glow" .. index
end
for index = 1, #C.beam_core do
  BEAM_KEYS[#BEAM_KEYS + 1] = "core" .. index
end
for index = 1, C.beam_tongues do
  BEAM_KEYS[#BEAM_KEYS + 1] = "tongue" .. index
end

-- Frees every object a beam owns. Keyed off the object table the beam carries, so a
-- beam that has outlived its turret (retire_beam) still frees its own objects and
-- cannot leave a stuck lance behind.
local function destroy_beam(beam)
  local objs = beam and beam.objs
  if not objs then
    return
  end
  for index = 1, #BEAM_KEYS do
    local key = BEAM_KEYS[index]
    destroy_object(objs[key])
    objs[key] = nil
  end
end

-- The heat at the mouth: the charge-up glow and the emitter bleeding off after a shot.
-- The hull's gauge lights are freed with it (they are the same kind of object: created
-- when the turret has something to say, gone when it has cooled down).
local function destroy_orb(state)
  local objs = state.objs
  if not objs then
    return
  end
  destroy_object(objs.orb_core)
  destroy_object(objs.orb_halo)
  objs.orb_core, objs.orb_halo = nil, nil
  for index = 1, C.spin_leds do
    local key = "led" .. index
    destroy_object(objs[key])
    objs[key] = nil
  end
end

local function clear_beam(state)
  destroy_beam(state.beam)
  state.beam = nil
end

local function clear_state(state)
  clear_beam(state)
  destroy_orb(state)
  state.beam_end = nil
end

local function state_for(entity)
  local state = turrets[entity.unit_number]
  if not state then
    state =
    {
      entity = entity,
      charge = 0,
      pulse_at = 0,
      debt = 0
    }
    turrets[entity.unit_number] = state
  end
  state.entity = entity
  -- refreshed here (build, and every reconcile) so a mod update that changes the
  -- quality ladder is picked up without touching the entity
  state.range = range_for(entity)
  return state
end

----------------------------------------------------------------- fuel --------

-- The engine already drinks fluid per shot. This is the surcharge that makes
-- holding a white-hot beam cost more than tapping it.
local function burn_surcharge(turret, state)
  state.debt = state.debt + C.extra_fluid_per_pulse_hot * state.charge
  if state.debt < 1 then
    return
  end
  -- positional API, and the order is (index, amount) -- the docs list them by `order`,
  -- not by position: remove_fluid(1, amount)
  local removed = turret.remove_fluid(1, state.debt)
  if removed and removed.amount then
    state.debt = state.debt - removed.amount
  end
  -- never bank more than one unit: a dry turret would otherwise owe fuel for
  -- minutes after the wave is dead
  if state.debt > 1 then
    state.debt = 1
  end
  if state.debt < 0 then
    state.debt = 0
  end
end

---------------------------------------------------------------- effects -----

-- Short-lived pops (auto-freed by the engine) so the beam has something to *do* at
-- both ends: a flash at the muzzle and a burn mark wherever a body is cut.
local function pop(surface, position, base, radius, alpha, layer)
  rendering.draw_sprite
  {
    sprite = C.beam_texture.flare.sprite,
    surface = surface,
    target = position,
    x_scale = radius * 2 / C.beam_texture.flare.tiles[1],
    y_scale = radius * 2 / C.beam_texture.flare.tiles[2],
    tint = {r = base.r, g = base.g, b = base.b, a = alpha},
    render_layer = layer or "projectile",
    time_to_live = C.beam_pop_ticks
  }
end

-------------------------------------------------------------- corridor -------

-- The beam is continuous, the damage clock is not.
--
-- Up to 0.6.1 the corridor was tested only on the tick a pulse happened, so a turret
-- sweeping across a swarm cut a visible arc through bodies that never took anything: a
-- biter could sit inside the drawn beam for seven of every eight ticks and be untouched if
-- no pulse landed on it. (Reported playtest: "some of them get touched by beam visually,
-- yet take no damage".) The fix is to separate the two clocks that were fused:
--
--   * DAMAGE runs every tick, at `pulse damage / pulse interval`, so what the beam visibly
--     touches for one tick is burnt for one tick's worth. Sweeping spreads one pulse over
--     everything the arc crossed instead of picking whoever happened to be on the axis at
--     the pulse tick;
--   * the PULSE clock keeps its job: the thump (muzzle flash, cut marks, impact pop), the
--     fuel surcharge and the "what is burning" sample all still happen 7.5x a second, so
--     the look and the balance of a locked-on beam are unchanged.
--
-- Cost discipline: the engine query is the expensive part, so the body list is only rebuilt
-- when the beam's GEOMETRY moved (a locked-on turret keeps it for a whole pulse window, i.e.
-- one query per 8 ticks, exactly as before) or every `C.hit_refresh_ticks` so bodies that
-- walked in are still picked up. A turret mid-sweep rebuilds it every tick -- which is
-- precisely when being right matters.
--
-- Per tick the cached bodies are re-tested with cheap maths, so a body that walked out of
-- the beam stops burning immediately instead of waiting for the next refresh.

-- where a body sits relative to the beam axis: distance along it, and across it
local function axis_of(position, muzzle, dx, dy)
  local vx = position.x - muzzle.x
  local vy = position.y - muzzle.y
  local along = vx * dx + vy * dy
  local across = math.sqrt((vx - dx * along) ^ 2 + (vy - dy * along) ^ 2)
  return along, across
end

local function body_radius(entity)
  local box = entity.bounding_box
  return math.max(box.right_bottom.x - box.left_top.x, box.right_bottom.y - box.left_top.y) * 0.5
end

local function corridor_clear(state)
  local hits = state.hits
  if hits then
    for index = 1, (state.hit_count or 0) do
      hits[index].entity = nil
      hits[index].along = 0
      hits[index].radius = 0
    end
  end
  state.hit_count = 0
  state.hit_tick = nil
end

local function corridor_stale(state, muzzle, dx, dy, reach, tick)
  local last = state.hit_tick
  if not last then
    return true
  end
  if tick - last >= C.hit_refresh_ticks then
    return true
  end
  -- ~0.1 deg of aim change, or a muzzle that moved by more than a fifth of a tile
  return math.abs(dx - state.hit_ax) > 0.002
      or math.abs(dy - state.hit_ay) > 0.002
      or math.abs(reach - state.hit_reach) > 0.05
      or math.abs(muzzle.x - state.hit_mx) > 0.2
      or math.abs(muzzle.y - state.hit_my) > 0.2
end

-- Rebuild the list of enemies whose skin crosses the beam axis, nearest first.
local function corridor_refresh(turret, state, muzzle, dx, dy, reach, tick)
  local hits = state.hits
  if not hits then
    hits = {}
    state.hits = hits
  end
  local force = turret.force
  local far_x = muzzle.x + dx * reach
  local far_y = muzzle.y + dy * reach
  local pad = 1.5
  local candidates = turret.surface.find_entities_filtered
  {
    area =
    {
      left_top = {math.min(muzzle.x, far_x) - pad, math.min(muzzle.y, far_y) - pad},
      right_bottom = {math.max(muzzle.x, far_x) + pad, math.max(muzzle.y, far_y) + pad}
    },
    is_military_target = true
  }

  local count = 0
  for _, candidate in pairs(candidates) do
    if candidate.valid and candidate ~= turret and candidate.force and force.is_enemy(candidate.force) then
      local along, across = axis_of(candidate.position, muzzle, dx, dy)
      local radius = body_radius(candidate)
      -- `along <= reach + radius`: a body whose *centre* is a fraction of a tile past the
      -- end of the corridor still has its skin inside it, and that is exactly how far the
      -- engine's own range test reaches (it measures to the bounding box). Without the
      -- radius the turret would aim at and burn fluid on a spawner 17 tiles out with a
      -- 16-tile beam and never hurt it.
      if along > 0 and along <= reach + radius and across <= C.hit_half_width + radius then
        count = count + 1
        local hit = hits[count]
        if not hit then
          hit = {}
          hits[count] = hit
        end
        hit.entity = candidate
        hit.along = along
        -- the radius is a prototype property, but `bounding_box` builds two tables every
        -- time it is read: keep it, because the per-tick path needs it and cannot afford it
        hit.radius = radius
      end
    end
  end
  state.hit_count = count
  state.hit_tick = tick
  state.hit_ax, state.hit_ay, state.hit_reach = dx, dy, reach
  state.hit_mx, state.hit_my = muzzle.x, muzzle.y

  -- Near-to-far, so a falloff ladder can put the first body in the line at full damage.
  -- With C.pierce_falloff = 1 (the default since damage went continuous) the order means
  -- nothing, so the sort is skipped entirely -- it is the only O(n^2) step in this path and
  -- it runs on every refresh of a sweeping beam.
  if (C.pierce_falloff or 1) >= 1 then
    return count
  end
  for index = 2, count do
    local moving = hits[index]
    local at = index - 1
    while at >= 1 and hits[at].along > moving.along do
      hits[at + 1] = hits[at]
      at = at - 1
    end
    hits[at + 1] = moving
  end
  return count
end

----------------------------------------------------------------- damage ------

-- One tick of burning. `share` is 1/interval, so a body that stays on the axis for a whole
-- pulse interval takes exactly one pulse's damage, and a body the beam only crosses for a
-- tick or two takes that fraction of it.
local function burn_tick(turret, state, muzzle, dx, dy, reach, tick)
  if corridor_stale(state, muzzle, dx, dy, reach, tick) then
    corridor_refresh(turret, state, muzzle, dx, dy, reach, tick)
  end
  local hits, count = state.hits, state.hit_count or 0
  if count == 0 then
    return nil, nil
  end

  local force = turret.force
  local profile = fuel_profile(turret, state)
  local interval = pulse_interval(turret)
  local damage = (C.damage_cold + (C.damage_hot - C.damage_cold) * state.charge)
                 * profile.damage_modifier * damage_multiplier(turret) / interval

  local falloff = C.pierce_falloff or 1
  -- ONE engine call per body per tick, not two. The fire and physical halves of a tick are
  -- applied on alternating ticks at double the amount: every resistance in the game is
  -- linear in the amount ((x + flat) * (1 - percent)), so over any two-tick window the body
  -- takes exactly what two calls per tick would have given it, and the loop costs half the
  -- engine calls. Measured with 20 turrets firing: docs/verification/sweep-damage.md.
  local fire_tick = (tick % 2) == 0
  local nearest, nearest_entity, nearest_along
  local rank = 0
  for index = 1, count do
    local hit = hits[index]
    local victim = hit.entity
    if victim and victim.valid and victim.health and victim.health > 0 then
      local along, across = axis_of(victim.position, muzzle, dx, dy)
      local radius = hit.radius or 0
      if along > 0 and along <= reach + radius and across <= C.hit_half_width + radius then
        local dealt = damage * 2   -- two ticks' worth, because each type lands every other tick
        if falloff ~= 1 then
          rank = rank + 1
          dealt = dealt * falloff ^ (rank - 1)
        end
        if nearest_along == nil or along < nearest_along then
          nearest, nearest_entity, nearest_along = victim.position, victim, along
        end
        -- Fire is what a melta is; the physical share is the mass of the stream hitting the
        -- body. `damage()` takes one type per call (positional: amount, force, type, cause),
        -- and the split is taken out of `dealt`, so balance depends only on the total -- a
        -- 100 % fire-resistant target still eats C.physical_share of the damage.
        --
        -- Flat armour is compensated out of the call (C.pierce_flat_armor): the engine
        -- subtracts `resistances[type].decrease` before the percentage, which is what eats a
        -- short-range burst weapon alive against armoured targets, so the hit is handed
        -- exactly that much extra. Percentage resistance is NOT touched.
        local amount, damage_type
        if fire_tick then
          amount, damage_type = dealt * (1 - C.physical_share), C.damage_type
        else
          amount, damage_type = dealt * C.physical_share, C.damage_type_hit
        end
        if C.pierce_flat_armor then
          amount = amount + flat_armor(victim, damage_type)
        end
        victim.damage(amount, force, damage_type, turret)
        -- Asteroids are 100 % fire resistant and their big/huge tiers subtract 2000/3000
        -- from every physical hit -- which the bypass above cancels, so a rock takes its
        -- 10 % percentage cut of the 15 % slice and nothing more. Rocks get an extra hit in
        -- `explosion`, the ladder the vanilla asteroid set is balanced around, sized off the
        -- same damage, on the same every-other-tick cadence.
        if victim.valid and victim.health and victim.health > 0 and victim.type == "asteroid" then
          victim.damage(dealt * C.asteroid_damage_multiplier, force, C.asteroid_damage_type, turret)
        end
        hit.along = along
      else
        -- walked out of the beam between refreshes: stop burning it now, not at the refresh
        hit.entity = nil
      end
    else
      hit.entity = nil
    end
  end
  return nearest, nearest_entity
end

----------------------------------------------------------------- pulse -------

-- The thump: cut marks on every body on the axis, the muzzle flash, the fuel surcharge and
-- the per-shot fuel sample. Damage no longer happens here (see burn_tick) -- this is the
-- 7.5 Hz clock that makes the beam feel like it has a pressure behind it.
local function pulse(turret, state, muzzle, dx, dy, reach)
  -- once per shot is the natural sampling rate for "what is burning": the engine has just
  -- taken its fluid, and a shot is 7.5/s, so this costs four engine reads per shot.
  sample_fuel(turret, state)
  local profile = fuel_profile(turret, state)

  local hits, count = state.hits, state.hit_count or 0
  local stop = {x = muzzle.x + dx * reach, y = muzzle.y + dy * reach}
  for index = 1, count do
    local hit = hits[index]
    local victim = hit.entity
    if victim and victim.valid and victim.health and victim.health > 0 then
      pop(turret.surface, victim.position, tier_color("sheath", state.charge, profile),
        0.38 + 0.42 * state.charge, 0.85, "higher-object-above")
      stop = victim.position
    end
  end
  if C.debug then
    log(string.format("melta pulse unit=%s charge=%.2f interval=%.2f bodies=%d fuel=%d",
      tostring(turret.unit_number), state.charge, pulse_interval(turret), count,
      turret.get_fluid_count()))
  end

  -- muzzle flash: forward of the barrel so it does not sit inside the sprite
  local flash = {x = muzzle.x + dx * 0.45, y = muzzle.y + dy * 0.45}
  pop(turret.surface, flash, tier_color("sheath", state.charge, profile),
    0.70 + 0.80 * state.charge, 0.55)
  pop(turret.surface, flash, tier_color("core", state.charge, profile),
    0.30 + 0.35 * state.charge, 0.95)

  burn_surcharge(turret, state)
  return stop
end

---------------------------------------------------------------- visuals ------

-- The lance, outside in:
--
--   * a CORE of two soft sprites (graphics/beam/generate.py: beam-core). It used to be
--     two `draw_line` quads, and that was three problems in one: `draw_line` has no
--     `render_layer` field, so the core sat on a fixed engine layer while every other
--     layer obeyed ours (with a smog mod, the core drew in front of the smoke and the
--     rest of the lance behind it); a quad has a hard edge at every zoom, so it read as
--     a graph line; and its two ends were flat cuts. The sprite is soft across, tapers
--     to nothing at the far end, tints with the fuel and shares one layer with
--     everything else;
--   * a wide, soft GLOW of three ADDITIVE sprites (prototypes/beam.lua, textures from
--     graphics/beam/generate.py). `draw_line` cannot do this at all: it paints a flat
--     quad with a hard edge, and -- the actual bug behind the old placeholder look --
--     its `width` is in PIXELS (32 per tile), so the old widest entry of 1.90 was a
--     1.9 px hairline, thinner than the barrel it came out of. Widths in constants.lua
--     are tiles; nothing is handed to the engine in pixels any more, because no layer of
--     the lance is a line;
--   * BOILING TONGUES: soft blobs that jump to a new offset, length and alpha every
--     few ticks, so the sheath never settles into a tidy light bar;
--   * a MUZZLE BURST (flare + blast cone) and an IMPACT FLARE on the nearest body the
--     pulse cut. Both swell for C.beam_pulse_ticks after a pulse, so each shot thumps
--     instead of the whole thing being a constant hum.
--
-- Cost discipline: every object is created once per turret and only mutated afterwards,
-- and all position/colour arguments come from two module-level scratch tables (V, COL)
-- -- so the per-tick draw path allocates nothing. A beam keeps its own geometry and
-- object ids, which is what lets it outlive its turret (see retire_beam / the fade
-- list): nothing can be left drawing after the turret or its target is gone.

local V = {x = 0, y = 0}                    -- scratch position, reused every setter
local COL = {r = 0, g = 0, b = 0, a = 1}    -- scratch colour, reused every setter
local CORE = {r = 1, g = 1, b = 1, a = 1}   -- scratch colour for a whitened core layer

-- One render layer for every object the beam draws (see constants.lua): the core used to
-- be draw_line quads, which have no layer field, and that split is what made a smog mod
-- render the core in front of the smoke and the rest of the lance behind it.
local BEAM_FRONT = C.beam_layer
local ORB_CORE = {r = 1, g = 1, b = 1, a = 1}
local ORB_HALO = {r = 1, g = 1, b = 1, a = 1}

local SPRITE = C.beam_texture

local function objects_of(state)
  state.objs = state.objs or {}
  return state.objs
end

-- The render object in `key`, created on first use. Creation is the only place in the
-- draw path that allocates, and it happens once per turret per key.
local function get_sprite(objs, key, texture, surface)
  local id = objs[key]
  local object = id and rendering.get_object_by_id(id)
  if object and object.valid then
    return object
  end
  object = rendering.draw_sprite
  {
    sprite = SPRITE[texture].sprite,
    surface = surface,
    target = {0, 0},
    x_scale = 1,
    y_scale = 1,
    tint = {r = 1, g = 1, b = 1, a = 1},
    render_layer = BEAM_FRONT,
    visible = false
  }
  objs[key] = object.id
  return object
end

-- Position, rotation, size and tint in one go. `x_scale`/`y_scale` are the *sprite
-- axes*: for a sprite, orientation 0 is north and the image is drawn unrotated, so a
-- beam layer is a tall image whose height runs along the beam and whose width is the
-- beam's thickness.
-- `layer` is optional and defaults to the front layer: the mouth glows want it, the
-- lance picks it per tick (see render_beam).
local function place(object, x, y, orientation, width, height, texture, base, alpha)
  V.x, V.y = x, y
  object.target = V
  object.orientation = orientation
  object.x_scale = width / SPRITE[texture].tiles[1]
  object.y_scale = height / SPRITE[texture].tiles[2]
  COL.r, COL.g, COL.b, COL.a = base.r, base.g, base.b, alpha
  object.color = COL
  object.render_layer = layer or BEAM_FRONT
  object.visible = alpha > 0.004
end

local function place_beam(objs, key, surface, x, y, orientation, width, height, texture, base, alpha)
  local object = get_sprite(objs, key, texture, surface)
  place(object, x, y, orientation, width, height, texture, base, alpha)
  return object
end

-- The beam's own state: the last geometry it drew, the colour inputs, and its object
-- ids. Kept out of the turret state on purpose, so a dead turret's lance can go on
-- being drawn (and then freed) by the fade list.
local function beam_for(state)
  local beam = state.beam
  if beam then
    return beam
  end
  beam =
  {
    objs = objects_of(state),
    from = {x = 0, y = 0},
    to = {x = 0, y = 0},
    ux = 0,
    uy = 1,
    orient = 0,
    length = 0,
    charge = 0,
    profile = DEFAULT_PROFILE,
    surface = nil,
    away = false,
    alpha = 1,
    tick = 0,
    pulse_tick = nil,
    hit = nil,
    rolls = {}
  }
  for index = 1, C.beam_tongues do
    beam.rolls[index] = {start = 0, finish = 0, offset = 0, alpha = 0, width = 0, length = 0}
  end
  state.beam = beam
  return beam
end

-- Draw one whole lance from its frozen geometry. Nothing here reads the turret, the
-- target or the world -- that is what makes it safe to keep drawing after either dies.
local function render_beam(beam, tick)
  local objs, surface = beam.objs, beam.surface
  local length = beam.length
  if not objs or not surface or not length or length < 0.01 then
    return
  end
  local charge, profile, fade = beam.charge, beam.profile, beam.alpha
  local from, to, ux, uy = beam.from, beam.to, beam.ux, beam.uy
  local orient = beam.orient
  local cx, cy = (from.x + to.x) * 0.5, (from.y + to.y) * 0.5
  local px, py = -uy, ux
  local flicker = 1 + C.beam_flicker * math.sin(tick * 0.7) * charge
  -- a dying lance thins as it dims (1 at full strength, 0.55 at the last frame)
  local narrow = 0.55 + 0.45 * fade

  -- 1. the glow: wide and faint outside, tight and bright inside
  for index = 1, #C.beam_glow do
    local style = C.beam_glow[index]
    local base = tier_color(style.tint, charge, profile)
    local width = lerp(style.width_cold, style.width_hot, charge) * flicker * narrow
    local alpha = lerp(style.alpha_cold, style.alpha_hot, charge) * fade
    place_beam(objs, "glow" .. index, surface, cx, cy, orient, width, length,
      style.texture, base, alpha)
  end

  -- 2. the cutting core: two soft sprites, tall like the glow, so it tapers into the far
  --    end instead of being cut off. Additive like everything else, which is why the
  --    inner layer can be whitened without the old "dark seam down the middle" problem.
  for index = 1, #C.beam_core do
    local style = C.beam_core[index]
    local width = lerp(style.width_cold, style.width_hot, charge) * flicker * narrow
    local alpha = lerp(style.alpha_cold, style.alpha_hot, charge) * fade
    local base = tier_color(style.tint, charge, profile)
    local whiten = style.whiten or 0
    CORE.r = lerp(base.r, 1.0, whiten)
    CORE.g = lerp(base.g, 1.0, whiten)
    CORE.b = lerp(base.b, 1.0, whiten)
    place_beam(objs, "core" .. index, surface, cx, cy, orient, width, length,
      style.texture, CORE, alpha)
  end

  -- 3. the boiling sheath: re-rolled a few times a second, not every tick
  if not beam.roll_tick or tick - beam.roll_tick >= C.beam_tongue_ticks then
    beam.roll_tick = tick
    for index = 1, C.beam_tongues do
      local roll = beam.rolls[index]
      if index > C.beam_tongues - C.beam_tongue_spill then
        -- the last few live at the very end of the lance and run PAST it, so the tip
        -- frays into separate tongues instead of stopping on a ruled line
        roll.start = 0.84 + math.random() * 0.16
        roll.finish = roll.start + 0.10 + math.random() * 0.30
      else
        roll.start = math.random() * 0.85
        roll.finish = roll.start + 0.05 + math.random() * 0.20
      end
      roll.offset = (math.random() * 2 - 1) * (0.30 + 0.60 * charge)
      roll.alpha = lerp(C.beam_tongue_alpha[1], C.beam_tongue_alpha[2], charge)
                     * (0.55 + 0.45 * math.random())
      roll.width = lerp(C.beam_tongue_width[1], C.beam_tongue_width[2], charge)
                     * (0.60 + 0.40 * math.random())
    end
  end
  for index = 1, C.beam_tongues do
    local roll = beam.rolls[index]
    local ax = from.x + ux * length * roll.start + px * roll.offset
    local ay = from.y + uy * length * roll.start + py * roll.offset
    local bx = from.x + ux * length * roll.finish + px * roll.offset * 0.4
    local by = from.y + uy * length * roll.finish + py * roll.offset * 0.4
    local sx, sy = bx - ax, by - ay
    local seg = math.sqrt(sx * sx + sy * sy)
    place_beam(objs, "tongue" .. index, surface, (ax + bx) * 0.5, (ay + by) * 0.5, orient,
      roll.width, seg + roll.width, "tongue", tier_color("sheath", charge, profile),
      roll.alpha * fade)
  end

  -- 4. muzzle: the flare sits just off the mouth, the cone points down the beam. Both
  --    swell for a few ticks after each pulse, which is the shot's thump.
  local pop = 1
  if beam.pulse_tick and tick - beam.pulse_tick < C.beam_pulse_ticks then
    pop = C.beam_pulse_pop
  end
  local mouth = C.beam_muzzle
  local flash = lerp(mouth.flare_cold, mouth.flare_hot, charge) * pop * narrow
  place_beam(objs, "muzzle", surface,
    from.x + ux * mouth.offset, from.y + uy * mouth.offset, orient,
    flash, flash, "flare", tier_color("sheath", charge, profile), mouth.flare_alpha * fade)
  local cone_len = lerp(mouth.cone_len_cold, mouth.cone_len_hot, charge) * pop * narrow
  local cone_width = lerp(mouth.cone_width_cold, mouth.cone_width_hot, charge) * pop * narrow
  place_beam(objs, "cone", surface,
    from.x + ux * cone_len * 0.5, from.y + uy * cone_len * 0.5, orient,
    cone_width, cone_len, "cone", tier_color("core", charge, profile), mouth.cone_alpha * fade)

  -- 5. impact: a flare on the nearest body the last pulse cut, so the beam visibly
  --    bites. It is re-positioned to the body's *current* position every tick (the cut
  --    only re-runs every pulse) and hidden the moment that body dies. Hidden, not
  --    destroyed, when the line is clear.
  local hit, hit_entity = beam.hit, beam.hit_entity
  if hit and hit_entity and (not hit_entity.valid
     or (hit_entity.health and hit_entity.health <= 0)) then
    hit = nil
  end
  if hit then
    local hx, hy = hit.x, hit.y
    if hit_entity and hit_entity.valid then
      local position = hit_entity.position
      hx, hy = position.x, position.y
    end
    local size = lerp(C.beam_impact.flare_cold, C.beam_impact.flare_hot, charge) * pop * narrow
    place_beam(objs, "impact", surface, hx, hy, orient, size, size, "flare",
      tier_color("core", charge, profile), C.beam_impact.alpha * fade)
  else
    local id = objs.impact
    local object = id and rendering.get_object_by_id(id)
    if object and object.valid then
      object.visible = false
    end
  end

  -- 6. the far end: the lance does not stop dead at maximum reach. A ragged plume is
  --    carried past the tip and dissolves, so the heat runs out of pressure instead of
  --    being scissored off, and a flare sits inside it where the core gives out. Both
  --    scale with charge, so a cold turret ends shorter and a hot one throws further --
  --    without either of them being allowed to reach past the turret's real range, which
  --    is what the damage corridor and range_for() still define.
  local dis = C.beam_dissipate
  local carry = lerp(dis.carry_cold, dis.carry_hot, charge) * narrow
  place_beam(objs, "spray", surface,
    to.x + ux * carry * 0.5, to.y + uy * carry * 0.5, orient,
    lerp(dis.width_cold, dis.width_hot, charge) * narrow, carry, "spray",
    tier_color("sheath", charge, profile),
    lerp(dis.alpha_cold, dis.alpha_hot, charge) * fade)
  local tip = lerp(C.beam_tip.flare_cold, C.beam_tip.flare_hot, charge) * narrow
  place_beam(objs, "tip", surface, to.x, to.y, orient, tip, tip, "flare",
    tier_color("sheath", charge, profile), C.beam_tip.alpha * fade)
end

-- Draw the lance from the mouth to `stop` this tick and remember that geometry: the
-- fade-out re-draws exactly the same data, so a beam looks the same for its whole life
-- however it ends.
local function draw_beam(turret, state, muzzle, stop, tick)
  local beam = beam_for(state)
  local dx, dy = stop.x - muzzle.x, stop.y - muzzle.y
  local length = math.sqrt(dx * dx + dy * dy)
  if length < 0.01 then
    return
  end
  local ux, uy = dx / length, dy / length
  -- A barrel pointing away from the camera fires a lance that the gun is standing in
  -- front of, so the drawn lance starts a little further down the barrel: the muzzle
  -- flare and the near end of the haze then sit past the gun's own silhouette instead of
  -- painting over it. Only the DRAWING moves; the mouth, the damage corridor and the
  -- reach are all still the turret's real ones.
  local start = 0
  if uy < -C.beam_behind_dot then
    start = C.beam_away_offset
  end
  local from_x, from_y = muzzle.x + ux * start, muzzle.y + uy * start
  beam.away = start > 0
  beam.surface = turret.surface
  beam.charge = state.charge
  beam.profile = fuel_profile(turret, state)
  beam.from.x, beam.from.y = from_x, from_y
  beam.to.x, beam.to.y = stop.x, stop.y
  beam.length = length - start
  beam.ux, beam.uy = ux, uy
  beam.orient = (atan2(dx, -dy) / (2 * math.pi)) % 1
  beam.alpha = 1
  beam.tick = tick
  render_beam(beam, tick)
end

-- One tick of fade-out; false when the beam is gone. Time is frozen on purpose: a dying
-- beam dims, it does not re-roll its sheath or re-pop its flare.
local function fade_beam(beam)
  beam.alpha = beam.alpha - 1 / C.beam_fade_ticks
  if beam.alpha <= 0 then
    destroy_beam(beam)
    return false
  end
  render_beam(beam, beam.tick)
  return true
end

local function fade_current_beam(state)
  local beam = state.beam
  if not beam then
    return
  end
  if not fade_beam(beam) then
    state.beam = nil
  end
end

-- The turret is gone: killed, mined, or removed by a script. Its lance is handed to the
-- fade list with the last geometry it drew, so it dims out on screen instead of
-- vanishing -- and its render objects stay reachable, so nothing can leak or stick.
local function retire_beam(state)
  local beam = state.beam
  state.beam = nil
  if beam and beam.surface and beam.length and beam.length > 0.01 then
    fades[#fades + 1] = beam
  else
    destroy_beam(beam)
  end
end

-- Two additive flares at the mouth: a hot core inside a soft halo. The same two objects
-- are the charge-up while the head swings (draw_windup) and the emitter bleeding off
-- its heat after a shot (draw_glow) -- only the colour and the size change.
local function draw_orb(surface, state, x, y, core, core_radius, halo, halo_radius)
  local objs = objects_of(state)
  local core_object = get_sprite(objs, "orb_core", "flare", surface)
  place(core_object, x, y, 0, core_radius * 2, core_radius * 2, "flare", core, core.a)
  local halo_object = get_sprite(objs, "orb_halo", "flare", surface)
  place(halo_object, x, y, 0, halo_radius * 2, halo_radius * 2, "flare", halo, halo.a)
end

-- the heat bleeding off the mouth while the turret is not firing
local function draw_glow(turret, state, muzzle)
  local charge = state.charge
  local profile = fuel_profile(turret, state)
  ORB_CORE.r, ORB_CORE.g, ORB_CORE.b = 1.0, lerp(0.55, 1.0, charge), lerp(0.25, 0.85, charge)
  ORB_CORE.a = 0.55 + 0.40 * charge
  ORB_HALO.r, ORB_HALO.g, ORB_HALO.b = profile.sheath.r, profile.sheath.g * 0.7, profile.sheath.b * 0.4
  ORB_HALO.a = 0.20 + 0.35 * charge
  draw_orb(turret.surface, state, muzzle.x, muzzle.y,
    ORB_CORE, 0.16 + 0.30 * charge,
    ORB_HALO, 0.30 + 0.95 * charge)
end

-- The charge-up that plays while the head is still swinging onto a target: a spot at
-- the mouth that grows over C.windup_ticks and pulses, then hands the mouth over to the
-- beam. Nothing is drawn along the barrel and nothing takes damage until the head is
-- within C.aim_tolerance of the target, so the shot cannot outrun the rotation.
local function draw_windup(turret, state, muzzle, elapsed, tick)
  local progress = math.min(1, elapsed / C.windup_ticks)
  local throb = 0.78 + 0.22 * math.sin(tick * 0.9)
  local sheath = fuel_profile(turret, state).sheath
  ORB_CORE.r, ORB_CORE.g, ORB_CORE.b = 1.0, lerp(0.40, 0.92, progress), lerp(0.12, 0.60, progress)
  ORB_CORE.a = (0.28 + 0.55 * progress) * throb
  ORB_HALO.r, ORB_HALO.g, ORB_HALO.b = sheath.r, sheath.g, sheath.b
  ORB_HALO.a = (0.10 + 0.28 * progress) * throb
  draw_orb(turret.surface, state, muzzle.x, muzzle.y,
    ORB_CORE, 0.09 + 0.25 * progress,
    ORB_HALO, 0.20 + 0.52 * progress)
end

-- The hull's spin-up gauge --------------------------------------------------
-- Six lights around the deck, filled in order as the charge climbs and emptied in reverse
-- as it falls, so "how far has this turret spun up" is readable from the map view instead
-- of being a guess. Everything the beam does with charge (wider, brighter, more tongues)
-- says "hotter"; none of it says "loading". This does.
--
-- They are additive sprites on a layer above the hull art, tinted with the burning fuel's
-- sheath colour, and they sit on an ELLIPSE: the camera is pitched, so a ring of lights
-- on a circular deck projects with its Y squashed by cos(tilt), and the whole ring is
-- lifted up-screen by the deck height. `spin_led_lift` is that lift.
local LED = {r = 1, g = 1, b = 1, a = 1}
local TAU = 2 * math.pi

local function draw_leds(turret, state)
  local count = C.spin_leds
  if not count or count <= 0 then
    return
  end
  local charge = state.charge
  local objs = objects_of(state)
  local sheath = fuel_profile(turret, state).sheath
  local radius, squash = C.spin_led_radius, COS_TILT
  local pivot_x, pivot_y = turret.position.x, turret.position.y - C.spin_led_lift
  -- No rotation on purpose: the ring is a ring, so turning the emplacement (R) cannot
  -- slide a light off a deck detail it was never aligned to. Reading turret.direction
  -- here would cost a wrapped call every tick and buy nothing on a 6-lamp ring.
  local turn = 0
  for index = 1, count do
    -- how far this light is into its own step: -1 means "not yet", 1 means "full"
    local level = charge * count - (index - 1)
    if level < 0 then
      level = 0
    elseif level > 1 then
      level = 1
    end
    -- smoothstep, so a light comes up over its step instead of snapping on
    local lit = level * level * (3 - 2 * level)
    local angle = turn + (index - 1) / count * TAU
    local size = C.spin_led_size * (0.55 + 0.45 * lit)
    local whiten = 0.15 + (C.spin_led_white - 0.15) * lit
    LED.r = lerp(sheath.r, 1, whiten)
    LED.g = lerp(sheath.g, 1, whiten)
    LED.b = lerp(sheath.b, 1, whiten)
    LED.a = C.spin_led_dim + (C.spin_led_alpha - C.spin_led_dim) * lit
    place(get_sprite(objs, "led" .. index, "flare", turret.surface),
      pivot_x + math.cos(angle) * radius,
      pivot_y + math.sin(angle) * radius * squash,
      0, size, size, "flare", LED, LED.a, C.spin_led_layer)
  end
end

------------------------------------------------------------------ tick -------

local function update(turret, state, tick)
  -- `shooting_state` is character-only (it throws on a turret), so engagement is
  -- read off the turret's own target. The engine happily keeps *aiming* at a target
  -- with an empty magazine, so the fuel check has to be ours: no cell, no beam.
  local range = state.range or C.range
  local target = turret.shooting_target
  -- A target handed over by a neighbour's help call can sit outside this turret's own
  -- reach, and the engine keeps aiming at it forever (it never re-checks whether the
  -- help call was sensible). If a reachable enemy exists, hand the engine that one
  -- instead; the beam then matches what the turret can actually burn.
  local reachable = target ~= nil and target.valid and in_reach(turret, target, range)
  if target ~= nil and not reachable and tick >= (state.scan_at or 0) then
    state.scan_at = tick + C.range_scan_ticks
    local better = nearest_enemy(turret, range)
    if better then
      target = better
      turret.shooting_target = better
    end
  end
  local firing = target ~= nil and target.valid and in_reach(turret, target, range) and has_fuel(turret)
  local aim = firing and target.position or nil

  if C.debug and firing ~= state.was_firing then
    log(string.format("melta unit=%s firing=%s target=%s", tostring(turret.unit_number), tostring(firing), firing and target.name or "-"))
    state.was_firing = firing
  end

  if firing then
    state.charge = math.min(1, state.charge + 1 / C.spin_up_ticks)
  else
    state.charge = math.max(0, state.charge - 1 / C.spin_down_ticks)
  end
  -- the hull gauge tracks the charge wherever the turret is in its cycle (firing,
  -- swinging, cooling), so it is drawn here rather than inside one of the branches below
  if state.charge > 0.01 then
    draw_leds(turret, state)
  end

  local dx, dy, distance = 0, 0, 0
  if aim then
    dx, dy, distance = normalize(aim.x - turret.position.x, aim.y - turret.position.y)
  end

  if firing and distance > 0.05 then
    -- the barrel's own direction, not the target's: the beam has to leave the mouth
    -- wherever the head currently points, and only once that IS the target
    local orientation = turret.orientation
    local fx, fy = facing(orientation or 0)
    local muzzle = muzzle_point(turret, fx, fy)
    state.last_muzzle = muzzle

    -- Is the head on the target? Compare the weapon's smooth orientation with the
    -- bearing to the target. A turret whose orientation cannot be read (no vanilla
    -- entity does this, but a modded one might) is treated as aligned rather than
    -- silently mute.
    local aligned = true
    local error_turns = 0
    if orientation then
      error_turns = aim_error(orientation, dx, dy)
      aligned = math.abs(error_turns) <= C.aim_tolerance
    end

    -- a fresh target restarts the wind-up -- unless the barrel already points at it,
    -- which is the common case when it finishes one biter and picks the next one on
    -- the same line: charging up there would cost a pulse per kill for nothing.
    if state.aim_target ~= target.unit_number then
      state.aim_target = target.unit_number
      state.aim_from = aligned and (tick - C.windup_ticks) or tick
    end
    local elapsed = tick - (state.aim_from or tick)

    if aligned and elapsed >= C.windup_ticks then
      -- The beam runs from the mouth to the target and on through whatever stands
      -- behind it, and the corridor test runs along that same line -- so the bodies
      -- the beam cuts are exactly the ones it visibly touches. It ends `range` from
      -- the turret centre (16 tiles plus the quality bonus), so the per-direction
      -- muzzle offset cannot shorten the reach.
      local ax, ay = normalize(aim.x - muzzle.x, aim.y - muzzle.y)
      local along = (muzzle.x - turret.position.x) * ax + (muzzle.y - turret.position.y) * ay
      local reach = math.max(1, range - along)

      -- DAMAGE every tick, so whatever the drawn beam crosses is burnt for as long as it
      -- is crossed (see burn_tick). The impact flare follows the nearest body from here,
      -- which also makes it track a moving target smoothly instead of jumping once a pulse.
      local impact, impact_entity = burn_tick(turret, state, muzzle, ax, ay, reach, tick)
      if state.beam then
        state.beam.hit = impact
        state.beam.hit_entity = impact_entity
      end

      if tick >= state.pulse_at then
        local interval = pulse_interval(turret)
        if state.pulse_at < tick - interval then
          -- the clock lost time (the beam stopped and re-acquired, or a target was
          -- held through a wind-up): start the countdown from now instead of firing
          -- a burst to "catch up"
          state.pulse_at = tick + interval
        else
          -- carry the fraction of a tick forward. `tick + interval` would round the
          -- interval UP to a whole tick every time, which silently threw away part of
          -- the researched firing speed: at +80 % rate the interval is 4.44 ticks, and
          -- firing every 5 ticks is 12/s instead of 13.5/s (measured: that alone cost
          -- the melta 15 % of its dps against the gun turret at tier 4). Carrying the
          -- remainder makes the average interval exactly the researched one while every
          -- pulse still lands on a whole tick.
          state.pulse_at = state.pulse_at + interval
        end
        beam_for(state).pulse_tick = tick
        state.beam_end = pulse(turret, state, muzzle, ax, ay, reach)
      end

      -- the lance always runs its full length: it does not stop at the first body it
      -- cuts, so whatever stands behind the current target is on the line too
      local stop =
      {
        x = muzzle.x + ax * reach,
        y = muzzle.y + ay * reach
      }
      draw_beam(turret, state, muzzle, stop, tick)
      draw_glow(turret, state, muzzle)
      if C.debug then
        log(string.format("melta unit=%s beam err=%.2fdeg ori=%.4f muzzle=(%.3f,%.3f) at=(%.1f,%.1f) reach=%.2f",
          tostring(turret.unit_number), error_turns * 360, orientation or -1,
          muzzle.x, muzzle.y, turret.position.x, turret.position.y, reach))
      end
      return
    end

    -- still swinging onto the target: charge the mouth, draw no beam, deal no damage.
    -- `state.pulse_at` is deliberately NOT advanced, so the first shot is due the
    -- moment the barrel arrives instead of a cooldown later.
    corridor_clear(state)
    fade_current_beam(state)
    draw_windup(turret, state, muzzle, elapsed, tick)
    if C.debug then
      log(string.format("melta unit=%s windup err=%.2fdeg aligned=%s elapsed=%d",
        tostring(turret.unit_number), error_turns * 360, tostring(aligned), elapsed))
    end
    return
  end

  -- not shooting: the beam is gone, the emitter bleeds off its heat
  corridor_clear(state)
  state.aim_target = nil
  state.pulse_at = tick + C.cooldown
  state.beam_end = nil
  -- the lance fades out over C.beam_fade_ticks instead of snapping off
  fade_current_beam(state)
  -- the head keeps turning after the last shot (a new target may already be acquired), so
  -- the bleed-off glow is re-anchored to where the mouth is NOW -- it used to stay at the
  -- last firing position and read as a glowing disc floating next to the gun
  local orientation = turret.orientation
  if orientation then
    local fx, fy = facing(orientation)
    state.last_muzzle = muzzle_point(turret, fx, fy)
  end
  if state.charge > 0.02 and state.last_muzzle then
    draw_glow(turret, state, state.last_muzzle)
  else
    destroy_orb(state)
    if state.charge <= 0 then
      if C.debug and state.debt ~= 0 then
        log(string.format("melta unit=%s cooled down", tostring(turret.unit_number)))
      end
      state.debt = 0
    end
  end
end

---------------------------------------------------------------- registry -----

local function unregister(entity)
  if not entity or not entity.unit_number then
    return
  end
  local state = turrets[entity.unit_number]
  if state then
    -- mid-beam destruction must not leave a lance hanging in the air: the beam is
    -- handed to the fade list and dims out, its objects still reachable
    retire_beam(state)
    destroy_orb(state)
    turrets[entity.unit_number] = nil
  end
end

-- Build/mine events cover everything a player or a robot places, but an entity
-- created by another mod's script raises nothing at all. The registry is only a
-- cache, so a periodic sweep repairs it instead of leaving silent dead turrets.
local function reconcile()
  local seen = {}
  for _, surface in pairs(game.surfaces) do
    for _, entity in pairs(surface.find_entities_filtered{name = TURRET}) do
      if entity.unit_number then
        seen[entity.unit_number] = true
        state_for(entity)
      end
    end
  end
  for unit_number, state in pairs(turrets) do
    if not seen[unit_number] or not state.entity or not state.entity.valid then
      retire_beam(state)
      destroy_orb(state)
      turrets[unit_number] = nil
    end
  end
end

script.on_init(function()
  storage.turrets = {}
  storage.fades = {}
  storage.bonus_cache = {}
  turrets = storage.turrets
  fades = storage.fades
end)

-- Research is the only thing that changes the bonus tables, so those two events
-- are the whole invalidation story. Cheap: the next pulse of any melta refills
-- the entry for its force.
local function forget_research()
  storage.bonus_cache = {}
end

script.on_event(defines.events.on_research_finished, forget_research)
script.on_event(defines.events.on_technology_effects_reset, forget_research)

script.on_configuration_changed(function()
  storage.turrets = storage.turrets or {}
  storage.fades = storage.fades or {}
  -- a changed prototype set can change resistances and technology effects
  storage.bonus_cache = {}
  flat_armor_cache = nil
  turrets = storage.turrets
  fades = storage.fades
  reconcile()
end)

script.on_nth_tick(600, function()
  reconcile()
end)

-- on_load only re-binds the local, the table itself is saved with the storage table
script.on_load(function()
  turrets = storage.turrets
  fades = storage.fades or {}
end)

local built_events =
{
  defines.events.on_built_entity,
  defines.events.on_robot_built_entity,
  defines.events.script_raised_built,
  defines.events.script_raised_revive
}

script.on_event(built_events, function(event)
  local entity = event.entity or event.created_entity
  if entity and entity.valid and entity.name == TURRET and entity.unit_number then
    state_for(entity)
  end
end)

local removed_events =
{
  defines.events.on_player_mined_entity,
  defines.events.on_robot_mined_entity,
  defines.events.on_entity_died,
  defines.events.script_raised_destroy
}

script.on_event(removed_events, function(event)
  unregister(event.entity)
end)

script.on_nth_tick(1, function(event)
  -- lances whose turret died mid-beam finish dying here
  for index = #fades, 1, -1 do
    if not fade_beam(fades[index]) then
      table.remove(fades, index)
    end
  end
  if not next(turrets) then
    return
  end
  local tick = event.tick
  for unit_number, state in pairs(turrets) do
    local turret = state.entity
    if turret and turret.valid then
      update(turret, state, tick)
    else
      retire_beam(state)
      destroy_orb(state)
      turrets[unit_number] = nil
    end
  end
end)

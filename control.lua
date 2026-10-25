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
--   * visuals    -- three stacked beam lines and a muzzle orb, all driven by charge
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

local function fuel_profile(turret)
  local best = nil
  for _, fuel in ipairs(fuels_here()) do
    if turret.get_fluid_count(fuel.name) > 0 then
      if not best or (fuel.damage_modifier or 1) > (best.damage_modifier or 1) then
        best = fuel
      end
    end
  end
  return best or DEFAULT_PROFILE
end

-- one entry per placed melta turret, keyed by unit_number:
--   entity, charge (0..1), pulse_at, debt, line, glow, beam_end, last_muzzle
local turrets

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
local function muzzle_point(turret, ux, uy)
  return
  {
    x = turret.position.x + C.muzzle_forward * ux,
    y = turret.position.y + COS_TILT * C.muzzle_forward * uy - MUZZLE_LIFT
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

local function clear_beam(state)
  for _, container in ipairs({state.lines, state.sheath}) do
    if container then
      for index = 1, #container do
        destroy_object(container[index])
      end
    end
  end
  state.lines = nil
  state.sheath = nil
  state.sheath_rolls = nil
  state.sheath_tick = nil
end

local function clear_glow(state)
  local glow = state.glow
  if not glow then
    return
  end
  destroy_object(glow.core)
  destroy_object(glow.halo)
  state.glow = nil
end

local function clear_state(state)
  clear_beam(state)
  clear_glow(state)
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
local function pop(surface, position, charge, radius, alpha, layer)
  rendering.draw_circle
  {
    surface = surface,
    target = position,
    color =
    {
      r = 1.0,
      g = lerp(0.50, 0.95, charge),
      b = lerp(0.18, 0.80, charge),
      a = alpha
    },
    radius = radius,
    filled = true,
    render_layer = layer or "projectile",
    time_to_live = 3
  }
end

----------------------------------------------------------------- pulse -------

-- Cuts everything standing on the beam axis and returns where the beam stopped.
local function pulse(turret, state, muzzle, dx, dy, reach)
  local force = turret.force
  local profile = fuel_profile(turret)
  local damage = (C.damage_cold + (C.damage_hot - C.damage_cold) * state.charge) * profile.damage_modifier
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

  local hits = {}
  for _, candidate in pairs(candidates) do
    if candidate.valid and candidate ~= turret and candidate.force and force.is_enemy(candidate.force) then
      local vx = candidate.position.x - muzzle.x
      local vy = candidate.position.y - muzzle.y
      local along = vx * dx + vy * dy
      local box = candidate.bounding_box
      local radius = math.max(box.right_bottom.x - box.left_top.x, box.right_bottom.y - box.left_top.y) * 0.5
      -- `along <= reach + radius`: a body whose *centre* is a fraction of a tile past the
      -- end of the corridor still has its skin inside it, and that is exactly how far the
      -- engine's own range test reaches (it measures to the bounding box). Without the
      -- radius the turret would aim at and burn fluid on a spawner 17 tiles out with a
      -- 16-tile beam and never hurt it.
      if along > 0 and along <= reach + radius then
        local offset = math.sqrt((vx - dx * along) ^ 2 + (vy - dy * along) ^ 2)
        if offset <= C.hit_half_width + radius then
          hits[#hits + 1] = {entity = candidate, along = along, position = candidate.position}
        end
      end
    end
  end
  table.sort(hits, function(left, right) return left.along < right.along end)

  local stop = {x = far_x, y = far_y}
  local cut = math.min(#hits, C.pierce_max)
  for index = 1, cut do
    local hit = hits[index]
    local victim = hit.entity
    -- everything in the corridor burns, enemies only: friendly forces and neutral
    -- scenery are filtered out above, so your own base is never in the line of fire
    local dealt = damage * C.pierce_falloff ^ (index - 1)
    if dealt > 0 and victim.valid and victim.health then
      -- Fire is what a melta is; the physical share is the mass of the stream hitting
      -- the body. Two calls because `damage()` takes one type per call (positional:
      -- amount, force, type, cause). The total is unchanged -- the split is taken out
      -- of `dealt`, so balance is identical and only the resistance maths differs:
      -- a 100 % fire-resistant target still eats C.physical_share of the pulse.
      victim.damage(dealt * (1 - C.physical_share), force, C.damage_type, turret)
      -- the fire hit may have killed it; a dead entity has nothing left to damage
      if victim.valid and victim.health and victim.health > 0 then
        victim.damage(dealt * C.physical_share, force, C.damage_type_hit, turret)
      end
      -- Asteroids are 100 % fire resistant and their big/huge tiers subtract 2000/3000
      -- from every physical hit, so a rock would otherwise take almost nothing from the
      -- beam. Rocks get an extra hit in `explosion` -- the damage type the vanilla
      -- asteroid ladder is balanced around -- sized off the same pulse, so it ramps with
      -- charge, with fuel and with pierce falloff like everything else. Gated on the
      -- entity type, so pawns, spawners and buildings never take it (constants.lua).
      if victim.valid and victim.health and victim.health > 0 and victim.type == "asteroid" then
        victim.damage(dealt * C.asteroid_damage_multiplier, force, C.asteroid_damage_type, turret)
      end
      pop(turret.surface, hit.position, state.charge, 0.42 + 0.35 * state.charge, 0.85, "higher-object-above")
    end
    stop = hit.position
  end

  -- muzzle flash: forward of the barrel so it does not sit inside the sprite
  local flash = {x = muzzle.x + dx * 0.45, y = muzzle.y + dy * 0.45}
  pop(turret.surface, flash, state.charge, 0.55 + 0.65 * state.charge, 0.55)
  pop(turret.surface, flash, state.charge, 0.25 + 0.30 * state.charge, 0.95)

  if C.debug then
    log(string.format("melta pulse unit=%s charge=%.2f damage=%.1f reach=%.1f candidates=%d hits=%d fuel=%d",
      tostring(turret.unit_number), state.charge, damage, reach, #candidates, #hits, turret.get_fluid_count()))
  end

  burn_surcharge(turret, state)
  return stop
end

---------------------------------------------------------------- visuals ------

local function update_line(turret, container, index, from, to, color, width)
  local line = container[index] and rendering.get_object_by_id(container[index])
  if line and line.valid then
    line.from = {from.x, from.y}
    line.to = {to.x, to.y}
    line.color = color
    line.width = width
    return
  end
  local object = rendering.draw_line
  {
    surface = turret.surface,
    from = {from.x, from.y},
    to = {to.x, to.y},
    color = color,
    width = width,
    render_layer = "projectile"
  }
  container[index] = object.id
end


-- A melta beam is a lance of superheated *stuff*, not a laser: the two inner layers
-- are stable, and the sheath around them is a set of short segments that jump to a
-- new random offset, length and alpha every few ticks. That boiling edge is what
-- stops it reading as a tidy light line.
local function draw_beam(turret, state, muzzle, stop, tick)
  local charge = state.charge
  local profile = fuel_profile(turret)
  local flicker = 1 + C.beam_flicker * math.sin(tick * 0.7) * charge

  local dx = stop.x - muzzle.x
  local dy = stop.y - muzzle.y
  local length = math.sqrt(dx * dx + dy * dy)
  if length < 0.01 then
    return
  end
  dx, dy = dx / length, dy / length
  -- perpendicular, for sideways jitter
  local px, py = -dy, dx

  local lines = state.lines
  if not lines then
    lines = {}
    state.lines = lines
  end

  -- inner layers: stable
  for index, style in ipairs(C.beam_layers) do
    local width = (style.width_cold + (style.width_hot - style.width_cold) * charge) * flicker
    update_line(turret, lines, index, muzzle, stop, beam_color(style, charge, profile), width)
  end

  ---------------------------------------------------------------- sheath -----
  local sheath = state.sheath
  if not sheath then
    sheath = {}
    state.sheath = sheath
  end
  -- re-roll the boiling edge a few times a second, not every tick
  if not state.sheath_tick or tick - state.sheath_tick >= C.sheath_retune_ticks then
    state.sheath_tick = tick
    state.sheath_rolls = {}
    for index = 1, C.sheath_segments do
      local start_f = math.random() * 0.85
      local run_f = start_f + 0.06 + math.random() * 0.22
      local offset = (math.random() * 2 - 1) * (0.35 + 0.55 * charge)
      local alpha = (0.12 + 0.24 * charge) * (0.55 + 0.45 * math.random())
      local width = (0.10 + 0.34 * charge) * (0.5 + 0.5 * math.random())
      state.sheath_rolls[index] = {start_f, run_f, offset, alpha, width}
    end
  end

  local sheath_color = profile.sheath
  for index, roll in ipairs(state.sheath_rolls or {}) do
    local start_f, run_f, offset, alpha, width = roll[1], roll[2], roll[3], roll[4], roll[5]
    local from =
    {
      x = muzzle.x + dx * (length * start_f) + px * offset,
      y = muzzle.y + dy * (length * start_f) + py * offset
    }
    local to =
    {
      x = muzzle.x + dx * (length * run_f) + px * offset * 0.4,
      y = muzzle.y + dy * (length * run_f) + py * offset * 0.4
    }
    update_line(turret, sheath, index,
      from, to,
      {r = sheath_color.r, g = sheath_color.g, b = sheath_color.b, a = alpha},
      width)
  end
end

-- Two filled circles at the muzzle: a hot core inside a soft halo. Circles rather than
-- draw_light on purpose -- a light needs a sprite file, and `__core__/...` paths are
-- not resolvable at runtime ("Unknown type __core__"), so this keeps the mod
-- asset-free. Both effects below (heat bleeding off, and the charge-up while the
-- barrel swings) are the same two circles with different colours and sizes.
local function draw_orb(turret, state, muzzle, core_color, core_radius, halo_color, halo_radius)
  state.glow = state.glow or {}
  local glow = state.glow

  local core = glow.core and rendering.get_object_by_id(glow.core)
  if core and core.valid then
    core.target = {muzzle.x, muzzle.y}
    core.radius = core_radius
    core.color = core_color
  else
    local object = rendering.draw_circle
    {
      surface = turret.surface,
      target = {muzzle.x, muzzle.y},
      color = core_color,
      radius = core_radius,
      filled = true,
      render_layer = "projectile"
    }
    glow.core = object.id
  end

  local halo = glow.halo and rendering.get_object_by_id(glow.halo)
  if halo and halo.valid then
    halo.target = {muzzle.x, muzzle.y}
    halo.radius = halo_radius
    halo.color = halo_color
  else
    local object = rendering.draw_circle
    {
      surface = turret.surface,
      target = {muzzle.x, muzzle.y},
      color = halo_color,
      radius = halo_radius,
      filled = true,
      render_layer = "projectile"
    }
    glow.halo = object.id
  end
end

-- the charge orb while the beam is burning / heat bleeding off the mouth
local function draw_glow(turret, state, muzzle)
  local charge = state.charge
  local color = beam_color(C.beam_layers[#C.beam_layers], charge, fuel_profile(turret))
  draw_orb(turret, state, muzzle,
    {r = 1.0, g = lerp(0.55, 1.0, charge), b = lerp(0.25, 0.85, charge), a = 0.55 + 0.4 * charge},
    0.16 + 0.30 * charge,
    {r = color.r, g = color.g * 0.7, b = color.b * 0.4, a = 0.18 + 0.35 * charge},
    0.30 + 0.95 * charge)
end

-- The charge-up that plays while the head is still swinging onto a target: a spot at
-- the mouth that grows over C.windup_ticks and pulses, then hands the mouth over to
-- the beam. Nothing is drawn along the barrel and nothing takes damage until the head
-- is within C.aim_tolerance of the target, so the shot cannot outrun the rotation.
local function draw_windup(turret, state, muzzle, elapsed, tick)
  local progress = math.min(1, elapsed / C.windup_ticks)
  local throb = 0.78 + 0.22 * math.sin(tick * 0.9)
  local sheath = fuel_profile(turret).sheath
  draw_orb(turret, state, muzzle,
    {r = 1.0, g = lerp(0.40, 0.92, progress), b = lerp(0.12, 0.60, progress),
     a = (0.28 + 0.55 * progress) * throb},
    0.09 + 0.25 * progress,
    {r = sheath.r, g = sheath.g, b = sheath.b, a = (0.08 + 0.26 * progress) * throb},
    0.20 + 0.52 * progress)
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

      if tick >= state.pulse_at then
        state.pulse_at = tick + C.cooldown
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
    clear_beam(state)
    draw_windup(turret, state, muzzle, elapsed, tick)
    if C.debug then
      log(string.format("melta unit=%s windup err=%.2fdeg aligned=%s elapsed=%d",
        tostring(turret.unit_number), error_turns * 360, tostring(aligned), elapsed))
    end
    return
  end

  -- not shooting: the beam is gone, the emitter bleeds off its heat
  state.aim_target = nil
  state.pulse_at = tick + C.cooldown
  state.beam_end = nil
  clear_beam(state)
  if state.charge > 0.02 and state.last_muzzle then
    draw_glow(turret, state, state.last_muzzle)
  else
    clear_glow(state)
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
  if not entity or not entity.valid or not entity.unit_number then
    return
  end
  local state = turrets[entity.unit_number]
  if state then
    clear_state(state)
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
      clear_state(state)
      turrets[unit_number] = nil
    end
  end
end

script.on_init(function()
  storage.turrets = {}
  turrets = storage.turrets
end)

script.on_configuration_changed(function()
  storage.turrets = storage.turrets or {}
  turrets = storage.turrets
  reconcile()
end)

script.on_nth_tick(600, function()
  reconcile()
end)

-- on_load only re-binds the local, the table itself is saved with the storage table
script.on_load(function()
  turrets = storage.turrets
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
  if not next(turrets) then
    return
  end
  local tick = event.tick
  for unit_number, state in pairs(turrets) do
    local turret = state.entity
    if turret and turret.valid then
      update(turret, state, tick)
    else
      clear_state(state)
      turrets[unit_number] = nil
    end
  end
end)

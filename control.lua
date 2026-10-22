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

local function beam_color(style, charge)
  local cold = style.color_cold
  local hot = style.color_hot
  return
  {
    r = lerp(cold.r, hot.r, charge),
    g = lerp(cold.g, hot.g, charge),
    b = lerp(cold.b, hot.b, charge),
    a = lerp(cold.a, hot.a, charge)
  }
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
  -- positional API (like damage()): remove_fluid(amount, fluidbox_index)
  local removed = turret.remove_fluid(state.debt, 1)
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
  local damage = C.damage_cold + (C.damage_hot - C.damage_cold) * state.charge
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
      if along > 0 and along <= reach then
        local offset = math.sqrt((vx - dx * along) ^ 2 + (vy - dy * along) ^ 2)
        local box = candidate.bounding_box
        local radius = math.max(box.right_bottom.x - box.left_top.x, box.right_bottom.y - box.left_top.y) * 0.5
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
      victim.damage(dealt, force, C.damage_type, turret)
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
      tostring(turret.unit_number), state.charge, damage, reach, #candidates, #hits, turret.get_fluid_count(C.fluid)))
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
    update_line(turret, lines, index, muzzle, stop, beam_color(style, charge), width)
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

  local hot = C.beam_layers[#C.beam_layers]
  local sheath_color = beam_color(hot, charge)
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
      {r = sheath_color.r, g = sheath_color.g * 0.85, b = sheath_color.b * 0.5, a = alpha},
      width)
  end
end

-- The charge orb at the muzzle: two filled circles (a hot core inside a soft
-- halo) that grow with charge. Circles rather than draw_light on purpose -- a
-- light needs a sprite file, and `__core__/...` paths are not resolvable at
-- runtime ("Unknown type __core__"), so this keeps the mod asset-free.
local function draw_glow(turret, state, muzzle)
  local charge = state.charge
  local color = beam_color(C.beam_layers[#C.beam_layers], charge)
  local halo_color = {r = color.r, g = color.g * 0.7, b = color.b * 0.4, a = 0.18 + 0.35 * charge}
  local core_color = {r = 1.0, g = lerp(0.55, 1.0, charge), b = lerp(0.25, 0.85, charge), a = 0.55 + 0.4 * charge}
  local core_radius = 0.16 + 0.30 * charge
  local halo_radius = 0.30 + 0.95 * charge

  state.glow = state.glow or {}

  local core = state.glow.core and rendering.get_object_by_id(state.glow.core)
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
    state.glow.core = object.id
  end

  local halo = state.glow.halo and rendering.get_object_by_id(state.glow.halo)
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
    state.glow.halo = object.id
  end
end

------------------------------------------------------------------ tick -------

local function update(turret, state, tick)
  -- `shooting_state` is character-only (it throws on a turret), so engagement is
  -- read off the turret's own target. The engine happily keeps *aiming* at a target
  -- with an empty magazine, so the fuel check has to be ours: no cell, no beam.
  local target = turret.shooting_target
  local firing = target ~= nil and target.valid and turret.get_fluid_count(C.fluid) > 0
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
    state.last_muzzle =
    {
      x = turret.position.x + dx * C.muzzle_offset,
      y = turret.position.y + dy * C.muzzle_offset
    }
    local reach = math.max(1, C.range - C.muzzle_offset)

    if tick >= state.pulse_at then
      state.pulse_at = tick + C.cooldown
      state.beam_end = pulse(turret, state, state.last_muzzle, dx, dy, reach)
    end

    -- the lance always runs its full length: it does not stop at the first body it
    -- cuts, so whatever stands behind the current target is on the line too
    local stop =
    {
      x = state.last_muzzle.x + dx * reach,
      y = state.last_muzzle.y + dy * reach
    }
    draw_beam(turret, state, state.last_muzzle, stop, tick)
    draw_glow(turret, state, state.last_muzzle)
    return
  end

  -- not shooting: the beam is gone, the emitter bleeds off its heat
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

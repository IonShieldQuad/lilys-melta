-- Measures, on 2.1:
--   * whether `ammo-damage` (bullet) and `turret-attack` (gun-turret) research
--     both scale a gun turret shot (the "double dip"), and whether they stack
--     multiplicatively or additively;
--   * whether vanilla flamethrower stream damage takes both (ammo-damage
--     flamethrower + turret-attack flamethrower-turret);
--   * whether LuaEntity.damage() (script damage) is scaled by either modifier.
-- Log lines are prefixed "[dip]".

local PHASE =
{
  {name = "none",  ammo = 0,   turret = 0},
  {name = "ammo",  ammo = 1.0, turret = 0},
  {name = "turret", ammo = 0,  turret = 1.0},
  {name = "both",  ammo = 1.0, turret = 1.0}
}
local PHASE_TICKS = 150
local WARMUP = 60

local gun, gundummy
local fl, fldummy

local function logf(fmt, ...)
  log(string.format("[dip] " .. fmt, ...))
end

local function apply_phase(index)
  local p = PHASE[index]
  local force = game.forces.player
  force.set_ammo_damage_modifier("bullet", p.ammo)
  force.set_turret_attack_modifier("gun-turret", p.turret)
  force.set_ammo_damage_modifier("flamethrower", p.ammo)
  force.set_turret_attack_modifier("flamethrower-turret", p.turret)
  logf("phase %d %s ammo=%.2f turret=%.2f", index, p.name, p.ammo, p.turret)
end

local function flatten(surface, x1, y1, x2, y2)
  local tiles = {}
  for x = x1, x2 do
    for y = y1, y2 do
      tiles[#tiles + 1] = {name = "grass-1", position = {x, y}}
    end
  end
  surface.set_tiles(tiles)
end

script.on_init(function()
  storage.phase = 1

  local surface = game.surfaces[1]
  surface.request_to_generate_chunks({0, 0}, 6)
  surface.force_generate_chunk_requests()
  flatten(surface, -20, -20, 60, 20)

  gun = surface.create_entity{name = "gun-turret", position = {0, 0}, force = game.forces.player}
  gun.insert{name = "firearm-magazine", count = 40}
  gundummy = surface.create_entity{name = "dip-dummy", position = {0, -8}, force = game.forces.enemy}
  gundummy.health = gundummy.max_health

  fl = surface.create_entity{name = "flamethrower-turret", position = {40, 0},
                             direction = defines.direction.north, force = game.forces.player}
  fldummy = surface.create_entity{name = "dip-dummy-flame", position = {40, -12}, force = game.forces.enemy}
  fldummy.health = fldummy.max_health

  storage.gun = gun
  storage.gundummy = gundummy
  storage.fl = fl
  storage.fldummy = fldummy
  apply_phase(1)
end)

script.on_load(function()
  gun, gundummy = storage.gun, storage.gundummy
  fl, fldummy = storage.fl, storage.fldummy
end)

script.on_nth_tick(1, function(event)
  local tick = event.tick
  local phase = storage.phase

  -- phase clock: WARMUP ticks of "none", then one PHASE_TICKS block per phase
  if tick >= WARMUP and (tick - WARMUP) % PHASE_TICKS == 0 then
    local next_phase = math.floor((tick - WARMUP) / PHASE_TICKS) + 1
    if next_phase <= #PHASE then
      storage.phase = next_phase
      phase = next_phase
      apply_phase(next_phase)
    end
  end

  -- keep the flamethrower fed (its buffer is 100 and it burns ~12/s)
  if fl and fl.valid then
    fl.insert_fluid{name = "light-oil", amount = 100}
  end

  local ammo = -1
  if gun and gun.valid then
    local inv = gun.get_inventory(defines.inventory.turret_ammo)
    if inv then
      ammo = inv.get_item_count("firearm-magazine")
    end
  end
  local name = (PHASE[phase] or PHASE[1]).name
  logf("t=%d ph=%s ghp=%.2f ammo=%d fhp=%.2f ffluid=%d",
       tick, name,
       gundummy and gundummy.valid and gundummy.health or -1,
       ammo,
       fldummy and fldummy.valid and fldummy.health or -1,
       fl and fl.valid and fl.get_fluid_count() or -1)
end)

-- script-damage check: a raw LuaEntity.damage() call must NOT be scaled by
-- research; only the engine's own ammo/stream damage is.
script.on_nth_tick(660, function()
  local force = game.forces.player
  force.set_ammo_damage_modifier("bullet", 1.0)
  force.set_turret_attack_modifier("gun-turret", 1.0)
  force.set_ammo_damage_modifier("flamethrower", 1.0)
  force.set_turret_attack_modifier("flamethrower-turret", 1.0)
  local before = gundummy.health
  gundummy.damage(10, force, "physical", gun)
  logf("script t=%d before=%.2f after=%.2f delta=%.2f (expect 10.00)",
       game.tick, before, gundummy.health, before - gundummy.health)
end)

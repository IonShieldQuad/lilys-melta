-- Save/reload probe (never shipped).
--
-- Phase 1 (--create): on_init builds a small scene -- a fuelled, rotated melta with
-- four pipes and a pipe full of fluid -- and stores handles in storage. The game then
-- writes the map to disk, so the save contains a live melta, not an empty pad.
-- Phase 2 (--load-game of that save): the first tick logs what survived.

local TURRET = "melta-turret"
local FLUID = "melta-fuel"
local MELTA = {x = 0, y = 200}

local function logf(fmt, ...)
  log("[persist] " .. string.format(fmt, ...))
end

local function conn_set(t)
  local out = {}
  for _, c in ipairs(t.get_fluid_box_pipe_connections(1) or {}) do
    out[#out + 1] = string.format("%.2f,%.2f", c.position.x, c.position.y)
  end
  table.sort(out)
  return table.concat(out, " ")
end

local function describe(label, t)
  if not t or not t.valid then
    logf("%s: turret NOT valid", label)
    return
  end
  logf("%s: valid dir=%s orient=%.4f fluid=%.1f hp=%.0f unit=%s",
    label, tostring(t.direction), t.orientation or -1, t.get_fluid_count(), t.health,
    tostring(t.unit_number))
  logf("%s: connections %s", label, conn_set(t))
end

script.on_init(function()
  local surface = game.surfaces[1]
  surface.always_day = true
  local ok_chunks, err = pcall(function()
    surface.request_to_generate_chunks({MELTA.x, MELTA.y}, 2)
    surface.force_generate_chunk_requests()
  end)
  logf("on_init: chunk generation %s %s", tostring(ok_chunks), tostring(err or ""))

  for _, e in ipairs(surface.find_entities_filtered{area = {{MELTA.x - 20, MELTA.y - 20}, {MELTA.x + 20, MELTA.y + 20}}}) do
    if e.valid then
      e.destroy()
    end
  end

  local turret = surface.create_entity{name = TURRET, position = {MELTA.x, MELTA.y},
                                       force = game.forces.player, raise_built = true}
  if not turret then
    logf("on_init: FAILED to create the turret")
    return
  end
  MELTA.x, MELTA.y = turret.position.x, turret.position.y
  turret.direction = defines.direction.east

  for _, p in ipairs({{0, -2}, {2, 0}, {0, 2}, {-2, 0}}) do
    local pipe = surface.create_entity{name = "pipe", position = {MELTA.x + p[1], MELTA.y + p[2]},
                                       force = game.forces.player}
    if pipe then
      pipe.set_fluid(1, {name = FLUID, amount = 100})
    end
  end
  -- no ticks run between on_init and the map being written, so the fuel is put
  -- straight into both fluid boxes (1 = piped box, 2 = internal buffer) instead of
  -- waiting for the pipes to feed the buffer
  local ok_fluid, err_fluid = pcall(function()
    turret.set_fluid(1, {name = FLUID, amount = 120})
    turret.set_fluid(2, {name = FLUID, amount = 140})
  end)
  logf("on_init: direct fluid fill %s %s", tostring(ok_fluid), tostring(err_fluid or ""))

  storage.persist = {turret = turret, built_at = MELTA.x .. "," .. MELTA.y}
  describe("on_init after build", turret)
end)

script.on_event(defines.events.on_tick, function(event)
  if event.tick ~= 1 then
    return
  end
  local st = storage.persist or {}
  logf("reload: storage.%s", st.built_at and ("built_at=" .. st.built_at) or "EMPTY")
  describe("reload", st.turret)
  local surface = game.surfaces[1]
  logf("reload: pipes on the map around the turret: %d",
    #surface.find_entities_filtered{name = "pipe", area = {{MELTA.x - 4, MELTA.y - 4}, {MELTA.x + 4, MELTA.y + 4}}})
  logf("reload: melta turrets on the map: %d",
    #surface.find_entities_filtered{name = TURRET, area = {{MELTA.x - 8, MELTA.y - 8}, {MELTA.x + 8, MELTA.y + 8}}})
  logf("PERSIST DONE")
end)

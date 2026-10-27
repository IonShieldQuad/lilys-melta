# Which fluid is the lance coloured by? (measured, 2.1.23)

Playtest report: *"beam color uses the color of the fluid in the connected pipe, not the
buffer"*. The script never reads a pipe — it reads `LuaEntity::get_fluid_count(name)` per
fuel in `constants.lua` — so the report only makes sense if a fluid turret holds **two
fluid boxes** and the read lands on the one the pipes fill while the engine burns the
other. That is exactly what the probe found.

## Probe

`ftest-fluid` run directory, headless (`--create` + `--benchmark 400`), one melta at
(0, 200) with an enemy spawner 9 tiles north so it keeps firing. No pipes at all: the probe
pushes fluids in with `insert_fluid`, which is the only way to reach a specific box.

Log (`factorio-current.log`, script output trimmed):

```
insert melta-fuel 1000 -> ok=true amount=200.0          # box 1 takes 200 and stops
after A count(melta-fuel)=200.0 count(light-oil)=0.0
after A contents: melta-fuel=200.0                      # nothing else is in there
insert light-oil 500  -> ok=true amount=0.0             # box 1 is full of another fluid
t60  contents: melta-fuel=184.3                          # firing, burning A
t200 count(melta-fuel)=126.7 count(light-oil)=0.0
t200 insert light-oil 300 -> ok=true amount=200.0        # <-- a SECOND box took it
t200 after B contents: light-oil=200.0 melta-fuel=126.7  # two boxes, two fluids
t380 count(melta-fuel)=69.2 count(light-oil)=111.6
t380 contents: light-oil=111.6 melta-fuel=69.2
```

Two conclusions, both measured:

1. **A fluid turret has two fluid boxes** — the piped one (`fluid_box`, the four
   `pipe_connections`) and the internal one the turret shoots from (`fluid_buffer_size`).
   With the first full, `insert_fluid` for a different fluid succeeded into the second, and
   `get_fluid_contents()` reports both.
2. **The engine drains both** while firing (over 180 ticks: light-oil −88.4, melta-fuel
   −57.5, total ≈ one shot's worth of fluid per shot). There is no "buffer only" read and
   no API to read a single box: `get_fluid_count`/`get_fluid_contents` are documented as
   "all or some fluid in this entity", and 2.1.23 exposes boxes only through
   `get_fluid_box_prototype/capacity/pipe_connections(index)`, never their contents.

So "highest `damage_modifier` present" — the 0.5.2 rule — is not the same question as
"what is burning". It answers with whatever is present, and it will keep answering with the
pipe fluid even after the turret has emptied that pipe box.

## Fix

`sample_fuel()` runs once per **pulse** (7.5/s — the engine has just taken its fluid, so
the delta is unambiguous) and remembers the fuel whose amount FELL. `fuel_profile()` prefers
that fuel, and falls back to the most plentiful one only when nothing has burnt yet (first
pulse, or a pulse that took no fluid). Verified in the same run with the mod's debug log
temporarily printing the choice:

```
melta pulse unit=5 charge=0.05 burn=melta-fuel dmgmod=1.60 fuel=200
melta pulse unit=5 charge=1.00 burn=melta-fuel dmgmod=1.60 fuel=136
melta pulse unit=5 charge=1.00 burn=light-oil  dmgmod=1.00 fuel=224   # after t200
```

The turret switched to light-oil the moment light-oil started draining faster than
melta-fuel — i.e. the lance, its flares and the `damage_modifier` now follow the fluid the
turret is actually consuming, which is also the one the engine multiplies its own stream
by. Under the old rule it would have stayed on melta-fuel (1.60 > 1.00) forever.

Cost: four engine reads per shot per turret, no allocation (both sample tables live in the
turret's state and are swapped).

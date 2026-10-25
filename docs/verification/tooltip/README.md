# The damage readout in the melta's inspect panel

## What was wrong

The panel had a Damage line, and the number in it was ~0.1 instead of ~420.

`before-panel.jpg` is a desktop grab of the panel as it shipped in 0.5.0 (the only way
to photograph a tooltip: `game.take_screenshot` never contains one). Its last lines:

```
Fluid damage modifier: 160%
Kills: 0
Damage dealt: 0
Effect
Damage: 0.09/s Fire
Damage: 0.02/s Physical
```

0.11/s against a weapon that deals 105/s cold and 420/s white-hot. The reason is that
the number is not the melta's damage at all: a fluid turret can only fire `stream`
attacks, so the prototype carries an invisible carrier stream, and the engine prints
*that stream's contact damage* -- 1 damage split 85 % fire / 15 % physical, which it
then divides down to a per-second figure. The real damage is script damage
(`control.lua`, `pulse()`), which the engine knows nothing about, so nothing in the
prototype could ever have described it.

## What the fix does

1. `prototypes/tooltip.lua` (new, data stage) generates the damage paragraph **from
   `constants.lua`** and appends it to both the entity description and the item
   description, so the inspect panel and the inventory tooltip cannot disagree:

   > Damage: 14 per pulse on a cold barrel, 56 at full intensity (85 % fire, 15 %
   > physical). At 7.5 pulses per second that is 105 to 420 per second on the first
   > body in the line; each body behind it takes 82 % of the one before, up to 12
   > bodies. Fuel multiplies it: light oil x1.00, petroleum gas x0.85, enriched melta
   > fuel x1.60. Rocks and asteroids also take an explosion hit at 160 % of the pulse.

   Every number is read out of `constants.lua` (charge ramp, `physical_share`,
   `cooldown`, `pierce_falloff`, `pierce_max`, each fuel's `damage_modifier`,
   `asteroid_damage_multiplier`), and only the fuels this install actually has are
   listed -- so a retune changes the tooltip by itself and an absent dependency
   cannot leave a ghost entry. Text lives in `locale/en` and `locale/ru`.
2. `prototypes/melta.lua` drops the carrier stream's 1 damage. It measured as dead
   code -- a full-charge pulse took exactly 56.00 hp off an unarmoured dummy, i.e. the
   script's number and not a point more -- but the engine still printed it as the
   panel's Damage line. With the effects at zero the engine leaves the whole Effect
   block out, so the panel no longer advertises a damage figure that is not the
   weapon's. Zero rather than an empty list because a stream action rejects an empty
   `target_effects` (`Key "type" not found`).

## How it was verified

`after-panel.jpg` is the same panel, same turret, after the change.

Damage actually dealt, measured on an unarmoured dummy with 1e6 hp (health sampled
every tick, so each pulse is one drop) by `melta-measure`:

| fuel | multiplier | steady drop per pulse | expected |
|---|---|---|---|
| light oil | x1.00 | **56.00** | 56 |
| enriched melta fuel | x1.60 | **89.63** | 89.6 |

First pulses ramp 17.63 -> 19.88 -> 22.13 (light oil): `14 + 42 * charge` with the
charge built over the ticks since the turret started firing, exactly as the tooltip's
"14 cold ... 56 at full intensity" says.

Other checks:

* **The tooltip follows the constants.** A staged copy with `C.damage_hot = 70`
  printed "70 at full intensity ... 105 to 525 per second" -- no second copy of the
  numbers exists to forget.
* **Translation resolves.** `localised_print` of the resolved description in both
  languages, all 11 parameters substituted (`locale/en`, `locale/ru`).
* **Works with and without the quality mod.** Loads and prints the identical text
  with `quality` + `recycler` enabled and with them off: the block reads no quality
  field at all, so an entity without a quality comp cannot break it. (Damage does not
  scale with quality; only range does, through the engine's own `range_multiplier`,
  which the description above the block already states.)

## Reproducing it

`harness/melta-probe` places a melta, a vanilla flamethrower turret and a gun turret on
a concrete pad and cycles the camera between them, logging `HOVER_<subject>` lines.
`hover capture` (`docs/verification/tooltip/tooltip_shots.py`, needs `Pillow`) launches
the staged env with `SteamAppId=427520` and a scratch `--config`/`--mod-directory`,
matches the game window **by process id**, parks the OS cursor on the subject and saves
the full desktop -- the tooltip only exists under the real cursor, and a second
Factorio instance on the same machine must not be photographed by accident.
`harness/melta-measure` is the damage measurement (headless: `--create` then
`--benchmark scene.zip --benchmark-ticks 700`).

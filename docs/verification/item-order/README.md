# Where the melta sorts in the item lists

The item prototype used to carry `subgroup = "defensive-structure"` with an order string
written against the pre-2.1 flat "combat" layout, so it landed at the tail of that subgroup —
one slot past the radar, away from every other turret.

As of 2.1 the combat group is split into two subgroups: `turret` (subgroup order `i`) and
`defensive-structure` (subgroup order `h`, which holds stone wall, gate, the radar and the
land mine). Turrets are not in `defensive-structure` at all, so no order string inside it can
put the melta next to a gun turret.

## What the item carries now

```lua
subgroup = "turret",
order    = "b[turret]-c[flamethrower-turret]-a[melta-turret]",
```

## Why that key

Factorio sorts order strings segment by segment, alternating text and `[bracket]` text; the
bracketed text is for humans and is ignored by the comparison, so the key above reads
`b-c-a`. Vanilla's own turret ladder is:

| key | item |
|---|---|
| `b-a` | gun turret |
| `b-b` | laser turret |
| `b-c` | flamethrower turret |
| **`b-c-a`** | **melta turret (this mod)** |
| `b-d-a` | artillery turret |
| `b-e-a` | rocket turret (space age) |
| `b-f-a` | tesla turret (space age) |
| `b-g-a` | railgun turret (space age) |

`b-c-a` is the flamethrower turret's key with a suffix: a longer string sharing a prefix
sorts after the shorter one, and `-a` keeps it ahead of artillery (`b-d-a`). So the melta
sits directly after the flamethrower turret — the liquid-fuel turret it is the bigger cousin
of — and before every heavier turret. Because the key is a prefix extension of vanilla's own,
it holds whatever the rest of the ladder does (a mod adding another turret under `b-h` still
lands after the melta), and it does not depend on space age being enabled.

## Evidence

### 1. Data stage, straight out of `--dump-data`

`docs/verification/harness/melta-itemorder/check_order.py` on a dump of the committed tree
(`git archive HEAD`), once with base only and once with the official mod set (base +
space age + quality + elevated rails + recycler):

| set | subgroup of `turret` (group `combat`, group order `e`, subgroup order `i`) |
|---|---|
| base only | 5 items: gun, laser, flamethrower, **melta (4)**, artillery |
| official set | 8 items: gun, laser, flamethrower, **melta (4)**, artillery, rocket, tesla, railgun |

Both runs: `PASS` under the documented comparison (bracket text ignored) *and* under plain
string comparison, so the key does not rely on one reading of the rule. `radar` was found in
subgroup `defensive-structure` at position 3 of 4 — a different subgroup, so it cannot be a
neighbour. Exactly one item prototype points at the entity `melta-turret`, so there is no
duplicate entry to explain.

### 2. Runtime prototype table

The probe mod logs every sibling of the subgroup from `prototypes.item` at runtime, in the
same session as the screenshots below — the table the crafting menu is built from:

```
[itemorder] PROBE READY ... subgroup=[LuaItemSubGroup: turret] order=b[turret]-c[flamethrower-turret]-a[melta-turret]
[itemorder] sib gun-turret order=b[turret]-a[gun-turret]
[itemorder] sib laser-turret order=b[turret]-b[laser-turret]
[itemorder] sib flamethrower-turret order=b[turret]-c[flamethrower-turret]
[itemorder] sib melta-turret order=b[turret]-c[flamethrower-turret]-a[melta-turret]
[itemorder] sib artillery-turret order=b[turret]-d[artillery-turret]-a[turret]
[itemorder] sib rocket-turret order=b[turret]-e[rocket-turret]-a[turret]
[itemorder] sib tesla-turret order=b[turret]-f[tesla-turret]-a[turret]
[itemorder] sib railgun-turret order=b[turret]-g[railgun-turret]-a[turret]
```

### 3. In the real crafting menu

`01-crafting-search-turret.png` — inventory (E) opened in a GUI launch of the official mod
set, search box filtered to `turret`: one row of eight turret recipes.
`02-hover-melta-turret.png` — the same row with slot 4 hovered.

Read back by hovering each slot, so each position is named by the game and not by guessing
at 30-pixel icons:

| slot | item (tooltip title) |
|---|---|
| 1 | Gun turret |
| 2 | Laser turret |
| 3 | Flamethrower turret |
| 4 | **Melta turret** |
| 5 | Artillery turret |
| 6 | Rocket turret |
| 7 | Tesla turret |
| 8 | Railgun turret |

The row holds eight entries — the seven vanilla turrets plus the melta once. No radar, no
second melta.

### 4. Nothing else in the install can re-sort it

A scan of every installed mod (238 enabled, `C:\Users\Lily\AppData\Roaming\Factorio\mods`)
found no mod other than `lilys-melta` that mentions `melta-turret`, and none that writes the
`turret` or `defensive-structure` item-subgroup.

## Reproducing it

```bash
H="H:/Factorio Mods/lilys-melta/docs/verification/harness/melta-itemorder"
bash "$H/stage.sh" official            # or: base   (stages an isolated env from HEAD)
cd <the printed dir>
"E:/SteamLibrary/steamapps/common/Factorio/bin/x64/Factorio.exe" \
  --config <env>/config.ini --mod-directory <env>/mods --dump-data
python "$H/check_order.py" <env>/write/script-output/data-raw-dump.json
```

`stage.sh official` and the 400 s probe-ready timeout in `run_gui.py` are what this check
needed: with space age enabled the sprite atlas takes ~200 s to build on this machine, and a
180 s timeout photographs the loading screen instead of the menu.

For the screenshots:

```bash
"E:/.../Factorio.exe" --config <env>/config.ini --mod-directory <env>/mods --create <env>/write/scene.zip
python "$H/run_gui.py" <env> <env>/out/gui   # plan: E, click the magnifier, type "turret", grab
```

# Melta turret: player-facing text (localisation pass)

Every visible string for the turret lives in `locale/en/locale.cfg` and
`locale/ru/locale.cfg`; the damage figures are generated from `constants.lua` and
joined with those strings by `prototypes/tooltip.lua`. This note records the final
strings, the vanilla references they were matched against, and how they were verified.

## Final strings (en)

| key | value |
|---|---|
| `item-name.melta-turret` | Melta turret |
| `item-description.melta-turret` | Short-ranged turret that burns liquid fuel to fire a pressurized stream of heat. Does not use ammunition. |
| `entity-name.melta-turret` | Melta turret |
| `entity-description.melta-turret` | Fires a pressurized stream of burning fuel at enemies. Needs a fluid supply instead of ammunition. |
| `fluid-name.melta-fuel` | Enriched melta fuel |
| `fluid-description.melta-fuel` | Light oil enriched with uranium dust and sulfur. Burns green-white and hotter than plain oil. |
| `recipe-name.melta-turret` | Melta turret |
| `recipe-name.melta-fuel` | Enriched melta fuel |
| `technology-name.melta-turret` | Melta turret |
| `technology-description.melta-turret` | Unlocks a turret that burns liquid fuel to fire a short-ranged, pressurized stream of heat. |
| `ammo-category-name.melta` | Melta |
| `mod-name.lilys-melta` | Melta turret |
| `mod-description.lilys-melta` | Adds a short-ranged turret that burns liquid fuel into a pressurized stream of heat. It needs no ammunition. |
| `melta-tooltip.armor` | Ignores the flat part of enemy armor. Percentage resistance still applies. |
| `melta-tooltip.research` | Improved by flamethrower damage and turret firing speed research. |

`info.json` carries the same title and description, because the mod list and the portal
read those two fields before any locale key is loaded.

## Vanilla references used

| vanilla 2.1.23 string | source |
|---|---|
| flamethrower-turret = "Fires a stream of burning liquid at enemies." | `data/base/locale/en/base.cfg` |
| artillery-turret = "Long-range cannon targeting enemy bases." | same |
| rocket-turret = "A long range turret that fires rockets." | `data/space-age/locale/en/space-age.cfg` |
| railgun-turret = "A long range electric cannon turret. Effective against enemies and asteroids." | same |
| tesla-turret = "Electrocutes a nearby enemy. The electric bolt can bounce to secondary enemies in an arcing chain." | same |

The melta mirrors the flamethrower's one-sentence form because it is the same family --
a liquid-fuel turret -- and adds the two facts that differ: the stream is pressurized,
and the fuel arrives by pipe instead of by magazine.

`gun-turret` and `laser-turret` have **no** `entity-description` in 2.1 at all, so the
"small, versatile turret" / "powerful turret" lines are not available as a model any
more; the flamethrower is the live one.

## Spelling and tone rules that were actually applied

- **American English.** Vanilla is US English: `armor` 38x in `base.cfg`, `colour` 0x.
  The pass took every `-ise`/`-our` form out of player-facing text (`pressurized`,
  `armor`).
- **Locale keys stay ASCII.** `grep -P '^[^\x00-\x7F]+='` over the vanilla Russian
  locale returns 0: a Cyrillic key never matches `{"melta-tooltip.armor"}`, so a
  translated key silently falls back to English. RU uses the same ASCII keys as EN.
- Sentence case, no exclamation marks, no marketing adjectives; longest rendered lines
  are 108 characters (en) and 122 (ru), so tooltips wrap on word boundaries.

## What in-game rendering actually turned out to be

Both tooltips were photographed from a real GUI run (steady-state save, real mouse
hover, window matched by process id). Two rendering facts that only the capture could
show, both fixed:

1. **`[fluid=light-oil]` renders as the fluid ICON ALONE inside a tooltip.** The first
   capture read `Fuel bonus: <drop> x1.00, <drop> x0.85, <drop> x1.60` -- three
   unlabelled drops. The block now spells each fluid's own `[fluid-name.*]` next to its
   icon: `Fuel bonus: <drop> Light oil x1.00, <drop> Petroleum gas x0.85, <drop>
   Enriched melta fuel x1.60.`
2. **A parameterised localised string swallows anything appended past its last
   parameter.** `{"melta-tooltip.block", __1__ ... __11__}` had two extra lines
   (armor, research) appended to it; the engine treated them as unused parameters and
   dropped them, so both tooltips ended at the rock sentence. The lines are now
   appended to the outer description, and both tooltips show them.

## Verification

| check | how | result |
|---|---|---|
| every key resolves, no `Unknown key` | `melta-locale-probe` `localised_print` in `on_init` during `--create` | 15/15 keys resolved (en) |
| placeholder count == parameter list | same run: `helpers.table_to_json(localised_description)` | `__1__`..`__11__` present, all substituted |
| both tooltips render | GUI run + OS-mouse hover, screenshots in `melta-locale-probe/out3` | item tooltip and entity panel both show flavour, damage block, fuel names, armor and research lines |
| key parity en/ru | `write_locale.py` validator (key sets, placeholder sets, ASCII keys, 140-char lines) | 0 problems |
| fluid names in the fuel list | probe prints each accepted fluid's `[fluid-name.*]` | Light oil / Petroleum gas / Enriched melta fuel |

Harness: `docs/verification/harness/melta-locale-probe/`
(`stage.sh` builds an isolated env, `capture_quickbar.py` photographs both tooltips,
`stage_rev.py` extracts an exact commit with python's tarfile -- `git archive | tar -x`
does not survive this box's bsdtar).

The final check was run on the commit itself, not the working tree: the tree of
`melta: put every turret string in vanilla voice, and make the block render` was
extracted with `stage_rev.py`, loaded with `--create`, and answered all 15 keys plus
the item and entity flavour lines correctly. So the committed files are the ones that
were proven, not a neighbour's uncommitted edits.

Screenshots from that run (2.1.23, en):

- `docs/verification/locale/item-tooltip.png` -- the inventory/quickbar tooltip: flavour
  line, damage block with the named fuel list, armor and research lines.
- `docs/verification/locale/entity-panel.png` -- the inspect panel on a placed turret,
  same description, plus status/health/range/consumption.

The Russian strings were resolved through the same probe with `locale=ru` in the
scratch config: all 15 keys, the item/entity flavour lines and the three fuel names
came back in Russian, no `Unknown key`. (`locale=`, not `language=` -- the latter is
ignored and the game starts in English, which is exactly the wrong result for a
locale check.)

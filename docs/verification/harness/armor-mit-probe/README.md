# armor-mit-probe — what `LuaEntity.damage()` does with flat `decrease` and `percent`

Harness mod, **never shipped**. Answers the one question the melta's flat-armour bypass
depends on: in which order the engine applies `resistances[type].decrease` and
`resistances[type].percent`, whether the result is clamped, what a negative `decrease` does,
and whether handing the engine `amount + decrease` really lands on the nominal number.

Six armour profiles, each created as two 100 000 hp dummy units (`small-biter` copies with
movement, vision and attack disabled — float32 health, so a big pool does not quantise the
damage away):

| key | prototype resistances |
|---|---|
| `no_res` | none |
| `flat12` | `physical decrease = 12` |
| `pct10` | `physical percent = 10` |
| `flat12_pct10` | `physical decrease = 12, percent = 10` |
| `flat12_pct100` | `physical decrease = 12, percent = 100` |
| `neg5_pct10` | `physical decrease = -5, percent = 10` |

`on_init` hits the first dummy of each pair with 100 `physical` and the second with
`100 + decrease`, logging the health delta and `damage()`'s return value. No ticks run, so
nothing has time to heal.

## Run

```bash
W=<scratch env>          # never the live mods dir
cp -r armor-mit-probe "$W/mods/"
# mod-list.json: base enabled, armor-mit-probe enabled
printf '[path]\r\nwrite-data=%s/write\r\n' "$W" > "$W/config.ini"
SteamAppId=427520 SteamGameId=427520 Factorio.exe \
  --config "$W/config.ini" --mod-directory "$W/mods" --create "$W/probe.zip"
grep mitprobe "$W/write/factorio-current.log"
```

`SteamAppId`/`SteamGameId` are required on this install (Steam build) even for a headless
run: without them the game restarts itself and exits.

## Result on 2.1.23

```
no_res         decrease=0    percent=0    | hit 100 -> landed 100.000 | hit 100 -> landed 100.000
flat12         decrease=12   percent=0    | hit 100 -> landed  88.000 | hit 112 -> landed 100.000
pct10          decrease=0    percent=10   | hit 100 -> landed  90.000 | hit 100 -> landed  90.000
flat12_pct10   decrease=12   percent=10   | hit 100 -> landed  79.203 | hit 112 -> landed  90.000
flat12_pct100  decrease=12   percent=100  | hit 100 -> landed   0.000 | hit 112 -> landed   0.000
neg5_pct10     decrease=-5   percent=10   | hit 100 -> landed  94.500 | hit  95 -> landed  90.000
```

i.e. `landed = max(0, amount - decrease) * (1 - percent/100)` — flat first, percentage second,
clamped at zero, negative `decrease` adds damage, `percent = 100` is absolute, and the
compensation identity (`amount + decrease`) is exact for both signs of `decrease`.
`damage()` returns the post-mitigation amount (`79.199997` for the 79.203 case, float32).

Analysis that uses these numbers: `docs/analysis/armor-mitigation.md`.

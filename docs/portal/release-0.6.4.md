# Portal text for the 0.6.4 release

Paste-ready. The mod-portal "About" box takes markdown-ish plain text (no rich formatting, but
`#`/`-`/`*` render as headings and lists on the current portal editor).

---

## Short description (already in `info.json`, shown in the mod list and the browser)

> Adds a short-ranged turret that burns liquid fuel into a pressurized stream of heat. It needs
> no ammunition. Balance and progression are still being tuned (see the changelog).

---

## Long description (portal "About")

**A fluid weapon, not an ammo weapon.** The melta drinks liquid fuel from a pipe — light oil,
petroleum gas, enriched melta fuel, cubonium gas, Lily's napalm if you run Incendiaries — and
keeps it in a 200-unit buffer, so a turret at the end of a dead pipe still has a few seconds of
beam left. Nothing to belt, nothing to reload.

**It spins up.** Holding fire on a target for 2.5 s takes the beam from 32 to 128 damage per
pulse (7.5 pulses/s), and five lights on the hull deck show how hot it is. Tap fire and you get
a cold emplacement; keep it fed and it becomes the hardest-hitting short-range turret in the
game.

**It is a cutter, not a sniper.** 16 tiles of reach at normal quality (24 at legendary), and the
beam burns *everything* it crosses — every body on the line takes the full hit, up to 30 at
once, with 85 % fire and 15 % physical so a fire-immune target still loses something. Flat
armour is ignored; percentage resistance is not.

**It sweeps.** The lance follows the barrel, and the turret does not stop firing while there are
enemies in range: when a target dies the beam keeps going and drags across whatever stands
between it and the next one.

**What it costs / what pays for it.** Fuelling is a trickle of oil rather than a belt of shells
(~19/s cold, ~47/s white hot), and damage scales with the fire damage line (`refined-flammables`)
and the turret firing-speed line — including the infinite tier, per level.

**Compatibility.** Space Age is optional (the pipe hardware falls back to vanilla covers), and
the turret picks up any fluid that exists in your pack. Balance is tuned against vanilla
turrets only; with overhaul mods it will be whatever those mods' numbers make it.

---

## Status note — please read before judging the balance (also in the 0.6.4 changelog)

> Balance and progression have **not** been through a balance pass. Everything in this release
> was measured in one save — dps against dummies, armour handling, asteroid damage, research at
> each tier — and the weapon's shape (continuous damage, no pierce falloff, barrel-following
> beam) is new. So the numbers are expected to move in a later version: damage per pulse, fuel
> cost, research scaling and where the turret sits in progression are all still open. Feedback
> of the "this feels too strong / too expensive / this comes too late" kind is wanted, and is
> not a report of a bug.

---

## Gallery

Ready to upload from `docs/portal/screenshots/` (1920×1080 JPEG):

| file | what it shows | suggested slot |
|---|---|---|
| `01-hero.jpg` | three emplacements firing into a wave, one burning down a cluster | first image |
| `02-emplacement.jpg` | close-up: the model, the muzzle, the five deck lights | item/art shot |
| `03-battle-line.jpg` | the emplacement line holding against a swarm | second image |
| `04-night.jpg` | the lance at night, ground glow and fuel-tinted colour | mood shot |
| `05-sweep.jpg` | mid-sweep: the beam crossing the gap between targets | the new behaviour |
| `06-wide.jpg` | the line from further out, terrain context | optional |

Thumbnail already in the repo root: `thumbnail.png` (512×512) and `thumbnail-144.png`.

---

## Upload

1. Build the artifact: `lilys-melta_0.6.4.zip` (docs/, .py, old zips and Photoshop sources are
   excluded by the packer — the previous uploads carried sources and were much larger).
2. Upload it on <https://mods.factorio.com/user/IonShield> → Melta turret → Edit → Upload a new
   version. The API key route (`ModPortal: Upload Mods`, from
   <https://factorio.com/profile>) also works:
   `python H:/Factorio Mods/_tools/portalupload.py --dir <folder with the zip>`
3. Paste the long description above into "About", set the gallery images in the order in the
   table, and keep the changelog as it is in the zip (0.6.0-0.6.3 entries are the internal
   history of the rework; 0.6.4 is the player-facing summary).

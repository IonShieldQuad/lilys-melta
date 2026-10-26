"""Reproduce the tables in docs/analysis/armor-mitigation.md §4.

Melta numbers are parsed out of the repo's constants.lua; enemy resistances and the
comparison turrets come out of a --dump-data of the game the mod runs on. Nothing is
hardcoded from prose, and a missing constant is a hard error rather than a silent zero.

    python docs/analysis/quantify_armor.py <path to data-raw-dump.json>

How to make the dump (2.1.23, scratch env, never the live mods dir):

    Factorio.exe --config <scratch>/config.ini --mod-directory <scratch>/mods --dump-data
    # <scratch>/mods/mod-list.json must enable base, space-age, quality, recycler,
    # elevated-rails; the dump lands in <scratch>/write/script-output/data-raw-dump.json

Mitigation, as measured by docs/verification/harness/armor-mit-probe (2.1.23):

    landed = max(0, amount - decrease) * (1 - percent / 100)
"""
import json
import os
import re
import sys

if len(sys.argv) < 2:
    raise SystemExit(__doc__)

DUMP = sys.argv[1]
CONSTANTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "constants.lua")
CONSTANTS = os.path.normpath(CONSTANTS)

src = open(CONSTANTS, encoding="utf-8").read()


def const(name):
    m = re.search(r"^C\.%s\s*=\s*([-\d.]+)" % re.escape(name), src, re.M)
    if not m:
        raise SystemExit("constants.lua no longer defines C.%s -- fix this script" % name)
    return float(m.group(1))


COLD = const("damage_cold")
HOT = const("damage_hot")
SHARE = const("physical_share")
COOLDOWN = const("cooldown")
ASTEROID_MULT = const("asteroid_damage_multiplier")
RATE = 60.0 / COOLDOWN

dump = json.load(open(DUMP, encoding="utf-8"))


def resistances(ptype, name):
    p = dump[ptype][name]
    out = {}
    res = p.get("resistances") or {}
    if isinstance(res, dict):
        for k, v in res.items():
            out[k] = (v.get("decrease", 0), v.get("percent", 0))
    else:
        for v in res:
            if isinstance(v, dict) and "type" in v:
                out[v["type"]] = (v.get("decrease", 0), v.get("percent", 0))
    return out


def land(amount, res):
    decrease, percent = res
    return max(0.0, amount - decrease) * (1 - percent / 100.0)


TARGETS = [
    ("small biter", "unit", "small-biter"),
    ("medium biter", "unit", "medium-biter"),
    ("big biter", "unit", "big-biter"),
    ("behemoth biter", "unit", "behemoth-biter"),
    ("behemoth spitter", "unit", "behemoth-spitter"),
    ("biter spawner", "unit-spawner", "biter-spawner"),
    ("behemoth worm", "turret", "behemoth-worm-turret"),
    ("big stomper pentapod", "spider-unit", "big-stomper-pentapod"),
    ("small asteroid", "asteroid", "small-metallic-asteroid"),
    ("medium asteroid", "asteroid", "medium-metallic-asteroid"),
    ("big asteroid", "asteroid", "big-metallic-asteroid"),
    ("huge asteroid", "asteroid", "huge-metallic-asteroid"),
]

# Boss profiles from the pack installed on this machine: mferrari_lib/prototypes/
# resistances.lua. Transcribed because they need that mod loaded to appear in a dump.
BOSSES = {
    "boss_fire_only": {"fire": (-5, -80), "physical": (20, 60), "impact": (20, 90),
                       "explosion": (20, 60), "laser": (10, 50), "electric": (10, 50)},
    "boss_fireworm": {"electric": (-10, -50), "laser": (-10, -40), "physical": (10, 10),
                      "fire": (0, 100), "impact": (0, 100), "explosion": (15, 40)},
}

GUN_RATE = 60.0 / dump["ammo-turret"]["gun-turret"]["attack_parameters"]["cooldown"]


def ammo_amount(name):
    action = dump["ammo"][name]["ammo_type"]["action"]
    if isinstance(action, list):
        action = action[0]
    delivery = action["action_delivery"]
    if isinstance(delivery, list):
        delivery = delivery[0]
    for effect in delivery["target_effects"]:
        if effect["type"] == "damage":
            return effect["damage"]["amount"], effect["damage"]["type"]
    raise SystemExit("no damage effect in %s" % name)


BULLETS = [("firearm", "firearm-magazine"), ("piercing", "piercing-rounds-magazine"),
           ("uranium", "uranium-rounds-magazine")]

# The tesla turret's damage lives in its chain trigger's beams, not in the ammo.
TESLA = dump["electric-turret"]["tesla-turret"]["attack_parameters"]
TESLA_DMG = None
for effect in dump["beam"]["chain-tesla-gun-beam-start"]["action"]["action_delivery"]["target_effects"]:
    if effect["type"] == "damage":
        TESLA_DMG = (effect["damage"]["amount"], effect["damage"]["type"])
TESLA_RATE = 60.0 / TESLA["cooldown"]


def melta(pulse, res, ignore_flat, asteroid=False):
    fire_amount = pulse * (1 - SHARE)
    phys_amount = pulse * SHARE
    if ignore_flat:
        fire_amount += max(0.0, res.get("fire", (0, 0))[0])
        phys_amount += max(0.0, res.get("physical", (0, 0))[0])
    total = land(fire_amount, res.get("fire", (0, 0))) + land(phys_amount, res.get("physical", (0, 0)))
    if asteroid:
        total += land(pulse * ASTEROID_MULT, res.get("explosion", (0, 0)))
    return total


print("melta: cold %.0f / hot %.0f per pulse, %.0f%% physical, %.1f pulses/s"
      % (COLD, HOT, SHARE * 100, RATE))
print("gun turret: %.0f shots/s; tesla: %.2f shots/s, %s %s per jump"
      % (GUN_RATE, TESLA_RATE, TESLA_DMG[0], TESLA_DMG[1]))
print()

print("| target | armour (flat / %) | melta cold today | cold, flat ignored | melta hot today | hot, flat ignored |")
print("|---|---|---|---|---|---|")
for label, ptype, name in TARGETS:
    res = resistances(ptype, name)
    armour = ", ".join("%s %g/%g%%" % (k[0].upper(), res[k][0], res[k][1])
                       for k in ("physical", "fire", "explosion") if k in res) or "none"
    ast = ptype == "asteroid"
    print("| %s | %s | %.2f | %.2f | %.2f | %.2f |" % (
        label, armour, melta(COLD, res, False, ast), melta(COLD, res, True, ast),
        melta(HOT, res, False, ast), melta(HOT, res, True, ast)))

print()
print("| target | firearm (5) | piercing (8) | uranium (24) | tesla (%s %s) | flat-armour loss: melta hot / uranium |"
      % (TESLA_DMG[0], TESLA_DMG[1]))
print("|---|---|---|---|---|---|")
for label, ptype, name in TARGETS:
    res = resistances(ptype, name)
    cells = ["%.2f" % land(ammo_amount(n)[0], res.get(ammo_amount(n)[1], (0, 0))) for _, n in BULLETS]
    tesla = land(TESLA_DMG[0], res.get(TESLA_DMG[1], (0, 0)))
    ast = ptype == "asteroid"
    today, ignored = melta(HOT, res, False, ast), melta(HOT, res, True, ast)
    melta_loss = 100.0 * (1 - today / ignored) if ignored else 0.0
    uranium, dtype = ammo_amount("uranium-rounds-magazine")
    gun_loss = 100.0 * (1 - land(uranium, res.get(dtype, (0, 0))) / uranium)
    print("| %s | %s | %.2f | melta hot %.1f%% / uranium %.1f%% |" % (
        label, " | ".join(cells), tesla, melta_loss, gun_loss))

print()
print("dps (single target, first body, %.1f pulses/s):" % RATE)
for label, ptype, name in TARGETS:
    res = resistances(ptype, name)
    ast = ptype == "asteroid"
    print("  %-22s cold %6.1f -> %6.1f   hot %6.1f -> %6.1f" % (
        label, melta(COLD, res, False, ast) * RATE, melta(COLD, res, True, ast) * RATE,
        melta(HOT, res, False, ast) * RATE, melta(HOT, res, True, ast) * RATE))

print()
print("| pack boss | melta hot today | hot, flat ignored | hot dps today -> ignored |")
print("|---|---|---|---|")
for label, res in BOSSES.items():
    print("| %s | %.2f | %.2f | %.1f -> %.1f |" % (
        label, melta(HOT, res, False), melta(HOT, res, True),
        melta(HOT, res, False) * RATE, melta(HOT, res, True) * RATE))

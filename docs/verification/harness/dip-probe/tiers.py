import json

# vanilla 2.1.23 per-level modifiers (parsed out of base/prototypes/technology.lua)
fire_levels = [0.2, 0.2, 0.2, 0.3, 0.3, 0.4]   # refined-flammables-N: ammo-damage(flamethrower) == turret-attack(flamethrower-turret)
rate_levels = [0.1, 0.2, 0.2, 0.3, 0.3, 0.4]   # weapon-shooting-speed-N: gun-speed(bullet)
bullet_dmg  = [0.1, 0.1, 0.2, 0.2, 0.2, 0.4]   # physical-projectile-damage-N: ammo-damage(bullet) == turret-attack(gun-turret) for 1..6

COLD, HOT = 32.0, 56.0
COOLDOWN   = 8          # ticks
RATE0      = 60.0 / COOLDOWN     # 7.5 pulses/s
FIRE_SHARE = 0.85
GUN_URANIUM = 24.0
GUN_RATE    = 10.0      # shots/s
TESLA       = 120.0 * 0.5

rows = []
fa = ra = ba = 0.0
for tier in range(0, 7):
    if tier > 0:
        fa += fire_levels[tier - 1]
        ra += rate_levels[tier - 1]
        ba += bullet_dmg[tier - 1]
    rate_mult = 1 + ra                       # pulse clock shortened by gun-speed
    single = 1 + fa
    double = (1 + fa) ** 2
    fireonly = (FIRE_SHARE * (1 + fa) + (1 - FIRE_SHARE))   # only the 85 % fire share scales
    fireonly_double = (FIRE_SHARE * (1 + fa) ** 2 + (1 - FIRE_SHARE))

    def dps(pulse_mult):
        return COLD * pulse_mult * RATE0 * rate_mult, HOT * pulse_mult * RATE0 * rate_mult

    s_c, s_h = dps(single)
    d_c, d_h = dps(double)
    fo_c, fo_h = dps(fireonly_double)
    none_c, none_h = dps(1.0)
    gun = GUN_URANIUM * (1 + ba) ** 2 * GUN_RATE * rate_mult

    rows.append(dict(tier=tier, fire=fa, rate=ra, bullet=ba,
                     pulse_single_cold=COLD * single, pulse_single_hot=HOT * single,
                     pulse_double_cold=COLD * double, pulse_double_hot=HOT * double,
                     dps_none=(none_c, none_h),
                     dps_single=(s_c, s_h), dps_double=(d_c, d_h),
                     dps_fireonly_double=(fo_c, fo_h),
                     gun_uranium=gun))

hdr = "| tier | fire dmg | rate | pulse cold S/D | pulse hot S/D | dps cold S/D | dps hot S/D | gun turret (uranium) |"
print(hdr)
print("|---|---|---|---|---|---|---|---|")
for r in rows:
    print("| %d | +%d%% | +%d%% | %.1f / %.1f | %.1f / %.1f | %.0f / %.0f | %.0f / %.0f | %.0f |" % (
        r["tier"], round(r["fire"] * 100), round(r["rate"] * 100),
        r["pulse_single_cold"], r["pulse_double_cold"],
        r["pulse_single_hot"], r["pulse_double_hot"],
        r["dps_single"][0], r["dps_double"][0],
        r["dps_single"][1], r["dps_double"][1],
        r["gun_uranium"]))

print()
print("no-scaling (today, HEAD): cold %.0f dps, hot %.0f dps" % rows[0]["dps_none"])
print()
print("double dip, fire-share-only variant (85 %% of pulse scaled):")
for r in rows:
    print("  tier %d: cold %.0f dps, hot %.0f dps  (vs whole-pulse %.0f / %.0f)" % (
        r["tier"], r["dps_fireonly_double"][0], r["dps_fireonly_double"][1],
        r["dps_double"][0], r["dps_double"][1]))

print()
print("double-dip / single-dip damage ratio per tier:",
      ", ".join("%.2fx" % (r["dps_double"][0] / r["dps_single"][0]) for r in rows))
print("melta single-dip vs gun turret ratio:",
      ", ".join("%.2f" % (r["dps_single"][0] / r["gun_uranium"]) for r in rows))
print("melta double-dip vs gun turret ratio:",
      ", ".join("%.2f" % (r["dps_double"][0] / r["gun_uranium"]) for r in rows))
print("gun turret dps by tier:", ", ".join("%.0f" % r["gun_uranium"] for r in rows))
print("tesla single-target dps (no research):", TESLA)

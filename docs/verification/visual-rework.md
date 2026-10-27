# Visual rework (0.6.0): art placement, beam core, beam end, layering, spin-up gauge

All of this was driven by playtest feedback on 0.5.2. Everything below was photographed in
the real GUI build (2.1.23) with the same scene rendered twice: once from `git archive HEAD`
(0.5.2) and once from the working tree. Probe: `docs/verification/harness/` scene in the
`ftest-vis-*` run directories; 14 shots per pass, both passes complete with no Lua errors.

## 1. The turret now stands on its own tile

`C.sprite_shift = {0, 0.5}` — both the hull (`base` sprite) and the cannon (head sheet)
are drawn half a tile further DOWN the screen. `shift` on a sprite is in **tiles**, `+y`
is south, and it does not rotate with the sprite (`rotate_shift` unset).

Measured proof that both moved, and that they moved together: cross-correlating the
before/after screenshots at zoom 2 (64 px/tile) puts the hull shift at **32 px = 0.5 tiles**
and the head at the same offset (a control run with the head at `{0, 2.0}` visibly drops
the gun onto the front rim of the deck, which is what proves the engine honours a
`shift` inside an `Animation`'s layers at all — the first attempt at this change silently
only reached the hull, and the playtest caught it).

`muzzle_point()` adds the same two numbers, so the lance leaves the mouth the player can
see; `drawing_box_vertical_extension` went 0.5 → 1.0 because the art now reaches half a
tile further south than the collision box.

**The pipe stubs do NOT move** (asked for explicitly). They are engine-drawn at each
`pipe_connections` point, in entity space, and they belong to the tile grid — moving them
with the art would slide them off the pipes they connect to. The cost is visible and
deliberate: at 0.5 the north port's stub loses half a tile of overlap with the hull, so
the north junction is looser than it was, while the south junction (which used to show raw
ground between the stub and the front rim) now tucks under the hull properly. See
`01-alignment-before-after.jpg`. The ports themselves are untouched: no existing build
disconnects.

## 2. The beam core is a sprite, not a `draw_line`

Two problems, one cause:

* `rendering.draw_line` has **no `render_layer` parameter** (2.1.23 parameter list:
  `color, width, gap_length, dash_length, dash_offset, from, to, surface, time_to_live,
  blink_interval, forces, players, visible, draw_on_ground, only_in_alt_mode, tall,
  render_mode`). It renders on a fixed engine layer. The glow sprites obeyed
  `render_layer = "projectile"`. With a smog mod installed that showed as the core drawing
  in FRONT of the smoke while the rest of the lance sat behind it.
* A line is a hard-edged quad: it read as a graph line at any zoom, and it ended flat.

So the core is now `graphics/entity/melta-beam/beam-core.png` (1 × 8 tiles, soft across,
the top 28 % fading to nothing) drawn as two additive layers — an outer fuel-tinted one and
an inner one mixed 70 % toward white — on the same layer as everything else. `draw_line`
no longer appears anywhere in the mod's runtime code. Proof: `rendering.get_all_objects
("lilys-melta")` for three firing turrets contains no line object at all, and the smog
inconsistency cannot recur because there is only one layer left to disagree with.

## 3. The lance no longer stops dead at maximum range

`C.beam_dissipate` carries a soft spray plume (`beam-spray.png`, 2 × 4 tiles, ragged noise
and holes) past the tip — 1.2 tiles at cold, 2.6 at white hot — and the last two of the six
sheath tongues are rolled to start at 84-100 % of the length and run past the end. Compare
`02-far-end-before-after.jpg`: before is a square-cut tip, after frays and thins out.

The flare that used to be the only thing at the end is still there, inside the plume.

## 4. Firing away from the camera: start the lance past the gun, not behind it

The first attempt drew the whole lance on `"object-under"` (122) when the barrel pointed
away from the camera. That works against the turret and is **wrong against everything
else**: the lance then rendered behind every biter nest, wall and tree along its length
(playtest: "very bad"). Render layers cannot express "behind this one entity".

So everything stays on `"projectile"` (157) and the *drawn* lance starts
`C.beam_away_offset` (0.55 tiles) further down the barrel whenever the beam points away
(20° off north, `C.beam_behind_dot`). The muzzle flare and the near end of the haze then
sit past the gun's silhouette instead of burning over it — `03-muzzle-behind-gun.jpg`:
before, the flare washes the barrel out; after, the barrel edge stays clean.

Only the drawing moves. The mouth, the damage corridor and the reach are still the
turret's real geometry, and the beam is still in front of the nest it lands in
(`05-beam-vs-nest.jpg`).

## 5. Spin-up gauge

Five additive lights on the hull deck (`C.spin_leds`), filled in order as `charge` climbs
and emptied in reverse as it falls, tinted with the burning fuel's sheath colour and mixed
toward white as each one comes up. Placed on an **ellipse** (y squashed by `cos(camera
tilt)`, whole ring lifted `C.spin_led_lift` up-screen) because the camera is pitched, and
drawn at `"higher-object-above"` so they sit on the hull rather than under it.

The first pass used six 0.26-tile lights and read as sparkle next to the model's own gauge
lights; five 0.34-tile lights at radius 1.0 is what the shots in `04-spin-up-gauge.jpg`
show. Count at charge ~0.12 / ~0.55 / 1.0 / cooling: 1 / 3 / 5 / falling.

Two smaller fixes in the same area: the emitter's bleed-off glow is now re-anchored to the
mouth every idle tick (it used to stay where the last shot was fired and read as a glowing
disc floating beside the gun once the head turned), and the mouth glow is tinted from the
same `fuel_profile` as the lance.

## What is still open

* The north pipe stub gap described in §1 — closing it means moving the port, which would
  disconnect already-placed turrets. Left as a deliberate trade.
* The gauge is a hint, not a HUD: at map zoom it is a few pixels. If it needs to be
  unmistakable, `C.spin_led_*` is the whole dial (count, size, radius, lift, whiteness).
* No smog/weather mod was installed in the verification run (none is required to load the
  melta); the layering fix was proved structurally — one layer, no line objects — rather
  than against a specific smoke mod's art.

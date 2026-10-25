"""Assemble the pipe-port sprites from the Blender renders (pipe_port.py).

Same three steps the turret sheets get (graphics/_blender/assemble.py), reused
rather than copied so the port sits in the same tone register and the same light:

 1. downscale the 4x supersampled render in premultiplied alpha
 2. the fitted tone curve (so the port's greys match the hull's)
 3. bake a cast shadow from its own silhouette, offset to the lower right

No de-squash here: only the hull base layer is stretched in Y. The port is drawn at
the connection point with `shift = {0, 0}`, so the frame centre must stay the
connection point, i.e. nothing may move the art inside the frame.

Run:  python assemble_port.py <raw_dir> [--out <mod root>]
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import assemble                      # tone curve, shadow bake, helpers
from PIL import Image                # noqa: E402

FRAME = 128                          # 64 art px/tile at scale 0.5, like the rest
SIDES = ("north", "east", "south", "west")
KINDS = (("open", "port"), ("cap", "cap"))

# assemble.load_frame() downsamples to its module-level FRAME; point it here so the
# whole tone/shadow path is the turret's own code instead of a second copy.
assemble.FRAME = FRAME


def main(argv):
    raw = argv[0] if argv and not argv[0].startswith("--") else "raw_pipe"
    out = HERE
    if "--out" in argv:
        out = argv[argv.index("--out") + 1]
    tex = os.path.join(out, "graphics", "entity", "melta-turret")
    os.makedirs(tex, exist_ok=True)

    written = []
    for kind, prefix in KINDS:
        for side in SIDES:
            src = os.path.join(raw, "port", "{}-{}.png".format(kind, side))
            rgb, alpha = assemble.load_frame(src, desquash_y=1.0)
            rgb = assemble.apply_curve(rgb) / 255.0
            rgb, alpha = assemble.compose(rgb, alpha, with_shadow=True)
            name = "melta-pipe-{}-{}.png".format(prefix, side)
            assemble.to_image(rgb, alpha).save(os.path.join(tex, name), optimize=True)
            written.append(name)
    print("wrote", len(written), "sprites into", tex)
    for name in written:
        im = Image.open(os.path.join(tex, name))
        print("  {:34s} {}x{}".format(name, im.width, im.height))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

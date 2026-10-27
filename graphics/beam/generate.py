"""Generate the melta's beam textures.

These are the soft, additive-looking layers of the beam: the engine's
`rendering.draw_line` can only draw a flat coloured quad, so everything that has to
*glow* is a sprite. All of them are white with the shape in the alpha channel --
the runtime tints them with the fuel colour (`rendering.draw_sprite.tint`), so one
set of textures serves every fuel (light oil orange, gas blue, melta green, napalm
red).

Orientation contract, and the reason every long texture here is a TALL one:
`rendering.draw_sprite` rotates about the sprite's centre and treats orientation 0
as "north", i.e. the image is drawn unrotated and the beam's forward direction is
the TOP of the image. So a beam layer is authored pointing up, and the runtime sets
`orientation = atan2(dx, -dy) / 2pi`. Sizes below are the natural footprint at
scale 1 (32 px per tile), so a 64x256 image is 2 x 8 tiles.

Everything is power-of-two in both axes so the atlas and the mipmaps stay clean.

Run:  python graphics/beam/generate.py
Writes: graphics/entity/melta-beam/*.png  and  graphics/beam/preview.png
"""

import os

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
MOD = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(MOD, "graphics", "entity", "melta-beam")


def grid(w, h):
    """Pixel-centre coordinates as -1..1 on both axes (u across, v down)."""
    y, x = np.mgrid[0:h, 0:w].astype(np.float64)
    u = (x + 0.5) / w * 2.0 - 1.0
    v = (y + 0.5) / h * 2.0 - 1.0
    return u, v


def smoothstep(t):
    t = np.clip(t, 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def taper_ends(v, margin):
    """1 in the middle of the texture, smoothly 0 at both tips."""
    if margin <= 0:
        return np.ones_like(v)
    return smoothstep((1.0 - np.abs(v)) / margin)


def streak_noise(w, h, seed, amount, cells=(6, 40)):
    """Low-frequency vertical streaking: plasma is not a smooth gradient."""
    rng = np.random.default_rng(seed)
    small = rng.random(cells)
    img = Image.fromarray((small * 255).astype(np.uint8), "L").resize((w, h), Image.BICUBIC)
    noise = np.asarray(img).astype(np.float64) / 255.0
    noise = noise - noise.mean()
    return 1.0 + noise * amount


def save(name, alpha):
    a = np.clip(alpha, 0.0, 1.0)
    h, w = a.shape
    rgba = np.empty((h, w, 4), dtype=np.uint8)
    rgba[..., 0:3] = 255                      # white; the runtime tints it
    rgba[..., 3] = np.round(a * 255.0).astype(np.uint8)
    path = os.path.join(OUT, name + ".png")
    Image.fromarray(rgba, "RGBA").save(path, optimize=True)
    return path


def haze():
    """Wide, very soft outer heat column (2 x 8 tiles at scale 1)."""
    w, h = 64, 256
    u, v = grid(w, h)
    body = np.exp(-((u / 0.62) ** 2) * 1.5)
    a = body * taper_ends(v, 0.14) * streak_noise(w, h, 7, 0.22)
    return save("beam-haze", a * 0.62)


def glow():
    """The bright gas around the cutting line (2 x 8 tiles at scale 1)."""
    w, h = 64, 256
    u, v = grid(w, h)
    body = np.exp(-((u / 0.30) ** 2) * 1.35)
    a = body * taper_ends(v, 0.07) * streak_noise(w, h, 11, 0.18)
    return save("beam-glow", a * 0.95)


def tongue():
    """One boiling plasma tongue of the sheath (1 x 2 tiles at scale 1)."""
    w, h = 32, 64
    u, v = grid(w, h)
    body = np.exp(-(((u / 0.55) ** 2) + ((v / 0.70) ** 2)) * 1.4)
    a = body * taper_ends(v, 0.30) * streak_noise(w, h, 23, 0.35)
    return save("beam-tongue", a * 0.85)


def flare():
    """Muzzle/impact burst: hot core, soft halo, six rays (4 x 4 tiles)."""
    w, h = 128, 128
    u, v = grid(w, h)
    r = np.sqrt(u * u + v * v)
    theta = np.arctan2(v, u)
    core = np.exp(-((r / 0.20) ** 2) * 2.0)
    halo = np.exp(-((r / 0.52) ** 2) * 1.6) * 0.55
    rays = np.zeros_like(r)
    for k in range(6):
        angle = k * np.pi / 3.0 + 0.22
        d = np.abs(np.arctan2(np.sin(theta - angle), np.cos(theta - angle)))
        rays += np.exp(-((d / 0.13) ** 2) * 1.2) * np.exp(-((r / 0.85) ** 2) * 1.5)
    a = (core + halo + rays * 0.55) * smoothstep((1.0 - r) / 0.10)
    return save("beam-flare", a * 0.95)


def cone():
    """Muzzle blast cone: apex at the mouth (bottom), widening away (2 x 4 tiles)."""
    w, h = 64, 128
    u, v = grid(w, h)
    # t = 0 at the mouth (bottom of the image), 1 at the far tip (top)
    t = (1.0 - v) * 0.5
    half = 0.10 + 0.80 * np.power(t, 0.65)
    edge = smoothstep((half - np.abs(u)) / np.maximum(half * 0.55, 1e-6))
    along = np.power(1.0 - t, 1.1) * smoothstep(t / 0.06) * smoothstep((1.0 - t) / 0.10)
    a = edge * along * streak_noise(w, h, 31, 0.25)
    return save("beam-cone", a * 0.85)


def core():
    """The cutting column (1 x 8 tiles at scale 1). Soft across, and it DIES at the far
    end: the top 28 % of the texture fades out, which is what stops the lance from
    ending on a ruled edge when it reaches the turret's maximum range. The bottom 5 %
    is a short fade so the muzzle end does not show a square corner either."""
    w, h = 32, 256
    u, v = grid(w, h)
    across = np.exp(-((u / 0.42) ** 2) * 1.7)
    far = smoothstep((v + 1.0) / 0.28)        # v = -1 is the far end (top)
    near = smoothstep((1.0 - v) / 0.05)
    a = across * far * near * streak_noise(w, h, 41, 0.12)
    return save("beam-core", a)


def spray():
    """Where the lance runs out of reach: a ragged plume that widens and dissolves
    (2 x 4 tiles at scale 1, apex at the bottom = the end of the beam). Deliberately
    NO hard edge anywhere -- this is the layer that has to read as heat losing
    pressure, so it is mostly holes and noise rather than a cone."""
    w, h = 64, 128
    u, v = grid(w, h)
    t = (1.0 - v) * 0.5                        # 0 at the apex, 1 at the open end
    half = 0.18 + 0.78 * np.power(t, 0.7)
    edge = smoothstep((half - np.abs(u)) / np.maximum(half * 0.8, 1e-6))
    body = np.power(1.0 - t, 1.7) * smoothstep(t / 0.10)
    rng = np.random.default_rng(57)
    holes = rng.random((h // 4, w // 4))
    holes = np.asarray(Image.fromarray((holes * 255).astype(np.uint8), "L")
                       .resize((w, h), Image.BICUBIC)).astype(np.float64) / 255.0
    a = edge * body * (0.45 + 0.75 * holes)
    return save("beam-spray", a)


def preview():
    """Contact sheet: every texture at its natural footprint, on dark ground, in fuel
    orange -- i.e. what the game will show at scale 1, 32 px per tile."""
    tiles = 32
    sheet = Image.new("RGB", (1180, 300), (18, 18, 20))
    x = 16
    # long layers, drawn the way the runtime draws them: 8 tiles long, this wide
    for name, width_tiles in (("beam-haze", 3.0), ("beam-glow", 1.4),
                              ("beam-cone", 1.6), ("beam-core", 0.5),
                              ("beam-spray", 1.4)):
        img = Image.open(os.path.join(OUT, name + ".png")).convert("RGBA")
        w_px, h_px = int(round(width_tiles * tiles)), 8 * tiles
        scaled = img.resize((w_px, h_px), Image.BICUBIC)
        tint = Image.new("RGBA", scaled.size, (255, 150, 40, 255))
        tinted = Image.composite(tint, Image.new("RGBA", scaled.size, (0, 0, 0, 0)),
                                 scaled.getchannel("A"))
        tinted.putalpha(scaled.getchannel("A"))
        sheet.paste(tinted, (x, 16), tinted)
        x += w_px + 20
    for name, size in (("beam-flare", 128), ("beam-tongue", 96)):
        img = Image.open(os.path.join(OUT, name + ".png")).convert("RGBA").resize((size, size), Image.BICUBIC)
        tint = Image.new("RGBA", img.size, (255, 150, 40, 255))
        tinted = Image.composite(tint, Image.new("RGBA", img.size, (0, 0, 0, 0)), img.getchannel("A"))
        tinted.putalpha(img.getchannel("A"))
        sheet.paste(tinted, (x, 16), tinted)
        x += size + 20
    sheet.save(os.path.join(HERE, "preview.png"))
    return os.path.join(HERE, "preview.png")


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    paths = [haze(), glow(), core(), tongue(), flare(), cone(), spray()]
    for p in paths:
        print(p)
    print(preview())

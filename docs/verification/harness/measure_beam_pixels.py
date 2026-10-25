"""Measure the beam before vs after from the probe screenshots (no eyeballing).

Both runs shot the same scene at the same zoom from the same camera, so the beam is
comparable as pixels: how wide it is, how bright, and how much light it puts on the
ground around it.

The baseline is the row's MEDIAN, not its minimum, and the headline number is the FWHM
(full width at half the peak's contrast) -- a concrete floor has bright speckles that are
wider than a hairline beam, so a fixed 10%-of-peak threshold measures that noise instead
of the beam. Both widths are reported so nothing is hidden.

Run: python measure_beam_pixels.py <before_dir> <after_dir>
"""
import os
import statistics
import sys

from PIL import Image

CENTER_Y = 540          # 1080 px tall shot: row 540 is the camera's centre
CAMERA_Y = 196.0        # 01-single-close was shot with the camera at {0, Y - 4}
ZOOM = 2.0              # 01-single-close was shot at zoom 2
PX_PER_TILE = 32 * ZOOM


def row_values(lum, y):
    px = lum.load()
    width = lum.size[0]
    return [px[x, y] for x in range(width)]


def width_at(values, baseline, peak, fraction):
    """Width of the run around the peak that stays above baseline + fraction*contrast."""
    threshold = baseline + (peak - baseline) * fraction
    index = values.index(peak)
    left = index
    while left > 0 and values[left - 1] >= threshold:
        left -= 1
    right = index
    while right < len(values) - 1 and values[right + 1] >= threshold:
        right += 1
    return right - left + 1


def measure(path, label):
    lum = Image.open(path).convert("L")
    world_ys = [197.5, 196.0, 194.5]     # pure beam: muzzle at 199, dummy body at 191.5
    rows = [int(CENTER_Y + (y - CAMERA_Y) * PX_PER_TILE) for y in world_ys]
    print("%s  (%s)" % (label, os.path.basename(path)))
    summary = []
    for y in rows:
        values = row_values(lum, y)
        baseline = statistics.median(values)
        peak = max(values)
        fwhm = width_at(values, baseline, peak, 0.5)
        tenth = width_at(values, baseline, peak, 0.10)
        light = sum(max(0, v - baseline) for v in values)
        summary.append((fwhm / PX_PER_TILE, tenth / PX_PER_TILE, peak, light))
        print("  row %4d  median=%3d peak=%3d  FWHM=%3d px = %.2f tiles"
              "   10%%-width=%3d px = %.2f tiles   light=%d"
              % (y, baseline, peak, fwhm, fwhm / PX_PER_TILE, tenth, tenth / PX_PER_TILE, light))
    mean = [sum(s[i] for s in summary) / len(summary) for i in range(4)]
    print("  mean: FWHM=%.2f tiles  10%%-width=%.2f tiles  peak=%.0f  light=%.0f"
          % tuple(mean))
    return mean


def main(dirs):
    results = []
    for run in dirs:
        path = os.path.join(run, "write", "script-output", "beam", "01-single-close.png")
        if not os.path.exists(path):
            print("missing", path)
            continue
        results.append(measure(path, run))
    if len(results) == 2:
        before, after = results
        print("\nafter/before: FWHM x%.2f   10%%-width x%.2f   peak x%.2f   light x%.2f"
              % (after[0] / before[0], after[1] / before[1], after[2] / before[2],
                 after[3] / before[3]))


main(sys.argv[1:])

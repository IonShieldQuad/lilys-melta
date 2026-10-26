"""Hover the quickbar's *upper* row and photograph the item tooltip.

The first sweep hovered 34 px above the bottom edge, which is the quickbar's lower row
(2.1 stacks two rows of 10); the melta sits in the upper row, slot 1. Two facts from
the first pass, both used here:

  * the item is in the upper row of the quickbar, first slot (a stack of 5);
  * the hovered slot in the lower row at x=768 was the leftmost, so slot 1 of the
    upper row is at the same x.

The tooltip itself is easy to find without matching style data: it is a dark panel
(background well under luminance 60) over the probe's light refined-concrete floor, so
each candidate is scored by "how many near-black pixels appeared in the band above the
bar" against a baseline grab.

Usage: python capture_quickbar.py <env dir> <out dir>
"""
import ctypes
import ctypes.wintypes as wt
import os
import re
import subprocess
import sys
import time

from PIL import Image, ImageChops, ImageGrab

user32 = ctypes.windll.user32
k32 = ctypes.windll.kernel32
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    pass

EXE = r"E:/SteamLibrary/steamapps/common/Factorio/bin/x64/Factorio.exe"
ENVVARS = dict(os.environ, SteamAppId="427520", SteamGameId="427520", SteamOverlayGameId="427520")
WM_CLOSE = 0x0010
PROCESS_TERMINATE = 0x0001
VIRTUAL_LEFT = 76
VIRTUAL_TOP = 77


def log(msg):
    print(msg, flush=True)


def windows():
    out = []

    @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    def cb(h, l):
        if user32.IsWindowVisible(h):
            n = user32.GetWindowTextLengthW(h)
            if n:
                buf = ctypes.create_unicode_buffer(n + 1)
                user32.GetWindowTextW(h, buf, n + 1)
                out.append((h, buf.value))
        return True

    user32.EnumWindows(cb, 0)
    return out


def pid_of(hwnd):
    pid = wt.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value


def window_for_pid(pid):
    for h, title in windows():
        if pid_of(h) == pid:
            return h, title
    return None, None


def client_rect(hwnd):
    r = wt.RECT()
    user32.GetClientRect(hwnd, ctypes.byref(r))
    tl = wt.POINT(0, 0)
    user32.ClientToScreen(hwnd, ctypes.byref(tl))
    return tl.x, tl.y, r.right - r.left, r.bottom - r.top


def click(x, y):
    user32.SetCursorPos(int(x), int(y))
    time.sleep(0.1)
    user32.mouse_event(2, 0, 0, 0, 0)
    time.sleep(0.05)
    user32.mouse_event(4, 0, 0, 0, 0)


def activate(hwnd, cx, cy):
    for attempt in range(6):
        user32.ShowWindow(hwnd, 9)
        user32.BringWindowToTop(hwnd)
        user32.SetForegroundWindow(hwnd)
        time.sleep(0.4)
        if user32.GetForegroundWindow() == hwnd:
            return True
        click(cx, cy)
        time.sleep(0.6)
        if user32.GetForegroundWindow() == hwnd:
            return True
        log("  activate attempt %d failed" % (attempt + 1))
    return False


def grab():
    return ImageGrab.grab(all_screens=True).convert("RGB")


def dark_pixels(image, box, threshold=70):
    """Near-black pixels in `box` (image coords): a tooltip's flat background."""
    crop = image.crop(tuple(int(v) for v in box)).convert("L")
    histogram = crop.histogram()
    return sum(histogram[:threshold])


def changed_pixels(a, b, box):
    delta = ImageChops.difference(a.crop(tuple(int(v) for v in box)),
                                  b.crop(tuple(int(v) for v in box)))
    return sum(1 for pixel in delta.getdata() if pixel != (0, 0, 0))


def main():
    env = sys.argv[1].replace("\\", "/")
    out = sys.argv[2].replace("\\", "/")
    os.makedirs(out, exist_ok=True)
    logpath = env + "/write/factorio-current.log"
    if os.path.exists(logpath):
        os.remove(logpath)
    lock = env + "/write/.lock"
    if os.path.exists(lock):
        os.remove(lock)

    proc = subprocess.Popen([EXE, "--config", env + "/config.ini",
                             "--mod-directory", env + "/mods",
                             "--load-game", env + "/write/scene.zip"],
                            env=ENVVARS, stdout=open(env + "/out/gui2.out", "w"),
                            stderr=subprocess.STDOUT)
    log("launched pid %d" % proc.pid)

    deadline = time.time() + 900
    hwnd = None
    while time.time() < deadline and hwnd is None:
        hwnd, title = window_for_pid(proc.pid)
        if hwnd is None:
            time.sleep(1.0)
    if hwnd is None:
        log("FATAL: no window owned by pid %d" % proc.pid)
        proc.terminate()
        return 1

    x, y, w, h = client_rect(hwnd)
    log("window %r pid %d client %d,%d %dx%d" % (title, proc.pid, x, y, w, h))
    cx, cy = x + w // 2, y + h // 2

    ready = False
    while time.time() < deadline and not ready:
        try:
            text = open(logpath, encoding="utf-8", errors="replace").read()
        except FileNotFoundError:
            time.sleep(0.5)
            continue
        ready = re.search(r"\[localeprobe\] READY zoom=", text) is not None
        if not ready:
            time.sleep(0.5)
    log("probe ready=%s" % ready)
    if not ready:
        user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
        return 2

    if not activate(hwnd, cx, cy):
        log("!! could not take focus")
    time.sleep(1.0)

    # ---- entity hover: the inspect panel, first -------------------------------
    match = re.search(r"\[localeprobe\] READY zoom=([\d.]+) dy=(\d+)",
                      open(logpath, encoding="utf-8", errors="replace").read())
    dy = int(match.group(2)) if match else 96
    subject_y = cy - dy
    for i in (1, 2):
        user32.SetCursorPos(int(cx) + 10, int(subject_y) + 8)
        time.sleep(0.35)
        user32.SetCursorPos(int(cx), int(subject_y))
        time.sleep(2.2)
        path = "%s/entity_hover_%d.png" % (out, i)
        grab().save(path)
        log("  saved %s" % path)
        time.sleep(0.5)

    vleft = user32.GetSystemMetrics(VIRTUAL_LEFT)
    vtop = user32.GetSystemMetrics(VIRTUAL_TOP)

    # park the cursor away from every slot and take the reference frame
    user32.SetCursorPos(int(cx), int(cy))
    time.sleep(1.0)
    baseline = grab()
    baseline.save("%s/item_baseline.png" % out)

    candidates = []
    for row_y in (h - 88, h - 96, h - 80):
        for dx in (-204, -192, -180, -168, -156):
            candidates.append((cx + dx, y + row_y))

    results = []
    for index, (px, py) in enumerate(candidates):
        user32.SetCursorPos(int(px) + 6, int(py) + 6)
        time.sleep(0.25)
        user32.SetCursorPos(int(px), int(py))
        time.sleep(1.6)
        shot = grab()
        name = "%s/item_hover_%02d_x%d_y%d.png" % (out, index, px, py)
        shot.save(name)
        band = (px - vleft - 400, py - vtop - 520, px - vleft + 380, py - vtop - 30)
        dark = dark_pixels(shot, band) - dark_pixels(baseline, band)
        moved = changed_pixels(baseline, shot, band)
        results.append((dark, moved, index, name))
        log("  hover %d at (%d,%d): dark+%d changed=%d" % (index, px, py, dark, moved))

    results.sort(reverse=True)
    log("ranking (dark pixels gained, changed pixels, index, path):")
    for row in results[:6]:
        log("   %d  %d  %d  %s" % row)

    log("closing pid %d" % proc.pid)
    user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
    end = time.time() + 25
    while time.time() < end and proc.poll() is None:
        time.sleep(0.5)
    if proc.poll() is None:
        handle = k32.OpenProcess(PROCESS_TERMINATE, False, proc.pid)
        if handle:
            k32.TerminateProcess(handle, 1)
            k32.CloseHandle(handle)
            log("terminated pid %d" % proc.pid)
    return 0


if __name__ == "__main__":
    sys.exit(main())

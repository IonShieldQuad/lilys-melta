"""Photograph the melta's tooltips in a real GUI run.

Why the OS mouse: a tooltip only exists under the real cursor, and
`game.take_screenshot` never contains one. The window is matched by *process id*,
never by title -- another Factorio instance can be alive on this machine and a title
match would silently photograph someone else's game.

Usage: python capture.py <env dir> <out dir>

The probe (melta-locale-probe/control.lua) logs
`[localeprobe] READY zoom=<z> dy=<px between camera centre and turret>` and puts the
melta in quickbar slot 1, which gives two deterministic hovers:

  1. the turret entity, dy pixels above the camera centre  -> entity tooltip
  2. quickbar slot 1, a horizontal sweep along the bottom  -> item tooltip

The quickbar's exact slot width is style data the script API does not expose, so the
sweep photographs ~17 candidate x positions and ranks them by how much the region
*above* the bar changed against a baseline grab: a tooltip is a big opaque panel, so
the hovered slot wins by a wide margin. The ranking is printed and every frame kept.
"""
import ctypes
import ctypes.wintypes as wt
import os
import re
import subprocess
import sys
import time

from PIL import ImageChops, ImageGrab

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
# the grab spans the whole virtual desktop (here: two monitors), so screen coords
# need the desktop's own origin, not the window's
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


def diff_pixels(a, b, box):
    """How many pixels of the region `box` (image coords) changed."""
    box = tuple(int(v) for v in box)
    delta = ImageChops.difference(a.crop(box), b.crop(box))
    return sum(1 for pixel in delta.getdata() if pixel != (0, 0, 0))


def main():
    env = sys.argv[1].replace("\\", "/")
    out = sys.argv[2].replace("\\", "/")
    os.makedirs(out, exist_ok=True)
    logpath = env + "/write/factorio-current.log"
    if os.path.exists(logpath):
        os.remove(logpath)

    proc = subprocess.Popen([EXE, "--config", env + "/config.ini",
                             "--mod-directory", env + "/mods",
                             "--load-game", env + "/write/scene.zip"],
                            env=ENVVARS, stdout=open(env + "/out/gui.out", "w"),
                            stderr=subprocess.STDOUT)
    log("launched pid %d" % proc.pid)

    deadline = time.time() + 420
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

    ready, dy = False, 96
    while time.time() < deadline and not ready:
        try:
            text = open(logpath, encoding="utf-8", errors="replace").read()
        except FileNotFoundError:
            time.sleep(0.5)
            continue
        match = re.search(r"\[localeprobe\] READY zoom=([\d.]+) dy=(\d+)", text)
        if match:
            ready = True
            dy = int(match.group(2))
            log("  probe ready, zoom=%s dy=%d" % (match.group(1), dy))
        else:
            time.sleep(0.5)
    log("probe ready=%s" % ready)
    if not ready:
        user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
        return 2

    if not activate(hwnd, cx, cy):
        log("!! could not take focus")
    user32.SetCursorPos(int(cx) + 20, int(cy) - dy + 20)
    time.sleep(0.6)

    subject_y = cy - dy
    shots = []
    for i in range(1, 3):
        # a hover only registers on a mouse *move* into the entity
        user32.SetCursorPos(int(cx) + 10, int(subject_y) + 8)
        time.sleep(0.35)
        user32.SetCursorPos(int(cx), int(subject_y))
        time.sleep(2.2)
        if user32.GetForegroundWindow() != hwnd:
            log("  reactivating before shot %d" % i)
            activate(hwnd, cx, cy)
            user32.SetCursorPos(int(cx), int(subject_y))
            time.sleep(2.2)
        path = "%s/entity_tooltip_%d.png" % (out, i)
        grab().save(path)
        shots.append(path)
        log("  saved %s" % path)
        time.sleep(0.6)

    # ---- 2. item tooltip: quickbar slot 1 (the probe set it) ----------------
    bar_y = y + h - 34
    user32.SetCursorPos(int(cx), int(cy) - 200)      # park: no tooltip anywhere
    time.sleep(0.9)
    baseline = grab()
    baseline.save("%s/quickbar_baseline.png" % out)

    # the grab spans the whole virtual desktop, so shift by its left/top edge
    vleft = user32.GetSystemMetrics(VIRTUAL_LEFT)
    vtop = user32.GetSystemMetrics(VIRTUAL_TOP)
    band = (x - vleft + 30, y - vtop + 40, x - vleft + w - 30, bar_y - vtop - 25)

    sweep = []
    for step in range(-8, 9):
        px = cx + step * 24
        user32.SetCursorPos(int(px), int(bar_y))
        time.sleep(0.75)
        shot = grab()
        path = "%s/quickbar_x%+04d.png" % (out, step)
        shot.save(path)
        value = diff_pixels(baseline, shot, band)
        sweep.append((value, step, path))
        log("  quickbar sweep x=%d diff=%d" % (px, value))

    sweep.sort(reverse=True)
    log("quickbar ranking (diff, step, path):")
    for row in sweep[:5]:
        log("   %d  %+d  %s" % row)

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

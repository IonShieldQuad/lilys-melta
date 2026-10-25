"""Launch the staged Factorio env, focus its own window, park the OS cursor on
whatever the harness is pointing the camera at, and screenshot the tooltip.

Two things make this necessary rather than nice-to-have:
  * `game.take_screenshot` never contains a tooltip, and a tooltip only appears under
    the real mouse cursor, so the cursor has to be moved by the OS.
  * several Factorio instances can be alive on this machine at once (other agents run
    their own), so the window is matched by *process id*, never by title -- otherwise
    a screenshot can silently show someone else's game.

Usage: python tooltip_shots2.py <env dir> <out dir> [cycles] [dy]
"""
import ctypes
import ctypes.wintypes as wt
import os
import re
import subprocess
import sys
import time

from PIL import ImageGrab

user32 = ctypes.windll.user32
k32 = ctypes.windll.kernel32
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    pass

EXE = r"E:/SteamLibrary/steamapps/common/Factorio/bin/x64/Factorio.exe"
WM_CLOSE = 0x0010
PROCESS_TERMINATE = 0x0001
TILE = 32  # screen pixels per tile at zoom 1


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
    """Windows will not hand the foreground to a background process on request, so do
    what a user does: click into the window. The click lands on empty concrete."""
    for attempt in range(6):
        user32.ShowWindow(hwnd, 9)  # SW_RESTORE
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


def grab(path, cx, cy, half_w=560, half_h=470):
    img = ImageGrab.grab(all_screens=True)
    # the whole virtual desktop: the info panel sits at the far right of the game
    # window while the world crop is around the cursor, so keeping the full frame
    # means the panel is never cropped away by mistake
    img.save(path)
    log("  saved %s (%dx%d)" % (path, img.size[0], img.size[1]))


def main():
    env, out = sys.argv[1], sys.argv[2]
    cycles = int(sys.argv[3]) if len(sys.argv) > 3 else 1
    dy = int(sys.argv[4]) if len(sys.argv) > 4 else 2 * TILE
    logpath = os.path.join(env, "write", "factorio-current.log")
    os.makedirs(out, exist_ok=True)
    if os.path.exists(logpath):
        os.remove(logpath)

    envvars = dict(os.environ, SteamAppId="427520", SteamGameId="427520")
    args = [EXE,
            "--config", env + "/config.ini",
            "--mod-directory", env + "/mods",
            "--load-game", env + "/scene.zip"]
    proc = subprocess.Popen(args, env=envvars,
                            stdout=open(os.path.join(env, "gui.out"), "w"),
                            stderr=subprocess.STDOUT)
    log("launched pid %d" % proc.pid)

    deadline = time.time() + 300
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
    subject_y = cy - dy  # the subject sits north of the centred camera
    activate(hwnd, cx, cy)

    seen = set()
    while time.time() < deadline:
        try:
            text = open(logpath, encoding="utf-8", errors="replace").read()
        except FileNotFoundError:
            time.sleep(0.5)
            continue
        for match in re.finditer(r"\[tooltip\] HOVER_(\w+) leg=(\d+)", text):
            key, leg = match.group(1), int(match.group(2))
            if leg in seen or leg > 3 * cycles:
                continue
            seen.add(leg)
            # a hover only registers on a mouse *move* into the entity
            user32.SetCursorPos(int(cx) + 12, int(subject_y) + 12)
            time.sleep(0.2)
            user32.SetCursorPos(int(cx), int(subject_y))
            time.sleep(2.5)
            fg = user32.GetForegroundWindow()
            if fg != hwnd:
                log("  leg %d foreground %d != %d, reactivating" % (leg, fg, hwnd))
                activate(hwnd, cx, cy)
                user32.SetCursorPos(int(cx), int(subject_y))
                time.sleep(2.5)
            if leg == 1:
                full = os.path.join(out, "full_leg1.png")
                ImageGrab.grab(all_screens=True).save(full)
                log("  saved full desktop %s" % full)
            grab(os.path.join(out, "%s_leg%d.png" % (key.lower(), leg)), cx, subject_y - 140)
            time.sleep(1.5)
            grab(os.path.join(out, "%s_leg%d_b.png" % (key.lower(), leg)), cx, subject_y - 140)
        if len(seen) >= 3 * cycles:
            break
        time.sleep(0.3)

    log("captured %d legs, closing pid %d" % (len(seen), proc.pid))
    user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
    deadline = time.time() + 20
    while time.time() < deadline and proc.poll() is None:
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

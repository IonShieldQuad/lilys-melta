"""Launch the staged combined-probe env in a real GUI, photograph the inspect panel for
each quality, then let the probe's own screenshot schedule run and close the game.

Why a desktop grab: `game.take_screenshot` never contains a tooltip and a tooltip only
exists under the *real* mouse cursor. The probe logs `[tooltip] HOVER_Q_<quality> leg=N`
when its camera has settled on a subject; this script parks the OS cursor on that subject
and grabs the whole virtual desktop (the inspect panel sits at the right edge of the game
window, so any world-centred crop would cut it away).

The window is matched by process id, never by title: another Factorio instance on this
machine must never be photographed by accident.

Usage: python hover_combined.py <run dir> <out dir> [legs]
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
ENVVARS = dict(os.environ, SteamAppId="427520", SteamGameId="427520", SteamOverlayGameId="427520")
WM_CLOSE = 0x0010
PROCESS_TERMINATE = 0x0001
TILE = 32


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


def main():
    run = sys.argv[1].replace("\\", "/")
    out = sys.argv[2].replace("\\", "/")
    legs_wanted = int(sys.argv[3]) if len(sys.argv) > 3 else 5
    os.makedirs(out, exist_ok=True)
    logpath = run + "/write/factorio-current.log"
    if os.path.exists(logpath):
        os.remove(logpath)

    proc = subprocess.Popen([EXE, "--config", run + "/config.ini",
                             "--mod-directory", run + "/mods",
                             "--load-game", run + "/write/scene.zip"],
                            env=ENVVARS, stdout=open(run + "/out/gui.out", "w"),
                            stderr=subprocess.STDOUT)
    log("launched pid %d" % proc.pid)

    deadline = time.time() + 480
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
    subject_y = cy - 2 * TILE
    activate(hwnd, cx, cy)

    seen = set()
    done = False
    while time.time() < deadline and not done:
        try:
            text = open(logpath, encoding="utf-8", errors="replace").read()
        except FileNotFoundError:
            time.sleep(0.5)
            continue
        for match in re.finditer(r"\[tooltip\] HOVER_(\w+) leg=(\d+)", text):
            key, leg = match.group(1), int(match.group(2))
            if leg in seen:
                continue
            seen.add(leg)
            user32.SetCursorPos(int(cx) + 12, int(subject_y) + 12)
            time.sleep(0.3)
            user32.SetCursorPos(int(cx), int(subject_y))
            time.sleep(1.6)
            fg = user32.GetForegroundWindow()
            if fg != hwnd:
                log("  leg %d foreground %d != %d, reactivating" % (leg, fg, hwnd))
                activate(hwnd, cx, cy)
                user32.SetCursorPos(int(cx), int(subject_y))
                time.sleep(1.8)
            path = os.path.join(out, "%s_leg%d.png" % (key.lower(), leg))
            ImageGrab.grab(all_screens=True).save(path)
            log("  saved %s" % path)
            time.sleep(0.8)
            ImageGrab.grab(all_screens=True).save(path[:-4] + "_b.png")
            time.sleep(0.6)
        if "COMBINED PROBE DONE" in text:
            done = True
            break
        if len(seen) > legs_wanted:
            log("!! more legs than expected (%d)" % len(seen))
        time.sleep(0.4)

    log("legs captured=%d done=%s -> closing pid %d" % (len(seen), done, proc.pid))
    time.sleep(2)
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
    return 0 if done else 2


if __name__ == "__main__":
    sys.exit(main())

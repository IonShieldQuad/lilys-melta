"""Launch the staged env in a real GUI, drive the crafting menu, and photograph the screen.

The crafting menu cannot be opened from a scenario script (there is no API for it), so the
menu is opened with the real `E` key and photographed off the compositor. That also means
the shot has to be validated by its contents, not by the fact that a file was written.

The window is matched by process id, never by title: another Factorio instance on this
machine must never be photographed by accident.

Usage: python run_gui.py <run dir> <out dir> [plan.json]

A plan is a list of steps, run in order:
  {"action": "key", "vk": 69, "hold": 0.08}     a real key press (VK 69 = E)
  {"action": "click", "x": 640, "y": 300}       client-area click
  {"action": "move", "x": 640, "y": 300}        park the cursor (no tooltip)
  {"action": "wait", "s": 2.0}
  {"action": "type", "text": "melta"}           unicode keystrokes, for the search box
  {"action": "grab", "name": "01-menu"}          whole virtual desktop -> <out>/01-menu.png
  {"action": "log", "marker": "..."}            wait until the game log contains a marker
"""
import ctypes
import ctypes.wintypes as wt
import json
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
KEYEVENTF_KEYUP = 0x0002


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


def press(vk, hold=0.08):
    user32.keybd_event(vk, 0, 0, 0)
    time.sleep(hold)
    user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)


def type_text(text):
    for char in text:
        user32.SendMessageW(user32.GetForegroundWindow(), 0x0102, ord(char), 0)  # WM_CHAR
        time.sleep(0.05)


def main():
    run = sys.argv[1].replace("\\", "/")
    out = sys.argv[2].replace("\\", "/")
    plan_path = sys.argv[3] if len(sys.argv) > 3 else os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "plan.json")
    plan = json.load(open(plan_path))
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

    hwnd = None
    deadline = time.time() + 420
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

    # wait for the probe to hand us a character. 400 s, not 180: with space age enabled the
    # sprite atlas alone takes ~200 s to build on this machine, and a shorter deadline
    # photographs the loading screen (probe ready=False, activate fails, key E goes nowhere).
    ready = False
    ready_deadline = min(deadline, time.time() + 400)
    while time.time() < ready_deadline and not ready:
        try:
            text = open(logpath, encoding="utf-8", errors="replace").read()
        except FileNotFoundError:
            time.sleep(0.5)
            continue
        if "[itemorder] PROBE READY" in text:
            ready = True
            for line in text.splitlines():
                if "[itemorder]" in line:
                    log("  " + line.strip())
        elif "Failed to load mods" in text:
            log("!! the game refused the mods; see " + logpath)
            break
        time.sleep(0.5)
    log("probe ready=%s" % ready)
    if not ready:
        # a modal error dialog or a half-loaded game: grab it, it explains the failure
        ImageGrab.grab(all_screens=True).save(os.path.join(out, "00-not-ready.png"))
        log("  saved %s/00-not-ready.png" % out)

    if not activate(hwnd, cx, cy):
        log("!! could not take focus")
    user32.SetCursorPos(int(cx), int(cy))
    time.sleep(0.5)

    for step in plan:
        action = step["action"]
        if action == "key":
            press(step["vk"], step.get("hold", 0.08))
            log("  key %d" % step["vk"])
        elif action == "click":
            click(x + step["x"], y + step["y"])
            log("  click %d,%d" % (step["x"], step["y"]))
        elif action == "move":
            user32.SetCursorPos(x + step["x"], y + step["y"])
            log("  move %d,%d" % (step["x"], step["y"]))
        elif action == "type":
            type_text(step["text"])
            log("  type %r" % step["text"])
        elif action == "wait":
            time.sleep(step["s"])
        elif action == "grab":
            path = os.path.join(out, step["name"] + ".png")
            ImageGrab.grab(all_screens=True).save(path)
            log("  saved %s (%dx%d)" % (path, *ImageGrab.grab(all_screens=True).size))
        elif action == "log":
            marker = step["marker"]
            start = time.time()
            while time.time() - start < step.get("timeout", 60):
                text = open(logpath, encoding="utf-8", errors="replace").read()
                if marker in text:
                    log("  marker %r seen" % marker)
                    break
                time.sleep(0.5)
        else:
            log("  !! unknown step %r" % action)

    log("done -> closing pid %d" % proc.pid)
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
    return 0 if ready else 2


if __name__ == "__main__":
    sys.exit(main())

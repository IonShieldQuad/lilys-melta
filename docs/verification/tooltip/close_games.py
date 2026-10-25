"""Terminate every running Factorio instance that has a visible window.

WM_CLOSE is posted first (a clean shutdown), then whatever is still alive after a
grace period is terminated through its own window's process id. This only ever
touches processes that own a window titled 'Factorio ...' -- the staged test runs --
and never the user's saves: the staged runs use their own write directory.
"""
import ctypes
import ctypes.wintypes as wt
import sys
import time

u = ctypes.windll.user32
k32 = ctypes.windll.kernel32
WM_CLOSE = 0x0010
PROCESS_TERMINATE = 0x0001


def game_windows():
    found = []

    @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    def cb(h, l):
        if u.IsWindowVisible(h):
            n = u.GetWindowTextLengthW(h)
            if n:
                buf = ctypes.create_unicode_buffer(n + 1)
                u.GetWindowTextW(h, buf, n + 1)
                if buf.value.lower().startswith("factorio"):
                    found.append((h, buf.value))
        return True

    u.EnumWindows(cb, 0)
    return found


def pid_of(hwnd):
    pid = wt.DWORD()
    u.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value


wins = game_windows()
for h, title in wins:
    print("closing", h, repr(title), "pid", pid_of(h))
    u.PostMessageW(h, WM_CLOSE, 0, 0)

deadline = time.time() + 15
while time.time() < deadline and game_windows():
    time.sleep(1.0)

for h, title in game_windows():
    pid = pid_of(h)
    handle = k32.OpenProcess(PROCESS_TERMINATE, False, pid)
    if handle:
        k32.TerminateProcess(handle, 1)
        k32.CloseHandle(handle)
        print("terminated pid", pid, repr(title))
    else:
        print("could not open pid", pid)

time.sleep(2)
print("remaining:", game_windows())
sys.exit(0 if not game_windows() else 1)

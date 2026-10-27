"""Gallery run that foregrounds the game window (Factorio pauses when unfocused)."""
import ctypes, ctypes.wintypes as w, os, subprocess, sys, time
EXE = r"E:/SteamLibrary/steamapps/common/Factorio/bin/x64/Factorio.exe"
ENV = dict(os.environ, SteamAppId="427520", SteamGameId="427520", SteamOverlayGameId="427520")
run = sys.argv[1].replace("\\", "/")
config, mods = run + "/config.ini", run + "/mods"
save, log = run + "/write/gallery.zip", run + "/write/factorio-current.log"
user32 = ctypes.windll.user32
try: ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception: pass

def pid_windows(pid):
    out = []
    @ctypes.WINFUNCTYPE(ctypes.c_bool, w.HWND, w.LPARAM)
    def cb(hwnd, lparam):
        owner = w.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
        if owner.value == pid and user32.IsWindowVisible(hwnd):
            out.append(hwnd)
        return True
    user32.EnumWindows(cb, 0)
    return out

def foreground(pid):
    for hwnd in pid_windows(pid):
        user32.ShowWindow(hwnd, 9)          # SW_RESTORE
        user32.SetForegroundWindow(hwnd)
        rect = w.RECT(); user32.GetClientRect(hwnd, ctypes.byref(rect))
        pt = w.POINT(); user32.ClientToScreen(hwnd, ctypes.byref(pt))
        cx, cy = pt.x + (rect.right - rect.left) // 2, pt.y + (rect.bottom - rect.top) // 2
        user32.SetCursorPos(cx, cy)
        user32.mouse_event(0x0002, 0, 0, 0, 0)   # LEFTDOWN
        user32.mouse_event(0x0004, 0, 0, 0, 0)   # LEFTUP
        return True
    return False

lock = run + "/write/.lock"
if os.path.exists(lock):
    try: os.remove(lock)
    except OSError: pass
if os.path.exists(log): os.remove(log)
proc = subprocess.Popen([EXE, "--config", config, "--mod-directory", mods, "--load-game", save], env=ENV)
deadline, state, focused = time.time() + 280, "timeout", False
while time.time() < deadline:
    time.sleep(2)
    if not focused and time.time() > deadline - 270:
        focused = foreground(proc.pid)
        print("foregrounded:", focused, flush=True)
    if os.path.exists(log):
        text = open(log, "r", errors="ignore").read()
        if "GALLERY DONE" in text:
            state = "done"; break
        if "non-recoverable error" in text:
            state = "errored"; break
    if proc.poll() is not None:
        state = "exited"; break
print("state:", state)
time.sleep(3)
if proc.poll() is None:
    subprocess.run(["taskkill", "/PID", str(proc.pid), "/F"], capture_output=True)
text = open(log, "r", errors="ignore").read() if os.path.exists(log) else ""
for line in text.splitlines():
    if "[gallery]" in line: print(line.split("[gallery] ", 1)[-1].strip())
for line in text.splitlines():
    if "Error" in line: print("!! " + line.strip()[:200])
d = run + "/write/script-output/gallery"
if os.path.isdir(d):
    print("shots:", len(os.listdir(d)))
    for n in sorted(os.listdir(d)): print("  ", n)

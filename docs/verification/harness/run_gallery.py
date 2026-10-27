"""Gallery run v2: draws the in-game shots, then photographs the technology screen.

Factorio pauses when its window is unfocused, so the window is foregrounded; the tech screen
needs a real keypress (there is no scripting API for it), which is why it happens here and not
in control.lua.
"""
import ctypes, ctypes.wintypes as w, os, subprocess, sys, time
from PIL import ImageGrab

EXE = r"E:/SteamLibrary/steamapps/common/Factorio/bin/x64/Factorio.exe"
ENV = dict(os.environ, SteamAppId="427520", SteamGameId="427520", SteamOverlayGameId="427520")
run = sys.argv[1].replace("\\", "/")
config, mods = run + "/config.ini", run + "/mods"
save, log = run + "/write/gallery.zip", run + "/write/factorio-current.log"
outdir = run + "/write/script-output/gallery"
user32 = ctypes.windll.user32
try: ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception: pass

def windows_of(pid):
    found = []
    @ctypes.WINFUNCTYPE(ctypes.c_bool, w.HWND, w.LPARAM)
    def cb(hwnd, lparam):
        owner = w.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
        if owner.value == pid and user32.IsWindowVisible(hwnd):
            found.append(hwnd)
        return True
    user32.EnumWindows(cb, 0)
    return found

def focus_and_rect(pid):
    for hwnd in windows_of(pid):
        user32.ShowWindow(hwnd, 9)
        user32.SetForegroundWindow(hwnd)
        rect = w.RECT()
        user32.GetClientRect(hwnd, ctypes.byref(rect))
        origin = w.POINT(0, 0)
        user32.ClientToScreen(hwnd, ctypes.byref(origin))
        return (origin.x, origin.y, origin.x + rect.right, origin.y + rect.bottom)
    return None

def press(vk):
    user32.keybd_event(vk, 0, 0, 0)
    time.sleep(0.05)
    user32.keybd_event(vk, 0, 2, 0)

lock = run + "/write/.lock"
if os.path.exists(lock):
    try: os.remove(lock)
    except OSError: pass
if os.path.exists(log):
    os.remove(log)

proc = subprocess.Popen([EXE, "--config", config, "--mod-directory", mods, "--load-game", save], env=ENV)
deadline = time.time() + 320
state, tech_done, focused = "timeout", False, False
while time.time() < deadline:
    time.sleep(2)
    if not focused:
        focused = focus_and_rect(proc.pid) is not None
    if os.path.exists(log):
        text = open(log, "r", errors="ignore").read()
        if "TECH READY" in text and not tech_done:
            time.sleep(2)
            rect = focus_and_rect(proc.pid)
            press(0x09)                       # Tab dismisses the "welcome to freeplay" tip
            time.sleep(1.2)
            press(0x54)                       # 'T' opens the technology screen
            time.sleep(2.5)
            rect = focus_and_rect(proc.pid)   # screen may have changed size
            if rect:
                os.makedirs(outdir, exist_ok=True)
                ImageGrab.grab(bbox=rect, all_screens=True).save(outdir + "/07-technologies.png")
                print("tech screen grabbed", rect, flush=True)
            tech_done = True
        if "GALLERY DONE" in text:
            state = "done"
            break
        if "non-recoverable error" in text:
            state = "errored"
            break
    if proc.poll() is not None:
        state = "exited"
        break
print("state:", state, "tech:", tech_done)
time.sleep(2)
if proc.poll() is None:
    subprocess.run(["taskkill", "/PID", str(proc.pid), "/F"], capture_output=True)
text = open(log, "r", errors="ignore").read() if os.path.exists(log) else ""
for line in text.splitlines():
    if "[gallery]" in line: print(line.split("[gallery] ", 1)[-1].strip())
for line in text.splitlines():
    if "Error" in line: print("!! " + line.strip()[:200])
if os.path.isdir(outdir):
    print("shots:", sorted(os.listdir(outdir)))

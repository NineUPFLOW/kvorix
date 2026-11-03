#!/usr/bin/env python3

import json
import os
import shutil
import socket
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fd6551 import FD6551

CFG = "/var/lib/front-panel/config.json"
DEFAULT = {"screens": ["clock", "temp", "cpu", "ram"], "seconds": 5,
           "brightness": 7, "night": True}
CELLS = (4, 3, 2, 1)
COLON = (2, 0x80)
GLYPH = {'0': 63, '1': 48, '2': 91, '3': 121, '4': 116, '5': 109, '6': 111, '7': 56, '8': 127,
         '9': 125, 'A': 126, 'B': 103, 'C': 15, 'D': 115, 'E': 79, 'F': 78, 'G': 47, 'H': 102,
         'I': 6, 'J': 51, 'K': 110, 'L': 7, 'M': 42, 'N': 62, 'O': 99, 'P': 94, 'Q': 124, 'R': 66,
         'S': 109, 'T': 71, 'U': 35, 'V': 55, 'W': 21, 'X': 118, 'Y': 117, 'Z': 91, '_': 1, '-': 64,
         ' ': 0}


SCREENS = {"clock", "date", "temp", "cpu", "ram", "disk", "node", "wifi", "uptime"}


def validate_config(raw):
    
    if not isinstance(raw, dict):
        raise ValueError("configuration must be an object")
    cfg = dict(DEFAULT, **raw)
    screens = cfg["screens"]
    if not isinstance(screens, list) or len(screens) > 32:
        raise ValueError("screens must be a list of at most 32 names")
    if any(not isinstance(s, str) or s not in SCREENS for s in screens):
        raise ValueError("unknown screen name")
    for key, low, high in (("brightness", 0, 7), ("seconds", 2, 3600)):
        value = cfg[key]
        if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
            raise ValueError("invalid " + key)
    if not isinstance(cfg["night"], bool):
        raise ValueError("night must be boolean")
    cfg["screens"] = list(screens) or ["clock"]
    return cfg


def read(p, d="0"):
    try:
        return open(p).read().strip()
    except OSError:
        return d


_cpu = [0, 0]


def cpu():
    v = list(map(int, read("/proc/stat").splitlines()[0].split()[1:8]))
    tot, idle = sum(v), v[3] + v[4]
    dt, di = tot - _cpu[0], idle - _cpu[1]
    _cpu[:] = [tot, idle]
    return 0 if dt <= 0 else round(100 * (1 - di / dt))


def temp():
    return int(read("/sys/class/thermal/thermal_zone0/temp")) // 1000


def node_ok():
    try:
        host = json.load(open("/etc/armbian-cluster/cluster.json"))["nodes"][0]["host"]
        with socket.create_connection((host, 9101), 1.5):
            return True
    except Exception:
        return False


def wifi_dbm():
    for line in read("/proc/net/wireless", "").splitlines()[2:]:
        f = line.split()
        if f and f[0].startswith("wlan"):
            return int(float(f[3]))
    return None


def screen(name, state):
    
    if name == "clock":
        return time.strftime("%H%M"), time.time() % 1 < 0.5
    if name == "date":
        return time.strftime("%d%m"), True
    if name == "temp":
        return "%3dC" % temp(), False
    if name == "cpu":
        return "C%3d" % min(state["cpu"], 999), False
    if name == "ram":
        m = dict((l.split(":")[0], int(l.split()[1])) for l in read("/proc/meminfo").splitlines())
        return "R%3d" % round(100 * (1 - m["MemAvailable"] / m["MemTotal"])), False
    if name == "disk":
        u = shutil.disk_usage("/")
        return "D%3d" % round(100 * u.used / u.total), False
    if name == "node":
        return ("N1ON" if state["node"] else "N1--"), False
    if name == "wifi":
        s = wifi_dbm()
        return ("%4d" % s if s is not None else "NO W"), False
    if name == "uptime":
        m = int(float(read("/proc/uptime").split()[0])) // 60
        return ("%02d%02d" % (m // 60 % 100, m % 60)) if m < 6000 else "%4d" % (m // 1440), True
    return time.strftime("%H%M"), True


def encode(text, colon):
    cells = [0] * 5
    for pos, ch in zip(CELLS, text.upper()[:4].rjust(4)):
        cells[pos] = GLYPH.get(ch, 0)
    if colon:
        cells[COLON[0]] |= COLON[1]
    return cells


def main():
    import signal
    signal.signal(signal.SIGTERM, lambda *a: sys.exit(0))
    d = FD6551()
    cfg, mtime, i, shown, last_slow, last = validate_config({}), 0, 0, 0.0, 0.0, None
    state, bright, last_cpu = {"node": True, "cpu": cpu()}, None, 0.0
    try:
        while True:
            try:
                m = os.path.getmtime(CFG)
                if m != mtime:
                    with open(CFG, encoding="utf-8") as f:
                        updated = validate_config(json.load(f))
                    cfg, mtime = updated, m
                    bright = None
            except (OSError, ValueError):
                pass
            now = time.monotonic()
            if now - last_cpu >= 2:
                last_cpu, state["cpu"] = now, cpu()
            hour = time.localtime().tm_hour
            want = 1 if cfg.get("night", True) and (hour >= 22 or hour < 7) else int(cfg["brightness"])
            if want != bright:
                bright = want
                d.brightness(bright)
            screens = [s for s in cfg["screens"] if s] or ["clock"]
            if temp() >= 75 and "temp" not in screens:
                screens.append("temp")
            if now - shown >= max(2, int(cfg["seconds"])):
                i, shown = (i + 1) % len(screens), now
            text, colon = screen(screens[i % len(screens)], state)
            cells = encode(text, colon)
            if cells != last:
                d.write(cells)
                last = cells
            time.sleep(0.25)
    finally:
        d.write([0] * 5)
        d.close()


if __name__ == "__main__":
    main()

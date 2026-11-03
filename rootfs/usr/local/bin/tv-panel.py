#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import json
import shutil
import socket
import time
import urllib.request
from datetime import datetime

from PIL import Image, ImageDraw, ImageFont

FB = "/dev/fb0"
UA = "armbian-tv-panel/1.0 (home server dashboard)"
MET_URL = ("https://api.met.no/weatherapi/locationforecast/2.0/compact"
           "?lat=45.04&lon=41.97")

BG_TOP    = (10, 14, 28)
BG_BOTTOM = (20, 27, 45)
CARD      = (24, 33, 54)
CARD_LINE = (42, 55, 84)
TEXT      = (230, 237, 243)
MUTED     = (139, 152, 176)
DIM       = (108, 122, 148)
FAINT     = (96, 108, 132)
ACCENT    = (79, 209, 197)
ACCENT2   = (246, 173, 85)
GOOD      = (104, 211, 145)
WARN      = (246, 173, 85)
BAD       = (245, 101, 101)
SUN       = (246, 173, 85)
CLOUD     = (168, 186, 212)
CLOUD_DK  = (130, 150, 180)

FONT_DIR = "/usr/share/fonts/truetype/dejavu/"
MONTHS = ["января", "февраля", "марта", "апреля", "мая", "июня", "июля",
          "августа", "сентября", "октября", "ноября", "декабря"]
WEEKDAYS = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"]

SYMBOL_MAP = [
    ("thunder",      "гроза"),
    ("sleet",        "мокрый снег"),
    ("snow",         "снег"),
    ("drizzle",      "морось"),
    ("showers",      "ливень"),
    ("rain",         "дождь"),
    ("fog",          "туман"),
    ("partlycloudy", "переменная облачность"),
    ("cloudy",       "облачно"),
    ("clearsky",     "ясно"),
    ("fair",         "прояснения"),
]


def font(name, size):
    try:
        return ImageFont.truetype(os.path.join(FONT_DIR, name), size)
    except Exception:
        return ImageFont.load_default()


def read(path, default=""):
    try:
        with open(path) as f:
            return f.read().strip()
    except Exception:
        return default


def cpu_temp():
    t = read("/sys/class/thermal/thermal_zone0/temp", "0")
    try:
        return int(t) / 1000.0 if t else None
    except Exception:
        return None


def memory():
    info = {}
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                k, v = line.split(":", 1)
                info[k] = int(v.split()[0])
        total = info["MemTotal"] / 1048576.0
        avail = info.get("MemAvailable", info["MemFree"]) / 1048576.0
        return total, total - avail
    except Exception:
        return None, None


def swap_used():
    try:
        with open("/proc/swaps") as f:
            lines = f.read().strip().splitlines()[1:]
        total = used = 0
        for l in lines:
            p = l.split()
            total += int(p[2]); used += int(p[3])
        return total / 1048576.0, used / 1048576.0
    except Exception:
        return 0.0, 0.0


def disk():
    try:
        s = shutil.disk_usage("/")
        return s.total / 2**30, (s.total - s.free) / 2**30
    except Exception:
        return None, None


def uptime_str():
    try:
        sec = float(read("/proc/uptime", "0").split()[0])
        d, rem = divmod(int(sec), 86400)
        h, rem = divmod(rem, 3600)
        m = rem // 60
        if d:
            return f"{d} д {h} ч"
        if h:
            return f"{h} ч {m} мин"
        return f"{m} мин"
    except Exception:
        return "—"


def load_avg():
    try:
        return float(read("/proc/loadavg", "0 0").split()[0])
    except Exception:
        return 0.0


def lan_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.2)
        s.connect(("192.168.0.1", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "—"


def wifi_signal():
    try:
        with open("/proc/net/wireless") as f:
            lines = f.read().strip().splitlines()[2:]
        for l in lines:
            if ":" in l:
                return float(l.split()[3].rstrip("."))
    except Exception:
        pass
    return None


_wcache = {"t": 0.0, "data": None}


def _symbol(kind, desc):
    return kind, desc


def symbol_info(code):
    code = (code or "").lower()
    base_kind, desc = "cloudy", "облачно"
    for key, label in SYMBOL_MAP:
        if key in code:
            base_kind, desc = key, label
            break
    if "clearsky" in code:
        base_kind, desc = "clearsky", "ясно"
    if "light" in code:
        desc = "небольшой " + desc if base_kind in ("rain", "snow", "sleet", "showers") else "слабый " + desc
    elif "heavy" in code:
        desc = "сильный " + desc if base_kind in ("rain", "snow", "sleet", "showers") else desc
    elif base_kind in ("rain", "snow", "sleet", "showers") and "light" not in code:
        desc = desc
    if base_kind == "partlycloudy":
        desc = "переменная облачность"
    return base_kind, desc


def weather():
    
    now = time.time()
    if _wcache["data"] and now - _wcache["t"] < 900:
        return _wcache["data"]
    try:
        req = urllib.request.Request(MET_URL, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=10) as r:
            d = json.loads(r.read().decode())
        ts = d["properties"]["timeseries"]
        cur = ts[0]["data"]["instant"]["details"]
        nxt = ts[0]["data"].get("next_1_hours") or ts[0]["data"].get("next_6_hours") or {}
        code = (nxt.get("summary") or {}).get("symbol_code", "cloudy")
        kind, desc = symbol_info(code)

        now_local = datetime.now().astimezone()
        day_t, night_t = [], []
        for t in ts[:26]:
            try:
                ts_local = datetime.fromisoformat(t["time"].replace("Z", "+00:00")).astimezone()
            except Exception:
                continue
            v = t["data"]["instant"]["details"].get("air_temperature")
            if v is None:
                continue
            (day_t if 8 <= ts_local.hour < 20 else night_t).append(v)

        w = {
            "temp": round(cur.get("air_temperature", 0)),
            "wind": round(cur.get("wind_speed", 0)),
            "tmax": round(max(day_t)) if day_t else None,
            "tmin": round(min(night_t)) if night_t else None,
            "desc": desc,
            "kind": kind,
        }
        _wcache.update(t=now, data=w)
        return w
    except Exception as e:
        print("погода: ошибка", e, file=sys.stderr)
        return _wcache["data"]


def gradient(w, h):
    strip = Image.new("RGB", (1, h))
    px = strip.load()
    for y in range(h):
        k = y / max(1, h - 1)
        px[0, y] = tuple(int(BG_TOP[i] + (BG_BOTTOM[i] - BG_TOP[i]) * k) for i in range(3))
    return strip.resize((w, h), Image.BILINEAR)


def rounded(d, box, r, fill=None, outline=None, width=1):
    d.rounded_rectangle(box, radius=r, fill=fill, outline=outline, width=width)


def bar(d, x, y, w, h, frac, color):
    rounded(d, (x, y, x + w, y + h), h // 2, fill=(38, 48, 72))
    frac = max(0.0, min(1.0, frac))
    if frac > 0.005:
        rounded(d, (x, y, x + max(h, int(w * frac)), y + h), h // 2, fill=color)


def temp_color(t):
    if t is None:
        return MUTED
    return GOOD if t < 60 else (WARN if t < 72 else BAD)


def fit_font(d, text, max_size, max_w, name="DejaVuSans-Bold.ttf", min_size=10):
    size = max_size
    while size > min_size:
        f = font(name, size)
        if d.textlength(text, font=f) <= max_w:
            return f
        size -= 2
    return font(name, min_size)


def weather_glyph(d, x, y, size, kind):
    
    import math
    cx, cy = x + size // 2, y + size // 2
    sun_r = size * 0.26

    def draw_sun(r, ox=0, oy=0):
        d.ellipse((cx + ox - r, cy + oy - r, cx + ox + r, cy + oy + r), fill=SUN)
        for a in range(8):
            ang = a * math.pi / 4 + math.pi / 8
            d.line((cx + ox + math.cos(ang) * r * 1.45, cy + oy + math.sin(ang) * r * 1.45,
                    cx + ox + math.cos(ang) * r * 2.0, cy + oy + math.sin(ang) * r * 2.0),
                   fill=SUN, width=max(2, size // 26))

    def draw_cloud(col, dy=0, sc=1.0):
        w2 = size * 0.34 * sc
        d.ellipse((cx - w2 * 1.7, cy + dy - w2 * 0.3, cx + w2 * 0.5, cy + dy + w2 * 1.0), fill=col)
        d.ellipse((cx - w2 * 0.8, cy + dy - w2 * 0.9, cx + w2 * 1.0, cy + dy + w2 * 0.5), fill=col)
        d.ellipse((cx - w2 * 0.1, cy + dy - w2 * 0.4, cx + w2 * 1.7, cy + dy + w2 * 1.0), fill=col)

    off = int(size * 0.12)
    if kind in ("clearsky", "fair"):
        draw_sun(sun_r)
    elif kind == "partlycloudy":
        draw_sun(size * 0.17, -off, -off)
        draw_cloud(CLOUD, int(size * 0.13), 0.95)
    elif kind in ("cloudy",):
        draw_cloud(CLOUD_DK)
    elif kind == "fog":
        draw_cloud(CLOUD)
        for i, dy in enumerate((0.30, 0.42)):
            d.line((cx - size * 0.34, cy + size * dy, cx + size * 0.34, cy + size * dy),
                   fill=MUTED, width=max(2, size // 30))
    elif kind in ("snow", "sleet"):
        draw_cloud(CLOUD)
        for dx in (-0.22, 0.0, 0.22):
            d.ellipse((cx + size * dx - 6, cy + size * 0.22, cx + size * dx + 6, cy + size * 0.36), fill=ACCENT)
    elif kind == "thunder":
        draw_cloud(CLOUD_DK)
        d.polygon([(cx - 6, cy + size * 0.02), (cx + 10, cy + size * 0.02),
                   (cx + 1, cy + size * 0.19), (cx + 13, cy + size * 0.19),
                   (cx - 8, cy + size * 0.44), (cx - 1, cy + size * 0.23),
                   (cx - 13, cy + size * 0.23)], fill=SUN)
    else:
        draw_cloud(CLOUD)
        for dx in (-0.22, 0.0, 0.22):
            d.line((cx + size * dx, cy + size * 0.16, cx + size * dx - 8, cy + size * 0.42),
                   fill=ACCENT, width=max(2, size // 24))


def _layout(w, h):
    margin = int(w * 0.033)
    col_gap = int(w * 0.026)
    right_w = int(w * 0.40)
    right_x = w - margin - right_w
    left_w = right_x - margin - col_gap
    top = int(h * 0.075)
    gap = int(h * 0.019)
    n = 4
    ch = int((h - top - int(h * 0.105) - gap * (n - 1)) / n)
    pad = int(right_w * 0.062)
    return dict(margin=margin, col_gap=col_gap, right_w=right_w, right_x=right_x,
                left_w=left_w, top=top, gap=gap, ch=ch, pad=pad, n=n)


CARD_TITLES = ("ТЕМПЕРАТУРА", "ПАМЯТЬ", "ДИСК", "СЕТЬ")
_BASE = {}


def build_base(w, h):
    
    L = _layout(w, h)
    img = gradient(w, h)
    d = ImageDraw.Draw(img)
    f_lbl = font("DejaVuSans-Bold.ttf", int(h * 0.0235))
    f_tiny = font("DejaVuSans.ttf", int(h * 0.0245))

    for i, title in enumerate(CARD_TITLES):
        y0 = L["top"] + i * (L["ch"] + L["gap"])
        y1 = y0 + L["ch"]
        rounded(d, (L["right_x"], y0, L["right_x"] + L["right_w"], y1),
                int(L["ch"] * 0.18), fill=CARD, outline=CARD_LINE)
        d.text((L["right_x"] + L["pad"], y0 + int(L["ch"] * 0.155)), title, font=f_lbl, fill=MUTED)

    d.line((L["margin"], int(h * 0.475), L["margin"] + L["left_w"], int(h * 0.475)),
           fill=CARD_LINE, width=1)
    by = h - int(h * 0.048)
    d.line((L["margin"], by - int(h * 0.020), w - L["margin"], by - int(h * 0.020)),
           fill=CARD_LINE, width=1)
    d.text((L["margin"], by - int(h * 0.009)),
           "armbian · Debian 13 · ядро 6.12.112-ophub", font=f_tiny, fill=FAINT)
    return img


def render(w, h):
    base = _BASE.get((w, h))
    if base is None:
        base = build_base(w, h)
        _BASE[(w, h)] = base

    img = base.copy()
    d = ImageDraw.Draw(img)
    L = _layout(w, h)
    now = datetime.now()

    f_small = font("DejaVuSans.ttf", int(h * 0.0275))
    f_tiny = font("DejaVuSans.ttf", int(h * 0.0245))

    time_txt = now.strftime("%H:%M")
    f_sec = font("DejaVuSans-Bold.ttf", int(h * 0.055))
    f_time = fit_font(d, time_txt, int(h * 0.30), L["left_w"] - int(w * 0.05))
    d.text((L["margin"], int(h * 0.075)), time_txt, font=f_time, fill=TEXT)
    tw = d.textlength(time_txt, font=f_time)
    sec_y = int(h * 0.075) + int(h * 0.30) - int(h * 0.055) - int(h * 0.02)
    d.text((L["margin"] + tw + int(w * 0.010), sec_y), now.strftime("%S"), font=f_sec, fill=ACCENT)

    date_txt = f"{WEEKDAYS[now.weekday()]}, {now.day} {MONTHS[now.month - 1]} {now.year}"
    d.text((L["margin"], int(h * 0.395)),
           date_txt, font=fit_font(d, date_txt, int(h * 0.040), L["left_w"], "DejaVuSans.ttf"),
           fill=MUTED)

    wx = weather()
    wy = int(h * 0.525)
    if wx:
        gsz = int(h * 0.145)
        weather_glyph(d, L["margin"], wy, gsz, wx["kind"])
        tx = L["margin"] + gsz + int(w * 0.014)
        d.text((tx, wy - int(h * 0.005)), f"{wx['temp']:+d}°",
               font=font("DejaVuSans-Bold.ttf", int(h * 0.080)), fill=TEXT)
        d.text((tx, wy + int(h * 0.088)), f"Ставрополь · {wx['desc']}", font=f_small, fill=MUTED)
        line2 = ""
        if wx["tmax"] is not None:
            line2 = f"днём {wx['tmax']:+d}°, ночью {wx['tmin']:+d}°"
        if wx.get("wind"):
            line2 += f" · ветер {wx['wind']} м/с"
        d.text((tx, wy + int(h * 0.125)), line2, font=f_tiny, fill=DIM)
    else:
        d.text((L["margin"], wy + int(h * 0.03)), "погода недоступна", font=f_small, fill=(90, 100, 125))

    t = cpu_temp()
    tot, used = memory()
    stot, sused = swap_used()
    dtot, dused = disk()
    lvl = wifi_signal()

    values = [
        (f"{t:.0f} °C" if t else "—", None, temp_color(t), "процессор"),
        (f"{used:.2f} / {tot:.1f} ГБ" if tot else "—", (used / tot) if tot else None,
         ACCENT, f"swap {sused:.1f} / {stot:.1f} ГБ" if stot else ""),
        (f"{dused:.1f} / {dtot:.0f} ГБ" if dtot else "—", (dused / dtot) if dtot else None,
         ACCENT2, "внутренняя память"),
        (f"{lvl:.0f} дБм" if lvl is not None else "—", None,
         GOOD if (lvl if lvl is not None else -100) > -70 else WARN, lan_ip()),
    ]

    for i, (value, frac, color, sub) in enumerate(values):
        y0 = L["top"] + i * (L["ch"] + L["gap"])
        f_val = fit_font(d, value, int(L["ch"] * 0.38), L["right_w"] - L["pad"] * 2)
        d.text((L["right_x"] + L["pad"], y0 + int(L["ch"] * 0.335)), value, font=f_val, fill=color)
        if frac is not None:
            bar(d, L["right_x"] + L["pad"], y0 + int(L["ch"] * 0.815),
                L["right_w"] - L["pad"] * 2, int(L["ch"] * 0.075), frac, color)
        elif sub:
            d.text((L["right_x"] + L["pad"], y0 + int(L["ch"] * 0.815)), sub, font=f_tiny, fill=DIM)

    by = h - int(h * 0.048)
    right_txt = f"аптайм {uptime_str()} · загрузка {load_avg():.2f}"
    rw = d.textlength(right_txt, font=f_tiny)
    d.text((w - L["margin"] - rw, by - int(h * 0.009)), right_txt, font=f_tiny, fill=FAINT)

    return img


def fb_info():
    w, h = 1360, 768
    vs = read("/sys/class/graphics/fb0/virtual_size", "1360,768")
    try:
        w, h = [int(v) for v in vs.split(",")]
    except Exception:
        pass
    bpp = 32
    try:
        bpp = int(read("/sys/class/graphics/fb0/bits_per_pixel", "32"))
    except Exception:
        pass
    stride = 0
    try:
        stride = int(read("/sys/class/graphics/fb0/stride", "0"))
    except Exception:
        pass
    if stride <= 0:
        stride = w * bpp // 8
    return w, h, bpp, stride


def to_bgra(frame):
    
    r, g, b = frame.convert("RGB").split()
    alpha = Image.new("L", frame.size, 255)
    return Image.merge("RGBA", (b, g, r, alpha)).tobytes()


def main():
    if os.geteuid() != 0:
        print("Нужны права root: sudo python3 tv-panel.py", file=sys.stderr)
        sys.exit(1)

    os.system("echo 0 > /sys/class/graphics/fbcon/cursor_blink 2>/dev/null")
    os.system("setterm --blank 0 --powersave off </dev/tty1 >/dev/null 2>&1")

    vw, vh, bpp, stride = fb_info()
    mode = read("/sys/class/graphics/fb0/modes", "U:1360x768p-0")
    try:
        h = int(mode.split(":")[1].split("x")[1].split("p")[0].split("-")[0])
    except Exception:
        h = min(vh, int(round(vw * 9 / 16)))
    w = vw

    print(f"табло: {w}x{h}, {bpp} bpp, stride {stride}, virtual {vw}x{vh}", flush=True)

    if bpp != 32:
        print(f"неподдерживаемый формат: {bpp} bpp", file=sys.stderr)
        sys.exit(1)
    bpx = 4
    row = w * bpx
    pad = b"\x00" * (stride - row) if stride != row else b""

    while True:
        t0 = time.time()
        try:
            data = to_bgra(render(w, h))
            with open(FB, "r+b", buffering=0) as fb:
                fb.seek(0)
                if not pad:
                    fb.write(data)
                else:
                    for y in range(h):
                        fb.write(data[y * row:(y + 1) * row])
                        fb.write(pad)
        except Exception as e:
            print("ошибка кадра:", e, file=sys.stderr, flush=True)
        dt = time.time() - t0
        time.sleep(max(0.05, 1.0 - dt))


if __name__ == "__main__":
    main()

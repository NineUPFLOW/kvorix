#!/usr/bin/python3

import os
import random
import subprocess
import sys
import time

from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 1360, 768

TOPBAR_H = 42
SIDEBAR_W = 188
BOTTOMBAR_H = 36
CENTER_X0, CENTER_X1 = 196, 1010
CONTENT_Y0, CONTENT_Y1 = 54, 732
RIGHT_X0, RIGHT_X1 = 1020, 1352
TERM_RECT = (202, 88, 796, 630)
BODY = (210, 104, 992, 720)

REFRESH = 1.0

C = {
    "bg":     (8, 17, 26),
    "panel":  (14, 26, 38),
    "stroke": (30, 48, 64),
    "text":   (228, 240, 247),
    "dim":    (127, 150, 168),
    "dim2":   (90, 112, 130),
    "cyan":   (34, 211, 238),
    "teal":   (45, 212, 191),
    "green":  (52, 211, 153),
    "yellow": (251, 191, 36),
    "orange": (251, 146, 60),
    "red":    (248, 113, 113),
    "violet": (167, 139, 250),
}

FONT_DIR = "/usr/share/fonts/truetype/dejavu"


def font(name, size):
    return ImageFont.truetype(os.path.join(FONT_DIR, name), size)


F = {
    "ui":      font("DejaVuSans.ttf", 14),
    "ui_sm":   font("DejaVuSans.ttf", 12),
    "ui_b":    font("DejaVuSans-Bold.ttf", 15),
    "ui_big":  font("DejaVuSans-Bold.ttf", 20),
    "mono":    font("DejaVuSansMono.ttf", 12),
    "mono_sm": font("DejaVuSansMono.ttf", 11),
    "mono_b":  font("DejaVuSansMono-Bold.ttf", 13),
    "mono_lg": font("DejaVuSansMono-Bold.ttf", 15),
}


def rrect(draw, box, r, fill=None, outline=None, width=1):
    draw.rounded_rectangle(box, radius=r, fill=fill, outline=outline, width=width)


def text(draw, xy, s, f="ui", fill=C["text"], anchor="la"):
    draw.text(xy, s, font=F[f], fill=fill, anchor=anchor)


def fit_text(draw, s, f, max_w):
    if max_w <= 6:
        return ""
    if draw.textlength(s, font=F[f]) <= max_w:
        return s
    while s and draw.textlength(s + "\u2026", font=F[f]) > max_w:
        s = s[:-1]
    return s + "\u2026"


def text_fit(draw, xy, s, f="ui", fill=C["text"], anchor="la", max_w=None):
    if max_w is not None:
        s = fit_text(draw, s, f, max_w)
    text(draw, xy, s, f, fill, anchor)


def ring(draw, cx, cy, r, frac, color, thickness=6, track=C["stroke"]):
    box = (cx - r, cy - r, cx + r, cy + r)
    draw.arc(box, 0, 360, fill=track, width=thickness)
    if frac > 0:
        draw.arc(box, -90, -90 + max(2, frac * 360), fill=color, width=thickness)


def sparkline(draw, box, values, color):
    x0, y0, x1, y1 = box
    if len(values) < 2:
        return
    lo, hi = min(values), max(values)
    if hi - lo < 1e-9:
        hi = lo + 1
    n = len(values)
    draw.line([(x0 + (x1 - x0) * i / (n - 1), y1 - (y1 - y0) * (v - lo) / (hi - lo))
               for i, v in enumerate(values)], fill=color, width=2, joint="curve")


def glass(img, box, radius=12, alpha=205, blur=9, tint=(9, 17, 25), strength=0.30):
    x0, y0, x1, y1 = [int(v) for v in box]
    x1, y1 = max(x1, x0 + 2), max(y1, y0 + 2)
    region = img.crop((x0, y0, x1, y1)).filter(ImageFilter.GaussianBlur(blur))
    region = region.point(lambda v: int(v * strength))
    region = Image.blend(region, Image.new("RGB", region.size, tint), 0.45)
    mask = Image.new("L", region.size, 0)
    md = ImageDraw.Draw(mask)
    if radius:
        md.rounded_rectangle((0, 0, region.size[0] - 1, region.size[1] - 1),
                             radius=radius, fill=alpha)
    else:
        md.rectangle((0, 0, region.size[0] - 1, region.size[1] - 1), fill=alpha)
    img.paste(region, (x0, y0), mask)
    dr = ImageDraw.Draw(img)
    if radius:
        dr.rounded_rectangle((x0, y0, x1 - 1, y1 - 1), radius=radius,
                             outline=(56, 82, 100, 190), width=1)
    else:
        dr.rectangle((x0, y0, x1 - 1, y1 - 1), outline=(42, 64, 80, 170), width=1)


def icon_wifi(d, cx, cy, color):
    for r in (9, 6, 3):
        d.arc((cx - r, cy - r + 3, cx + r, cy + r + 3), 215, 325, fill=color, width=2)
    d.ellipse((cx - 1, cy + 3, cx + 2, cy + 6), fill=color)


def icon_clock(d, cx, cy, color):
    d.ellipse((cx - 8, cy - 8, cx + 8, cy + 8), outline=color, width=2)
    d.line((cx, cy, cx, cy - 5), fill=color, width=2)
    d.line((cx, cy, cx + 4, cy + 2), fill=color, width=2)


def icon_chip(d, cx, cy, color):
    d.rounded_rectangle((cx - 7, cy - 7, cx + 7, cy + 7), radius=3, outline=color, width=2)
    d.rectangle((cx - 3, cy - 3, cx + 3, cy + 3), outline=color, width=1)


def icon_thermo(d, cx, cy, color):
    d.rounded_rectangle((cx - 3, cy - 8, cx + 3, cy + 2), radius=3, outline=color, width=2)
    d.ellipse((cx - 5, cy + 1, cx + 5, cy + 11), outline=color, width=2)


def icon_disk(d, cx, cy, color):
    d.ellipse((cx - 8, cy - 5, cx + 8, cy + 5), outline=color, width=2)
    d.ellipse((cx - 2, cy - 2, cx + 2, cy + 2), outline=color, width=1)


def icon_net(d, cx, cy, color):
    d.ellipse((cx - 8, cy - 8, cx + 8, cy + 8), outline=color, width=2)
    d.line((cx - 8, cy, cx + 8, cy), fill=color, width=2)
    d.arc((cx - 4, cy - 8, cx + 4, cy + 8), 90, 270, fill=color, width=2)


def icon_list(d, cx, cy, color):
    for dy in (-6, 0, 6):
        d.line((cx - 8, cy + dy, cx + 8, cy + dy), fill=color, width=2)


def icon_box(d, cx, cy, color):
    d.rectangle((cx - 8, cy - 8, cx + 8, cy + 8), outline=color, width=2)
    d.line((cx - 8, cy - 2, cx + 8, cy - 2), fill=color, width=2)


def icon_user(d, cx, cy, color):
    d.ellipse((cx - 5, cy - 9, cx + 5, cy + 1), outline=color, width=2)
    d.arc((cx - 9, cy + 1, cx + 9, cy + 19), 200, 340, fill=color, width=2)


def icon_gear(d, cx, cy, color):
    d.ellipse((cx - 7, cy - 7, cx + 7, cy + 7), outline=color, width=2)
    for dx, dy in ((0, -9), (0, 9), (-9, 0), (9, 0)):
        d.line((cx + dx * 0.72, cy + dy * 0.72, cx + dx, cy + dy), fill=color, width=2)


ICONS = {"terminal": icon_list, "system": icon_chip, "net": icon_net, "disk": icon_disk,
         "proc": icon_list, "temp": icon_thermo, "pkg": icon_box, "user": icon_user,
         "gear": icon_gear}

TITLES = {}
MENU = [("Терминал", "terminal"), ("Система", "system"), ("Сеть", "net"),
        ("Диски", "disk"), ("Процессы", "proc"), ("Пакеты", "pkg"),
        ("Сервисы", "svc"), ("Пользователи", "user"), ("Настройки", "settings")]
TITLES = {k: l for l, k in MENU}


WALLPAPER = "/usr/local/share/console/wallpaper-cockpit.png"


def load_wallpaper(path=None):
    for p_ in (path, os.environ.get("COCKPIT_WALLPAPER"), WALLPAPER):
        if p_ and os.path.exists(p_):
            try:
                im = Image.open(p_).convert("RGB")
                k = max(W / im.width, H / im.height)
                im = im.resize((max(W, int(im.width * k + 0.5)),
                                max(H, int(im.height * k + 0.5))), Image.LANCZOS)
                left = (im.width - W) // 2
                top = (im.height - H) // 2
                return im.crop((left, top, left + W, top + H))
            except Exception as e:
                print("обои не открылись:", p_, e)
    return build_scene()


def build_scene():
    from PIL import ImageChops
    horizon = 545
    img = Image.new("RGB", (W, H), (4, 10, 17))
    d = ImageDraw.Draw(img)
    for y in range(horizon):
        t = (y / horizon) ** 1.5
        d.line((0, y, W, y), fill=(int(4 + 12 * t), int(11 + 22 * t), int(22 + 30 * t)))
    rnd = random.Random(11)
    for _ in range(320):
        x, y = rnd.randrange(W), int(rnd.randrange(horizon - 160) * 0.94)
        b = rnd.randint(45, 140)
        if rnd.random() < 0.07:
            b = rnd.randint(190, 240)
        d.point((x, y), fill=(b, b, min(255, int(b * 1.1))))
    mx, my = 1080, 150
    glow = Image.new("RGB", (W, H), (0, 0, 0))
    grad = Image.radial_gradient("L").resize((620, 620))
    mask = grad.point(lambda v: int((255 - v) ** 2 / 255 / 2.6))
    glow.paste(Image.new("RGB", (620, 620), (120, 158, 196)), (mx - 310, my - 310), mask)
    img = ImageChops.add(img, glow.filter(ImageFilter.GaussianBlur(14)))
    d = ImageDraw.Draw(img)
    d.ellipse((mx - 27, my - 27, mx + 27, my + 27), fill=(238, 244, 250))
    for base_y, color, (hmin, hmax), seed, blur in [
            (horizon - 118, (30, 52, 70), (120, 200), 5, 3.0),
            (horizon - 78, (22, 41, 57), (95, 160), 17, 2.2),
            (horizon - 44, (14, 28, 41), (70, 120), 29, 1.4),
            (horizon - 16, (9, 19, 29), (45, 85), 41, 0.8)]:
        rnd2 = random.Random(seed)
        layer = Image.new("RGB", (W, H), (0, 0, 0))
        m = Image.new("L", (W, H), 0)
        pts = [(0, horizon)]
        x = 0
        while x < W:
            step = rnd2.randint(150, 300)
            pts.append((x + step // 2, base_y - rnd2.randint(hmin // 2, hmax)))
            pts.append((x + step, base_y - rnd2.randint(-10, 20)))
            x += step
        pts.append((W, horizon))
        ImageDraw.Draw(layer).polygon(pts, fill=color)
        ImageDraw.Draw(m).polygon(pts, fill=255)
        if blur:
            layer, m = layer.filter(ImageFilter.GaussianBlur(blur)), m.filter(
                ImageFilter.GaussianBlur(blur))
        img.paste(layer, (0, 0), m)
    for y in range(horizon, H):
        t = (y - horizon) / max(1, H - horizon)
        d.line((0, y, W, y), fill=(int(6 + 4 * t), int(14 + 7 * t), int(23 + 10 * t)))
    return img


_CACHE = {}


def cached(key, ttl, fn):
    now = time.time()
    ent = _CACHE.get(key)
    if ent and now - ent[0] < ttl:
        return ent[1]
    try:
        val = fn()
    except Exception:
        val = None
    _CACHE[key] = (now, val)
    return val


def sh(cmd, timeout=3):
    try:
        return subprocess.run(cmd, shell=isinstance(cmd, str), capture_output=True,
                              text=True, timeout=timeout).stdout.strip()
    except Exception:
        return ""


def read_cpu():
    vals = [int(v) for v in open("/proc/stat").readline().split()[1:]]
    return sum(vals), vals[3] + vals[4]


def read_mem():
    info = {}
    for line in open("/proc/meminfo"):
        k, v = line.split(":", 1)
        info[k] = int(v.split()[0])
    total = info["MemTotal"] / 1024
    used = total - info.get("MemAvailable", info["MemFree"]) / 1024
    return used / total * 100, used, total


def read_disk(path="/"):
    st = os.statvfs(path)
    total = st.f_blocks * st.f_frsize / 1024 ** 3
    used = total - st.f_bavail * st.f_frsize / 1024 ** 3
    return (used / total * 100 if total else 0), used, total


def read_net():
    rx = tx = 0
    for line in open("/proc/net/dev").readlines()[2:]:
        name, data = line.split(":", 1)
        if name.strip() == "lo":
            continue
        f = data.split()
        rx += int(f[0])
        tx += int(f[8])
    return rx, tx


def read_temps():
    out = {}
    for i in range(8):
        base = f"/sys/class/thermal/thermal_zone{i}"
        if not os.path.isdir(base):
            continue
        try:
            out[open(f"{base}/type").read().strip()] = round(
                int(open(f"{base}/temp").read().strip()) / 1000)
        except Exception:
            pass
    return out


def read_procs(prev=None, dt=1.0):
    cur = {}
    for pid in os.listdir("/proc"):
        if not pid.isdigit():
            continue
        try:
            raw = open(f"/proc/{pid}/stat").read()
            r = raw.rfind(")")
            name = raw[raw.find("(") + 1:r]
            parts = raw[r + 2:].split()
            cur[int(pid)] = (name, int(parts[11]) + int(parts[12]),
                             int(parts[21]) * 4096 // 1024 ** 2)
        except Exception:
            continue
    out = []
    for pid, (name, ticks, rss) in cur.items():
        pticks = prev[pid][1] if (prev and pid in prev) else ticks
        cpu = max(0.0, (ticks - pticks) / os.sysconf("SC_CLK_TCK") / max(dt, 0.2) * 100)
        out.append({"pid": pid, "name": name, "cpu": cpu, "mem": rss})
    out.sort(key=lambda p: (-p["cpu"], -p["mem"]))
    return out[:6], cur


_PROC_PREV = {"d": None, "t": time.time()}


def top_procs():
    
    dt = max(0.2, time.time() - _PROC_PREV["t"])
    _PROC_PREV["t"] = time.time()
    procs, cur = read_procs(_PROC_PREV["d"], dt)
    _PROC_PREV["d"] = cur
    return procs


SERVICES = ["navidrome", "minidlna", "smbd", "shairport-sync", "ssh"]


def services_ok():
    ok = sum(1 for n in SERVICES
             if subprocess.run(["systemctl", "is-active", "--quiet", n],
                               timeout=2).returncode == 0)
    return ok, len(SERVICES)


def cpu_freq():
    try:
        raw = open("/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq").read().strip()
        return f"{int(raw) // 1000} МГц"
    except Exception:
        return "—"


def fmt_uptime():
    up = float(open("/proc/uptime").read().split()[0]) / 60
    return f"{int(up // 60)} ч {int(up % 60):02d} мин" if up >= 60 else f"{int(up)} мин"


def page_rows(page):
    
    if page == "system":
        mem = read_mem()
        disk = read_disk()
        tmp = read_temps()
        load = open("/proc/loadavg").read().split()[:3]
        model = open("/sys/firmware/devicetree/base/model").read().strip("\0") \
            if os.path.exists("/sys/firmware/devicetree/base/model") else "Amlogic S905X3"
        return [
            ("r", "Система", f"{os.popen('grep PRETTY_NAME /etc/os-release').read().split(chr(34))[1]}", C["text"]),
            ("r", "Ядро", os.uname().release, C["text"]),
            ("r", "Плата", model, C["text"]),
            ("r", "Время работы", fmt_uptime(), C["text"]),
            ("r", "Нагрузка", " ".join(load), C["teal"]),
            ("r", "Память", f"{mem[1]:.0f} из {mem[2]:.0f} Ми ({mem[0]:.0f}%)", C["teal"]),
            ("r", "Диск /", f"{disk[1]:.1f} из {disk[2]:.1f} ГБ ({disk[0]:.0f}%)", C["yellow"]),
            ("r", "Температура CPU",
             f"{tmp['cpu-thermal']} °C" if "cpu-thermal" in tmp else "нет датчика", C["orange"]),
            ("r", "Температура DDR",
             f"{tmp['ddr-thermal']} °C" if "ddr-thermal" in tmp else "нет датчика", C["orange"]),
            ("r", "Частота CPU", cached("freq", 5, cpu_freq), C["text"]),
            ("h", "Обслуживание"),
            ("r", "Журнал", "ограничен 100 МБ", C["dim"]),
            ("r", "TRIM (fstrim)", cached("trim", 60, lambda: sh("systemctl is-active fstrim.timer")), C["dim"]),
            ("r", "Автообновления", "включены", C["dim"]),
        ]
    if page == "net":
        ip = cached("ip", 10, lambda: sh("ip -4 -br a show wlan0").split()[2].split("/")[0]
                    if sh("ip -4 -br a show wlan0") else "—")
        ssid = cached("ssid", 30, lambda: (sh("nmcli -t -f ACTIVE,SSID dev wifi | grep '^yes'")
                                           .split(":")[-1]) or "—")
        sig = cached("sig", 30, lambda: sh("nmcli -t -f IN-USE,SIGNAL dev wifi | grep '^\\*'").split(":")[-1])
        gw = sh("ip route | grep default | head -1 | awk '{print $3}'") or "—"
        dns = sh("grep nameserver /etc/resolv.conf | head -1 | awk '{print $2}'") or "—"
        rx, tx = read_net()
        up = fmt_uptime()
        return [
            ("r", "Интерфейс", "wlan0 (Wi-Fi)", C["text"]),
            ("r", "Сеть", ssid, C["text"]),
            ("r", "IP-адрес", ip, C["teal"]),
            ("r", "Сигнал", f"{sig or '—'} %", C["teal"]),
            ("r", "Шлюз", gw, C["dim"]),
            ("r", "DNS", dns, C["dim"]),
            ("h", "Трафик за всё время"),
            ("r", "Принято", f"{rx / 1024 ** 3:.2f} ГБ", C["teal"]),
            ("r", "Отправлено", f"{tx / 1024 ** 3:.2f} ГБ", C["orange"]),
            ("h", "Открыто снаружи"),
            ("r", "Samba", "\\\\192.168.0.157\\share", C["dim"]),
            ("r", "DLNA", "порт 8200", C["dim"]),
            ("r", "Navidrome", "порт 4533", C["dim"]),
            ("r", "AirPlay", "Armbian TV", C["dim"]),
            ("r", "Прошло с включения", up, C["dim2"]),
        ]
    if page == "disk":
        rows = [("h", "Разделы")]
        for line in sh("df -h --output=target,size,used,avail,pcent -x tmpfs -x devtmpfs").splitlines()[1:]:
            p = line.split()
            if len(p) >= 5 and p[0] in ("/", "/boot", "/srv/share", "/home"):
                rows.append(("r", p[0], f"{p[2]} из {p[1]} ({p[4]})", C["yellow"]))
        st = os.statvfs("/")
        rows.append(("h", "Флеш-память"))
        rows.append(("bar", "Занято", 100 * (1 - st.f_bavail / st.f_blocks),
                     f"{read_disk()[1]:.1f} / {read_disk()[2]:.1f} ГБ", C["yellow"]))
        rows.append(("r", "TRIM", cached("trim2", 60, lambda: sh("systemctl is-active fstrim.timer")), C["green"]))
        rows.append(("r", "Резервная копия", "каждый день в 03:30", C["dim"]))
        rows.append(("r", "Куда", "/srv/share/backup", C["dim"]))
        return rows
    if page == "proc":
        procs = top_procs()
        rows = [("h", "Самые нагруженные прямо сейчас")]
        for p in procs:
            rows.append(("r", f"{p['name'][:22]} (pid {p['pid']})",
                         f"{p['cpu']:.1f}% · {p['mem']} МБ", C["teal"]))
        rows.append(("h", "Всего"))
        rows.append(("r", "Процессов в системе",
                     cached("cnt", 3, lambda: str(len([p for p in os.listdir('/proc') if p.isdigit()]))), C["text"]))
        rows.append(("r", "Потоков",
                     cached("thr", 3, lambda: sh("ps -eLf --no-headers | wc -l")), C["text"]))
        return rows
    if page == "pkg":
        n = cached("pkg", 120, lambda: sh("dpkg-query -f '.\\n' -W 2>/dev/null | wc -l"))
        up = cached("pkgup", 600, lambda: sh("apt list --upgradable 2>/dev/null | grep -c upgradable")
                    or "0")
        return [
            ("r", "Установлено пакетов", n or "—", C["text"]),
            ("r", "Доступно обновлений", up, C["yellow"]),
            ("r", "Обновления безопасности", "ставятся сами", C["green"]),
            ("h", "Основное из установленного"),
            ("r", "Navidrome", "v0.64.2 · порт 4533", C["dim"]),
            ("r", "MiniDLNA", "1.3.3 · порт 8200", C["dim"]),
            ("r", "Samba", "\\\\192.168.0.157\\share", C["dim"]),
            ("r", "Shairport-sync", "AirPlay «Armbian TV»", C["dim"]),
            ("r", "bluez-alsa", "Bluetooth-приёмник", C["dim"]),
            ("r", "python3-xlib + Pillow", "эта панель", C["dim"]),
            ("h", "Как поставить своё"),
            ("r", "Команда", "sudo apt install имя", C["dim2"]),
        ]
    if page == "svc":
        running = cached("svcrun", 15, lambda: sh(
            "systemctl list-units --type=service --state=running --no-legend --no-pager "
            "| awk '{print $1}' | sed 's/.service$//' | head -14"))
        failed = cached("svcfail", 15, lambda: sh("systemctl --failed --no-legend --no-pager | wc -l"))
        rows = [("r", "Активных", cached("svcn", 15, lambda: sh(
            "systemctl list-units --type=service --state=running --no-legend --no-pager | wc -l")),
            C["green"]),
            ("r", "Упавших", failed, C["green"] if failed in ("0", "0\n") else C["red"]),
            ("h", "Работают прямо сейчас")]
        for s in (running or "").splitlines()[:12]:
            rows.append(("r", s, "active", C["teal"]))
        return rows
    if page == "user":
        who = sh("who") or "—"
        rows = [("h", "Кто в системе")]
        for line in who.splitlines()[:4]:
            parts = line.split()
            rows.append(("r", parts[0], parts[-1] if parts else "", C["text"]))
        rows += [
            ("h", "Учётные записи"),
            ("r", "agent", "ваш рабочий пользователь", C["dim"]),
            ("r", "root", "системный (sudo)", C["dim"]),
            ("h", "Файлы"),
            ("r", "Общая папка", "/srv/share", C["dim"]),
            ("r", "Резервные копии", "/srv/share/backup", C["dim"]),
            ("r", "Музыка для Navidrome", "/srv/share/music", C["dim"]),
            ("r", "Обои панели", "/usr/local/share/console", C["dim"]),
        ]
        return rows
    if page == "settings":
        return [
            ("h", "Обслуживание панели"),
            ("r", "Сменить обои", "panel-wallpaper /фото.jpg", C["teal"]),
            ("r", "Вернуть встроенные", "panel-wallpaper --reset", C["teal"]),
            ("r", "Перезапустить панель", "sudo systemctl restart tty-console", C["teal"]),
            ("r", "Выключить панель", "sudo systemctl disable --now tty-console", C["dim"]),
            ("h", "Мини-ПК"),
            ("r", "Выключить", "sudo poweroff", C["orange"]),
            ("r", "Перезагрузить", "sudo reboot", C["orange"]),
            ("r", "Состояние", "health", C["teal"]),
            ("r", "Снимок экрана", "tvshot.py /home/agent/shot.png", C["teal"]),
            ("h", "Доступ агента"),
            ("r", "Код сессии", cached("tok", 5, lambda: (
                open("/run/agent-session.txt").read().strip()
                if os.path.exists("/run/agent-session.txt") else "—")), C["dim2"]),
            ("r", "Служба", "agent-access.service", C["dim2"]),
        ]
    return []


MAX_IMAGE_BYTES = 65535 * 4
DEFAULT_DIRTY = [(0, 0, W, TOPBAR_H),
                 (0, H - BOTTOMBAR_H, W, H),
                 (0, TOPBAR_H, SIDEBAR_W, H - BOTTOMBAR_H),
                 (RIGHT_X0 - 8, CONTENT_Y0 - 8, RIGHT_X1 + 8, CONTENT_Y1 + 4)]


def _put(drawable, gc, x, y, w, h, raw, X):
    row = w * 4
    step = max(1, min(h, MAX_IMAGE_BYTES // row))
    for off in range(0, h, step):
        n = min(step, h - off)
        drawable.put_image(gc, x, y + off, w, n, X.ZPixmap, 24, 0,
                           raw[off * row:(off + n) * row])


class Screen:
    

    def __init__(self):
        from Xlib import display, X
        self.X = X
        self.d = display.Display()
        scr = self.d.screen()
        self.win = scr.root.create_window(
            0, 0, W, H, 0, scr.root_depth, X.InputOutput, X.CopyFromParent,
            background_pixel=0,
            event_mask=X.ExposureMask | X.ButtonPressMask | X.StructureNotifyMask)
        self.win.change_attributes(override_redirect=1)
        self.win.set_wm_name("cockpit")
        self.win.map()
        self.pix = self.win.create_pixmap(W, H, scr.root_depth)
        self.gc = self.win.create_gc()
        self.d.sync()

    def show(self, img, rects):
        rgb = img.convert("RGB")
        for x0, y0, x1, y1 in rects:
            _put(self.pix, self.gc, x0, y0, x1 - x0, y1 - y0,
                 rgb.crop((x0, y0, x1, y1)).tobytes("raw", "BGRX"), self.X)
            self.win.copy_area(self.gc, self.pix, x0, y0, x1 - x0, y1 - y0, x0, y0)
        self.d.sync()

    def term_above(self):
        
        ids = {int(i) for i in sh("xdotool search --class URxvt 2>/dev/null").split()
               if i.isdigit()}
        if not ids:
            return True
        kids = [c.id for c in self.d.screen().root.query_tree().children]
        if self.win.id not in kids:
            return True
        mine = kids.index(self.win.id)
        top = max((kids.index(i) for i in ids if i in kids), default=-1)
        return top > mine

    def events(self):
        out = []
        while self.d.pending_events():
            e = self.d.next_event()
            if e.type == self.X.Expose:
                out.append(("expose", 0, 0))
            elif e.type == self.X.ButtonPress:
                out.append(("click", e.event_x, e.event_y))
        return out

    def set_wallpaper_on_root(self, img):
        
        from Xlib import Xatom
        root = self.d.screen().root
        pix = root.create_pixmap(W, H, self.d.screen().root_depth)
        gc = root.create_gc()
        _put(pix, gc, 0, 0, W, H, img.convert("RGB").tobytes("raw", "BGRX"), self.X)
        root.change_attributes(background_pixmap=pix)
        for name in ("_XROOTPMAP_ID", "ESETROOT_PMAP_ID"):
            try:
                root.change_property(self.d.intern_atom(name), Xatom.PIXMAP, 32, [pix.id])
            except Exception:
                pass
        root.clear_area(0, 0, W, H)
        self.d.sync()


def term_windows():
    ids = sh("xdotool search --class URxvt 2>/dev/null").split()
    return [i for i in ids if i.isdigit()]


def term_show(on):
    
    for wid in term_windows():
        sh(["xdotool", "windowmap" if on else "windowunmap", wid])
        if on:
            sh(["xdotool", "windowraise", wid])
            sh(["xdotool", "windowfocus", wid])





class Cockpit:
    def __init__(self, wallpaper=None):
        self.scene = load_wallpaper(wallpaper)
        self.base = self.build_base()
        self.hist_cpu = [0.0] * 60
        self.hist_net = [0.0] * 60
        self.prev_cpu = read_cpu()
        self.prev_net = read_net()
        self.prev_proc = None
        self.last_t = time.time()
        self.cpu_pct = self.mem_pct = self.rx_em = self.tx_em = 0.0
        self.page = "terminal"
        self.menu_hits = {}
        self.page_dirty = True

    def card_boxes(self):
        y = CONTENT_Y0
        boxes = {}
        for name, h in (("system", 206), ("net", 142), ("temp", 112), ("proc", 194)):
            boxes[name] = (RIGHT_X0, y, RIGHT_X1, y + h)
            y += h + 8
        return boxes

    def build_base(self):
        img = self.scene.copy().convert("RGB")
        glass(img, (0, 0, W, TOPBAR_H), radius=0, alpha=198, blur=10, strength=0.20)
        glass(img, (0, H - BOTTOMBAR_H, W, H), radius=0, alpha=198, blur=10, strength=0.20)
        glass(img, (0, TOPBAR_H, SIDEBAR_W, H - BOTTOMBAR_H), radius=0, alpha=170,
              blur=12, strength=0.22)
        glass(img, (CENTER_X0, CONTENT_Y0, CENTER_X1, CONTENT_Y1), radius=12,
              alpha=205, blur=12, strength=0.14)
        d = ImageDraw.Draw(img, "RGBA")
        d.rectangle((CENTER_X0 + 1, CONTENT_Y0 + 1, CENTER_X1 - 1, CONTENT_Y0 + 34),
                    fill=(13, 25, 36, 225))
        d.text((CENTER_X0 + 146, CONTENT_Y0 + 18), "+", font=F["ui_big"],
               fill=(120, 146, 165), anchor="lm")
        for ic, color in (("system", C["cyan"]), ("net", C["teal"]),
                          ("temp", C["orange"]), ("proc", C["violet"])):
            box = self.card_boxes()[ic]
            x0, y0 = box[0], box[1]
            ICONS[ic](d, x0 + 24, y0 + 24, color)
            text(d, (x0 + 40, y0 + 24),
                 {"system": "Система", "net": "Сеть", "temp": "Температура",
                  "proc": "Процессы"}[ic], "ui_b", C["text"], "lm")
        for box in self.card_boxes().values():
            glass(img, box, radius=12, alpha=196, blur=10, strength=0.22)
        d = ImageDraw.Draw(img, "RGBA")
        for ic, color in (("system", C["cyan"]), ("net", C["teal"]),
                          ("temp", C["orange"]), ("proc", C["violet"])):
            box = self.card_boxes()[ic]
            x0, y0 = box[0], box[1]
            ICONS[ic](d, x0 + 24, y0 + 24, color)
            text(d, (x0 + 40, y0 + 24),
                 {"system": "Система", "net": "Сеть", "temp": "Температура",
                  "proc": "Процессы"}[ic], "ui_b", C["text"], "lm")
        return img

    def frame(self, demo=False):
        dt = max(0.2, time.time() - self.last_t)
        self.last_t = time.time()
        if demo:
            cpu, mem, mem_u, mem_t = 22.0, 42.0, 842, 1985
            disk, disk_u, disk_t = 28.0, 6.2, 22.3
            rx, tx = 2.4 * 2**20, 314 * 1024
            temps = {"cpu-thermal": 48, "ddr-thermal": 53}
            procs = [{"pid": 1428, "name": "navidrome", "cpu": 4.2, "mem": 312},
                     {"pid": 1562, "name": "Xorg", "cpu": 2.1, "mem": 68},
                     {"pid": 1876, "name": "urxvt", "cpu": 1.8, "mem": 18},
                     {"pid": 1023, "name": "systemd", "cpu": 0.6, "mem": 18},
                     {"pid": 1102, "name": "smbd", "cpu": 0.4, "mem": 26}]
            if os.environ.get("COCKPIT_STRESS"):
                cpu, mem, mem_u, mem_t = 100.0, 100.0, 1937, 1937
                disk, disk_u, disk_t = 100.0, 14.0, 14.0
                rx, tx = 120.0 * 2**20, 88.0 * 2**20
                temps = {"cpu-thermal": 101, "ddr-thermal": 98}
                procs = [{"pid": 999999, "name": "systemd-journald-very-long-name",
                          "cpu": 100.0, "mem": 1937},
                         {"pid": 1, "name": "kworker/u8:3-events_unbound", "cpu": 9.9, "mem": 5},
                         {"pid": 2, "name": "NetworkManager-dispatcher", "cpu": 8.8, "mem": 4}]
        else:
            total, idle = read_cpu()
            dtot, didle = total - self.prev_cpu[0], idle - self.prev_cpu[1]
            self.prev_cpu = (total, idle)
            cpu = 100.0 * (1 - didle / dtot) if dtot > 0 else 0.0
            mem, mem_u, mem_t = read_mem()
            disk, disk_u, disk_t = read_disk()
            r, t = read_net()
            rx, tx = max(0, r - self.prev_net[0]) / dt, max(0, t - self.prev_net[1]) / dt
            self.prev_net = (r, t)
            temps = read_temps()
            procs, self.prev_proc = read_procs(self.prev_proc, dt)

        self.cpu_pct = self.cpu_pct * 0.45 + cpu * 0.55
        self.mem_pct = self.mem_pct * 0.6 + mem * 0.4
        self.rx_em = self.rx_em * 0.45 + rx * 0.55
        self.tx_em = self.tx_em * 0.45 + tx * 0.55
        self.hist_cpu = self.hist_cpu[1:] + [self.cpu_pct]
        self.hist_net = self.hist_net[1:] + [self.rx_em]

        img = self.base.copy()
        d = ImageDraw.Draw(img, "RGBA")
        self.draw_topbar(d, demo)
        self.draw_menu(d, demo)
        self.draw_system(d, self.cpu_pct, self.mem_pct, mem_u, mem_t, disk, disk_u, disk_t)
        self.draw_net(d, self.rx_em, self.tx_em)
        self.draw_temp(d, temps)
        self.draw_proc(d, procs)
        self.draw_status(d)
        self.draw_center(d)
        return img

    def draw_topbar(self, d, demo):
        d.ellipse((18, 11, 38, 31), fill=C["teal"])
        icon_chip(d, 28, 21, (6, 20, 24))
        text(d, (46, 21), "Armbian TV", "ui_b", C["text"], "lm")
        text(d, (150, 21), "│", "ui", (38, 58, 74), "lm")
        text_fit(d, (166, 21), "Linux " + os.uname().release, "ui", C["dim"], "lm", max_w=620)
        ip = "192.168.0.157" if demo else cached("ipaddr", 10, lambda: (
            sh("ip -4 -br a show wlan0").split()[2].split("/")[0]
            if len(sh("ip -4 -br a show wlan0").split()) > 2 else ""))
        clock_s = time.strftime("%d.%m %H:%M")
        clock_x = W - 18 - d.textlength(clock_s, font=F["ui"])
        icon_clock(d, clock_x - 16, 21, C["dim"])
        text(d, (W - 18, 21), clock_s, "ui", C["text"], "rm")
        ip_s = ip or "нет сети"
        ip_x = clock_x - 46 - d.textlength(ip_s, font=F["ui"])
        icon_wifi(d, ip_x - 16, 20, C["teal"] if ip else C["red"])
        text(d, (ip_x, 21), ip_s, "ui", C["text"] if ip else C["red"], "lm")

    def draw_menu(self, d, demo):
        y = TOPBAR_H + 16
        self.menu_hits = {}
        for label, key in MENU:
            box = (10, y, SIDEBAR_W - 12, y + 40)
            active = (key == self.page)
            if active:
                rrect(d, box, 9, fill=(14, 116, 144, 235))
            self.menu_hits[key] = box
            ICONS["terminal" if key == "terminal" else
                  {"system": "system", "net": "net", "disk": "disk", "proc": "proc",
                   "pkg": "pkg", "svc": "temp", "user": "user",
                   "settings": "gear"}[key]](d, 34, y + 20,
                                              C["text"] if active else C["dim"])
            text_fit(d, (56, y + 20), label, "ui",
                     C["text"] if active else C["dim"], "lm", max_w=SIDEBAR_W - 70)
            y += 46

        ok, tot = (5, 5) if demo else (cached("svc", 15, services_ok) or (0, 5))
        by = H - BOTTOMBAR_H - 88
        rrect(d, (12, by, SIDEBAR_W - 14, by + 78), 10, fill=(10, 20, 29, 200),
              outline=(26, 44, 58, 210))
        text(d, (24, by + 14), "Службы", "ui_sm", C["dim"], "lm")
        d.ellipse((24, by + 28, 34, by + 38), fill=C["green"] if ok == tot else C["yellow"])
        text(d, (42, by + 33), f"{ok} из {tot} активны", "ui_sm", C["text"], "lm")
        text_fit(d, (24, by + 50), "AirPlay · DLNA · Samba", "ui_sm", C["dim2"], "lm",
                 max_w=SIDEBAR_W - 46)
        tok = cached("tok2", 5, lambda: (open("/run/agent-session.txt").read().strip()
                                         if os.path.exists("/run/agent-session.txt") else ""))
        if tok:
            short = tok if len(tok) <= 12 else tok[:6] + "…" + tok[-4:]
            text(d, (24, by + 65), f"агент: {short}", "ui_sm", C["dim2"], "lm")

    def draw_system(self, d, cpu, mem, mem_u, mem_t, disk, disk_u, disk_t):
        x0, y0, x1, _ = self.card_boxes()["system"]
        rows = [("CPU", cpu, C["cyan"], f"{cpu:.0f}%"),
                ("RAM", mem, C["teal"], f"{mem:.0f}%"),
                ("Диск", disk, C["yellow"], f"{disk:.0f}%")]
        y = y0 + 60
        for label, frac, color, val in rows:
            ring(d, x0 + 34, y + 16, 19, frac / 100, color, 6)
            text(d, (x0 + 34, y + 16), val, "mono_b", C["text"], "mm")
            text(d, (x0 + 70, y + 6), label, "ui_sm", C["dim"], "lm")
            detail = {"CPU": f"{cpu:.0f}%  загрузка",
                      "RAM": f"{mem_u:.0f} / {mem_t:.0f} Ми",
                      "Диск": f"{disk_u:.1f} / {disk_t:.0f} ГБ"}[label]
            text_fit(d, (x0 + 70, y + 24), detail, "ui_sm", C["text"], "lm", max_w=92)
            bx0, bx1 = x0 + 170, x1 - 16
            d.line((bx0, y + 18, bx1, y + 18), fill=C["stroke"], width=3)
            d.line((bx0, y + 18, bx0 + (bx1 - bx0) * frac / 100, y + 18), fill=color, width=3)
            y += 50

    def draw_net(self, d, rx, tx):
        x0, y0, x1, y1 = self.card_boxes()["net"]

        def rate(v):
            return f"{v / 2**20:.1f} МБ/с" if v > 2**20 else f"{v / 1024:.0f} КБ/с"

        text(d, (x0 + 24, y0 + 58), "↓  Загрузка", "ui_sm", C["dim"], "lm")
        text(d, (x1 - 18, y0 + 58), rate(rx), "mono_b", C["teal"], "rm")
        text(d, (x0 + 24, y0 + 80), "↑  Отправка", "ui_sm", C["dim"], "lm")
        text(d, (x1 - 18, y0 + 80), rate(tx), "mono_b", C["orange"], "rm")
        sparkline(d, (x0 + 16, y0 + 90, x1 - 16, y1 - 14), self.hist_net, C["teal"])

    def draw_temp(self, d, temps):
        x0, y0, x1, y1 = self.card_boxes()["temp"]
        rows = [("CPU", temps.get("cpu") or temps.get("cpu-thermal")),
                ("DDR", temps.get("ddr") or temps.get("ddr-thermal")),
                ("Плата", temps.get("board") or temps.get("boot"))]
        rows = [r for r in rows if r[1]]
        y = y0 + 56
        for label, val in rows:
            d.ellipse((x0 + 22, y - 4, x0 + 30, y + 4), fill=C["dim2"])
            text(d, (x0 + 40, y), label, "ui_sm", C["dim"], "lm")
            col = C["green"] if val < 55 else (C["yellow"] if val < 70 else C["red"])
            text(d, (x1 - 18, y), f"{int(val)} °C", "mono_b", col, "rm")
            y += 26

    def draw_proc(self, d, procs):
        x0, y0, x1, y1 = self.card_boxes()["proc"]
        text(d, (x0 + 22, y0 + 48), "PID", "mono_sm", C["dim2"], "lm")
        text(d, (x0 + 74, y0 + 48), "ИМЯ", "mono_sm", C["dim2"], "lm")
        text(d, (x1 - 108, y0 + 48), "CPU", "mono_sm", C["dim2"], "lm")
        text(d, (x1 - 54, y0 + 48), "ПАМ", "mono_sm", C["dim2"], "lm")
        y = y0 + 72
        for p in procs[:max(3, (y1 - y - 8) // 22)]:
            text(d, (x0 + 22, y), str(p["pid"]), "mono_sm", C["dim"], "lm")
            text_fit(d, (x0 + 74, y), p["name"], "mono_sm", C["text"], "lm",
                     max_w=(x1 - 118) - (x0 + 74))
            text(d, (x1 - 108, y), f"{p['cpu']:.1f}%", "mono_sm", C["teal"], "lm")
            text(d, (x1 - 54, y), f"{p['mem']:.0f}М", "mono_sm", C["dim"], "lm")
            y += 22

    def draw_status(self, d):
        text(d, (18, H - BOTTOMBAR_H // 2), "●", "ui", C["green"], "lm")
        text(d, (36, H - BOTTOMBAR_H // 2), "agent@armbian", "mono", C["dim"], "lm")
        text(d, (150, H - BOTTOMBAR_H // 2), "/home/agent", "mono", C["dim2"], "lm")
        text(d, (W - 18, H - BOTTOMBAR_H // 2),
             f"Armbian trixie · ядро {os.uname().release} · {fmt_uptime()}",
             "ui_sm", C["dim2"], "rm")

    def draw_center(self, d, force_page=None):
        page = force_page or self.page
        x0, y0, x1, y1 = CENTER_X0, CONTENT_Y0, CENTER_X1, CONTENT_Y1
        title = TITLES.get(page, page)
        tw = d.textlength(title, font=F["ui_sm"])
        rrect(d, (x0 + 10, y0 + 6, x0 + 34 + tw, y0 + 30), 6, fill=(14, 66, 82, 235))
        text(d, (x0 + 22, y0 + 18), title, "ui_sm", (226, 244, 250), "lm")
        if page == "terminal":
            return
        bx0, by0, bx1, by1 = BODY
        rows = page_rows(page)
        y = by0 + 24
        for r in rows:
            if y > by1 - 20:
                break
            if r[0] == "h":
                y += 12
                text_fit(d, (bx0, y), r[1].upper(), "ui_sm", C["cyan"], "lm",
                         max_w=bx1 - bx0)
                d.line((bx0, y + 12, bx1, y + 12), fill=(38, 62, 78, 200), width=1)
                y += 26
            elif r[0] == "bar":
                label, frac, val, color = r[1], r[2], r[3], r[4]
                text(d, (bx0, y), label, "ui_sm", C["dim"], "lm")
                text(d, (bx1, y), val, "mono_b", C["text"], "rm")
                bw = 300
                d.line((bx0, y + 16, bx0 + bw, y + 16), fill=C["stroke"], width=6)
                d.line((bx0, y + 16, bx0 + bw * min(1, frac / 100), y + 16), fill=color, width=6)
                y += 34
            else:
                _, label, val, color = r
                text_fit(d, (bx0, y), label, "ui_sm", C["dim"], "lm", max_w=300)
                text_fit(d, (bx1, y), str(val), "mono_b", color, "rm", max_w=bx1 - bx0 - 310)
                y += 30


def main():
    args = sys.argv[1:]
    demo = "--demo" in args
    loop = "--loop" in args
    out = args[args.index("--out") + 1] if "--out" in args else "/tmp/cockpit.bmp"
    wall = args[args.index("--wallpaper") + 1] if "--wallpaper" in args else None
    page = args[args.index("--page") + 1] if "--page" in args else "terminal"

    cp = Cockpit(wall)
    cp.page = page

    if demo:
        img = cp.frame(demo=True)
        fmt = "BMP" if out.lower().endswith((".bmp", ".tmp")) else None
        img.save(out, format=fmt) if fmt else img.save(out)
        print("кадр:", out)
        return

    if not loop:
        cp.frame().save(out, format="BMP")
        return

    scr = Screen()
    scr.set_wallpaper_on_root(cp.scene)
    term_show(True)
    cp.page = "terminal"
    last_raise = 0.0
    full = True
    while True:
        t0 = time.time()
        for kind, mx, my in scr.events():
            if kind == "expose":
                full = True
                if cp.page == "terminal":
                    term_show(True)
                continue
            for key, (bx0, by0, bx1, by1) in cp.menu_hits.items():
                if bx0 <= mx <= bx1 and by0 <= my <= by1:
                    if cp.page != key:
                        cp.page = key
                        term_show(key == "terminal")
                        full = True
                    break
        try:
            img = cp.frame()
            if full:
                scr.show(img, [(0, 0, W, H)])
                full = False
                if cp.page == "terminal":
                    term_show(True)
            else:
                dirty = list(DEFAULT_DIRTY)
                if cp.page != "terminal":
                    dirty.append((CENTER_X0, CONTENT_Y0, CENTER_X1, CONTENT_Y1))
                scr.show(img, dirty)
        except Exception as e:
            print("ошибка кадра:", e, flush=True)
        if cp.page == "terminal" and time.time() - last_raise > 5.0:
            last_raise = time.time()
            if not scr.term_above():
                term_show(True)
        rest = REFRESH - (time.time() - t0)
        if rest > 0:
            time.sleep(min(rest, 0.05))
            while rest > 0:
                time.sleep(min(0.05, rest))
                for kind, mx, my in scr.events():
                    if kind == "expose":
                        full = True
                        if cp.page == "terminal":
                            term_show(True)
                        continue
                    for key, (bx0, by0, bx1, by1) in cp.menu_hits.items():
                        if bx0 <= mx <= bx1 and by0 <= my <= by1:
                            if cp.page != key:
                                cp.page = key
                                term_show(key == "terminal")
                                full = True
                            break
                rest = REFRESH - (time.time() - t0)


if __name__ == "__main__":
    main()

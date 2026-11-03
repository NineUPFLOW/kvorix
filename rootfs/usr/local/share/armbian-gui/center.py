#!/usr/bin/env python3

import glob
import json
import math
import os
import re
import struct
import subprocess
import tempfile
import threading
import time
import wave

_RUN = "/run/user/%d" % os.getuid()
_PID = os.path.join(_RUN if os.path.isdir(_RUN) else "/tmp", "armbian-center.pid")
_REQ = _PID[:-3] + "req"


def _forward():
    page = ""
    for a in os.sys.argv[1:]:
        if a.startswith("--page="):
            page = a.split("=", 1)[1]
    try:
        pid = int(open(_PID).read().strip())
        if pid != os.getpid() and b"center.py" in open("/proc/%d/cmdline" % pid, "rb").read():
            if "--prewarm" not in os.sys.argv:
                with open(_REQ, "w") as f:
                    f.write(page)
                os.kill(pid, 10)
            os.sys.exit(0)
    except (OSError, ValueError):
        pass


if __name__ == "__main__":
    _forward()

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Gdk, GdkPixbuf, GLib, Gtk

import autostart as A
import common as C
import ui

WALL_DIR = C.WALL_DIR
THEME_DIRS = ["/usr/share/themes"]
ICON_DIRS = ["/usr/share/icons"]


def _spawn(cmd, **kw):
    
    p = subprocess.Popen(cmd, **kw)
    GLib.timeout_add(250, lambda: p.poll() is None)
    return p


def lsdirs(paths):
    res = []
    for p in paths:
        if os.path.isdir(p):
            for d in sorted(os.listdir(p)):
                if os.path.isdir(os.path.join(p, d)):
                    res.append(d)
    return res


def xfset(channel, prop, value):
    code, o = C.run(["xfconf-query", "-c", channel, "-p", prop, "-s", str(value)], timeout=8)
    if code != 0:
        C.run(["xfconf-query", "-c", channel, "-p", prop, "-n", "-t", "string",
               "-s", str(value)], timeout=8)


def xfget(channel, prop, default="—"):
    code, o = C.run(["xfconf-query", "-c", channel, "-p", prop], timeout=6)
    return o.strip() if code == 0 and o.strip() else default


def log_window(parent, title, logfile):
    
    w = Gtk.Window(title=title, transient_for=parent)
    w.set_default_size(760, 460)
    sw = Gtk.ScrolledWindow()
    tv = Gtk.TextView()
    tv.set_editable(False)
    tv.set_monospace(True)
    buf = tv.get_buffer()
    sw.add(tv)
    w.add(sw)
    w.show_all()

    def tick():
        if os.path.exists(logfile):
            txt = open(logfile, errors="replace").read()[-20000:]
            buf.set_text(txt)
            it = buf.get_end_iter()
            tv.scroll_to_iter(it, 0.0, False, 0, 0)
        return w.get_visible()

    GLib.timeout_add(900, tick)
    return w


class _Into:
    
    def __init__(self, page, box):
        self._page, self._box = page, box

    def add(self, w):
        self._box.pack_start(w, False, False, 0)

    def card(self, *a, **kw):
        c = ui.Card(*a, **kw)
        self.add(c)
        return c

    def __getattr__(self, k):
        return getattr(self._page, k)


STORE = [
    ("vlc", "VLC", "Плеер любого видео и музыки", "vlc", "vlc"),
    ("kodi", "Kodi", "Медиацентр для телевизора", "kodi", "kodi"),
    ("firefox-esr", "Firefox", "Второй браузер", "firefox-esr", "firefox-esr"),
    ("telegram-desktop", "Telegram", "Мессенджер", "telegram", "telegram-desktop"),
    ("libreoffice-writer", "LibreOffice Writer", "Документы Word", "libreoffice-writer", "libreoffice --writer"),
    ("gimp", "GIMP", "Редактор фото", "gimp", "gimp"),
    ("transmission-gtk", "Transmission", "Торрент-клиент", "transmission", "transmission-gtk"),
    ("audacious", "Audacious", "Музыкальный плеер", "audacious", "audacious"),
    ("thunderbird", "Thunderbird", "Почта", "thunderbird", "thunderbird"),
    ("keepassxc", "KeePassXC", "Менеджер паролей", "keepassxc", "keepassxc"),
    ("retroarch", "RetroArch", "Ретро-игры и эмуляторы", "retroarch", "retroarch"),
    ("filezilla", "FileZilla", "FTP-клиент", "filezilla", "filezilla"),
]


FP_SCREENS = [("clock", "Часы"), ("date", "Дата"), ("temp", "Температура"), ("cpu", "Загрузка процессора"),
              ("ram", "Память"), ("disk", "Диск"), ("wifi", "Сигнал Wi-Fi"), ("uptime", "Время работы")]
TIMEZONES = ["Europe/Kaliningrad", "Europe/Moscow", "Europe/Samara", "Asia/Yekaterinburg", "Asia/Omsk",
             "Asia/Novosibirsk", "Asia/Krasnoyarsk", "Asia/Irkutsk", "Asia/Yakutsk", "Asia/Vladivostok",
             "Asia/Magadan", "Asia/Kamchatka", "Europe/Minsk", "Europe/Kyiv", "Asia/Almaty", "Asia/Tashkent", "UTC"]
TZ_NAMES = {"Europe/Kaliningrad": "Калининград (UTC+2)", "Europe/Moscow": "Москва (UTC+3)",
            "Europe/Samara": "Самара (UTC+4)", "Asia/Yekaterinburg": "Екатеринбург (UTC+5)", "Asia/Omsk": "Омск (UTC+6)",
            "Asia/Novosibirsk": "Новосибирск (UTC+7)", "Asia/Krasnoyarsk": "Красноярск (UTC+7)",
            "Asia/Irkutsk": "Иркутск (UTC+8)", "Asia/Yakutsk": "Якутск (UTC+9)", "Asia/Vladivostok": "Владивосток (UTC+10)",
            "Asia/Magadan": "Магадан (UTC+11)", "Asia/Kamchatka": "Камчатка (UTC+12)", "Europe/Minsk": "Минск (UTC+3)",
            "Europe/Kyiv": "Киев (UTC+2/+3)", "Asia/Almaty": "Алматы (UTC+5)", "Asia/Tashkent": "Ташкент (UTC+5)",
            "UTC": "UTC"}
_USB_KIND = {"01": "звук", "02": "модем/сеть", "03": "ввод", "06": "телефон/камера", "07": "принтер",
             "08": "накопитель", "0a": "модем/сеть", "0e": "веб-камера", "e0": "беспроводной адаптер", "ff": "устройство"}


def usb_devices():
    
    res = []
    for d in sorted(glob.glob("/sys/bus/usb/devices/[0-9]*-[0-9]*")):
        if ":" in os.path.basename(d) or not os.path.exists(d + "/idVendor"):
            continue
        name = (C.read(d + "/manufacturer") + " " + C.read(d + "/product")).strip() or \
            "%s:%s" % (C.read(d + "/idVendor"), C.read(d + "/idProduct"))
        kinds, ok = [], True
        for itf in glob.glob(d + ":*"):
            cls = C.read(itf + "/bInterfaceClass")
            if cls == "09":
                continue
            k = _USB_KIND.get(cls, "устройство")
            if cls == "03":
                k = {"01": "клавиатура", "02": "мышь"}.get(C.read(itf + "/bInterfaceProtocol"), "пульт/кнопки")
            if k not in kinds:
                kinds.append(k)
            if not os.path.exists(itf + "/driver") and cls not in ("06",):
                ok = False
        if kinds:
            res.append((name, ", ".join(kinds), ok))
    return res


def removable_mounts():
    
    import json as _j
    try:
        data = _j.loads(C.out(["lsblk", "-J", "-o", "NAME,PATH,LABEL,MOUNTPOINT,SIZE,RM,HOTPLUG"]))
    except ValueError:
        return []
    res = []
    def walk(nodes, removable):
        for n in nodes or []:
            rm = removable or n.get("rm") in (True, "1") or n.get("hotplug") in (True, "1")
            if rm and n.get("mountpoint"):
                res.append((n["path"], n.get("label") or n["name"], n["mountpoint"], n.get("size") or ""))
            walk(n.get("children"), rm)
    walk(data.get("blockdevices"), False)
    return res


def pointer_names():
    
    names = []
    for block in C.read("/proc/bus/input/devices").split("\n\n"):
        if "mouse" in block and "Handlers" in block:
            n = next((l.split("=", 1)[1].strip('"') for l in block.splitlines() if l.startswith("N: Name=")), "")
            if n and n.replace(" ", "_") not in names:
                names.append(n.replace(" ", "_"))
    return names


def _model():
    m = C.read("/proc/device-tree/model").strip("\x00 \n")
    return m or "Мини-ПК Kvorix"


MENU = [
    ("overview", "Главная", "go-home-symbolic"),
    ("__sec__", "Система", ""),
    ("display", "Экран", "video-display-symbolic"),
    ("sound", "Звук", "audio-volume-high-symbolic"),
    ("power", "Питание", "system-shutdown-symbolic"),
    ("disks", "Хранилище", "drive-harddisk-symbolic"),
    ("perf", "Быстродействие", "utilities-system-monitor-symbolic"),
    ("__sec__", "Устройства и сеть", ""),
    ("network", "Сеть и интернет", "network-wireless-symbolic"),
    ("bluetooth", "Bluetooth", "bluetooth-active-symbolic"),
    ("devices", "Устройства", "input-mouse-symbolic"),
    ("__sec__", "Персонализация", ""),
    ("appearance", "Оформление", "preferences-desktop-appearance-symbolic"),
    ("wallpaper", "Обои", "preferences-desktop-wallpaper-symbolic"),
    ("timelang", "Время и язык", "preferences-desktop-locale-symbolic"),
    ("__sec__", "Приложения", ""),
    ("packages", "Приложения", "view-app-grid-symbolic"),
    ("autostart", "Автозагрузка", "system-run-symbolic"),
    ("services", "Фоновые службы", "applications-system-symbolic"),
    ("__sec__", "Учётные записи и защита", ""),
    ("users", "Учётные записи", "system-users-symbolic"),
    ("security", "Безопасность", "security-high-symbolic"),
    ("updates", "Обновления", "software-update-available-symbolic"),
    ("ai", "Доступ ИИ", "network-server-symbolic"),
    ("system", "О системе", "help-about-symbolic"),
]
KEYWORDS = {
    "bluetooth": "bluetooth",
    "devices": "usb флешка мышь клавиатура принтер сканер камера телефон геймпад devices printer mouse keyboard",
    "timelang": "время часовой пояс дата язык раскладка клавиатуры time timezone language keyboard layout",
    "overview": "обзор домой начало home",
    "display": "монитор разрешение тв hdmi размер края подгонка display screen resolution monitor",
    "sound": "громкость динамики hdmi аудио sound audio volume",
    "network": "сеть wifi вайфай интернет ip dns network wifi internet",
    "appearance": "тема тёмная светлая цвет акцент прозрачность анимация ночной theme dark light accent personalization",
    "wallpaper": "фон рабочий стол картинка wallpaper background",
    "power": "выключение перезагрузка сон power shutdown reboot",
    "packages": "магазин store программы установить удалить apt apps programs install",
    "autostart": "запуск при входе startup autostart",
    "users": "пользователи пароль аккаунт users accounts password",
    "updates": "обновить apt пакеты update upgrade",
    "security": "брандмауэр ssh firewall security firewall",
    "ai": "агент удалённый доступ claude ai agent remote access",
    "perf": "быстродействие производительность скорость нагрузка процессор память частота температура zram performance cpu ram",
    "disks": "диски память место emmc storage disk",
    "services": "службы фоновые процессы сервисы демоны автозапуск systemd services daemons",
    "system": "версия ядро железо armbian kvorix about system info",
}
TILES = [("network", "Wi-Fi", "network-wireless-symbolic"),
         ("bluetooth", "Bluetooth", "bluetooth-active-symbolic"),
         ("display", "Экран", "video-display-symbolic"),
         ("appearance", "Оформление", "preferences-desktop-appearance-symbolic"),
         ("updates", "Обновления", "software-update-available-symbolic"),
         ("ai", "Доступ ИИ", "network-server-symbolic")]

EXTRA_CSS = """
.nav image { color: alpha(@text, 0.75); }
.nav row:selected image { color: @accent; }
.card-head image { color: @accent; }
.tile-ic { min-width: 36px; min-height: 36px; border-radius: 10px; color: #ffffff; margin-bottom: 4px; }
.tile-ic-network { background-color: #2f7cf6; }
.tile-ic-bluetooth { background-color: #5b6cf0; }
.tile-ic-display { background-color: #0f9d8f; }
.tile-ic-appearance { background-color: #c2410c; }
.tile-ic-updates { background-color: #16a34a; }
.tile-ic-ai { background-color: #7c3aed; }
.profile { padding: 18px 16px 10px 16px; }
.profile-name { font-size: 15px; font-weight: 700; }
.side-search { margin: 4px 12px 10px 12px; }
.hero-name { font-size: 24px; font-weight: 700; }
.tile { padding: 14px; border-radius: 10px; background-image: none;
        background-color: @card; border: 1px solid @border; }
.tile:hover { border-color: @accent; }
.tile-title { font-size: 14px; font-weight: 600; }
"""


class Center(Gtk.Window):
    def __init__(self, start_page=None):
        super().__init__(title="Настройки")
        self.set_default_size(1340, 700)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_icon_name("preferences-system")

        hb = Gtk.HeaderBar(show_close_button=True)
        hb.set_title("Настройки")
        self.set_titlebar(hb)

        root = Gtk.Box()
        self.add(root)

        side = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        side.get_style_context().add_class("sidebar")
        side.set_size_request(244, -1)
        prof = Gtk.Box(spacing=12)
        prof.get_style_context().add_class("profile")
        av = Gtk.Image.new_from_icon_name("avatar-default", Gtk.IconSize.DND)
        av.set_pixel_size(44)
        prof.pack_start(av, False, False, 0)
        pv = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        pv.set_valign(Gtk.Align.CENTER)
        n = Gtk.Label(label=C.USER, xalign=0)
        n.get_style_context().add_class("profile-name")
        m = Gtk.Label(label="%s · %s" % (os.uname().nodename, _model()), xalign=0)
        m.get_style_context().add_class("muted")
        m.set_ellipsize(3)
        pv.pack_start(n, False, False, 0)
        pv.pack_start(m, False, False, 0)
        prof.pack_start(pv, True, True, 0)
        side.pack_start(prof, False, False, 0)
        self.search = Gtk.SearchEntry(placeholder_text="Найти параметр")
        self.search.get_style_context().add_class("side-search")
        side.pack_start(self.search, False, False, 0)

        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.stack.set_transition_duration(140)

        self.pages = []
        self.builders = {
            "overview": self.page_overview,
            "system": self.page_system,
            "display": self.page_display,
            "sound": self.page_sound,
            "network": self.page_network,
            "bluetooth": self.page_bluetooth,
            "disks": self.page_disks,
            "packages": self.page_packages,
            "users": self.page_users,
            "autostart": self.page_autostart,
            "services": self.page_services,
            "perf": self.page_perf,
            "updates": self.page_updates,
            "security": self.page_security,
            "ai": self.page_ai,
            "appearance": self.page_appearance,
            "wallpaper": self.page_wallpaper,
            "power": self.page_power,
            "devices": self.page_devices,
            "timelang": self.page_timelang,
        }
        menu = MENU

        lst = Gtk.ListBox()
        lst.set_selection_mode(Gtk.SelectionMode.SINGLE)
        lst.get_style_context().add_class("nav")
        self.rows = {}
        for i, (key, title, icon) in enumerate(menu):
            r = Gtk.ListBoxRow()
            if key == "__sec__":
                r.key = None
                r.set_selectable(False)
                r.set_activatable(False)
                l = Gtk.Label(label=title.upper(), xalign=0)
                l.get_style_context().add_class("nav-section")
                self.__dict__.setdefault("_nav_text", []).append(r)
                b = Gtk.Box()
                b.set_margin_top(10)
                b.set_margin_start(14)
                b.pack_start(l, False, False, 0)
                r.add(b)
                lst.add(r)
                continue
            b = Gtk.Box(spacing=10)
            b.set_margin_top(1)
            img = Gtk.Image.new_from_icon_name(icon, Gtk.IconSize.MENU)
            lab = Gtk.Label(label=title, xalign=0)
            b.pack_start(img, False, False, 0)
            b.pack_start(lab, True, True, 0)
            self.__dict__.setdefault("_nav_text", []).append(lab)
            r.add(b)
            r.key = key
            r.words = (title + " " + KEYWORDS.get(key, "")).lower()
            lst.add(r)
            self.rows[key] = r
        lst.connect("row-selected", self.on_row)

        from settings_search import attach as attach_settings_search
        self.settings_search = attach_settings_search(
            self, self.search, lst, MENU, KEYWORDS, __file__)
        sc = Gtk.ScrolledWindow()
        sc.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        sc.add(lst)
        side.pack_start(sc, True, True, 0)
        root.pack_start(side, False, False, 0)

        holder = Gtk.ScrolledWindow()
        holder.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
        holder.set_propagate_natural_width(False)
        holder.set_propagate_natural_height(False)
        holder.add(self.stack)
        self.content = holder
        root.pack_start(holder, True, True, 0)

        self.built = {}
        first = start_page if start_page in self.builders else "overview"
        self.show_page(first)
        lst.select_row(self.rows[first])
        self.connect("delete-event", lambda *a: self.search.set_text("") or self.hide() or True)
        self._side, self._compact = side, None
        self.connect("size-allocate", self._adapt)

    def _adapt(self, _w, alloc):
        compact = alloc.width < 900
        if compact == self._compact:
            return
        self._compact = compact
        self._side.set_size_request(64 if compact else 244, -1)
        for w in self._nav_text + [self.search, self._side.get_children()[0]]:
            w.set_visible(not compact)

    def _visible_only(self, fn):
        self.__dict__.setdefault("_ticks", []).append(fn)
        return lambda: fn() if self.get_visible() else True

    def refresh_now(self):
        for fn in getattr(self, "_ticks", []):
            try:
                fn()
            except Exception:
                pass

    def open_page(self, key):
        if key in self.builders:
            self.show_page(key)
            row = self.rows[key]
            row.get_parent().select_row(row)

    def on_row(self, lst, row):
        if row is not None:
            self.show_page(row.key)

    def show_page(self, key):
        if key not in self.built:
            page = self.builders[key]()
            self.built[key] = page
            self.stack.add_named(page, key)
            page.show_all()
        self.stack.set_visible_child_name(key)

    def live_row(self, parent, label, getter, suffix=""):
        r = ui.info_row(label, lambda: "%s%s" % (getter(), suffix))
        parent.add(r)
        return r

    def page_overview(self):
        p = ui.Page("Главная", "Устройство и самое нужное — в один клик")
        self.ov = {}

        hero = ui.Card()
        hero.get_style_context().add_class("hero")
        hb_ = Gtk.Box(spacing=18)
        ic = Gtk.Image.new_from_icon_name("computer", Gtk.IconSize.DIALOG)
        ic.set_pixel_size(64)
        hb_.pack_start(ic, False, False, 0)
        hv = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        hv.set_valign(Gtk.Align.CENTER)
        hn = Gtk.Label(label=os.uname().nodename, xalign=0)
        hn.get_style_context().add_class("hero-name")
        hv.pack_start(hn, False, False, 0)
        hv.pack_start(ui._lbl(_model(), "muted"), False, False, 0)
        self.ov["hero"] = ui._lbl("", "muted")
        hv.pack_start(self.ov["hero"], False, False, 0)
        hb_.pack_start(hv, True, True, 0)
        hero.add(hb_)
        p.add(hero)

        tiles = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, homogeneous=True,
                            min_children_per_line=2, max_children_per_line=6,
                            column_spacing=12, row_spacing=12)
        self.ov_tiles = {}
        for key, title, icon in TILES:
            b = Gtk.Button()
            b.get_style_context().add_class("tile")
            bx = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            # значок в цветном скруглённом квадрате, как в Windows 11 / Android
            im = Gtk.Image.new_from_icon_name(icon, Gtk.IconSize.LARGE_TOOLBAR)
            im.set_pixel_size(20)
            badge = Gtk.Box()
            badge.set_halign(Gtk.Align.START)
            for c in ("tile-ic", "tile-ic-" + key):
                badge.get_style_context().add_class(c)
            badge.pack_start(im, True, True, 0)
            bx.pack_start(badge, False, False, 2)
            bx.pack_start(ui._lbl(title, "tile-title"), False, False, 0)
            st = ui._lbl("", "muted")
            st.set_xalign(0)
            st.set_ellipsize(3)
            bx.pack_start(st, False, False, 0)
            b.add(bx)
            b.connect("clicked", lambda _b, k=key: self.open_page(k))
            tiles.add(b)
            self.ov_tiles[key] = st
        p.add(tiles)

        grid = Gtk.Grid(column_spacing=12, row_spacing=12)
        grid.set_column_homogeneous(True)

        def big_card(title, key, sub_key, icon):
            c = ui.Card(title, icon=icon)
            v = Gtk.Label(label="—", xalign=0)
            v.get_style_context().add_class("dash-big")
            c.add(v)
            s = Gtk.Label(label="", xalign=0)
            s.get_style_context().add_class("muted")
            s.set_line_wrap(True)
            s.set_max_width_chars(30)
            c.add(s)
            self.ov[key] = v
            self.ov[sub_key] = s
            return c

        c1 = big_card("Процессор", "cpu", "cpu_sub", "cpu")
        c2 = big_card("Память", "ram", "ram_sub", "media-flash")
        c3 = big_card("Температура", "temp", "temp_sub", "sensors-temperature-symbolic")
        c4 = big_card("Свободно на диске", "disk", "disk_sub", "drive-harddisk")
        c5 = big_card("Сеть", "net", "net_sub", "network-transmit-receive")
        c6 = big_card("Время работы", "up", "up_sub", "preferences-system-time")

        grid.attach(c1, 0, 0, 1, 1)
        grid.attach(c2, 1, 0, 1, 1)
        grid.attach(c3, 2, 0, 1, 1)
        p.add(grid)


        def tick():
            if not self.ov.get("cpu"):
                return True
            busy, total = C.cpu_times()
            pb, pt = getattr(self, "_pc", (busy, total))
            pct = 100.0 * (busy - pb) / (total - pt) if total != pt else 0
            self._pc = (busy, total)
            self.ov["cpu"].set_text("%.0f %%" % pct)
            self.ov["cpu_sub"].set_text("%d ядра · %d МГц · LA %s" % (
                os.cpu_count() or 0, C.cpu_cur_mhz(), " ".join(C.loadavg()[:2])))
            tot, used, avail = C.ram()
            self.ov["ram"].set_text("%d МБ" % used)
            self.ov["ram_sub"].set_text("из %d МБ занято · свободно %d МБ" % (tot, avail))
            tt = C.temps()
            if tt:
                self.ov["temp"].set_text("%.0f °C" % max(v for _, v in tt))
                self.ov["temp_sub"].set_text(" · ".join("%s %.0f°" % (n, v) for n, v in tt))
            else:
                self.ov["temp"].set_text("нет датчика")
            ds = [d for d in C.disks() if d["mount"] == "/"]
            if ds:
                d = ds[0]
                self.ov["disk"].set_text(C.human_bytes(d["free"]))
                self.ov["disk_sub"].set_text("из %s · занято %d %%" % (C.human_bytes(d["total"]), d["pct"]))
            rx, tx = C.net_bytes()
            prx, ptx = getattr(self, "_pn", (rx, tx))
            self._pn = (rx, tx)
            kb = max(0.0, ((rx - prx) + (tx - ptx)) / 1024.0)
            info = C.net_info()
            self.ov["net"].set_text("%.0f КБ/с" % kb)
            self.ov["net_sub"].set_text("%s · %s" % (info["dev"], info["ip"]))
            self.ov["up"].set_text(C.uptime())
            self.ov["up_sub"].set_text("%d процессов" % self._proc_count())
            self.ov["hero"].set_text("IP %s · работает %s" % (info["ip"], C.uptime()))
            self._tile_status(info)
            return True

        GLib.timeout_add(2000, self._visible_only(tick))
        return p

    def _tile_status(self, info):
        
        T = self.ov_tiles
        link = C.out(["/usr/sbin/iw", "dev", info["dev"], "link"]) if info["dev"].startswith("wl") else ""
        ssid = next((l.split(":", 1)[1].strip() for l in link.splitlines() if l.strip().startswith("SSID:")), "")
        wired = info["dev"].startswith(("eth", "en"))
        T["network"].set_text(ssid or (("кабель · " if wired else "") + info["ip"] if info["ip"] != "—" else "нет сети"))
        bt = [r for r in glob.glob("/sys/class/rfkill/rfkill*")
              if C.read(r + "/type") == "bluetooth" and C.read(r + "/soft") == "0" and C.read(r + "/hard") == "0"]
        T["bluetooth"].set_text("включён" if bt and os.path.exists("/sys/class/bluetooth/hci0") else "выключен")
        disp = Gdk.Display.get_default()
        mon = disp.get_primary_monitor() or (disp.get_monitor(0) if disp and disp.get_n_monitors() else None) if disp else None
        if mon is not None:
            geo = mon.get_geometry()
            T["display"].set_text("%d × %d" % (geo.width, geo.height))
        else:
            scr = self.get_screen()
            T["display"].set_text("%d × %d" % (scr.get_width(), scr.get_height()))
        th = C.read(os.path.expanduser("~/.config/rsaarm/theme")).strip()
        T["appearance"].set_text("тёмная тема" if th == "dark" else "светлая тема")
        v = str(self._upgradable())
        T["updates"].set_text("проверка…" if not v.isdigit() else "всё обновлено" if v == "0" else "доступно: " + v)
        T["ai"].set_text("включён" if self._svc_ai() else "выключен")

    def _svc_ai(self):
        return subprocess.run(["systemctl", "is-active", "-q", "agent-slot@0"]).returncode == 0

    def _proc_count(self):
        return len([d for d in os.listdir("/proc") if d.isdigit()])

    def _failed_count(self):
        return len([l for l in C.out(["systemctl", "--failed", "--no-legend", "--no-pager"]).splitlines() if l])

    def _running_count(self):
        return len([l for l in C.out(["systemctl", "list-units", "--type=service", "--state=running",
                                     "--no-legend", "--no-pager"]).splitlines() if l])

    def _svc(self, key):
        
        cur = time.time()
        st = getattr(self, "_svc_cache", None)
        if st and cur - st["t"] < 30:
            return str(st[key])
        if not getattr(self, "_svc_busy", False):
            self._svc_busy = True

            def _bg():
                d = {"t": time.time(), "failed": self._failed_count(),
                     "running": self._running_count()}
                self._svc_cache = d
                self._svc_busy = False

            threading.Thread(target=_bg, daemon=True).start()
        return "…"

    def _upgradable(self):
        
        if getattr(self, "_upd_val", None) is not None:
            return self._upd_val
        if not getattr(self, "_upd_busy", False):
            self._upd_busy = True

            def _bg():
                o = C.out("apt list --upgradable 2>/dev/null | grep -c upgradable",
                          timeout=25)
                self._upd_val = (o or "0").strip() or "0"
                self._upd_busy = False
                row = getattr(self, "_upd_row", None)
                if row is not None:
                    GLib.idle_add(lambda: (row.refresh(), False)[1])

            threading.Thread(target=_bg, daemon=True).start()
        return "проверяем…"

    def page_system(self):
        p = ui.Page("Система", "Информация об устройстве и его имени в сети")
        c = p.card("Устройство", icon="computer")
        c.add(ui.info_row("Модель", "Tanix TX3 · Amlogic S905X3"))
        c.add(ui.info_row("Процессор", lambda: "4 × Cortex-A55 до 2100 МГц"))
        c.add(ui.info_row("Оперативная память", lambda: "%d МБ" % C.ram()[0]))
        c.add(ui.info_row("Ядро", lambda: C.read("/proc/sys/kernel/osrelease")))
        c.add(ui.info_row("Система", C.os_pretty))
        c.add(ui.info_row("Работает", C.uptime))

        c = p.card("Имя устройства", icon="network-server")
        c.add(ui.row("Имя в сети (hostname)", ui.button(
            "Изменить", self.change_hostname, "btn", "document-edit"),
            sub="По этому имени мини-ПК виден в локальной сети: %s" % C.out(["hostname"])))
        c.add(ui.row("Часовой пояс", ui.button("Изменить", self.change_timezone, "ghost"),
                     sub="Сейчас: %s" % (C.read("/etc/timezone") or
                                         C.out(["timedatectl", "show", "-p", "Timezone", "--value"]))))

        def _boot_summary():
            raw = C.out("systemd-analyze", timeout=6)
            mk = re.search(r"([0-9.]+)s\s*\(kernel\)", raw)
            mu = re.search(r"([0-9.]+)s\s*\(userspace\)", raw)
            if mk and mu:
                return "Ядро: %s с · Службы: %s с" % (mk.group(1), mu.group(1))
            return raw.replace("\n", " ") or "—"

        c = p.card("Загрузка системы", icon="preferences-system-time")
        c.add(ui.info_row("Последняя загрузка", _boot_summary))
        c.add(ui.info_row("Самая долгая служба", lambda: (C.out("systemd-analyze blame | head -1", timeout=8) or "—")))
        c.add(ui.row("", ui.button("Подробный отчёт загрузки", self.boot_report, "ghost"),
                     sub="Откроет список служб и время их запуска"))
        return p

    def change_hostname(self):
        new = ui.ask_text(self, "Имя устройства", "Новое имя (латиницей, без пробелов):",
                          default=C.out(["hostname"]))
        if not new:
            return
        code, o = C.sudo(["hostnamectl", "set-hostname", new.strip()])
        if code == 0:
            C.notify("Система", "Имя изменено на %s" % new.strip())
        else:
            ui.dialog(self, "Не получилось", o, ok="Закрыть")

    def change_timezone(self):
        zones = C.out("timedatectl list-timezones | grep -E '^(Europe|Asia)/' | head -400", timeout=15).splitlines()
        idx = ui.ask_choice(self, "Часовой пояс", "Выберите город:", zones)
        if idx is None:
            return
        C.sudo(["timedatectl", "set-timezone", zones[idx]])
        C.notify("Система", "Часовой пояс: %s" % zones[idx])

    def boot_report(self):
        txt = C.out("systemd-analyze blame | head -25", timeout=25)
        d = Gtk.MessageDialog(transient_for=self, modal=True, message_type=Gtk.MessageType.INFO,
                              buttons=Gtk.ButtonsType.CLOSE)
        d.set_markup("<b>Время запуска служб</b>")
        d.format_secondary_text(txt or "нет данных")
        d.run()
        d.destroy()

    def xrandr_outputs(self):
        text = C.out(["xrandr", "--query"])
        res = []
        cur = None
        for line in text.splitlines():
            m = re.match(r"^(\S+) connected(?: primary)?(?:\s+(\d+)x(\d+)\+(\d+)\+(\d+))?", line)
            if m:
                cur = {"name": m.group(1),
                       "mode": "%sx%s" % (m.group(2), m.group(3)) if m.group(2) else "—",
                       "modes": []}
                res.append(cur)
                continue
            m2 = re.match(r"^\s+(\d+)x(\d+)i?\s+", line)
            if m2 and cur is not None:
                cur["modes"].append("%sx%s" % (m2.group(1), m2.group(2)))
        return res

    def page_display(self):
        p = ui.Page("Экран", "Разрешение и параметры вывода изображения")
        outs = self.xrandr_outputs()
        for o in outs:
            c = p.card("Вывод: %s" % o["name"], icon="video-display")
            c.add(ui.info_row("Текущее разрешение", o["mode"]))
            modes = o["modes"] or [o["mode"]]
            idx = modes.index(o["mode"]) if o["mode"] in modes else 0
            c.add(ui.row("Разрешение", ui.combo(modes, idx, lambda i, t: self.set_mode(o["name"], t))))
        c_fit = p.card("Калибровка границ и смещения ТВ", icon="video-display")
        c_fit.add(ui.row(
            "Рамки не совпадают или картинка съехала вбок?",
            ui.button("Подгонка границ экрана…", lambda: _spawn(["/usr/local/bin/armbian-screen-fit"]), "btn", "zoom-fit-best"),
            sub="Включает 4 зелёные контрольные линии по краям, автоадаптацию VESA/HD и ручную регулировку сдвига и полей"
        ))
        c = p.card("Подсказка", icon="dialog-information")
        c.add(ui.row("", Gtk.Label(label="Телевизор лучше всего показывает 1360×768 или 1920×1080.\n"
                                          "После смены разрешения экран может мигнуть — это нормально.",
                                   xalign=0)))
        self.disp_info = ui.info_row("Плотность пикселей", lambda: C.out(
            ["xdpyinfo"], timeout=6).split("resolution:")[1].split("x")[0].strip() + " dpi"
            if "resolution:" in C.out(["xdpyinfo"], timeout=6) else "—")
        c = p.card("Монитор", icon="preferences-desktop-display")
        c.add(self.disp_info)
        return p

    def set_mode(self, name, mode):
        code, o = C.run(["xrandr", "--output", name, "--mode", mode], timeout=15)
        if code != 0:
            ui.dialog(self, "Не удалось сменить разрешение", o, ok="Закрыть")
            return False
        A.add_custom("Разрешение экрана", "xrandr --output %s --mode %s" % (name, mode),
                     "Автоматически сохранённое разрешение")
        C.notify("Экран", "%s → %s (сохранено в автозагрузку)" % (name, mode))
        return True

    def hdmi_volumes(self):
        
        items = []
        o = C.out(["amixer", "-c", "0", "controls"], timeout=8)
        for line in o.splitlines():
            if "Volume" not in line or "numid=" not in line:
                continue
            numid = line.split("numid=")[1].split(",")[0]
            if "name='" in line:
                name = line.split("name='")[1].rstrip("'")
            else:
                continue
            info = C.sudo(["amixer", "-c", "0", "cget", "numid=" + numid], timeout=8)[1]
            if "min=0,max=255" not in info:
                continue
            cur = 0
            if ": values=" in info:
                try:
                    cur = int(info.split(": values=")[1].split(",")[0])
                except Exception:
                    cur = 0
            items.append({"numid": numid, "name": name, "value": cur})
        return items

    def pulse_volume(self):
        o = C.out(["pactl", "get-sink-volume", "@DEFAULT_SINK@"], timeout=5)
        m = re.search(r"(\d+)\s*%", o)
        return int(m.group(1)) if m else 100

    def pulse_muted(self):
        o = C.out(["pactl", "get-sink-mute", "@DEFAULT_SINK@"], timeout=5)
        return "yes" in o.lower() or "да" in o.lower()

    def pulse_sinks(self):
        res = []
        default_sink = C.out(["pactl", "get-default-sink"], timeout=5).strip()
        o = C.out(["pactl", "list", "short", "sinks"], timeout=5)
        for line in o.splitlines():
            parts = line.split("\t")
            if len(parts) >= 2:
                name = parts[1].strip()
                if "bluez" in name:
                    title = "Bluetooth-устройство (%s)" % name.split(".")[-1]
                elif "hdmi" in name.lower() or "platform-sound" in name:
                    title = "Телевизор / монитор HDMI (TX3)"
                elif "usb" in name.lower():
                    title = "USB-аудиоустройство (%s)" % name
                else:
                    title = name
                res.append((name, title, name == default_sink))
        return res

    def page_sound(self):
        p = ui.Page("Звук", "Управление громкостью системы, выходом HDMI / Bluetooth и проверкой звука")
        c = p.card("Выход звука", icon="audio-card")
        c.add(ui.info_row("Звуковая карта", lambda: C.out(
            "aplay -l | grep -m1 '^card' | sed 's/device.*//'") or "—"))
        c.add(ui.info_row("Звуковой сервер", lambda: (
            "PipeWire активен (%s)" % (C.out(["pactl", "get-default-sink"], timeout=4).strip() or "готов")
            if C.run(["pactl", "info"], timeout=4)[0] == 0 else "ALSA напрямую")))
        c.add(ui.info_row("Bluetooth-аудио (A2DP)", lambda: (
            "готово (PipeWire + WirePlumber)"
            if C.out(["systemctl", "--user", "is-active", "wireplumber"]) == "active"
            else ("готово (bluealsa)" if C.out(["systemctl", "is-active", "bluealsa"]) == "active" else "выключено"))))
        c.add(ui.info_row("AirPlay / DLNA / Navidrome", lambda: (
            "%s · порты 8200 / 4533" % (
                "AirPlay включён" if C.out(["systemctl", "is-active", "shairport-sync"]) == "active" else "AirPlay выкл."))))

        cur_vol = self.pulse_volume()
        c_sys = p.card("Громкость системы (браузер, видео, музыка, Bluetooth)", icon="audio-volume-high")
        vol_lab = Gtk.Label(label="%d %%" % cur_vol)
        vol_lab.get_style_context().add_class("value")
        c_sys.add(ui.row("Общая громкость", vol_lab))

        def on_sys_vol(val):
            iv = int(val)
            C.run(["pactl", "set-sink-mute", "@DEFAULT_SINK@", "0"], timeout=4)
            C.run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", "%d%%" % iv], timeout=4)
            vol_lab.set_text("%d %%" % iv)

        c_sys.add(ui.slider(0, 150, 5, min(150, max(0, cur_vol)), on_sys_vol))
        c_sys.add(ui.row("Звук выключен (Mute)", ui.switch(
            self.pulse_muted(),
            lambda muted: C.run(["pactl", "set-sink-mute", "@DEFAULT_SINK@", "1" if muted else "0"], timeout=4))))

        sinks = self.pulse_sinks()
        if sinks:
            for s_name, s_title, is_def in sinks:
                mark = "активен" if is_def else "переключить"
                c_sys.add(ui.row(
                    s_title,
                    ui.button(mark, lambda _=None, sn=s_name, st=s_title: self.select_pulse_sink(sn, st),
                              "btn" if not is_def else "ghost", "audio-speakers")))

        c_sys.add(ui.row("Расширенный микшер приложений",
                         ui.button("Открыть микшер громкости", self.open_pavucontrol, "btn", "multimedia-volume-control"),
                         sub="Позволяет менять громкость отдельных вкладок браузера и выбирать колонки/наушники"))

        vols = self.hdmi_volumes()
        if vols:
            c = p.card("Аппаратное усиление HDMI", "регуляторы звуковой карты Amlogic; держите на 100 %")
            for v in vols:
                pct = int(round(v["value"] / 255.0 * 100))
                lab = Gtk.Label(label="%d %%" % pct)
                lab.get_style_context().add_class("value")
                c.add(ui.row(v["name"], lab))

                def on_vol(val, v=v, lab=lab):
                    C.sudo(["amixer", "-c", "0", "cset", "numid=" + v["numid"], "%d%%" % int(val)])
                    lab.set_text("%d %%" % int(val))

                c.add(ui.slider(0, 100, 5, pct, on_vol))
            c.add(ui.row("Выставить максимум", ui.button(
                "Все каналы на 100 %", self.sound_max, "btn", "audio-volume-high")))

        c = p.card("Проверка", icon="media-playback-start")
        c.add(ui.row("Проиграть проверочный стереосигнал",
                     ui.button("Проверить звук", self.test_sound, "btn", "audio-volume-high"),
                     sub="Прозвучит чистый двухтональный сигнал (левый и правый канал) через активный выход"))
        return p

    def select_pulse_sink(self, sink_name, title):
        C.run(["pactl", "set-default-sink", sink_name], timeout=5)
        for line in C.out(["pactl", "list", "short", "sink-inputs"], timeout=4).splitlines():
            parts = line.split("\t")
            if parts and parts[0].isdigit():
                C.run(["pactl", "move-sink-input", parts[0], sink_name], timeout=4)
        C.notify("Звук", "Активный выход: %s" % title)
        self.show_page("sound")

    def open_pavucontrol(self):
        _spawn(["pavucontrol"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def test_sound(self):
        C.notify("Проверка звука", "Воспроизвожу проверочный стереосигнал…")

        def _play():
            wav_path = None
            try:
                rate = 48000
                fd, wav_path = tempfile.mkstemp(prefix="armbian_test_", suffix=".wav")
                os.close(fd)
                with wave.open(wav_path, "wb") as wf:
                    wf.setnchannels(2)
                    wf.setsampwidth(2)
                    wf.setframerate(rate)
                    frames = bytearray()
                    segments = [(0.42, 440.0, 1.0, 0.15), (0.42, 554.37, 0.15, 1.0), (0.36, 659.25, 0.9, 0.9)]
                    for dur, freq, l_gain, r_gain in segments:
                        n = int(rate * dur)
                        for i in range(n):
                            env = min(1.0, i / 600.0, (n - i) / 800.0)
                            s = math.sin(2.0 * math.pi * freq * i / rate) * 18000.0 * env
                            frames += struct.pack("<hh", int(s * l_gain), int(s * r_gain))
                    wf.writeframes(bytes(frames))
                C.run(["pactl", "set-sink-mute", "@DEFAULT_SINK@", "0"], timeout=3)
                rc, _ = C.run(["paplay", wav_path], timeout=8)
                if rc != 0:
                    C.run(["aplay", "-q", "-D", "plughw:0,0", wav_path], timeout=8)
            finally:
                if wav_path and os.path.exists(wav_path):
                    try:
                        os.unlink(wav_path)
                    except OSError:
                        pass

        threading.Thread(target=_play, daemon=True).start()
        return True

    def sound_max(self):
        for v in self.hdmi_volumes():
            C.sudo(["amixer", "-c", "0", "cset", "numid=" + v["numid"], "100%"])
        C.run(["pactl", "set-sink-mute", "@DEFAULT_SINK@", "0"], timeout=4)
        C.run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", "100%"], timeout=4)
        C.notify("Звук", "Все каналы HDMI и громкость выставлены на 100 %")
        return True

    def page_network(self):
        p = ui.Page("Wi-Fi и сеть", "Подключение к интернету и локальной сети")

        c = p.card("Состояние", icon="network-workgroup")
        c.add(ui.info_row("Интерфейс", lambda: C.net_info()["dev"]))
        c.add(ui.info_row("IP-адрес", lambda: C.net_info()["ip"]))
        c.add(ui.info_row("Шлюз", lambda: C.net_info()["gw"]))
        c.add(ui.info_row("Сеть Wi-Fi", lambda: C.net_info()["link"] or "—"))
        c.add(ui.info_row("Сигнал", lambda: C.net_info()["signal"] or "—"))

        wifi_on = "enabled" in C.out(["nmcli", "radio", "wifi"])
        c.add(ui.row("Wi-Fi включён", ui.switch(wifi_on, self.toggle_wifi),
                     sub="Выключать Wi-Fi стоит только если мини-ПК подключён кабелем"))

        c = p.card("Доступные сети", icon="network-wireless")
        self.wifi_store = Gtk.ListStore(str, str, str, str)
        tv = Gtk.TreeView(model=self.wifi_store)
        for i, (t, w) in enumerate([("Сеть", 300), ("Сигнал", 120), ("Защита", 150), ("Статус", 120)]):
            r = Gtk.CellRendererText(xalign=0)
            col = Gtk.TreeViewColumn(t, r, text=i)
            col.set_fixed_width(w)
            col.set_expand(i == 0)
            tv.append_column(col)
        tv.set_size_request(-1, 200)
        c.add(tv)
        rowb = Gtk.Box(spacing=8)
        rowb.pack_start(ui.button("Обновить список", self.scan_wifi, "btn", "view-refresh"), False, False, 0)
        rowb.pack_start(ui.button("Подключиться", lambda: self.connect_wifi(tv), "btn", "network-wireless"), False, False, 0)
        rowb.pack_end(ui.button("Отключиться", self.disconnect_wifi, "ghost"), False, False, 0)
        c.add(rowb)
        GLib.idle_add(lambda: (self.scan_wifi(rescan=False), False)[1])

        c = p.card("Сохранённые подключения", icon="document-save")
        self.con_store = Gtk.ListStore(str, str, str)
        tv2 = Gtk.TreeView(model=self.con_store)
        for i, (t, w) in enumerate([("Имя", 320), ("Тип", 180), ("Устройство", 160)]):
            r = Gtk.CellRendererText()
            col = Gtk.TreeViewColumn(t, r, text=i)
            col.set_fixed_width(w)
            tv2.append_column(col)
        c.add(tv2)
        self.fill_connections()
        return p

    def fill_connections(self):
        rows = []
        text = C.out(["nmcli", "-t", "-f", "NAME,TYPE,DEVICE", "connection", "show"])
        for line in text.splitlines():
            f = line.split(":")
            if len(f) >= 2:
                rows.append([f[0], f[1], f[2] if len(f) > 2 else ""])
        self.con_store.clear()
        for r in rows:
            self.con_store.append(r)

    def toggle_wifi(self, on):
        C.run(["nmcli", "radio", "wifi", "on" if on else "off"], timeout=15)
        C.notify("Сеть", "Wi-Fi %s" % ("включён" if on else "выключен"))
        return True

    def scan_wifi(self, *a, rescan=True):
        
        def work():
            text = C.out(["nmcli", "-t", "-f", "SSID,SIGNAL,SECURITY,ACTIVE", "device", "wifi", "list",
                          "--rescan", "yes" if rescan else "no"], timeout=25)
            GLib.idle_add(self._fill_wifi, text)
        threading.Thread(target=work, daemon=True).start()

    def _fill_wifi(self, text):
        rows = []
        for line in text.splitlines():
            f = line.split(":")
            if len(f) >= 3 and f[0]:
                rows.append([f[0], f[1] + " %", f[2] or "открытая",
                             "подключено" if (len(f) > 3 and f[3] == "yes") else ""])
        rows.sort(key=lambda r: -int(r[1].split()[0] or 0))
        self.wifi_store.clear()
        for r in rows:
            self.wifi_store.append(r)
        return False

    def connect_wifi(self, tv):
        model, it = tv.get_selection().get_selected()
        if it is None:
            ui.dialog(self, "Выберите сеть", "Сначала нажмите на сеть в списке.", ok="Закрыть")
            return
        ssid = model[it][0]
        pwd = ui.ask_text(self, "Подключение к Wi-Fi", "Пароль для сети «%s»:" % ssid, password=True)
        if pwd is None:
            return
        code, o = C.run(["nmcli", "device", "wifi", "connect", ssid, "password", pwd], timeout=45)
        if code == 0:
            C.notify("Сеть", "Подключено к %s" % ssid)
        else:
            ui.dialog(self, "Не удалось подключиться", o, ok="Закрыть")
        self.scan_wifi()
        self.fill_connections()

    def disconnect_wifi(self):
        dev = C.net_info()["dev"]
        C.run(["nmcli", "device", "disconnect", dev], timeout=20)
        C.notify("Сеть", "Отключено: %s" % dev)

    def bt_power(self):
        o = C.out(["bluetoothctl", "show"], timeout=10)
        return "Powered: yes" in o

    def bt_devices(self):
        res = []
        o = C.out(["bluetoothctl", "devices"], timeout=10)
        for line in o.splitlines():
            m = re.match(r"Device (\S+) (.+)", line)
            if m:
                res.append((m.group(1), m.group(2)))
        return res

    def page_bluetooth(self):
        p = ui.Page("Bluetooth", "Наушники, колонки, мыши, пульты и другие устройства рядом")
        c = p.card("Адаптер", icon="bluetooth")
        c.add(ui.row("Bluetooth включён", ui.switch(self.bt_power(), self.set_bt_power)))
        c.add(ui.info_row("Контроллер", lambda: (C.out(["bluetoothctl", "show"], timeout=5)
                                                 .split("Controller")[1].split()[0]
                                                 if "Controller" in C.out(["bluetoothctl", "show"], timeout=5)
                                                 else "—")))
        c.add(ui.info_row("Устройств в памяти", lambda: str(len(self.bt_devices()))))
        c.add(ui.row("Графический менеджер Blueman",
                     ui.button("Открыть Blueman", self.open_blueman, "btn", "bluetooth"),
                     sub="Удобное окно сопряжения наушников, колонок, геймпадов и передачи файлов"))

        c = p.card("Сопряжённые и известные устройства", icon="audio-headset")
        self.bt_store = Gtk.ListStore(str, str, str)
        tv = Gtk.TreeView(model=self.bt_store)
        for i, (t, w) in enumerate([("Устройство", 340), ("MAC", 200), ("Состояние", 160)]):
            r = Gtk.CellRendererText()
            col = Gtk.TreeViewColumn(t, r, text=i)
            col.set_fixed_width(w)
            col.set_expand(i == 0)
            tv.append_column(col)
        tv.set_size_request(-1, 180)
        c.add(tv)
        b = Gtk.Box(spacing=8)
        b.pack_start(ui.button("Подключить", lambda: self.bt_action(tv, "connect"), "btn"), False, False, 0)
        b.pack_start(ui.button("Отключить", lambda: self.bt_action(tv, "disconnect"), "ghost"), False, False, 0)
        b.pack_start(ui.button("Забыть", lambda: self.bt_action(tv, "remove"), "danger"), False, False, 0)
        b.pack_start(ui.button("Обновить", self.fill_bt, "ghost", "view-refresh"), False, False, 0)
        c.add(b)

        c = p.card("Поиск новых устройств", icon="system-search")
        self.bt_scan_status = Gtk.Label(label="Переведите наушники или колонку в режим сопряжения и нажмите «Начать поиск».",
                                        xalign=0)
        c.add(ui.row("Сканировать эфир (12 секунд, без зависания окна)",
                     ui.button("Начать поиск", self.bt_scan, "btn", "view-refresh")))
        c.add(self.bt_scan_status)
        self.bt_found = Gtk.ListStore(str, str, str)
        tvf = Gtk.TreeView(model=self.bt_found)
        for i, (t, w) in enumerate([("Устройство", 340), ("MAC", 200), ("Действие", 160)]):
            r = Gtk.CellRendererText()
            col = Gtk.TreeViewColumn(t, r, text=i)
            col.set_fixed_width(w)
            tvf.append_column(col)
        tvf.set_size_request(-1, 150)
        c.add(tvf)
        c.add(ui.button("Сопрячь и подключить выбранное", lambda: self.bt_action(tvf, "pair"), "btn"))
        self.fill_bt()
        return p

    def open_blueman(self):
        _spawn(["blueman-manager"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def set_bt_power(self, on):
        if on:
            C.sudo(["rfkill", "unblock", "bluetooth"], timeout=5)
        C.run(["bluetoothctl", "power", "on" if on else "off"], timeout=8)
        if on:
            C.run(["bluetoothctl", "pairable", "on"], timeout=5)
            C.run(["bluetoothctl", "discoverable", "on"], timeout=5)
        C.notify("Bluetooth", "Включён" if on else "Выключен")
        return True

    def fill_bt(self):
        if not hasattr(self, "bt_store"):
            return
        self.bt_store.clear()
        for mac, name in self.bt_devices():
            info = C.out(["bluetoothctl", "info", mac], timeout=5)
            st = "подключено" if "Connected: yes" in info else (
                "сопряжено" if "Paired: yes" in info else "найдено")
            self.bt_store.append([name, mac, st])

    def bt_action(self, tv, action):
        model, it = tv.get_selection().get_selected()
        if it is None:
            C.notify("Bluetooth", "Сначала выберите устройство в списке")
            return
        mac = model[it][1]
        name = model[it][0]
        if action == "remove" and not ui.dialog(self, "Забыть устройство?",
                                                "«%s» будет удалено из сопряжённых." % name,
                                                ok="Забыть", cancel=True):
            return

        if hasattr(self, "bt_scan_status"):
            self.bt_scan_status.set_text("Выполняю «%s» для %s (%s)…" % (action, name, mac))

        def _worker():
            if action == "pair":
                script = (
                    "power on\n"
                    "agent NoInputNoOutput\n"
                    "default-agent\n"
                    "pair %s\n"
                    "trust %s\n"
                    "connect %s\n"
                    "quit\n"
                ) % (mac, mac, mac)
                try:
                    subprocess.run(
                        ["bluetoothctl"],
                        input=script,
                        text=True,
                        capture_output=True,
                        timeout=30,
                    )
                except Exception:
                    pass
                time.sleep(1.0)
                C.run(["bluetoothctl", "trust", mac], timeout=8)
                C.run(["bluetoothctl", "connect", mac], timeout=15)
            elif action == "connect":
                C.run(["bluetoothctl", "trust", mac], timeout=8)
                C.run(["bluetoothctl", "connect", mac], timeout=18)
            else:
                C.run(["bluetoothctl", action, mac], timeout=15)

            info = C.out(["bluetoothctl", "info", mac], timeout=5)
            ok_msg = "подключено" if "Connected: yes" in info else (
                "сопряжено" if "Paired: yes" in info else action)

            def _done():
                C.notify("Bluetooth", "%s — %s" % (name, ok_msg))
                if hasattr(self, "bt_scan_status"):
                    self.bt_scan_status.set_text("Готово: %s (%s) — %s." % (name, mac, ok_msg))
                self.fill_bt()
                return False

            GLib.idle_add(_done)

        threading.Thread(target=_worker, daemon=True).start()

    def bt_scan(self):
        if getattr(self, "_bt_scanning", False):
            return
        self._bt_scanning = True
        C.notify("Bluetooth", "Идёт поиск устройств рядом (12 секунд)…")
        if hasattr(self, "bt_scan_status"):
            self.bt_scan_status.set_text("Идёт поиск устройств рядом (12 секунд)…")

        def _scan_worker():
            try:
                C.sudo(["rfkill", "unblock", "bluetooth"], timeout=4)
                C.run(["bluetoothctl", "power", "on"], timeout=5)
                C.run(["bluetoothctl", "--timeout", "12", "scan", "on"], timeout=18)
                devs = self.bt_devices()
            finally:
                self._bt_scanning = False

            def _finish():
                if hasattr(self, "bt_found"):
                    self.bt_found.clear()
                    for mac, name in devs:
                        info = C.out(["bluetoothctl", "info", mac], timeout=4)
                        act = "подключено" if "Connected: yes" in info else "сопрячь и подключить"
                        self.bt_found.append([name, mac, act])
                if hasattr(self, "bt_scan_status"):
                    self.bt_scan_status.set_text("Поиск завершён: найдено устройств — %d." % len(devs))
                self.fill_bt()
                return False

            GLib.idle_add(_finish)

        threading.Thread(target=_scan_worker, daemon=True).start()

    def page_disks(self):
        p = ui.Page("Хранилище", "Встроенная память мини-ПК, подключённые накопители и свободное место")
        mount_names = {
            "/": "Основная память системы",
            "/boot": "Загрузочный раздел",
        }
        for d in C.disks():
            mnt = d["mount"]
            if mnt.startswith("/var/log") or mnt.startswith("/snap"):
                continue
            title = mount_names.get(mnt, "Накопитель (%s)" % os.path.basename(mnt.rstrip("/")) if mnt != "/" else mnt)
            dev_desc = ("Встроенная память eMMC (%s)" % d["dev"] if "mmcblk" in d["dev"]
                        else "Внешний накопитель USB (%s)" % d["dev"] if "/sd" in d["dev"] else d["dev"])
            c = p.card(title, icon="drive-harddisk")
            c.add(ui.info_row("Носитель", dev_desc))
            c.add(ui.info_row("Объём", "%s (занято %d %%)" % (C.human_bytes(d["total"]), d["pct"])))
            c.add(ui.info_row("Свободно", C.human_bytes(d["free"])))
            c.add(ui.progress(d["pct"] / 100.0))
            c.add(ui.row("Открыть в Проводнике",
                         ui.button("Открыть", lambda m=mnt: C.run(["setsid", "thunar", m], timeout=3),
                                   "ghost", "folder-open")))

        c = p.card("Подключённые накопители и разделы", icon="drive-removable-media")
        self.blk_store = Gtk.ListStore(str, str, str, str, str)
        tv = Gtk.TreeView(model=self.blk_store)
        for i, (t, w) in enumerate([("Устройство", 150), ("Размер", 100), ("Файловая система", 170),
                                    ("Точка монтирования", 220), ("Тип", 120)]):
            r = Gtk.CellRendererText()
            col = Gtk.TreeViewColumn(t, r, text=i)
            col.set_fixed_width(w)
            col.set_expand(i == 3)
            tv.append_column(col)
        tv.set_size_request(-1, 200)
        c.add(tv)
        b = Gtk.Box(spacing=8)
        b.pack_start(ui.button("Смонтировать", lambda: self.mount_sel(tv, True), "btn"), False, False, 0)
        b.pack_start(ui.button("Отмонтировать", lambda: self.mount_sel(tv, False), "ghost"), False, False, 0)
        b.pack_end(ui.button("Обновить", self.fill_blk, "ghost", "view-refresh"), False, False, 0)
        c.add(b)
        self.fill_blk()
        return p

    def fill_blk(self):
        self.blk_store.clear()
        o = C.out(["lsblk", "-o", "NAME,SIZE,FSTYPE,MOUNTPOINT,TYPE", "-e", "7", "--noheadings"], timeout=10)
        for line in o.splitlines():
            f = line.split(None, 4)
            if len(f) < 4:
                continue
            self.blk_store.append([f[0], f[1], f[2] or "—", f[3] if len(f) > 3 else "", f[4] if len(f) > 4 else ""])

    def mount_sel(self, tv, on):
        model, it = tv.get_selection().get_selected()
        if it is None:
            return
        dev = "/dev/" + model[it][0].strip()
        if on:
            code, o = C.run(["udisksctl", "mount", "-b", dev], timeout=30)
            if code != 0:
                code, o = C.sudo(["mount", dev, "/mnt"])
        else:
            code, o = C.run(["udisksctl", "unmount", "-b", dev], timeout=30)
        C.notify("Диски", o.strip()[:120] or "готово")
        self.fill_blk()

    def page_packages(self):
        p = ui.Page("Приложения", "Магазин программ — установка в один клик, без терминала")
        self.pkgs = C.packages_installed()

        cs = p.card("Магазин", icon="system-software-install",
                    subtitle="Программы из официальных репозиториев Debian, проверенные для ARM")
        flow = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, homogeneous=True,
                           min_children_per_line=1, max_children_per_line=4,
                           column_spacing=12, row_spacing=12)
        self.store_btns = {}
        for pkg, name, desc, icon, cmd in STORE:
            box = Gtk.Box(spacing=12)
            box.get_style_context().add_class("tile")
            im = Gtk.Image.new_from_icon_name(icon, Gtk.IconSize.DIALOG)
            im.set_pixel_size(48)
            box.pack_start(im, False, False, 0)
            v = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            v.pack_start(ui._lbl(name, "tile-title"), False, False, 0)
            d = ui._lbl(desc, "muted", wrap=True)
            d.set_max_width_chars(24)
            v.pack_start(d, False, False, 0)
            bb = Gtk.Box(spacing=6)
            b1 = Gtk.Button()
            b1.connect("clicked", lambda _b, k=pkg, c=cmd: self.store_main(k, c))
            b2 = Gtk.Button(label="Удалить")
            b2.get_style_context().add_class("ghost")
            b2.connect("clicked", lambda _b, k=pkg, n=name: self.store_remove(k, n))
            bb.pack_start(b1, False, False, 0)
            bb.pack_start(b2, False, False, 0)
            v.pack_start(bb, False, False, 4)
            box.pack_start(v, True, True, 0)
            flow.add(box)
            self.store_btns[pkg] = (b1, b2)
        cs.add(flow)
        self.store_refresh()
        GLib.timeout_add_seconds(3, lambda: self.store_refresh() if cs.get_mapped() else True)

        exp = Gtk.Expander(label="Все установленные пакеты (для опытных)")
        p.add(exp)
        adv = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        exp.add(adv)
        p = _Into(p, adv)

        c = p.card("Установленные программы", icon="system-software-install",
                   subtitle="Всего пакетов: %d · занято: %.1f ГБ" % (
                       len(self.pkgs), sum(x["kb"] for x in self.pkgs) / 1024 / 1024))
        self.pkg_store = Gtk.ListStore(str, str, str)
        self.pkg_filter = Gtk.ListStore(str, str, str)
        tv = Gtk.TreeView(model=self.pkg_filter)
        for i, (t, w) in enumerate([("Пакет", 320), ("Версия", 240), ("Размер", 110)]):
            r = Gtk.CellRendererText()
            col = Gtk.TreeViewColumn(t, r, text=i)
            col.set_fixed_width(w)
            col.set_expand(i == 0)
            tv.append_column(col)
        for x in self.pkgs:
            self.pkg_store.append([x["name"], x["ver"], C.human_kb(x["kb"])])
            self.pkg_filter.append([x["name"], x["ver"], C.human_kb(x["kb"])])
        sw = Gtk.ScrolledWindow()
        sw.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        sw.set_min_content_height(260)
        sw.add(tv)
        c.add(sw)
        e = ui.entry("", "Поиск установленного пакета…", width=320)
        e.connect("changed", lambda w: self.pkg_search(w.get_text(), self.pkg_filter))
        c.add(e)

        c = p.card("Установить программу", icon="list-add")
        self.pkg_name = ui.entry("", "например: gimp, vlc, gparted", width=300)
        c.add(ui.row("Имя пакета", ui.button("Установить", self.install_pkg, "btn", "document-save")))
        c.add(self.pkg_name)
        c.add(Gtk.Label(label="Пакет скачается из репозиториев Debian. Прогресс откроется в отдельном окне.",
                        xalign=0))
        return getattr(p, "_page", p)

    def pkg_search(self, q, model):
        model.clear()
        q = q.lower()
        n = 0
        for x in self.pkgs:
            if q in x["name"].lower():
                model.append([x["name"], x["ver"], C.human_kb(x["kb"])])
                n += 1
                if n > 400:
                    break

    def install_pkg(self):
        name = self.pkg_name.get_text().strip()
        if not re.fullmatch(r"[a-z0-9][a-z0-9.+-]*( [a-z0-9][a-z0-9.+-]*)*", name):
            ui.dialog(self, "Нет имени", "Впишите имя пакета латиницей, например vlc.", ok="Закрыть")
            return
        log = C.sudo_bg("DEBIAN_FRONTEND=noninteractive apt-get -y install %s" % name,
                        "/tmp/armbian-install.log")
        log_window(self, "Установка %s" % name, log)
        C.notify("Программы", "Установка %s началась" % name)

    def store_installed(self):
        out = C.out(["dpkg-query", "-W", "-f=${Package} ${db:Status-Status}\n"] + [s[0] for s in STORE])
        return {l.split()[0] for l in out.splitlines() if l.endswith(" installed")}

    def store_refresh(self):
        inst = self.store_installed()
        busy = getattr(self, "_store_busy", None)
        for pkg, (b1, b2) in self.store_btns.items():
            if busy == pkg:
                b1.set_label("Идёт установка…" if pkg not in inst else "Удаляется…")
                b1.set_sensitive(False)
                b2.hide()
                continue
            b1.set_sensitive(True)
            b1.set_label("Открыть" if pkg in inst else "Установить")
            b2.set_visible(pkg in inst)
        if busy and C.out(["pgrep", "-x", "apt-get"]).strip() == "":
            self._store_busy = None
            name = next((s[1] for s in STORE if s[0] == busy), busy)
            C.notify("Приложения", ("%s установлен" % name) if busy in inst else ("%s удалён" % name))
            GLib.idle_add(self.store_refresh)
        return True

    def store_main(self, pkg, cmd):
        if pkg in self.store_installed():
            _spawn(["setsid", "sh", "-c", cmd], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return
        if getattr(self, "_store_busy", None):
            ui.dialog(self, "Подождите", "Сейчас уже идёт установка другой программы.", ok="Понятно")
            return
        self._store_busy = pkg
        log = C.sudo_bg("DEBIAN_FRONTEND=noninteractive apt-get -y install %s" % pkg, "/tmp/armbian-install.log")
        self.store_refresh()

    def store_remove(self, pkg, name):
        if not ui.dialog(self, "Удалить %s?" % name, "Программа будет удалена, ваши файлы останутся.",
                         ok="Удалить", cancel="Отмена"):
            return
        self._store_busy = pkg
        C.sudo_bg("DEBIAN_FRONTEND=noninteractive apt-get -y remove %s" % pkg, "/tmp/armbian-install.log")
        self.store_refresh()

    def all_users(self):
        res = []
        for line in C.read("/etc/passwd").splitlines():
            f = line.split(":")
            if len(f) >= 7:
                try:
                    uid = int(f[2])
                except ValueError:
                    continue
                if uid >= 1000 or uid == 0:
                    res.append({"name": f[0], "uid": uid, "home": f[5], "shell": f[6]})
        return res

    def page_users(self):
        p = ui.Page("Учётные записи", "Пользователи, вход в систему и права администратора")
        users = sorted(self.all_users(), key=lambda x: (0 if x["name"] == "agent" else 1, x["uid"]))
        for u in users:
            groups = C.out(["groups", u["name"]], timeout=6)
            is_admin = (u["name"] == "root") or ("sudo" in groups)
            title = ("Основной пользователь (%s)" % u["name"] if u["name"] == "agent"
                     else "Системная учётная запись (%s)" % u["name"] if u["name"] == "root"
                     else u["name"])
            c = p.card(title, icon="avatar-default")
            c.add(ui.info_row("Домашняя папка", u["home"]))
            c.add(ui.info_row("Тип учётной записи", lambda a=is_admin: "Администратор" if a else "Стандартный пользователь"))
            if u["name"] != "root":
                c.add(ui.row("Автоматический вход при включении",
                             ui._lbl("включён" if u["name"] == "agent" else "выключен", "value"),
                             sub="Рабочий стол открывается сразу без ввода пароля"))
            c.add(ui.row("Пароль входа", ui.button("Сменить пароль", lambda n=u["name"]: self.chpasswd(n), "ghost"),
                         sub="Используется для защиты учётной записи"))
        return p

    def set_admin(self, name, on):
        C.sudo(["gpasswd", "-a" if on else "-d", name, "sudo"])
        C.notify("Пользователи", "%s: права администратора %s" % (name, "выданы" if on else "сняты"))
        return True

    def chpasswd(self, name):
        p1 = ui.ask_text(self, "Новый пароль", "Пароль для %s:" % name, password=True)
        if not p1:
            return
        p2 = ui.ask_text(self, "Повторите", "Ещё раз:", password=True)
        if p1 != p2:
            ui.dialog(self, "Не совпало", "Пароли различаются, попробуйте снова.", ok="Закрыть")
            return
        code, o = C.sudo("echo '%s:%s' | chpasswd" % (name, p1))
        C.notify("Пользователи", "Пароль %s %s" % (name, "изменён" if code == 0 else "не изменён"))

    def add_user(self):
        name = self.new_user.get_text().strip()
        if not name or not re.match(r"^[a-z][a-z0-9_-]{2,20}$", name):
            ui.dialog(self, "Недопустимое имя", "Имя: строчные латинские буквы и цифры, 3–20 символов.",
                      ok="Закрыть")
            return
        pwd = ui.ask_text(self, "Пароль", "Пароль для нового пользователя:", password=True)
        if not pwd:
            return
        code, o = C.sudo(["useradd", "-m", "-s", "/bin/bash", name])
        if code != 0:
            ui.dialog(self, "Не получилось", o, ok="Закрыть")
            return
        C.sudo("echo '%s:%s' | chpasswd" % (name, pwd))
        C.notify("Пользователи", "Пользователь %s создан" % name)

    def page_autostart(self):
        p = ui.Page("Автозагрузка", "Всё, что запускается само — можно выключить и вернуть обратно")
        items = A.collect_all()
        on = sum(1 for i in items if i["enabled"])
        c = p.card("Сводка", icon="preferences-system-session")
        c.add(ui.info_row("Всего записей", str(len(items))))
        c.add(ui.info_row("Включено", str(on)))
        c.add(ui.info_row("Выключено", str(len(items) - on)))
        c.add(ui.info_row("Резервная копия", A.BACKUP))
        c.add(ui.row("Полный менеджер с поиском, фильтрами и добавлением",
                     ui.button("Открыть «Автозагрузку»",
                               lambda: C.run(["setsid", "armbian-autostart"], timeout=3),
                               "btn", "preferences-system-session")))

        c = p.card("Автозапуск сеанса", "программы, которые стартуют вместе с рабочим столом")
        self.as_store = Gtk.ListStore(bool, str, str)
        tv = Gtk.TreeView(model=self.as_store)
        r = Gtk.CellRendererToggle()
        r.set_property("activatable", True)
        r.connect("toggled", self.as_toggle)
        tv.append_column(Gtk.TreeViewColumn("ВКЛ", r, active=0))
        c1 = Gtk.CellRendererText()
        col = Gtk.TreeViewColumn("Программа", c1, text=1)
        col.set_expand(True)
        tv.append_column(col)
        c2 = Gtk.CellRendererText()
        c2.set_property("foreground", "#93a4b8")
        tv.append_column(Gtk.TreeViewColumn("Файл", c2, text=2))
        tv.set_size_request(-1, 200)
        c.add(tv)
        self.as_items = {}
        for it in items:
            if it["type"] in ("sys-desktop", "user-desktop"):
                self.as_store.append([it["enabled"], it["name"], it["path"]])
                self.as_items[it["key"]] = it
        return p

    def as_toggle(self, renderer, path):
        row = self.as_store[path]
        for key, it in self.as_items.items():
            if it["path"] == row[2]:
                A.backup_state(list(self.as_items.values()))
                A.set_enabled(it, not row[0])
                it["enabled"] = not row[0]
                self.as_store[path][0] = not row[0]
                C.notify("Автозагрузка", "%s — %s" % (it["name"], "включено" if it["enabled"] else "выключено"))
                return

    def page_services(self):
        p = ui.Page("Фоновые службы", "Программы, которые работают в фоне: сеть, принтер, экран, доступ извне. Основные службы управляются одним переключателем")

        key_svcs = [
            ("kvorix-vnc", "Показ экрана на телефоне", "Передача экрана в домашней сети через браузер", True),
            ("tailscaled", "Частная сеть Tailscale", "Связь между своими устройствами по защищённому каналу", True),
            ("kvorix-zapret", "Обход блокировок связи (Zapret)", "Нужен для стабильной работы Tailscale у провайдера", True),
            ("bluetooth", "Беспроводные устройства Bluetooth", "Наушники, колонки, пульты и мыши", True),
            ("cups", "Печать на принтерах (CUPS)", "Печать документов по USB и по домашней сети", True),
            ("front-panel", "Часы на корпусе (88:88)", "Светодиодный индикатор времени на передней панели", True),
            ("ssh", "Удалённый доступ SSH", "Системное управление мини-ПК по сети (защищена)", False),
            ("chrony", "Точное время через интернет", "Автоматическая настройка часов (защищена)", False),
        ]
        ck = p.card("Основные фоновые службы", icon="preferences-system-services",
                    subtitle="Понятное управление главными возможностями мини-ПК без риска сломать систему")
        for unit, title, desc, can_toggle in key_svcs:
            is_on = subprocess.run(["systemctl", "is-active", "-q", unit]).returncode == 0
            if can_toggle:
                def _toggle(st, u=unit, t=title):
                    act = "start" if st else "stop"
                    code, out = C.sudo(["systemctl", act, u])
                    if code == 0:
                        C.sudo(["systemctl", "enable" if st else "disable", u])
                        C.notify("Фоновые службы", "%s — %s" % (t, "включено" if st else "выключено"))
                        self.fill_services()
                        return True
                    C.notify("Фоновые службы", out.strip()[:100] or "Ошибка")
                    return False
                ck.add(ui.row(title, ui.switch(is_on, _toggle), sub=desc))
            else:
                ck.add(ui.row(title, ui._lbl("работает · системная" if is_on else "выключена", "value"), sub=desc))

        exp = Gtk.Expander(label="Все системные службы (для опытных)")
        p.add(exp)
        adv = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        exp.add(adv)
        p_adv = _Into(p, adv)

        c = p_adv.card("Полный список служб Linux", icon="applications-system",
                       subtitle="Выберите службу и нажмите действие. Критичные системные службы защищены от остановки.")
        self.svc_store = Gtk.ListStore(str, str, str, str, str)
        self.svc_filter = Gtk.ListStore(str, str, str, str, str)
        tv = Gtk.TreeView(model=self.svc_filter)
        for i, (t, w) in enumerate([("Служба", 250), ("Состояние", 130), ("Автозапуск", 130), ("Описание", 380), ("", 20)]):
            r = Gtk.CellRendererText()
            col = Gtk.TreeViewColumn(t, r, text=i)
            col.set_fixed_width(w)
            col.set_expand(i == 3)
            tv.append_column(col)
        sw = Gtk.ScrolledWindow()
        sw.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        sw.set_min_content_height(300)
        sw.add(tv)
        c.add(sw)
        e = ui.entry("", "Поиск службы…", width=320)
        e.connect("changed", lambda w: self.svc_search(w.get_text()))
        c.add(e)
        b = Gtk.Box(spacing=8)
        b.pack_start(ui.button("Запустить", lambda: self.svc_action(tv, "start"), "btn", "media-playback-start"), False, False, 0)
        b.pack_start(ui.button("Остановить", lambda: self.svc_action(tv, "stop"), "danger", "media-playback-stop"), False, False, 0)
        b.pack_start(ui.button("В автозапуск", lambda: self.svc_action(tv, "enable"), "ghost"), False, False, 0)
        b.pack_start(ui.button("Из автозапуска", lambda: self.svc_action(tv, "disable"), "ghost"), False, False, 0)
        b.pack_end(ui.button("Обновить", self.fill_services, "ghost", "view-refresh"), False, False, 0)
        c.add(b)
        self.fill_services()
        return p

    def fill_services(self):
        o = C.out(["systemctl", "list-units", "--type=service", "--all", "--no-legend",
                   "--no-pager", "--plain"], timeout=20)
        files = C.out(["systemctl", "list-unit-files", "--type=service", "--no-legend",
                       "--no-pager"], timeout=20)
        state = {}
        for line in files.splitlines():
            f = line.split()
            if len(f) >= 2:
                state[f[0]] = f[1]
        act_ru = {"active": "работает", "inactive": "выключена", "failed": "ошибка",
                  "activating": "запускается", "deactivating": "останавливается"}
        en_ru = {"enabled": "включён", "disabled": "выключен", "static": "системная",
                 "masked": "заблокирован", "indirect": "по запросу", "generated": "системная"}
        self.svc_store.clear()
        for line in o.splitlines():
            f = line.split(None, 4)
            if len(f) < 4:
                continue
            unit, load, active, sub = f[0], f[1], f[2], f[3]
            desc = f[4] if len(f) > 4 else ""
            if not unit.endswith(".service"):
                continue
            en = state.get(unit, "static")
            self.svc_store.append([unit, act_ru.get(active, active), en_ru.get(en, en), desc, ""])
        self.svc_search("")

    def svc_search(self, q):
        self.svc_filter.clear()
        q = q.lower()
        for row in self.svc_store:
            if q in (row[0] + row[3]).lower():
                self.svc_filter.append(list(row))

    def svc_action(self, tv, action):
        model, it = tv.get_selection().get_selected()
        if it is None:
            return
        unit = model[it][0]
        if A.is_critical(unit) and action in ("stop", "disable"):
            ui.dialog(self, "Служба защищена",
                      "%s — критичный компонент системы. Остановка отключила бы сеть, вход "
                      "или саму систему.\n\nДействие заблокировано." % unit, ok="Понятно")
            return
        if action in ("stop", "disable") and not ui.dialog(
                self, "Подтвердите", "Служба <b>%s</b> — %s?" % (
                    unit, "остановить" if action == "stop" else "убрать из автозапуска"),
                ok="Да", cancel=True):
            return
        code, out = C.sudo(["systemctl", action, unit])
        C.notify("Фоновые службы", "%s: %s" % (unit, "ок" if code == 0 else out.strip()[:100]))
        self.fill_services()

    def page_perf(self):
        p = ui.Page("Быстродействие", "Насколько загружен мини-ПК прямо сейчас: процессор, память, температура. Если притормаживает — смотрите «Что грузит систему»")
        c = p.card("Процессор", icon="cpu")
        self.perf_cpu = ui.info_row("Загрузка", lambda: self.perf_cpu_value())
        c.add(self.perf_cpu)
        self.perf_freq = ui.info_row("Частота", lambda: "%d МГц" % C.cpu_cur_mhz())
        c.add(self.perf_freq)
        c.add(ui.info_row("Ядер", lambda: str(os.cpu_count())))
        self.perf_la = ui.info_row("Средняя нагрузка", lambda: " · ".join(C.loadavg()))
        c.add(self.perf_la)
        govs = C.out("cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_available_governors", timeout=6).split() or ["schedutil"]
        gov_labels = {
            "schedutil": "Сбалансированный (рекомендуется)",
            "ondemand": "По нагрузке (авто)",
            "performance": "Максимальная скорость",
            "powersave": "Экономия энергии (тихий)",
            "conservative": "Плавный набор частоты",
            "userspace": "Ручной режим",
        }
        cur = C.cpu_governor()
        idx = govs.index(cur) if cur in govs else 0
        c.add(ui.row("Режим работы", ui.combo([gov_labels.get(g, g) for g in govs], idx,
                                              lambda i, _t: self.set_governor(govs[i])),
                     sub="Сбалансированный ускоряет процессор под нагрузкой и снижает нагрев в простое"))

        c = p.card("Память", icon="media-flash")
        self.perf_ram = ui.info_row(
            "Оперативная память",
            lambda: (lambda tot, used, _av: "%d из %d МБ (%d %%)" % (used, tot, 100 * used // max(1, tot)))(*C.ram()),
        )
        c.add(self.perf_ram)
        self.perf_swap = ui.info_row(
            "Подкачка",
            lambda: (lambda tot, used: "%d из %d МБ" % (used, tot))(*C.swap()),
        )
        c.add(self.perf_swap)
        c.add(ui.row("Очистить кэш памяти",
                     ui.button("Очистить", self.drop_caches, "ghost", "edit-clear"),
                     sub="Освобождает кэш файлов. Открытые программы и ваши данные не затрагиваются"))

        c = p.card("Температуры", icon="sensors-temperature-symbolic")
        self.perf_temp = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        c.add(self.perf_temp)

        c = p.card("Что грузит систему", icon="utilities-system-monitor")
        self.perf_store = Gtk.ListStore(str, str, str)
        tv = Gtk.TreeView(model=self.perf_store)
        for i, (t, w) in enumerate([("Программа", 280), ("Номер (PID)", 110), ("Нагрузка CPU", 120)]):
            r = Gtk.CellRendererText()
            col = Gtk.TreeViewColumn(t, r, text=i)
            col.set_fixed_width(w)
            col.set_expand(i == 0)
            tv.append_column(col)
        tv.set_size_request(-1, 180)
        c.add(tv)

        def tick():
            if not self.perf_cpu.get_parent():
                return True
            self.perf_cpu.refresh()
            self.perf_freq.refresh()
            self.perf_la.refresh()
            self.perf_ram.refresh()
            self.perf_swap.refresh()
            self.perf_store.clear()
            for pr in C.top_procs(8):
                self.perf_store.append([pr["name"], pr["pid"], "%.1f %%" % pr["cpu"]])
            for ch in self.perf_temp.get_children():
                ch.destroy()
            for n, v in C.temps():
                self.perf_temp.add(ui.info_row(n, "%.0f °C" % v))
            self.perf_temp.show_all()
            return True

        tick()
        GLib.timeout_add(1500, self._visible_only(tick))
        return p

    def perf_cpu_value(self):
        busy, total = C.cpu_times()
        pb, pt = getattr(self, "_pp2", (busy, total))
        self._pp2 = (busy, total)
        pct = 100.0 * (busy - pb) / (total - pt) if total != pt else 0
        return "%.1f %%" % pct

    def set_governor(self, gov):
        names = {
            "schedutil": "Сбалансированный",
            "ondemand": "По нагрузке",
            "performance": "Максимальная скорость",
            "powersave": "Экономия энергии",
        }
        code, o = C.sudo("for c in /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor; do echo %s > $c; done" % gov)
        C.notify("Быстродействие", "Режим: %s" % names.get(gov, gov))
        return True

    def drop_caches(self):
        C.sudo("sync; echo 3 > /proc/sys/vm/drop_caches")
        C.notify("Память", "Кэш очищен")

    def page_updates(self):
        p = ui.Page("Обновления", "Обновление системы и установленных программ")
        c = p.card("Состояние", icon="software-update-available")
        c.add(ui.info_row("Доступно обновлений", lambda: self._upgradable()))
        c.add(ui.info_row("Автообновления", lambda: "включены (unattended-upgrades)"
                          if C.out(["systemctl", "is-enabled", "unattended-upgrades"]) == "enabled"
                          else "выключены"))
        c.add(ui.info_row("Последняя проверка", lambda: time.strftime(
            "%d.%m %H:%M", time.localtime(os.path.getmtime("/var/lib/apt/lists")))
            if os.path.exists("/var/lib/apt/lists") else "—"))
        c.add(ui.row("Проверить обновления", ui.button("Проверить сейчас", self.apt_update, "btn", "view-refresh")))
        c.add(ui.row("Обновить систему", ui.button("Установить обновления", self.apt_upgrade, "btn", "software-update-available"),
                     sub="Скачает и установит всё. Займёт несколько минут, ход — в отдельном окне"))
        c.add(ui.row("Полное обновление", ui.button("Обновить + новые пакеты", self.apt_full, "ghost")))
        return p

    def apt_update(self):
        log = C.sudo_bg("DEBIAN_FRONTEND=noninteractive apt-get update", "/tmp/armbian-update.log")
        log_window(self, "Проверка обновлений", log)
        C.notify("Обновления", "Проверка списка пакетов началась")

    def apt_upgrade(self):
        if not ui.dialog(self, "Обновить систему?",
                         "Все установленные программы получат обновления. Мини-ПК останется "
                         "включённой, перезагрузка обычно не нужна.", ok="Обновить", cancel=True):
            return
        log = C.sudo_bg("DEBIAN_FRONTEND=noninteractive apt-get -y upgrade", "/tmp/armbian-upgrade.log")
        log_window(self, "Обновление системы", log)
        C.notify("Обновления", "Установка обновлений началась")

    def apt_full(self):
        log = C.sudo_bg("DEBIAN_FRONTEND=noninteractive apt-get -y full-upgrade", "/tmp/armbian-full.log")
        log_window(self, "Полное обновление", log)

    def page_security(self):
        p = ui.Page("Безопасность", "Защита доступа к экрану, удалённого входа и сетевых служб")

        cs = p.card("Защита показа экрана", icon="video-display")
        funnel_off = "Funnel on" not in C.out(["tailscale", "funnel", "status"], timeout=5)
        vnc_local = "127.0.0.1:5900" in C.out(["ss", "-ltn"], timeout=5)
        cs.add(ui.info_row("Публичный доступ из интернета", "закрыт (только домашняя сеть)" if funnel_off else "включён (Funnel)"))
        cs.add(ui.info_row("Ссылка экрана на телефоне", "защищена 48-значным секретным ключом"))
        cs.add(ui.info_row("Прямой порт VNC (:5900)", "закрыт извне (только внутри устройства)" if vnc_local else "проверьте настройки"))

        c = p.card("Удалённый вход (SSH)", icon="security-high")
        ssh_on = C.out(["systemctl", "is-active", "ssh"]) == "active"
        def _root_ssh_label():
            m = re.search(r"^\s*PermitRootLogin\s+(\S+)", C.read("/etc/ssh/sshd_config"), re.M)
            val = m.group(1).lower() if m else ""
            if val in ("prohibit-password", "without-password"):
                return "только по ключу (вход по паролю закрыт)"
            if val == "no":
                return "полностью отключён"
            if val == "yes":
                return "разрешён по паролю"
            return "по умолчанию (только по ключу)"

        c.add(ui.info_row("Служба SSH", lambda: "работает" if ssh_on else "выключена"))
        c.add(ui.info_row("Порт подключения", lambda: (re.search(r"^\s*Port\s+(\d+)", C.read("/etc/ssh/sshd_config"), re.M)
                                                       or re.search(r"(\d+)", "22")).group(1)))
        c.add(ui.info_row("Вход администратора (root)", _root_ssh_label))
        c.add(ui.row("Разрешить вход root по ключу SSH", ui.switch(
            self.root_ssh_on(),
            self.set_root_ssh), sub="Выключено — root не может войти по SSH даже по ключу"))

        c = p.card("Учётные записи с правами администратора", icon="dialog-password")
        c.add(ui.info_row("Администраторы системы", lambda: C.out(["getent", "group", "sudo"]).split(":")[-1] or "agent"))
        c.add(ui.info_row("Управление настройками", lambda: "без лишних запросов пароля для основного пользователя"))

        c = p.card("Защита системы и сеть", icon="security-medium")
        c.add(ui.info_row("Автоматические обновления безопасности",
                          lambda: "включены" if C.out(["systemctl", "is-enabled", "unattended-upgrades"]) == "enabled" else "выключены"))
        c.add(ui.info_row("Сетевой фильтр", lambda: self.fw_state()))
        c.add(ui.row("Открытые сетевые порты", ui.button("Показать", self.show_ports, "ghost", "network-server"),
                     sub="Покажет, какие службы принимают подключения по сети"))

        c = p.card("Журнал сбоев", icon="dialog-warning")
        c.add(ui.info_row("Служб с ошибками", lambda: str(self._failed_count())))
        c.add(ui.row("Последние системные ошибки", ui.button("Открыть журнал", self.show_errors, "ghost")))
        return p

    def root_ssh_on(self):
        m = re.search(r"^\s*PermitRootLogin\s+(\S+)", C.read("/etc/ssh/sshd_config"), re.M)
        return bool(m and m.group(1).lower() in ("yes", "prohibit-password"))

    def set_root_ssh(self, on):
        if not ui.dialog(self, "Изменить вход root по SSH?",
                         "Будет изменён /etc/ssh/sshd_config и перезапущен SSH. "
                         "Резервная копия сохранится рядом с файлом.", ok="Изменить", cancel=True):
            return False
        val = "prohibit-password" if on else "no"
        C.sudo("cp -n /etc/ssh/sshd_config /etc/ssh/sshd_config.bak; "
               "sed -i 's/^#*PermitRootLogin.*/PermitRootLogin %s/' /etc/ssh/sshd_config; "
               "systemctl reload ssh" % val)
        C.notify("Безопасность", "Вход root по SSH: %s" % ("только по ключу" if on else "отключён"))
        return True

    def fw_state(self):
        code, o = C.sudo(["nft", "list", "tables"], timeout=8)
        if code == 0 and o.strip():
            return "активен (таблиц правил: %d)" % len(o.strip().splitlines())
        return "стандартный режим домашней сети"

    def show_ports(self):
        raw = C.sudo("ss -tlnH | awk '{print $4}'")[1]
        known = {
            "22": "Удалённый доступ SSH",
            "80": "Веб-сервер",
            "631": "Служба печати принтеров (CUPS)",
            "5900": "Внутренний сервер экрана VNC",
            "6080": "Показ экрана в браузере (по секретной ссылке)",
            "6081": "Внутренний мост WebSocket для экрана",
        }
        seen = []
        for addr in raw.splitlines():
            addr = addr.strip()
            if not addr or ":" not in addr:
                continue
            host, port = addr.rsplit(":", 1)
            scope = "только внутри устройства" if host in ("127.0.0.1", "[::1]", "::1") else "в локальной сети"
            desc = known.get(port, "Сетевая служба")
            line = "Порт %-5s · %-26s — %s" % (port, scope, desc)
            if line not in seen:
                seen.append(line)
        d = Gtk.MessageDialog(transient_for=self, modal=True, message_type=Gtk.MessageType.INFO,
                              buttons=Gtk.ButtonsType.CLOSE)
        d.set_markup("<b>Открытые сетевые порты</b>")
        d.format_secondary_text("\n".join(seen[:25]) if seen else "активных портов нет")
        d.run()
        d.destroy()

    def show_errors(self):
        txt = C.sudo("journalctl -p 3 -b --no-pager | tail -25")[1]
        d = Gtk.MessageDialog(transient_for=self, modal=True, message_type=Gtk.MessageType.INFO,
                              buttons=Gtk.ButtonsType.CLOSE)
        d.set_markup("<b>Ошибки текущей загрузки</b>")
        d.format_secondary_text(txt or "ошибок нет")
        d.run()
        d.destroy()

    def page_appearance(self):
        
        p = ui.Page("Персонализация", "Режим, цвет акцента и эффекты — применяется сразу")
        try:
            cur = json.loads(subprocess.run(["armbian-personalize", "get"], capture_output=True,
                                            text=True).stdout)
        except ValueError:
            cur = {"mode": "light", "accent": "blue", "transparency": True, "animations": True,
                   "nightlight": False, "accents": {}}

        def put(key, val):
            _spawn(["armbian-personalize", "set", key, str(val).lower()],
                             env=dict(os.environ, ARMBIAN_FROM_CENTER="1"))
            cur[key] = val
            GLib.timeout_add(900, lambda: (ui.reload_css(), False)[1])

        c = p.card("Режим", icon="preferences-desktop-theme")
        box = Gtk.Box(spacing=12)
        first = None
        for key, title, sub in (("light", "Светлый", "светлые окна и панель"),
                                ("dark", "Тёмный", "тёмные окна и панель")):
            rb = Gtk.RadioButton.new_with_label_from_widget(first, "%s — %s" % (title, sub))
            first = first or rb
            rb.set_active(cur["mode"] == key)
            rb.connect("toggled", lambda b, k=key: b.get_active() and put("mode", k))
            box.pack_start(rb, True, True, 0)
        c.add(box)

        c2 = p.card("Цвет акцента", icon="preferences-color")
        flow = Gtk.Box(spacing=10)
        names = cur.get("accents") or {}
        colors = {"blue": "#2f7cf6", "teal": "#0f8f94", "green": "#1e8a3c", "purple": "#7a4ce0",
                  "pink": "#c8327a", "red": "#d13438", "orange": "#c75c00", "graphite": "#56606e"}
        swatches = {}

        def mark(sel):
            for k, b in swatches.items():
                ctx = b.get_style_context()
                (ctx.add_class if k == sel else ctx.remove_class)("swatch-on")

        for key, col in colors.items():
            b = Gtk.Button()
            b.set_tooltip_text(names.get(key, key))
            b.set_size_request(40, 40)
            b.set_valign(Gtk.Align.CENTER)
            prov = Gtk.CssProvider()
            prov.load_from_data((
                "button { background: %s; border-radius: 999px; min-width: 36px; min-height: 36px; padding: 0;"
                " border: 3px solid transparent; box-shadow: none; }"
                "button.swatch-on { border-color: @text; }" % col).encode())
            b.get_style_context().add_provider(prov, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 1)
            b.connect("clicked", lambda _b, k=key: (put("accent", k), mark(k)))
            swatches[key] = b
            flow.pack_start(b, False, False, 0)
        mark(cur["accent"])
        c2.add(flow)

        c3 = p.card("Эффекты", icon="preferences-desktop-effects")
        c3.add(ui.row("Ночной свет", ui.switch(cur["nightlight"], lambda st: put("nightlight", st)),
                      sub="Тёплые тона экрана вечером — меньше нагрузка на глаза"))

        c4 = p.card("Текст", icon="preferences-desktop-font")
        size = 10
        try:
            size = int(xfget("xsettings", "/Gtk/FontName", "Inter 10").split()[-1])
        except ValueError:
            pass
        lab = Gtk.Label(label="%d pt" % size)
        lab.get_style_context().add_class("value")

        def on_size(v):
            xfset("xsettings", "/Gtk/FontName", "Inter %d" % int(v))
            lab.set_text("%d pt" % int(v))

        c4.add(ui.row("Размер шрифта", lab))
        c4.add(ui.slider(8, 16, 1, size, on_size))
        return p

    def page_ai(self):
        
        p = ui.Page("Доступ ИИ", "Удалённое управление этим мини-ПК ИИ-агентом (например, Claude)")

        def slots():
            r = subprocess.run(["systemctl", "is-active", "agent-slot@0", "agent-slot@1"],
                               capture_output=True, text=True).stdout.split()
            return sum(1 for s in r if s == "active")

        c = p.card("Разрешение", icon="preferences-system-privacy")
        status = ui._lbl("", "value")

        def show():
            n = slots()
            status.set_text("включён — мини-ПК ждёт подключения" if n else "выключен — подключиться нельзя")
            return False

        def toggle(on):
            _spawn(["sudo", "-n", "/usr/local/sbin/ai-access", "on" if on else "off"])
            GLib.timeout_add(2500, show)
            GLib.timeout_add(3000, lambda: poll_who() and False)

        c.add(ui.row("Разрешить ИИ-агентам подключаться", ui.switch(slots() > 0, toggle),
                     sub="Выключите — и никто не сможет подключиться удалённо"))
        c.add(ui.row("Сейчас", status))
        show()

        # подключение агента: три шага по порядку; ключ и QR — под «Ещё»
        ck = p.card("Подключить ИИ-агента", icon="network-server")
        AI = "/usr/local/share/kvorix/ai"
        KIT = os.path.expanduser("~/Загрузки/kvorix-ai")

        def ai_out(*a):
            return C.out(["sudo", "-n", "/usr/local/sbin/ai-access"] + list(a))

        def tpl(template):
            try:
                return open(AI + "/" + template, encoding="utf-8").read().replace("@TOPIC@", ai_out("topic").strip())
            except OSError:
                return ""

        def qr_img(text, path):
            subprocess.run(["qrencode", "-s", "3", "-m", "1", "-o", path, text], capture_output=True)
            return Gtk.Image.new_from_file(path)

        def copy(text, what):
            Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD).set_text(text, -1)
            C.notify("Доступ ИИ", what + " скопирован в буфер обмена")

        def save_kit():
            os.makedirs(KIT, exist_ok=True)
            for name, text, mode in (("id_ed25519", ai_out("key"), 0o600), ("connect.sh", tpl("connect.sh"), 0o755),
                                     ("ДЛЯ-ИИ.txt", tpl("prompt.txt"), 0o644)):
                path = os.path.join(KIT, name)
                with open(path, "w", encoding="utf-8", newline="\n") as f:
                    f.write(text)
                os.chmod(path, mode)
            _spawn(["thunar", KIT])

        ck.add(ui.row("1. Сохраните набор для агента", ui.button("Сохранить", save_kit, "btn", "document-save"),
                      sub="Ключ и скрипт подключения появятся в папке «Загрузки → kvorix-ai»"))
        ck.add(ui.row("2. Перенесите папку kvorix-ai на компьютер, где работает ИИ",
                      sub="Флешкой, по сети или через облако — эта папка и есть пропуск для агента"))
        ck.add(ui.row("3. Отправьте агенту это сообщение",
                      ui.button("Скопировать текст", lambda: copy(tpl("prompt.txt"), "Текст"), "ghost", "edit-copy"),
                      sub="Вставьте его в чат с ИИ — он сам подключится"))
        msg = ui._lbl(tpl("prompt.txt").strip(), "muted", wrap=True)
        msg.set_selectable(True)
        msg.set_xalign(0)
        mb = Gtk.Box()
        mb.get_style_context().add_class("tile")
        mb.pack_start(msg, True, True, 0)
        ck.add(mb)

        more = Gtk.Expander(label="Ещё: ключ отдельно, QR, замена ключа")
        mbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        mbox.set_margin_top(6)
        key_qr = Gtk.Box()

        def show_key_qr():
            for ch in key_qr.get_children():
                key_qr.remove(ch)
            key_qr.pack_start(qr_img(ai_out("key"), "/tmp/kvorix-ai-key.png"), False, False, 0)
            key_qr.show_all()

        def new_key():
            if not ui.dialog(self, "Заменить ключ?", "Старый ключ перестанет работать, подключённые агенты отключатся. "
                             "Потом сохраните набор заново.", ok="Заменить", cancel="Отмена"):
                return
            ai_out("newkey")
            C.notify("Доступ ИИ", "Ключ заменён — сохраните набор заново")
            if key_qr.get_children():
                show_key_qr()

        kb = Gtk.Box(spacing=6)
        kb.pack_start(ui.button("Показать ключ как QR", show_key_qr, "ghost", "view-reveal-symbolic"), False, False, 0)
        kb.pack_start(ui.button("Скопировать ключ", lambda: copy(ai_out("key"), "Ключ"), "ghost", "edit-copy"), False, False, 0)
        kb.pack_start(ui.button("Заменить ключ", new_key, "ghost", "view-refresh"), False, False, 0)
        mbox.pack_start(kb, False, False, 0)
        mbox.pack_start(key_qr, False, False, 0)
        more.add(mbox)
        ck.add(more)

        cw = p.card("Кто подключён прямо сейчас", icon="system-users")
        head = ui._lbl("", "dash-big")
        cw.add(head)
        who_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        cw.add(who_box)
        cw.add(ui.row("Выгнать всех", ui.button("Отключить", lambda: (_spawn(
            ["sudo", "-n", "/usr/local/sbin/ai-access", "kick"]), GLib.timeout_add(5000, poll_who)),
            "ghost", "process-stop"),
            sub="Все подключения рвутся; снова войти сможет только агент, у которого есть ключ"))

        def fill(rows):
            for ch in who_box.get_children():
                who_box.remove(ch)
            if not rows:
                head.set_text("Никого нет")
            else:
                ai_n = sum(1 for r in rows if r and r[0] == "ИИ-агент")
                hu_n = len(rows) - ai_n
                head.set_text("Подключено: %d — ИИ-агентов: %d, людей: %d" % (len(rows), ai_n, hu_n))
            for typ, ident, addr, detail, since in rows:
                box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
                box.get_style_context().add_class("tile")
                if typ == "ИИ-агент":
                    d = [s.strip() for s in detail.split(" · ")]
                    slot, prog, where = (d + ["", "", ""])[:3]
                    host, name = (d[3:] + ["", ""])[:2]
                    title = "%s на компьютере %s" % (name, host) if host else "ИИ-агент"
                    box.pack_start(ui._lbl(title, "tile-title"), False, False, 0)
                    box.pack_start(ui._lbl("Адрес в интернете: %s — %s" % (addr, where), "muted"), False, False, 0)
                    box.pack_start(ui._lbl("Ключ: «%s» · %s · %s" % (ident, prog, slot), "muted"), False, False, 0)
                else:
                    box.pack_start(ui._lbl("Человек — пользователь «%s»" % ident, "tile-title"), False, False, 0)
                    box.pack_start(ui._lbl("Откуда: %s (адрес в вашей сети)" % addr, "muted"), False, False, 0)
                    box.pack_start(ui._lbl("Подключён: %s · %s" % (since, detail), "muted"), False, False, 0)
                who_box.pack_start(box, False, False, 0)
            who_box.show_all()
            return False

        def poll_who():
            def bg():
                try:
                    out = subprocess.run(["sudo", "-n", "/usr/local/sbin/ai-access", "who"],
                                         capture_output=True, text=True, timeout=20).stdout
                except Exception:
                    out = ""
                GLib.idle_add(fill, [l.split("	") for l in out.splitlines() if l.count("	") == 4])
            threading.Thread(target=bg, daemon=True).start()
            return True

        poll_who()
        def _tick():
            if cw.get_mapped():
                poll_who()
                poll_hist()
            return True
        GLib.timeout_add_seconds(8, _tick)

        ch = p.card("Последние входы (журнал)", icon="document-open-recent")
        hist_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        ch.add(hist_box)

        def fill_hist(text):
            for c0 in hist_box.get_children():
                hist_box.remove(c0)
            for line in text.splitlines():
                parts = line.split("\t")
                if len(parts) != 5:
                    continue
                t, user, rhost, kind, src = parts
                mark = "ИИ" if kind == "ИИ" else "человек"
                hist_box.pack_start(ui._lbl("%s   %s   %s   ← %s (%s)" % (t, mark, user, rhost, src), "muted"),
                                    False, False, 0)
            if not hist_box.get_children():
                hist_box.pack_start(ui._lbl("Журнал пуст", "muted"), False, False, 0)
            hist_box.show_all()
            return False

        def poll_hist():
            def bg():
                try:
                    out = subprocess.run(["sudo", "-n", "/usr/local/sbin/ai-access", "history", "15"],
                                         capture_output=True, text=True, timeout=10).stdout
                except Exception:
                    out = ""
                GLib.idle_add(fill_hist, out)
            threading.Thread(target=bg, daemon=True).start()
            return True

        poll_hist()

        c2 = p.card("Как это работает", icon="dialog-information")
        for t in ("Мини-ПК сам соединяется с upterm.dev — роутер настраивать не нужно.",
                  "Войти может только агент с ключом; «Новый ключ» отключает старый.",
                  "Входы записываются в /var/lib/kvorix/access.log."):
            c2.add(ui._lbl("• " + t, None, wrap=True))
        return p

    def page_devices(self):
        p = ui.Page("Устройства", "Вставили — работает: флешки, телефоны, мыши, клавиатуры, принтеры, камеры")

        cu = p.card("Подключено по USB", icon="drive-removable-media")
        ubox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        cu.add(ubox)

        cd = p.card("Флешки и диски", icon="drive-removable-media")
        dbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        cd.add(dbox)

        def fill():
            for b in (ubox, dbox):
                for ch in b.get_children():
                    b.remove(ch)
            for name, kind, ok in usb_devices():
                ubox.pack_start(ui.row(name, ui._lbl(kind if ok else "нет драйвера", "value" if ok else "pill-warn")),
                                False, False, 0)
            if not ubox.get_children():
                ubox.pack_start(ui._lbl("Ничего не подключено", "muted"), False, False, 0)
            for dev, label, mnt, size in removable_mounts():
                bb = Gtk.Box(spacing=6)
                bb.pack_start(ui.button("Открыть", lambda m=mnt: _spawn(["thunar", m]), "ghost", "folder-open"),
                              False, False, 0)
                bb.pack_start(ui.button("Извлечь", lambda d=dev: eject(d), "ghost", "media-eject"), False, False, 0)
                dbox.pack_start(ui.row("%s (%s)" % (label, size), bb, sub=mnt), False, False, 0)
            if not dbox.get_children():
                dbox.pack_start(ui._lbl("Вставьте флешку — она откроется сама", "muted"), False, False, 0)
            ubox.show_all(); dbox.show_all()
            return True

        def eject(dev):
            subprocess.run(["udisksctl", "unmount", "-b", dev], capture_output=True)
            base = dev.rstrip("0123456789")
            subprocess.run(["udisksctl", "power-off", "-b", base], capture_output=True)
            C.notify("Устройства", "Можно отключать")
            fill()

        fill()
        GLib.timeout_add_seconds(3, lambda: fill() if cu.get_mapped() else True)

        cp = p.card("Принтеры и сканеры", icon="printer")
        printers = [l.strip() for l in C.out(["lpstat", "-e"]).splitlines() if l.strip() and " " not in l.strip()]
        cp.add(ui.row("Принтеры", ui._lbl(", ".join(printers) if printers else "не добавлены", "value"),
                      sub="USB-принтеры с поддержкой «без драйвера» (IPP-USB) находятся сами"))
        bb = Gtk.Box(spacing=6)
        bb.pack_start(ui.button("Добавить принтер", lambda: _spawn(["system-config-printer"]), "btn", "list-add"),
                      False, False, 0)
        bb.pack_start(ui.button("Сканировать", lambda: _spawn(["simple-scan"]), "ghost", "scanner"),
                      False, False, 0)
        cp.add(ui.row("", bb))

        cs = p.card("Показ экрана на телефоне", icon="video-display")
        ip = C.net_info()["ip"]

        def screen_link():
            pw = C.out(["sudo", "-n", "cat", "/etc/kvorix/vnc.pass.txt"]).strip()
            tok = C.out(["sudo", "-n", "cat", "/etc/kvorix/novnc.token"]).strip()
            return pw, "http://%s:6080/%s/vnc.html?autoconnect=1&resize=scale&password=%s" % (ip, tok, pw)

        qr_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        qr_box.pack_start(ui._lbl("В той же сети (телефон, компьютер)", "tile-title"), False, False, 0)
        pw_lbl = ui._lbl("", "value")

        def fill_qr():
            pw, full = screen_link()
            for ch in qr_box.get_children()[1:]:
                qr_box.remove(ch)
            png = "/tmp/kvorix-qr-local.png"
            subprocess.run(["qrencode", "-s", "6", "-m", "2", "-o", png, full], capture_output=True)
            qr_box.pack_start(Gtk.Image.new_from_file(png), False, False, 0)
            lb = ui._lbl(full, "muted"); lb.set_selectable(True)
            qr_box.pack_start(lb, False, False, 0)
            pw_lbl.set_text(pw or "—")
            qr_box.show_all()

        def new_link():
            C.out(["sudo", "-n", "/usr/local/sbin/kvorix-novnc-token"])
            C.notify("Показ экрана", "Ссылка обновлена — отсканируйте новый QR")
            fill_qr()

        fill_qr()
        bb = Gtk.Box(spacing=6)
        bb.pack_start(ui.button("Сменить ссылку", lambda: new_link(), "ghost", "view-refresh"), False, False, 0)
        cs.add(qr_box)
        cs.add(ui.row("Пароль VNC", pw_lbl,
                      sub="QR уже содержит ссылку и пароль — наведите камеру и входите. Ссылка секретная: 48-значный токен в URL (длиннее любого пароля VNC). Доступ из интернета закрыт — только домашняя сеть"))
        cs.add(ui.row("", bb))

        cf = p.card("Индикатор на корпусе (88:88)", icon="preferences-system-time")
        FP = "/var/lib/front-panel/config.json"
        try:
            fpc = json.load(open(FP))
        except (OSError, ValueError):
            fpc = {}
        fpc = dict({"screens": ["clock"], "seconds": 5, "brightness": 7, "night": True}, **fpc)
        def fp_save():
            subprocess.run(["sudo", "-n", "tee", FP], input=json.dumps(fpc, ensure_ascii=False), text=True,
                           capture_output=True)
        def fp_toggle(key, on):
            s = [x for x in fpc["screens"] if x != key]
            if on:
                s.append(key)
            fpc["screens"] = [k for k, _ in FP_SCREENS if k in s] or ["clock"]
            fp_save()
        grid = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, min_children_per_line=2, max_children_per_line=3)
        for key, name in FP_SCREENS:
            cb = Gtk.CheckButton(label=name)
            cb.set_active(key in fpc["screens"])
            cb.connect("toggled", lambda w, k=key: fp_toggle(k, w.get_active()))
            grid.add(cb)
        cf.add(ui._lbl("Что показывать (по очереди):", "muted"))
        cf.add(grid)
        cf.add(ui.row("Смена каждые, секунд", ui.slider(2, 30, 1, fpc["seconds"],
                      lambda v: (fpc.__setitem__("seconds", int(v)), fp_save()))))
        cf.add(ui.row("Яркость", ui.slider(0, 7, 1, fpc["brightness"],
                      lambda v: (fpc.__setitem__("brightness", int(v)), fp_save()))))
        cf.add(ui.row("Ночью тусклее (22:00–7:00)", ui.switch(fpc.get("night", True),
                      lambda on: (fpc.__setitem__("night", on), fp_save()))))

        cm = p.card("Мышь", icon="input-mouse")
        mice = pointer_names()
        def set_speed(v):
            for n in mice:
                subprocess.run(["xfconf-query", "-c", "pointers", "-p", "/%s/Properties/libinput_Accel_Speed" % n,
                                "-n", "-t", "double", "-s", "%.2f" % v], capture_output=True)
        def set_natural(on):
            for n in mice:
                subprocess.run(["xfconf-query", "-c", "pointers", "-p", "/%s/Properties/libinput_Natural_Scrolling_Enabled" % n,
                                "-n", "-t", "int", "-s", "1" if on else "0"], capture_output=True)
        cur = xfget("pointers", "/%s/Properties/libinput_Accel_Speed" % mice[0], "0") if mice else "0"
        nat_cur = xfget("pointers", "/%s/Properties/libinput_Natural_Scrolling_Enabled" % mice[0], "0") == "1" if mice else False
        try:
            cur = float(cur.replace(",", "."))
        except ValueError:
            cur = 0.0
        cm.add(ui.row("Скорость указателя", ui.slider(-1, 1, 0.1, cur, set_speed),
                      sub="Для всех подключённых мышей и тачпадов"))
        cm.add(ui.row("Естественная прокрутка", ui.switch(nat_cur, set_natural), sub="Колесо крутит страницу, а не ползунок"))
        if not mice:
            cm.add(ui._lbl("Мышь не найдена", "muted"))

        _dev = p.card("Пульт и датчики", "Сопряжение XING WEI 2.4G: зажмите одновременно OK и Menu на 2–3 с, пока светодиод не замигает часто, поднесите пульт к приёмнику (~10 см) и подождите до 20 с — свет погас, значит сопряжено. Не помогло: выньте приёмник, выключите и включите пульт, вставьте приёмник заново", icon="input-keyboard")
        ev_lbl = ui._lbl("…", "muted", wrap=True)
        import os as _os
        _st = {}
        _ev_size = struct.calcsize("llHHi")
        def _devs():
            res = []
            for i in range(16):
                e = "/dev/input/event%d" % i
                if not _os.path.exists(e):
                    continue
                nm = "?"
                for base in ("/sys/class/input/event%d/device" % i, "/sys/class/input/event%d" % i):
                    try:
                        with open(base + "/name", encoding="utf-8", errors="replace") as nf:
                            nm = nf.read().strip()
                        break
                    except OSError:
                        pass
                res.append((e, nm))
            return res
        def _tick(force=False):
            if not force and not ev_lbl.get_mapped():
                return True
            now = time.time()
            lines = []
            for e, nm in _devs():
                st = _st.setdefault(e, [0, 0.0])
                try:
                    fd = _os.open(e, _os.O_RDONLY | _os.O_NONBLOCK)
                except OSError:
                    fd = None
                if fd is not None:
                    try:
                        while True:
                            try:
                                data = _os.read(fd, 65536)
                            except OSError:
                                break
                            if not data:
                                break
                            st[0] += max(1, len(data) // _ev_size)
                            st[1] = now
                    finally:
                        _os.close(fd)
                if not st[1]:
                    s2 = "нет событий"
                else:
                    q = int(now - st[1])
                    s2 = "тишина %d с" % q if q < 60 else "тишина %d мин" % (q // 60)
                lines.append("%s — %d событий, %s" % (nm, st[0], s2))
            try:
                ev_lbl.set_text("сигналы по устройствам:\n" + "\n".join(lines) if lines else "входов нет")
            except Exception:
                pass
            return True
        _tick(force=True)
        _tid = GLib.timeout_add_seconds(1, _tick)
        ev_lbl._tid = _tid
        def _kill(*a):
            try:
                if getattr(ev_lbl, "_tid", None) == _tid:
                    GLib.source_remove(_tid)
                ev_lbl._tid = None
            except Exception:
                pass
        ev_lbl.connect("destroy", _kill)
        _dev.add(ev_lbl)
        return p

    def page_timelang(self):
        p = ui.Page("Время и язык", "Часовой пояс и раскладки клавиатуры")
        c = p.card("Дата и время", icon="preferences-system-time")
        tz = C.out(["timedatectl", "show", "-p", "Timezone", "--value"]).strip() or "UTC"
        sync = C.out(["timedatectl", "show", "-p", "NTPSynchronized", "--value"]).strip() == "yes"
        zones = TIMEZONES if tz in TIMEZONES else [tz] + TIMEZONES
        def set_tz(i, *_):
            if i is None or not (0 <= i < len(zones)):
                return
            subprocess.run(["sudo", "-n", "timedatectl", "set-timezone", zones[i]], capture_output=True)
            C.notify("Время и язык", "Часовой пояс: " + TZ_NAMES.get(zones[i], zones[i]))
        c.add(ui.row("Часовой пояс", ui.combo([TZ_NAMES.get(z, z) for z in zones], zones.index(tz), set_tz)))
        c.add(ui.row("Синхронизация через интернет", ui._lbl("работает" if sync else "нет связи с сервером времени",
                                                            "value")))
        k = p.card("Клавиатура", icon="input-keyboard")
        cur_opt = xfget("keyboard-layout", "/Default/XkbOptions/Group", "grp:alt_shift_toggle")
        keys = [("grp:alt_shift_toggle", "Alt + Shift"), ("grp:ctrl_shift_toggle", "Ctrl + Shift"),
                ("grp:win_space_toggle", "Win + Пробел (как в Windows 11)")]
        idx = next((i for i, (o, _) in enumerate(keys) if o == cur_opt), 0)
        def set_key(i, *_):
            if i is None or not (0 <= i < len(keys)):
                return
            opt = keys[i][0]
            for prop, typ, val in (("/Default/XkbDisable", "bool", "false"), ("/Default/XkbLayout", "string", "us,ru"),
                                   ("/Default/XkbOptions/Group", "string", opt)):
                subprocess.run(["xfconf-query", "-c", "keyboard-layout", "-p", prop, "-n", "-t", typ, "-s", val],
                               capture_output=True)
            subprocess.run(["setxkbmap", "-layout", "us,ru", "-option", "", "-option", opt], capture_output=True)
            C.notify("Клавиатура", "Переключение языка: " + keys[i][1])
        k.add(ui.row("Раскладки", ui._lbl("English, Русский", "value")))
        k.add(ui.row("Переключение языка", ui.combo([n for _, n in keys], idx, set_key)))
        return p

    def page_wallpaper(self):
        p = ui.Page("Обои", "Фотография на рабочем столе — меняется сразу")
        os.makedirs(WALL_DIR, exist_ok=True)
        c = p.card("Готовые обои", icon="preferences-desktop-wallpaper")
        flow = Gtk.FlowBox()
        flow.set_valign(Gtk.Align.START)
        flow.set_max_children_per_line(4)
        flow.set_selection_mode(Gtk.SelectionMode.NONE)
        flow.set_row_spacing(10)
        flow.set_column_spacing(10)
        for fn in sorted(os.listdir(WALL_DIR)):
            if not fn.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
                continue
            path = os.path.join(WALL_DIR, fn)
            b = Gtk.Button()
            b.set_relief(Gtk.ReliefStyle.NONE)
            v = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
            try:
                pix = Gtk.Image.new_from_pixbuf(
                    GdkPixbuf.Pixbuf.new_from_file_at_scale(path, 260, 146, True))
            except Exception:
                pix = Gtk.Image.new_from_icon_name("image-x-generic", Gtk.IconSize.DIALOG)
            v.pack_start(pix, False, False, 0)
            lab = Gtk.Label(label=fn.rsplit(".", 1)[0])
            lab.get_style_context().add_class("muted")
            v.pack_start(lab, False, False, 0)
            b.add(v)
            b.connect("clicked", lambda _w, pp=path: self.set_wallpaper(pp))
            flow.add(b)
        c.add(flow)

        c = p.card("Своя картинка", icon="document-open")
        c.add(ui.row("Выбрать файл с фотографией",
                     ui.button("Выбрать…", self.choose_wallpaper, "btn", "document-open"),
                     sub="JPG или PNG. Скопируется в %s и станет обоями" % WALL_DIR))
        c.add(ui.row("Вернуть стандартные", ui.button("Сбросить", self.reset_wallpaper, "ghost", "edit-undo")))
        return p

    def set_wallpaper(self, path):
        keys = C.out(["xfconf-query", "-c", "xfce4-desktop", "-l"], timeout=8).splitlines()
        done = 0
        for k in keys:
            if k.endswith("last-image"):
                xfset("xfce4-desktop", k, path)
                done += 1
        if done == 0:
            C.run(["xfconf-query", "-c", "xfce4-desktop", "-p", "/backdrop/screen0/monitor0/workspace0/last-image",
                   "-n", "-t", "string", "-s", path], timeout=8)
        C.run(["xfdesktop", "--reload"], timeout=8)
        C.notify("Обои", "Установлено: %s" % os.path.basename(path))

    def choose_wallpaper(self):
        d = Gtk.FileChooserDialog(title="Выберите фотографию", transient_for=self,
                                  action=Gtk.FileChooserAction.OPEN)
        d.add_buttons("Отмена", Gtk.ResponseType.CANCEL, "Поставить", Gtk.ResponseType.OK)
        f = Gtk.FileFilter()
        f.set_name("Изображения")
        f.add_mime_type("image/*")
        d.add_filter(f)
        if d.run() == Gtk.ResponseType.OK:
            src = d.get_filename()
            os.makedirs(WALL_DIR, exist_ok=True)
            dst = os.path.join(WALL_DIR, os.path.basename(src))
            try:
                import shutil
                shutil.copy2(src, dst)
                self.set_wallpaper(dst)
            except Exception as e:
                ui.dialog(self, "Ошибка", str(e), ok="Закрыть")
        d.destroy()

    def reset_wallpaper(self):
        th = C.read(os.path.expanduser("~/.config/rsaarm/theme")).strip()
        default = "/usr/local/share/rsaarm/wallpaper-%s.png" % ("dark" if th == "dark" else "light")
        if not os.path.exists(default):
            default = os.path.join(WALL_DIR, "armbian-space.png")
        if os.path.exists(default):
            self.set_wallpaper(default)

    def page_power(self):
        p = ui.Page("Питание", "Перезагрузка, выключение и гашение экрана")
        c = p.card("Питание мини-ПК", icon="system-shutdown")
        c.add(ui.row("Перезагрузить", ui.button("Перезагрузить", self.reboot, "btn", "system-reboot"),
                     sub="Мини-ПК выключится и включится сама, настройки сохранятся"))
        c.add(ui.row("Выключить", ui.button("Выключить", self.poweroff, "danger", "system-shutdown"),
                     sub="Полное выключение. Включить — кнопкой на корпусе"))
        c.add(ui.row("Выйти из системы", ui.button("Выйти", self.logout, "ghost", "system-log-out")))
        c.add(ui.row("Заблокировать экран", ui.button("Заблокировать", self.lock, "ghost", "system-lock-screen")))

        c = p.card("Экран", icon="video-display")
        blank = "DPMS is Enabled" in C.out(["xset", "q"], timeout=6)
        c.add(ui.row("Гасить экран при простое", ui.switch(blank, self.set_blank),
                     sub="Стандартно экран гаснет через 10–15 минут бездействия"))
        c.add(ui.row("Погасить прямо сейчас", ui.button("Погасить", lambda: (C.run(["xset", "dpms", "force", "off"]),
                                                                          C.notify("Экран", "Нажмите любую клавишу")),
                                                        "ghost")))
        return p

    def reboot(self):
        if ui.dialog(self, "Перезагрузить мини-ПК?", "Работа будет прервана на ~1 минуту.",
                     ok="Перезагрузить", cancel=True):
            C.sudo(["systemctl", "reboot"])

    def poweroff(self):
        if ui.dialog(self, "Выключить мини-ПК?", "Экран погаснет. Включить — кнопкой на корпусе.",
                     ok="Выключить", cancel=True):
            C.sudo(["systemctl", "poweroff"])

    def logout(self):
        if ui.dialog(self, "Выйти из системы?", "Рабочий стол закроется, вы вернётесь к экрану входа.",
                     ok="Выйти", cancel=True):
            C.run(["xfce4-session-logout", "--logout"], timeout=5)

    def lock(self):
        C.run(["xflock4"], timeout=5)

    def set_blank(self, on):
        if on:
            C.run("xset +dpms; xset dpms 600 0 900", timeout=6)
        else:
            C.run("xset s off -dpms", timeout=6)
        C.notify("Экран", "Гашение экрана %s" % ("включено (10/15 мин)" if on else "выключено"))
        return True


def main():
    ui.load_css(EXTRA_CSS)
    page = None
    for a in os.sys.argv[1:]:
        if a.startswith("--page="):
            page = a.split("=", 1)[1]
    w = Center(page)
    with open(_PID, "w") as f:
        f.write(str(os.getpid()))

    def summon(*a):
        try:
            w.open_page(open(_REQ).read().strip())
        except OSError:
            pass
        w.show_all()
        w.maximize()
        w.present()
        GLib.idle_add(lambda: w.refresh_now() and False)
        try:
            from gi.repository import GdkX11
            w.get_window().focus(GdkX11.x11_get_server_time(w.get_window()))
        except Exception:
            pass
        return True

    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, 10, summon)
    def _css_reload(*a):
        try:
            ui.reload_css()
        except Exception:
            pass
    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, 12, _css_reload)
    if "--prewarm" not in os.sys.argv:
        w.show_all()
        w.maximize()
    Gtk.main()


if __name__ == "__main__":
    main()

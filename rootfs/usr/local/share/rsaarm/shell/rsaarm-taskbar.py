#!/usr/bin/env python3

import json
import locale
import math
import os
import shutil
import subprocess
import threading
import time

import cairo
import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Gdk, GdkPixbuf, GLib, Gtk
try:
    gi.require_version("Wnck", "3.0")
    from gi.repository import Wnck
except (ValueError, ImportError):
    Wnck = None

SHELL = os.path.dirname(os.path.abspath(__file__))
THEME = os.environ.get("RSAARM_THEME", "light")
CENTER = "/usr/local/share/armbian-gui/center.py"
MENU = os.path.join(SHELL, "rsaarm-menu.py")
MENU_TOGGLE = (
    "P=$(cat /tmp/rsaarm-menu-$(id -u).pid 2>/dev/null); "
    "if [ -n \"$P\" ] && [ \"$(cat /proc/$P/comm 2>/dev/null)\" = python3 ]; "
    "then kill -USR1 $P; "
    "else env RSAARM_THEME=%s python3 '%s'; fi"
)
CONF = os.path.expanduser("~/.config/rsaarm")


def _tv_crop_bottom():
    try:
        with open(os.path.expanduser("~/.config/armbian-tv/screen-fit.json")) as f:
            return max(0, min(64, int(json.load(f).get("bottom", 0))))
    except Exception:
        return 0


CROP_B = _tv_crop_bottom()
TB_H = 52 + CROP_B

try:
    locale.setlocale(locale.LC_TIME, "ru_RU.UTF-8")
except Exception:
    pass

PINNED = [
    ("Файлы", "system-file-manager", "thunar", "Thunar"),
    ("Браузер", "chromium", "rsaarm-browser", "chromium"),
    ("Диспетчер задач", "utilities-system-monitor", "kvorix-taskmanager", "taskmanager"),
    ("Хранилище", "drive-harddisk", "kvorix-disks", "kvorix-disks"),
    ("Терминал", "utilities-terminal", "xfce4-terminal", "xfce4-terminal"),
    ("Настройки", "preferences-system", "python3 " + CENTER, "center.py"),
]

RUS_DAYS = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
RUS_MONTHS = ["января", "февраля", "марта", "апреля", "мая", "июня",
              "июля", "августа", "сентября", "октября", "ноября", "декабря"]


def run(cmd, timeout=6):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return (r.stdout or "").strip()
    except Exception:
        return ""


def launch(cmd):
    import shlex
    env = dict(os.environ)
    if not any(ch in cmd for ch in ("|", ";", "&", ">", "<", "$", "`", "\n", "=")):
        argv = shlex.split(cmd)
    else:
        argv = ["sh", "-c", "exec " + cmd if "||" not in cmd and "&&" not in cmd and ";" not in cmd and "|" not in cmd else cmd]
    p = subprocess.Popen(
        argv,
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True, close_fds=True, env=env,
    )
    GLib.timeout_add(300, lambda: p.poll() is None)


def get_theme():
    try:
        with open(os.path.join(CONF, "theme")) as f:
            return f.read().strip() or "light"
    except Exception:
        return "light"


def animations_enabled():
    try:
        with open(os.path.join(CONF, "personalize.json")) as f:
            return bool(json.load(f).get("animations", True))
    except Exception:
        return True


def make_win11_logo_pixbuf(size=26):
    
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, size, size)
    cr = cairo.Context(surf)
    pad = 2.0
    gap = 2.2
    half = (size - 2 * pad - gap) / 2.0
    r = 2.6

    grad = cairo.LinearGradient(0, 0, size, size)
    grad.add_color_stop_rgb(0.0, 0.22, 0.72, 1.00)
    grad.add_color_stop_rgb(0.55, 0.11, 0.50, 0.96)
    grad.add_color_stop_rgb(1.0, 0.02, 0.36, 0.80)

    def rrect(x, y, w, h, rad, tl=True, tr=True, br=True, bl=True):
        cr.new_sub_path()
        if tr:
            cr.arc(x + w - rad, y + rad, rad, -math.pi / 2, 0)
        else:
            cr.move_to(x + w, y)
        if br:
            cr.arc(x + w - rad, y + h - rad, rad, 0, math.pi / 2)
        else:
            cr.line_to(x + w, y + h)
        if bl:
            cr.arc(x + rad, y + h - rad, rad, math.pi / 2, math.pi)
        else:
            cr.line_to(x, y + h)
        if tl:
            cr.arc(x + rad, y + rad, rad, math.pi, 1.5 * math.pi)
        else:
            cr.line_to(x, y)
        cr.close_path()

    rrect(pad, pad, half, half, r, tl=True, tr=False, br=False, bl=False)
    rrect(pad + half + gap, pad, half, half, r, tl=False, tr=True, br=False, bl=False)
    rrect(pad, pad + half + gap, half, half, r, tl=False, tr=False, br=False, bl=True)
    rrect(pad + half + gap, pad + half + gap, half, half, r, tl=False, tr=False, br=True, bl=False)
    cr.set_source(grad)
    cr.fill()
    return Gdk.pixbuf_get_from_surface(surf, 0, 0, size, size)


def apply_xshape_rounded(win, w, h, radius=14):
    
    if w < 16 or h < 16 or not win.get_window():
        return
    surf = cairo.ImageSurface(cairo.FORMAT_A1, w, h)
    cr = cairo.Context(surf)
    cr.set_operator(cairo.OPERATOR_CLEAR)
    cr.paint()
    cr.set_operator(cairo.OPERATOR_OVER)
    cr.set_source_rgba(1, 1, 1, 1)
    r = min(radius, w // 2, h // 2)
    cr.arc(w - r, r, r, -math.pi / 2, 0)
    cr.arc(w - r, h - r, r, 0, math.pi / 2)
    cr.arc(r, h - r, r, math.pi / 2, math.pi)
    cr.arc(r, r, r, math.pi, 1.5 * math.pi)
    cr.close_path()
    cr.fill()
    reg = Gdk.cairo_region_create_from_surface(surf)
    win.get_window().shape_combine_region(reg, 0, 0)


def draw_rounded_border(wid, cr, radius=14):
    
    w = wid.get_allocated_width()
    h = wid.get_allocated_height()
    if w < 16 or h < 16:
        return False
    dark = get_theme() == "dark"
    cr.save()
    cr.new_path()
    cr.set_line_width(1.6)
    if dark:
        cr.set_source_rgba(1.0, 1.0, 1.0, 0.16)
    else:
        cr.set_source_rgba(0.08, 0.12, 0.22, 0.16)
    r = min(radius, w // 2, h // 2) - 0.8
    cr.arc(w - r - 0.8, r + 0.8, r, -math.pi / 2, 0)
    cr.arc(w - r - 0.8, h - r - 0.8, r, 0, math.pi / 2)
    cr.arc(r + 0.8, h - r - 0.8, r, math.pi / 2, math.pi)
    cr.arc(r + 0.8, r + 0.8, r, math.pi, 1.5 * math.pi)
    cr.close_path()
    cr.stroke()
    cr.restore()
    return False


class MiniPop(Gtk.Window):
    
    def __init__(self, content, width, on_open=None):
        super().__init__(type=Gtk.WindowType.TOPLEVEL)
        self.set_type_hint(Gdk.WindowTypeHint.DOCK)
        self.set_decorated(False)
        self.set_skip_taskbar_hint(True)
        self.set_skip_pager_hint(True)
        self.set_resizable(False)
        self.set_keep_above(True)
        self.set_title("rsaarm-pop")
        self.pw = width
        self._on_open = on_open
        self._last_shape = (0, 0)

        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        card.get_style_context().add_class("qs-pop")
        card.pack_start(content, True, True, 0)
        card.connect_after("draw", draw_rounded_border, 14)
        self.add(card)
        self.connect("size-allocate", self._on_alloc)
        self.connect("key-press-event", self.on_key)

    def _on_alloc(self, _w, alloc):
        sz = (alloc.width, alloc.height)
        if sz != self._last_shape:
            self._last_shape = sz
            apply_xshape_rounded(self, alloc.width, alloc.height, 14)

    def on_key(self, _w, ev):
        if ev.keyval == Gdk.KEY_Escape:
            self.hide()
            return True
        return False

    def popup(self, sw, sh, siblings=()):
        if self.get_visible():
            self.hide()
            return
        for s in siblings:
            if s is not self and s.get_visible():
                s.hide()
        if self._on_open:
            try:
                self._on_open()
            except Exception:
                pass
        self.show_all()
        try:
            _mn, nat = self.get_preferred_size()
            w_, h_ = nat.width or self.pw, nat.height or 200
        except Exception:
            w_, h_ = self.pw, 200
        w_ = max(w_, self.pw)
        self.resize(w_, h_)
        apply_xshape_rounded(self, w_, h_, 14)

        tx = max(0, sw - w_ - 10)
        ty = max(0, sh - TB_H - 10 - h_)
        if animations_enabled():
            start_y = ty + 14
            self.move(tx, start_y)
            self.present()
            step = [0]

            def _anim():
                step[0] += 1
                t = min(1.0, step[0] / 6.0)
                ease = 1.0 - (1.0 - t) ** 3
                self.move(tx, int(round(start_y + (ty - start_y) * ease)))
                return t < 1.0

            GLib.timeout_add(16, _anim)
        else:
            self.move(tx, ty)
            self.present()

    def poll_outside(self):
        if not self.get_visible():
            return True
        try:
            sh = Gdk.Screen.get_default().get_height()
            disp = Gdk.Display.get_default()
            ptr = disp.get_default_seat().get_pointer()
            _s, x, y = ptr.get_position()
            ax, ay = self.get_position()
            w_, h_ = self.get_size()
            m = 26
            if y >= sh - TB_H - 6:
                return True
            if x < ax - m or x > ax + w_ + m or y < ay - m or y > ay + h_ + m:
                self.hide()
        except Exception:
            pass
        return True


def _resolve_win_icon(wm_class, name, wnck_win=None):
    low_c = (wm_class or "").lower()
    low_n = (name or "").lower()
    mapping = [
        (("center.py", "armbian-center", "настройки"), "preferences-system"),
        (("taskmanager", "диспетчер задач"), "utilities-system-monitor"),
        (("kvorix-disks", "хранилище и диски"), "drive-harddisk"),
        (("xfce4-terminal", "терминал", "журнал", "агент"), "utilities-terminal"),
        (("thunar", "файлы"), "system-file-manager"),
        (("chromium", "браузер"), "chromium"),
        (("pavucontrol", "громкость", "звук"), "multimedia-volume-control"),
        (("blueman", "bluetooth"), "preferences-system-bluetooth"),
        (("mousepad", "блокнот"), "org.xfce.mousepad"),
        (("ristretto", "фотографии"), "org.xfce.ristretto"),
        (("galculator", "calculator", "калькулятор"), "galculator"),
        (("vlc", "медиаплеер"), "vlc"),
        (("appfinder", "выполнить"), "system-run"),
        (("экран", "screen-fit", "разрешение"), "preferences-desktop-display"),
    ]
    theme = Gtk.IconTheme.get_default()
    for keys, ic in mapping:
        if any(k in low_c or k in low_n for k in keys) and theme.has_icon(ic):
            return ic, None
    if low_c and theme.has_icon(low_c):
        return low_c, None
    if wnck_win is not None:
        try:
            pix = wnck_win.get_icon()
            if pix:
                return None, pix.scale_simple(26, 26, GdkPixbuf.InterpType.BILINEAR)
        except Exception:
            pass
    return "preferences-desktop-applications", None


class TbBtn(Gtk.Button):
    
    def __init__(self, title, icon_name, cmd, match, pixbuf=None):
        super().__init__()
        self.title, self.cmd, self.match = title, cmd, match
        self.xid = None
        self.minimized = False
        vb = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        vb.set_valign(Gtk.Align.CENTER)
        if pixbuf is not None:
            self.img = Gtk.Image.new_from_pixbuf(pixbuf)
        else:
            ic = icon_name if Gtk.IconTheme.get_default().has_icon(icon_name) else "application-x-executable"
            self.img = Gtk.Image.new_from_icon_name(ic, Gtk.IconSize.LARGE_TOOLBAR)
            self.img.set_pixel_size(26)
        vb.pack_start(self.img, False, False, 0)
        self.ind = Gtk.Box()
        self.ind.set_halign(Gtk.Align.CENTER)
        self.ind.get_style_context().add_class("tb-ind")
        vb.pack_start(self.ind, False, False, 0)
        self.add(vb)
        self.get_style_context().add_class("tb-btn")
        self.set_tooltip_text(title)
        self.connect("clicked", self.on_click)
        self.connect("button-press-event", self.on_right)

    def on_click(self, *_a):
        if self.xid:
            def _focus():
                act = run("xprop -root _NET_ACTIVE_WINDOW | grep -oE '0x[0-9a-f]+' | head -1")
                if act == self.xid:
                    run("xdotool windowminimize %d" % int(self.xid, 16))
                else:
                    run("xdotool windowactivate %d" % int(self.xid, 16))
            threading.Thread(target=_focus, daemon=True).start()
        elif self.cmd:
            launch(self.cmd)

    def on_right(self, _w, ev):
        if ev.button == 3:
            m = Gtk.Menu()
            if self.cmd:
                i1 = Gtk.MenuItem(label="Открыть новое окно")
                i1.connect("activate", lambda *_: launch(self.cmd))
                m.append(i1)
            if self.xid:
                dec_id = str(int(self.xid, 16))
                for lbl, d in (
                    ("Прикрепить к левой половине", "left"),
                    ("Прикрепить к правой половине", "right"),
                    ("Развернуть на весь экран", "up"),
                ):
                    it = Gtk.MenuItem(label=lbl)
                    it.connect("activate", lambda *_a, dr=d, wid=dec_id: launch(f"rsaarm-snap {dr} {wid}"))
                    m.append(it)
                m.append(Gtk.SeparatorMenuItem())
                ic = Gtk.MenuItem(label="Закрыть окно")
                ic.connect("activate", lambda *_a, x=self.xid: run(f"wmctrl -ic {x}"))
                m.append(ic)
            m.show_all()
            m.popup_at_pointer(ev)
            return True
        return False

    def update_state(self, xid, minimized, active):
        self.xid = xid
        self.minimized = bool(minimized)
        st = self.get_style_context()
        if xid:
            st.add_class("running")
            if active:
                st.add_class("active-app")
            else:
                st.remove_class("active-app")
            if minimized:
                st.add_class("minimized")
            else:
                st.remove_class("minimized")
        else:
            for c in ("running", "active-app", "minimized"):
                st.remove_class(c)


class DynBtn(TbBtn):
    def __init__(self, wm_class, name, xid, wnck_win=None):
        ic, pix = _resolve_win_icon(wm_class, name, wnck_win)
        super().__init__(name or wm_class, ic or "utilities-terminal", "", wm_class, pixbuf=pix)
        self.update_state(xid, False, False)


class Taskbar(Gtk.Window):
    def __init__(self):
        super().__init__(type=Gtk.WindowType.TOPLEVEL)
        self.set_type_hint(Gdk.WindowTypeHint.DOCK)
        self.set_decorated(False)
        self.set_skip_taskbar_hint(True)
        self.set_skip_pager_hint(True)
        self.stick()
        self.set_resizable(False)
        self.set_title("rsaarm-taskbar")

        screen = Gdk.Screen.get_default()
        self.sw, self.sh = screen.get_width(), screen.get_height()
        self.set_default_size(self.sw, TB_H)
        self.set_size_request(self.sw, TB_H)
        self.move(0, self.sh - TB_H)

        scr = self.get_screen()
        vis = scr.get_rgba_visual()
        if vis:
            self.set_visual(vis)
        self._css_pr = self._css()
        Gtk.StyleContext.add_provider_for_screen(
            scr, self._css_pr, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        evbox = Gtk.EventBox()
        evbox.set_visible_window(False)
        evbox.connect("button-press-event", self._on_bar_context)
        self.add(evbox)

        root = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        root.get_style_context().add_class("rsaarm-taskbar")
        root.set_margin_bottom(CROP_B)
        evbox.add(root)

        self.center = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        root.pack_start(Gtk.Box(), True, True, 0)
        root.pack_start(self.center, False, False, 0)
        root.pack_start(Gtk.Box(), True, True, 0)

        st = Gtk.Button()
        vb = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        vb.set_valign(Gtk.Align.CENTER)
        logo = Gtk.Image.new_from_pixbuf(make_win11_logo_pixbuf(26))
        vb.pack_start(logo, False, False, 0)
        ind = Gtk.Box()
        ind.get_style_context().add_class("tb-ind")
        vb.pack_start(ind, False, False, 0)
        st.add(vb)
        st.get_style_context().add_class("tb-btn")
        st.get_style_context().add_class("tb-start")
        st.set_tooltip_text("Пуск (Win)")
        st.connect("clicked", lambda *_: launch(MENU_TOGGLE % (get_theme(), MENU)))
        self.center.pack_start(st, False, False, 0)

        self.pin_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        self.center.pack_start(self.pin_box, False, False, 0)
        self.pin_btns = []
        for title, icon, cmd, match in PINNED:
            b = TbBtn(title, icon, cmd, match)
            self.pin_btns.append(b)
            self.pin_box.pack_start(b, False, False, 0)
        self.dyn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        self.center.pack_start(self.dyn_box, False, False, 0)

        right = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
        root.pack_end(right, False, False, 0)

        self.lang_btn = Gtk.Button()
        self.lang_lbl = Gtk.Label(label="ENG")
        self.lang_btn.add(self.lang_lbl)
        self.lang_btn.set_size_request(38, -1)
        self.lang_btn.get_style_context().add_class("tb-btn")
        self.lang_btn.get_style_context().add_class("tb-lang")
        self.lang_btn.set_tooltip_text("Язык ввода — нажмите для переключения (Alt+Shift)")
        self.lang_btn.connect("clicked", self._toggle_kbd_layout)
        right.pack_start(self.lang_btn, False, False, 0)

        self.tray = Gtk.Button()
        self.tray.set_size_request(56, -1)
        tray_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=7)
        tray_box.set_halign(Gtk.Align.CENTER)
        self.ic_net = Gtk.Image.new_from_icon_name("network-wireless-signal-excellent-symbolic", Gtk.IconSize.MENU)
        self.ic_vol = Gtk.Image.new_from_icon_name("audio-volume-high-symbolic", Gtk.IconSize.MENU)
        tray_box.pack_start(self.ic_net, False, False, 0)
        tray_box.pack_start(self.ic_vol, False, False, 0)
        self.tray.add(tray_box)
        self.tray.get_style_context().add_class("tb-btn")
        self.tray.get_style_context().add_class("tb-tray")
        self.tray.set_tooltip_text("Быстрые настройки: сеть, звук, экран")
        right.pack_start(self.tray, False, False, 0)

        self.clock = Gtk.Button()
        self.clock.set_size_request(68, -1)
        self.clock_lbl = Gtk.Label()
        self.clock_lbl.set_justify(Gtk.Justification.RIGHT)
        self.clock.add(self.clock_lbl)
        self.clock.get_style_context().add_class("tb-btn")
        self.clock.get_style_context().add_class("tb-clock")
        self.clock.set_tooltip_text("Календарь и сводка системы")
        right.pack_start(self.clock, False, False, 0)

        pw = Gtk.Button()
        pw.set_size_request(36, -1)
        pw.add(Gtk.Image.new_from_icon_name("system-shutdown-symbolic", Gtk.IconSize.MENU))
        pw.get_style_context().add_class("tb-btn")
        pw.get_style_context().add_class("tb-pw")
        pw.set_tooltip_text("Питание")
        right.pack_start(pw, False, False, 0)

        sdesk = Gtk.Button()
        sdesk.set_size_request(5, -1)
        sdesk.get_style_context().add_class("tb-showdesk")
        sdesk.set_tooltip_text("Свернуть все окна (Win+D)")
        sdesk.connect("clicked", lambda *_: launch("rsaarm-showdesk"))
        right.pack_start(sdesk, False, False, 0)

        self._vol_suppress = False
        self._tg_suppress = False
        self.qs = MiniPop(self.build_quick(), 356, on_open=self._refresh_qs_live)
        self.cal = MiniPop(self.build_calendar(), 336, on_open=self._refresh_cal_live)
        self.pwpop = MiniPop(self.build_power(), 248)
        pops = (self.qs, self.cal, self.pwpop)

        self.tray.connect("clicked", lambda *_: self.qs.popup(self.sw, self.sh, pops))
        self.clock.connect("clicked", lambda *_: self.cal.popup(self.sw, self.sh, pops))
        pw.connect("clicked", lambda *_: self.pwpop.popup(self.sw, self.sh, pops))

        _menv = dict(os.environ, RSAARM_THEME=get_theme())
        _mp = subprocess.Popen(
            ["python3", MENU, "--prewarm"],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True, close_fds=True, env=_menv,
        )
        GLib.timeout_add(300, lambda: _mp.poll() is None)

        self._wnck_map = {}
        self._wnck_pending = False
        if Wnck:
            wscr = Wnck.Screen.get_default()
            for sig in ("window-opened", "window-closed", "active-window-changed"):
                wscr.connect(sig, self._wnck_changed)
            wscr.connect("window-opened", lambda _s, w: self._wnck_watch(w))
            wscr.force_update()
            for w in wscr.get_windows():
                self._wnck_watch(w)
            self._wnck_changed()

        threading.Thread(target=self.bg_worker, daemon=True).start()
        for pop in pops:
            GLib.timeout_add(350, pop.poll_outside)

    def _on_bar_context(self, _w, ev):
        if ev.button == 3:
            m = Gtk.Menu()
            for lbl, cmd in (
                ("Диспетчер задач", "kvorix-taskmanager"),
                ("Хранилище и диски", "kvorix-disks"),
                ("Снимок экрана (Ножницы)", "kvorix-snip"),
                ("Параметры панели и темы", f"python3 {CENTER} --page=appearance"),
            ):
                it = Gtk.MenuItem(label=lbl)
                it.connect("activate", lambda *_a, c=cmd: launch(c))
                m.append(it)
            m.show_all()
            m.popup_at_pointer(ev)
            return True
        return False

    def _toggle_kbd_layout(self, *_):
        cur = self.lang_lbl.get_text()
        opt = run("setxkbmap -query | awk '/^options/{print $2}'") or "grp:alt_shift_toggle"
        if cur == "РУС":
            run(f"setxkbmap -layout us,ru -option '' -option {opt}")
            self.lang_lbl.set_text("ENG")
        else:
            run(f"setxkbmap -layout ru,us -option '' -option {opt}")
            self.lang_lbl.set_text("РУС")

    def _read_kbd_label(self):
        lay = run("setxkbmap -query | awk '/^layout/{print $2}'").split(",")
        led = run("xset -q | awk '/LED mask/{print $NF}'")
        grp = 0
        try:
            if int(led, 16) & 0x1000:
                grp = 1
        except Exception:
            pass
        active = lay[grp] if grp < len(lay) else (lay[0] if lay else "us")
        return "РУС" if active.startswith("ru") else "ENG"

    def build_power(self):
        pwbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        pwbox.set_margin_start(10); pwbox.set_margin_end(10)
        pwbox.set_margin_top(10); pwbox.set_margin_bottom(10)
        for title, icon, cmd in (
            ("Заблокировать экран", "system-lock-screen", "dm-tool lock"),
            ("Погасить монитор", "video-display-symbolic", "xset dpms force off"),
            ("Перезагрузка", "system-reboot", "sudo systemctl reboot"),
            ("Выключение", "system-shutdown", "sudo systemctl poweroff"),
        ):
            b = Gtk.Button()
            bb = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=9)
            bb.pack_start(Gtk.Image.new_from_icon_name(icon, Gtk.IconSize.MENU), False, False, 0)
            bb.pack_start(Gtk.Label(label=title), False, False, 0)
            b.add(bb)
            b.get_style_context().add_class("pop-btn")
            b.connect("clicked", lambda *_a, c=cmd: (self.pwpop.hide(), launch(c)))
            pwbox.pack_start(b, False, False, 0)
        return pwbox

    def build_quick(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.get_style_context().add_class("qs")
        box.set_margin_start(14); box.set_margin_end(14)
        box.set_margin_top(14); box.set_margin_bottom(12)

        self.qs_grid = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.pack_start(self.qs_grid, False, False, 0)

        r1 = Gtk.Box(spacing=8); r1.set_homogeneous(True)
        self.btn_wifi, self.lbl_wifi_tile = self.qs_tile("Wi-Fi", "network-wireless-symbolic", self.tg_wifi)
        self.btn_bt, self.lbl_bt_tile = self.qs_tile("Bluetooth", "bluetooth-symbolic", self.tg_bt)
        r1.pack_start(self.btn_wifi, True, True, 0)
        r1.pack_start(self.btn_bt, True, True, 0)
        self.qs_grid.pack_start(r1, False, False, 0)

        r2 = Gtk.Box(spacing=8); r2.set_homogeneous(True)
        self.btn_dark, _ = self.qs_tile("Тёмная тема", "weather-clear-night-symbolic", self.tg_dark)
        self.btn_night, _ = self.qs_tile("Ночной свет", "preferences-color-symbolic", self.tg_night)
        r2.pack_start(self.btn_dark, True, True, 0)
        r2.pack_start(self.btn_night, True, True, 0)
        self.qs_grid.pack_start(r2, False, False, 0)

        r3 = Gtk.Box(spacing=8); r3.set_homogeneous(True)
        self.btn_perf, _ = self.qs_tile("Макс. скорость", "utilities-system-monitor-symbolic", self.tg_perf)
        snip_b = Gtk.Button()
        svb = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        simg = Gtk.Image.new_from_icon_name("applets-screenshooter-symbolic", Gtk.IconSize.MENU)
        if not Gtk.IconTheme.get_default().has_icon("applets-screenshooter-symbolic"):
            simg = Gtk.Image.new_from_icon_name("camera-photo-symbolic", Gtk.IconSize.MENU)
        simg.set_pixel_size(18)
        svb.pack_start(simg, False, False, 0)
        slb = Gtk.Label(label="Снимок экрана"); slb.get_style_context().add_class("qs-tile-label")
        svb.pack_start(slb, False, False, 0)
        snip_b.add(svb)
        snip_b.get_style_context().add_class("qs-tile")
        snip_b.set_size_request(152, 54)
        snip_b.connect("clicked", lambda *_: (self.qs.hide(), launch("kvorix-snip")))
        r3.pack_start(self.btn_perf, True, True, 0)
        r3.pack_start(snip_b, True, True, 0)
        self.qs_grid.pack_start(r3, False, False, 0)

        net_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        net_bar.get_style_context().add_class("qs-info")
        self.lbl_net_status = Gtk.Label(label="Сеть: проверка…", xalign=0)
        self.lbl_net_status.get_style_context().add_class("qs-cap")
        net_bar.pack_start(self.lbl_net_status, True, True, 0)
        net_go = Gtk.Button(label="Сеть ›")
        net_go.get_style_context().add_class("sm-link")
        net_go.connect("clicked", lambda *_: (self.qs.hide(), launch(f"python3 {CENTER} --page=network")))
        net_bar.pack_start(net_go, False, False, 0)
        box.pack_start(net_bar, False, False, 0)

        vb = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        vhdr = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        lbl = Gtk.Label(label="Громкость", xalign=0); lbl.get_style_context().add_class("qs-cap")
        vhdr.pack_start(lbl, True, True, 0)
        self.lbl_vol_pct = Gtk.Label(label="— %")
        self.lbl_vol_pct.get_style_context().add_class("qs-cap")
        vhdr.pack_start(self.lbl_vol_pct, False, False, 6)
        snd_go = Gtk.Button(label="Звук ›")
        snd_go.get_style_context().add_class("sm-link")
        snd_go.connect("clicked", lambda *_: (self.qs.hide(), launch(f"python3 {CENTER} --page=sound")))
        vhdr.pack_start(snd_go, False, False, 0)
        vb.pack_start(vhdr, False, False, 0)

        vrow = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.mute_btn = Gtk.ToggleButton()
        self.mute_ic = Gtk.Image.new_from_icon_name("audio-volume-high-symbolic", Gtk.IconSize.MENU)
        self.mute_btn.add(self.mute_ic)
        self.mute_btn.get_style_context().add_class("pop-btn")
        self.mute_btn.set_tooltip_text("Без звука")
        self.mute_btn.connect("toggled", self.on_mute)
        vrow.pack_start(self.mute_btn, False, False, 0)

        self.vol_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 1)
        self.vol_scale.set_draw_value(False)
        self.vol_scale.connect("value-changed", self.on_vol)
        vrow.pack_start(self.vol_scale, True, True, 0)
        vb.pack_start(vrow, False, False, 0)
        box.pack_start(vb, False, False, 0)

        foot = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        foot.get_style_context().add_class("qs-foot")
        self.lbl_qs_hw = Gtk.Label(label="ЦП — · ОЗУ — · — °C", xalign=0)
        self.lbl_qs_hw.get_style_context().add_class("qs-cap")
        foot.pack_start(self.lbl_qs_hw, True, True, 0)

        tm_b = Gtk.Button(label="Задачи")
        tm_b.get_style_context().add_class("pop-btn")
        tm_b.set_tooltip_text("Открыть Диспетчер задач")
        tm_b.connect("clicked", lambda *_: (self.qs.hide(), launch("kvorix-taskmanager")))
        foot.pack_start(tm_b, False, False, 0)

        b = Gtk.Button(label="⚙ Параметры")
        b.get_style_context().add_class("pop-btn")
        b.connect("clicked", lambda *_: (self.qs.hide(), launch("python3 " + CENTER)))
        foot.pack_start(b, False, False, 0)
        box.pack_start(foot, False, False, 0)
        return box

    def qs_tile(self, title, icon, cb):
        b = Gtk.ToggleButton()
        vb = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        vb.set_valign(Gtk.Align.CENTER)
        img = Gtk.Image.new_from_icon_name(icon, Gtk.IconSize.MENU)
        img.set_pixel_size(18)
        vb.pack_start(img, False, False, 0)
        lbl = Gtk.Label(label=title)
        lbl.get_style_context().add_class("qs-tile-label")
        vb.pack_start(lbl, False, False, 0)
        b.add(vb)
        b.get_style_context().add_class("qs-tile")
        b.set_size_request(152, 54)
        b.connect("toggled", lambda bt: cb(bt.get_active()))
        return b, lbl

    def _refresh_qs_live(self):
        try:
            with open("/sys/class/thermal/thermal_zone0/temp") as f:
                tc = int(f.read().strip()) // 1000
        except Exception:
            tc = 0
        mem_used = mem_tot = 0
        try:
            info = {}
            with open("/proc/meminfo") as f:
                for line in f:
                    k, v = line.split(":", 1)
                    info[k] = int(v.split()[0])
            mem_tot = info["MemTotal"] // 1024
            mem_used = mem_tot - info.get("MemAvailable", 0) // 1024
        except Exception:
            pass
        self.lbl_qs_hw.set_text(f"ОЗУ {mem_used}/{mem_tot} МБ · {tc} °C")

        gov = "schedutil"
        try:
            with open("/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor") as f:
                gov = f.read().strip()
        except Exception:
            pass
        nl = False
        try:
            with open(os.path.join(CONF, "personalize.json")) as f:
                nl = bool(json.load(f).get("nightlight", False))
        except Exception:
            pass
        self._tg_suppress = True
        self.btn_perf.set_active(gov == "performance")
        self.btn_night.set_active(nl)
        self.btn_dark.set_active(get_theme() == "dark")
        self._tg_suppress = False

    def tg_wifi(self, on):
        if self._tg_suppress:
            return
        run("nmcli radio wifi %s" % ("on" if on else "off"))
        run("notify-send -t 2000 'Kvorix' 'Wi-Fi: %s'" % ("включён" if on else "выключен"))

    def tg_bt(self, on):
        if self._tg_suppress:
            return
        run("bluetoothctl power %s" % ("on" if on else "off"))
        run("notify-send -t 2000 'Kvorix' 'Bluetooth: %s'" % ("включён" if on else "выключен"))

    def tg_dark(self, on):
        if self._tg_suppress:
            return
        launch("armbian-personalize set mode %s" % ("dark" if on else "light"))

    def tg_night(self, on):
        if self._tg_suppress:
            return
        launch("armbian-personalize set nightlight %s" % ("true" if on else "false"))

    def tg_perf(self, on):
        if self._tg_suppress:
            return
        gov = "performance" if on else "schedutil"
        launch(f"sudo -n sh -c 'for c in /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor; do echo {gov} > $c; done'")
        run("notify-send -t 2000 'Быстродействие' 'Режим ЦП: %s'" % ("Максимальная скорость" if on else "Сбалансированный"))

    def on_vol(self, scale):
        if self._vol_suppress:
            return
        v = int(scale.get_value())
        self.lbl_vol_pct.set_text("%d %%" % v)
        threading.Thread(
            target=lambda: run("pactl set-sink-volume @DEFAULT_SINK@ %d%%" % v),
            daemon=True,
        ).start()

    def on_mute(self, btn):
        if self._vol_suppress:
            return
        muted = btn.get_active()
        self.mute_ic.set_from_icon_name(
            "audio-volume-muted-symbolic" if muted else "audio-volume-high-symbolic",
            Gtk.IconSize.MENU,
        )
        run("pactl set-sink-mute @DEFAULT_SINK@ %s" % ("1" if muted else "0"))

    def build_calendar(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.get_style_context().add_class("qs")
        box.set_margin_start(14); box.set_margin_end(14)
        box.set_margin_top(14); box.set_margin_bottom(12)

        hero = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        vdt = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self.lbl_cal_time = Gtk.Label(label=time.strftime("%H:%M:%S"), xalign=0)
        self.lbl_cal_time.get_style_context().add_class("cal-hero-time")
        self.lbl_cal_date = Gtk.Label(label="", xalign=0)
        self.lbl_cal_date.get_style_context().add_class("cal-hero-date")
        vdt.pack_start(self.lbl_cal_time, False, False, 0)
        vdt.pack_start(self.lbl_cal_date, False, False, 0)
        hero.pack_start(vdt, True, True, 0)

        today_b = Gtk.Button(label="Сегодня")
        today_b.get_style_context().add_class("sm-link")
        today_b.set_valign(Gtk.Align.START)
        today_b.connect("clicked", lambda *_: self._jump_today())
        hero.pack_start(today_b, False, False, 0)
        box.pack_start(hero, False, False, 0)

        self.cal_widget = Gtk.Calendar()
        self.cal_widget.get_style_context().add_class("rsaarm-cal")
        box.pack_start(self.cal_widget, False, False, 0)

        info_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        info_card.get_style_context().add_class("qs-info")
        self.lbl_cal_sys = Gtk.Label(label="Свободно на диске: —", xalign=0)
        self.lbl_cal_sys.get_style_context().add_class("qs-cap")
        info_card.pack_start(self.lbl_cal_sys, False, False, 0)
        box.pack_start(info_card, False, False, 0)

        b = Gtk.Button(label="Дата, время и язык — параметры")
        b.get_style_context().add_class("pop-btn")
        b.connect("clicked", lambda *_: (self.cal.hide(), launch(f"python3 {CENTER} --page=timelang")))
        box.pack_start(b, False, False, 0)
        return box

    def _jump_today(self):
        lt = time.localtime()
        self.cal_widget.select_month(lt.tm_mon - 1, lt.tm_year)
        self.cal_widget.select_day(lt.tm_mday)

    def _refresh_cal_live(self):
        lt = time.localtime()
        self.lbl_cal_time.set_text(time.strftime("%H:%M", lt))
        self.lbl_cal_date.set_text(f"{RUS_DAYS[lt.tm_wday]}, {lt.tm_mday} {RUS_MONTHS[lt.tm_mon - 1]} {lt.tm_year} г.")
        self._jump_today()
        try:
            du = shutil.disk_usage("/")
            up_min = int(float(open("/proc/uptime").read().split()[0]) // 60)
            up_str = f"{up_min // 60} ч {up_min % 60} мин" if up_min >= 60 else f"{up_min} мин"
            self.lbl_cal_sys.set_text(
                f"В работе: {up_str}  ·  Свободно: {du.free / (1024**3):.1f} ГБ"
            )
        except Exception:
            pass

    def collect_windows(self):
        out = run("xprop -root _NET_CLIENT_LIST")
        ids = [t for t in out.replace(",", " ").split() if t.startswith("0x")]
        act = run("xprop -root _NET_ACTIVE_WINDOW | grep -oE '0x[0-9a-f]+' | head -1")
        wins = []
        for xid in ids:
            info = run("xprop -id %s WM_CLASS _NET_WM_NAME _NET_WM_STATE" % xid)
            if not info:
                continue
            wm_class, name, minimized = "", "", False
            for line in info.splitlines():
                if line.startswith("WM_CLASS"):
                    try:
                        wm_class = line.split('"')[1]
                    except Exception:
                        pass
                elif line.startswith("_NET_WM_NAME"):
                    try:
                        name = line.split('"')[1]
                    except Exception:
                        pass
                elif "_NET_WM_STATE_HIDDEN" in line:
                    minimized = True
            skip_cls = ("xfdesktop", "Live_panel.py", "live_panel.py", "Toolkit", "firefox-esr")
            if wm_class and "rsaarm" not in wm_class.lower() and wm_class not in skip_cls:
                wins.append((xid, wm_class, name, minimized))
        return wins, act

    def apply_windows(self, wins, act):
        try:
            pinned_x = set()
            for b in self.pin_btns:
                xid = mini = None
                for (x, cls, name, m) in wins:
                    low_c, low_n, low_m = cls.lower(), (name or "").lower(), b.match.lower()
                    if low_m in low_c or (low_n and low_m in low_n):
                        xid, mini = x, m
                        break
                if xid:
                    pinned_x.add(xid)
                b.update_state(xid, mini, act == xid)
            dyn_wins = [w for w in wins if w[0] not in pinned_x]
            key = ",".join(f"{w[0]}:{w[3]}:{act == w[0]}" for w in dyn_wins)
            if key != getattr(self, "_dyn_key", None):
                self._dyn_key = key
                for ch in self.dyn_box.get_children():
                    self.dyn_box.remove(ch)
                for (x, cls, name, m) in dyn_wins:
                    b = DynBtn(cls, name, x, self._wnck_map.get(x))
                    b.update_state(x, m, act == x)
                    self.dyn_box.pack_start(b, False, False, 0)
                self.dyn_box.show_all()
        except Exception:
            pass
        return False

    def collect_state(self):
        st = {}
        v = run("pactl get-sink-volume @DEFAULT_SINK@")
        vol = 0
        for tok in v.split():
            if tok.endswith("%"):
                try:
                    vol = int(tok[:-1])
                    break
                except ValueError:
                    pass
        st["vol"] = min(100, vol)
        st["muted"] = "yes" in run("pactl get-sink-mute @DEFAULT_SINK@").lower()
        st["wifi"] = "enabled" in run("nmcli radio wifi").lower()
        st["bt"] = "powered: yes" in run("bluetoothctl show").lower()
        con_line = run("nmcli -t -f TYPE,NAME,DEVICE connection show --active | head -2")
        ip_addr = run("ip -4 -o addr show scope global | awk '!/100\\./{print $4; exit}' | cut -d/ -f1")
        st["net_line"] = con_line
        st["ip"] = ip_addr
        st["dark"] = get_theme() == "dark"
        st["lang"] = self._read_kbd_label()
        return st

    def apply_state(self, st):
        try:
            self.clock_lbl.set_markup(
                "%s\n<span size=\"8500\" alpha=\"72%%\">%s</span>" % (
                    time.strftime("%H:%M"), time.strftime("%d.%m.%Y"))
            )
            self.lang_lbl.set_text(st.get("lang", "ENG"))
            vol, muted = st["vol"], st["muted"]
            self._vol_suppress = True
            self.vol_scale.set_value(vol)
            self.lbl_vol_pct.set_text("%d %%" % vol)
            self.mute_btn.set_active(muted)
            self.mute_ic.set_from_icon_name(
                "audio-volume-muted-symbolic" if muted else "audio-volume-high-symbolic",
                Gtk.IconSize.MENU,
            )
            self._vol_suppress = False

            if muted:
                ic = "audio-volume-muted-symbolic"
            elif vol > 60:
                ic = "audio-volume-high-symbolic"
            elif vol > 25:
                ic = "audio-volume-medium-symbolic"
            else:
                ic = "audio-volume-low-symbolic"
            self.ic_vol.set_from_icon_name(ic, Gtk.IconSize.MENU)

            nl = st.get("net_line", "")
            ip = st.get("ip", "")
            if "ethernet" in nl:
                nic = "network-wired-symbolic"
                ssid = nl.split(":")[1] if ":" in nl else "Проводная сеть"
                self.lbl_net_status.set_text(f"Проводная сеть ({ssid})" + (f" · {ip}" if ip else ""))
            elif "wireless" in nl or "wifi" in nl:
                nic = "network-wireless-signal-excellent-symbolic"
                ssid = nl.split(":")[1] if ":" in nl else "Wi-Fi"
                self.lbl_wifi_tile.set_text(ssid[:14] if ssid else "Wi-Fi")
                self.lbl_net_status.set_text(f"Wi-Fi: {ssid}" + (f" · {ip}" if ip else ""))
            else:
                nic = "network-wireless-offline-symbolic"
                self.lbl_wifi_tile.set_text("Wi-Fi")
                self.lbl_net_status.set_text("Нет активного подключения")
            self.ic_net.set_from_icon_name(nic, Gtk.IconSize.MENU)

            self._tg_suppress = True
            self.btn_wifi.set_active(st["wifi"])
            self.btn_bt.set_active(st["bt"])
            self.btn_dark.set_active(st["dark"])
            self._tg_suppress = False
        except Exception:
            pass
        return False

    def _wnck_watch(self, w):
        w.connect("state-changed", self._wnck_changed)
        w.connect("name-changed", self._wnck_changed)

    def _wnck_changed(self, *_a):
        if not self._wnck_pending:
            self._wnck_pending = True
            GLib.timeout_add(60, self._wnck_apply)

    def _wnck_apply(self):
        self._wnck_pending = False
        scr = Wnck.Screen.get_default()
        act = scr.get_active_window()
        act_xid = "0x%x" % act.get_xid() if act else ""
        skip = ("xfdesktop", "Live_panel.py", "live_panel.py", "Toolkit", "firefox-esr")
        wins = []
        wmap = {}
        for w in scr.get_windows():
            if w.is_skip_tasklist() or w.get_window_type() in (Wnck.WindowType.DESKTOP, Wnck.WindowType.DOCK):
                continue
            cls = w.get_class_instance_name() or w.get_class_group_name() or ""
            if cls and "rsaarm" not in cls.lower() and cls not in skip:
                hx = "0x%x" % w.get_xid()
                wmap[hx] = w
                wins.append((hx, cls, w.get_name() or "", w.is_minimized()))
        self._wnck_map = wmap
        self.apply_windows(wins, act_xid)
        return False

    def bg_worker(self):
        last_w = last_s = None
        n = 0
        while True:
            if not Wnck:
                try:
                    w = self.collect_windows()
                    if w != last_w:
                        last_w = w
                        GLib.idle_add(self.apply_windows, *w)
                except Exception:
                    pass
            if n % 2 == 0:
                try:
                    st = self.collect_state()
                    st["clock"] = time.strftime("%H:%M %d.%m.%Y")
                    if st != last_s:
                        last_s = st
                        GLib.idle_add(self.apply_state, st)
                except Exception:
                    pass
            n += 1
            time.sleep(1.5)

    def _css(self):
        pr = Gtk.CssProvider()
        _u = os.path.expanduser("~/.config/rsaarm/shell.css")
        pr.load_from_path(_u if os.path.exists(_u) else os.path.join(SHELL, "rsaarm-dark.css" if THEME == "dark" else "rsaarm.css"))
        return pr

    def _reload_css(self):
        _u = os.path.expanduser("~/.config/rsaarm/shell.css")
        try:
            self._css_pr.load_from_path(_u if os.path.exists(_u) else os.path.join(SHELL, "rsaarm-dark.css" if THEME == "dark" else "rsaarm.css"))
            self.queue_draw()
            for pop in (self.qs, self.cal, self.pwpop):
                pop.queue_draw()
        except Exception:
            pass
        return False


def main():
    import signal
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    signal.signal(signal.SIGUSR1, signal.SIG_IGN)
    GLib.set_prgname("rsaarm-taskbar")
    _tb = {"w": None}

    def _usr1(*_a):
        if _tb["w"] is not None:
            GLib.idle_add(_tb["w"]._reload_css)

    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGUSR1, lambda: (_tb["w"]._reload_css() if _tb["w"] else None, True)[1])
    Gtk.init(None)
    w = Taskbar()
    _tb["w"] = w
    w.show_all()

    def _set_strut():
        try:
            xid = w.get_window().get_xid()
            h = w.get_allocated_height()
            sw = w.get_screen().get_width()
            p = subprocess.Popen(
                ["xprop", "-id", str(xid),
                 "-f", "_NET_WM_STRUT_PARTIAL", "32c",
                 "-set", "_NET_WM_STRUT_PARTIAL",
                 "0, 0, 0, %d, 0, 0, 0, 0, 0, 0, 0, %d" % (h, sw - 1)],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True,
            )
            GLib.timeout_add(200, lambda: p.poll() is None)
        except Exception:
            pass
        return False

    GLib.timeout_add(800, _set_strut)
    Gtk.main()


if __name__ == "__main__":
    main()

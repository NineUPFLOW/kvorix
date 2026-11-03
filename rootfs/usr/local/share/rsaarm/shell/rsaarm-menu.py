#!/usr/bin/env python3

import glob
import json
import math
import os
import subprocess
import time

import cairo
import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, GLib, Gtk, Pango

SHELL = os.path.dirname(os.path.abspath(__file__))
THEME = os.environ.get("RSAARM_THEME", "light")
W, H = 656, 652
CONF = os.path.expanduser("~/.config/rsaarm")


def _tv_crop_bottom():
    try:
        with open(os.path.expanduser("~/.config/armbian-tv/screen-fit.json")) as f:
            return max(0, min(64, int(json.load(f).get("bottom", 0))))
    except Exception:
        return 0


CROP_B = _tv_crop_bottom()
TB_H = 52 + CROP_B

PINNED = [
    ("Браузер", "chromium", "rsaarm-browser"),
    ("Файлы", "system-file-manager", "thunar"),
    ("Настройки", "preferences-system", "python3 /usr/local/share/armbian-gui/center.py"),
    ("Диспетчер задач", "utilities-system-monitor", "kvorix-taskmanager"),
    ("Хранилище", "drive-harddisk", "kvorix-disks"),
    ("Фотографии", "org.xfce.ristretto", "ristretto"),
    ("Видео", "vlc", "vlc"),
    ("Блокнот", "org.xfce.mousepad", "mousepad"),
    ("Калькулятор", "galculator", "galculator"),
    ("Терминал", "utilities-terminal", "xfce4-terminal"),
    ("Звук", "multimedia-volume-control", "pavucontrol"),
    ("Выполнить", "system-run", "xfce4-appfinder -c"),
]

QUICK_RECS = [
    {"title": "Папка «Загрузки»", "sub": "Скачанные из интернета файлы", "icon": "folder-download", "cmd": "thunar ~/Загрузки"},
    {"title": "Снимок экрана (Ножницы)", "sub": "Сохранить экран в буфер и PNG", "icon": "applets-screenshooter", "cmd": "kvorix-snip"},
    {"title": "Автозагрузка программ", "sub": "Управление стартом сеанса", "icon": "preferences-system-session", "cmd": "armbian-center --page=autostart"},
    {"title": "Экран на телефоне (QR)", "sub": "Беспроводной доступ в домашней сети", "icon": "phone", "cmd": "armbian-center --page=devices"},
]

CATS = [
    ("Все", None), ("Интернет", "Интернет"), ("Мультимедиа", "Мультимедиа"),
    ("Графика", "Графика"), ("Система", "Система"),
    ("Настройки", "Настройки"), ("Утилиты", "Утилиты"),
]

CATMAP = {
    "Network": "Интернет", "WebBrowser": "Интернет",
    "AudioVideo": "Мультимедиа", "Audio": "Мультимедиа", "Video": "Мультимедиа",
    "Graphics": "Графика",
    "System": "Система", "FileManager": "Система",
    "Settings": "Настройки", "DesktopSettings": "Настройки", "XFCE": "Настройки",
    "Utility": "Утилиты", "Development": "Утилиты",
}

APP_ALIASES = {
    "galculator": "calc калькулятор калькулятор",
    "chromium": "браузер браузер интернет chrome",
    "thunar": "файлы проводник файл папка",
    "xfce4-terminal": "терминал консоль команда",
    "mousepad": "блокнот записки текст",
    "vlc": "видео проигрыватель фильм",
    "ristretto": "фотографии изображение картинка",
    "kvorix-taskmanager": "диспетчер задачи процессы",
    "kvorix-disks": "диски хранилище накопитель",
    "pavucontrol": "звук громкость микшер",
    "xfce4-appfinder": "выполнить запуск команду",
    "ristretto": "фото просмотр изображение",
}




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


def launch(cmd):
    import shlex
    env = dict(os.environ)
    env.setdefault("DISPLAY", ":0")
    env.setdefault("XAUTHORITY", os.path.expanduser("~/.Xauthority"))
    env.setdefault("XDG_RUNTIME_DIR", "/run/user/%d" % os.getuid())
    if not any(ch in cmd for ch in ("|", ";", "&", ">", "<", "$", "`", "\n", "=")):
        argv = shlex.split(cmd)
    else:
        argv = ["sh", "-c", cmd]
    p = subprocess.Popen(
        argv,
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True, close_fds=True, env=env,
    )
    GLib.timeout_add(300, lambda: p.poll() is None)


def apply_xshape_rounded(win, w, h, radius=16):
    if w < 20 or h < 20 or not win.get_window():
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
    win.get_window().shape_combine_region(Gdk.cairo_region_create_from_surface(surf), 0, 0)


def draw_menu_border(wid, cr):
    w = wid.get_allocated_width()
    h = wid.get_allocated_height()
    if w < 20 or h < 20:
        return False
    dark = get_theme() == "dark"
    cr.save()
    cr.new_path()
    cr.set_line_width(1.6)
    if dark:
        cr.set_source_rgba(1.0, 1.0, 1.0, 0.16)
    else:
        cr.set_source_rgba(0.08, 0.12, 0.22, 0.15)
    r = 15.2
    cr.arc(w - r - 0.8, r + 0.8, r, -math.pi / 2, 0)
    cr.arc(w - r - 0.8, h - r - 0.8, r, 0, math.pi / 2)
    cr.arc(r + 0.8, h - r - 0.8, r, math.pi / 2, math.pi)
    cr.arc(r + 0.8, r + 0.8, r, math.pi, 1.5 * math.pi)
    cr.close_path()
    cr.stroke()
    cr.restore()
    return False


SKIP_DESKTOP = {
    # дубли и служебное: «Файлы» вместо Thunar, консольные htop/mc, сервер VNC, picom, выход есть в меню
    "onboard.desktop", "onboard-settings.desktop",
    "thunar.desktop", "htop.desktop", "mc.desktop", "mcedit.desktop", "picom.desktop",
    "x11vnc.desktop", "xfce4-run.desktop", "xfce4-session-logout.desktop",
    "xfce-settings-manager.desktop", "xfce-wm-settings.desktop",
    "xfce-wmtweaks-settings.desktop", "xfce-workspaces-settings.desktop",
    "xfce-backdrop-settings.desktop", "xfce-ui-settings.desktop",
    "xfce-session-settings.desktop", "xfce-keyboard-settings.desktop",
    "xfce-mouse-settings.desktop", "xfce-display-settings.desktop",
    "xfce4-accessibility-settings.desktop", "xfce4-color-settings.desktop",
    "xfce4-mime-settings.desktop", "xfce4-notifyd-config.desktop",
    "xfce4-power-manager-settings.desktop", "xfce4-about.desktop",
    "xfce4-mail-reader.desktop", "xfce4-file-manager.desktop",
    "xfce4-terminal-emulator.desktop", "xfce4-web-browser.desktop",
    "thunar-settings.desktop", "thunar-volman-settings.desktop",
    "thunar-bulk-rename.desktop", "panel-desktop-handler.desktop",
    "blueman-adapters.desktop", "python3.13.desktop", "vim.desktop",
    "xfce4-taskmanager.desktop", "org.xfce.Parole.desktop",
    "rxvt-unicode.desktop", "debian-uxterm.desktop", "debian-xterm.desktop",
    "uxterm.desktop", "xterm.desktop",
}


def load_apps():
    apps = []
    for path in sorted(glob.glob("/usr/share/applications/*.desktop")):
        if os.path.basename(path) in SKIP_DESKTOP:
            continue
        try:
            name = name_ru = icon = exec_ = cats = ""
            kw = kw_ru = gn = gn_ru = cm_ru = ""
            nodisplay = hidden = False
            with open(path, encoding="utf-8", errors="replace") as f:
                for line in f:
                    if "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    v = v.strip()
                    if k == "Name":
                        name = v
                    elif k == "Name[ru]":
                        name_ru = v
                    elif k == "Icon":
                        icon = v
                    elif k == "Exec":
                        exec_ = v
                    elif k == "Categories":
                        cats = v
                    elif k == "Keywords":
                        kw = v
                    elif k == "Keywords[ru]":
                        kw_ru = v
                    elif k == "GenericName":
                        gn = v
                    elif k == "GenericName[ru]":
                        gn_ru = v
                    elif k == "Comment[ru]":
                        cm_ru = v
                    elif k == "NoDisplay":
                        nodisplay = v.lower() == "true"
                    elif k == "Hidden":
                        hidden = v.lower() == "true"
            if nodisplay or hidden or not exec_ or not icon:
                continue
            clean_exec = " ".join(tok for tok in exec_.split() if not tok.startswith("%"))
            cat = "Утилиты"
            for c in cats.split(";"):
                if c in CATMAP:
                    cat = CATMAP[c]
                    break
            exec_bin = clean_exec.split()[0].split("/")[-1] if clean_exec else ""
            aliases = APP_ALIASES.get(exec_bin.lower(), "")
            hay = ";".join(filter(None, (name.lower(), name_ru.lower(), kw.lower(),
                                         kw_ru.lower(), gn.lower(), gn_ru.lower(),
                                         cm_ru.lower(), exec_bin.lower(), aliases)))
            apps.append({"name": name_ru or name, "icon": icon, "exec": clean_exec,
                         "cat": cat, "search": hay})
        except Exception:
            continue
    apps.sort(key=lambda a: a["name"].lower())
    return apps


def load_recent():
    path = os.path.expanduser("~/.local/share/recently-used.xbel")
    out = []
    try:
        import urllib.parse
        import xml.etree.ElementTree as ET
        tree = ET.parse(path)
        ns = "{http://www.gnome.org/xbel}"
        items = []
        for bk in tree.getroot().findall(ns + "bookmark"):
            href = bk.get("href", "")
            added = bk.get("added", "")
            if href.startswith("file://"):
                fpath = urllib.parse.unquote(href[7:])
                if os.path.exists(fpath) and not os.path.basename(fpath).startswith("."):
                    items.append((added, fpath))
        items.sort(reverse=True)
        seen = set()
        for _, fpath in items:
            if fpath in seen:
                continue
            seen.add(fpath)
            base = os.path.basename(fpath)
            ext = base.rsplit(".", 1)[-1].lower() if "." in base else ""
            icon = {
                "png": "image-x-generic", "jpg": "image-x-generic", "jpeg": "image-x-generic",
                "txt": "text-x-generic", "md": "text-x-generic", "pdf": "application-pdf",
                "mp3": "audio-x-generic", "flac": "audio-x-generic",
                "mp4": "video-x-generic", "mkv": "video-x-generic",
                "zip": "package-x-generic", "gz": "package-x-generic",
                "sh": "application-x-script",
            }.get(ext, "text-x-generic")
            qpath = fpath.replace("'", "'\\''")
            out.append({
                "title": base,
                "sub": os.path.dirname(fpath).replace(os.path.expanduser("~"), "~"),
                "icon": icon,
                "cmd": f"xdg-open '{qpath}'",
            })
            if len(out) >= 4:
                break
    except Exception:
        pass
    return out


def _user_label():
    import pwd
    import socket
    p = pwd.getpwuid(os.getuid())
    uname = p.pw_gecos.split(",")[0].strip() or p.pw_name
    if uname == "Пользователь":
        uname = p.pw_name
    host = socket.gethostname() or "Kvorix"
    return f"{uname} · {host.capitalize()}"


_EN_K = "qwertyuiop[]asdfghjkl;'zxcvbnm,./`"
_RU_K = "йцукенгшщзхъфывапролджэячсмитьбю.ё"
_LAYOUT_MAP = str.maketrans(_EN_K + _EN_K.upper() + _RU_K + _RU_K.upper(),
                            _RU_K + _RU_K.upper() + _EN_K + _EN_K.upper())


def _swap_layout(text):
    return text.translate(_LAYOUT_MAP)


def _load_settings_index(center_py="/usr/local/share/armbian-gui/center.py"):
    try:
        import ast
        import sys
        gui_dir = os.path.dirname(center_py)
        if gui_dir not in sys.path:
            sys.path.insert(0, gui_dir)
        from settings_search import SearchIndex
        tree = ast.parse(open(center_py, encoding="utf-8").read())
        vals = {}
        for node in tree.body:
            if isinstance(node, ast.Assign):
                for t in node.targets:
                    if isinstance(t, ast.Name) and t.id in ("MENU", "KEYWORDS"):
                        vals[t.id] = ast.literal_eval(node.value)
        menu = vals.get("MENU", [])
        icons = {k: ic for k, _, ic in menu if k != "__sec__"}
        return SearchIndex.from_file(menu, vals.get("KEYWORDS", {}), center_py), icons
    except Exception:
        return None, {}


def _add_to_desktop(app):
    desk = os.path.expanduser("~/Desktop")
    if not os.path.isdir(desk) and os.path.isdir(os.path.expanduser("~/Рабочий стол")):
        desk = os.path.expanduser("~/Рабочий стол")
    os.makedirs(desk, exist_ok=True)
    safe = "".join(ch for ch in app["name"] if ch.isalnum() or ch in " _-").strip() or "App"
    p = os.path.join(desk, f"{safe}.desktop")
    with open(p, "w", encoding="utf-8") as f:
        f.write(
            "[Desktop Entry]\nVersion=1.0\nType=Application\n"
            f"Name={app['name']}\nExec={app['exec']}\nIcon={app['icon']}\nTerminal=false\n"
        )
    os.chmod(p, 0o755)
    subprocess.Popen(["notify-send", "-i", app["icon"], "Рабочий стол", f"Ярлык «{app['name']}» добавлен"],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


class StartMenu(Gtk.Window):
    def __init__(self, focus_search=False):
        super().__init__(type=Gtk.WindowType.TOPLEVEL)
        self.set_type_hint(Gdk.WindowTypeHint.UTILITY)
        self.set_decorated(False)
        self.set_skip_taskbar_hint(True)
        self.set_skip_pager_hint(True)
        self.set_resizable(False)
        self.set_accept_focus(True)
        self.set_title("rsaarm-menu")
        self._last_shape = (0, 0)

        screen = Gdk.Screen.get_default()
        sw, sh = screen.get_width(), screen.get_height()
        self.set_default_size(W, H)
        self.set_size_request(W, H)
        self.resize(W, H)
        self.set_keep_above(True)
        self.move((sw - W) // 2, sh - TB_H - 10 - H)

        scr = self.get_screen()
        self._css_pr = self._css()
        Gtk.StyleContext.add_provider_for_screen(
            scr, self._css_pr, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        self.apps = load_apps()
        self.recent = load_recent()
        self._settings_idx, self._settings_icons = _load_settings_index()
        self.all_mode = False
        self.active_cat = "Все"
        self.query = ""
        self._launched = False
        self._rebuilding = False

        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        card.get_style_context().add_class("sm")
        card.connect_after("draw", draw_menu_border)
        self.add(card)
        self.connect("size-allocate", self._on_alloc)

        self.search = Gtk.SearchEntry()
        self.search.get_style_context().add_class("sm-search")
        self.search.set_placeholder_text("Поиск программ, файлов и параметров…")
        self.search.connect("changed", self.on_search)
        self.search.connect("key-press-event", self.on_key)
        card.pack_start(self.search, False, False, 0)

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.get_style_context().add_class("sm-scroll")
        self.body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        scroll.add(self.body)
        card.pack_start(scroll, True, True, 0)

        footer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        footer.get_style_context().add_class("sm-footer")
        ub = Gtk.Button()
        ubox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        ulabel = _user_label()
        av = Gtk.Label(label=ulabel[:1].upper())
        av.get_style_context().add_class("sm-avatar")
        ubox.pack_start(av, False, False, 0)
        ul = Gtk.Label(label=ulabel)
        ul.get_style_context().add_class("sm-user")
        ubox.pack_start(ul, False, False, 0)
        ub.add(ubox)
        ub.set_tooltip_text("Параметры учётной записи")
        ub.get_style_context().add_class("sm-foot-btn")
        ub.connect("clicked", lambda *_: (self.hide(), launch(
            "python3 /usr/local/share/armbian-gui/center.py --page=users")))
        footer.pack_start(ub, False, False, 0)
        footer.pack_start(Gtk.Box(), True, True, 0)

        for title, icon, cmd in (
            ("Заблокировать", "system-lock-screen-symbolic", "dm-tool lock"),
            ("Перезагрузка", "system-reboot-symbolic", "sudo systemctl reboot"),
            ("Выключение", "system-shutdown-symbolic", "sudo systemctl poweroff"),
        ):
            b = Gtk.Button()
            b.set_tooltip_text(title)
            b.add(Gtk.Image.new_from_icon_name(icon, Gtk.IconSize.MENU))
            b.get_style_context().add_class("sm-foot-btn")
            b.connect("clicked", lambda *_a, c=cmd: (self.hide(), launch(c)))
            footer.pack_start(b, False, False, 0)
        card.pack_start(footer, False, False, 0)

        self.rebuild()
        self.connect("key-press-event", self.on_key_root)
        self.connect("button-press-event", self.on_bpress)
        if focus_search:
            GLib.idle_add(lambda: (self.search.grab_focus(), False)[1])

    def _on_alloc(self, _w, alloc):
        sz = (alloc.width, alloc.height)
        if sz != self._last_shape:
            self._last_shape = sz
            apply_xshape_rounded(self, alloc.width, alloc.height, 16)

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
        except Exception:
            pass
        return False

    def on_key_root(self, _w, ev):
        if ev.keyval == Gdk.KEY_Escape:
            self.hide()
        return False

    def on_bpress(self, _w, ev):
        try:
            ax, ay = self.get_position()
            ww, wh = self.get_size()
            if ev.x_root < ax or ev.x_root > ax + ww or ev.y_root < ay or ev.y_root > ay + wh:
                self.hide()
        except Exception:
            pass
        return False

    def poll_outside(self):
        try:
            if not self.get_visible() or time.time() - getattr(self, "_shown_at", 0) < 1.8:
                return True
            own_popup = any(
                w is not self and w.get_visible() and w.get_window_type() == Gtk.WindowType.POPUP
                and w.get_size()[0] > 1 for w in Gtk.Window.list_toplevels()
            )
            if not self.is_active() and not own_popup:
                disp = Gdk.Display.get_default()
                ptr = disp.get_default_seat().get_pointer()
                _s, x, y = ptr.get_position()
                ax, ay = self.get_position()
                w_, h_ = self.get_size()
                if x < ax - 16 or x > ax + w_ + 16 or y < ay - 16 or y > ay + h_ + 16:
                    self.hide()
        except Exception:
            pass
        return True

    def on_key(self, _w, ev):
        if ev.keyval == Gdk.KEY_Return:
            self.run_first()
            return True
        return False

    def on_search(self, e):
        self.query = e.get_text().strip().lower()
        self.rebuild()

    def run_first(self):
        ch = self.grid.get_selected_children() if hasattr(self, "grid") else []
        if not ch and hasattr(self, "grid"):
            c0 = self.grid.get_child_at_index(0)
            ch = [c0] if c0 else []
        if ch:
            self.run_app(ch[0].get_child().app)

    def run_app(self, app):
        if self._launched:
            return
        self._launched = True
        launch(app["exec"])
        import time as _t
        _t.sleep(0.5)
        GLib.idle_add(self.hide)

    def section_header(self, title, btn_label=None, cb=None):
        hb = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        lbl = Gtk.Label()
        lbl.set_markup("<b>%s</b>" % GLib.markup_escape_text(title))
        lbl.get_style_context().add_class("sm-h")
        hb.pack_start(lbl, False, False, 0)
        hb.pack_start(Gtk.Box(), True, True, 0)
        if btn_label:
            b = Gtk.Button(label=btn_label)
            b.get_style_context().add_class("sm-link")
            if cb:
                b.connect("clicked", cb)
            hb.pack_start(b, False, False, 0)
        return hb

    def app_btn(self, app, small=False):
        b = Gtk.Button()
        vb = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        ic = app["icon"] if Gtk.IconTheme.get_default().has_icon(app["icon"]) else "application-x-executable"
        img = Gtk.Image.new_from_icon_name(ic, Gtk.IconSize.DIALOG)
        if small:
            img.set_pixel_size(34)
        vb.pack_start(img, False, False, 0)
        lbl = Gtk.Label(label=app["name"])
        lbl.get_style_context().add_class("sm-app-label")
        lbl.set_max_width_chars(11 if small else 14)
        lbl.set_ellipsize(Pango.EllipsizeMode.END)
        vb.pack_start(lbl, False, False, 0)
        b.add(vb)
        b.get_style_context().add_class("sm-app")
        b.app = app
        b.connect("clicked", lambda w: self.run_app(w.app))
        b.connect("button-press-event", self._on_app_right)
        return b

    def _on_app_right(self, btn, ev):
        if ev.button == 3:
            m = Gtk.Menu()
            i1 = Gtk.MenuItem(label="Открыть")
            i1.connect("activate", lambda *_: self.run_app(btn.app))
            m.append(i1)
            i2 = Gtk.MenuItem(label="Добавить ярлык на Рабочий стол")
            i2.connect("activate", lambda *_: _add_to_desktop(btn.app))
            m.append(i2)
            m.show_all()
            m.popup_at_pointer(ev)
            return True
        return False

    def _rec_btn(self, item):
        b = Gtk.Button()
        hb = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        ic = item["icon"] if Gtk.IconTheme.get_default().has_icon(item["icon"]) else "text-x-generic"
        img = Gtk.Image.new_from_icon_name(ic, Gtk.IconSize.LARGE_TOOLBAR)
        img.set_pixel_size(26)
        hb.pack_start(img, False, False, 0)

        vb = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
        tl = Gtk.Label(label=item["title"], xalign=0)
        tl.set_ellipsize(Pango.EllipsizeMode.END)
        tl.set_max_width_chars(24)
        sl = Gtk.Label(label=item.get("sub", ""), xalign=0)
        sl.get_style_context().add_class("sm-rec-sub")
        sl.set_ellipsize(Pango.EllipsizeMode.END)
        sl.set_max_width_chars(28)
        vb.pack_start(tl, False, False, 0)
        vb.pack_start(sl, False, False, 0)
        hb.pack_start(vb, True, True, 0)

        b.add(hb)
        b.get_style_context().add_class("sm-rec")
        cmd = item["cmd"]
        b.connect("clicked", lambda *_: (self.hide(), launch(cmd)))
        return b

    def rebuild(self):
        for ch in self.body.get_children():
            self.body.remove(ch)

        if self.query:
            self.grid = Gtk.FlowBox()
            self.grid.set_valign(Gtk.Align.START)
            self.grid.set_max_children_per_line(4)
            self.grid.set_column_spacing(4); self.grid.set_row_spacing(4)
            self.grid.set_homogeneous(True)
            q_words = self.query.split()
            matched_apps = [app for app in self.apps
                            if all(w in (app.get("search") or app["name"].lower()) for w in q_words)]
            if not matched_apps:
                alt_words = _swap_layout(self.query).lower().split()
                if alt_words and alt_words != q_words:
                    matched_apps = [app for app in self.apps
                                    if all(w in (app.get("search") or app["name"].lower()) for w in alt_words)]
            count = 0
            for app in matched_apps:
                self.grid.add(self.app_btn(app, small=True))
                count += 1
            if self._settings_idx is not None:
                for hit in self._settings_idx.search(self.query)[:6]:
                    ic = self._settings_icons.get(hit.key) or "preferences-system"
                    self.grid.add(self.app_btn({
                        "name": "Настройки: " + hit.title,
                        "icon": ic,
                        "exec": "armbian-center --page=" + hit.key,
                    }, small=True))
                    count += 1
            if count:
                self.body.pack_start(self.grid, True, True, 0)
            else:
                empty = Gtk.Label(label="Ничего не найдено — попробуйте другое слово")
                empty.get_style_context().add_class("sm-dim")
                empty.set_margin_top(28)
                self.body.pack_start(empty, False, False, 0)
            self.body.show_all()
            return

        if not self.all_mode:
            self.body.pack_start(self.section_header(
                "Закреплённые", "Все приложения  ›", lambda *_: self.show_all_apps()), False, False, 0)
            grid = Gtk.FlowBox()
            grid.set_valign(Gtk.Align.START)
            grid.set_min_children_per_line(6)
            grid.set_max_children_per_line(6)
            grid.set_column_spacing(2); grid.set_row_spacing(4)
            grid.set_homogeneous(True)
            for name, icon, cmd in PINNED:
                grid.add(self.app_btn({"name": name, "icon": icon, "exec": cmd}, small=True))
            self.body.pack_start(grid, False, False, 0)

            self.body.pack_start(self.section_header("Рекомендуемые"), False, False, 0)
            rec_grid = Gtk.Grid()
            rec_grid.set_column_homogeneous(True)
            rec_grid.set_column_spacing(8)
            rec_grid.set_row_spacing(4)
            combined = list(self.recent)
            for q in QUICK_RECS:
                if len(combined) >= 4:
                    break
                combined.append(q)
            for idx, item in enumerate(combined[:4]):
                rec_grid.attach(self._rec_btn(item), idx % 2, idx // 2, 1, 1)
            self.body.pack_start(rec_grid, False, False, 0)
        else:
            chips = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
            self.cat_btns = {}
            for title, _ in CATS:
                b = Gtk.ToggleButton(label=title)
                b.get_style_context().add_class("chip")
                if title == self.active_cat:
                    self._rebuilding = True
                    b.set_active(True)
                    self._rebuilding = False
                b.connect("toggled", self.on_cat, title)
                self.cat_btns[title] = b
                chips.pack_start(b, False, False, 0)
            self.body.pack_start(chips, False, False, 0)

            back = Gtk.Button(label="‹  Закреплённые")
            back.get_style_context().add_class("sm-link")
            back.connect("clicked", lambda *_: self.show_pins())
            self.body.pack_start(back, False, False, 0)

            self.grid = Gtk.FlowBox()
            self.grid.set_valign(Gtk.Align.START)
            self.grid.set_max_children_per_line(4)
            self.grid.set_column_spacing(4); self.grid.set_row_spacing(4)
            self.grid.set_homogeneous(True)
            for app in self.apps:
                if self.active_cat == "Все" or app["cat"] == self.active_cat:
                    self.grid.add(self.app_btn(app, small=True))
            self.body.pack_start(self.grid, True, True, 0)
        self.body.show_all()

    def on_cat(self, btn, title):
        if self._rebuilding:
            return
        if not btn.get_active():
            if self.active_cat == title:
                self._rebuilding = True
                btn.set_active(True)
                self._rebuilding = False
            return
        self.active_cat = title
        for t, b in self.cat_btns.items():
            if t != title:
                self._rebuilding = True
                b.set_active(False)
                self._rebuilding = False
        self.rebuild()

    def show_all_apps(self):
        self.all_mode = True
        self.rebuild()

    def show_pins(self):
        self.all_mode = False
        self.rebuild()

    def toggle(self, *_a):
        if self.get_visible():
            self.hide()
        else:
            self._launched = False
            self.all_mode = False
            self.recent = load_recent()
            if self.search.get_text():
                self.query = ""
                self.search.set_text("")
            self.rebuild()
            self.show_all()
            self.resize(W, H)
            apply_xshape_rounded(self, W, H, 16)
            sw_ = Gdk.Screen.get_default().get_width()
            sh_ = Gdk.Screen.get_default().get_height()
            tx = (sw_ - W) // 2
            ty = sh_ - TB_H - 10 - H
            self._shown_at = time.time()

            if animations_enabled():
                sy = ty + 16
                self.move(tx, sy)
                self.present()
                step = [0]

                def _anim():
                    step[0] += 1
                    t = min(1.0, step[0] / 6.0)
                    ease = 1.0 - (1.0 - t) ** 3
                    self.move(tx, int(round(sy + (ty - sy) * ease)))
                    return t < 1.0

                GLib.timeout_add(16, _anim)
            else:
                self.move(tx, ty)
                self.present()

            GLib.idle_add(lambda: (self.search.grab_focus(), False)[1])
            try:
                from gi.repository import GdkX11
                self.get_window().focus(GdkX11.x11_get_server_time(self.get_window()))
            except Exception:
                pass
        return False


def main():
    import fcntl
    import signal
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    signal.signal(signal.SIGUSR1, signal.SIG_IGN)
    signal.signal(signal.SIGUSR2, signal.SIG_IGN)
    prewarm = "--prewarm" in os.sys.argv[1:]
    focus = "--search" in os.sys.argv[1:]

    global _LOCK
    _LOCK = open("/tmp/rsaarm-menu-%d.lock" % os.getuid(), "w")
    try:
        fcntl.flock(_LOCK, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        if not prewarm:
            try:
                os.kill(int(open("/tmp/rsaarm-menu-%d.pid" % os.getuid()).read()), signal.SIGUSR1)
            except (OSError, ValueError):
                pass
        return

    try:
        for pid in subprocess.check_output(["pgrep", "-f", "rsaarm-menu.py"]).split():
            pid = int(pid)
            if pid == os.getpid() or pid == os.getppid():
                continue
            try:
                with open("/proc/%d/comm" % pid) as f:
                    if f.read().strip() != "python3":
                        continue
            except Exception:
                continue
            if prewarm:
                return
            os.kill(pid, signal.SIGUSR1)
            return
    except Exception:
        pass

    GLib.set_prgname("rsaarm-menu")
    Gtk.init(None)

    w = StartMenu(focus_search=focus)
    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGUSR1, lambda: (w.toggle(), True)[1])
    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGUSR2, lambda: (w._reload_css(), True)[1])
    try:
        with open("/tmp/rsaarm-menu-%d.pid" % os.getuid(), "w") as f:
            f.write(str(os.getpid()))
    except Exception:
        pass

    if not prewarm:
        w.show_all()
        w.resize(W, H)
        apply_xshape_rounded(w, W, H, 16)
        sw_, sh_ = Gdk.Screen.get_default().get_width(), Gdk.Screen.get_default().get_height()
        w.move((sw_ - W) // 2, sh_ - TB_H - 10 - H)
        w.present()
        w._shown_at = time.time()

    GLib.timeout_add(300, w.poll_outside)
    Gtk.main()


if __name__ == "__main__":
    main()

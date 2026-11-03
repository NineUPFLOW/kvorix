#!/usr/bin/env python3

import configparser
import json
import os
import re
import shutil
import time

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk

import common as C
import ui

BACKUP = os.path.join(os.path.expanduser("~/.config/armbian-tv"), "autostart-backup.json")
USER_AUTOSTART = os.path.expanduser("~/.config/autostart")
SYSTEM_AUTOSTART = "/etc/xdg/autostart"

CRITICAL = {
    "dbus.service", "systemd-journald.service", "systemd-logind.service",
    "systemd-resolved.service", "systemd-udevd.service", "NetworkManager.service",
    "ssh.service", "sshd.service", "wpa_supplicant.service", "user@1001.service",
    "getty@tty1.service", "systemd-user-sessions.service", "cron.service",
    "lightdm.service", "polkit.service", "udisks2.service",
}
CRITICAL_PREFIX = ("systemd-", "dbus", "user@", "getty@", "ssh")
SEVERITY_WARN = {"bluetooth.service", "smbd.service", "minidlna.service",
                 "navidrome.service", "shairport-sync.service", "bluealsa.service"}


def unit_description(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            text = f.read()
    except Exception:
        return ""
    m = re.search(r"^Description\s*=\s*(.+)$", text, re.M)
    return m.group(1).strip() if m else ""


def unit_exec(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            text = f.read()
    except Exception:
        return ""
    m = re.search(r"^ExecStart\s*=\s*[-@+!:]*\s*(.+)$", text, re.M)
    return m.group(1).strip() if m else ""


def find_unit_file(unit, is_user=False):
    dirs = ([os.path.expanduser("~/.config/systemd/user"), "/usr/lib/systemd/user",
             "/etc/systemd/user"] if is_user else
            ["/etc/systemd/system", "/usr/lib/systemd/system", "/lib/systemd/system"])
    for d in dirs:
        p = os.path.join(d, unit)
        if os.path.exists(p):
            return p
    return ""


def is_critical(unit):
    return unit in CRITICAL or unit.startswith(CRITICAL_PREFIX)


def collect_systemd(is_user=False):
    cmd = (["systemctl", "--user"] if is_user else ["systemctl"]) + \
          ["list-unit-files", "--type=service", "--no-legend", "--no-pager"]
    code, o = C.run(cmd, timeout=25)
    items = []
    for line in o.splitlines():
        f = line.split()
        if len(f) < 2:
            continue
        unit, state = f[0], f[1]
        if state in ("static", "alias", "indirect", "generated"):
            continue
        path = find_unit_file(unit, is_user)
        if not path:
            continue
        items.append({
            "key": ("user:" if is_user else "sys:") + unit,
            "unit": unit,
            "name": unit.replace(".service", ""),
            "kind": "Служба пользователя" if is_user else "Служба системы",
            "type": "user-unit" if is_user else "sys-unit",
            "path": path,
            "exec": unit_exec(path),
            "desc": unit_description(path) or "—",
            "enabled": state in ("enabled", "enabled-runtime"),
            "state": state,
            "critical": is_critical(unit),
        })
    return items


def parse_desktop(path):
    cp = configparser.RawConfigParser(strict=False)
    try:
        cp.read(path, encoding="utf-8")
    except Exception:
        return None
    if not cp.has_section("Desktop Entry"):
        return None
    s = cp["Desktop Entry"]
    hidden = s.get("Hidden", "false").lower() == "true"
    auto = s.get("X-GNOME-Autostart-enabled", "true").lower() != "false"
    only_show_in = s.get("OnlyShowIn", "")
    if only_show_in and "XFCE" not in only_show_in:
        auto = False
    return {
        "name": s.get("Name", os.path.basename(path)),
        "exec": s.get("Exec", ""),
        "desc": s.get("Comment", "—"),
        "enabled": (not hidden) and auto,
        "hidden": hidden,
        "type_key": s.get("Type", "Application"),
    }


def collect_desktop():
    items = []
    seen = set()
    for base, is_user in ((USER_AUTOSTART, True), (SYSTEM_AUTOSTART, False)):
        if not os.path.isdir(base):
            continue
        for fn in sorted(os.listdir(base)):
            if not fn.endswith(".desktop"):
                continue
            path = os.path.join(base, fn)
            d = parse_desktop(path)
            if d is None:
                continue
            if not is_user and fn in seen:
                continue
            seen.add(fn)
            items.append({
                "key": "xdg:" + ("user:" if is_user else "sys:") + fn,
                "unit": fn,
                "name": d["name"],
                "kind": "Автозапуск сеанса" if is_user else "Автозапуск сеанса (система)",
                "type": "user-desktop" if is_user else "sys-desktop",
                "path": path,
                "exec": d["exec"],
                "desc": d["desc"],
                "enabled": d["enabled"],
                "state": "включено" if d["enabled"] else "выключено",
                "critical": False,
            })
    return items


def collect_all():
    items = collect_systemd(False)
    items += collect_systemd(True)
    items += collect_desktop()
    items.sort(key=lambda x: (not x["enabled"], x["name"].lower()))
    return items


def backup_state(items):
    os.makedirs(os.path.dirname(BACKUP), exist_ok=True)
    data = {"time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "items": {i["key"]: i["enabled"] for i in items}}
    with open(BACKUP, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    return BACKUP


def set_enabled(item, on):
    
    t = item["type"]
    if t == "sys-unit":
        if on and item["state"] == "masked":
            C.sudo(["systemctl", "unmask", item["unit"]])
        code, o = C.sudo(["systemctl", "enable" if on else "disable", item["unit"]])
        return code == 0, o.strip()
    if t == "user-unit":
        code, o = C.run(["systemctl", "--user", "enable" if on else "disable", item["unit"]], timeout=25)
        return code == 0, o.strip()
    if t == "sys-desktop":
        os.makedirs(USER_AUTOSTART, exist_ok=True)
        dst = os.path.join(USER_AUTOSTART, item["unit"])
        if on:
            if os.path.exists(dst):
                os.remove(dst)
            return True, "переопределение снято"
        shutil.copy2(item["path"], dst)
        s = open(dst).read()
        if "Hidden=" in s:
            s = re.sub(r"^Hidden=.*$", "Hidden=true", s, flags=re.M)
        else:
            s = s.replace("[Desktop Entry]", "[Desktop Entry]\nHidden=true", 1)
        open(dst, "w").write(s)
        return True, "создано переопределение с Hidden=true"
    if t == "user-desktop":
        s = open(item["path"]).read()
        if "Hidden=" in s:
            s = re.sub(r"^Hidden=.*$", "Hidden=%s" % ("false" if on else "true"), s, flags=re.M)
        else:
            s = s.replace("[Desktop Entry]",
                          "[Desktop Entry]\nHidden=%s" % ("false" if on else "true"), 1)
        open(item["path"], "w").write(s)
        return True, "изменён файл автозапуска"
    return False, "неизвестный тип"


def add_custom(name, command, comment=""):
    os.makedirs(USER_AUTOSTART, exist_ok=True)
    fn = re.sub(r"[^a-zA-Z0-9_.-]", "-", name.strip().lower()) or "custom"
    path = os.path.join(USER_AUTOSTART, fn + ".desktop")
    with open(path, "w") as f:
        f.write("[Desktop Entry]\nType=Application\nName=%s\nComment=%s\nExec=%s\n"
                "Terminal=false\nX-GNOME-Autostart-enabled=true\n" % (name, comment or "Добавлено вручную", command))
    os.chmod(path, 0o755)
    return path


COLS = [("state", "ВКЛ", 62), ("name", "НАЗВАНИЕ", 250), ("kind", "ТИП", 190),
        ("path", "ФАЙЛ / КОМАНДА", 380), ("desc", "ОПИСАНИЕ", 320)]


class AutostartWindow(Gtk.Window):
    def __init__(self):
        super().__init__(title="Автозагрузка — Armbian TV")
        self.set_default_size(1330, 690)
        self.set_icon_name("preferences-system-session")
        self.items = []
        self.filtered = []

        hb = Gtk.HeaderBar(show_close_button=True)
        hb.set_title("Автозагрузка")
        hb.set_subtitle("всё, что стартует само: службы, сеанс, пользовательские записи")
        self.set_titlebar(hb)

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        root.set_margin_top(14)
        root.set_margin_bottom(14)
        root.set_margin_start(16)
        root.set_margin_end(16)
        self.add(ui.fit(root))

        bar = Gtk.Box(spacing=8)
        self.search = Gtk.SearchEntry()
        self.search.set_placeholder_text("Поиск по названию, описанию, файлу…")
        self.search.set_size_request(320, -1)
        self.search.connect("search-changed", lambda *_: self.refresh_view())
        bar.pack_start(self.search, False, False, 0)

        self.f_kind = Gtk.ComboBoxText()
        for t in ["Все типы", "Службы системы", "Службы пользователя",
                  "Автозапуск сеанса", "Только включённые", "Только выключенные"]:
            self.f_kind.append_text(t)
        self.f_kind.set_active(0)
        self.f_kind.connect("changed", lambda *_: self.refresh_view())
        bar.pack_start(self.f_kind, False, False, 0)

        self.f_sort = Gtk.ComboBoxText()
        for t in ["Сортировка: по названию", "Сортировка: по типу", "Сортировка: состояние"]:
            self.f_sort.append_text(t)
        self.f_sort.set_active(0)
        self.f_sort.connect("changed", lambda *_: self.refresh_view())
        bar.pack_start(self.f_sort, False, False, 0)

        bar.pack_end(ui.button("Обновить", self.reload, "ghost", "view-refresh"), False, False, 0)
        bar.pack_end(ui.button("Откатить изменения", self.restore_backup, "ghost", "edit-undo"),
                     False, False, 0)
        bar.pack_end(ui.button("Добавить программу", self.add_dialog, "btn", "list-add"),
                     False, False, 0)
        root.pack_start(bar, False, False, 0)

        self.store = Gtk.ListStore(bool, str, str, str, str, str)
        self.tv = Gtk.TreeView(model=self.store)
        self.tv.set_headers_visible(True)
        for i, (cid, title, width) in enumerate(COLS):
            if cid == "state":
                r = Gtk.CellRendererToggle()
                r.set_property("activatable", True)
                r.connect("toggled", self.on_toggle)
                col = Gtk.TreeViewColumn(title, r, active=0)
                col.set_fixed_width(width)
            else:
                r = Gtk.CellRendererText(ellipsize=3)
                col = Gtk.TreeViewColumn(title, r, text=i)
                col.set_fixed_width(width)
                col.set_resizable(True)
                if cid == "path":
                    r.set_property("family", "DejaVu Sans Mono")
                    r.set_property("size", 10 * 1024)
                    r.set_property("foreground", "#93a4b8")
            self.tv.append_column(col)
        self.tv.get_selection().connect("changed", self.on_select)
        sw = Gtk.ScrolledWindow()
        sw.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        sw.add(self.tv)
        root.pack_start(sw, True, True, 0)

        self.details = ui.Card("Выбранный элемент")
        self.d_name = Gtk.Label(xalign=0)
        self.d_name.get_style_context().add_class("card-title")
        self.details.add(self.d_name)
        self.d_path = Gtk.Label(xalign=0, selectable=True)
        self.d_path.get_style_context().add_class("tile-path")
        self.d_path.set_line_wrap(True)
        self.details.add(self.d_path)
        self.d_exec = Gtk.Label(xalign=0, selectable=True)
        self.d_exec.get_style_context().add_class("tile-path")
        self.d_exec.set_line_wrap(True)
        self.details.add(self.d_exec)
        self.d_info = Gtk.Label(xalign=0)
        self.d_info.get_style_context().add_class("muted")
        self.d_info.set_line_wrap(True)
        self.details.add(self.d_info)
        acts = Gtk.Box(spacing=8)
        self.b_toggle = ui.button("Выключить", self.toggle_selected, "btn")
        self.b_open = ui.button("Показать файл", self.show_file, "ghost", "text-x-generic")
        self.b_remove = ui.button("Удалить запись", self.remove_selected, "danger", "user-trash")
        acts.pack_start(self.b_toggle, False, False, 0)
        acts.pack_start(self.b_open, False, False, 0)
        acts.pack_end(self.b_remove, False, False, 0)
        self.details.add(acts)
        root.pack_start(self.details, False, False, 0)

        self.status = Gtk.Label(xalign=0)
        self.status.get_style_context().add_class("muted")
        root.pack_start(self.status, False, False, 0)

        self.reload()
        self.connect("destroy", Gtk.main_quit)

    def reload(self):
        self.status.set_text("Читаю список автозагрузки…")
        while Gtk.events_pending():
            Gtk.main_iteration()
        self.items = collect_all()
        self.refresh_view()
        n_on = sum(1 for i in self.items if i["enabled"])
        self.status.set_text("Всего записей: %d · включено: %d · выключено: %d · "
                             "резервная копия: %s" % (len(self.items), n_on,
                                                      len(self.items) - n_on, BACKUP))

    def refresh_view(self):
        q = self.search.get_text().strip().lower()
        mode = self.f_kind.get_active()
        rows = []
        for i in self.items:
            if mode == 1 and i["type"] not in ("sys-unit",):
                continue
            if mode == 2 and i["type"] != "user-unit":
                continue
            if mode == 3 and i["type"] not in ("sys-desktop", "user-desktop"):
                continue
            if mode == 4 and not i["enabled"]:
                continue
            if mode == 5 and i["enabled"]:
                continue
            if q and q not in (i["name"] + " " + i["desc"] + " " + i["exec"] + " " +
                               i["path"] + " " + i["kind"]).lower():
                continue
            rows.append(i)
        s = self.f_sort.get_active()
        if s == 1:
            rows.sort(key=lambda x: (x["type"], x["name"].lower()))
        elif s == 2:
            rows.sort(key=lambda x: (not x["enabled"], x["name"].lower()))
        else:
            rows.sort(key=lambda x: x["name"].lower())
        self.filtered = rows
        self.store.clear()
        for i in rows:
            self.store.append([i["enabled"], i["name"], i["kind"],
                               i["path"] or i["exec"], i["desc"], i["key"]])

    def by_key(self, key):
        for i in self.items:
            if i["key"] == key:
                return i
        return None

    def selected(self):
        model, it = self.tv.get_selection().get_selected()
        if it is None:
            return None
        return self.by_key(model[it][5])

    def on_toggle(self, renderer, path):
        row = self.store[path]
        item = self.by_key(row[5])
        if item is None:
            return
        self.apply_toggle(item, not row[0])

    def toggle_selected(self):
        item = self.selected()
        if item:
            self.apply_toggle(item, not item["enabled"])

    def apply_toggle(self, item, on):
        if item["critical"] and not on:
            ui.dialog(self, "Это критичный компонент",
                      "%s — системный компонент, без которого мини-ПК может перестать "
                      "загружаться или потеряет доступ по сети.\n\nОтключение заблокировано."
                      % item["name"], ok="Понятно")
            return
        if on is False and item["type"] == "sys-unit" and item["name"] in SEVERITY_WARN:
            if not ui.dialog(self, "Выключить службу?",
                             "%s отвечает за одну из ваших функций (медиа, файлы, звук).\n"
                             "Её можно вернуть в любой момент этим же переключателем."
                             % item["name"], ok="Выключить", cancel=True):
                return
        backup_state(self.items)
        ok, msg = set_enabled(item, on)
        if not ok:
            ui.dialog(self, "Не получилось", msg or "Система отказала в операции", ok="Закрыть")
        else:
            C.notify("Автозагрузка", "%s — %s" % (item["name"], "включено" if on else "выключено"))
        self.reload()

    def on_select(self, sel):
        item = self.selected()
        if item is None:
            self.d_name.set_text("—")
            self.d_path.set_text("")
            self.d_exec.set_text("")
            self.d_info.set_text("")
            return
        self.d_name.set_text("%s  (%s)" % (item["name"], item["kind"]))
        self.d_path.set_text("Файл: " + item["path"])
        self.d_exec.set_text("Запуск: " + (item["exec"] or "—"))
        extra = ""
        if item["critical"]:
            extra = "  ⚠ критичный компонент — выключение заблокировано"
        self.d_info.set_text("Состояние: %s · тип: %s%s" % (
            "включено" if item["enabled"] else "выключено", item["type"], extra))
        self.b_toggle.set_label("Выключить" if item["enabled"] else "Включить")
        self.b_remove.set_sensitive(item["type"] == "user-desktop")
        self.b_open.set_sensitive(bool(item["path"]))

    def show_file(self):
        item = self.selected()
        if not item or not item["path"]:
            return
        C.run(["setsid", "mousepad", item["path"]], timeout=3)

    def remove_selected(self):
        item = self.selected()
        if not item or item["type"] != "user-desktop":
            return
        if not ui.dialog(self, "Удалить запись?",
                         "Файл <b>%s</b> будет удалён. Службы так не удаляются — "
                         "только пользовательские записи автозапуска." % item["path"],
                         ok="Удалить", cancel=True):
            return
        try:
            os.remove(item["path"])
            C.notify("Автозагрузка", "Запись удалена: %s" % item["name"])
        except Exception as e:
            ui.dialog(self, "Ошибка", str(e), ok="Закрыть")
        self.reload()

    def add_dialog(self):
        d = Gtk.Dialog(title="Добавить в автозагрузку", transient_for=self, modal=True)
        d.add_button("Отмена", Gtk.ResponseType.CANCEL)
        d.add_button("Добавить", Gtk.ResponseType.OK)
        box = d.get_content_area()
        box.set_spacing(8)
        box.set_margin_top(16)
        box.set_margin_bottom(16)
        box.set_margin_start(18)
        box.set_margin_end(18)
        e_name = ui.entry("", "Например: Мой плеер", width=320)
        e_cmd = ui.entry("", "Например: vlc --started-from-file", width=320)
        e_cmt = ui.entry("", "Что это за программа", width=320)
        box.add(ui.row("Название", e_name))
        box.add(ui.row("Команда запуска", e_cmd))
        box.add(ui.row("Описание", e_cmt))
        box.add(Gtk.Label(label="Запись появится в ~/.config/autostart и сработает "
                                "при входе в систему.",
                          xalign=0))
        d.show_all()
        r = d.run()
        name, cmd, cmt = e_name.get_text().strip(), e_cmd.get_text().strip(), e_cmt.get_text().strip()
        d.destroy()
        if r != Gtk.ResponseType.OK:
            return
        if not name or not cmd:
            ui.dialog(self, "Не хватает данных", "Нужны и название, и команда запуска.", ok="Закрыть")
            return
        path = add_custom(name, cmd, cmt)
        C.notify("Автозагрузка", "Добавлено: %s" % path)
        self.reload()

    def restore_backup(self):
        if not os.path.exists(BACKUP):
            ui.dialog(self, "Резервной копии нет",
                      "Копия создаётся автоматически перед первым изменением.", ok="Закрыть")
            return
        data = json.load(open(BACKUP))
        if not ui.dialog(self, "Откатить изменения?",
                         "Состояние автозагрузки будет возвращено к копии от <b>%s</b>.\n"
                         "Будет обработано записей: %d." % (data["time"], len(data["items"])),
                         ok="Откатить", cancel=True):
            return
        items = {i["key"]: i for i in self.items}
        fixed = 0
        for key, want in data["items"].items():
            it = items.get(key)
            if it and it["enabled"] != want and not (it["critical"] and not want):
                set_enabled(it, want)
                fixed += 1
        C.notify("Автозагрузка", "Откат выполнен, изменено записей: %d" % fixed)
        self.reload()


def main():
    ui.load_css()
    w = AutostartWindow()
    w.show_all()
    Gtk.main()


if __name__ == "__main__":
    main()

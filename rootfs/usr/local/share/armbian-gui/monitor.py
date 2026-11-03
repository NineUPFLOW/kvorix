#!/usr/bin/env python3

import os
import time

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, GLib, Gtk

import common as C
import ui


class Spark(Gtk.DrawingArea):
    

    def __init__(self, color="#38bdf8", points=60, height=48):
        super().__init__()
        self.vals = [0.0] * points
        self.color = color
        self.set_size_request(-1, height)
        self.connect("draw", self._draw)

    def push(self, v):
        self.vals.append(max(0.0, min(1.0, v)))
        self.vals = self.vals[-len(self.vals):]
        self.queue_draw()

    def _draw(self, w, cr):
        a = w.get_allocation()
        ww, hh = a.width, a.height
        cr.set_source_rgba(0, 0, 0, 0)
        cr.paint()
        n = len(self.vals)
        if n < 2:
            return
        step = ww / float(n - 1)
        pts = [(i * step, hh - self.vals[i] * (hh - 6) - 3) for i in range(n)]
        cr.move_to(0, hh)
        for x, y in pts:
            cr.line_to(x, y)
        cr.line_to(ww, hh)
        cr.close_path()
        g = Gdk.RGBA()
        g.parse(self.color)
        g.alpha = 0.16
        cr.set_source_rgba(g.red, g.green, g.blue, g.alpha)
        cr.fill()
        cr.move_to(*pts[0])
        for p in pts[1:]:
            cr.line_to(*p)
        cr.set_source_rgba(g.red, g.green, g.blue, 1.0)
        cr.set_line_width(1.8)
        cr.stroke()


class Monitor(Gtk.Window):
    def __init__(self):
        super().__init__(title="Системный монитор — Armbian TV")
        self.set_default_size(1040, 566)
        self.set_icon_name("utilities-system-monitor")
        self.prev_cpu = C.cpu_times()
        self.prev_net = C.net_bytes()
        self.prev_procs = None
        self.t0 = time.time()

        hb = Gtk.HeaderBar(show_close_button=True)
        hb.set_title("Системный монитор")
        hb.set_subtitle("Armbian TV · S905X3")
        hb.pack_end(ui.button("Центр управления", self.open_center, "btn", "preferences-system"))
        hb.pack_start(ui.button("Терминал", self.open_term, "ghost", "utilities-terminal"))
        self.set_titlebar(hb)

        grid = Gtk.Grid(column_spacing=12, row_spacing=12)
        grid.set_margin_top(16)
        grid.set_margin_bottom(16)
        grid.set_margin_start(16)
        grid.set_margin_end(16)
        grid.set_column_homogeneous(True)

        c_cpu = ui.Card("Процессор")
        self.l_cpu = Gtk.Label(label="—", xalign=0)
        self.l_cpu.get_style_context().add_class("dash-big")
        c_cpu.add(self.l_cpu)
        self.l_cpu_sub = Gtk.Label(label="", xalign=0)
        self.l_cpu_sub.get_style_context().add_class("muted")
        self.l_cpu_sub.set_line_wrap(True)
        self.l_cpu_sub.set_max_width_chars(30)
        c_cpu.add(self.l_cpu_sub)
        self.sp_cpu = Spark("#38bdf8")
        c_cpu.add(self.sp_cpu)

        c_ram = ui.Card("Оперативная память")
        self.l_ram = Gtk.Label(label="—", xalign=0)
        self.l_ram.get_style_context().add_class("dash-big")
        c_ram.add(self.l_ram)
        self.p_ram = ui.progress(0)
        c_ram.add(self.p_ram)
        self.l_ram_sub = Gtk.Label(label="", xalign=0)
        self.l_ram_sub.get_style_context().add_class("muted")
        self.l_ram_sub.set_line_wrap(True)
        self.l_ram_sub.set_max_width_chars(30)
        c_ram.add(self.l_ram_sub)

        c_tmp = ui.Card("Температура")
        self.tmp_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        c_tmp.add(self.tmp_box)

        c_disk = ui.Card("Накопители")
        self.disk_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        c_disk.add(self.disk_box)

        c_net = ui.Card("Сеть")
        self.l_net = Gtk.Label(label="—", xalign=0)
        self.l_net.get_style_context().add_class("dash-big")
        c_net.add(self.l_net)
        self.sp_net = Spark("#22d3ee")
        c_net.add(self.sp_net)
        self.l_net_sub = Gtk.Label(label="", xalign=0)
        self.l_net_sub.get_style_context().add_class("muted")
        self.l_net_sub.set_line_wrap(True)
        self.l_net_sub.set_max_width_chars(30)
        c_net.add(self.l_net_sub)

        c_sys = ui.Card("Система")
        self.sys_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        c_sys.add(self.sys_box)

        grid.attach(c_cpu, 0, 0, 1, 1)
        grid.attach(c_ram, 1, 0, 1, 1)
        grid.attach(c_tmp, 2, 0, 1, 1)
        grid.attach(c_disk, 0, 1, 1, 1)
        grid.attach(c_net, 1, 1, 1, 1)
        grid.attach(c_sys, 2, 1, 1, 1)

        procs = ui.Card("Процессы")
        self.store = Gtk.ListStore(str, str, str, str)
        tv = Gtk.TreeView(model=self.store)
        for i, (name, title, width) in enumerate([("pid", "PID", 70), ("name", "Имя", 220),
                                                  ("cpu", "CPU", 90), ("ram", "ПАМЯТЬ", 100)]):
            r = Gtk.CellRendererText(xalign=1 if i > 1 else 0)
            col = Gtk.TreeViewColumn(title, r, text=i)
            col.set_fixed_width(width)
            col.set_expand(i == 1)
            tv.append_column(col)
        tv.get_style_context().add_class("procview")
        sw = Gtk.ScrolledWindow()
        sw.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        sw.set_min_content_height(130)
        sw.add(tv)
        procs.add(sw)
        btns = Gtk.Box(spacing=8)
        btns.pack_start(ui.button("Завершить процесс", lambda: self.kill_selected(tv), "danger",
                                  "process-stop"), False, False, 0)
        btns.pack_end(ui.button("Открыть центр управления", self.open_center, "ghost"), False, False, 0)
        procs.add(btns)

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        outer.pack_start(grid, False, False, 0)
        outer.pack_start(procs, True, True, 0)
        outer.set_margin_start(16)
        outer.set_margin_end(16)
        outer.set_margin_bottom(16)
        self.add(ui.fit(outer))

        self.tick()
        GLib.timeout_add(1000, self.tick)
        self.connect("destroy", Gtk.main_quit)

    def open_center(self):
        C.run(["setsid", "armbian-center"], timeout=3)

    def open_term(self):
        C.run(["setsid", "xfce4-terminal"], timeout=3)

    def kill_selected(self, tv):
        model, it = tv.get_selection().get_selected()
        if it is None:
            return
        pid, name = model[it][0], model[it][1]
        if not ui.dialog(self, "Завершить процесс?",
                         "Процесс <b>%s</b> (PID %s) будет остановлен." % (name, pid),
                         ok="Завершить", cancel=True):
            return
        C.sudo(["kill", "-TERM", pid])
        C.notify("Процесс завершён", "%s (PID %s)" % (name, pid))

    def tick(self):
        busy, total = C.cpu_times()
        pb, pt = self.prev_cpu
        pct = 0.0
        if total - pt > 0:
            pct = 100.0 * (busy - pb) / (total - pt)
        self.prev_cpu = (busy, total)
        self.l_cpu.set_text("%.0f %%" % pct)
        self.l_cpu_sub.set_text("%d ядра · %d МГц · режим %s · LA %s" % (
            os.cpu_count() or 0, C.cpu_cur_mhz(), C.cpu_governor(), " ".join(C.loadavg()[:3])))
        self.sp_cpu.push(pct / 100.0)

        tot, used, avail = C.ram()
        self.l_ram.set_text("%.0f %%" % (100.0 * used / max(1, tot)))
        self.p_ram.set_fraction(used / float(max(1, tot)))
        st, su = C.swap()
        self.l_ram_sub.set_text("%d из %d МБ занято · свободно %d МБ · подкачка %d/%d МБ" % (
            used, tot, avail, su, st))

        for ch in self.tmp_box.get_children():
            ch.destroy()
        for name, val in C.temps():
            r = Gtk.Box(spacing=8)
            lab = Gtk.Label(label=name, xalign=0)
            lab.set_hexpand(True)
            v = Gtk.Label(label="%.0f °C" % val, xalign=1)
            v.get_style_context().add_class("value")
            r.pack_start(lab, True, True, 0)
            r.pack_end(v, False, False, 0)
            self.tmp_box.pack_start(r, False, False, 0)
        self.tmp_box.show_all()

        for ch in self.disk_box.get_children():
            ch.destroy()
        for d in C.disks()[:3]:
            r = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
            top = Gtk.Box(spacing=8)
            lab = Gtk.Label(label=d["mount"], xalign=0)
            lab.set_hexpand(True)
            v = Gtk.Label(label="%s свободно из %s" % (C.human_bytes(d["free"]),
                                                       C.human_bytes(d["total"])), xalign=1)
            v.get_style_context().add_class("value")
            top.pack_start(lab, True, True, 0)
            top.pack_end(v, False, False, 0)
            r.pack_start(top, False, False, 0)
            r.pack_start(ui.progress(d["pct"] / 100.0), False, False, 0)
            self.disk_box.pack_start(r, False, False, 0)
        self.disk_box.show_all()

        rx, tx = C.net_bytes()
        prx, ptx = self.prev_net
        self.prev_net = (rx, tx)
        sp = ((rx - prx) + (tx - ptx)) / 1024.0
        info = C.net_info()
        self.l_net.set_text("%.0f КБ/с" % max(0.0, sp))
        self.l_net_sub.set_text("%s · %s%s%s" % (info["dev"], info["ip"],
                                                 " · " + info["link"] if info["link"] else "",
                                                 " · " + info["signal"] if info["signal"] else ""))
        self.sp_net.push(min(1.0, max(0.0, sp) / 2000.0))

        for ch in self.sys_box.get_children():
            ch.destroy()
        rows = [("Ядро", C.read("/proc/sys/kernel/osrelease", "—")),
                ("Работает", C.uptime()),
                ("Устройство", "Tanix TX3 (S905X3)"),
                ("Пользователь", C.USER),
                ("Служба автозапуска", "xfce4-session")]
        for k, v in rows:
            r = Gtk.Box(spacing=8)
            lab = Gtk.Label(label=k, xalign=0)
            lab.set_hexpand(True)
            val = Gtk.Label(label=v, xalign=1)
            val.get_style_context().add_class("value")
            r.pack_start(lab, True, True, 0)
            r.pack_end(val, False, False, 0)
            self.sys_box.pack_start(r, False, False, 0)
        self.sys_box.show_all()

        procs = C.top_procs(10)
        self.store.clear()
        for p in procs:
            self.store.append([p["pid"], p["name"], "%.1f %%" % p["cpu"],
                               C.human_kb(p["rss"])])
        return True


def main():
    ui.load_css()
    win = Monitor()
    win.show_all()
    Gtk.main()


if __name__ == "__main__":
    main()

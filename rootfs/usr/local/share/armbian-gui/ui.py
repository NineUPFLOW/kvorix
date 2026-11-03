
import os

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, Gtk

from common import GUI_DIR


def _ic(name):
    """Однотонный (symbolic) вариант значка, если он есть в теме: единый вид, как в Windows 11 / Android."""
    if name and not name.endswith("-symbolic") and Gtk.IconTheme.get_default().has_icon(name + "-symbolic"):
        return name + "-symbolic"
    return name


_CSS = {}


def load_css(extra=""):
    
    old = _CSS.get("p")
    css = Gtk.CssProvider()
    user = os.path.expanduser("~/.config/rsaarm/center.css")
    path = user if os.path.exists(user) else os.path.join(GUI_DIR, "style.css")
    data = ""
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            data = f.read()
    css.load_from_data((data + extra).encode())
    scr = Gdk.Screen.get_default()
    if old:
        Gtk.StyleContext.remove_provider_for_screen(scr, old)
    Gtk.StyleContext.add_provider_for_screen(scr, css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
    _CSS["p"], _CSS["extra"] = css, extra


def reload_css():
    load_css(_CSS.get("extra", ""))


def _lbl(text, cls=None, wrap=False):
    l = Gtk.Label(label=text, xalign=0)
    l.set_line_wrap(wrap)
    if cls:
        l.get_style_context().add_class(cls)
    return l


def spacer(w=0, h=0, expand=False):
    b = Gtk.Box()
    b.set_size_request(w, h)
    if expand:
        b.set_hexpand(True)
    return b


class Card(Gtk.Box):
    

    def __init__(self, title=None, subtitle=None, icon=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.get_style_context().add_class("card")
        self.set_margin_bottom(12)
        if title:
            head = Gtk.Box(spacing=8)
            head.get_style_context().add_class("card-head")
            if icon:
                img = Gtk.Image.new_from_icon_name(_ic(icon), Gtk.IconSize.MENU)
                head.pack_start(img, False, False, 0)
            head.pack_start(_lbl(title, "card-title"), False, False, 0)
            self.pack_start(head, False, False, 0)
        if subtitle:
            self.pack_start(_lbl(subtitle, "muted", wrap=True), False, False, 0)
        self.body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.pack_start(self.body, False, False, 0)

    def add(self, w):
        self.body.pack_start(w, False, False, 0)
        return w


def row(label, widget=None, sub=None):
    
    b = Gtk.Box(spacing=12)
    b.get_style_context().add_class("row")
    text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
    head = _lbl(label, "row-label")
    head.set_ellipsize(3)
    head.set_max_width_chars(48)
    text.pack_start(head, False, False, 0)
    if sub:
        text.pack_start(_lbl(sub, "muted", wrap=True), False, False, 0)
    b.pack_start(text, True, True, 0)
    if widget is not None:
        b.pack_end(widget, False, False, 0)
    return b


def info_row(label, value_getter, cls="value"):
    
    v = Gtk.Label(xalign=1)
    v.get_style_context().add_class(cls)
    v.set_selectable(True)
    v.set_ellipsize(3)
    v.set_max_width_chars(46)

    def refresh():
        txt = value_getter() if callable(value_getter) else str(value_getter)
        txt = txt.replace("\n", " ")
        v.set_text(txt)
        v.set_tooltip_text(txt)

    refresh()
    b = row(label, v)
    b.refresh = refresh
    return b


def switch(active, on_toggle, sensitive=True):
    s = Gtk.Switch()
    s.set_active(bool(active))
    s.set_valign(Gtk.Align.CENTER)
    s.set_sensitive(sensitive)
    busy = {"v": False}

    def changed(w, state):
        if busy["v"]:
            return
        busy["v"] = True
        try:
            ok = on_toggle(state)
            if ok is False:
                s.set_active(not state)
        finally:
            busy["v"] = False

    s.connect("state-set", lambda w, st: (changed(w, st), False)[1])
    return s


def button(text, cb, cls="btn", icon=None, sensitive=True):
    b = Gtk.Button(label=text)
    b.get_style_context().add_class(cls)
    b.set_sensitive(sensitive)
    if icon:
        b.set_image(Gtk.Image.new_from_icon_name(_ic(icon), Gtk.IconSize.BUTTON))
        b.set_always_show_image(True)
    b.connect("clicked", lambda *_: cb())
    return b


def entry(text="", hint="", password=False, width=220):
    e = Gtk.Entry(text=text, placeholder_text=hint)
    e.set_visibility(not password)
    e.set_width_chars(16)
    e.set_size_request(width, -1)
    return e


def slider(lo, hi, step, value, on_change, marks=None):
    s = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, lo, hi, step)
    s.set_value(value)
    s.set_draw_value(True)
    s.set_size_request(240, -1)
    s.connect("value-changed", lambda w: on_change(w.get_value()))
    return s


def combo(options, current_index, on_change):
    c = Gtk.ComboBoxText()
    for o in options:
        c.append_text(o)
    c.set_active(current_index if current_index is not None and 0 <= current_index < len(options) else 0)
    c.connect("changed", lambda w: on_change(w.get_active(), w.get_active_text()))
    return c


def pill(text, kind="ok"):
    l = Gtk.Label(label=text)
    l.get_style_context().add_class("pill")
    l.get_style_context().add_class("pill-" + kind)
    return l


def hline():
    s = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
    s.get_style_context().add_class("hline")
    return s


class Page(Gtk.ScrolledWindow):
    

    def __init__(self, title, subtitle=None):
        super().__init__()
        self.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        box.set_margin_top(20)
        box.set_margin_bottom(24)
        box.set_margin_start(26)
        box.set_margin_end(26)
        t = _lbl(title, "page-title")
        box.pack_start(t, False, False, 0)
        if subtitle:
            box.pack_start(_lbl(subtitle, "page-sub", wrap=True), False, False, 0)
        box.pack_start(spacer(h=10), False, False, 0)
        self.content = box
        Gtk.ScrolledWindow.add(self, box)

    def add(self, w):
        self.content.pack_start(w, False, False, 0)
        return w

    def card(self, *a, **kw):
        c = Card(*a, **kw)
        self.add(c)
        return c


def header(title, subtitle=None):
    b = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
    b.pack_start(_lbl(title, "header-title"), False, False, 0)
    if subtitle:
        b.pack_start(_lbl(subtitle, "header-sub"), False, False, 0)
    return b


def dialog(parent, title, text, ok="Понятно", cancel=None):
    d = Gtk.MessageDialog(transient_for=parent, modal=True,
                          message_type=Gtk.MessageType.QUESTION if cancel else Gtk.MessageType.INFO,
                          buttons=Gtk.ButtonsType.NONE)
    d.set_markup("<b>%s</b>\n\n%s" % (title, text))
    d.add_button("Отмена" if cancel else ok, Gtk.ResponseType.CANCEL)
    if cancel:
        d.add_button(ok, Gtk.ResponseType.OK)
    r = d.run()
    d.destroy()
    return r == Gtk.ResponseType.OK or not cancel


def ask_text(parent, title, label, password=False, default=""):
    d = Gtk.Dialog(title=title, transient_for=parent, modal=True)
    d.add_button("Отмена", Gtk.ResponseType.CANCEL)
    d.add_button("Применить", Gtk.ResponseType.OK)
    d.set_default_response(Gtk.ResponseType.OK)
    box = d.get_content_area()
    box.set_spacing(8)
    box.set_margin_top(14)
    box.set_margin_bottom(14)
    box.set_margin_start(16)
    box.set_margin_end(16)
    box.add(_lbl(label, "muted"))
    e = entry(default, password=password, width=280)
    box.add(e)
    d.show_all()
    r = d.run()
    val = e.get_text()
    d.destroy()
    return val if r == Gtk.ResponseType.OK else None


def ask_choice(parent, title, label, options):
    
    d = Gtk.Dialog(title=title, transient_for=parent, modal=True)
    d.add_button("Отмена", Gtk.ResponseType.CANCEL)
    d.add_button("Готово", Gtk.ResponseType.OK)
    box = d.get_content_area()
    box.set_spacing(8)
    box.set_margin_top(14)
    box.set_margin_bottom(14)
    box.set_margin_start(16)
    box.set_margin_end(16)
    box.add(_lbl(label, "muted"))
    c = Gtk.ComboBoxText()
    for o in options:
        c.append_text(o)
    c.set_active(0)
    c.set_size_request(320, -1)
    box.add(c)
    d.show_all()
    r = d.run()
    idx = c.get_active()
    d.destroy()
    return idx if r == Gtk.ResponseType.OK else None


def progress(fraction):
    p = Gtk.ProgressBar()
    p.set_fraction(max(0.0, min(1.0, fraction)))
    p.set_size_request(-1, 8)
    return p


def fit(box):
    
    sw = Gtk.ScrolledWindow()
    sw.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
    sw.set_propagate_natural_width(False)
    sw.set_propagate_natural_height(False)
    sw.add(box)
    return sw


def refresh_tree(widget):
    
    if hasattr(widget, "refresh"):
        widget.refresh()
    if isinstance(widget, Gtk.Container):
        for ch in widget.get_children():
            refresh_tree(ch)

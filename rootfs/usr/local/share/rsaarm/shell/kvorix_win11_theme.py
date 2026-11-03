#!/usr/bin/env python3

import math
import os
import cairo


def _hex(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


def _save(surf, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    surf.write_to_png(path)


def build_xfwm4(dest_dir, dark=False):
    os.makedirs(dest_dir, exist_ok=True)
    bg_act = _hex("#20242f" if dark else "#f3f5fa")
    bg_inact = _hex("#1a1d26" if dark else "#ebedf4")
    border_act = _hex("#343b4d" if dark else "#cfd5e2")
    border_inact = _hex("#282d3b" if dark else "#d8dde8")
    fg_act = _hex("#eef1f8" if dark else "#1c2130")
    fg_inact = _hex("#7d8597" if dark else "#8a92a3")
    hover_bg = (1, 1, 1, 0.10) if dark else (0, 0, 0, 0.07)
    press_bg = (1, 1, 1, 0.16) if dark else (0, 0, 0, 0.13)

    H = 30
    BW = 42

    for state, bg, brd in (("active", bg_act, border_act), ("inactive", bg_inact, border_inact)):
        s = cairo.ImageSurface(cairo.FORMAT_ARGB32, 8, H)
        cr = cairo.Context(s)
        cr.set_source_rgba(*bg, 1.0)
        cr.paint()
        cr.set_source_rgba(*brd, 1.0)
        cr.rectangle(0, 0, 8, 1)
        cr.fill()
        for i in range(1, 6):
            _save(s, os.path.join(dest_dir, f"title-{i}-{state}.png"))

    R = 8
    for side in ("left", "right"):
        for state, bg, brd in (("active", bg_act, border_act), ("inactive", bg_inact, border_inact)):
            s = cairo.ImageSurface(cairo.FORMAT_ARGB32, R, H)
            cr = cairo.Context(s)
            cr.set_operator(cairo.OPERATOR_CLEAR)
            cr.paint()
            cr.set_operator(cairo.OPERATOR_OVER)
            cr.new_path()
            if side == "left":
                cr.arc(R, R, R, math.pi, 1.5 * math.pi)
                cr.line_to(R, 0)
                cr.line_to(R, H)
                cr.line_to(0, H)
            else:
                cr.arc(0, R, R, 1.5 * math.pi, 2.0 * math.pi)
                cr.line_to(R, H)
                cr.line_to(0, H)
            cr.close_path()
            cr.set_source_rgba(*bg, 1.0)
            cr.fill_preserve()
            cr.set_line_width(1.2)
            cr.set_source_rgba(*brd, 1.0)
            cr.stroke()
            cr.set_source_rgba(*brd, 1.0)
            if side == "left":
                cr.rectangle(0, R, 1, H - R)
            else:
                cr.rectangle(R - 1, R, 1, H - R)
            cr.fill()
            _save(s, os.path.join(dest_dir, f"top-{side}-{state}.png"))

    for state, brd, bg in (("active", border_act, bg_act), ("inactive", border_inact, bg_inact)):
        for side in ("left", "right"):
            s = cairo.ImageSurface(cairo.FORMAT_ARGB32, 2, 16)
            cr = cairo.Context(s)
            cr.set_source_rgba(*bg, 1.0)
            cr.paint()
            cr.set_source_rgba(*brd, 1.0)
            cr.rectangle(0 if side == "left" else 1, 0, 1, 16)
            cr.fill()
            _save(s, os.path.join(dest_dir, f"{side}-{state}.png"))
        s = cairo.ImageSurface(cairo.FORMAT_ARGB32, 16, 2)
        cr = cairo.Context(s)
        cr.set_source_rgba(*bg, 1.0)
        cr.paint()
        cr.set_source_rgba(*brd, 1.0)
        cr.rectangle(0, 1, 16, 1)
        cr.fill()
        _save(s, os.path.join(dest_dir, f"bottom-{state}.png"))
        for side in ("left", "right"):
            sc = cairo.ImageSurface(cairo.FORMAT_ARGB32, 4, 4)
            crc = cairo.Context(sc)
            crc.set_source_rgba(*brd, 1.0)
            crc.paint()
            _save(sc, os.path.join(dest_dir, f"bottom-{side}-{state}.png"))

    def make_btn(glyph, state):
        s = cairo.ImageSurface(cairo.FORMAT_ARGB32, BW, H)
        cr = cairo.Context(s)
        base_bg = bg_inact if state == "inactive" else bg_act
        cr.set_source_rgba(*base_bg, 1.0)
        cr.paint()
        brd = border_inact if state == "inactive" else border_act
        cr.set_source_rgba(*brd, 1.0)
        cr.rectangle(0, 0, BW, 1)
        cr.fill()

        fg = fg_inact if state == "inactive" else fg_act
        if glyph == "close" and state in ("prelight", "pressed"):
            red = _hex("#b02417" if state == "pressed" else "#c42b1c")
            cr.set_source_rgba(*red, 1.0)
            if glyph == "close":
                cr.rectangle(0, 1, BW, H - 1)
                cr.fill()
            fg = (1.0, 1.0, 1.0)
        elif state == "prelight":
            cr.set_source_rgba(*hover_bg)
            cr.rectangle(0, 1, BW, H - 1)
            cr.fill()
        elif state == "pressed":
            cr.set_source_rgba(*press_bg)
            cr.rectangle(0, 1, BW, H - 1)
            cr.fill()

        cx, cy = BW / 2.0, H / 2.0 + 0.5
        cr.set_source_rgba(*fg, 1.0)
        cr.set_line_width(1.25)
        cr.set_line_cap(cairo.LINE_CAP_ROUND)
        cr.set_line_join(cairo.LINE_JOIN_ROUND)

        if glyph == "hide":
            cr.move_to(cx - 5, int(cy) + 0.5)
            cr.line_to(cx + 5, int(cy) + 0.5)
            cr.stroke()
        elif glyph == "maximize":
            cr.rectangle(int(cx - 4.5) + 0.5, int(cy - 4.5) + 0.5, 9.0, 9.0)
            cr.stroke()
        elif glyph == "maximize-toggled":
            cr.rectangle(int(cx - 5) + 0.5, int(cy - 3) + 0.5, 7.5, 7.5)
            cr.stroke()
            cr.move_to(int(cx - 3) + 0.5, int(cy - 3) + 0.5)
            cr.line_to(int(cx - 3) + 0.5, int(cy - 5) + 0.5)
            cr.line_to(int(cx + 5) + 0.5, int(cy - 5) + 0.5)
            cr.line_to(int(cx + 5) + 0.5, int(cy + 3) + 0.5)
            cr.line_to(int(cx + 3) + 0.5, int(cy + 3) + 0.5)
            cr.stroke()
        elif glyph == "close":
            cr.set_line_width(1.35)
            cr.move_to(cx - 4.5, cy - 4.5)
            cr.line_to(cx + 4.5, cy + 4.5)
            cr.move_to(cx + 4.5, cy - 4.5)
            cr.line_to(cx - 4.5, cy + 4.5)
            cr.stroke()
        return s

    for glyph in ("hide", "maximize", "maximize-toggled", "close"):
        for st in ("active", "inactive", "prelight", "pressed"):
            _save(make_btn(glyph, st), os.path.join(dest_dir, f"{glyph}-{st}.png"))

    for st, bg, brd in (("active", bg_act, border_act), ("inactive", bg_inact, border_inact), ("pressed", bg_act, border_act)):
        s = cairo.ImageSurface(cairo.FORMAT_ARGB32, 26, H)
        cr = cairo.Context(s)
        cr.set_source_rgba(*bg, 1.0)
        cr.paint()
        cr.set_source_rgba(*brd, 1.0)
        cr.rectangle(0, 0, 26, 1)
        cr.fill()
        _save(s, os.path.join(dest_dir, f"menu-{st}.png"))

    themerc = """button_offset=0
button_spacing=0
show_app_icon=true
full_width_title=true
title_shadow_active=false
title_shadow_inactive=false
title_horizontal_offset=6
title_vertical_offset_active=1
title_vertical_offset_inactive=1
active_text_color={act_fg}
active_text_shadow_color={act_bg}
inactive_text_color={inact_fg}
inactive_text_shadow_color={inact_bg}
shadow_delta_height=2
shadow_delta_width=0
shadow_delta_x=0
shadow_delta_y=-5
shadow_opacity=35
frame_border_top=2
""".format(
        act_fg="#eef1f8" if dark else "#1c2130",
        act_bg="#20242f" if dark else "#f3f5fa",
        inact_fg="#7d8597" if dark else "#7c8496",
        inact_bg="#1a1d26" if dark else "#ebedf4",
    )
    with open(os.path.join(dest_dir, "themerc"), "w", encoding="utf-8") as f:
        f.write(themerc)


if __name__ == "__main__":
    build_xfwm4("/usr/share/themes/Kvorix/xfwm4", dark=False)
    build_xfwm4("/usr/share/themes/Kvorix-Dark/xfwm4", dark=True)
    print("Windows 11 xfwm4 themes built successfully.")

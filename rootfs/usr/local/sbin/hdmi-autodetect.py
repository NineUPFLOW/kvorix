#!/usr/bin/env python3

import fcntl
import glob
import hashlib
import json
import os
import pwd
import subprocess
import time

I2C, ADDR = "/dev/i2c-0", 0x50
OVERRIDE = glob.glob("/sys/kernel/debug/dri/*/HDMI-A-1/edid_override")
STATUS = glob.glob("/sys/class/drm/card*-HDMI-A-1/status")
CHOICE_DIR = "/var/lib/hdmi-autodetect"
HEADER = b"\x00\xff\xff\xff\xff\xff\xff\x00"

FIT_TIMINGS = {
    "1360x768": (1360, 1424, 1536, 1792, 768, 771, 777, 795),
    "1280x720": (1280, 1390, 1430, 1650, 720, 725, 730, 750),
    "1920x1080": (1920, 2008, 2052, 2200, 1080, 1084, 1089, 1125),
}


def read_edid():
    try:
        fd = os.open(I2C, os.O_RDWR)
    except OSError:
        return None
    try:
        fcntl.ioctl(fd, 0x0703, ADDR)
        os.write(fd, b"\x00")
        e = os.read(fd, 128)
        if len(e) != 128 or not e.startswith(HEADER) or sum(e) % 256:
            return None
        n = min(e[126], 1)
        if n:
            os.write(fd, b"\x00")
            full = os.read(fd, 256)
            ext = full[128:256]
            if len(ext) == 128 and sum(ext) % 256 == 0 and not ext.startswith(HEADER) and full[:128] == e:
                return e + ext
            e = bytearray(e)
            e[126] = 0
            e[127] = (-sum(e[:127])) % 256
            e = bytes(e)
        return e
    except OSError:
        return None
    finally:
        os.close(fd)


def x_session():
    
    out = subprocess.run(["loginctl", "list-sessions", "--no-legend"], capture_output=True, text=True).stdout
    for line in out.splitlines():
        f = line.split()
        if len(f) >= 4 and f[3] == "seat0":
            p = pwd.getpwnam(f[2])
            env = dict(os.environ, DISPLAY=":0", HOME=p.pw_dir, USER=p.pw_name,
                       XAUTHORITY=os.path.join(p.pw_dir, ".Xauthority"),
                       XDG_RUNTIME_DIR="/run/user/%d" % p.pw_uid,
                       DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/%d/bus" % p.pw_uid)
            return p, env
    return None, None


def as_user(p, env, cmd):
    # служба идёт с Nice=10 — без сброса панель и меню наследуют низкий приоритет и тормозят
    return subprocess.run(["runuser", "-u", p.pw_name, "--", "sh", "-c", cmd], env=env,
                          capture_output=True, text=True, timeout=30,
                          preexec_fn=lambda: os.setpriority(os.PRIO_PROCESS, 0, 0))


def kernel_edid():
    try:
        return open(glob.glob("/sys/class/drm/card*-HDMI-A-1/edid")[0], "rb").read()
    except (OSError, IndexError):
        return b""


def expected_fit_mode(home_dir):
    cfg = {"base_mode": "1360x768", "h_shift": 0, "v_shift": 0}
    try:
        with open(os.path.join(home_dir, ".config/armbian-tv/screen-fit.json"), encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            cfg.update(data)
    except (OSError, ValueError):
        pass
    base = cfg.get("base_mode", "1360x768")
    if base not in FIT_TIMINGS:
        return base
    hd, hss, hse, htot, vd, vss, vse, vtot = FIT_TIMINGS[base]
    hs, vs = int(cfg.get("h_shift", 0)), int(cfg.get("v_shift", 0))
    sync_w, vsync_w = hse - hss, vse - vss
    new_hss = max(hd + 8, min(htot - sync_w - 8, hss - hs))
    new_vss = max(vd + 1, min(vtot - vsync_w - 1, vss - vs))
    return "%s_fit_%d_%d" % (base, new_hss, new_vss)


def parse_xrandr(xr_text):
    out, cur_mode, pref_mode = "HDMI-1", "", ""
    in_conn = False
    for line in xr_text.splitlines():
        if " connected" in line:
            out = line.split()[0]
            in_conn = True
            continue
        if in_conn and line and not line[0].isspace():
            in_conn = False
        if in_conn and line.startswith(" "):
            parts = line.split()
            if not parts:
                continue
            m = parts[0]
            if "*" in line and not cur_mode:
                cur_mode = m
            if "+" in line and not pref_mode:
                pref_mode = m
    return out, cur_mode, pref_mode


def apply(edid, key):
    same_edid = (kernel_edid() == edid)
    if not same_edid:
        for f in OVERRIDE:
            open(f, "wb").write(edid)
        for f in STATUS:
            open(f, "w").write("on")
        p0, env0 = x_session()
        if p0:
            as_user(p0, env0, "O=$(xrandr | awk '/ connected/{print $1; exit}'); xrandr --output ${O:-HDMI-1} --off; sleep 1")
    p, env = x_session()
    if not p:
        return "нет графического сеанса"
    choice = ""
    try:
        choice = open(os.path.join(CHOICE_DIR, key)).read().strip()
    except OSError:
        pass
    xr = as_user(p, env, "xrandr --query").stdout
    if not xr.strip():
        return "нет графического сеанса"
    out, cur_mode, pref_mode = parse_xrandr(xr)
    if choice == "fit":
        want_mode = expected_fit_mode(p.pw_dir)
    elif choice:
        want_mode = choice
    else:
        want_mode = pref_mode

    if same_edid and want_mode and cur_mode == want_mode:
        return "%s (уже активен)" % cur_mode

    if choice == "fit":
        as_user(p, env, "armbian-screen-fit --apply")
    elif choice:
        as_user(p, env, "armbian-display-auto --modes-only; xrandr --output %s --mode %s" % (out, choice))
    else:
        as_user(p, env, "xrandr --output %s --auto" % out)

    xr_after = as_user(p, env, "xrandr --query").stdout
    _, new_mode, _ = parse_xrandr(xr_after)
    if new_mode != cur_mode or not same_edid:
        # своя scope в сеансе пользователя: иначе панель в cgroup службы и гибнет при её перезапуске
        as_user(p, env, "systemd-run --user --scope -q sh -c '/usr/local/bin/kvorix-restart-panel; "
                        "/usr/local/bin/kvorix-restart-menu' >/dev/null 2>&1 || "
                        "{ /usr/local/bin/kvorix-restart-panel; /usr/local/bin/kvorix-restart-menu; } >/dev/null 2>&1; true")
    return new_mode or cur_mode or "режим не определён"


def main():
    os.makedirs(CHOICE_DIR, exist_ok=True)
    os.chmod(CHOICE_DIR, 0o1777)
    last = None
    saved = os.path.join(CHOICE_DIR, "last.edid")
    while True:
        e = read_edid()
        if not e and last is None and os.path.exists(saved) and x_session()[0]:
            e = open(saved, "rb").read()
        if e:
            key = hashlib.sha1(e[:128]).hexdigest()[:12]
            open("/run/hdmi-monitor", "w").write(key)
            if key != last:
                res = apply(e, key)
                print("монитор %s: %s" % (key, res), flush=True)
                if res != "нет графического сеанса":
                    last = key
                open(saved, "wb").write(e)
        time.sleep(3)


if __name__ == "__main__":
    main()

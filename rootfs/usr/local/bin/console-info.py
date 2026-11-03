#!/usr/bin/env python3
import shutil
import subprocess
import time
import os

R = "\033[0m"
DIM = "\033[38;5;242m"
VAL = "\033[38;5;252m"
LBL = "\033[38;5;245m"
ACC = "\033[38;5;79m"
TIT = "\033[38;5;110m"
OK = "\033[38;5;114m"
WARN = "\033[38;5;179m"
ERR = "\033[38;5;203m"
BOLD = "\033[1m"


def sh(cmd, default=""):
    try:
        return subprocess.run(cmd, shell=True, capture_output=True, text=True,
                              timeout=4).stdout.strip() or default
    except Exception:
        return default


def dot(level):
    return {"ok": OK + "●" + R, "warn": WARN + "●" + R}.get(level, ERR + "●" + R)


def row(level, label, value):
    print(f"  {dot(level)}  {LBL}{label}{R}  {VAL}{value}{R}")


def human_uptime():
    try:
        up = float(open("/proc/uptime").read().split()[0])
    except Exception:
        return "—"
    d, rem = divmod(int(up), 86400)
    h, rem = divmod(rem, 3600)
    m = rem // 60
    if d:
        return f"{d} д {h} ч"
    if h:
        return f"{h} ч {m} мин"
    return f"{m} мин"


def main():
    width = int(os.environ.get("COLUMNS", 0) or 0) or shutil.get_terminal_size((100, 30)).columns
    width = max(70, width - 2)

    host = sh("hostname", "armbian")
    kernel = sh("uname -r")
    load = sh("cut -d' ' -f1-3 /proc/loadavg")
    ip = sh("ip -4 -br a show wlan0 2>/dev/null | awk '{print $3}' | cut -d/ -f1")
    ssid = sh("nmcli -t -f ACTIVE,SSID dev wifi 2>/dev/null | awk -F: '$1==\"yes\"{print $2; exit}'")
    temp = sh("awk '{printf \"%d\", $1/1000}' /sys/class/thermal/thermal_zone0/temp", "0")
    mem = sh("free -m | awk '/Mem:/{print $3\" \"$2}'", "0 0").split()
    disk = sh("df -h / | awk 'NR==2{print $3\" \"$2}'", "0 0").split()

    services = ["bluetooth", "bt-agent", "bluealsa", "bluealsa-aplay", "bt-beacon",
                "shairport-sync", "avahi-daemon", "smbd", "minidlna", "navidrome"]
    active = sum(1 for s in services
                 if sh(f"systemctl is-active {s}") == "active")

    clock = time.strftime("%H:%M")
    head_left = f"{host} · S905X3 · Armbian TV"
    gap = max(1, width - 4 - len(head_left) - len(clock))
    print()
    print(f"  {BOLD}{TIT}{head_left}{R}{' ' * gap}{DIM}{clock}{R}")
    print(f"  {DIM}{'─' * (width - 2)}{R}")
    print()

    row("ok", "система", f"Armbian trixie · ядро {kernel}")
    row("ok", "работа", f"{human_uptime()} · загрузка {load}")
    if ip:
        net = f"wlan0 {ip}" + (f" · {ssid}" if ssid else "")
        row("ok", "сеть", net)
    else:
        row("err", "сеть", "нет подключения")
    row("ok", "память", f"{mem[0]} Ми из {mem[1]} · swap свободен")
    row("ok", "диск", f"{disk[0]} из {disk[1]}")
    try:
        t = int(temp)
    except ValueError:
        t = 0
    row("warn" if t >= 70 else "ok", "чип", f"{t} °C")
    row("ok" if active == len(services) else "warn", "службы",
        f"{active} из {len(services)} активны")

    print()
    media = [f"DLNA {ACC}:8200{R}", f"Navidrome {ACC}:4533{R}",
             f"AirPlay {ACC}Armbian TV{R}", f"Samba {ACC}\\\\{ip}\\share{R}"]
    cmds = [f"{ACC}health{R}", f"{ACC}music-play{R}", f"{ACC}bt-test{R}",
            f"{ACC}dashboard-on{R}"]
    for label, items in (("медиа", media), ("команды", cmds)):
        while items:
            plain_len = 10 + len(" · ".join(__import__("re").sub(r"\033\[[0-9;]*m", "", x) for x in items))
            if plain_len <= width or len(items) == 1:
                break
            items = items[:-1]
        print(f"  {LBL}{label}{R}   " + " · ".join(items))
    print()


if __name__ == "__main__":
    main()

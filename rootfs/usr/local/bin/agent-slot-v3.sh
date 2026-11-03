#!/bin/bash
i=${1:?номер слота}
TOPIC=$(sed -n "s/^TOPIC=//p" /etc/kvorix/ai.conf 2>/dev/null)
HOSTS="https://ntfy.sh https://ntfy.hostux.net"
UP=/usr/local/bin/upterm
LOG=/run/slot-$i.out
KEYS=/etc/agent-access/guests_authorized_keys
SELF=/etc/agent-access/selfcheck_ed25519
: > "$LOG"

publish() {
    for h in $HOSTS; do curl -s -m 10 -d "SESSION $1" "$h/$TOPIC" >/dev/null 2>&1; done
    echo "$(date '+%F %T') slot$i $1" >> /var/log/agent-sessions.log
}
alive() {
    timeout 15 ssh -i "$SELF" -o BatchMode=yes -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
        -o ConnectTimeout=10 -o LogLevel=ERROR -N "$1:uptermd.upterm.dev@uptermd.upterm.dev" 2>/dev/null
    [ $? -eq 124 ]
}

sleep infinity | "$UP" host --accept --skip-host-key-check --allow-local-tcp-forwarding \
    --authorized-keys "$KEYS" -- bash > "$LOG" 2>&1 &
UPID=$!

code="" last=0 checked=$(date +%s) bad=0
while kill -0 "$UPID" 2>/dev/null; do
    c=$(grep -m1 -oE 'Session: [A-Za-z0-9]+' "$LOG" | awk '{print $2}')
    now=$(date +%s)
    if [ -n "$c" ] && { [ "$c" != "$code" ] || [ $((now - last)) -ge 14400 ]; }; then
        code=$c last=$now
        echo "$c" > "/run/session-$i.txt"
        publish "$c"
    fi
    if [ -n "$code" ] && [ $((now - checked)) -ge 300 ]; then
        checked=$now
        if alive "$code"; then bad=0; else bad=$((bad + 1)); fi
        if [ "$bad" -ge 2 ]; then
            echo "$(date '+%F %T') slot$i: сессия $code недоступна через ретранслятор — пересоздаю" >> /var/log/agent-sessions.log
            kill "$UPID"; break
        fi
    fi
    sleep 10
done
exit 1

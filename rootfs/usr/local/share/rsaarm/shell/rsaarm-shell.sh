#!/bin/bash
SHELL_DIR=/usr/local/share/rsaarm/shell
CONF="$HOME/.config/rsaarm"
mkdir -p "$CONF" 2>/dev/null
THEME=$(cat "$CONF/theme" 2>/dev/null || echo light)
EFFECTS=$(cat "$CONF/effects" 2>/dev/null || echo off)
export RSAARM_THEME=$THEME

xfconf-query -c xfwm4 -p /general/use_compositing -s false 2>/dev/null || true

for i in 1 2 3; do
    pgrep -x xfce4-panel >/dev/null 2>&1 || break
    pkill -x xfce4-panel 2>/dev/null
    sleep 1
done

if [ "$EFFECTS" = off ]; then pkill -x -u "$(id -u)" picom 2>/dev/null; true
elif ! pgrep -x picom >/dev/null 2>&1; then
    case "$EFFECTS" in
        full)  PC="--config $CONF/picom-full.conf" ;;
        off)   PC="--config $CONF/picom-off.conf" ;;
        *)     PC="--config $CONF/picom-basic.conf" ;;
    esac
    setsid picom $PC >/tmp/picom.log 2>&1 < /dev/null &
fi

pkill -f 'rsaarm-[b]ar.py'  2>/dev/null || true
pkill -f 'rsaarm-[d]ock.py' 2>/dev/null || true

pgrep -f 'rsaarm-[w]atchdog' >/dev/null 2>&1 || \
    setsid bash "$SHELL_DIR/rsaarm-watchdog.sh" >/dev/null 2>&1 < /dev/null &

pgrep -f 'rsaarm-[t]askbar.py' >/dev/null 2>&1 || \
    setsid python3 "$SHELL_DIR/rsaarm-taskbar.py" >/dev/null 2>&1 < /dev/null &

exit 0

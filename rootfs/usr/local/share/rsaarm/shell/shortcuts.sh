#!/bin/bash
export DISPLAY=${DISPLAY:-:0} XAUTHORITY=${XAUTHORITY:-$HOME/.Xauthority}
export DBUS_SESSION_BUS_ADDRESS=${DBUS_SESSION_BUS_ADDRESS:-unix:path=/run/user/$(id -u)/bus}
S=/usr/local/share/rsaarm/shell

setk() {
  xfconf-query -c xfce4-keyboard-shortcuts -p "$1" -s "$2" 2>/dev/null \
    || xfconf-query -c xfce4-keyboard-shortcuts -n -t string -p "$1" -s "$2"
}
MENU_CMD="sh -c 'env RSAARM_THEME=\$(cat \$HOME/.config/rsaarm/theme 2>/dev/null || echo light) python3 $S/rsaarm-menu.py --toggle'"

setk "/commands/custom/Super_L" "$MENU_CMD"
setk "/commands/custom/<Super>s" "$MENU_CMD"
setk "/commands/custom/<Super>space" "$MENU_CMD"
setk "/commands/custom/<Primary><Alt>space" "$MENU_CMD"
setk "/commands/custom/<Primary><Alt>t" "xfce4-terminal"
setk "/commands/custom/<Super>e" "thunar"
setk "/commands/custom/<Super>i" "armbian-center"
setk "/commands/custom/<Super>r" "xfce4-appfinder -c"
setk "/commands/custom/<Super>v" "xfce4-popup-clipman"
setk "/commands/custom/<Super>p" "kvorix-display-pop"
setk "/commands/custom/<Super>l" "dm-tool lock"
setk "/commands/custom/<Primary><Shift>Escape" "kvorix-taskmanager"
setk "/commands/custom/<Super>x" "kvorix-taskmanager"
setk "/commands/custom/<Super><Shift>s" "kvorix-snip"
setk "/commands/custom/Print" "kvorix-snip"
setk "/commands/custom/<Super>Tab" "kvorix-taskview"
setk "/commands/custom/<Super>Left" "rsaarm-snap left"
setk "/commands/custom/<Super>Right" "rsaarm-snap right"
setk "/commands/custom/<Super>Up" "rsaarm-snap max"
setk "/commands/custom/<Super>Down" "rsaarm-snap restore"

xfconf-query -c xfwm4 -p /general/show_desktop_key -s "<Super>d" 2>/dev/null \
  || xfconf-query -c xfwm4 -n -t string -p /general/show_desktop_key -s "<Super>d"
xfconf-query -c xfwm4 -p /general/tile_on_move -s true 2>/dev/null \
  || xfconf-query -c xfwm4 -n -t bool -p /general/tile_on_move -s true
xfconf-query -c xfwm4 -p /general/workspace_count -s 4 2>/dev/null \
  || xfconf-query -c xfwm4 -n -t int -p /general/workspace_count -s 4

echo "=== Горячие клавиши Kvorix Windows 11 назначены ==="

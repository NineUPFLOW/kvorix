#!/bin/bash
for i in $(seq 1 20); do
    if bluetoothctl list 2>/dev/null | grep -q Controller; then break; fi
    sleep 2
done
for i in $(seq 1 10); do
    bluetoothctl show 2>/dev/null | grep -q "Powered: yes" && break
    bluetoothctl power on >/dev/null 2>&1 || true
    sleep 2
done

ADAPTERS=$(bluetoothctl list 2>/dev/null | awk '{print $2}')
USB=""
for h in $ADAPTERS; do
    if hciconfig "$h" 2>/dev/null | grep -q "Bus: USB"; then USB="$h"; break; fi
done

for h in $ADAPTERS; do
    hciconfig "$h" up >/dev/null 2>&1 || true
    bluetoothctl select "$h" >/dev/null 2>&1 || true
    bluetoothctl power on >/dev/null 2>&1 || true
    if [ -n "$USB" ] && [ "$h" != "$USB" ]; then
        bluetoothctl power off >/dev/null 2>&1 || true
        continue
    fi
    bluetoothctl system-alias "Kvorix" >/dev/null 2>&1 || true
    hciconfig "$h" name "Kvorix" >/dev/null 2>&1 || true
    hcitool -i "$h" cmd 0x03 0x0024 0x1c 0x04 0x20 >/dev/null 2>&1 || true
    bluetoothctl discoverable on >/dev/null 2>&1 || true
    bluetoothctl pairable on >/dev/null 2>&1 || true
done

for mac in $(bluetoothctl devices 2>/dev/null | awk '{print $2}'); do
    bluetoothctl trust "$mac" >/dev/null 2>&1 || true
done

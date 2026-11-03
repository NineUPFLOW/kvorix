#!/bin/bash
set -e
ts=$(date +%Y%m%d-%H%M%S)
B=/root/rsaarm-backup-$ts
mkdir -p $B/autostart

hostnamectl set-hostname rsaarm 2>/dev/null || true
hostnamectl set-hostname --pretty "RSAarm мини-ПК" 2>/dev/null || true
sed -i 's/^127\.0\.1\.1.*/127.0.1.1 rsaarm nebo armbian localhost.localdomain/' /etc/hosts || true

cp -a /usr/local/share/armbian-gui/center.py $B/center.py.bak
cp -a /usr/local/share/armbian-gui/style.css $B/style.css.bak 2>/dev/null || true
sed -i 's/НЕБО/RSAarm/g' /usr/local/share/armbian-gui/center.py
sed -i 's/НЕБО/RSAarm/g' /usr/local/share/armbian-gui/style.css 2>/dev/null || true

cp -a /usr/local/bin/bt-beacon.sh $B/bt-beacon.sh.bak 2>/dev/null || true
sed -i 's/НЕБО/RSAarm/g' /usr/local/bin/bt-beacon.sh 2>/dev/null || true
systemctl restart bt-beacon 2>/dev/null || true

sed -i 's/НЕБО/RSAarm/g' /tmp/live_panel.py 2>/dev/null || true

for f in autostart-monitor.desktop blueman.desktop; do
  mv /home/agent/.config/autostart/$f $B/autostart/ 2>/dev/null || true
done

if [ -d /usr/share/plymouth/themes/nebo ]; then
  cp -a /usr/share/plymouth/themes/nebo $B/plymouth-theme-nebo
  mv /usr/share/plymouth/themes/nebo /usr/share/plymouth/themes/rsaarm
  cd /usr/share/plymouth/themes/rsaarm
  [ -f nebo.plymouth ] && mv nebo.plymouth rsaarm.plymouth
  sed -i 's/Name=nebo/Name=rsaarm/; s/\[nebo\]/[rsaarm]/; s|themes/nebo|themes/rsaarm|g' rsaarm.plymouth
  plymouth-set-default-theme rsaarm || true
fi

ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 cluster-node-1 \
  "sed -i 's/ nebo armbian cluster-main/ rsaarm nebo armbian cluster-main/' /etc/hosts" 2>/dev/null || true

echo "REBRAND-DONE backup=$B"

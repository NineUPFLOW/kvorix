#!/bin/bash
set -e
ts=$(date +%Y%m%d-%H%M%S)
B=/root/rsaarm-backup-$ts
mkdir -p $B

systemctl is-enabled navidrome minidlna shairport-sync smbd nmbd openvpn rpcbind nfs-blkmap avahi-daemon 2>/dev/null > $B/services-were-enabled.txt || true
for s in navidrome minidlna shairport-sync smbd nmbd openvpn rpcbind nfs-blkmap avahi-daemon; do
  systemctl stop "$s" 2>/dev/null || true
  systemctl disable "$s" 2>/dev/null || true
done
echo "службы отключены (список в $B/services-were-enabled.txt)"

grep -n swapfile /etc/fstab || true
cp -a /etc/fstab $B/fstab.bak
sed -i '/swapfile/d' /etc/fstab
rm -f /swapfile
echo "swap-файл удалён (2 ГБ свободно)"

THEMES="ZOMG-PONIES! XP-Balloon Kokodi Moheli MBOpus blondie bluebox borillo Bright Daloa Retro Smoke Emacs"
for t in $THEMES; do
  [ -d "/usr/share/themes/$t" ] && rm -rf "/usr/share/themes/$t" && echo "тема удалена: $t"
done

for t in bgrt fade-in glow solar spinfinity spinner tribar armbian; do
  [ -d "/usr/share/plymouth/themes/$t" ] && rm -rf "/usr/share/plymouth/themes/$t" && echo "plymouth удалён: $t"
done
echo "CLEANUP-DONE backup=$B"

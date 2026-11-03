#!/bin/bash
set -e
DEST=/srv/share/backup
mkdir -p "$DEST"
STAMP=$(date +%Y-%m-%d)
TMP=$(mktemp -d)
mkdir -p "$TMP/etc/armbian-cluster" "$TMP/boot" "$TMP/local/bin" "$TMP/local/gui"
cp -a /etc/samba/smb.conf "$TMP/etc/" 2>/dev/null || true
cp -a /etc/ssh/sshd_config "$TMP/etc/" 2>/dev/null || true
cp -a /etc/fstab "$TMP/etc/" 2>/dev/null || true
cp -a /etc/hosts "$TMP/etc/" 2>/dev/null || true
cp -a /etc/armbian-cluster/cluster.json "$TMP/etc/armbian-cluster/" 2>/dev/null || true
cp -a /boot/uEnv.txt "$TMP/boot/" 2>/dev/null || true
cp -a /usr/local/bin/cockpit.py /usr/local/bin/cluster_agent.py /usr/local/bin/armbian-cluster \
      /usr/local/bin/box-watchdog.sh /usr/local/bin/box-backup.sh /usr/local/bin/join-cluster-node.sh \
      "$TMP/local/bin/" 2>/dev/null || true
cp -a /usr/local/share/armbian-gui/*.py "$TMP/local/gui/" 2>/dev/null || true
dpkg --get-selections > "$TMP/packages.txt"
systemctl list-unit-files --state=enabled --no-legend > "$TMP/enabled-services.txt" 2>/dev/null || true
tar czf "$DEST/armbian-$STAMP.tar.gz" -C "$TMP" . 2>/dev/null
rm -rf "$TMP"
chown agent:users "$DEST/armbian-$STAMP.tar.gz" 2>/dev/null || true
ls -1t "$DEST"/armbian-*.tar.gz 2>/dev/null | tail -n +8 | xargs -r rm -f
ls -lh "$DEST/armbian-$STAMP.tar.gz" | awk '{print "бэкап:", $9, $5}'

/usr/local/bin/armbian-cluster backup-sync >/dev/null 2>&1 || true

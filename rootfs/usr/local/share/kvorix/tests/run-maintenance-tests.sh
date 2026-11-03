#!/usr/bin/env bash
set -uo pipefail
cd /usr/local/share/kvorix/tests || exit 2
fail=0
for t in test-config-verify.py test-front-panel.py test-health-check.py; do
    out=$(python3 "$t" 2>&1)
    rc=$?
    echo "=== $t ==="
    echo "$out" | tail -4
    if [ "$rc" -eq 0 ]; then
        echo "OK   $t"
    else
        echo "FAIL $t (rc=$rc)"
        echo "$out" | tail -30
        fail=1
    fi
done
echo "=== health-check ==="
kvorix-health-check | tail -1 || fail=1
echo "=== verify --all ==="
sudo -n kvorix-config-verify --all | python3 -c '
import json, sys
d = json.load(sys.stdin)
print("verified=%s checked=%s failures=%s orphan=%s missing=%s" % (
    d["verified"], d["checked"], len(d["failures"]),
    len(d["orphan_manifests"]), len(d["missing_manifests"])))
sys.exit(0 if d["verified"] else 1)
' || fail=1
exit "$fail"

#!/usr/bin/env bash
set -euo pipefail

VM="mainhost"
IMGDIR="/var/lib/libvirt/images"

ACTIVE="$IMGDIR/mainhost.qcow2"
BASE="$IMGDIR/mainhost-base.qcow2"

echo "[*] Checking active disk..."
test -f "$ACTIVE"

echo "[*] Shutting down VM..."
virsh shutdown "$VM" 2>/dev/null || true

echo "[*] Waiting for shutdown..."
for i in {1..60}; do
    state="$(virsh domstate "$VM" 2>/dev/null || true)"
    if [[ "$state" == "shut off" ]]; then
        break
    fi
    sleep 2
done

state="$(virsh domstate "$VM" 2>/dev/null || true)"
if [[ "$state" != "shut off" ]]; then
    echo "[!] Graceful shutdown failed, forcing power off..."
    virsh destroy "$VM" 2>/dev/null || true
fi

echo "[*] Replacing previous baseline..."
rm -f "$BASE"
cp --reflink=auto "$ACTIVE" "$BASE"

echo "[*] Baseline saved to:"
echo "    $BASE"

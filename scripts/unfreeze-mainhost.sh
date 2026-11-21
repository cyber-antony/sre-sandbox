#!/usr/bin/env bash
set -euo pipefail

VM="mainhost"
IMGDIR="/var/lib/libvirt/images"

ACTIVE="$IMGDIR/mainhost.qcow2"
BASE="$IMGDIR/mainhost-base.qcow2"

echo "[*] Checking baseline..."
test -f "$BASE"

echo "[*] Stopping VM..."
virsh destroy "$VM" 2>/dev/null || true

echo "[*] Removing current working disk..."
rm -f "$ACTIVE"

echo "[*] Creating fresh working overlay from baseline..."
qemu-img create -f qcow2 -F qcow2 -b "$BASE" "$ACTIVE"

echo "[*] Starting VM..."
#virsh start "$VM"

echo "[*] Restored from baseline."

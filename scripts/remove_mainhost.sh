#!/usr/bin/env bash
set -e

VM="mainhost"
IMG_DIR="/var/lib/libvirt/images"

echo "[*] Destroy VM..."
virsh destroy "$VM" 2>/dev/null || true

echo "[*] Undefine VM..."
virsh undefine "$VM" --remove-all-storage 2>/dev/null || true

echo "[*] Remove disks..."
rm -f $IMG_DIR/mainhost.qcow2
rm -f $IMG_DIR/mainhost-seed.iso

echo "[*] Done. Clean state."

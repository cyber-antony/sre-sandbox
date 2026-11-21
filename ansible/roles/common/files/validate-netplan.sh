#!/bin/sh
set -eu

# Generate into an isolated root so validation cannot change live networking.
validation_root=$(mktemp -d)
trap 'rm -rf -- "$validation_root"' EXIT
mkdir -p "$validation_root/etc/netplan"
cp -- "$1" "$validation_root/etc/netplan/validation.yaml"
chmod 600 "$validation_root/etc/netplan/validation.yaml"
netplan generate --root-dir "$validation_root"

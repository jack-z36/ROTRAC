#!/usr/bin/env bash
set -Eeuo pipefail

RULE_FILE="/etc/udev/rules.d/99-hcan-usb-canfd.rules"
RULE='SUBSYSTEM=="usb", ATTR{idVendor}=="a8fa", ATTR{idProduct}=="8598", MODE="0660", GROUP="plugdev", TAG+="uaccess"'

printf '%s\n' "$RULE" | sudo tee "$RULE_FILE" >/dev/null
sudo udevadm control --reload-rules
sudo udevadm trigger --attr-match=idVendor=a8fa --attr-match=idProduct=8598

echo "[hcan-udev] wrote $RULE_FILE:"
sudo sed -n '1,5p' "$RULE_FILE"
echo "[hcan-udev] current HCAN USB node:"
for device in /dev/bus/usb/*/*; do
  if udevadm info -q property -n "$device" 2>/dev/null | grep -q 'ID_VENDOR_ID=a8fa'; then
    ls -l "$device"
  fi
done

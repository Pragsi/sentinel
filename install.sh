#!/usr/bin/env bash
set -euo pipefail

if [ "${EUID}" -ne 0 ]; then
  echo "Run with: sudo ./install.sh"
  exit 1
fi

apt update
apt install -y python3 python3-tk python3-spidev python3-pigpio pigpio lxterminal xdg-utils network-manager bluez raspi-config polkit pkexec

CFG="/boot/config.txt"
[ -f /boot/firmware/config.txt ] && CFG="/boot/firmware/config.txt"
grep -q '^dtparam=spi=on' "$CFG" || echo 'dtparam=spi=on' >> "$CFG"

systemctl enable pigpiod
systemctl restart pigpiod || true

mkdir -p /opt/sentinel /var/lib/sentinel
cp sentinel/*.py /opt/sentinel/
chmod 755 /opt/sentinel/*.py
cp sentinel-update-helper /usr/local/sbin/sentinel-update-helper
chmod 755 /usr/local/sbin/sentinel-update-helper

cat >/usr/local/bin/sentinel <<'EOF'
#!/bin/sh
exec python3 /opt/sentinel/sentinel_launcher.py
EOF
chmod 755 /usr/local/bin/sentinel

USER_NAME="${SUDO_USER:-pi}"
USER_HOME="$(getent passwd "$USER_NAME" | cut -d: -f6)"
mkdir -p "$USER_HOME/.config/autostart" "$USER_HOME/.sentinel/captures"
cat >"$USER_HOME/.config/autostart/sentinel.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=Sentinel
Exec=/usr/local/bin/sentinel
Terminal=false
X-GNOME-Autostart-enabled=true
EOF
chown -R "$USER_NAME:$USER_NAME" "$USER_HOME/.config/autostart" "$USER_HOME/.sentinel"

echo "Sentinel 1.3 installed. Reboot with: sudo reboot"

#!/bin/bash
set -e

# Raspberry Pi Dictaphone Go Uninstallation Script

INSTALL_DIR="/opt/dictaphone"
USER="aleks"

echo "🗑️ Uninstalling Raspberry Pi Dictaphone Go..."

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo "This script must be run as root (use sudo)" 
   exit 1
fi

# Stop and disable services
echo "Stopping services..."
systemctl stop dictaphone.service || true
systemctl stop usb-monitor.service || true

echo "Disabling services..."
systemctl disable dictaphone.service || true
systemctl disable usb-monitor.service || true

# Remove systemd service files
echo "Removing systemd services..."
rm -f /etc/systemd/system/dictaphone.service
rm -f /etc/systemd/system/usb-monitor.service
systemctl daemon-reload

# Remove PolicyKit rules
echo "Removing PolicyKit rules..."
rm -f /etc/polkit-1/localauthority/50-local.d/10-udisks2.pkla

# Remove udev rules
echo "Removing udev rules..."
rm -f /etc/udev/rules.d/99-dictaphone-input.rules
udevadm control --reload-rules

# Remove application files
echo "Removing application files..."
rm -rf "$INSTALL_DIR"

# Ask about user data
echo ""
read -p "Do you want to remove user data (/home/$USER/records, /home/$USER/cache_tts)? [y/N]: " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Removing user data..."
    rm -rf "/home/$USER/records"
    rm -rf "/home/$USER/cache_tts"
    echo "User data removed."
else
    echo "User data preserved in /home/$USER/"
fi

# Ask about user account
echo ""
read -p "Do you want to remove user account '$USER'? [y/N]: " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Removing user account..."
    userdel -r "$USER" 2>/dev/null || echo "User account removal failed or user doesn't exist"
    echo "User account removed."
else
    echo "User account preserved."
fi

echo ""
echo "✅ Uninstallation completed!"
echo ""
echo "📋 Manual cleanup (if needed):"
echo "   - Remove Go installation: rm -rf /usr/local/go"
echo "   - Remove system packages: apt remove alsa-utils mpg123 sox vlc-bin ffmpeg udisks2"
echo "   - Clean package cache: apt autoremove && apt autoclean"

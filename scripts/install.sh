#!/bin/bash
set -e

# Raspberry Pi Dictaphone Go Installation Script
# This script installs the dictaphone application and its dependencies

INSTALL_DIR="/opt/dictaphone"
USER="aleks"
SERVICE_USER="aleks"

echo "🎙️ Installing Raspberry Pi Dictaphone Go..."

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo "This script must be run as root (use sudo)" 
   exit 1
fi

# Check if user exists
if ! id "$USER" &>/dev/null; then
    echo "Creating user $USER..."
    useradd -m -s /bin/bash -G audio,dialout "$USER"
    echo "User $USER created. Please set password with: passwd $USER"
fi

# Install system dependencies
echo "Installing system dependencies..."
apt-get update
apt-get install -y \
    alsa-utils \
    pulseaudio \
    pulseaudio-utils \
    mpg123 \
    sox \
    vlc-bin \
    ffmpeg \
    udisks2 \
    libudev-dev \
    libasound2-dev \
    libpulse-dev \
    curl \
    wget

# Install Go if not present
if ! command -v go &> /dev/null; then
    echo "Installing Go..."
    GO_VERSION="1.21.5"
    GO_ARCH="arm64"
    if [[ $(uname -m) == "armv7l" ]]; then
        GO_ARCH="armv6l"
    fi
    
    cd /tmp
    wget "https://golang.org/dl/go${GO_VERSION}.linux-${GO_ARCH}.tar.gz"
    rm -rf /usr/local/go
    tar -C /usr/local -xzf "go${GO_VERSION}.linux-${GO_ARCH}.tar.gz"
    
    # Add Go to PATH
    echo 'export PATH=$PATH:/usr/local/go/bin' >> /etc/profile
    export PATH=$PATH:/usr/local/go/bin
fi

# Create installation directory
echo "Creating installation directory..."
mkdir -p "$INSTALL_DIR"/{bin,configs,cache,logs}
chown -R "$USER:$USER" "$INSTALL_DIR"

# Create user directories
echo "Creating user directories..."
sudo -u "$USER" mkdir -p "/home/$USER"/{records,cache_tts}
sudo -u "$USER" mkdir -p "/home/$USER/records"/{Заметки,Идеи,Важное,Работа,Личное}

# Copy application files
echo "Installing application files..."
if [ -f "./bin/dictaphone" ]; then
    cp ./bin/dictaphone "$INSTALL_DIR/bin/"
    cp ./bin/usb-monitor "$INSTALL_DIR/bin/"
    chmod +x "$INSTALL_DIR/bin"/*
else
    echo "Building application from source..."
    cd "$(dirname "$0")/.."
    go build -o "$INSTALL_DIR/bin/dictaphone" ./cmd/dictaphone
    go build -o "$INSTALL_DIR/bin/usb-monitor" ./cmd/usb-monitor
    chmod +x "$INSTALL_DIR/bin"/*
fi

# Copy configuration
echo "Installing configuration..."
cp ./configs/config.yaml "$INSTALL_DIR/"
chown "$USER:$USER" "$INSTALL_DIR/config.yaml"

# Install systemd services
echo "Installing systemd services..."
cp ./systemd/*.service /etc/systemd/system/
systemctl daemon-reload

# Set up PolicyKit rules for udisks2
echo "Setting up PolicyKit rules..."
cat > /etc/polkit-1/localauthority/50-local.d/10-udisks2.pkla << EOF
[Allow user to mount USB devices]
Identity=unix-user:$USER
Action=org.freedesktop.udisks2.filesystem-mount;org.freedesktop.udisks2.filesystem-mount-system;org.freedesktop.udisks2.power-off-drive
ResultActive=yes
ResultInactive=no
ResultAny=no
EOF

# Set up udev rules for input devices
echo "Setting up udev rules..."
cat > /etc/udev/rules.d/99-dictaphone-input.rules << EOF
# Allow access to input devices for dictaphone
SUBSYSTEM=="input", GROUP="input", MODE="0664"
KERNEL=="event*", SUBSYSTEM=="input", GROUP="input", MODE="0664"

# Specific rule for HAOBO remote control
SUBSYSTEM=="input", ATTRS{name}=="*HAOBO*", GROUP="input", MODE="0664", TAG+="uaccess"
EOF

# Add user to required groups
echo "Adding user to required groups..."
usermod -a -G audio,input,plugdev "$USER"

# Set up PulseAudio for system service
echo "Configuring PulseAudio..."
mkdir -p "/home/$USER/.config/pulse"
sudo -u "$USER" cp /etc/pulse/default.pa "/home/$USER/.config/pulse/"

# Create startup script
echo "Creating startup script..."
cat > "$INSTALL_DIR/start.sh" << EOF
#!/bin/bash
export HOME="/home/$USER"
export XDG_RUNTIME_DIR="/run/user/\$(id -u $USER)"
export PULSE_RUNTIME_PATH="\$XDG_RUNTIME_DIR/pulse"

cd "$INSTALL_DIR"
exec ./bin/dictaphone --config ./config.yaml
EOF

chmod +x "$INSTALL_DIR/start.sh"
chown "$USER:$USER" "$INSTALL_DIR/start.sh"

# Enable and start services
echo "Enabling services..."
systemctl enable usb-monitor.service
systemctl enable dictaphone.service

# Reload udev rules
udevadm control --reload-rules
udevadm trigger

echo "✅ Installation completed successfully!"
echo ""
echo "📋 Next steps:"
echo "1. Copy your Google Cloud TTS credentials to: $INSTALL_DIR/credentials-google-api.json"
echo "2. Edit configuration if needed: $INSTALL_DIR/config.yaml"
echo "3. Start the services:"
echo "   sudo systemctl start usb-monitor"
echo "   sudo systemctl start dictaphone"
echo ""
echo "📊 Check status with:"
echo "   sudo systemctl status dictaphone"
echo "   sudo systemctl status usb-monitor"
echo ""
echo "📜 View logs with:"
echo "   sudo journalctl -u dictaphone -f"
echo "   sudo journalctl -u usb-monitor -f"
echo ""
echo "🔧 For manual testing:"
echo "   sudo -u $USER $INSTALL_DIR/bin/dictaphone --config $INSTALL_DIR/config.yaml"
echo ""
echo "⚠️  Remember to:"
echo "   - Set password for user '$USER': sudo passwd $USER"
echo "   - Reboot the system to ensure all changes take effect"

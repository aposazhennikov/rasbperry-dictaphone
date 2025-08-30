# 🎙️ Raspberry Pi Dictaphone Go

A voice-controlled dictaphone application for visually impaired users, running on Raspberry Pi with Ubuntu. This is a complete rewrite of the original Python version in Go, providing better performance, reliability, and easier deployment.

## ✨ Features

- **🗣️ Voice Navigation**: Complete TTS (Text-to-Speech) interface with Russian voice support
- **🎙️ Audio Recording**: High-quality audio recording with pause/resume functionality  
- **▶️ Audio Playback**: Full playback control with speed adjustment, seeking, and volume control
- **🎛️ Remote Control**: Support for HAOBO Technology USB remote control
- **💾 USB Management**: Automatic USB storage device detection and mounting
- **📻 Radio Stations**: Support for radio stations and podcasts
- **⚙️ Settings Management**: Voice-controlled settings configuration
- **🖥️ Visual Interface**: Optional text-based visual interface
- **🔧 System Integration**: Systemd services for automatic startup

## 🏗️ Architecture

### Core Components

- **Audio System**: Recording and playback using `malgo` library with system utilities fallback
- **TTS System**: Google Cloud TTS with gTTS fallback and intelligent caching
- **Input Handler**: Linux input events processing for remote control
- **USB Monitor**: Automatic USB device detection using `go-udev`
- **Menu System**: Hierarchical menu navigation with TTS integration
- **Visual Interface**: Optional terminal-based UI

### Technology Stack

- **Language**: Go 1.21+
- **Audio**: `github.com/gen2brain/malgo` + system utilities (aplay, mpg123, vlc)
- **TTS**: Google Cloud TTS SDK + gTTS fallback
- **USB**: `github.com/jochenvg/go-udev` + udisks2
- **Input**: Direct Linux input events processing
- **Logging**: Sentry integration + structured logging

## 📋 Requirements

### Hardware
- Raspberry Pi 4 (recommended) or Raspberry Pi 3B+
- USB Audio device or built-in audio
- HAOBO Technology USB remote control
- USB storage devices (optional)

### Software
- Ubuntu 20.04+ on Raspberry Pi
- Go 1.21+ (for building from source)
- System packages (installed automatically):
  - `alsa-utils`, `pulseaudio`
  - `mpg123`, `sox`, `vlc-bin`, `ffmpeg`
  - `udisks2`, `libudev-dev`

## 🚀 Quick Start

### Option 1: Binary Installation (Recommended)

1. Download the latest release for your architecture:
```bash
# For Raspberry Pi 4 (ARM64)
wget https://github.com/username/raspberry-dictaphone-go/releases/latest/download/raspberry-dictaphone-go-linux-arm64.tar.gz

# For Raspberry Pi 3 (ARM32)
wget https://github.com/username/raspberry-dictaphone-go/releases/latest/download/raspberry-dictaphone-go-linux-arm.tar.gz
```

2. Extract and install:
```bash
tar -xzf raspberry-dictaphone-go-*.tar.gz
cd raspberry-dictaphone-go
sudo ./scripts/install.sh
```

3. Configure Google Cloud TTS credentials:
```bash
sudo cp your-credentials.json /opt/dictaphone/credentials-google-api.json
sudo chown aleks:aleks /opt/dictaphone/credentials-google-api.json
```

4. Start the services:
```bash
sudo systemctl start usb-monitor
sudo systemctl start dictaphone
```

### Option 2: Build from Source

1. Clone the repository:
```bash
git clone https://github.com/username/raspberry-dictaphone-go.git
cd raspberry-dictaphone-go
```

2. Build and install:
```bash
make build-rpi4  # or make build-rpi3 for older Pi
sudo make install
```

### Option 3: Docker (Experimental)

1. Build and run with Docker Compose:
```bash
docker-compose up -d
```

## ⚙️ Configuration

The main configuration file is located at `/opt/dictaphone/config.yaml`:

```yaml
app:
  name: "Raspberry Pi Dictaphone"
  version: "2.0.0"
  debug: false

audio:
  sample_rate: 44100
  channels: 1
  max_duration: "3h"
  min_free_space: "1GB"
  records_dir: "/home/aleks/records"
  
tts:
  primary_engine: "google_cloud"
  fallback_engine: "gtts"
  cache_dir: "/home/aleks/cache_tts"
  voice: "ru-RU-Standard-A"
  credentials_path: "/opt/dictaphone/credentials-google-api.json"
  
input:
  device_name: "HAOBO Technology USB Composite Device Keyboard"
  
usb:
  monitor_enabled: true
  auto_mount: true
  
logging:
  level: "info"
  sentry_dsn: "your-sentry-dsn"
  sentry_enabled: true

visual_interface:
  enabled: true
  width: 80
  height: 24
  refresh_rate: "100ms"
```

## 🎛️ Remote Control

The application supports the HAOBO Technology USB remote control with the following key mappings:

| Key | Function |
|-----|----------|
| ↑↓ | Menu navigation |
| ⏎ (SELECT) | Select menu item / Pause recording |
| ← (BACK) | Go back / Stop |
| ←→ | Seek backward/forward (10s) |
| Page Up/Down | Volume control |
| Volume Up/Down | Playback speed control |
| Power | Delete file |

## 📁 Directory Structure

```
/opt/dictaphone/          # Application directory
├── bin/                  # Binaries
│   ├── dictaphone       # Main application
│   └── usb-monitor      # USB monitoring service
├── config.yaml          # Configuration file
├── credentials-google-api.json  # Google Cloud credentials
└── scripts/             # Installation scripts

/home/aleks/             # User directory
├── records/             # Audio recordings
│   ├── Заметки/        # Notes folder
│   ├── Идеи/           # Ideas folder
│   ├── Важное/         # Important folder
│   ├── Работа/         # Work folder
│   └── Личное/         # Personal folder
└── cache_tts/          # TTS cache
```

## 🛠️ Development

### Building

```bash
# Install dependencies
make deps

# Build for current platform
make build

# Build for specific platforms
make build-rpi4    # Raspberry Pi 4 (ARM64)
make build-rpi3    # Raspberry Pi 3 (ARM32)
make build-amd64   # x86_64 for testing

# Create distribution package
make dist

# Format code and run linter
make fmt
make lint

# Run tests
make test
```

### Development Environment

```bash
# Set up development environment
make dev-setup

# Run locally for testing
make run-dictaphone
make run-usb-monitor

# Pre-generate TTS cache
make pregenerate
```

## 🔧 System Integration

### Systemd Services

The application runs as two systemd services:

1. **dictaphone.service**: Main application
2. **usb-monitor.service**: USB device monitoring

```bash
# Check status
sudo systemctl status dictaphone
sudo systemctl status usb-monitor

# View logs
sudo journalctl -u dictaphone -f
sudo journalctl -u usb-monitor -f

# Control services
sudo systemctl start/stop/restart dictaphone
sudo systemctl enable/disable dictaphone
```

### Permissions

The application requires specific permissions for:
- Audio devices (ALSA/PulseAudio)
- Input devices (evdev)
- USB mounting (udisks2 via PolicyKit)
- System volume control

These are configured automatically during installation.

## 🚨 Troubleshooting

### Common Issues

1. **No audio devices found**
   ```bash
   # Check ALSA devices
   aplay -l
   arecord -l
   
   # Check PulseAudio
   sudo -u aleks pulseaudio --check -v
   ```

2. **Remote control not working**
   ```bash
   # Check input devices
   ls -la /dev/input/
   cat /proc/bus/input/devices | grep -A 5 "HAOBO"
   
   # Test input events
   sudo evtest
   ```

3. **USB devices not mounting**
   ```bash
   # Check udisks2
   udisksctl status
   
   # Check PolicyKit rules
   pkaction --action-id org.freedesktop.udisks2.filesystem-mount
   ```

4. **TTS not working**
   ```bash
   # Check Google Cloud credentials
   ls -la /opt/dictaphone/credentials-google-api.json
   
   # Test TTS manually
   sudo -u aleks /opt/dictaphone/bin/dictaphone pregenerate
   ```

### Logs

- Application logs: `sudo journalctl -u dictaphone -f`
- USB monitor logs: `sudo journalctl -u usb-monitor -f`
- System logs: `sudo journalctl -f`

## 📊 Performance

### Resource Usage

- **Memory**: ~50-100MB (main app), ~20MB (USB monitor)
- **CPU**: <5% during normal operation, ~20% during TTS generation
- **Storage**: ~500MB for application, variable for recordings and TTS cache

### Optimization

- TTS responses are cached to minimize API calls and improve performance
- Audio processing uses efficient native libraries
- USB monitoring is event-driven to minimize CPU usage

## 🔒 Security

- Services run with minimal privileges
- Input validation for all user data
- Secure credential storage
- Optional Sentry integration for error monitoring

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Development Guidelines

- Follow Go best practices
- Add tests for new functionality
- Update documentation
- Use conventional commit messages
- Ensure code passes linting

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Original Python version developers
- Go community for excellent libraries
- Google Cloud for TTS services
- Raspberry Pi Foundation

## 📞 Support

- Create an issue on GitHub for bugs or feature requests
- Check existing issues before creating new ones
- Provide detailed information including logs and system configuration

---

**Made with ❤️ for the visually impaired community**

#!/bin/bash
set -e

# Build script for Raspberry Pi Dictaphone Go

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_DIR="$PROJECT_ROOT/build"
BIN_DIR="$BUILD_DIR/bin"

echo "🔨 Building Raspberry Pi Dictaphone Go..."

# Clean previous build
echo "Cleaning previous build..."
rm -rf "$BUILD_DIR"
mkdir -p "$BIN_DIR"

# Set build information
VERSION=$(git describe --tags --always --dirty 2>/dev/null || echo "dev")
BUILD_TIME=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
COMMIT=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")

# Go build flags
LDFLAGS="-s -w"
LDFLAGS="$LDFLAGS -X main.Version=$VERSION"
LDFLAGS="$LDFLAGS -X main.BuildTime=$BUILD_TIME"
LDFLAGS="$LDFLAGS -X main.GitCommit=$COMMIT"

# Build for current architecture
echo "Building dictaphone..."
cd "$PROJECT_ROOT"
go build -ldflags "$LDFLAGS" -o "$BIN_DIR/dictaphone" ./cmd/dictaphone

echo "Building usb-monitor..."
go build -ldflags "$LDFLAGS" -o "$BIN_DIR/usb-monitor" ./cmd/usb-monitor

# Copy additional files
echo "Copying additional files..."
cp -r configs "$BUILD_DIR/"
cp -r systemd "$BUILD_DIR/"
cp -r scripts "$BUILD_DIR/"

# Make scripts executable
chmod +x "$BUILD_DIR/scripts"/*.sh

# Create archive
echo "Creating distribution archive..."
cd "$BUILD_DIR"
tar -czf "../raspberry-dictaphone-go-${VERSION}.tar.gz" .

echo "✅ Build completed successfully!"
echo "📦 Binaries: $BIN_DIR/"
echo "📦 Archive: $PROJECT_ROOT/raspberry-dictaphone-go-${VERSION}.tar.gz"
echo ""
echo "🚀 To install on Raspberry Pi:"
echo "   1. Copy the archive to your Raspberry Pi"
echo "   2. Extract: tar -xzf raspberry-dictaphone-go-${VERSION}.tar.gz"
echo "   3. Run: cd raspberry-dictaphone-go && sudo ./scripts/install.sh"

# Makefile for Raspberry Pi Dictaphone Go

# Project information
PROJECT_NAME = raspberry-dictaphone-go
VERSION ?= $(shell git describe --tags --always --dirty 2>/dev/null || echo "dev")
BUILD_TIME = $(shell date -u +"%Y-%m-%dT%H:%M:%SZ")
COMMIT = $(shell git rev-parse --short HEAD 2>/dev/null || echo "unknown")

# Directories
BUILD_DIR = build
BIN_DIR = $(BUILD_DIR)/bin
DIST_DIR = dist

# Go build settings
GOOS ?= linux
GOARCH ?= arm64
CGO_ENABLED ?= 1

# Build flags
LDFLAGS = -s -w
LDFLAGS += -X main.Version=$(VERSION)
LDFLAGS += -X main.BuildTime=$(BUILD_TIME)
LDFLAGS += -X main.GitCommit=$(COMMIT)

# Go build command
GOBUILD = CGO_ENABLED=$(CGO_ENABLED) GOOS=$(GOOS) GOARCH=$(GOARCH) go build -ldflags "$(LDFLAGS)"

.PHONY: all build clean install uninstall test lint fmt deps help

# Default target
all: clean build

# Build all binaries
build: deps
	@echo "🔨 Building $(PROJECT_NAME) v$(VERSION)..."
	@mkdir -p $(BIN_DIR)
	$(GOBUILD) -o $(BIN_DIR)/dictaphone ./cmd/dictaphone
	$(GOBUILD) -o $(BIN_DIR)/usb-monitor ./cmd/usb-monitor
	@echo "✅ Build completed!"

# Build for Raspberry Pi 4 (ARM64)
build-rpi4:
	@$(MAKE) build GOARCH=arm64

# Build for Raspberry Pi 3 and older (ARM32)
build-rpi3:
	@$(MAKE) build GOARCH=arm GOARM=7

# Build for x86_64 (for testing)
build-amd64:
	@$(MAKE) build GOARCH=amd64

# Create distribution package
dist: build
	@echo "📦 Creating distribution package..."
	@mkdir -p $(DIST_DIR)
	@rm -rf $(BUILD_DIR)/configs $(BUILD_DIR)/systemd $(BUILD_DIR)/scripts
	@cp -r configs $(BUILD_DIR)/
	@cp -r systemd $(BUILD_DIR)/
	@cp -r scripts $(BUILD_DIR)/
	@chmod +x $(BUILD_DIR)/scripts/*.sh
	@cd $(BUILD_DIR) && tar -czf ../$(DIST_DIR)/$(PROJECT_NAME)-$(VERSION)-$(GOOS)-$(GOARCH).tar.gz .
	@echo "✅ Distribution package created: $(DIST_DIR)/$(PROJECT_NAME)-$(VERSION)-$(GOOS)-$(GOARCH).tar.gz"

# Install dependencies
deps:
	@echo "📥 Installing dependencies..."
	@go mod download
	@go mod tidy

# Run tests
test:
	@echo "🧪 Running tests..."
	@go test -v ./...

# Run linter
lint:
	@echo "🔍 Running linter..."
	@if command -v golangci-lint >/dev/null 2>&1; then \
		golangci-lint run; \
	else \
		echo "golangci-lint not found, install it: https://golangci-lint.run/usage/install/"; \
		go vet ./...; \
	fi

# Format code
fmt:
	@echo "✨ Formatting code..."
	@go fmt ./...
	@if command -v goimports >/dev/null 2>&1; then \
		goimports -w .; \
	fi

# Clean build artifacts
clean:
	@echo "🧹 Cleaning build artifacts..."
	@rm -rf $(BUILD_DIR) $(DIST_DIR)

# Install on local system (requires sudo)
install: build
	@echo "📦 Installing to system..."
	@sudo ./scripts/install.sh

# Uninstall from local system (requires sudo)
uninstall:
	@echo "🗑️ Uninstalling from system..."
	@sudo ./scripts/uninstall.sh

# Run dictaphone locally (for development)
run-dictaphone: build
	@echo "🎙️ Running dictaphone..."
	@./$(BIN_DIR)/dictaphone --config ./configs/config.yaml

# Run USB monitor locally (for development)
run-usb-monitor: build
	@echo "💾 Running USB monitor..."
	@./$(BIN_DIR)/usb-monitor --config ./configs/config.yaml

# Pre-generate TTS cache
pregenerate: build
	@echo "🗣️ Pre-generating TTS cache..."
	@./$(BIN_DIR)/dictaphone pregenerate --config ./configs/config.yaml

# Show help
help:
	@echo "📋 Available targets:"
	@echo "  all             - Clean and build all binaries"
	@echo "  build           - Build all binaries for current platform"
	@echo "  build-rpi4      - Build for Raspberry Pi 4 (ARM64)"
	@echo "  build-rpi3      - Build for Raspberry Pi 3 (ARM32)"
	@echo "  build-amd64     - Build for x86_64"
	@echo "  dist            - Create distribution package"
	@echo "  deps            - Install Go dependencies"
	@echo "  test            - Run tests"
	@echo "  lint            - Run linter"
	@echo "  fmt             - Format code"
	@echo "  clean           - Clean build artifacts"
	@echo "  install         - Install to system (requires sudo)"
	@echo "  uninstall       - Uninstall from system (requires sudo)"
	@echo "  run-dictaphone  - Run dictaphone locally"
	@echo "  run-usb-monitor - Run USB monitor locally"
	@echo "  pregenerate     - Pre-generate TTS cache"
	@echo "  help            - Show this help"
	@echo ""
	@echo "🔧 Environment variables:"
	@echo "  VERSION         - Version string (default: git describe)"
	@echo "  GOOS            - Target OS (default: linux)"
	@echo "  GOARCH          - Target architecture (default: arm64)"
	@echo "  CGO_ENABLED     - Enable CGO (default: 1)"

# Development targets
.PHONY: dev-deps dev-setup

# Install development dependencies
dev-deps:
	@echo "🛠️ Installing development dependencies..."
	@go install github.com/golangci/golangci-lint/cmd/golangci-lint@latest
	@go install golang.org/x/tools/cmd/goimports@latest

# Set up development environment
dev-setup: dev-deps deps
	@echo "🚀 Development environment ready!"
	@echo "💡 Useful commands:"
	@echo "  make build      - Build the application"
	@echo "  make test       - Run tests"
	@echo "  make lint       - Check code quality"
	@echo "  make fmt        - Format code"

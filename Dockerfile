# Multi-stage Dockerfile for Raspberry Pi Dictaphone Go

# Build stage
FROM golang:1.21-alpine AS builder

# Install build dependencies
RUN apk add --no-cache \
    gcc \
    musl-dev \
    alsa-lib-dev \
    pulseaudio-dev \
    libudev-zero-dev \
    git

# Set working directory
WORKDIR /app

# Copy go mod files
COPY go.mod go.sum ./

# Download dependencies
RUN go mod download

# Copy source code
COPY . .

# Build the applications
RUN CGO_ENABLED=1 GOOS=linux go build -ldflags="-s -w" -o bin/dictaphone ./cmd/dictaphone
RUN CGO_ENABLED=1 GOOS=linux go build -ldflags="-s -w" -o bin/usb-monitor ./cmd/usb-monitor

# Runtime stage
FROM alpine:3.18

# Install runtime dependencies
RUN apk add --no-cache \
    alsa-utils \
    pulseaudio \
    mpg123 \
    sox \
    vlc \
    ffmpeg \
    udisks2 \
    udev \
    ca-certificates \
    tzdata

# Create user for running the application
RUN addgroup -g 1000 aleks && \
    adduser -D -s /bin/sh -u 1000 -G aleks aleks && \
    addgroup aleks audio && \
    addgroup aleks input

# Create directories
RUN mkdir -p /opt/dictaphone/{bin,configs,cache,logs} && \
    mkdir -p /home/aleks/{records,cache_tts} && \
    mkdir -p /home/aleks/records/{Заметки,Идеи,Важное,Работа,Личное} && \
    chown -R aleks:aleks /opt/dictaphone /home/aleks

# Copy binaries from builder
COPY --from=builder /app/bin/* /opt/dictaphone/bin/

# Copy configuration and scripts
COPY configs/config.yaml /opt/dictaphone/
COPY scripts/ /opt/dictaphone/scripts/

# Make binaries and scripts executable
RUN chmod +x /opt/dictaphone/bin/* /opt/dictaphone/scripts/*

# Set working directory
WORKDIR /opt/dictaphone

# Create health check script
RUN echo '#!/bin/sh\npgrep -f dictaphone > /dev/null || exit 1' > /opt/dictaphone/healthcheck.sh && \
    chmod +x /opt/dictaphone/healthcheck.sh

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD ["/opt/dictaphone/healthcheck.sh"]

# Switch to non-root user
USER aleks

# Expose any necessary ports (none for this application)
# EXPOSE 8080

# Set environment variables
ENV HOME=/home/aleks
ENV XDG_RUNTIME_DIR=/tmp/runtime-aleks
ENV PULSE_RUNTIME_PATH=/tmp/runtime-aleks/pulse
ENV DICTAPHONE_CONFIG_PATH=/opt/dictaphone/config.yaml

# Create runtime directories
RUN mkdir -p $XDG_RUNTIME_DIR/pulse

# Default command
CMD ["/opt/dictaphone/bin/dictaphone", "--config", "/opt/dictaphone/config.yaml"]

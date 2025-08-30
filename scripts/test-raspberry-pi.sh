#!/bin/bash
set -e

# Test script for Raspberry Pi hardware
# This script should be run on actual Raspberry Pi hardware

echo "🍓 Testing Raspberry Pi Dictaphone on real hardware..."

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Test results
TESTS_PASSED=0
TESTS_FAILED=0

# Function to run a test
run_test() {
    local test_name="$1"
    local test_command="$2"
    
    echo -e "${BLUE}Testing: $test_name${NC}"
    
    if eval "$test_command"; then
        echo -e "${GREEN}✅ PASS: $test_name${NC}"
        ((TESTS_PASSED++))
    else
        echo -e "${RED}❌ FAIL: $test_name${NC}"
        ((TESTS_FAILED++))
    fi
    echo
}

# Check if we're on Raspberry Pi
if ! grep -q "Raspberry Pi" /proc/cpuinfo; then
    echo -e "${YELLOW}⚠️  Warning: This doesn't appear to be a Raspberry Pi${NC}"
fi

# Test 1: System dependencies
echo -e "${BLUE}Checking system dependencies...${NC}"
MISSING_DEPS=""

for dep in aplay arecord mpg123 sox vlc udisksctl; do
    if ! command -v "$dep" >/dev/null 2>&1; then
        MISSING_DEPS="$MISSING_DEPS $dep"
    fi
done

if [ -n "$MISSING_DEPS" ]; then
    echo -e "${RED}❌ Missing dependencies:$MISSING_DEPS${NC}"
    echo "Install with: sudo apt install alsa-utils mpg123 sox vlc udisks2"
    ((TESTS_FAILED++))
else
    echo -e "${GREEN}✅ All system dependencies found${NC}"
    ((TESTS_PASSED++))
fi

# Test 2: Audio devices
run_test "Audio playback devices" "aplay -l | grep -q 'card'"
run_test "Audio recording devices" "arecord -l | grep -q 'card'"

# Test 3: PulseAudio (if available)
if command -v pulseaudio >/dev/null 2>&1; then
    run_test "PulseAudio server" "pulseaudio --check || pulseaudio --start"
    run_test "PulseAudio devices" "pactl list short sources | grep -q '.'"
else
    echo -e "${YELLOW}⚠️  PulseAudio not available, using ALSA only${NC}"
fi

# Test 4: Input devices
run_test "Input devices available" "ls /dev/input/event* >/dev/null 2>&1"

# Test 5: Check for HAOBO remote
if ls /dev/input/by-id/*HAOBO* >/dev/null 2>&1; then
    echo -e "${GREEN}✅ HAOBO remote control detected${NC}"
    ((TESTS_PASSED++))
else
    echo -e "${YELLOW}⚠️  HAOBO remote control not detected${NC}"
    echo "Available input devices:"
    ls /dev/input/by-id/ 2>/dev/null || echo "No input devices found"
fi

# Test 6: USB subsystem
run_test "USB subsystem" "lsusb | grep -q 'Bus'"
run_test "udisks2 service" "systemctl is-active --quiet udisks2 || systemctl status udisks2"

# Test 7: File system permissions
TEST_DIR="/tmp/dictaphone-test"
mkdir -p "$TEST_DIR"
run_test "File system write permissions" "touch '$TEST_DIR/test' && rm '$TEST_DIR/test'"
rmdir "$TEST_DIR"

# Test 8: Network connectivity (for TTS)
run_test "Network connectivity" "ping -c 1 google.com >/dev/null 2>&1"

# Test 9: Go installation (if available)
if command -v go >/dev/null 2>&1; then
    run_test "Go installation" "go version | grep -q 'go version'"
else
    echo -e "${YELLOW}⚠️  Go not installed${NC}"
fi

# Test 10: Build test (if Go is available and source is present)
if command -v go >/dev/null 2>&1 && [ -f "go.mod" ]; then
    echo -e "${BLUE}Testing build for ARM architecture...${NC}"
    
    # Test ARM64 build
    if GOOS=linux GOARCH=arm64 CGO_ENABLED=0 go build -o /tmp/dictaphone-test ./cmd/dictaphone >/dev/null 2>&1; then
        echo -e "${GREEN}✅ ARM64 build successful${NC}"
        rm -f /tmp/dictaphone-test
        ((TESTS_PASSED++))
    else
        echo -e "${RED}❌ ARM64 build failed${NC}"
        ((TESTS_FAILED++))
    fi
    
    # Test ARM32 build
    if GOOS=linux GOARCH=arm GOARM=7 CGO_ENABLED=0 go build -o /tmp/dictaphone-test ./cmd/dictaphone >/dev/null 2>&1; then
        echo -e "${GREEN}✅ ARM32 build successful${NC}"
        rm -f /tmp/dictaphone-test
        ((TESTS_PASSED++))
    else
        echo -e "${RED}❌ ARM32 build failed${NC}"
        ((TESTS_FAILED++))
    fi
fi

# Test 11: Audio playback test
echo -e "${BLUE}Testing audio playback...${NC}"
if command -v speaker-test >/dev/null 2>&1; then
    if timeout 5 speaker-test -t sine -f 1000 -l 1 >/dev/null 2>&1; then
        echo -e "${GREEN}✅ Audio playback test successful${NC}"
        ((TESTS_PASSED++))
    else
        echo -e "${RED}❌ Audio playback test failed${NC}"
        ((TESTS_FAILED++))
    fi
else
    echo -e "${YELLOW}⚠️  speaker-test not available${NC}"
fi

# Test 12: Audio recording test
echo -e "${BLUE}Testing audio recording...${NC}"
TEMP_RECORDING="/tmp/test_recording.wav"
if timeout 2 arecord -d 1 -f cd "$TEMP_RECORDING" >/dev/null 2>&1; then
    if [ -f "$TEMP_RECORDING" ] && [ -s "$TEMP_RECORDING" ]; then
        echo -e "${GREEN}✅ Audio recording test successful${NC}"
        rm -f "$TEMP_RECORDING"
        ((TESTS_PASSED++))
    else
        echo -e "${RED}❌ Audio recording test failed (empty file)${NC}"
        ((TESTS_FAILED++))
    fi
else
    echo -e "${RED}❌ Audio recording test failed${NC}"
    ((TESTS_FAILED++))
fi

# Test 13: System resources
echo -e "${BLUE}Checking system resources...${NC}"

# Memory
TOTAL_MEM=$(free -m | awk 'NR==2{printf "%.0f", $2}')
if [ "$TOTAL_MEM" -lt 512 ]; then
    echo -e "${YELLOW}⚠️  Low memory: ${TOTAL_MEM}MB (recommended: 1GB+)${NC}"
else
    echo -e "${GREEN}✅ Memory: ${TOTAL_MEM}MB${NC}"
    ((TESTS_PASSED++))
fi

# Disk space
AVAILABLE_SPACE=$(df / | awk 'NR==2 {print $4}')
AVAILABLE_SPACE_MB=$((AVAILABLE_SPACE / 1024))
if [ "$AVAILABLE_SPACE_MB" -lt 1000 ]; then
    echo -e "${YELLOW}⚠️  Low disk space: ${AVAILABLE_SPACE_MB}MB (recommended: 2GB+)${NC}"
else
    echo -e "${GREEN}✅ Disk space: ${AVAILABLE_SPACE_MB}MB${NC}"
    ((TESTS_PASSED++))
fi

# CPU temperature (if available)
if [ -f "/sys/class/thermal/thermal_zone0/temp" ]; then
    TEMP=$(cat /sys/class/thermal/thermal_zone0/temp)
    TEMP_C=$((TEMP / 1000))
    if [ "$TEMP_C" -gt 70 ]; then
        echo -e "${YELLOW}⚠️  High CPU temperature: ${TEMP_C}°C${NC}"
    else
        echo -e "${GREEN}✅ CPU temperature: ${TEMP_C}°C${NC}"
        ((TESTS_PASSED++))
    fi
fi

# Test 14: Systemd compatibility
run_test "Systemd available" "systemctl --version | grep -q systemd"

# Test 15: User permissions
echo -e "${BLUE}Checking user permissions...${NC}"

# Audio group
if groups | grep -q audio; then
    echo -e "${GREEN}✅ User in audio group${NC}"
    ((TESTS_PASSED++))
else
    echo -e "${RED}❌ User not in audio group${NC}"
    echo "Add with: sudo usermod -a -G audio \$USER"
    ((TESTS_FAILED++))
fi

# Input group
if groups | grep -q input; then
    echo -e "${GREEN}✅ User in input group${NC}"
    ((TESTS_PASSED++))
else
    echo -e "${YELLOW}⚠️  User not in input group (may need for remote control)${NC}"
    echo "Add with: sudo usermod -a -G input \$USER"
fi

# Summary
echo "===================="
echo "🧪 HARDWARE TEST SUMMARY"
echo "===================="
echo -e "Tests passed: ${GREEN}$TESTS_PASSED${NC}"
echo -e "Tests failed: ${RED}$TESTS_FAILED${NC}"
echo -e "Total tests: $((TESTS_PASSED + TESTS_FAILED))"

# Recommendations
echo ""
echo "📋 RECOMMENDATIONS:"

if [ $TESTS_FAILED -gt 0 ]; then
    echo -e "${RED}🔧 Fix the failed tests before installing the dictaphone${NC}"
fi

echo "1. Ensure all system dependencies are installed"
echo "2. Add user to audio and input groups"
echo "3. Test audio recording/playback manually"
echo "4. Connect HAOBO remote control if available"
echo "5. Ensure stable network connection for TTS"

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${GREEN}🎉 Hardware tests passed! Ready for dictaphone installation.${NC}"
    exit 0
else
    echo -e "${RED}💥 Some hardware tests failed. Please fix issues before proceeding.${NC}"
    exit 1
fi

#!/bin/bash
set -e

# Test script for Raspberry Pi Dictaphone Go
# This script runs various tests to verify the application works correctly

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

echo "🧪 Testing Raspberry Pi Dictaphone Go..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Test results
TESTS_PASSED=0
TESTS_FAILED=0

# Function to run a test
run_test() {
    local test_name="$1"
    local test_command="$2"
    
    echo -e "${BLUE}Running test: $test_name${NC}"
    
    if eval "$test_command"; then
        echo -e "${GREEN}✅ PASS: $test_name${NC}"
        ((TESTS_PASSED++))
    else
        echo -e "${RED}❌ FAIL: $test_name${NC}"
        ((TESTS_FAILED++))
    fi
    echo
}

# Test 1: Go module validation
run_test "Go module validation" "go mod verify"

# Test 2: Code formatting
run_test "Code formatting check" "test -z \$(gofmt -l .)"

# Test 3: Go vet
run_test "Go vet analysis" "go vet ./..."

# Test 4: Build dictaphone (cross-compile for Linux ARM64)
run_test "Build dictaphone for ARM64" "GOOS=linux GOARCH=arm64 CGO_ENABLED=0 go build -o /tmp/dictaphone ./cmd/dictaphone"

# Test 5: Build usb-monitor (cross-compile for Linux ARM64)
run_test "Build usb-monitor for ARM64" "GOOS=linux GOARCH=arm64 CGO_ENABLED=0 go build -o /tmp/usb-monitor ./cmd/usb-monitor"

# Test 6: Configuration validation
run_test "Configuration file validation" "test -f configs/config.yaml"

# Test 7: Systemd service files validation
run_test "Systemd services validation" "test -f systemd/dictaphone.service && test -f systemd/usb-monitor.service"

# Test 8: Installation script validation
run_test "Installation script validation" "test -x scripts/install.sh"

# Test 9: Docker build test (if Docker is available)
if command -v docker >/dev/null 2>&1; then
    run_test "Docker build test" "docker build -t dictaphone-test -f Dockerfile ."
else
    echo -e "${YELLOW}⚠️  SKIP: Docker not available${NC}"
fi

# Test 10: Makefile targets
run_test "Makefile help target" "make help >/dev/null"

# Summary
echo "===================="
echo "🧪 TEST SUMMARY"
echo "===================="
echo -e "Tests passed: ${GREEN}$TESTS_PASSED${NC}"
echo -e "Tests failed: ${RED}$TESTS_FAILED${NC}"
echo -e "Total tests: $((TESTS_PASSED + TESTS_FAILED))"

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${GREEN}🎉 All tests passed!${NC}"
    exit 0
else
    echo -e "${RED}💥 Some tests failed!${NC}"
    exit 1
fi

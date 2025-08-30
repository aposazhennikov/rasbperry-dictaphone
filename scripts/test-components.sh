#!/bin/bash
set -e

# Simple component testing without hardware dependencies
echo "🧪 Testing Raspberry Pi Dictaphone Components (Software Only)..."

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

TESTS_PASSED=0
TESTS_FAILED=0

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

# Test 1: Go module validation
run_test "Go module validation" "go mod verify"

# Test 2: Configuration file validation
run_test "Configuration file exists" "test -f configs/config.yaml"

# Test 3: Test configuration parsing
echo -e "${BLUE}Testing configuration parsing...${NC}"
cat > /tmp/test_config.go << 'EOF'
package main

import (
	"fmt"
	"os"
	"raspberry-dictaphone-go/internal/config"
)

func main() {
	cfg, err := config.Load("configs/config.yaml")
	if err != nil {
		fmt.Printf("Error loading config: %v\n", err)
		os.Exit(1)
	}
	
	// Test parsing
	duration, err := cfg.Audio.GetMaxDuration()
	if err != nil {
		fmt.Printf("Error parsing max duration: %v\n", err)
		os.Exit(1)
	}
	fmt.Printf("Max duration: %v\n", duration)
	
	freeSpace, err := cfg.Audio.GetMinFreeSpaceBytes()
	if err != nil {
		fmt.Printf("Error parsing min free space: %v\n", err)
		os.Exit(1)
	}
	fmt.Printf("Min free space: %d bytes\n", freeSpace)
	
	refreshRate, err := cfg.Visual.GetRefreshRate()
	if err != nil {
		fmt.Printf("Error parsing refresh rate: %v\n", err)
		os.Exit(1)
	}
	fmt.Printf("Refresh rate: %v\n", refreshRate)
	
	fmt.Println("Configuration parsing successful!")
}
EOF

if go run /tmp/test_config.go; then
    echo -e "${GREEN}✅ PASS: Configuration parsing${NC}"
    ((TESTS_PASSED++))
else
    echo -e "${RED}❌ FAIL: Configuration parsing${NC}"
    ((TESTS_FAILED++))
fi
rm -f /tmp/test_config.go
echo

# Test 4: Test menu system
echo -e "${BLUE}Testing menu system...${NC}"
cat > /tmp/test_menu.go << 'EOF'
package main

import (
	"context"
	"fmt"
	"os"
	"raspberry-dictaphone-go/internal/menu"
)

func main() {
	// Create menu manager
	mgr := menu.NewBasicManager()
	
	// Create test menu
	testMenu := mgr.CreateMenu("test", "Test Menu", "Testing")
	
	// Add items
	item1 := menu.NewActionItem("item1", "Item 1", "First item", func(ctx context.Context) error {
		fmt.Println("Item 1 executed")
		return nil
	})
	
	item2 := menu.NewActionItem("item2", "Item 2", "Second item", func(ctx context.Context) error {
		fmt.Println("Item 2 executed")
		return nil
	})
	
	if err := mgr.AddItem(testMenu, item1); err != nil {
		fmt.Printf("Error adding item1: %v\n", err)
		os.Exit(1)
	}
	
	if err := mgr.AddItem(testMenu, item2); err != nil {
		fmt.Printf("Error adding item2: %v\n", err)
		os.Exit(1)
	}
	
	mgr.SetRootMenu(testMenu)
	
	// Test navigation
	result := mgr.Navigate(menu.NavDown)
	if !result.Changed {
		fmt.Println("Navigation failed")
		os.Exit(1)
	}
	
	result = mgr.Navigate(menu.NavUp)
	if !result.Changed {
		fmt.Println("Navigation up failed")
		os.Exit(1)
	}
	
	// Test execution
	ctx := context.Background()
	if err := mgr.ExecuteCurrentItem(ctx); err != nil {
		fmt.Printf("Execution failed: %v\n", err)
		os.Exit(1)
	}
	
	// Test breadcrumb
	breadcrumb := mgr.GetBreadcrumb()
	if len(breadcrumb) == 0 {
		fmt.Println("Breadcrumb empty")
		os.Exit(1)
	}
	
	fmt.Printf("Breadcrumb: %v\n", breadcrumb)
	fmt.Println("Menu system test successful!")
}
EOF

if go run /tmp/test_menu.go; then
    echo -e "${GREEN}✅ PASS: Menu system${NC}"
    ((TESTS_PASSED++))
else
    echo -e "${RED}❌ FAIL: Menu system${NC}"
    ((TESTS_FAILED++))
fi
rm -f /tmp/test_menu.go
echo

# Test 5: Test menu renderer
echo -e "${BLUE}Testing menu renderer...${NC}"
cat > /tmp/test_renderer.go << 'EOF'
package main

import (
	"fmt"
	"os"
	"raspberry-dictaphone-go/internal/menu"
)

func main() {
	// Create renderer
	renderer := menu.NewConsoleRenderer(80, 24)
	
	// Create test menu
	testMenu := &menu.Menu{
		ID:           "test",
		Title:        "Test Menu",
		Description:  "Test menu for rendering",
		Items:        make([]*menu.Item, 0),
		CurrentIndex: 0,
	}
	
	// Add test items
	item1 := menu.NewActionItem("item1", "Test Item 1", "First item", nil)
	item2 := menu.NewActionItem("item2", "Test Item 2 with long title", "Second item", nil)
	sep := menu.NewSeparatorItem("sep1")
	back := menu.NewBackItem()
	
	testMenu.Items = append(testMenu.Items, item1, item2, sep, back)
	
	// Render menu
	output := renderer.RenderMenu(testMenu)
	if output == "" {
		fmt.Println("Renderer produced empty output")
		os.Exit(1)
	}
	
	fmt.Println("Rendered menu:")
	fmt.Println(output)
	
	// Test breadcrumb
	breadcrumb := []string{"Main", "Settings", "Audio"}
	breadcrumbOutput := renderer.RenderBreadcrumb(breadcrumb)
	if breadcrumbOutput == "" {
		fmt.Println("Breadcrumb rendering failed")
		os.Exit(1)
	}
	
	fmt.Printf("Breadcrumb: %s\n", breadcrumbOutput)
	fmt.Println("Renderer test successful!")
}
EOF

if go run /tmp/test_renderer.go; then
    echo -e "${GREEN}✅ PASS: Menu renderer${NC}"
    ((TESTS_PASSED++))
else
    echo -e "${RED}❌ FAIL: Menu renderer${NC}"
    ((TESTS_FAILED++))
fi
rm -f /tmp/test_renderer.go
echo

# Test 6: Test logger
echo -e "${BLUE}Testing logger...${NC}"
cat > /tmp/test_logger.go << 'EOF'
package main

import (
	"fmt"
	"raspberry-dictaphone-go/internal/logger"
)

func main() {
	// Create logger without Sentry
	log, err := logger.New("info", "", false)
	if err != nil {
		fmt.Printf("Error creating logger: %v\n", err)
		return
	}
	defer log.Close()
	
	// Test different log levels
	log.Debug("Debug message")
	log.Info("Info message")
	log.Warn("Warning message")
	log.Error("Error message")
	
	// Test context
	log.SetContext("test", map[string]interface{}{
		"component": "test",
		"test_id":   123,
	})
	
	log.Info("Logger test successful!")
}
EOF

if go run /tmp/test_logger.go; then
    echo -e "${GREEN}✅ PASS: Logger${NC}"
    ((TESTS_PASSED++))
else
    echo -e "${RED}❌ FAIL: Logger${NC}"
    ((TESTS_FAILED++))
fi
rm -f /tmp/test_logger.go
echo

# Test 7: Cross-compilation test (ARM64)
echo -e "${BLUE}Testing cross-compilation for ARM64...${NC}"
if GOOS=linux GOARCH=arm64 CGO_ENABLED=0 go build -o /tmp/dictaphone-arm64 ./cmd/test-components >/dev/null 2>&1; then
    echo -e "${GREEN}✅ PASS: ARM64 cross-compilation${NC}"
    rm -f /tmp/dictaphone-arm64
    ((TESTS_PASSED++))
else
    echo -e "${RED}❌ FAIL: ARM64 cross-compilation${NC}"
    ((TESTS_FAILED++))
fi

# Test 8: Cross-compilation test (ARM32)
echo -e "${BLUE}Testing cross-compilation for ARM32...${NC}"
if GOOS=linux GOARCH=arm GOARM=7 CGO_ENABLED=0 go build -o /tmp/dictaphone-arm32 ./cmd/test-components >/dev/null 2>&1; then
    echo -e "${GREEN}✅ PASS: ARM32 cross-compilation${NC}"
    rm -f /tmp/dictaphone-arm32
    ((TESTS_PASSED++))
else
    echo -e "${RED}❌ FAIL: ARM32 cross-compilation${NC}"
    ((TESTS_FAILED++))
fi

# Test 9: Systemd service files validation
run_test "Systemd service files" "test -f systemd/dictaphone.service && test -f systemd/usb-monitor.service"

# Test 10: Docker files validation
run_test "Docker files" "test -f Dockerfile && test -f docker-compose.yml"

# Summary
echo "===================="
echo "🧪 COMPONENT TEST SUMMARY"
echo "===================="
echo -e "Tests passed: ${GREEN}$TESTS_PASSED${NC}"
echo -e "Tests failed: ${RED}$TESTS_FAILED${NC}"
echo -e "Total tests: $((TESTS_PASSED + TESTS_FAILED))"

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${GREEN}🎉 All component tests passed!${NC}"
    echo ""
    echo "✅ The software components are working correctly"
    echo "✅ Cross-compilation for ARM works"
    echo "✅ Configuration parsing works"
    echo "✅ Menu system is functional"
    echo "✅ Logging system works"
    echo ""
    echo "🚀 Ready for deployment to Raspberry Pi!"
    exit 0
else
    echo -e "${RED}💥 Some component tests failed!${NC}"
    echo "Please fix the issues before deploying."
    exit 1
fi

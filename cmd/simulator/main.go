package main

import (
	"context"
	"fmt"
	"log"
	"os"
	"time"

	"github.com/spf13/cobra"
	"raspberry-dictaphone-go/internal/config"
	"raspberry-dictaphone-go/internal/logger"
	"raspberry-dictaphone-go/internal/menu"
)

// Simulator for testing dictaphone components without real hardware.
type Simulator struct {
	config *config.Config
	logger *logger.Logger
}

// NewSimulator creates a new simulator instance.
func NewSimulator(cfg *config.Config) (*Simulator, error) {
	// Initialize logger without Sentry for testing.
	log, err := logger.New(cfg.Log.Level, "", false)
	if err != nil {
		return nil, fmt.Errorf("failed to initialize logger: %w", err)
	}

	return &Simulator{
		config: cfg,
		logger: log,
	}, nil
}

// SimulateMenuSystem tests the menu system.
func (s *Simulator) SimulateMenuSystem() error {
	s.logger.Info("🧪 Testing menu system...")

	// Create basic menu manager.
	menuMgr := menu.NewBasicManager()

	// Create a simple test menu.
	mainMenu := menuMgr.CreateMenu("main", "Test Menu", "Testing menu functionality")
	
	// Add test items.
	item1 := menu.NewActionItem("item1", "Test Item 1", "First test item", func(ctx context.Context) error {
		s.logger.Info("Executed Test Item 1")
		return nil
	})
	
	item2 := menu.NewActionItem("item2", "Test Item 2", "Second test item", func(ctx context.Context) error {
		s.logger.Info("Executed Test Item 2")
		return nil
	})

	submenu := menuMgr.CreateMenu("submenu", "Test Submenu", "Testing submenu")
	submenuItem := menu.NewSubmenuItem("submenu_item", "Submenu", "Enter submenu", submenu)

	if err := menuMgr.AddItem(mainMenu, item1); err != nil {
		return fmt.Errorf("failed to add item1: %w", err)
	}
	if err := menuMgr.AddItem(mainMenu, item2); err != nil {
		return fmt.Errorf("failed to add item2: %w", err)
	}
	if err := menuMgr.AddItem(mainMenu, submenuItem); err != nil {
		return fmt.Errorf("failed to add submenu item: %w", err)
	}

	// Set as root menu.
	menuMgr.SetRootMenu(mainMenu)

	// Test navigation.
	s.logger.Info("Testing navigation...")
	
	// Navigate down.
	result := menuMgr.Navigate(menu.NavDown)
	if !result.Changed {
		return fmt.Errorf("navigation down failed")
	}
	
	// Navigate up.
	result = menuMgr.Navigate(menu.NavUp)
	if !result.Changed {
		return fmt.Errorf("navigation up failed")
	}

	// Execute current item.
	ctx := context.Background()
	if err := menuMgr.ExecuteCurrentItem(ctx); err != nil {
		return fmt.Errorf("failed to execute current item: %w", err)
	}

	// Test breadcrumb.
	breadcrumb := menuMgr.GetBreadcrumb()
	if len(breadcrumb) == 0 {
		return fmt.Errorf("breadcrumb is empty")
	}

	s.logger.Info("✅ Menu system test passed")
	return nil
}

// SimulateRenderer tests the menu renderer.
func (s *Simulator) SimulateRenderer() error {
	s.logger.Info("🧪 Testing menu renderer...")

	// Create renderer.
	renderer := menu.NewConsoleRenderer(80, 24)

	// Create test menu.
	testMenu := &menu.Menu{
		ID:           "test",
		Title:        "Test Menu",
		Description:  "This is a test menu for renderer testing",
		Items:        make([]*menu.Item, 0),
		CurrentIndex: 0,
	}

	// Add test items.
	items := []*menu.Item{
		menu.NewActionItem("test1", "Test Item 1", "First test item", nil),
		menu.NewActionItem("test2", "Test Item 2 with very long title that might be truncated", "Second test item", nil),
		menu.NewSeparatorItem("sep1"),
		menu.NewActionItem("test3", "Disabled Item", "This item is disabled", nil),
		menu.NewBackItem(),
	}

	// Disable one item for testing.
	items[3].Enabled = false

	for _, item := range items {
		testMenu.Items = append(testMenu.Items, item)
	}

	// Render menu.
	output := renderer.RenderMenu(testMenu)
	if output == "" {
		return fmt.Errorf("renderer produced empty output")
	}

	s.logger.Info("Rendered menu output:")
	fmt.Println(output)

	// Test breadcrumb rendering.
	breadcrumb := []string{"Main Menu", "Settings", "Audio"}
	breadcrumbOutput := renderer.RenderBreadcrumb(breadcrumb)
	if breadcrumbOutput == "" {
		return fmt.Errorf("breadcrumb rendering failed")
	}

	s.logger.Info("Breadcrumb: %s", breadcrumbOutput)

	s.logger.Info("✅ Renderer test passed")
	return nil
}

// SimulateConfig tests configuration loading.
func (s *Simulator) SimulateConfig() error {
	s.logger.Info("🧪 Testing configuration...")

	// Test max duration parsing.
	duration, err := s.config.Audio.GetMaxDuration()
	if err != nil {
		return fmt.Errorf("failed to parse max duration: %w", err)
	}
	s.logger.Info("Max duration: %v", duration)

	// Test min free space parsing.
	freeSpace, err := s.config.Audio.GetMinFreeSpaceBytes()
	if err != nil {
		return fmt.Errorf("failed to parse min free space: %w", err)
	}
	s.logger.Info("Min free space: %d bytes", freeSpace)

	// Test visual config.
	refreshRate, err := s.config.Visual.GetRefreshRate()
	if err != nil {
		return fmt.Errorf("failed to parse refresh rate: %w", err)
	}
	s.logger.Info("Refresh rate: %v", refreshRate)

	s.logger.Info("✅ Configuration test passed")
	return nil
}

// SimulateLogger tests the logging system.
func (s *Simulator) SimulateLogger() error {
	s.logger.Info("🧪 Testing logger...")

	// Test different log levels.
	s.logger.Debug("This is a debug message")
	s.logger.Info("This is an info message")
	s.logger.Warn("This is a warning message")
	s.logger.Error("This is an error message")

	// Test context setting.
	s.logger.SetContext("test", map[string]interface{}{
		"component": "simulator",
		"test_id":   12345,
	})

	// Test breadcrumb.
	s.logger.AddBreadcrumb("test", "Testing breadcrumb functionality", "info")

	s.logger.Info("✅ Logger test passed")
	return nil
}

// RunAllTests runs all simulation tests.
func (s *Simulator) RunAllTests() error {
	tests := []struct {
		name string
		fn   func() error
	}{
		{"Configuration", s.SimulateConfig},
		{"Logger", s.SimulateLogger},
		{"Menu System", s.SimulateMenuSystem},
		{"Renderer", s.SimulateRenderer},
	}

	passed := 0
	failed := 0

	for _, test := range tests {
		fmt.Printf("\n🧪 Running test: %s\n", test.name)
		if err := test.fn(); err != nil {
			fmt.Printf("❌ FAILED: %s - %v\n", test.name, err)
			failed++
		} else {
			fmt.Printf("✅ PASSED: %s\n", test.name)
			passed++
		}
	}

	fmt.Printf("\n📊 Test Results: %d passed, %d failed\n", passed, failed)

	if failed > 0 {
		return fmt.Errorf("%d tests failed", failed)
	}

	return nil
}

func main() {
	var configPath string

	rootCmd := &cobra.Command{
		Use:   "simulator",
		Short: "Dictaphone Component Simulator",
		Long:  "Simulates and tests dictaphone components without requiring real hardware",
		RunE: func(cmd *cobra.Command, args []string) error {
			// Load configuration.
			cfg, err := config.Load(configPath)
			if err != nil {
				return fmt.Errorf("failed to load configuration: %w", err)
			}

			// Create simulator.
			sim, err := NewSimulator(cfg)
			if err != nil {
				return fmt.Errorf("failed to create simulator: %w", err)
			}

			// Run all tests.
			return sim.RunAllTests()
		},
	}

	// Add flags.
	rootCmd.PersistentFlags().StringVarP(&configPath, "config", "c", "", "Path to configuration file")

	// Add individual test commands.
	menuCmd := &cobra.Command{
		Use:   "menu",
		Short: "Test menu system",
		RunE: func(cmd *cobra.Command, args []string) error {
			cfg, err := config.Load(configPath)
			if err != nil {
				return err
			}
			sim, err := NewSimulator(cfg)
			if err != nil {
				return err
			}
			return sim.SimulateMenuSystem()
		},
	}

	rendererCmd := &cobra.Command{
		Use:   "renderer",
		Short: "Test menu renderer",
		RunE: func(cmd *cobra.Command, args []string) error {
			cfg, err := config.Load(configPath)
			if err != nil {
				return err
			}
			sim, err := NewSimulator(cfg)
			if err != nil {
				return err
			}
			return sim.SimulateRenderer()
		},
	}

	configCmd := &cobra.Command{
		Use:   "config",
		Short: "Test configuration loading",
		RunE: func(cmd *cobra.Command, args []string) error {
			cfg, err := config.Load(configPath)
			if err != nil {
				return err
			}
			sim, err := NewSimulator(cfg)
			if err != nil {
				return err
			}
			return sim.SimulateConfig()
		},
	}

	rootCmd.AddCommand(menuCmd, rendererCmd, configCmd)

	if err := rootCmd.Execute(); err != nil {
		log.Fatal(err)
	}
}

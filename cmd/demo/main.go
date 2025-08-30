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

// Demo application for testing components without hardware dependencies.
func main() {
	var configPath string

	rootCmd := &cobra.Command{
		Use:   "demo",
		Short: "Dictaphone Demo Mode",
		Long:  "Demonstrates dictaphone functionality without hardware dependencies",
		RunE: func(cmd *cobra.Command, args []string) error {
			return runDemo(configPath)
		},
	}

	rootCmd.PersistentFlags().StringVarP(&configPath, "config", "c", "", "Path to configuration file")

	if err := rootCmd.Execute(); err != nil {
		log.Fatal(err)
	}
}

func runDemo(configPath string) error {
	fmt.Println("🎙️ Raspberry Pi Dictaphone - Demo Mode")
	fmt.Println("======================================")

	// Load configuration
	fmt.Println("📋 Loading configuration...")
	cfg, err := config.Load(configPath)
	if err != nil {
		return fmt.Errorf("failed to load configuration: %w", err)
	}
	fmt.Printf("✅ Configuration loaded: %s v%s\n", cfg.App.Name, cfg.App.Version)

	// Initialize logger
	fmt.Println("📝 Initializing logger...")
	logger, err := logger.New(cfg.Log.Level, "", false) // No Sentry in demo
	if err != nil {
		return fmt.Errorf("failed to initialize logger: %w", err)
	}
	defer logger.Close()
	fmt.Println("✅ Logger initialized")

	// Test configuration parsing
	fmt.Println("⚙️ Testing configuration parsing...")
	duration, err := cfg.Audio.GetMaxDuration()
	if err != nil {
		return fmt.Errorf("failed to parse max duration: %w", err)
	}
	fmt.Printf("   Max recording duration: %v\n", duration)

	freeSpace, err := cfg.Audio.GetMinFreeSpaceBytes()
	if err != nil {
		return fmt.Errorf("failed to parse min free space: %w", err)
	}
	fmt.Printf("   Min free space: %d bytes (%.1f MB)\n", freeSpace, float64(freeSpace)/(1024*1024))

	refreshRate, err := cfg.Visual.GetRefreshRate()
	if err != nil {
		return fmt.Errorf("failed to parse refresh rate: %w", err)
	}
	fmt.Printf("   Visual refresh rate: %v\n", refreshRate)
	fmt.Println("✅ Configuration parsing successful")

	// Test menu system
	fmt.Println("📋 Testing menu system...")
	menuManager := menu.NewBasicManager()

	// Create demo menu
	mainMenu := menuManager.CreateMenu("main", "Демо Меню", "Демонстрация функциональности меню")
	
	// Add demo items
	recordItem := menu.NewActionItem("record", "🎙️ Запись", "Начать запись аудио", func(ctx context.Context) error {
		fmt.Println("   🎙️ Демо: Начинаю запись...")
		time.Sleep(1 * time.Second)
		fmt.Println("   ⏸️ Демо: Запись приостановлена")
		return nil
	})

	playItem := menu.NewActionItem("play", "▶️ Воспроизведение", "Воспроизвести записи", func(ctx context.Context) error {
		fmt.Println("   ▶️ Демо: Воспроизведение файла...")
		time.Sleep(1 * time.Second)
		fmt.Println("   ⏹️ Демо: Воспроизведение остановлено")
		return nil
	})

	settingsMenu := menuManager.CreateMenu("settings", "Настройки", "Настройки системы")
	settingsItem := menu.NewSubmenuItem("settings_item", "⚙️ Настройки", "Перейти в настройки", settingsMenu)

	// Add settings items
	ttsItem := menu.NewActionItem("tts", "🗣️ Голос", "Настройки синтеза речи", func(ctx context.Context) error {
		fmt.Println("   🗣️ Демо: Текущий голос - ru-RU-Standard-A")
		return nil
	})
	
	volumeItem := menu.NewActionItem("volume", "🔊 Громкость", "Настройка громкости", func(ctx context.Context) error {
		fmt.Println("   🔊 Демо: Громкость - 80%")
		return nil
	})

	backItem := menu.NewBackItem()

	// Build menu structure
	menuManager.AddItem(mainMenu, recordItem)
	menuManager.AddItem(mainMenu, playItem)
	menuManager.AddItem(mainMenu, settingsItem)

	menuManager.AddItem(settingsMenu, ttsItem)
	menuManager.AddItem(settingsMenu, volumeItem)
	menuManager.AddItem(settingsMenu, backItem)

	menuManager.SetRootMenu(mainMenu)
	fmt.Println("✅ Menu system initialized")

	// Test menu renderer
	fmt.Println("🖥️ Testing menu renderer...")
	renderer := menu.NewConsoleRenderer(80, 24)
	output := renderer.RenderMenu(mainMenu)
	fmt.Println("📄 Rendered main menu:")
	fmt.Println(output)

	// Test navigation
	fmt.Println("🧭 Testing navigation...")
	fmt.Println("   Navigating down...")
	result := menuManager.Navigate(menu.NavDown)
	if result.Changed {
		fmt.Printf("   Current item: %s\n", result.CurrentItem.Title)
	}

	fmt.Println("   Navigating down again...")
	result = menuManager.Navigate(menu.NavDown)
	if result.Changed {
		fmt.Printf("   Current item: %s\n", result.CurrentItem.Title)
	}

	fmt.Println("   Entering settings...")
	result = menuManager.Navigate(menu.NavSelect)
	if result.Changed {
		fmt.Printf("   Entered: %s\n", result.CurrentMenu.Title)
		
		// Render settings menu
		settingsOutput := renderer.RenderMenu(result.CurrentMenu)
		fmt.Println("📄 Settings menu:")
		fmt.Println(settingsOutput)
	}

	// Test breadcrumb
	breadcrumb := menuManager.GetBreadcrumb()
	fmt.Printf("🍞 Breadcrumb: %v\n", breadcrumb)

	// Execute current item
	fmt.Println("⚡ Executing current menu item...")
	ctx := context.Background()
	err = menuManager.ExecuteCurrentItem(ctx)
	if err != nil {
		fmt.Printf("   Error: %v\n", err)
	}

	// Go back
	fmt.Println("   Going back...")
	result = menuManager.Navigate(menu.NavBack)
	if result.Changed {
		fmt.Printf("   Returned to: %s\n", result.CurrentMenu.Title)
	}

	fmt.Println("✅ Navigation testing completed")

	// Test logger
	fmt.Println("📝 Testing logger...")
	logger.Debug("This is a debug message")
	logger.Info("This is an info message")
	logger.Warn("This is a warning message")
	logger.Error("This is an error message")
	fmt.Println("✅ Logger testing completed")

	// Demo summary
	fmt.Println("")
	fmt.Println("🎉 DEMO COMPLETED SUCCESSFULLY!")
	fmt.Println("==============================")
	fmt.Println("✅ Configuration loading and parsing")
	fmt.Println("✅ Menu system and navigation")
	fmt.Println("✅ Menu rendering")
	fmt.Println("✅ Action execution")
	fmt.Println("✅ Breadcrumb navigation")
	fmt.Println("✅ Logging system")
	fmt.Println("")
	fmt.Println("🍓 Ready for deployment to Raspberry Pi!")

	return nil
}

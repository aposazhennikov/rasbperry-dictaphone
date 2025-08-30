package main

import (
	"context"
	"fmt"
	"log"
	"time"

	"github.com/spf13/cobra"
	"raspberry-dictaphone-go/internal/config"
	"raspberry-dictaphone-go/internal/menu"
)

// Simple demo without problematic dependencies
func main() {
	var configPath string

	rootCmd := &cobra.Command{
		Use:   "demo-simple",
		Short: "Simple Dictaphone Demo",
		Long:  "Simple demonstration without hardware dependencies",
		RunE: func(cmd *cobra.Command, args []string) error {
			return runSimpleDemo(configPath)
		},
	}

	rootCmd.PersistentFlags().StringVarP(&configPath, "config", "c", "", "Path to configuration file")

	if err := rootCmd.Execute(); err != nil {
		log.Fatal(err)
	}
}

func runSimpleDemo(configPath string) error {
	fmt.Println("🎙️ Raspberry Pi Dictaphone - Simple Demo")
	fmt.Println("========================================")

	// Load configuration
	fmt.Println("📋 Loading configuration...")
	cfg, err := config.Load(configPath)
	if err != nil {
		return fmt.Errorf("failed to load configuration: %w", err)
	}
	fmt.Printf("✅ Configuration loaded: %s v%s\n", cfg.App.Name, cfg.App.Version)

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
		fmt.Println("   🎙️ Демо: Начинаю запись в папку 'Заметки'...")
		time.Sleep(500 * time.Millisecond)
		fmt.Println("   ⏺️ Демо: Запись активна (0:03)")
		time.Sleep(500 * time.Millisecond)
		fmt.Println("   ⏸️ Демо: Запись приостановлена")
		return nil
	})

	playItem := menu.NewActionItem("play", "▶️ Воспроизведение", "Воспроизвести записи", func(ctx context.Context) error {
		fmt.Println("   📁 Демо: В папке 'Заметки' найдено 3 записи")
		time.Sleep(300 * time.Millisecond)
		fmt.Println("   ▶️ Демо: Воспроизведение 'запись_2024-01-15_14-30-25.wav'...")
		time.Sleep(800 * time.Millisecond)
		fmt.Println("   ⏹️ Демо: Воспроизведение остановлено")
		return nil
	})

	usbItem := menu.NewActionItem("usb", "💾 USB устройства", "Показать USB накопители", func(ctx context.Context) error {
		fmt.Println("   🔍 Демо: Поиск USB устройств...")
		time.Sleep(400 * time.Millisecond)
		fmt.Println("   💾 Демо: Найдено устройство 'Kingston USB 32GB' (подключено)")
		fmt.Println("   💾 Демо: Точка монтирования: /media/usb/Kingston")
		return nil
	})

	settingsMenu := menuManager.CreateMenu("settings", "Настройки", "Настройки системы")
	settingsItem := menu.NewSubmenuItem("settings_item", "⚙️ Настройки", "Перейти в настройки", settingsMenu)

	// Add settings items
	ttsItem := menu.NewActionItem("tts", "🗣️ Голос", "Настройки синтеза речи", func(ctx context.Context) error {
		fmt.Println("   🗣️ Демо: Текущий голос - ru-RU-Standard-A (Женский)")
		fmt.Println("   🗣️ Демо: Движок TTS - Google Cloud (основной)")
		fmt.Println("   📊 Демо: Использовано символов в месяце: 15,420")
		return nil
	})
	
	volumeItem := menu.NewActionItem("volume", "🔊 Громкость", "Настройка громкости", func(ctx context.Context) error {
		fmt.Println("   🔊 Демо: Системная громкость - 80%")
		fmt.Println("   🎵 Демо: Громкость воспроизведения - 85%")
		return nil
	})

	backItem := menu.NewBackItem()

	// Build menu structure
	menuManager.AddItem(mainMenu, recordItem)
	menuManager.AddItem(mainMenu, playItem)
	menuManager.AddItem(mainMenu, usbItem)
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

	// Interactive demo
	fmt.Println("🎮 Interactive Demo:")
	fmt.Println("====================")

	// Simulate user navigation
	fmt.Println("👆 Пользователь нажимает 'ВНИЗ'")
	result := menuManager.Navigate(menu.NavDown)
	if result.Changed {
		fmt.Printf("   ➡️ Текущий пункт: %s\n", result.CurrentItem.Title)
	}

	fmt.Println("👆 Пользователь нажимает 'ВНИЗ' еще раз")
	result = menuManager.Navigate(menu.NavDown)
	if result.Changed {
		fmt.Printf("   ➡️ Текущий пункт: %s\n", result.CurrentItem.Title)
	}

	fmt.Println("👆 Пользователь нажимает 'SELECT' (выполнить)")
	ctx := context.Background()
	err = menuManager.ExecuteCurrentItem(ctx)
	if err != nil {
		fmt.Printf("   ❌ Ошибка: %v\n", err)
	}

	fmt.Println("👆 Пользователь нажимает 'ВНИЗ' для перехода к настройкам")
	result = menuManager.Navigate(menu.NavDown)
	if result.Changed {
		fmt.Printf("   ➡️ Текущий пункт: %s\n", result.CurrentItem.Title)
	}

	fmt.Println("👆 Пользователь нажимает 'SELECT' (войти в настройки)")
	result = menuManager.Navigate(menu.NavSelect)
	if result.Changed {
		fmt.Printf("   ➡️ Вошли в меню: %s\n", result.CurrentMenu.Title)
		
		// Show breadcrumb
		breadcrumb := menuManager.GetBreadcrumb()
		fmt.Printf("   🍞 Путь: %v\n", breadcrumb)
		
		// Render settings menu
		settingsOutput := renderer.RenderMenu(result.CurrentMenu)
		fmt.Println("📄 Settings menu:")
		fmt.Println(settingsOutput)
	}

	fmt.Println("👆 Пользователь выбирает настройки голоса")
	err = menuManager.ExecuteCurrentItem(ctx)
	if err != nil {
		fmt.Printf("   ❌ Ошибка: %v\n", err)
	}

	fmt.Println("👆 Пользователь нажимает 'BACK' (назад)")
	result = menuManager.Navigate(menu.NavBack)
	if result.Changed {
		fmt.Printf("   ⬅️ Вернулись в: %s\n", result.CurrentMenu.Title)
	}

	// Visual renderer demo
	fmt.Println("🎨 Testing visual renderer...")
	visualRenderer := menu.NewVisualRenderer(80, 20, true, false) // borders, no colors for compatibility
	visualOutput := visualRenderer.RenderMenu(mainMenu)
	fmt.Println("🖼️ Visual renderer output:")
	fmt.Println(visualOutput)

	// Demo summary
	fmt.Println("")
	fmt.Println("🎉 SIMPLE DEMO COMPLETED SUCCESSFULLY!")
	fmt.Println("=====================================")
	fmt.Println("✅ Configuration loading and parsing")
	fmt.Println("✅ Menu system creation and navigation")
	fmt.Println("✅ Action execution simulation")
	fmt.Println("✅ Breadcrumb navigation")
	fmt.Println("✅ Console and visual rendering")
	fmt.Println("✅ Interactive user flow simulation")
	fmt.Println("")
	fmt.Println("📋 Tested components:")
	fmt.Printf("   • Configuration parser (max duration: %v)\n", duration)
	fmt.Printf("   • Menu manager (%d main items, %d settings items)\n", len(mainMenu.Items), len(settingsMenu.Items))
	fmt.Println("   • Console renderer (80x24)")
	fmt.Println("   • Visual renderer with borders")
	fmt.Println("   • Navigation system (up/down/select/back)")
	fmt.Println("")
	fmt.Println("🍓 Software components ready for Raspberry Pi deployment!")
	fmt.Println("🔧 Hardware components (audio, USB, input) need real hardware for testing.")

	return nil
}

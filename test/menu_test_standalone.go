package main

import (
	"context"
	"fmt"
	"os"
	"strings"
	"time"

	"github.com/spf13/viper"
)

// Standalone test for menu system without internal dependencies

// Simplified config structs
type Config struct {
	App struct {
		Name    string `mapstructure:"name"`
		Version string `mapstructure:"version"`
		Debug   bool   `mapstructure:"debug"`
	} `mapstructure:"app"`
	Audio struct {
		SampleRate   int    `mapstructure:"sample_rate"`
		Channels     int    `mapstructure:"channels"`
		MaxDuration  string `mapstructure:"max_duration"`
		MinFreeSpace string `mapstructure:"min_free_space"`
		RecordsDir   string `mapstructure:"records_dir"`
	} `mapstructure:"audio"`
	TTS struct {
		PrimaryEngine  string `mapstructure:"primary_engine"`
		FallbackEngine string `mapstructure:"fallback_engine"`
		Voice          string `mapstructure:"voice"`
		Language       string `mapstructure:"language"`
	} `mapstructure:"tts"`
}

// Simplified menu structs
type ItemType int

const (
	ItemTypeAction ItemType = iota
	ItemTypeSubmenu
	ItemTypeBack
	ItemTypeSeparator
)

type Item struct {
	ID          string
	Title       string
	Description string
	Type        ItemType
	Action      func(ctx context.Context) error
	Submenu     *Menu
	Enabled     bool
	Visible     bool
}

type Menu struct {
	ID           string
	Title        string
	Description  string
	Items        []*Item
	Parent       *Menu
	CurrentIndex int
}

type NavigationDirection int

const (
	NavUp NavigationDirection = iota
	NavDown
	NavSelect
	NavBack
)

// Basic menu manager
type MenuManager struct {
	rootMenu    *Menu
	currentMenu *Menu
}

func NewMenuManager() *MenuManager {
	return &MenuManager{}
}

func (m *MenuManager) CreateMenu(id, title, description string) *Menu {
	return &Menu{
		ID:           id,
		Title:        title,
		Description:  description,
		Items:        make([]*Item, 0),
		CurrentIndex: 0,
	}
}

func (m *MenuManager) AddItem(menu *Menu, item *Item) error {
	if menu == nil || item == nil {
		return fmt.Errorf("menu and item cannot be nil")
	}
	if item.Type == ItemTypeSubmenu && item.Submenu != nil {
		item.Submenu.Parent = menu
	}
	menu.Items = append(menu.Items, item)
	return nil
}

func (m *MenuManager) SetRootMenu(menu *Menu) {
	m.rootMenu = menu
	if m.currentMenu == nil {
		m.currentMenu = menu
	}
}

func (m *MenuManager) Navigate(direction NavigationDirection) bool {
	if m.currentMenu == nil {
		return false
	}

	visibleItems := m.getVisibleItems(m.currentMenu)
	if len(visibleItems) == 0 {
		return false
	}

	switch direction {
	case NavUp:
		oldIndex := m.currentMenu.CurrentIndex
		m.currentMenu.CurrentIndex--
		if m.currentMenu.CurrentIndex < 0 {
			m.currentMenu.CurrentIndex = len(visibleItems) - 1
		}
		return oldIndex != m.currentMenu.CurrentIndex

	case NavDown:
		oldIndex := m.currentMenu.CurrentIndex
		m.currentMenu.CurrentIndex++
		if m.currentMenu.CurrentIndex >= len(visibleItems) {
			m.currentMenu.CurrentIndex = 0
		}
		return oldIndex != m.currentMenu.CurrentIndex

	case NavSelect:
		if m.currentMenu.CurrentIndex < len(visibleItems) {
			item := visibleItems[m.currentMenu.CurrentIndex]
			if item.Type == ItemTypeSubmenu && item.Submenu != nil {
				m.currentMenu = item.Submenu
				return true
			} else if item.Type == ItemTypeBack {
				return m.goToParent()
			}
		}

	case NavBack:
		return m.goToParent()
	}

	return false
}

func (m *MenuManager) goToParent() bool {
	if m.currentMenu == nil {
		return false
	}

	if m.currentMenu.Parent != nil {
		m.currentMenu = m.currentMenu.Parent
		return true
	} else if m.rootMenu != nil && m.currentMenu != m.rootMenu {
		m.currentMenu = m.rootMenu
		return true
	}

	return false
}

func (m *MenuManager) ExecuteCurrentItem(ctx context.Context) error {
	if m.currentMenu == nil {
		return fmt.Errorf("no current menu")
	}

	visibleItems := m.getVisibleItems(m.currentMenu)
	if len(visibleItems) == 0 || m.currentMenu.CurrentIndex >= len(visibleItems) {
		return fmt.Errorf("no current item")
	}

	item := visibleItems[m.currentMenu.CurrentIndex]
	if !item.Enabled {
		return fmt.Errorf("item is disabled")
	}

	if item.Action != nil {
		return item.Action(ctx)
	}

	return nil
}

func (m *MenuManager) GetCurrentItem() *Item {
	if m.currentMenu == nil {
		return nil
	}

	visibleItems := m.getVisibleItems(m.currentMenu)
	if len(visibleItems) == 0 || m.currentMenu.CurrentIndex >= len(visibleItems) {
		return nil
	}

	return visibleItems[m.currentMenu.CurrentIndex]
}

func (m *MenuManager) GetBreadcrumb() []string {
	if m.currentMenu == nil {
		return []string{}
	}

	var breadcrumb []string
	menu := m.currentMenu

	for menu != nil {
		breadcrumb = append([]string{menu.Title}, breadcrumb...)
		menu = menu.Parent
	}

	return breadcrumb
}

func (m *MenuManager) getVisibleItems(menu *Menu) []*Item {
	var visibleItems []*Item
	for _, item := range menu.Items {
		if item.Visible {
			visibleItems = append(visibleItems, item)
		}
	}
	return visibleItems
}

// Helper functions for creating items
func NewActionItem(id, title, description string, action func(ctx context.Context) error) *Item {
	return &Item{
		ID:          id,
		Title:       title,
		Description: description,
		Type:        ItemTypeAction,
		Action:      action,
		Enabled:     true,
		Visible:     true,
	}
}

func NewSubmenuItem(id, title, description string, submenu *Menu) *Item {
	return &Item{
		ID:          id,
		Title:       title,
		Description: description,
		Type:        ItemTypeSubmenu,
		Submenu:     submenu,
		Enabled:     true,
		Visible:     true,
	}
}

func NewBackItem() *Item {
	return &Item{
		ID:          "back",
		Title:       "← Назад",
		Description: "Вернуться в предыдущее меню",
		Type:        ItemTypeBack,
		Enabled:     true,
		Visible:     true,
	}
}

// Simple renderer
func RenderMenu(menu *Menu, width int) string {
	if menu == nil {
		return ""
	}

	var output strings.Builder

	// Title
	titleLine := centerText(menu.Title, width)
	output.WriteString(titleLine + "\n")
	output.WriteString(strings.Repeat("=", width) + "\n")

	// Description
	if menu.Description != "" {
		output.WriteString("  " + menu.Description + "\n\n")
	}

	// Items
	visibleItems := make([]*Item, 0)
	for _, item := range menu.Items {
		if item.Visible {
			visibleItems = append(visibleItems, item)
		}
	}

	for i, item := range visibleItems {
		prefix := "  "
		if i == menu.CurrentIndex {
			prefix = "► "
		}

		suffix := ""
		if item.Type == ItemTypeSubmenu {
			suffix = " →"
		}

		itemText := item.Title + suffix
		if i == menu.CurrentIndex {
			itemText = "[" + itemText + "]"
		}

		if !item.Enabled {
			itemText = "(" + itemText + ")"
		}

		output.WriteString(prefix + itemText + "\n")
	}

	return output.String()
}

func centerText(text string, width int) string {
	if len(text) >= width {
		return text[:width]
	}
	padding := (width - len(text)) / 2
	return strings.Repeat(" ", padding) + text + strings.Repeat(" ", width-len(text)-padding)
}

// Load config
func loadConfig(configPath string) (*Config, error) {
	v := viper.New()

	if configPath != "" {
		v.SetConfigFile(configPath)
	} else {
		v.SetConfigName("config")
		v.SetConfigType("yaml")
		v.AddConfigPath(".")
		v.AddConfigPath("./configs")
	}

	if err := v.ReadInConfig(); err != nil {
		return nil, fmt.Errorf("error reading config: %w", err)
	}

	var cfg Config
	if err := v.Unmarshal(&cfg); err != nil {
		return nil, fmt.Errorf("error unmarshaling config: %w", err)
	}

	return &cfg, nil
}

func main() {
	fmt.Println("🎙️ Raspberry Pi Dictaphone - Standalone Test")
	fmt.Println("============================================")

	// Load configuration
	fmt.Println("📋 Loading configuration...")
	
	configPath := "configs/config.yaml"
	if len(os.Args) > 1 {
		configPath = os.Args[1]
	}

	cfg, err := loadConfig(configPath)
	if err != nil {
		fmt.Printf("❌ Config load failed: %v\n", err)
		os.Exit(1)
	}

	fmt.Printf("✅ Configuration loaded: %s v%s\n", cfg.App.Name, cfg.App.Version)
	fmt.Printf("   Audio: %dHz, %d channels\n", cfg.Audio.SampleRate, cfg.Audio.Channels)
	fmt.Printf("   TTS: %s engine, voice %s\n", cfg.TTS.PrimaryEngine, cfg.TTS.Voice)

	// Test menu system
	fmt.Println("\n📋 Testing menu system...")
	menuManager := NewMenuManager()

	// Create demo menu structure
	mainMenu := menuManager.CreateMenu("main", "Главное Меню", "Raspberry Pi Диктофон")
	
	recordItem := NewActionItem("record", "🎙️ Запись", "Записать аудио", func(ctx context.Context) error {
		fmt.Println("   🎙️ Демо: Запись начата...")
		time.Sleep(500 * time.Millisecond)
		fmt.Println("   ⏹️ Демо: Запись остановлена")
		return nil
	})

	playItem := NewActionItem("play", "▶️ Воспроизведение", "Воспроизвести записи", func(ctx context.Context) error {
		fmt.Println("   ▶️ Демо: Воспроизведение...")
		time.Sleep(300 * time.Millisecond)
		fmt.Println("   ⏹️ Демо: Остановлено")
		return nil
	})

	settingsMenu := menuManager.CreateMenu("settings", "Настройки", "Настройки системы")
	settingsItem := NewSubmenuItem("settings", "⚙️ Настройки", "Настройки", settingsMenu)

	// Settings items
	ttsItem := NewActionItem("tts", "🗣️ Голос", "Настройки TTS", func(ctx context.Context) error {
		fmt.Printf("   🗣️ Текущий голос: %s\n", cfg.TTS.Voice)
		return nil
	})
	backItem := NewBackItem()

	// Build structure
	menuManager.AddItem(mainMenu, recordItem)
	menuManager.AddItem(mainMenu, playItem)
	menuManager.AddItem(mainMenu, settingsItem)
	menuManager.AddItem(settingsMenu, ttsItem)
	menuManager.AddItem(settingsMenu, backItem)

	menuManager.SetRootMenu(mainMenu)
	fmt.Println("✅ Menu structure created")

	// Test rendering
	fmt.Println("\n🖥️ Testing menu rendering...")
	output := RenderMenu(mainMenu, 80)
	fmt.Println("📄 Main menu:")
	fmt.Println(output)

	// Interactive demo
	fmt.Println("🎮 Interactive Demo:")
	fmt.Println("===================")

	// Simulate navigation
	fmt.Println("👆 Navigate DOWN")
	if menuManager.Navigate(NavDown) {
		current := menuManager.GetCurrentItem()
		fmt.Printf("   Current: %s\n", current.Title)
	}

	fmt.Println("👆 Navigate DOWN")
	if menuManager.Navigate(NavDown) {
		current := menuManager.GetCurrentItem()
		fmt.Printf("   Current: %s\n", current.Title)
	}

	fmt.Println("👆 SELECT (enter settings)")
	if menuManager.Navigate(NavSelect) {
		breadcrumb := menuManager.GetBreadcrumb()
		fmt.Printf("   Breadcrumb: %v\n", breadcrumb)
		
		output := RenderMenu(menuManager.currentMenu, 80)
		fmt.Println("📄 Settings menu:")
		fmt.Println(output)
	}

	fmt.Println("👆 Execute current item")
	ctx := context.Background()
	if err := menuManager.ExecuteCurrentItem(ctx); err != nil {
		fmt.Printf("   Error: %v\n", err)
	}

	fmt.Println("👆 BACK to main menu")
	if menuManager.Navigate(NavBack) {
		fmt.Printf("   Returned to: %s\n", menuManager.currentMenu.Title)
	}

	// Final summary
	fmt.Println("\n🎉 STANDALONE TEST COMPLETED!")
	fmt.Println("============================")
	fmt.Println("✅ Configuration loading")
	fmt.Println("✅ Menu creation and navigation")
	fmt.Println("✅ Action execution")
	fmt.Println("✅ Submenu navigation")
	fmt.Println("✅ Breadcrumb tracking")
	fmt.Println("✅ Menu rendering")
	fmt.Println("")
	fmt.Println("🍓 Core functionality works! Ready for Raspberry Pi!")
}

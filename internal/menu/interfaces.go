package menu

import (
	"context"
)

// ItemType represents the type of menu item.
type ItemType int

const (
	// ItemTypeAction represents an action item.
	ItemTypeAction ItemType = iota
	// ItemTypeSubmenu represents a submenu item.
	ItemTypeSubmenu
	// ItemTypeBack represents a back/return item.
	ItemTypeBack
	// ItemTypeSeparator represents a separator item.
	ItemTypeSeparator
)

// Item represents a menu item.
type Item struct {
	ID          string                 `json:"id"`
	Title       string                 `json:"title"`
	Description string                 `json:"description"`
	Type        ItemType               `json:"type"`
	Action      func(ctx context.Context) error `json:"-"`
	Submenu     *Menu                  `json:"submenu,omitempty"`
	Enabled     bool                   `json:"enabled"`
	Visible     bool                   `json:"visible"`
	Data        map[string]interface{} `json:"data,omitempty"`
}

// Menu represents a menu with items.
type Menu struct {
	ID          string  `json:"id"`
	Title       string  `json:"title"`
	Description string  `json:"description"`
	Items       []*Item `json:"items"`
	Parent      *Menu   `json:"-"`
	CurrentIndex int     `json:"current_index"`
}

// NavigationDirection represents navigation direction.
type NavigationDirection int

const (
	// NavUp moves up in the menu.
	NavUp NavigationDirection = iota
	// NavDown moves down in the menu.
	NavDown
	// NavSelect selects current item.
	NavSelect
	// NavBack goes back to parent menu.
	NavBack
)

// NavigationResult represents the result of navigation.
type NavigationResult struct {
	Changed     bool   `json:"changed"`
	CurrentMenu *Menu  `json:"current_menu"`
	CurrentItem *Item  `json:"current_item"`
	Message     string `json:"message,omitempty"`
	Error       error  `json:"-"`
}

// Manager defines the interface for menu management.
type Manager interface {
	// CreateMenu creates a new menu.
	CreateMenu(id, title, description string) *Menu

	// AddItem adds an item to a menu.
	AddItem(menu *Menu, item *Item) error

	// RemoveItem removes an item from a menu.
	RemoveItem(menu *Menu, itemID string) error

	// SetCurrentMenu sets the current active menu.
	SetCurrentMenu(menu *Menu) error

	// GetCurrentMenu returns the current active menu.
	GetCurrentMenu() *Menu

	// Navigate performs navigation in the current menu.
	Navigate(direction NavigationDirection) NavigationResult

	// ExecuteCurrentItem executes the current menu item.
	ExecuteCurrentItem(ctx context.Context) error

	// GetCurrentItem returns the current menu item.
	GetCurrentItem() *Item

	// GoToParent navigates to parent menu.
	GoToParent() NavigationResult

	// GoToRoot navigates to root menu.
	GoToRoot() NavigationResult

	// GetBreadcrumb returns the current menu breadcrumb.
	GetBreadcrumb() []string

	// SetRootMenu sets the root menu.
	SetRootMenu(menu *Menu)

	// GetRootMenu returns the root menu.
	GetRootMenu() *Menu

	// FindMenu finds a menu by ID.
	FindMenu(id string) *Menu

	// FindItem finds an item by ID in current menu hierarchy.
	FindItem(id string) *Item

	// GetVisibleItems returns visible items from current menu.
	GetVisibleItems() []*Item

	// GetEnabledItems returns enabled items from current menu.
	GetEnabledItems() []*Item

	// RefreshMenu refreshes the current menu state.
	RefreshMenu()

	// GetMenuPath returns the path to current menu.
	GetMenuPath() string
}

// Builder defines the interface for building menu structures.
type Builder interface {
	// BuildMainMenu builds the main menu structure.
	BuildMainMenu() *Menu

	// BuildRecordingMenu builds the recording menu.
	BuildRecordingMenu() *Menu

	// BuildPlaybackMenu builds the playback menu.
	BuildPlaybackMenu() *Menu

	// BuildSettingsMenu builds the settings menu.
	BuildSettingsMenu() *Menu

	// BuildUSBMenu builds the USB devices menu.
	BuildUSBMenu() *Menu

	// BuildRadioMenu builds the radio stations menu.
	BuildRadioMenu() *Menu

	// BuildSystemMenu builds the system menu.
	BuildSystemMenu() *Menu

	// AddDynamicItems adds dynamic items to a menu (e.g., file lists).
	AddDynamicItems(menu *Menu, itemType string) error

	// RefreshDynamicItems refreshes dynamic menu items.
	RefreshDynamicItems(menu *Menu) error
}

// Renderer defines the interface for rendering menus.
type Renderer interface {
	// RenderMenu renders a menu to string.
	RenderMenu(menu *Menu) string

	// RenderItem renders a menu item to string.
	RenderItem(item *Item, isSelected bool) string

	// RenderBreadcrumb renders breadcrumb to string.
	RenderBreadcrumb(breadcrumb []string) string

	// RenderStatus renders status information.
	RenderStatus(status string) string

	// SetWidth sets the rendering width.
	SetWidth(width int)

	// SetHeight sets the rendering height.
	SetHeight(height int)

	// GetWidth returns the current width.
	GetWidth() int

	// GetHeight returns the current height.
	GetHeight() int
}

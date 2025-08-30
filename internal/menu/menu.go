package menu

import (
	"context"
	"fmt"
	"strings"
	"sync"
)

// BasicManager implements the Manager interface.
type BasicManager struct {
	rootMenu    *Menu
	currentMenu *Menu
	mutex       sync.RWMutex
}

// NewBasicManager creates a new basic menu manager.
func NewBasicManager() *BasicManager {
	return &BasicManager{}
}

// CreateMenu creates a new menu.
func (m *BasicManager) CreateMenu(id, title, description string) *Menu {
	return &Menu{
		ID:          id,
		Title:       title,
		Description: description,
		Items:       make([]*Item, 0),
		CurrentIndex: 0,
	}
}

// AddItem adds an item to a menu.
func (m *BasicManager) AddItem(menu *Menu, item *Item) error {
	if menu == nil {
		return fmt.Errorf("menu cannot be nil")
	}
	if item == nil {
		return fmt.Errorf("item cannot be nil")
	}

	// Set parent menu for submenu items.
	if item.Type == ItemTypeSubmenu && item.Submenu != nil {
		item.Submenu.Parent = menu
	}

	menu.Items = append(menu.Items, item)
	return nil
}

// RemoveItem removes an item from a menu.
func (m *BasicManager) RemoveItem(menu *Menu, itemID string) error {
	if menu == nil {
		return fmt.Errorf("menu cannot be nil")
	}

	for i, item := range menu.Items {
		if item.ID == itemID {
			// Remove item from slice.
			menu.Items = append(menu.Items[:i], menu.Items[i+1:]...)
			
			// Adjust current index if needed.
			if menu.CurrentIndex >= len(menu.Items) && len(menu.Items) > 0 {
				menu.CurrentIndex = len(menu.Items) - 1
			} else if len(menu.Items) == 0 {
				menu.CurrentIndex = 0
			}
			
			return nil
		}
	}

	return fmt.Errorf("item not found: %s", itemID)
}

// SetCurrentMenu sets the current active menu.
func (m *BasicManager) SetCurrentMenu(menu *Menu) error {
	m.mutex.Lock()
	defer m.mutex.Unlock()

	if menu == nil {
		return fmt.Errorf("menu cannot be nil")
	}

	m.currentMenu = menu
	return nil
}

// GetCurrentMenu returns the current active menu.
func (m *BasicManager) GetCurrentMenu() *Menu {
	m.mutex.RLock()
	defer m.mutex.RUnlock()

	return m.currentMenu
}

// Navigate performs navigation in the current menu.
func (m *BasicManager) Navigate(direction NavigationDirection) NavigationResult {
	m.mutex.Lock()
	defer m.mutex.Unlock()

	result := NavigationResult{
		Changed:     false,
		CurrentMenu: m.currentMenu,
	}

	if m.currentMenu == nil {
		result.Error = fmt.Errorf("no current menu")
		return result
	}

	visibleItems := m.getVisibleItemsInternal(m.currentMenu)
	if len(visibleItems) == 0 {
		result.Error = fmt.Errorf("no visible items in menu")
		return result
	}

	switch direction {
	case NavUp:
		oldIndex := m.currentMenu.CurrentIndex
		m.currentMenu.CurrentIndex--
		if m.currentMenu.CurrentIndex < 0 {
			m.currentMenu.CurrentIndex = len(visibleItems) - 1
		}
		result.Changed = (oldIndex != m.currentMenu.CurrentIndex)

	case NavDown:
		oldIndex := m.currentMenu.CurrentIndex
		m.currentMenu.CurrentIndex++
		if m.currentMenu.CurrentIndex >= len(visibleItems) {
			m.currentMenu.CurrentIndex = 0
		}
		result.Changed = (oldIndex != m.currentMenu.CurrentIndex)

	case NavSelect:
		if m.currentMenu.CurrentIndex < len(visibleItems) {
			item := visibleItems[m.currentMenu.CurrentIndex]
			if item.Type == ItemTypeSubmenu && item.Submenu != nil {
				m.currentMenu = item.Submenu
				result.Changed = true
				result.CurrentMenu = m.currentMenu
				result.Message = fmt.Sprintf("Entered submenu: %s", item.Title)
			} else if item.Type == ItemTypeBack {
				return m.goToParentInternal()
			}
		}

	case NavBack:
		return m.goToParentInternal()
	}

	// Set current item.
	if m.currentMenu.CurrentIndex < len(visibleItems) {
		result.CurrentItem = visibleItems[m.currentMenu.CurrentIndex]
	}

	return result
}

// ExecuteCurrentItem executes the current menu item.
func (m *BasicManager) ExecuteCurrentItem(ctx context.Context) error {
	m.mutex.RLock()
	defer m.mutex.RUnlock()

	if m.currentMenu == nil {
		return fmt.Errorf("no current menu")
	}

	visibleItems := m.getVisibleItemsInternal(m.currentMenu)
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

// GetCurrentItem returns the current menu item.
func (m *BasicManager) GetCurrentItem() *Item {
	m.mutex.RLock()
	defer m.mutex.RUnlock()

	if m.currentMenu == nil {
		return nil
	}

	visibleItems := m.getVisibleItemsInternal(m.currentMenu)
	if len(visibleItems) == 0 || m.currentMenu.CurrentIndex >= len(visibleItems) {
		return nil
	}

	return visibleItems[m.currentMenu.CurrentIndex]
}

// GoToParent navigates to parent menu.
func (m *BasicManager) GoToParent() NavigationResult {
	m.mutex.Lock()
	defer m.mutex.Unlock()

	return m.goToParentInternal()
}

// goToParentInternal navigates to parent menu (internal, no locking).
func (m *BasicManager) goToParentInternal() NavigationResult {
	result := NavigationResult{
		Changed:     false,
		CurrentMenu: m.currentMenu,
	}

	if m.currentMenu == nil {
		result.Error = fmt.Errorf("no current menu")
		return result
	}

	if m.currentMenu.Parent != nil {
		m.currentMenu = m.currentMenu.Parent
		result.Changed = true
		result.CurrentMenu = m.currentMenu
		result.Message = fmt.Sprintf("Returned to: %s", m.currentMenu.Title)
	} else if m.rootMenu != nil && m.currentMenu != m.rootMenu {
		m.currentMenu = m.rootMenu
		result.Changed = true
		result.CurrentMenu = m.currentMenu
		result.Message = "Returned to main menu"
	}

	// Set current item.
	visibleItems := m.getVisibleItemsInternal(m.currentMenu)
	if len(visibleItems) > 0 && m.currentMenu.CurrentIndex < len(visibleItems) {
		result.CurrentItem = visibleItems[m.currentMenu.CurrentIndex]
	}

	return result
}

// GoToRoot navigates to root menu.
func (m *BasicManager) GoToRoot() NavigationResult {
	m.mutex.Lock()
	defer m.mutex.Unlock()

	result := NavigationResult{
		Changed:     false,
		CurrentMenu: m.currentMenu,
	}

	if m.rootMenu == nil {
		result.Error = fmt.Errorf("no root menu")
		return result
	}

	if m.currentMenu != m.rootMenu {
		m.currentMenu = m.rootMenu
		result.Changed = true
		result.CurrentMenu = m.currentMenu
		result.Message = "Returned to main menu"
	}

	// Set current item.
	visibleItems := m.getVisibleItemsInternal(m.currentMenu)
	if len(visibleItems) > 0 && m.currentMenu.CurrentIndex < len(visibleItems) {
		result.CurrentItem = visibleItems[m.currentMenu.CurrentIndex]
	}

	return result
}

// GetBreadcrumb returns the current menu breadcrumb.
func (m *BasicManager) GetBreadcrumb() []string {
	m.mutex.RLock()
	defer m.mutex.RUnlock()

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

// SetRootMenu sets the root menu.
func (m *BasicManager) SetRootMenu(menu *Menu) {
	m.mutex.Lock()
	defer m.mutex.Unlock()

	m.rootMenu = menu
	if m.currentMenu == nil {
		m.currentMenu = menu
	}
}

// GetRootMenu returns the root menu.
func (m *BasicManager) GetRootMenu() *Menu {
	m.mutex.RLock()
	defer m.mutex.RUnlock()

	return m.rootMenu
}

// FindMenu finds a menu by ID.
func (m *BasicManager) FindMenu(id string) *Menu {
	m.mutex.RLock()
	defer m.mutex.RUnlock()

	if m.rootMenu == nil {
		return nil
	}

	return m.findMenuRecursive(m.rootMenu, id)
}

// findMenuRecursive recursively finds a menu by ID.
func (m *BasicManager) findMenuRecursive(menu *Menu, id string) *Menu {
	if menu.ID == id {
		return menu
	}

	for _, item := range menu.Items {
		if item.Type == ItemTypeSubmenu && item.Submenu != nil {
			if found := m.findMenuRecursive(item.Submenu, id); found != nil {
				return found
			}
		}
	}

	return nil
}

// FindItem finds an item by ID in current menu hierarchy.
func (m *BasicManager) FindItem(id string) *Item {
	m.mutex.RLock()
	defer m.mutex.RUnlock()

	if m.rootMenu == nil {
		return nil
	}

	return m.findItemRecursive(m.rootMenu, id)
}

// findItemRecursive recursively finds an item by ID.
func (m *BasicManager) findItemRecursive(menu *Menu, id string) *Item {
	for _, item := range menu.Items {
		if item.ID == id {
			return item
		}

		if item.Type == ItemTypeSubmenu && item.Submenu != nil {
			if found := m.findItemRecursive(item.Submenu, id); found != nil {
				return found
			}
		}
	}

	return nil
}

// GetVisibleItems returns visible items from current menu.
func (m *BasicManager) GetVisibleItems() []*Item {
	m.mutex.RLock()
	defer m.mutex.RUnlock()

	if m.currentMenu == nil {
		return []*Item{}
	}

	return m.getVisibleItemsInternal(m.currentMenu)
}

// getVisibleItemsInternal returns visible items (internal, no locking).
func (m *BasicManager) getVisibleItemsInternal(menu *Menu) []*Item {
	var visibleItems []*Item
	for _, item := range menu.Items {
		if item.Visible {
			visibleItems = append(visibleItems, item)
		}
	}
	return visibleItems
}

// GetEnabledItems returns enabled items from current menu.
func (m *BasicManager) GetEnabledItems() []*Item {
	m.mutex.RLock()
	defer m.mutex.RUnlock()

	if m.currentMenu == nil {
		return []*Item{}
	}

	var enabledItems []*Item
	for _, item := range m.currentMenu.Items {
		if item.Visible && item.Enabled {
			enabledItems = append(enabledItems, item)
		}
	}

	return enabledItems
}

// RefreshMenu refreshes the current menu state.
func (m *BasicManager) RefreshMenu() {
	m.mutex.Lock()
	defer m.mutex.Unlock()

	if m.currentMenu == nil {
		return
	}

	// Ensure current index is valid.
	visibleItems := m.getVisibleItemsInternal(m.currentMenu)
	if m.currentMenu.CurrentIndex >= len(visibleItems) {
		if len(visibleItems) > 0 {
			m.currentMenu.CurrentIndex = len(visibleItems) - 1
		} else {
			m.currentMenu.CurrentIndex = 0
		}
	}
}

// GetMenuPath returns the path to current menu.
func (m *BasicManager) GetMenuPath() string {
	breadcrumb := m.GetBreadcrumb()
	return strings.Join(breadcrumb, " > ")
}

// Utility functions for creating menu items.

// NewActionItem creates a new action item.
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

// NewSubmenuItem creates a new submenu item.
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

// NewBackItem creates a new back item.
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

// NewSeparatorItem creates a new separator item.
func NewSeparatorItem(id string) *Item {
	return &Item{
		ID:          id,
		Title:       "---",
		Description: "",
		Type:        ItemTypeSeparator,
		Enabled:     false,
		Visible:     true,
	}
}

// ItemTypeToString converts item type to string.
func ItemTypeToString(itemType ItemType) string {
	switch itemType {
	case ItemTypeAction:
		return "ACTION"
	case ItemTypeSubmenu:
		return "SUBMENU"
	case ItemTypeBack:
		return "BACK"
	case ItemTypeSeparator:
		return "SEPARATOR"
	default:
		return "UNKNOWN"
	}
}

// NavigationDirectionToString converts navigation direction to string.
func NavigationDirectionToString(direction NavigationDirection) string {
	switch direction {
	case NavUp:
		return "UP"
	case NavDown:
		return "DOWN"
	case NavSelect:
		return "SELECT"
	case NavBack:
		return "BACK"
	default:
		return "UNKNOWN"
	}
}

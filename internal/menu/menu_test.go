package menu

import (
	"context"
	"testing"
)

func TestBasicManager_CreateMenu(t *testing.T) {
	manager := NewBasicManager()
	
	menu := manager.CreateMenu("test", "Test Menu", "Test Description")
	
	if menu == nil {
		t.Fatal("CreateMenu returned nil")
	}
	
	if menu.ID != "test" {
		t.Errorf("Expected ID 'test', got '%s'", menu.ID)
	}
	
	if menu.Title != "Test Menu" {
		t.Errorf("Expected Title 'Test Menu', got '%s'", menu.Title)
	}
	
	if menu.Description != "Test Description" {
		t.Errorf("Expected Description 'Test Description', got '%s'", menu.Description)
	}
	
	if len(menu.Items) != 0 {
		t.Errorf("Expected 0 items, got %d", len(menu.Items))
	}
	
	if menu.CurrentIndex != 0 {
		t.Errorf("Expected CurrentIndex 0, got %d", menu.CurrentIndex)
	}
}

func TestBasicManager_AddItem(t *testing.T) {
	manager := NewBasicManager()
	menu := manager.CreateMenu("test", "Test Menu", "Test Description")
	
	item := NewActionItem("item1", "Test Item", "Test Description", nil)
	
	err := manager.AddItem(menu, item)
	if err != nil {
		t.Fatalf("AddItem failed: %v", err)
	}
	
	if len(menu.Items) != 1 {
		t.Errorf("Expected 1 item, got %d", len(menu.Items))
	}
	
	if menu.Items[0] != item {
		t.Error("Item was not added correctly")
	}
}

func TestBasicManager_RemoveItem(t *testing.T) {
	manager := NewBasicManager()
	menu := manager.CreateMenu("test", "Test Menu", "Test Description")
	
	item1 := NewActionItem("item1", "Test Item 1", "Test Description 1", nil)
	item2 := NewActionItem("item2", "Test Item 2", "Test Description 2", nil)
	
	manager.AddItem(menu, item1)
	manager.AddItem(menu, item2)
	
	err := manager.RemoveItem(menu, "item1")
	if err != nil {
		t.Fatalf("RemoveItem failed: %v", err)
	}
	
	if len(menu.Items) != 1 {
		t.Errorf("Expected 1 item, got %d", len(menu.Items))
	}
	
	if menu.Items[0].ID != "item2" {
		t.Errorf("Wrong item remaining, expected 'item2', got '%s'", menu.Items[0].ID)
	}
}

func TestBasicManager_Navigation(t *testing.T) {
	manager := NewBasicManager()
	menu := manager.CreateMenu("test", "Test Menu", "Test Description")
	
	// Add test items.
	item1 := NewActionItem("item1", "Test Item 1", "Test Description 1", nil)
	item2 := NewActionItem("item2", "Test Item 2", "Test Description 2", nil)
	item3 := NewActionItem("item3", "Test Item 3", "Test Description 3", nil)
	
	manager.AddItem(menu, item1)
	manager.AddItem(menu, item2)
	manager.AddItem(menu, item3)
	
	manager.SetCurrentMenu(menu)
	
	// Test navigation down.
	result := manager.Navigate(NavDown)
	if !result.Changed {
		t.Error("Navigation down should have changed")
	}
	if menu.CurrentIndex != 1 {
		t.Errorf("Expected CurrentIndex 1, got %d", menu.CurrentIndex)
	}
	
	// Test navigation up.
	result = manager.Navigate(NavUp)
	if !result.Changed {
		t.Error("Navigation up should have changed")
	}
	if menu.CurrentIndex != 0 {
		t.Errorf("Expected CurrentIndex 0, got %d", menu.CurrentIndex)
	}
	
	// Test wrap-around navigation up.
	result = manager.Navigate(NavUp)
	if !result.Changed {
		t.Error("Navigation up (wrap-around) should have changed")
	}
	if menu.CurrentIndex != 2 {
		t.Errorf("Expected CurrentIndex 2 (wrap-around), got %d", menu.CurrentIndex)
	}
	
	// Test wrap-around navigation down.
	result = manager.Navigate(NavDown)
	if !result.Changed {
		t.Error("Navigation down (wrap-around) should have changed")
	}
	if menu.CurrentIndex != 0 {
		t.Errorf("Expected CurrentIndex 0 (wrap-around), got %d", menu.CurrentIndex)
	}
}

func TestBasicManager_ExecuteCurrentItem(t *testing.T) {
	manager := NewBasicManager()
	menu := manager.CreateMenu("test", "Test Menu", "Test Description")
	
	executed := false
	item := NewActionItem("item1", "Test Item", "Test Description", func(ctx context.Context) error {
		executed = true
		return nil
	})
	
	manager.AddItem(menu, item)
	manager.SetCurrentMenu(menu)
	
	ctx := context.Background()
	err := manager.ExecuteCurrentItem(ctx)
	if err != nil {
		t.Fatalf("ExecuteCurrentItem failed: %v", err)
	}
	
	if !executed {
		t.Error("Item action was not executed")
	}
}

func TestBasicManager_Breadcrumb(t *testing.T) {
	manager := NewBasicManager()
	
	// Create menu hierarchy.
	rootMenu := manager.CreateMenu("root", "Root Menu", "Root Description")
	subMenu := manager.CreateMenu("sub", "Sub Menu", "Sub Description")
	subSubMenu := manager.CreateMenu("subsub", "SubSub Menu", "SubSub Description")
	
	// Set up hierarchy.
	subMenu.Parent = rootMenu
	subSubMenu.Parent = subMenu
	
	manager.SetRootMenu(rootMenu)
	manager.SetCurrentMenu(subSubMenu)
	
	breadcrumb := manager.GetBreadcrumb()
	
	expectedBreadcrumb := []string{"Root Menu", "Sub Menu", "SubSub Menu"}
	if len(breadcrumb) != len(expectedBreadcrumb) {
		t.Errorf("Expected breadcrumb length %d, got %d", len(expectedBreadcrumb), len(breadcrumb))
	}
	
	for i, expected := range expectedBreadcrumb {
		if breadcrumb[i] != expected {
			t.Errorf("Expected breadcrumb[%d] = '%s', got '%s'", i, expected, breadcrumb[i])
		}
	}
}

func TestBasicManager_FindMenu(t *testing.T) {
	manager := NewBasicManager()
	
	rootMenu := manager.CreateMenu("root", "Root Menu", "Root Description")
	subMenu := manager.CreateMenu("sub", "Sub Menu", "Sub Description")
	
	subMenuItem := NewSubmenuItem("sub_item", "Sub Menu Item", "Sub Menu Description", subMenu)
	manager.AddItem(rootMenu, subMenuItem)
	
	manager.SetRootMenu(rootMenu)
	
	// Test finding root menu.
	found := manager.FindMenu("root")
	if found != rootMenu {
		t.Error("Failed to find root menu")
	}
	
	// Test finding sub menu.
	found = manager.FindMenu("sub")
	if found != subMenu {
		t.Error("Failed to find sub menu")
	}
	
	// Test finding non-existent menu.
	found = manager.FindMenu("nonexistent")
	if found != nil {
		t.Error("Found non-existent menu")
	}
}

func TestNewActionItem(t *testing.T) {
	executed := false
	action := func(ctx context.Context) error {
		executed = true
		return nil
	}
	
	item := NewActionItem("test", "Test Item", "Test Description", action)
	
	if item.ID != "test" {
		t.Errorf("Expected ID 'test', got '%s'", item.ID)
	}
	
	if item.Type != ItemTypeAction {
		t.Errorf("Expected Type %v, got %v", ItemTypeAction, item.Type)
	}
	
	if !item.Enabled {
		t.Error("Expected item to be enabled")
	}
	
	if !item.Visible {
		t.Error("Expected item to be visible")
	}
	
	// Test action execution.
	ctx := context.Background()
	err := item.Action(ctx)
	if err != nil {
		t.Fatalf("Action execution failed: %v", err)
	}
	
	if !executed {
		t.Error("Action was not executed")
	}
}

func TestNewSubmenuItem(t *testing.T) {
	submenu := &Menu{ID: "submenu", Title: "Submenu"}
	item := NewSubmenuItem("test", "Test Submenu", "Test Description", submenu)
	
	if item.Type != ItemTypeSubmenu {
		t.Errorf("Expected Type %v, got %v", ItemTypeSubmenu, item.Type)
	}
	
	if item.Submenu != submenu {
		t.Error("Submenu was not set correctly")
	}
}

func TestNewBackItem(t *testing.T) {
	item := NewBackItem()
	
	if item.ID != "back" {
		t.Errorf("Expected ID 'back', got '%s'", item.ID)
	}
	
	if item.Type != ItemTypeBack {
		t.Errorf("Expected Type %v, got %v", ItemTypeBack, item.Type)
	}
}

func TestNewSeparatorItem(t *testing.T) {
	item := NewSeparatorItem("sep1")
	
	if item.ID != "sep1" {
		t.Errorf("Expected ID 'sep1', got '%s'", item.ID)
	}
	
	if item.Type != ItemTypeSeparator {
		t.Errorf("Expected Type %v, got %v", ItemTypeSeparator, item.Type)
	}
	
	if item.Enabled {
		t.Error("Expected separator to be disabled")
	}
}

package menu

import (
	"fmt"
	"strings"
	"unicode/utf8"
)

// ConsoleRenderer implements the Renderer interface for console output.
type ConsoleRenderer struct {
	width  int
	height int
}

// NewConsoleRenderer creates a new console renderer.
func NewConsoleRenderer(width, height int) *ConsoleRenderer {
	return &ConsoleRenderer{
		width:  width,
		height: height,
	}
}

// RenderMenu renders a menu to string.
func (r *ConsoleRenderer) RenderMenu(menu *Menu) string {
	if menu == nil {
		return ""
	}

	var output strings.Builder

	// Render menu title.
	titleLine := r.centerText(menu.Title, r.width)
	output.WriteString(titleLine + "\n")
	output.WriteString(strings.Repeat("=", r.width) + "\n")

	// Render menu description if present.
	if menu.Description != "" {
		descLine := r.wrapText(menu.Description, r.width-4)
		for _, line := range strings.Split(descLine, "\n") {
			output.WriteString("  " + line + "\n")
		}
		output.WriteString("\n")
	}

	// Get visible items.
	visibleItems := make([]*Item, 0)
	for _, item := range menu.Items {
		if item.Visible {
			visibleItems = append(visibleItems, item)
		}
	}

	// Render menu items.
	for i, item := range visibleItems {
		isSelected := (i == menu.CurrentIndex)
		itemLine := r.RenderItem(item, isSelected)
		output.WriteString(itemLine + "\n")
	}

	return output.String()
}

// RenderItem renders a menu item to string.
func (r *ConsoleRenderer) RenderItem(item *Item, isSelected bool) string {
	if item == nil {
		return ""
	}

	var prefix string
	var suffix string

	// Add selection indicator.
	if isSelected {
		prefix = "► "
	} else {
		prefix = "  "
	}

	// Add type indicator.
	switch item.Type {
	case ItemTypeSubmenu:
		suffix = " →"
	case ItemTypeBack:
		// No additional suffix for back items.
	case ItemTypeSeparator:
		return r.centerText(item.Title, r.width)
	case ItemTypeAction:
		if !item.Enabled {
			suffix = " (недоступно)"
		}
	}

	// Build item text.
	itemText := item.Title + suffix

	// Add selection highlighting.
	if isSelected {
		itemText = "[" + itemText + "]"
	}

	// Apply enabled/disabled styling.
	if !item.Enabled {
		itemText = "(" + itemText + ")"
	}

	// Ensure line fits within width.
	maxTextWidth := r.width - utf8.RuneCountInString(prefix)
	if utf8.RuneCountInString(itemText) > maxTextWidth {
		itemText = r.truncateText(itemText, maxTextWidth-3) + "..."
	}

	return prefix + itemText
}

// RenderBreadcrumb renders breadcrumb to string.
func (r *ConsoleRenderer) RenderBreadcrumb(breadcrumb []string) string {
	if len(breadcrumb) == 0 {
		return ""
	}

	breadcrumbText := strings.Join(breadcrumb, " > ")
	
	// Truncate if too long.
	if utf8.RuneCountInString(breadcrumbText) > r.width {
		breadcrumbText = r.truncateText(breadcrumbText, r.width-3) + "..."
	}

	return breadcrumbText
}

// RenderStatus renders status information.
func (r *ConsoleRenderer) RenderStatus(status string) string {
	if status == "" {
		return ""
	}

	// Wrap status text.
	wrappedStatus := r.wrapText(status, r.width-4)
	var output strings.Builder

	output.WriteString(strings.Repeat("-", r.width) + "\n")
	for _, line := range strings.Split(wrappedStatus, "\n") {
		output.WriteString("  " + line + "\n")
	}

	return output.String()
}

// SetWidth sets the rendering width.
func (r *ConsoleRenderer) SetWidth(width int) {
	r.width = width
}

// SetHeight sets the rendering height.
func (r *ConsoleRenderer) SetHeight(height int) {
	r.height = height
}

// GetWidth returns the current width.
func (r *ConsoleRenderer) GetWidth() int {
	return r.width
}

// GetHeight returns the current height.
func (r *ConsoleRenderer) GetHeight() int {
	return r.height
}

// Helper functions.

// centerText centers text within the given width.
func (r *ConsoleRenderer) centerText(text string, width int) string {
	textLen := utf8.RuneCountInString(text)
	if textLen >= width {
		return r.truncateText(text, width)
	}

	padding := (width - textLen) / 2
	leftPadding := strings.Repeat(" ", padding)
	rightPadding := strings.Repeat(" ", width-textLen-padding)

	return leftPadding + text + rightPadding
}

// wrapText wraps text to fit within the given width.
func (r *ConsoleRenderer) wrapText(text string, width int) string {
	if width <= 0 {
		return text
	}

	words := strings.Fields(text)
	if len(words) == 0 {
		return ""
	}

	var lines []string
	var currentLine strings.Builder

	for _, word := range words {
		wordLen := utf8.RuneCountInString(word)
		currentLen := utf8.RuneCountInString(currentLine.String())

		// Check if adding this word would exceed the width.
		if currentLen > 0 && currentLen+1+wordLen > width {
			// Start a new line.
			lines = append(lines, currentLine.String())
			currentLine.Reset()
		}

		// Add word to current line.
		if currentLine.Len() > 0 {
			currentLine.WriteString(" ")
		}
		currentLine.WriteString(word)
	}

	// Add the last line if not empty.
	if currentLine.Len() > 0 {
		lines = append(lines, currentLine.String())
	}

	return strings.Join(lines, "\n")
}

// truncateText truncates text to fit within the given width.
func (r *ConsoleRenderer) truncateText(text string, width int) string {
	if width <= 0 {
		return ""
	}

	runes := []rune(text)
	if len(runes) <= width {
		return text
	}

	return string(runes[:width])
}

// VisualRenderer implements enhanced visual rendering with borders and colors.
type VisualRenderer struct {
	*ConsoleRenderer
	showBorders bool
	showColors  bool
}

// NewVisualRenderer creates a new visual renderer.
func NewVisualRenderer(width, height int, showBorders, showColors bool) *VisualRenderer {
	return &VisualRenderer{
		ConsoleRenderer: NewConsoleRenderer(width, height),
		showBorders:     showBorders,
		showColors:      showColors,
	}
}

// RenderMenu renders a menu with enhanced visuals.
func (r *VisualRenderer) RenderMenu(menu *Menu) string {
	if menu == nil {
		return ""
	}

	var output strings.Builder

	if r.showBorders {
		// Top border.
		output.WriteString("┌" + strings.Repeat("─", r.width-2) + "┐\n")
	}

	// Render menu title.
	titleLine := r.centerText(menu.Title, r.width-4)
	if r.showBorders {
		output.WriteString("│ " + titleLine + " │\n")
		output.WriteString("├" + strings.Repeat("─", r.width-2) + "┤\n")
	} else {
		output.WriteString(titleLine + "\n")
		output.WriteString(strings.Repeat("=", r.width) + "\n")
	}

	// Render menu description if present.
	if menu.Description != "" {
		descLines := strings.Split(r.wrapText(menu.Description, r.width-6), "\n")
		for _, line := range descLines {
			if r.showBorders {
				paddedLine := line + strings.Repeat(" ", r.width-6-utf8.RuneCountInString(line))
				output.WriteString("│  " + paddedLine + "  │\n")
			} else {
				output.WriteString("  " + line + "\n")
			}
		}
		if r.showBorders {
			output.WriteString("├" + strings.Repeat("─", r.width-2) + "┤\n")
		} else {
			output.WriteString("\n")
		}
	}

	// Get visible items.
	visibleItems := make([]*Item, 0)
	for _, item := range menu.Items {
		if item.Visible {
			visibleItems = append(visibleItems, item)
		}
	}

	// Render menu items.
	for i, item := range visibleItems {
		isSelected := (i == menu.CurrentIndex)
		itemLine := r.renderVisualItem(item, isSelected)
		if r.showBorders {
			output.WriteString("│ " + itemLine + " │\n")
		} else {
			output.WriteString(itemLine + "\n")
		}
	}

	if r.showBorders {
		// Bottom border.
		output.WriteString("└" + strings.Repeat("─", r.width-2) + "┘\n")
	}

	return output.String()
}

// renderVisualItem renders an item with visual enhancements.
func (r *VisualRenderer) renderVisualItem(item *Item, isSelected bool) string {
	if item == nil {
		return ""
	}

	var prefix string
	var suffix string

	// Add selection indicator.
	if isSelected {
		if r.showColors {
			prefix = "▶ "
		} else {
			prefix = "► "
		}
	} else {
		prefix = "  "
	}

	// Add type indicator.
	switch item.Type {
	case ItemTypeSubmenu:
		suffix = " →"
	case ItemTypeBack:
		prefix = "◄ "
	case ItemTypeSeparator:
		borderChar := "─"
		if r.showBorders {
			borderChar = "─"
		}
		return r.centerText(strings.Repeat(borderChar, utf8.RuneCountInString(item.Title)), r.width-4)
	case ItemTypeAction:
		if !item.Enabled {
			suffix = " (недоступно)"
		}
	}

	// Build item text.
	itemText := item.Title + suffix

	// Add selection highlighting.
	if isSelected && r.showColors {
		itemText = fmt.Sprintf("\033[1;32m%s\033[0m", itemText) // Green bold.
	} else if isSelected {
		itemText = "[" + itemText + "]"
	}

	// Apply enabled/disabled styling.
	if !item.Enabled {
		if r.showColors {
			itemText = fmt.Sprintf("\033[2;37m%s\033[0m", itemText) // Dim gray.
		} else {
			itemText = "(" + itemText + ")"
		}
	}

	// Calculate available width.
	availableWidth := r.width - 4 - utf8.RuneCountInString(prefix)
	if r.showBorders {
		availableWidth -= 2
	}

	// Ensure line fits within width.
	displayText := itemText
	if !r.showColors { // Don't count ANSI codes in length.
		if utf8.RuneCountInString(itemText) > availableWidth {
			displayText = r.truncateText(itemText, availableWidth-3) + "..."
		}
	}

	// Pad to full width if borders are shown.
	if r.showBorders {
		padding := availableWidth - utf8.RuneCountInString(displayText)
		if padding > 0 {
			displayText += strings.Repeat(" ", padding)
		}
	}

	return prefix + displayText
}

// RenderBreadcrumb renders breadcrumb with visual enhancements.
func (r *VisualRenderer) RenderBreadcrumb(breadcrumb []string) string {
	if len(breadcrumb) == 0 {
		return ""
	}

	separator := " ► "
	if r.showColors {
		separator = fmt.Sprintf(" \033[1;34m►\033[0m ") // Blue arrow.
	}

	breadcrumbText := strings.Join(breadcrumb, separator)
	
	// Truncate if too long.
	availableWidth := r.width
	if r.showBorders {
		availableWidth -= 4
	}

	if utf8.RuneCountInString(breadcrumbText) > availableWidth {
		breadcrumbText = r.truncateText(breadcrumbText, availableWidth-3) + "..."
	}

	if r.showBorders {
		padding := availableWidth - utf8.RuneCountInString(breadcrumbText)
		if padding > 0 {
			breadcrumbText += strings.Repeat(" ", padding)
		}
		return "│ " + breadcrumbText + " │"
	}

	return breadcrumbText
}

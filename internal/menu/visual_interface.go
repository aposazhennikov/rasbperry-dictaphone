package menu

import (
	"context"
	"fmt"
	"os"
	"os/exec"
	"strings"
	"sync"
	"time"

	"raspberry-dictaphone-go/internal/audio"
	"raspberry-dictaphone-go/internal/input"
	"raspberry-dictaphone-go/internal/logger"
	"raspberry-dictaphone-go/internal/tts"
	"raspberry-dictaphone-go/internal/usb"
)

// VisualInterface represents the text-based visual interface.
type VisualInterface struct {
	manager      Manager
	builder      Builder
	renderer     Renderer
	inputHandler *input.Handler
	audioManager audio.Manager
	ttsManager   tts.Manager
	usbManager   usb.Manager
	logger       *logger.Logger

	// Display settings.
	width        int
	height       int
	refreshRate  time.Duration
	showBorders  bool
	showColors   bool

	// State.
	isRunning    bool
	ctx          context.Context
	cancel       context.CancelFunc
	mutex        sync.RWMutex
	lastUpdate   time.Time
	statusLine   string
	errorMessage string
	
	// Display buffer.
	displayBuffer strings.Builder
}

// NewVisualInterface creates a new visual interface.
func NewVisualInterface(
	mgr Manager,
	builder Builder,
	inputHandler *input.Handler,
	audioMgr audio.Manager,
	ttsMgr tts.Manager,
	usbMgr usb.Manager,
	log *logger.Logger,
	width, height int,
	refreshRate time.Duration,
) *VisualInterface {
	return &VisualInterface{
		manager:      mgr,
		builder:      builder,
		inputHandler: inputHandler,
		audioManager: audioMgr,
		ttsManager:   ttsMgr,
		usbManager:   usbMgr,
		logger:       log,
		width:        width,
		height:       height,
		refreshRate:  refreshRate,
		showBorders:  true,
		showColors:   true,
		lastUpdate:   time.Now(),
	}
}

// Start starts the visual interface.
func (vi *VisualInterface) Start(ctx context.Context) error {
	vi.mutex.Lock()
	defer vi.mutex.Unlock()

	if vi.isRunning {
		return fmt.Errorf("visual interface already running")
	}

	// Set up context.
	vi.ctx, vi.cancel = context.WithCancel(ctx)

	// Initialize renderer.
	vi.renderer = NewVisualRenderer(vi.width, vi.height, vi.showBorders, vi.showColors)

	// Clear screen and hide cursor.
	vi.clearScreen()
	vi.hideCursor()

	// Start update loop.
	go vi.updateLoop()

	// Start input processing.
	go vi.processInput()

	vi.isRunning = true
	vi.logger.Info("Visual interface started (%dx%d)", vi.width, vi.height)

	return nil
}

// Stop stops the visual interface.
func (vi *VisualInterface) Stop() error {
	vi.mutex.Lock()
	defer vi.mutex.Unlock()

	if !vi.isRunning {
		return nil
	}

	// Cancel context.
	if vi.cancel != nil {
		vi.cancel()
	}

	// Show cursor and clear screen.
	vi.showCursor()
	vi.clearScreen()

	vi.isRunning = false
	vi.logger.Info("Visual interface stopped")

	return nil
}

// IsRunning returns true if the interface is running.
func (vi *VisualInterface) IsRunning() bool {
	vi.mutex.RLock()
	defer vi.mutex.RUnlock()
	return vi.isRunning
}

// SetStatus sets the status line message.
func (vi *VisualInterface) SetStatus(message string) {
	vi.mutex.Lock()
	defer vi.mutex.Unlock()
	vi.statusLine = message
}

// SetError sets an error message.
func (vi *VisualInterface) SetError(message string) {
	vi.mutex.Lock()
	defer vi.mutex.Unlock()
	vi.errorMessage = message
	vi.logger.Error("UI Error: %s", message)
}

// ClearError clears the error message.
func (vi *VisualInterface) ClearError() {
	vi.mutex.Lock()
	defer vi.mutex.Unlock()
	vi.errorMessage = ""
}

// updateLoop runs the display update loop.
func (vi *VisualInterface) updateLoop() {
	ticker := time.NewTicker(vi.refreshRate)
	defer ticker.Stop()

	for {
		select {
		case <-vi.ctx.Done():
			return
		case <-ticker.C:
			vi.updateDisplay()
		}
	}
}

// updateDisplay updates the visual display.
func (vi *VisualInterface) updateDisplay() {
	vi.mutex.Lock()
	defer vi.mutex.Unlock()

	// Clear display buffer.
	vi.displayBuffer.Reset()

	// Build display content.
	vi.buildHeader()
	vi.buildMenuContent()
	vi.buildStatusBar()
	vi.buildFooter()

	// Update screen.
	vi.clearScreen()
	vi.moveCursor(1, 1)
	fmt.Print(vi.displayBuffer.String())

	vi.lastUpdate = time.Now()
}

// buildHeader builds the header section.
func (vi *VisualInterface) buildHeader() {
	title := "🎙️ Raspberry Pi Диктофон v2.0"
	timestamp := time.Now().Format("15:04:05 02.01.2006")

	if vi.showBorders {
		vi.displayBuffer.WriteString("┌" + strings.Repeat("─", vi.width-2) + "┐\n")
		
		// Title line.
		titlePadding := vi.width - 4 - len(title)
		vi.displayBuffer.WriteString("│ " + title + strings.Repeat(" ", titlePadding) + " │\n")
		
		// Timestamp line.
		timestampPadding := vi.width - 4 - len(timestamp)
		vi.displayBuffer.WriteString("│ " + timestamp + strings.Repeat(" ", timestampPadding) + " │\n")
		
		vi.displayBuffer.WriteString("├" + strings.Repeat("─", vi.width-2) + "┤\n")
	} else {
		vi.displayBuffer.WriteString(title + strings.Repeat(" ", vi.width-len(title)-len(timestamp)) + timestamp + "\n")
		vi.displayBuffer.WriteString(strings.Repeat("=", vi.width) + "\n")
	}
}

// buildMenuContent builds the main menu content.
func (vi *VisualInterface) buildMenuContent() {
	currentMenu := vi.manager.GetCurrentMenu()
	if currentMenu == nil {
		vi.displayBuffer.WriteString("Меню не загружено\n")
		return
	}

	// Render breadcrumb.
	breadcrumb := vi.manager.GetBreadcrumb()
	if len(breadcrumb) > 0 {
		breadcrumbText := vi.renderer.RenderBreadcrumb(breadcrumb)
		if vi.showBorders {
			vi.displayBuffer.WriteString("│ " + breadcrumbText + " │\n")
			vi.displayBuffer.WriteString("├" + strings.Repeat("─", vi.width-2) + "┤\n")
		} else {
			vi.displayBuffer.WriteString(breadcrumbText + "\n")
			vi.displayBuffer.WriteString(strings.Repeat("-", vi.width) + "\n")
		}
	}

	// Render menu.
	menuContent := vi.renderer.RenderMenu(currentMenu)
	vi.displayBuffer.WriteString(menuContent)
}

// buildStatusBar builds the status bar with system information.
func (vi *VisualInterface) buildStatusBar() {
	var statusItems []string

	// Recording status.
	if vi.audioManager != nil {
		recorder := vi.audioManager.GetRecorder()
		if recorder != nil {
			info := recorder.GetRecordingInfo()
			switch info.State {
			case audio.StateRecording:
				statusItems = append(statusItems, fmt.Sprintf("🔴 REC %s", formatShortDuration(info.Duration)))
			case audio.StatePaused:
				statusItems = append(statusItems, fmt.Sprintf("⏸️ PAUSE %s", formatShortDuration(info.Duration)))
			}
		}
	}

	// Playback status.
	if vi.audioManager != nil {
		player := vi.audioManager.GetPlayer()
		if player != nil {
			info := player.GetPlaybackInfo()
			switch info.State {
			case audio.PlaybackPlaying:
				statusItems = append(statusItems, fmt.Sprintf("▶️ PLAY %s", info.Filename))
			case audio.PlaybackPaused:
				statusItems = append(statusItems, fmt.Sprintf("⏸️ %s", info.Filename))
			}
		}
	}

	// USB devices count.
	if vi.usbManager != nil {
		devices := vi.usbManager.GetMonitor().GetDevices()
		mountedCount := 0
		for _, device := range devices {
			if device.State == usb.DeviceMounted {
				mountedCount++
			}
		}
		if mountedCount > 0 {
			statusItems = append(statusItems, fmt.Sprintf("💾 %d USB", mountedCount))
		}
	}

	// System volume.
	if vi.audioManager != nil {
		if volume, err := vi.audioManager.GetSystemVolume(); err == nil {
			statusItems = append(statusItems, fmt.Sprintf("🔊 %d%%", volume))
		}
	}

	// Build status line.
	statusText := strings.Join(statusItems, " | ")
	if vi.statusLine != "" {
		if statusText != "" {
			statusText = vi.statusLine + " | " + statusText
		} else {
			statusText = vi.statusLine
		}
	}

	if statusText != "" {
		if vi.showBorders {
			vi.displayBuffer.WriteString("├" + strings.Repeat("─", vi.width-2) + "┤\n")
			statusPadding := vi.width - 4 - len(statusText)
			if statusPadding < 0 {
				statusText = statusText[:vi.width-7] + "..."
				statusPadding = 0
			}
			vi.displayBuffer.WriteString("│ " + statusText + strings.Repeat(" ", statusPadding) + " │\n")
		} else {
			vi.displayBuffer.WriteString(strings.Repeat("-", vi.width) + "\n")
			vi.displayBuffer.WriteString(statusText + "\n")
		}
	}
}

// buildFooter builds the footer with help and error messages.
func (vi *VisualInterface) buildFooter() {
	var footerLines []string

	// Error message.
	if vi.errorMessage != "" {
		footerLines = append(footerLines, "❌ ОШИБКА: "+vi.errorMessage)
	}

	// Help text.
	helpText := "↑↓ Навигация | ⏎ Выбор | ← Назад | ⏸ Пауза/Возобновление | ⏹ Стоп"
	footerLines = append(footerLines, helpText)

	// Render footer.
	if len(footerLines) > 0 {
		if vi.showBorders {
			vi.displayBuffer.WriteString("├" + strings.Repeat("─", vi.width-2) + "┤\n")
			for _, line := range footerLines {
				linePadding := vi.width - 4 - len(line)
				if linePadding < 0 {
					line = line[:vi.width-7] + "..."
					linePadding = 0
				}
				vi.displayBuffer.WriteString("│ " + line + strings.Repeat(" ", linePadding) + " │\n")
			}
			vi.displayBuffer.WriteString("└" + strings.Repeat("─", vi.width-2) + "┘\n")
		} else {
			vi.displayBuffer.WriteString(strings.Repeat("=", vi.width) + "\n")
			for _, line := range footerLines {
				vi.displayBuffer.WriteString(line + "\n")
			}
		}
	}
}

// processInput processes input commands.
func (vi *VisualInterface) processInput() {
	if vi.inputHandler == nil {
		return
	}

	commandChan := vi.inputHandler.GetCommandChannel()
	
	for {
		select {
		case <-vi.ctx.Done():
			return
		case cmd := <-commandChan:
			vi.handleCommand(cmd)
		}
	}
}

// handleCommand handles input commands.
func (vi *VisualInterface) handleCommand(cmd input.CommandEvent) {
	vi.logger.Debug("Handling command: %s", input.CommandToString(cmd.Command))

	// Clear any previous error.
	vi.ClearError()

	switch cmd.Command {
	case input.CmdUp:
		result := vi.manager.Navigate(NavUp)
		if result.Changed {
			vi.announceCurrentItem()
		}

	case input.CmdDown:
		result := vi.manager.Navigate(NavDown)
		if result.Changed {
			vi.announceCurrentItem()
		}

	case input.CmdSelect:
		// Execute current item or navigate to submenu.
		result := vi.manager.Navigate(NavSelect)
		if result.Changed {
			vi.announceCurrentItem()
		} else {
			// Execute action.
			if err := vi.manager.ExecuteCurrentItem(vi.ctx); err != nil {
				vi.SetError(err.Error())
			}
		}

	case input.CmdBack:
		result := vi.manager.Navigate(NavBack)
		if result.Changed {
			vi.announceCurrentItem()
		}

	case input.CmdLeft:
		vi.handleSeek(-10 * time.Second)

	case input.CmdRight:
		vi.handleSeek(10 * time.Second)

	case input.CmdVolumeUp:
		vi.handleVolumeChange(5)

	case input.CmdVolumeDown:
		vi.handleVolumeChange(-5)

	case input.CmdSpeedUp:
		vi.handleSpeedChange(0.1)

	case input.CmdSpeedDown:
		vi.handleSpeedChange(-0.1)

	case input.CmdDelete:
		vi.handleDelete()

	default:
		vi.logger.Debug("Unhandled command: %s", input.CommandToString(cmd.Command))
	}
}

// announceCurrentItem announces the current menu item via TTS.
func (vi *VisualInterface) announceCurrentItem() {
	if vi.ttsManager == nil {
		return
	}

	currentItem := vi.manager.GetCurrentItem()
	if currentItem != nil {
		go vi.ttsManager.PlaySpeech(vi.ctx, currentItem.Title)
	}
}

// handleSeek handles seeking in audio playback.
func (vi *VisualInterface) handleSeek(offset time.Duration) {
	if vi.audioManager == nil {
		return
	}

	player := vi.audioManager.GetPlayer()
	if player == nil {
		return
	}

	info := player.GetPlaybackInfo()
	if info.State == audio.PlaybackStopped {
		return
	}

	newPosition := info.Position + offset
	if newPosition < 0 {
		newPosition = 0
	}
	if newPosition > info.Duration {
		newPosition = info.Duration
	}

	if err := player.Seek(newPosition); err != nil {
		vi.SetError(fmt.Sprintf("Ошибка перемотки: %v", err))
	} else {
		vi.SetStatus(fmt.Sprintf("Позиция: %s", formatShortDuration(newPosition)))
	}
}

// handleVolumeChange handles volume changes.
func (vi *VisualInterface) handleVolumeChange(delta int) {
	if vi.audioManager == nil {
		return
	}

	currentVolume, err := vi.audioManager.GetSystemVolume()
	if err != nil {
		vi.SetError(fmt.Sprintf("Ошибка получения громкости: %v", err))
		return
	}

	newVolume := currentVolume + delta
	if newVolume < 0 {
		newVolume = 0
	}
	if newVolume > 100 {
		newVolume = 100
	}

	if err := vi.audioManager.SetSystemVolume(newVolume); err != nil {
		vi.SetError(fmt.Sprintf("Ошибка установки громкости: %v", err))
	} else {
		vi.SetStatus(fmt.Sprintf("Громкость: %d%%", newVolume))
		if vi.ttsManager != nil {
			go vi.ttsManager.PlaySpeech(vi.ctx, fmt.Sprintf("Громкость %d процентов", newVolume))
		}
	}
}

// handleSpeedChange handles playback speed changes.
func (vi *VisualInterface) handleSpeedChange(delta float64) {
	if vi.audioManager == nil {
		return
	}

	player := vi.audioManager.GetPlayer()
	if player == nil {
		return
	}

	info := player.GetPlaybackInfo()
	if info.State == audio.PlaybackStopped {
		return
	}

	newSpeed := info.Speed + delta
	if newSpeed < 0.5 {
		newSpeed = 0.5
	}
	if newSpeed > 2.0 {
		newSpeed = 2.0
	}

	if err := player.SetSpeed(newSpeed); err != nil {
		vi.SetError(fmt.Sprintf("Ошибка установки скорости: %v", err))
	} else {
		vi.SetStatus(fmt.Sprintf("Скорость: %.1fx", newSpeed))
		if vi.ttsManager != nil {
			go vi.ttsManager.PlaySpeech(vi.ctx, fmt.Sprintf("Скорость %.1f", newSpeed))
		}
	}
}

// handleDelete handles delete operations.
func (vi *VisualInterface) handleDelete() {
	// This would implement file deletion logic.
	vi.SetStatus("Функция удаления пока не реализована")
}

// Screen control functions.

// clearScreen clears the terminal screen.
func (vi *VisualInterface) clearScreen() {
	fmt.Print("\033[2J")
}

// moveCursor moves the cursor to the specified position.
func (vi *VisualInterface) moveCursor(row, col int) {
	fmt.Printf("\033[%d;%dH", row, col)
}

// hideCursor hides the terminal cursor.
func (vi *VisualInterface) hideCursor() {
	fmt.Print("\033[?25l")
}

// showCursor shows the terminal cursor.
func (vi *VisualInterface) showCursor() {
	fmt.Print("\033[?25h")
}

// getTerminalSize gets the terminal size.
func (vi *VisualInterface) getTerminalSize() (int, int, error) {
	cmd := exec.Command("stty", "size")
	cmd.Stdin = os.Stdin
	output, err := cmd.Output()
	if err != nil {
		return 80, 24, err // Default size.
	}

	var rows, cols int
	if _, err := fmt.Sscanf(string(output), "%d %d", &rows, &cols); err != nil {
		return 80, 24, err
	}

	return cols, rows, nil
}

// UpdateTerminalSize updates the interface size to match terminal.
func (vi *VisualInterface) UpdateTerminalSize() {
	width, height, err := vi.getTerminalSize()
	if err != nil {
		vi.logger.Warn("Failed to get terminal size: %v", err)
		return
	}

	vi.mutex.Lock()
	vi.width = width
	vi.height = height
	if vi.renderer != nil {
		vi.renderer.SetWidth(width)
		vi.renderer.SetHeight(height)
	}
	vi.mutex.Unlock()

	vi.logger.Debug("Terminal size updated: %dx%d", width, height)
}

// Helper functions.

func formatShortDuration(d time.Duration) string {
	minutes := int(d.Minutes())
	seconds := int(d.Seconds()) % 60
	return fmt.Sprintf("%d:%02d", minutes, seconds)
}

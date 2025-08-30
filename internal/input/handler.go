package input

import (
	"context"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"time"

	"raspberry-dictaphone-go/internal/logger"
)

// Command represents an input command.
type Command int

const (
	// Navigation commands.
	CmdUp Command = iota
	CmdDown
	CmdLeft
	CmdRight
	CmdSelect
	CmdBack

	// Media commands.
	CmdPlay
	CmdPause
	CmdStop
	CmdVolumeUp
	CmdVolumeDown
	CmdSpeedUp
	CmdSpeedDown

	// System commands.
	CmdDelete
	CmdPower

	// Unknown command.
	CmdUnknown
)

// CommandEvent represents a processed command event.
type CommandEvent struct {
	Command   Command
	Timestamp time.Time
	KeyCode   uint16
	KeyState  int32
}

// Handler handles input events from remote control devices.
type Handler struct {
	deviceName     string
	devicePath     string
	eventReader    *EventReader
	commandChan    chan CommandEvent
	logger         *logger.Logger
	ctx            context.Context
	cancel         context.CancelFunc
	wg             sync.WaitGroup
	isRunning      bool
	mutex          sync.RWMutex
	keyStates      map[uint16]KeyState
	repeatDelay    time.Duration
	repeatInterval time.Duration
}

// KeyState tracks the state of a key for repeat detection.
type KeyState struct {
	Pressed     bool
	PressTime   time.Time
	LastRepeat  time.Time
	RepeatCount int
}

// NewHandler creates a new input handler.
func NewHandler(deviceName string, log *logger.Logger) *Handler {
	return &Handler{
		deviceName:     deviceName,
		commandChan:    make(chan CommandEvent, 100),
		logger:         log,
		keyStates:      make(map[uint16]KeyState),
		repeatDelay:    500 * time.Millisecond,
		repeatInterval: 100 * time.Millisecond,
	}
}

// Start starts the input handler.
func (h *Handler) Start(ctx context.Context) error {
	h.mutex.Lock()
	defer h.mutex.Unlock()

	if h.isRunning {
		return fmt.Errorf("handler is already running")
	}

	// Find device.
	devicePath, err := h.findDevice()
	if err != nil {
		return fmt.Errorf("failed to find device: %w", err)
	}

	h.devicePath = devicePath
	h.logger.Info("Found input device: %s at %s", h.deviceName, devicePath)

	// Open event reader.
	h.eventReader, err = NewEventReader(devicePath)
	if err != nil {
		return fmt.Errorf("failed to open event reader: %w", err)
	}

	// Set up context.
	h.ctx, h.cancel = context.WithCancel(ctx)

	// Start event processing.
	h.wg.Add(1)
	go h.processEvents()

	h.isRunning = true
	h.logger.Info("Input handler started")

	return nil
}

// Stop stops the input handler.
func (h *Handler) Stop() error {
	h.mutex.Lock()
	defer h.mutex.Unlock()

	if !h.isRunning {
		return nil
	}

	// Cancel context.
	if h.cancel != nil {
		h.cancel()
	}

	// Wait for goroutines to finish.
	h.wg.Wait()

	// Close event reader.
	if h.eventReader != nil {
		h.eventReader.Close()
		h.eventReader = nil
	}

	// Close command channel.
	close(h.commandChan)

	h.isRunning = false
	h.logger.Info("Input handler stopped")

	return nil
}

// GetCommandChannel returns the command channel.
func (h *Handler) GetCommandChannel() <-chan CommandEvent {
	return h.commandChan
}

// IsRunning returns true if the handler is running.
func (h *Handler) IsRunning() bool {
	h.mutex.RLock()
	defer h.mutex.RUnlock()
	return h.isRunning
}

// findDevice finds the input device by name.
func (h *Handler) findDevice() (string, error) {
	inputDir := "/dev/input"
	
	entries, err := os.ReadDir(inputDir)
	if err != nil {
		return "", fmt.Errorf("failed to read input directory: %w", err)
	}

	for _, entry := range entries {
		if !strings.HasPrefix(entry.Name(), "event") {
			continue
		}

		devicePath := filepath.Join(inputDir, entry.Name())
		
		// Get device info.
		info, err := GetDeviceInfo(devicePath)
		if err != nil {
			h.logger.Debug("Failed to get info for device %s: %v", devicePath, err)
			continue
		}

		h.logger.Debug("Found device: %s (%s)", info.Name, devicePath)

		// Check if this is our target device.
		if strings.Contains(info.Name, h.deviceName) {
			return devicePath, nil
		}
	}

	return "", fmt.Errorf("device not found: %s", h.deviceName)
}

// processEvents processes input events in a loop.
func (h *Handler) processEvents() {
	defer h.wg.Done()

	h.logger.Debug("Starting event processing loop")

	for {
		select {
		case <-h.ctx.Done():
			h.logger.Debug("Event processing stopped by context")
			return

		default:
			// Read key event with timeout.
			keyEvent, err := h.readKeyEventWithTimeout(100 * time.Millisecond)
			if err != nil {
				if !strings.Contains(err.Error(), "timeout") {
					h.logger.Error("Failed to read key event: %v", err)
					time.Sleep(100 * time.Millisecond)
				}
				continue
			}

			if keyEvent != nil {
				h.processKeyEvent(*keyEvent)
			}
		}
	}
}

// readKeyEventWithTimeout reads a key event with timeout.
func (h *Handler) readKeyEventWithTimeout(timeout time.Duration) (*KeyEvent, error) {
	// This is a simplified implementation.
	// In a real implementation, you might want to use select with a timer.
	keyEvent, err := h.eventReader.ReadKeyEvent()
	if err != nil {
		return nil, err
	}

	return keyEvent, nil
}

// processKeyEvent processes a single key event.
func (h *Handler) processKeyEvent(keyEvent KeyEvent) {
	h.logger.Debug("Key event: %s %s", 
		KeyCodeToString(keyEvent.Code), 
		KeyStateToString(keyEvent.State))

	// Update key state.
	h.updateKeyState(keyEvent)

	// Convert to command.
	command := h.keyCodeToCommand(keyEvent.Code, keyEvent.State)
	if command == CmdUnknown {
		return
	}

	// Send command event.
	commandEvent := CommandEvent{
		Command:   command,
		Timestamp: keyEvent.Timestamp,
		KeyCode:   keyEvent.Code,
		KeyState:  keyEvent.State,
	}

	select {
	case h.commandChan <- commandEvent:
		h.logger.Debug("Sent command: %v", command)
	default:
		h.logger.Warn("Command channel full, dropping event")
	}
}

// updateKeyState updates the state of a key for repeat detection.
func (h *Handler) updateKeyState(keyEvent KeyEvent) {
	state, exists := h.keyStates[keyEvent.Code]
	
	switch keyEvent.State {
	case KEY_PRESSED:
		h.keyStates[keyEvent.Code] = KeyState{
			Pressed:     true,
			PressTime:   keyEvent.Timestamp,
			LastRepeat:  keyEvent.Timestamp,
			RepeatCount: 0,
		}

	case KEY_RELEASED:
		if exists {
			state.Pressed = false
			h.keyStates[keyEvent.Code] = state
		}

	case KEY_REPEATED:
		if exists && state.Pressed {
			state.LastRepeat = keyEvent.Timestamp
			state.RepeatCount++
			h.keyStates[keyEvent.Code] = state
		}
	}
}

// keyCodeToCommand converts a key code and state to a command.
func (h *Handler) keyCodeToCommand(code uint16, state int32) Command {
	// Only process key press events for most commands.
	if state != KEY_PRESSED && state != KEY_REPEATED {
		return CmdUnknown
	}

	switch code {
	case KEY_UP:
		return CmdUp
	case KEY_DOWN:
		return CmdDown
	case KEY_LEFT:
		// For left/right, we might want to handle both press and repeat for seeking.
		return CmdLeft
	case KEY_RIGHT:
		return CmdRight
	case KEY_SELECT:
		// Only respond to key press, not repeat for select.
		if state == KEY_PRESSED {
			return CmdSelect
		}
		return CmdUnknown
	case KEY_BACK:
		if state == KEY_PRESSED {
			return CmdBack
		}
		return CmdUnknown
	case KEY_POWER:
		if state == KEY_PRESSED {
			return CmdDelete
		}
		return CmdUnknown
	case KEY_PAGEUP:
		return CmdVolumeUp
	case KEY_PAGEDOWN:
		return CmdVolumeDown
	case KEY_VOLUMEUP:
		return CmdSpeedUp
	case KEY_VOLUMEDOWN:
		return CmdSpeedDown
	default:
		return CmdUnknown
	}
}

// CommandToString converts a command to string.
func CommandToString(cmd Command) string {
	switch cmd {
	case CmdUp:
		return "UP"
	case CmdDown:
		return "DOWN"
	case CmdLeft:
		return "LEFT"
	case CmdRight:
		return "RIGHT"
	case CmdSelect:
		return "SELECT"
	case CmdBack:
		return "BACK"
	case CmdPlay:
		return "PLAY"
	case CmdPause:
		return "PAUSE"
	case CmdStop:
		return "STOP"
	case CmdVolumeUp:
		return "VOLUME_UP"
	case CmdVolumeDown:
		return "VOLUME_DOWN"
	case CmdSpeedUp:
		return "SPEED_UP"
	case CmdSpeedDown:
		return "SPEED_DOWN"
	case CmdDelete:
		return "DELETE"
	case CmdPower:
		return "POWER"
	default:
		return "UNKNOWN"
	}
}

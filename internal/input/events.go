package input

import (
	"encoding/binary"
	"fmt"
	"os"
	"syscall"
	"time"
	"unsafe"
)

// Linux input event constants.
const (
	// Event types.
	EV_KEY = 0x01

	// Key codes.
	KEY_UP         = 103
	KEY_DOWN       = 108
	KEY_SELECT     = 353
	KEY_BACK       = 158
	KEY_LEFT       = 105
	KEY_RIGHT      = 106
	KEY_POWER      = 116
	KEY_PAGEUP     = 104
	KEY_PAGEDOWN   = 109
	KEY_VOLUMEUP   = 115
	KEY_VOLUMEDOWN = 114

	// Key states.
	KEY_RELEASED = 0
	KEY_PRESSED  = 1
	KEY_REPEATED = 2
)

// InputEvent represents a Linux input event.
type InputEvent struct {
	Time  syscall.Timeval
	Type  uint16
	Code  uint16
	Value int32
}

// KeyEvent represents a processed key event.
type KeyEvent struct {
	Code      uint16
	State     int32 // 0=released, 1=pressed, 2=repeated
	Timestamp time.Time
}

// EventReader reads Linux input events from device files.
type EventReader struct {
	devicePath string
	file       *os.File
}

// NewEventReader creates a new event reader for the specified device.
func NewEventReader(devicePath string) (*EventReader, error) {
	file, err := os.OpenFile(devicePath, os.O_RDONLY, 0)
	if err != nil {
		return nil, fmt.Errorf("failed to open device file: %w", err)
	}

	return &EventReader{
		devicePath: devicePath,
		file:       file,
	}, nil
}

// ReadEvent reads a single input event from the device.
func (r *EventReader) ReadEvent() (*InputEvent, error) {
	var event InputEvent
	
	// Read binary data from device file.
	err := binary.Read(r.file, binary.LittleEndian, &event)
	if err != nil {
		return nil, fmt.Errorf("failed to read input event: %w", err)
	}

	return &event, nil
}

// ReadKeyEvent reads and processes a key event.
func (r *EventReader) ReadKeyEvent() (*KeyEvent, error) {
	for {
		event, err := r.ReadEvent()
		if err != nil {
			return nil, err
		}

		// Only process key events.
		if event.Type == EV_KEY {
			return &KeyEvent{
				Code:      event.Code,
				State:     event.Value,
				Timestamp: time.Unix(event.Time.Sec, event.Time.Usec*1000),
			}, nil
		}

		// Skip non-key events.
	}
}

// Close closes the event reader.
func (r *EventReader) Close() error {
	if r.file != nil {
		return r.file.Close()
	}
	return nil
}

// DeviceInfo represents information about an input device.
type DeviceInfo struct {
	Path string
	Name string
	ID   DeviceID
}

// DeviceID represents device identification.
type DeviceID struct {
	BusType uint16
	Vendor  uint16
	Product uint16
	Version uint16
}

// GetDeviceInfo gets information about an input device.
func GetDeviceInfo(devicePath string) (*DeviceInfo, error) {
	file, err := os.OpenFile(devicePath, os.O_RDONLY, 0)
	if err != nil {
		return nil, fmt.Errorf("failed to open device: %w", err)
	}
	defer file.Close()

	info := &DeviceInfo{Path: devicePath}

	// Get device name using EVIOCGNAME ioctl.
	nameBuffer := make([]byte, 256)
	_, _, errno := syscall.Syscall(
		syscall.SYS_IOCTL,
		uintptr(file.Fd()),
		uintptr(0x80ff4506), // EVIOCGNAME(len)
		uintptr(unsafe.Pointer(&nameBuffer[0])),
	)
	
	if errno != 0 {
		return nil, fmt.Errorf("failed to get device name: %v", errno)
	}

	// Convert null-terminated string.
	for i, b := range nameBuffer {
		if b == 0 {
			info.Name = string(nameBuffer[:i])
			break
		}
	}

	// Get device ID using EVIOCGID ioctl.
	var deviceID [4]uint16
	_, _, errno = syscall.Syscall(
		syscall.SYS_IOCTL,
		uintptr(file.Fd()),
		uintptr(0x80084502), // EVIOCGID
		uintptr(unsafe.Pointer(&deviceID[0])),
	)

	if errno != 0 {
		return nil, fmt.Errorf("failed to get device ID: %v", errno)
	}

	info.ID = DeviceID{
		BusType: deviceID[0],
		Vendor:  deviceID[1],
		Product: deviceID[2],
		Version: deviceID[3],
	}

	return info, nil
}

// KeyCodeToString converts key code to human-readable string.
func KeyCodeToString(code uint16) string {
	switch code {
	case KEY_UP:
		return "UP"
	case KEY_DOWN:
		return "DOWN"
	case KEY_LEFT:
		return "LEFT"
	case KEY_RIGHT:
		return "RIGHT"
	case KEY_SELECT:
		return "SELECT"
	case KEY_BACK:
		return "BACK"
	case KEY_POWER:
		return "POWER"
	case KEY_PAGEUP:
		return "PAGE_UP"
	case KEY_PAGEDOWN:
		return "PAGE_DOWN"
	case KEY_VOLUMEUP:
		return "VOLUME_UP"
	case KEY_VOLUMEDOWN:
		return "VOLUME_DOWN"
	default:
		return fmt.Sprintf("KEY_%d", code)
	}
}

// KeyStateToString converts key state to human-readable string.
func KeyStateToString(state int32) string {
	switch state {
	case KEY_RELEASED:
		return "RELEASED"
	case KEY_PRESSED:
		return "PRESSED"
	case KEY_REPEATED:
		return "REPEATED"
	default:
		return fmt.Sprintf("STATE_%d", state)
	}
}

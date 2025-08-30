package usb

import (
	"context"
	"time"
)

// DeviceState represents the state of a USB device.
type DeviceState int

const (
	// DeviceConnected indicates device is connected but not mounted.
	DeviceConnected DeviceState = iota
	// DeviceMounted indicates device is connected and mounted.
	DeviceMounted
	// DeviceDisconnected indicates device is disconnected.
	DeviceDisconnected
)

// Device represents a USB storage device.
type Device struct {
	DevicePath  string      `json:"device_path"`
	Name        string      `json:"name"`
	Label       string      `json:"label"`
	Size        int64       `json:"size"`
	MountPoint  string      `json:"mount_point"`
	FileSystem  string      `json:"file_system"`
	State       DeviceState `json:"state"`
	ConnectedAt time.Time   `json:"connected_at"`
	MountedAt   time.Time   `json:"mounted_at"`
}

// DeviceEvent represents a USB device event.
type DeviceEvent struct {
	Type      EventType `json:"type"`
	Device    Device    `json:"device"`
	Timestamp time.Time `json:"timestamp"`
}

// EventType represents the type of device event.
type EventType int

const (
	// EventDeviceAdded indicates a device was connected.
	EventDeviceAdded EventType = iota
	// EventDeviceRemoved indicates a device was disconnected.
	EventDeviceRemoved
	// EventDeviceMounted indicates a device was mounted.
	EventDeviceMounted
	// EventDeviceUnmounted indicates a device was unmounted.
	EventDeviceUnmounted
)

// Monitor defines the interface for USB device monitoring.
type Monitor interface {
	// Start starts the USB monitor.
	Start(ctx context.Context) error

	// Stop stops the USB monitor.
	Stop() error

	// GetDevices returns currently connected devices.
	GetDevices() []Device

	// GetDevice returns a specific device by path.
	GetDevice(devicePath string) (*Device, error)

	// GetEventChannel returns the channel for device events.
	GetEventChannel() <-chan DeviceEvent

	// IsRunning returns true if monitor is running.
	IsRunning() bool
}

// Mounter defines the interface for mounting/unmounting devices.
type Mounter interface {
	// Mount mounts a device and returns the mount point.
	Mount(ctx context.Context, devicePath string) (string, error)

	// Unmount unmounts a device.
	Unmount(ctx context.Context, devicePath string) error

	// IsMounted checks if a device is mounted.
	IsMounted(devicePath string) (bool, string, error)

	// GetMountPoint returns the mount point for a device.
	GetMountPoint(devicePath string) (string, error)

	// GetSupportedFileSystems returns supported file systems.
	GetSupportedFileSystems() []string
}

// Manager defines the interface for managing USB operations.
type Manager interface {
	// GetMonitor returns the USB monitor instance.
	GetMonitor() Monitor

	// GetMounter returns the USB mounter instance.
	GetMounter() Mounter

	// Initialize initializes the USB manager.
	Initialize() error

	// Close closes the USB manager and releases resources.
	Close() error

	// AutoMount enables/disables automatic mounting.
	SetAutoMount(enabled bool)

	// IsAutoMount returns true if auto-mount is enabled.
	IsAutoMount() bool

	// MountDevice mounts a device.
	MountDevice(ctx context.Context, devicePath string) (string, error)

	// UnmountDevice unmounts a device.
	UnmountDevice(ctx context.Context, devicePath string) error

	// EjectDevice safely ejects a device.
	EjectDevice(ctx context.Context, devicePath string) error

	// GetDeviceInfo returns detailed information about a device.
	GetDeviceInfo(devicePath string) (*DeviceInfo, error)
}

// DeviceInfo contains detailed information about a USB device.
type DeviceInfo struct {
	DevicePath   string            `json:"device_path"`
	Name         string            `json:"name"`
	Label        string            `json:"label"`
	Size         int64             `json:"size"`
	FileSystem   string            `json:"file_system"`
	MountPoint   string            `json:"mount_point"`
	State        DeviceState       `json:"state"`
	Properties   map[string]string `json:"properties"`
	ConnectedAt  time.Time         `json:"connected_at"`
	MountedAt    time.Time         `json:"mounted_at"`
	FreeSpace    int64             `json:"free_space"`
	UsedSpace    int64             `json:"used_space"`
	IsReadOnly   bool              `json:"is_read_only"`
	IsRemovable  bool              `json:"is_removable"`
	Vendor       string            `json:"vendor"`
	Model        string            `json:"model"`
	SerialNumber string            `json:"serial_number"`
}

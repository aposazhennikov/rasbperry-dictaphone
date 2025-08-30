package usb

import (
	"context"
	"fmt"
	"strconv"
	"strings"
	"sync"
	"time"

	"github.com/jochenvg/go-udev"
	"raspberry-dictaphone-go/internal/logger"
)

// UdevMonitor implements the Monitor interface using go-udev.
type UdevMonitor struct {
	udev        *udev.Udev
	monitor     *udev.Monitor
	devices     map[string]Device
	eventChan   chan DeviceEvent
	logger      *logger.Logger
	ctx         context.Context
	cancel      context.CancelFunc
	wg          sync.WaitGroup
	isRunning   bool
	mutex       sync.RWMutex
	autoMount   bool
	mounter     Mounter
}

// NewUdevMonitor creates a new USB monitor using udev.
func NewUdevMonitor(log *logger.Logger, mounter Mounter) (*UdevMonitor, error) {
	// Initialize udev.
	u := udev.Udev{}
	
	// Create monitor for block devices.
	monitor := u.NewMonitorFromNetlink("udev")
	if monitor == nil {
		return nil, fmt.Errorf("failed to create udev monitor")
	}

	// Filter for block devices.
	if err := monitor.FilterAddMatchSubsystemDevtype("block", "partition"); err != nil {
		return nil, fmt.Errorf("failed to add filter: %w", err)
	}

	return &UdevMonitor{
		udev:      &u,
		monitor:   monitor,
		devices:   make(map[string]Device),
		eventChan: make(chan DeviceEvent, 100),
		logger:    log,
		autoMount: true,
		mounter:   mounter,
	}, nil
}

// Start starts the USB monitor.
func (m *UdevMonitor) Start(ctx context.Context) error {
	m.mutex.Lock()
	defer m.mutex.Unlock()

	if m.isRunning {
		return fmt.Errorf("monitor is already running")
	}

	// Set up context.
	m.ctx, m.cancel = context.WithCancel(ctx)

	// Enable monitoring.
	if err := m.monitor.EnableReceiving(); err != nil {
		return fmt.Errorf("failed to enable monitoring: %w", err)
	}

	// Scan for existing devices.
	if err := m.scanExistingDevices(); err != nil {
		m.logger.Warn("Failed to scan existing devices: %v", err)
	}

	// Start monitoring goroutine.
	m.wg.Add(1)
	go m.monitorEvents()

	m.isRunning = true
	m.logger.Info("USB monitor started")

	return nil
}

// Stop stops the USB monitor.
func (m *UdevMonitor) Stop() error {
	m.mutex.Lock()
	defer m.mutex.Unlock()

	if !m.isRunning {
		return nil
	}

	// Cancel context.
	if m.cancel != nil {
		m.cancel()
	}

	// Wait for goroutines to finish.
	m.wg.Wait()

	// Disable monitoring.
	if m.monitor != nil {
		m.monitor.DisableReceiving()
	}

	// Close event channel.
	close(m.eventChan)

	m.isRunning = false
	m.logger.Info("USB monitor stopped")

	return nil
}

// GetDevices returns currently connected devices.
func (m *UdevMonitor) GetDevices() []Device {
	m.mutex.RLock()
	defer m.mutex.RUnlock()

	devices := make([]Device, 0, len(m.devices))
	for _, device := range m.devices {
		devices = append(devices, device)
	}

	return devices
}

// GetDevice returns a specific device by path.
func (m *UdevMonitor) GetDevice(devicePath string) (*Device, error) {
	m.mutex.RLock()
	defer m.mutex.RUnlock()

	device, exists := m.devices[devicePath]
	if !exists {
		return nil, fmt.Errorf("device not found: %s", devicePath)
	}

	return &device, nil
}

// GetEventChannel returns the channel for device events.
func (m *UdevMonitor) GetEventChannel() <-chan DeviceEvent {
	return m.eventChan
}

// IsRunning returns true if monitor is running.
func (m *UdevMonitor) IsRunning() bool {
	m.mutex.RLock()
	defer m.mutex.RUnlock()
	return m.isRunning
}

// scanExistingDevices scans for existing USB storage devices.
func (m *UdevMonitor) scanExistingDevices() error {
	// Create enumerator for block devices.
	enumerate := m.udev.NewEnumerate()
	if err := enumerate.AddMatchSubsystem("block"); err != nil {
		return fmt.Errorf("failed to add subsystem match: %w", err)
	}

	if err := enumerate.AddMatchProperty("DEVTYPE", "partition"); err != nil {
		return fmt.Errorf("failed to add devtype match: %w", err)
	}

	if err := enumerate.ScanDevices(); err != nil {
		return fmt.Errorf("failed to scan devices: %w", err)
	}

	// Process each device.
	for device := enumerate.ListEntry(); device != nil; device = device.GetNext() {
		udevDevice := m.udev.NewDeviceFromSyspath(device.GetName())
		if udevDevice != nil {
			if usbDevice := m.processUdevDevice(udevDevice, "add"); usbDevice != nil {
				m.devices[usbDevice.DevicePath] = *usbDevice
				m.logger.Debug("Found existing device: %s", usbDevice.DevicePath)
			}
			udevDevice.Unref()
		}
	}

	enumerate.Unref()
	return nil
}

// monitorEvents monitors udev events in a loop.
func (m *UdevMonitor) monitorEvents() {
	defer m.wg.Done()

	m.logger.Debug("Starting USB event monitoring")

	for {
		select {
		case <-m.ctx.Done():
			m.logger.Debug("USB monitoring stopped by context")
			return

		default:
			// Receive device event with timeout.
			device := m.monitor.ReceiveDeviceTimeout(100)
			if device == nil {
				continue
			}

			// Process the event.
			m.processDeviceEvent(device)
			device.Unref()
		}
	}
}

// processDeviceEvent processes a single udev device event.
func (m *UdevMonitor) processDeviceEvent(udevDevice *udev.Device) {
	action := udevDevice.GetAction()
	if action == "" {
		return
	}

	m.logger.Debug("USB event: %s for device %s", action, udevDevice.GetDevnode())

	switch action {
	case "add":
		if device := m.processUdevDevice(udevDevice, action); device != nil {
			m.mutex.Lock()
			m.devices[device.DevicePath] = *device
			m.mutex.Unlock()

			// Send event.
			m.sendEvent(DeviceEvent{
				Type:      EventDeviceAdded,
				Device:    *device,
				Timestamp: time.Now(),
			})

			// Auto-mount if enabled.
			if m.autoMount && m.mounter != nil {
				go m.autoMountDevice(device.DevicePath)
			}
		}

	case "remove":
		devicePath := udevDevice.GetDevnode()
		if devicePath != "" {
			m.mutex.Lock()
			device, exists := m.devices[devicePath]
			if exists {
				delete(m.devices, devicePath)
			}
			m.mutex.Unlock()

			if exists {
				device.State = DeviceDisconnected
				m.sendEvent(DeviceEvent{
					Type:      EventDeviceRemoved,
					Device:    device,
					Timestamp: time.Now(),
				})
			}
		}
	}
}

// processUdevDevice converts a udev device to our Device struct.
func (m *UdevMonitor) processUdevDevice(udevDevice *udev.Device, action string) *Device {
	devicePath := udevDevice.GetDevnode()
	if devicePath == "" {
		return nil
	}

	// Check if this is a removable storage device.
	if !m.isRemovableStorageDevice(udevDevice) {
		return nil
	}

	device := &Device{
		DevicePath:  devicePath,
		Name:        m.getDeviceName(udevDevice),
		Label:       udevDevice.GetProperty("ID_FS_LABEL"),
		FileSystem:  udevDevice.GetProperty("ID_FS_TYPE"),
		State:       DeviceConnected,
		ConnectedAt: time.Now(),
	}

	// Get device size.
	if sizeStr := udevDevice.GetSysattrValue("size"); sizeStr != "" {
		if size, err := strconv.ParseInt(sizeStr, 10, 64); err == nil {
			device.Size = size * 512 // Size is in 512-byte blocks.
		}
	}

	// Check if already mounted.
	if mounted, mountPoint, err := m.mounter.IsMounted(devicePath); err == nil && mounted {
		device.State = DeviceMounted
		device.MountPoint = mountPoint
		device.MountedAt = time.Now()
	}

	return device
}

// isRemovableStorageDevice checks if a device is a removable storage device.
func (m *UdevMonitor) isRemovableStorageDevice(device *udev.Device) bool {
	// Check if it's a partition.
	if device.GetProperty("DEVTYPE") != "partition" {
		return false
	}

	// Check if it's removable.
	parent := device.GetParent()
	if parent == nil {
		return false
	}

	removable := parent.GetSysattrValue("removable")
	if removable != "1" {
		return false
	}

	// Check if it has a file system.
	fsType := device.GetProperty("ID_FS_TYPE")
	if fsType == "" {
		return false
	}

	// Check if file system is supported.
	supportedFS := []string{"vfat", "exfat", "ntfs", "ext2", "ext3", "ext4"}
	for _, supported := range supportedFS {
		if fsType == supported {
			return true
		}
	}

	return false
}

// getDeviceName generates a human-readable device name.
func (m *UdevMonitor) getDeviceName(device *udev.Device) string {
	// Try to get vendor and model.
	vendor := device.GetProperty("ID_VENDOR")
	model := device.GetProperty("ID_MODEL")

	if vendor != "" && model != "" {
		return fmt.Sprintf("%s %s", vendor, model)
	}

	if model != "" {
		return model
	}

	if vendor != "" {
		return vendor
	}

	// Fallback to device path.
	devicePath := device.GetDevnode()
	if devicePath != "" {
		parts := strings.Split(devicePath, "/")
		if len(parts) > 0 {
			return parts[len(parts)-1]
		}
	}

	return "Unknown Device"
}

// autoMountDevice automatically mounts a device.
func (m *UdevMonitor) autoMountDevice(devicePath string) {
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	mountPoint, err := m.mounter.Mount(ctx, devicePath)
	if err != nil {
		m.logger.Error("Failed to auto-mount device %s: %v", devicePath, err)
		return
	}

	// Update device state.
	m.mutex.Lock()
	if device, exists := m.devices[devicePath]; exists {
		device.State = DeviceMounted
		device.MountPoint = mountPoint
		device.MountedAt = time.Now()
		m.devices[devicePath] = device

		// Send mount event.
		go m.sendEvent(DeviceEvent{
			Type:      EventDeviceMounted,
			Device:    device,
			Timestamp: time.Now(),
		})
	}
	m.mutex.Unlock()

	m.logger.Info("Auto-mounted device %s at %s", devicePath, mountPoint)
}

// sendEvent sends a device event to the event channel.
func (m *UdevMonitor) sendEvent(event DeviceEvent) {
	select {
	case m.eventChan <- event:
	default:
		m.logger.Warn("Event channel full, dropping USB event")
	}
}

// Close closes the monitor and releases resources.
func (m *UdevMonitor) Close() error {
	if err := m.Stop(); err != nil {
		return err
	}

	if m.monitor != nil {
		m.monitor.Unref()
	}

	if m.udev != nil {
		m.udev.Unref()
	}

	return nil
}

package usb

import (
	"context"
	"fmt"
	"os/exec"
	"strconv"
	"strings"
	"syscall"

	"raspberry-dictaphone-go/internal/logger"
)

// USBManager implements the Manager interface.
type USBManager struct {
	monitor   Monitor
	mounter   Mounter
	logger    *logger.Logger
	autoMount bool
}

// NewUSBManager creates a new USB manager.
func NewUSBManager(log *logger.Logger, useUdisks bool) (*USBManager, error) {
	var mounter Mounter

	// Choose mounter implementation.
	if useUdisks {
		mounter = NewUdisksMounter(log)
	} else {
		mounter = NewSystemMounter(log, "/mnt")
	}

	// Create monitor.
	monitor, err := NewUdevMonitor(log, mounter)
	if err != nil {
		return nil, fmt.Errorf("failed to create monitor: %w", err)
	}

	return &USBManager{
		monitor:   monitor,
		mounter:   mounter,
		logger:    log,
		autoMount: true,
	}, nil
}

// GetMonitor returns the USB monitor instance.
func (m *USBManager) GetMonitor() Monitor {
	return m.monitor
}

// GetMounter returns the USB mounter instance.
func (m *USBManager) GetMounter() Mounter {
	return m.mounter
}

// Initialize initializes the USB manager.
func (m *USBManager) Initialize() error {
	// Check if required utilities are available.
	if err := m.checkRequiredUtilities(); err != nil {
		return fmt.Errorf("required utilities check failed: %w", err)
	}

	m.logger.Info("USB manager initialized successfully")
	return nil
}

// Close closes the USB manager and releases resources.
func (m *USBManager) Close() error {
	if monitor, ok := m.monitor.(*UdevMonitor); ok {
		return monitor.Close()
	}
	return nil
}

// SetAutoMount enables/disables automatic mounting.
func (m *USBManager) SetAutoMount(enabled bool) {
	m.autoMount = enabled
	if monitor, ok := m.monitor.(*UdevMonitor); ok {
		monitor.autoMount = enabled
	}
	m.logger.Info("Auto-mount %s", map[bool]string{true: "enabled", false: "disabled"}[enabled])
}

// IsAutoMount returns true if auto-mount is enabled.
func (m *USBManager) IsAutoMount() bool {
	return m.autoMount
}

// MountDevice mounts a device.
func (m *USBManager) MountDevice(ctx context.Context, devicePath string) (string, error) {
	return m.mounter.Mount(ctx, devicePath)
}

// UnmountDevice unmounts a device.
func (m *USBManager) UnmountDevice(ctx context.Context, devicePath string) error {
	return m.mounter.Unmount(ctx, devicePath)
}

// EjectDevice safely ejects a device.
func (m *USBManager) EjectDevice(ctx context.Context, devicePath string) error {
	m.logger.Debug("Ejecting device: %s", devicePath)

	// First unmount the device.
	if err := m.mounter.Unmount(ctx, devicePath); err != nil {
		return fmt.Errorf("failed to unmount device: %w", err)
	}

	// Get the parent block device (e.g., /dev/sdb from /dev/sdb1).
	parentDevice := m.getParentBlockDevice(devicePath)

	// Use udisksctl to power off the device if available.
	if m.isUdisksAvailable() {
		cmd := exec.CommandContext(ctx, "udisksctl", "power-off", "-b", parentDevice, "--no-user-interaction")
		if output, err := cmd.CombinedOutput(); err != nil {
			m.logger.Warn("Failed to power off device %s: %v, output: %s", parentDevice, err, string(output))
		} else {
			m.logger.Info("Successfully ejected device %s", devicePath)
			return nil
		}
	}

	// Fallback: sync and eject using eject command.
	if err := m.syncDevice(parentDevice); err != nil {
		m.logger.Warn("Failed to sync device: %v", err)
	}

	cmd := exec.CommandContext(ctx, "eject", parentDevice)
	if output, err := cmd.CombinedOutput(); err != nil {
		return fmt.Errorf("failed to eject device %s: %w, output: %s", parentDevice, err, string(output))
	}

	m.logger.Info("Successfully ejected device %s", devicePath)
	return nil
}

// GetDeviceInfo returns detailed information about a device.
func (m *USBManager) GetDeviceInfo(devicePath string) (*DeviceInfo, error) {
	// Get basic device info from monitor.
	device, err := m.monitor.GetDevice(devicePath)
	if err != nil {
		return nil, fmt.Errorf("device not found: %w", err)
	}

	// Create detailed info.
	info := &DeviceInfo{
		DevicePath:   device.DevicePath,
		Name:         device.Name,
		Label:        device.Label,
		Size:         device.Size,
		FileSystem:   device.FileSystem,
		MountPoint:   device.MountPoint,
		State:        device.State,
		Properties:   make(map[string]string),
		ConnectedAt:  device.ConnectedAt,
		MountedAt:    device.MountedAt,
		IsRemovable:  true, // All USB devices are removable.
	}

	// Get additional information.
	if err := m.enrichDeviceInfo(info); err != nil {
		m.logger.Warn("Failed to get additional device info: %v", err)
	}

	return info, nil
}

// checkRequiredUtilities checks if required utilities are available.
func (m *USBManager) checkRequiredUtilities() error {
	// Check for basic utilities.
	required := []string{"mount", "umount", "blkid"}
	for _, util := range required {
		if err := exec.Command("which", util).Run(); err != nil {
			return fmt.Errorf("required utility not found: %s", util)
		}
	}

	// Check for optional utilities.
	optional := []string{"udisksctl", "eject", "sync"}
	for _, util := range optional {
		if err := exec.Command("which", util).Run(); err != nil {
			m.logger.Warn("Optional utility not found: %s", util)
		}
	}

	return nil
}

// isUdisksAvailable checks if udisksctl is available.
func (m *USBManager) isUdisksAvailable() bool {
	return exec.Command("which", "udisksctl").Run() == nil
}

// getParentBlockDevice gets the parent block device path.
func (m *USBManager) getParentBlockDevice(devicePath string) string {
	// Convert /dev/sdb1 to /dev/sdb.
	if len(devicePath) > 0 && devicePath[len(devicePath)-1] >= '0' && devicePath[len(devicePath)-1] <= '9' {
		// Remove the partition number.
		for i := len(devicePath) - 1; i >= 0; i-- {
			if devicePath[i] < '0' || devicePath[i] > '9' {
				return devicePath[:i+1]
			}
		}
	}
	return devicePath
}

// syncDevice syncs a device to ensure all data is written.
func (m *USBManager) syncDevice(devicePath string) error {
	// Use sync command.
	cmd := exec.Command("sync")
	if err := cmd.Run(); err != nil {
		return fmt.Errorf("sync failed: %w", err)
	}

	// Also try device-specific sync.
	cmd = exec.Command("blockdev", "--flushbufs", devicePath)
	if err := cmd.Run(); err != nil {
		// This might fail on some systems, so just warn.
		m.logger.Warn("Failed to flush device buffers for %s: %v", devicePath, err)
	}

	return nil
}

// enrichDeviceInfo adds additional information to device info.
func (m *USBManager) enrichDeviceInfo(info *DeviceInfo) error {
	// Get vendor and model using lsblk.
	cmd := exec.Command("lsblk", "-n", "-o", "VENDOR,MODEL,SERIAL", info.DevicePath)
	output, err := cmd.Output()
	if err == nil {
		fields := strings.Fields(string(output))
		if len(fields) >= 1 && fields[0] != "" {
			info.Vendor = fields[0]
		}
		if len(fields) >= 2 && fields[1] != "" {
			info.Model = fields[1]
		}
		if len(fields) >= 3 && fields[2] != "" {
			info.SerialNumber = fields[2]
		}
	}

	// Get disk usage if mounted.
	if info.State == DeviceMounted && info.MountPoint != "" {
		if err := m.getDiskUsage(info); err != nil {
			m.logger.Debug("Failed to get disk usage for %s: %v", info.MountPoint, err)
		}
	}

	// Check if read-only.
	if err := m.checkReadOnly(info); err != nil {
		m.logger.Debug("Failed to check read-only status for %s: %v", info.DevicePath, err)
	}

	return nil
}

// getDiskUsage gets disk usage information.
func (m *USBManager) getDiskUsage(info *DeviceInfo) error {
	var stat syscall.Statfs_t
	if err := syscall.Statfs(info.MountPoint, &stat); err != nil {
		return fmt.Errorf("failed to get filesystem stats: %w", err)
	}

	// Calculate sizes.
	blockSize := int64(stat.Bsize)
	totalSize := int64(stat.Blocks) * blockSize
	freeSize := int64(stat.Bavail) * blockSize
	usedSize := totalSize - freeSize

	info.Size = totalSize
	info.FreeSpace = freeSize
	info.UsedSpace = usedSize

	return nil
}

// checkReadOnly checks if device is mounted read-only.
func (m *USBManager) checkReadOnly(info *DeviceInfo) error {
	if info.State != DeviceMounted {
		return nil
	}

	// Check mount options in /proc/mounts.
	cmd := exec.Command("grep", info.DevicePath, "/proc/mounts")
	output, err := cmd.Output()
	if err != nil {
		return fmt.Errorf("failed to check mount options: %w", err)
	}

	mountLine := string(output)
	if strings.Contains(mountLine, "ro,") || strings.Contains(mountLine, ",ro") || strings.HasSuffix(mountLine, " ro") {
		info.IsReadOnly = true
	}

	return nil
}

// EventTypeToString converts event type to string.
func EventTypeToString(eventType EventType) string {
	switch eventType {
	case EventDeviceAdded:
		return "ADDED"
	case EventDeviceRemoved:
		return "REMOVED"
	case EventDeviceMounted:
		return "MOUNTED"
	case EventDeviceUnmounted:
		return "UNMOUNTED"
	default:
		return "UNKNOWN"
	}
}

// DeviceStateToString converts device state to string.
func DeviceStateToString(state DeviceState) string {
	switch state {
	case DeviceConnected:
		return "CONNECTED"
	case DeviceMounted:
		return "MOUNTED"
	case DeviceDisconnected:
		return "DISCONNECTED"
	default:
		return "UNKNOWN"
	}
}

// FormatSize formats a size in bytes to human-readable format.
func FormatSize(bytes int64) string {
	const unit = 1024
	if bytes < unit {
		return fmt.Sprintf("%d B", bytes)
	}
	div, exp := int64(unit), 0
	for n := bytes / unit; n >= unit; n /= unit {
		div *= unit
		exp++
	}
	return fmt.Sprintf("%.1f %cB", float64(bytes)/float64(div), "KMGTPE"[exp])
}

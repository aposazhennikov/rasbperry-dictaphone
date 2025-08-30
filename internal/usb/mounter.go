package usb

import (
	"bufio"
	"context"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"time"

	"raspberry-dictaphone-go/internal/logger"
)

// UdisksMounter implements the Mounter interface using udisks2.
type UdisksMounter struct {
	logger             *logger.Logger
	mountTimeout       time.Duration
	supportedFileSystems []string
}

// NewUdisksMounter creates a new udisks2-based mounter.
func NewUdisksMounter(log *logger.Logger) *UdisksMounter {
	return &UdisksMounter{
		logger:       log,
		mountTimeout: 30 * time.Second,
		supportedFileSystems: []string{
			"vfat", "fat32", "fat16", "fat12",
			"exfat",
			"ntfs",
			"ext2", "ext3", "ext4",
			"hfs", "hfsplus",
		},
	}
}

// Mount mounts a device and returns the mount point.
func (m *UdisksMounter) Mount(ctx context.Context, devicePath string) (string, error) {
	m.logger.Debug("Mounting device: %s", devicePath)

	// Check if already mounted.
	if mounted, mountPoint, err := m.IsMounted(devicePath); err != nil {
		return "", fmt.Errorf("failed to check mount status: %w", err)
	} else if mounted {
		m.logger.Debug("Device %s already mounted at %s", devicePath, mountPoint)
		return mountPoint, nil
	}

	// Create context with timeout.
	ctx, cancel := context.WithTimeout(ctx, m.mountTimeout)
	defer cancel()

	// Use udisksctl to mount the device.
	cmd := exec.CommandContext(ctx, "udisksctl", "mount", "-b", devicePath, "--no-user-interaction")
	output, err := cmd.CombinedOutput()
	if err != nil {
		return "", fmt.Errorf("failed to mount device %s: %w, output: %s", devicePath, err, string(output))
	}

	// Parse mount point from output.
	// Output format: "Mounted /dev/sdb1 at /media/user/LABEL."
	outputStr := string(output)
	mountPoint := m.parseMountPoint(outputStr)
	if mountPoint == "" {
		return "", fmt.Errorf("failed to parse mount point from output: %s", outputStr)
	}

	m.logger.Info("Successfully mounted %s at %s", devicePath, mountPoint)
	return mountPoint, nil
}

// Unmount unmounts a device.
func (m *UdisksMounter) Unmount(ctx context.Context, devicePath string) error {
	m.logger.Debug("Unmounting device: %s", devicePath)

	// Check if mounted.
	if mounted, _, err := m.IsMounted(devicePath); err != nil {
		return fmt.Errorf("failed to check mount status: %w", err)
	} else if !mounted {
		m.logger.Debug("Device %s is not mounted", devicePath)
		return nil
	}

	// Create context with timeout.
	ctx, cancel := context.WithTimeout(ctx, m.mountTimeout)
	defer cancel()

	// Use udisksctl to unmount the device.
	cmd := exec.CommandContext(ctx, "udisksctl", "unmount", "-b", devicePath, "--no-user-interaction")
	output, err := cmd.CombinedOutput()
	if err != nil {
		return fmt.Errorf("failed to unmount device %s: %w, output: %s", devicePath, err, string(output))
	}

	m.logger.Info("Successfully unmounted %s", devicePath)
	return nil
}

// IsMounted checks if a device is mounted.
func (m *UdisksMounter) IsMounted(devicePath string) (bool, string, error) {
	// Read /proc/mounts to check if device is mounted.
	file, err := os.Open("/proc/mounts")
	if err != nil {
		return false, "", fmt.Errorf("failed to open /proc/mounts: %w", err)
	}
	defer file.Close()

	scanner := bufio.NewScanner(file)
	for scanner.Scan() {
		line := scanner.Text()
		fields := strings.Fields(line)
		if len(fields) >= 2 && fields[0] == devicePath {
			return true, fields[1], nil
		}
	}

	if err := scanner.Err(); err != nil {
		return false, "", fmt.Errorf("error reading /proc/mounts: %w", err)
	}

	return false, "", nil
}

// GetMountPoint returns the mount point for a device.
func (m *UdisksMounter) GetMountPoint(devicePath string) (string, error) {
	mounted, mountPoint, err := m.IsMounted(devicePath)
	if err != nil {
		return "", err
	}

	if !mounted {
		return "", fmt.Errorf("device %s is not mounted", devicePath)
	}

	return mountPoint, nil
}

// GetSupportedFileSystems returns supported file systems.
func (m *UdisksMounter) GetSupportedFileSystems() []string {
	return m.supportedFileSystems
}

// parseMountPoint parses mount point from udisksctl output.
func (m *UdisksMounter) parseMountPoint(output string) string {
	// Example output: "Mounted /dev/sdb1 at /media/user/LABEL."
	lines := strings.Split(output, "\n")
	for _, line := range lines {
		line = strings.TrimSpace(line)
		if strings.HasPrefix(line, "Mounted") && strings.Contains(line, " at ") {
			parts := strings.Split(line, " at ")
			if len(parts) >= 2 {
				mountPoint := strings.TrimSuffix(parts[1], ".")
				return strings.TrimSpace(mountPoint)
			}
		}
	}
	return ""
}

// SystemMounter implements the Mounter interface using system mount command.
type SystemMounter struct {
	logger             *logger.Logger
	mountTimeout       time.Duration
	mountBaseDir       string
	supportedFileSystems []string
}

// NewSystemMounter creates a new system mount-based mounter.
func NewSystemMounter(log *logger.Logger, mountBaseDir string) *SystemMounter {
	if mountBaseDir == "" {
		mountBaseDir = "/mnt"
	}

	return &SystemMounter{
		logger:       log,
		mountTimeout: 30 * time.Second,
		mountBaseDir: mountBaseDir,
		supportedFileSystems: []string{
			"vfat", "fat32", "fat16", "fat12",
			"exfat",
			"ntfs",
			"ext2", "ext3", "ext4",
		},
	}
}

// Mount mounts a device and returns the mount point.
func (m *SystemMounter) Mount(ctx context.Context, devicePath string) (string, error) {
	m.logger.Debug("Mounting device: %s", devicePath)

	// Check if already mounted.
	if mounted, mountPoint, err := m.IsMounted(devicePath); err != nil {
		return "", fmt.Errorf("failed to check mount status: %w", err)
	} else if mounted {
		m.logger.Debug("Device %s already mounted at %s", devicePath, mountPoint)
		return mountPoint, nil
	}

	// Detect file system.
	fsType, err := m.detectFileSystem(devicePath)
	if err != nil {
		return "", fmt.Errorf("failed to detect file system: %w", err)
	}

	// Create mount point.
	deviceName := filepath.Base(devicePath)
	mountPoint := filepath.Join(m.mountBaseDir, deviceName)
	
	if err := os.MkdirAll(mountPoint, 0755); err != nil {
		return "", fmt.Errorf("failed to create mount point: %w", err)
	}

	// Create context with timeout.
	ctx, cancel := context.WithTimeout(ctx, m.mountTimeout)
	defer cancel()

	// Mount the device.
	var cmd *exec.Cmd
	switch fsType {
	case "vfat", "fat32", "fat16", "fat12":
		cmd = exec.CommandContext(ctx, "mount", "-t", "vfat", "-o", "rw,umask=0000", devicePath, mountPoint)
	case "exfat":
		cmd = exec.CommandContext(ctx, "mount", "-t", "exfat", "-o", "rw,umask=0000", devicePath, mountPoint)
	case "ntfs":
		cmd = exec.CommandContext(ctx, "mount", "-t", "ntfs-3g", "-o", "rw,umask=0000", devicePath, mountPoint)
	case "ext2", "ext3", "ext4":
		cmd = exec.CommandContext(ctx, "mount", "-t", fsType, "-o", "rw", devicePath, mountPoint)
	default:
		// Try auto-detection.
		cmd = exec.CommandContext(ctx, "mount", "-o", "rw", devicePath, mountPoint)
	}

	output, err := cmd.CombinedOutput()
	if err != nil {
		// Clean up mount point on failure.
		os.Remove(mountPoint)
		return "", fmt.Errorf("failed to mount device %s: %w, output: %s", devicePath, err, string(output))
	}

	m.logger.Info("Successfully mounted %s at %s", devicePath, mountPoint)
	return mountPoint, nil
}

// Unmount unmounts a device.
func (m *SystemMounter) Unmount(ctx context.Context, devicePath string) error {
	m.logger.Debug("Unmounting device: %s", devicePath)

	// Get current mount point.
	mounted, mountPoint, err := m.IsMounted(devicePath)
	if err != nil {
		return fmt.Errorf("failed to check mount status: %w", err)
	}

	if !mounted {
		m.logger.Debug("Device %s is not mounted", devicePath)
		return nil
	}

	// Create context with timeout.
	ctx, cancel := context.WithTimeout(ctx, m.mountTimeout)
	defer cancel()

	// Unmount the device.
	cmd := exec.CommandContext(ctx, "umount", devicePath)
	output, err := cmd.CombinedOutput()
	if err != nil {
		return fmt.Errorf("failed to unmount device %s: %w, output: %s", devicePath, err, string(output))
	}

	// Remove mount point if it's in our base directory.
	if strings.HasPrefix(mountPoint, m.mountBaseDir) {
		if err := os.Remove(mountPoint); err != nil {
			m.logger.Warn("Failed to remove mount point %s: %v", mountPoint, err)
		}
	}

	m.logger.Info("Successfully unmounted %s", devicePath)
	return nil
}

// IsMounted checks if a device is mounted.
func (m *SystemMounter) IsMounted(devicePath string) (bool, string, error) {
	// Read /proc/mounts to check if device is mounted.
	file, err := os.Open("/proc/mounts")
	if err != nil {
		return false, "", fmt.Errorf("failed to open /proc/mounts: %w", err)
	}
	defer file.Close()

	scanner := bufio.NewScanner(file)
	for scanner.Scan() {
		line := scanner.Text()
		fields := strings.Fields(line)
		if len(fields) >= 2 && fields[0] == devicePath {
			return true, fields[1], nil
		}
	}

	if err := scanner.Err(); err != nil {
		return false, "", fmt.Errorf("error reading /proc/mounts: %w", err)
	}

	return false, "", nil
}

// GetMountPoint returns the mount point for a device.
func (m *SystemMounter) GetMountPoint(devicePath string) (string, error) {
	mounted, mountPoint, err := m.IsMounted(devicePath)
	if err != nil {
		return "", err
	}

	if !mounted {
		return "", fmt.Errorf("device %s is not mounted", devicePath)
	}

	return mountPoint, nil
}

// GetSupportedFileSystems returns supported file systems.
func (m *SystemMounter) GetSupportedFileSystems() []string {
	return m.supportedFileSystems
}

// detectFileSystem detects the file system type of a device.
func (m *SystemMounter) detectFileSystem(devicePath string) (string, error) {
	cmd := exec.Command("blkid", "-p", "-s", "TYPE", "-o", "value", devicePath)
	output, err := cmd.Output()
	if err != nil {
		return "", fmt.Errorf("failed to detect file system: %w", err)
	}

	fsType := strings.TrimSpace(string(output))
	if fsType == "" {
		return "", fmt.Errorf("unknown file system type")
	}

	return fsType, nil
}

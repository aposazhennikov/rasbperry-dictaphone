package main

import (
	"context"
	"fmt"
	"os"
	"os/signal"
	"syscall"

	"github.com/spf13/cobra"
	"raspberry-dictaphone-go/internal/config"
	"raspberry-dictaphone-go/internal/logger"
	"raspberry-dictaphone-go/internal/usb"
)

// USBMonitorService represents the USB monitoring service.
type USBMonitorService struct {
	config     *config.Config
	logger     *logger.Logger
	usbManager usb.Manager
	ctx        context.Context
	cancel     context.CancelFunc
}

// NewUSBMonitorService creates a new USB monitor service.
func NewUSBMonitorService(cfg *config.Config) (*USBMonitorService, error) {
	// Initialize logger.
	log, err := logger.New(cfg.Log.Level, cfg.Log.SentryDSN, cfg.Log.SentryEnabled)
	if err != nil {
		return nil, fmt.Errorf("failed to initialize logger: %w", err)
	}

	service := &USBMonitorService{
		config: cfg,
		logger: log,
	}

	// Set up context.
	service.ctx, service.cancel = context.WithCancel(context.Background())

	// Initialize USB manager.
	if err := service.initializeUSB(); err != nil {
		return nil, fmt.Errorf("failed to initialize USB manager: %w", err)
	}

	return service, nil
}

// initializeUSB initializes the USB monitoring system.
func (s *USBMonitorService) initializeUSB() error {
	s.logger.Info("Initializing USB monitoring system...")

	// Create USB manager.
	usbMgr, err := usb.NewUSBManager(s.logger, true) // Use udisks2.
	if err != nil {
		return fmt.Errorf("failed to create USB manager: %w", err)
	}

	// Initialize USB manager.
	if err := usbMgr.Initialize(); err != nil {
		return fmt.Errorf("failed to initialize USB manager: %w", err)
	}

	// Set auto-mount.
	usbMgr.SetAutoMount(s.config.USB.AutoMount)

	s.usbManager = usbMgr
	s.logger.Info("USB monitoring system initialized successfully")

	return nil
}

// Start starts the USB monitoring service.
func (s *USBMonitorService) Start() error {
	s.logger.Info("Starting USB monitoring service...")

	// Start USB monitoring.
	if err := s.usbManager.GetMonitor().Start(s.ctx); err != nil {
		return fmt.Errorf("failed to start USB monitor: %w", err)
	}

	// Start event processing.
	go s.processUSBEvents()

	s.logger.Info("USB monitoring service started successfully")
	return nil
}

// Stop stops the USB monitoring service.
func (s *USBMonitorService) Stop() error {
	s.logger.Info("Stopping USB monitoring service...")

	// Cancel context.
	if s.cancel != nil {
		s.cancel()
	}

	// Close USB manager.
	if s.usbManager != nil {
		if err := s.usbManager.Close(); err != nil {
			s.logger.Error("Failed to close USB manager: %v", err)
		}
	}

	// Close logger.
	if s.logger != nil {
		s.logger.Close()
	}

	return nil
}

// processUSBEvents processes USB device events.
func (s *USBMonitorService) processUSBEvents() {
	eventChan := s.usbManager.GetMonitor().GetEventChannel()

	for {
		select {
		case <-s.ctx.Done():
			return
		case event := <-eventChan:
			s.handleUSBEvent(event)
		}
	}
}

// handleUSBEvent handles a single USB device event.
func (s *USBMonitorService) handleUSBEvent(event usb.DeviceEvent) {
	eventTypeStr := usb.EventTypeToString(event.Type)
	s.logger.Info("USB Event: %s - Device: %s (%s)", 
		eventTypeStr, event.Device.Name, event.Device.DevicePath)

	switch event.Type {
	case usb.EventDeviceAdded:
		s.logger.Info("USB device connected: %s", event.Device.Name)
		
	case usb.EventDeviceRemoved:
		s.logger.Info("USB device disconnected: %s", event.Device.Name)
		
	case usb.EventDeviceMounted:
		s.logger.Info("USB device mounted: %s at %s", 
			event.Device.Name, event.Device.MountPoint)
		
	case usb.EventDeviceUnmounted:
		s.logger.Info("USB device unmounted: %s", event.Device.Name)
	}

	// Log device details.
	if s.config.App.Debug {
		s.logger.Debug("Device details: Path=%s, Size=%s, FileSystem=%s, State=%s",
			event.Device.DevicePath,
			usb.FormatSize(event.Device.Size),
			event.Device.FileSystem,
			usb.DeviceStateToString(event.Device.State),
		)
	}
}

// Run runs the USB monitoring service until interrupted.
func (s *USBMonitorService) Run() error {
	// Start the service.
	if err := s.Start(); err != nil {
		return fmt.Errorf("failed to start USB monitoring service: %w", err)
	}

	// Set up signal handling.
	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, syscall.SIGINT, syscall.SIGTERM)

	// Wait for shutdown signal.
	select {
	case sig := <-sigChan:
		s.logger.Info("Received signal %v, shutting down...", sig)
	case <-s.ctx.Done():
		s.logger.Info("Context cancelled, shutting down...")
	}

	// Stop the service.
	return s.Stop()
}

// CLI setup.

func main() {
	var configPath string

	rootCmd := &cobra.Command{
		Use:   "usb-monitor",
		Short: "USB Device Monitor Service",
		Long:  "A service that monitors USB storage devices and handles automatic mounting",
		RunE: func(cmd *cobra.Command, args []string) error {
			// Load configuration.
			cfg, err := config.Load(configPath)
			if err != nil {
				return fmt.Errorf("failed to load configuration: %w", err)
			}

			// Create and run service.
			service, err := NewUSBMonitorService(cfg)
			if err != nil {
				return fmt.Errorf("failed to create USB monitor service: %w", err)
			}

			return service.Run()
		},
	}

	// Add flags.
	rootCmd.PersistentFlags().StringVarP(&configPath, "config", "c", "", "Path to configuration file")

	// Add version command.
	versionCmd := &cobra.Command{
		Use:   "version",
		Short: "Show version information",
		Run: func(cmd *cobra.Command, args []string) {
			fmt.Println("USB Monitor Service v2.0")
			fmt.Println("Part of Raspberry Pi Dictaphone")
		},
	}
	rootCmd.AddCommand(versionCmd)

	// Add list command to show current devices.
	listCmd := &cobra.Command{
		Use:   "list",
		Short: "List connected USB devices",
		RunE: func(cmd *cobra.Command, args []string) error {
			// Load configuration.
			cfg, err := config.Load(configPath)
			if err != nil {
				return fmt.Errorf("failed to load configuration: %w", err)
			}

			// Initialize logger (console only).
			log, err := logger.New("info", "", false)
			if err != nil {
				return fmt.Errorf("failed to initialize logger: %w", err)
			}

			// Create USB manager.
			usbMgr, err := usb.NewUSBManager(log, true)
			if err != nil {
				return fmt.Errorf("failed to create USB manager: %w", err)
			}
			defer usbMgr.Close()

			if err := usbMgr.Initialize(); err != nil {
				return fmt.Errorf("failed to initialize USB manager: %w", err)
			}

			// Start monitor briefly to scan devices.
			ctx, cancel := context.WithCancel(context.Background())
			defer cancel()

			if err := usbMgr.GetMonitor().Start(ctx); err != nil {
				return fmt.Errorf("failed to start USB monitor: %w", err)
			}

			// Get devices.
			devices := usbMgr.GetMonitor().GetDevices()

			if len(devices) == 0 {
				fmt.Println("No USB storage devices found.")
				return nil
			}

			fmt.Printf("Found %d USB storage device(s):\n\n", len(devices))

			for i, device := range devices {
				fmt.Printf("%d. %s\n", i+1, device.Name)
				fmt.Printf("   Path: %s\n", device.DevicePath)
				fmt.Printf("   Size: %s\n", usb.FormatSize(device.Size))
				fmt.Printf("   File System: %s\n", device.FileSystem)
				fmt.Printf("   State: %s\n", usb.DeviceStateToString(device.State))
				if device.MountPoint != "" {
					fmt.Printf("   Mount Point: %s\n", device.MountPoint)
				}
				fmt.Printf("   Connected: %s\n", device.ConnectedAt.Format("2006-01-02 15:04:05"))
				if !device.MountedAt.IsZero() {
					fmt.Printf("   Mounted: %s\n", device.MountedAt.Format("2006-01-02 15:04:05"))
				}
				fmt.Println()
			}

			return nil
		},
	}
	rootCmd.AddCommand(listCmd)

	// Execute command.
	if err := rootCmd.Execute(); err != nil {
		fmt.Fprintf(os.Stderr, "Error: %v\n", err)
		os.Exit(1)
	}
}

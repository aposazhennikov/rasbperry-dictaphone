package main

import (
	"context"
	"fmt"
	"os"
	"os/signal"
	"path/filepath"
	"syscall"
	"time"

	"github.com/spf13/cobra"
	"raspberry-dictaphone-go/internal/audio"
	"raspberry-dictaphone-go/internal/config"
	"raspberry-dictaphone-go/internal/input"
	"raspberry-dictaphone-go/internal/logger"
	"raspberry-dictaphone-go/internal/menu"
	"raspberry-dictaphone-go/internal/tts"
	"raspberry-dictaphone-go/internal/usb"
)

// Application represents the main application.
type Application struct {
	config       *config.Config
	logger       *logger.Logger
	audioManager audio.Manager
	ttsManager   tts.Manager
	usbManager   usb.Manager
	inputHandler *input.Handler
	menuManager  menu.Manager
	menuBuilder  menu.Builder
	visualUI     *menu.VisualInterface

	ctx    context.Context
	cancel context.CancelFunc
}

// NewApplication creates a new application instance.
func NewApplication(cfg *config.Config) (*Application, error) {
	// Initialize logger.
	log, err := logger.New(cfg.Log.Level, cfg.Log.SentryDSN, cfg.Log.SentryEnabled)
	if err != nil {
		return nil, fmt.Errorf("failed to initialize logger: %w", err)
	}

	app := &Application{
		config: cfg,
		logger: log,
	}

	// Set up context.
	app.ctx, app.cancel = context.WithCancel(context.Background())

	// Initialize components.
	if err := app.initializeComponents(); err != nil {
		return nil, fmt.Errorf("failed to initialize components: %w", err)
	}

	return app, nil
}

// initializeComponents initializes all application components.
func (app *Application) initializeComponents() error {
	// Initialize audio manager.
	if err := app.initializeAudio(); err != nil {
		return fmt.Errorf("audio initialization failed: %w", err)
	}

	// Initialize TTS manager.
	if err := app.initializeTTS(); err != nil {
		return fmt.Errorf("TTS initialization failed: %w", err)
	}

	// Initialize USB manager.
	if err := app.initializeUSB(); err != nil {
		return fmt.Errorf("USB initialization failed: %w", err)
	}

	// Initialize input handler.
	if err := app.initializeInput(); err != nil {
		return fmt.Errorf("input initialization failed: %w", err)
	}

	// Initialize menu system.
	if err := app.initializeMenu(); err != nil {
		return fmt.Errorf("menu initialization failed: %w", err)
	}

	// Initialize visual interface.
	if err := app.initializeVisualInterface(); err != nil {
		return fmt.Errorf("visual interface initialization failed: %w", err)
	}

	return nil
}

// initializeAudio initializes the audio system.
func (app *Application) initializeAudio() error {
	app.logger.Info("Initializing audio system...")

	// Parse max duration.
	maxDuration, err := app.config.Audio.GetMaxDuration()
	if err != nil {
		return fmt.Errorf("invalid max duration: %w", err)
	}

	// Parse min free space.
	minFreeSpaceBytes, err := app.config.Audio.GetMinFreeSpaceBytes()
	if err != nil {
		return fmt.Errorf("invalid min free space: %w", err)
	}

	// Create audio manager.
	audioMgr, err := audio.NewAudioManager(
		app.config.Audio.RecordsDir,
		uint32(app.config.Audio.SampleRate),
		uint32(app.config.Audio.Channels),
		maxDuration,
		minFreeSpaceBytes,
	)
	if err != nil {
		return fmt.Errorf("failed to create audio manager: %w", err)
	}

	// Initialize audio manager.
	if err := audioMgr.Initialize(); err != nil {
		return fmt.Errorf("failed to initialize audio manager: %w", err)
	}

	app.audioManager = audioMgr
	app.logger.Info("Audio system initialized successfully")

	return nil
}

// initializeTTS initializes the TTS system.
func (app *Application) initializeTTS() error {
	app.logger.Info("Initializing TTS system...")

	// Create TTS manager.
	ttsMgr, err := tts.NewTTSManager(
		app.config.TTS.CacheDir,
		app.config.TTS.CredentialsPath,
		app.config.TTS.PrimaryEngine,
		app.config.TTS.FallbackEngine,
		app.config.TTS.Voice,
	)
	if err != nil {
		return fmt.Errorf("failed to create TTS manager: %w", err)
	}

	app.ttsManager = ttsMgr
	app.logger.Info("TTS system initialized successfully")

	return nil
}

// initializeUSB initializes the USB monitoring system.
func (app *Application) initializeUSB() error {
	app.logger.Info("Initializing USB system...")

	// Create USB manager.
	usbMgr, err := usb.NewUSBManager(app.logger, true) // Use udisks2.
	if err != nil {
		return fmt.Errorf("failed to create USB manager: %w", err)
	}

	// Initialize USB manager.
	if err := usbMgr.Initialize(); err != nil {
		return fmt.Errorf("failed to initialize USB manager: %w", err)
	}

	// Set auto-mount.
	usbMgr.SetAutoMount(app.config.USB.AutoMount)

	app.usbManager = usbMgr
	app.logger.Info("USB system initialized successfully")

	return nil
}

// initializeInput initializes the input handling system.
func (app *Application) initializeInput() error {
	app.logger.Info("Initializing input system...")

	// Create input handler.
	inputHandler := input.NewHandler(app.config.Input.DeviceName, app.logger)

	app.inputHandler = inputHandler
	app.logger.Info("Input system initialized successfully")

	return nil
}

// initializeMenu initializes the menu system.
func (app *Application) initializeMenu() error {
	app.logger.Info("Initializing menu system...")

	// Create menu manager.
	menuMgr := menu.NewBasicManager()

	// Create menu builder.
	menuBuilder := menu.NewDictaphoneBuilder(
		app.audioManager,
		app.ttsManager,
		app.usbManager,
		app.logger,
		app.config.Audio.RecordsDir,
	)

	// Build main menu.
	mainMenu := menuBuilder.BuildMainMenu()
	menuMgr.SetRootMenu(mainMenu)
	menuMgr.SetCurrentMenu(mainMenu)

	app.menuManager = menuMgr
	app.menuBuilder = menuBuilder
	app.logger.Info("Menu system initialized successfully")

	return nil
}

// initializeVisualInterface initializes the visual interface.
func (app *Application) initializeVisualInterface() error {
	if !app.config.Visual.Enabled {
		app.logger.Info("Visual interface disabled")
		return nil
	}

	app.logger.Info("Initializing visual interface...")

	// Parse refresh rate.
	refreshRate, err := app.config.Visual.GetRefreshRate()
	if err != nil {
		refreshRate = 100 * time.Millisecond
		app.logger.Warn("Invalid refresh rate, using default: %v", refreshRate)
	}

	// Create visual interface.
	visualUI := menu.NewVisualInterface(
		app.menuManager,
		app.menuBuilder,
		app.inputHandler,
		app.audioManager,
		app.ttsManager,
		app.usbManager,
		app.logger,
		app.config.Visual.Width,
		app.config.Visual.Height,
		refreshRate,
	)

	app.visualUI = visualUI
	app.logger.Info("Visual interface initialized successfully")

	return nil
}

// Start starts the application.
func (app *Application) Start() error {
	app.logger.Info("Starting Raspberry Pi Dictaphone v2.0...")

	// Start USB monitoring.
	if err := app.usbManager.GetMonitor().Start(app.ctx); err != nil {
		return fmt.Errorf("failed to start USB monitor: %w", err)
	}

	// Start input handler.
	if err := app.inputHandler.Start(app.ctx); err != nil {
		return fmt.Errorf("failed to start input handler: %w", err)
	}

	// Start visual interface.
	if app.visualUI != nil {
		if err := app.visualUI.Start(app.ctx); err != nil {
			return fmt.Errorf("failed to start visual interface: %w", err)
		}
	}

	// Announce startup.
	if app.ttsManager != nil {
		go func() {
			time.Sleep(1 * time.Second) // Give systems time to initialize.
			app.ttsManager.PlaySpeech(app.ctx, "Диктофон готов к работе")
		}()
	}

	app.logger.Info("Application started successfully")
	return nil
}

// Stop stops the application.
func (app *Application) Stop() error {
	app.logger.Info("Stopping application...")

	// Cancel context.
	if app.cancel != nil {
		app.cancel()
	}

	// Stop visual interface.
	if app.visualUI != nil {
		if err := app.visualUI.Stop(); err != nil {
			app.logger.Error("Failed to stop visual interface: %v", err)
		}
	}

	// Stop input handler.
	if app.inputHandler != nil {
		if err := app.inputHandler.Stop(); err != nil {
			app.logger.Error("Failed to stop input handler: %v", err)
		}
	}

	// Stop USB manager.
	if app.usbManager != nil {
		if err := app.usbManager.Close(); err != nil {
			app.logger.Error("Failed to close USB manager: %v", err)
		}
	}

	// Close TTS manager.
	if app.ttsManager != nil {
		if err := app.ttsManager.Close(); err != nil {
			app.logger.Error("Failed to close TTS manager: %v", err)
		}
	}

	// Close audio manager.
	if app.audioManager != nil {
		if err := app.audioManager.Close(); err != nil {
			app.logger.Error("Failed to close audio manager: %v", err)
		}
	}

	// Close logger.
	if app.logger != nil {
		app.logger.Close()
	}

	return nil
}

// Run runs the application until interrupted.
func (app *Application) Run() error {
	// Start the application.
	if err := app.Start(); err != nil {
		return fmt.Errorf("failed to start application: %w", err)
	}

	// Set up signal handling.
	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, syscall.SIGINT, syscall.SIGTERM)

	// Wait for shutdown signal.
	select {
	case sig := <-sigChan:
		app.logger.Info("Received signal %v, shutting down...", sig)
	case <-app.ctx.Done():
		app.logger.Info("Context cancelled, shutting down...")
	}

	// Stop the application.
	return app.Stop()
}

// CLI setup.

func main() {
	var configPath string

	rootCmd := &cobra.Command{
		Use:   "dictaphone",
		Short: "Raspberry Pi Dictaphone v2.0",
		Long:  "A voice-controlled dictaphone for visually impaired users running on Raspberry Pi",
		RunE: func(cmd *cobra.Command, args []string) error {
			// Load configuration.
			cfg, err := config.Load(configPath)
			if err != nil {
				return fmt.Errorf("failed to load configuration: %w", err)
			}

			// Create and run application.
			app, err := NewApplication(cfg)
			if err != nil {
				return fmt.Errorf("failed to create application: %w", err)
			}

			return app.Run()
		},
	}

	// Add flags.
	rootCmd.PersistentFlags().StringVarP(&configPath, "config", "c", "", "Path to configuration file")

	// Add version command.
	versionCmd := &cobra.Command{
		Use:   "version",
		Short: "Show version information",
		Run: func(cmd *cobra.Command, args []string) {
			fmt.Println("Raspberry Pi Dictaphone v2.0")
			fmt.Println("Built with Go")
		},
	}
	rootCmd.AddCommand(versionCmd)

	// Add pre-generate command for TTS.
	pregenCmd := &cobra.Command{
		Use:   "pregenerate",
		Short: "Pre-generate TTS cache",
		Long:  "Pre-generate speech for all menu items to improve performance",
		RunE: func(cmd *cobra.Command, args []string) error {
			// Load configuration.
			cfg, err := config.Load(configPath)
			if err != nil {
				return fmt.Errorf("failed to load configuration: %w", err)
			}

			// Initialize minimal components for TTS.
			log, err := logger.New(cfg.Log.Level, "", false) // Disable Sentry for pregeneration.
			if err != nil {
				return fmt.Errorf("failed to initialize logger: %w", err)
			}

			ttsMgr, err := tts.NewTTSManager(
				cfg.TTS.CacheDir,
				cfg.TTS.CredentialsPath,
				cfg.TTS.PrimaryEngine,
				cfg.TTS.FallbackEngine,
				cfg.TTS.Voice,
			)
			if err != nil {
				return fmt.Errorf("failed to create TTS manager: %w", err)
			}
			defer ttsMgr.Close()

			// Pre-generate common phrases.
			phrases := []string{
				"Диктофон готов к работе",
				"Главное меню",
				"Запись",
				"Воспроизведение",
				"Настройки",
				"USB устройства",
				"Радиостанции",
				"Система",
				"Назад",
				"Заметки",
				"Идеи",
				"Важное",
				"Работа",
				"Личное",
				"Начинаю запись",
				"Запись остановлена",
				"Воспроизведение начато",
				"Воспроизведение остановлено",
			}

			log.Info("Pre-generating TTS cache for %d phrases...", len(phrases))

			ctx := context.Background()
			if err := ttsMgr.PreGenerateTexts(ctx, phrases); err != nil {
				return fmt.Errorf("failed to pre-generate TTS: %w", err)
			}

			log.Info("TTS pre-generation completed successfully")
			return nil
		},
	}
	rootCmd.AddCommand(pregenCmd)

	// Execute command.
	if err := rootCmd.Execute(); err != nil {
		fmt.Fprintf(os.Stderr, "Error: %v\n", err)
		os.Exit(1)
	}
}

// Helper function to get the executable directory.
func getExecutableDir() string {
	ex, err := os.Executable()
	if err != nil {
		return "."
	}
	return filepath.Dir(ex)
}

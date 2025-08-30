package config

import (
	"fmt"
	"os"
	"path/filepath"
	"time"

	"github.com/spf13/viper"
)

// Config represents the application configuration.
type Config struct {
	App    AppConfig    `mapstructure:"app"`
	Audio  AudioConfig  `mapstructure:"audio"`
	TTS    TTSConfig    `mapstructure:"tts"`
	Input  InputConfig  `mapstructure:"input"`
	USB    USBConfig    `mapstructure:"usb"`
	Log    LogConfig    `mapstructure:"logging"`
	Visual VisualConfig `mapstructure:"visual_interface"`
}

// AppConfig contains application-level configuration.
type AppConfig struct {
	Name    string `mapstructure:"name"`
	Version string `mapstructure:"version"`
	Debug   bool   `mapstructure:"debug"`
}

// AudioConfig contains audio-related configuration.
type AudioConfig struct {
	SampleRate    int    `mapstructure:"sample_rate"`
	Channels      int    `mapstructure:"channels"`
	MaxDuration   string `mapstructure:"max_duration"`
	MinFreeSpace  string `mapstructure:"min_free_space"`
	RecordsDir    string `mapstructure:"records_dir"`
}

// TTSConfig contains text-to-speech configuration.
type TTSConfig struct {
	PrimaryEngine   string `mapstructure:"primary_engine"`
	FallbackEngine  string `mapstructure:"fallback_engine"`
	CacheDir        string `mapstructure:"cache_dir"`
	Voice           string `mapstructure:"voice"`
	Language        string `mapstructure:"language"`
	CredentialsPath string `mapstructure:"credentials_path"`
}

// InputConfig contains input handling configuration.
type InputConfig struct {
	DeviceName string `mapstructure:"device_name"`
}

// USBConfig contains USB monitoring configuration.
type USBConfig struct {
	MonitorEnabled bool `mapstructure:"monitor_enabled"`
	AutoMount      bool `mapstructure:"auto_mount"`
}

// LogConfig contains logging configuration.
type LogConfig struct {
	Level         string `mapstructure:"level"`
	SentryDSN     string `mapstructure:"sentry_dsn"`
	SentryEnabled bool   `mapstructure:"sentry_enabled"`
}

// VisualConfig contains visual interface configuration.
type VisualConfig struct {
	Enabled     bool   `mapstructure:"enabled"`
	Width       int    `mapstructure:"width"`
	Height      int    `mapstructure:"height"`
	RefreshRate string `mapstructure:"refresh_rate"`
}

// Load loads configuration from file and environment variables.
func Load(configPath string) (*Config, error) {
	v := viper.New()

	// Set defaults.
	setDefaults(v)

	// Set config file path.
	if configPath != "" {
		v.SetConfigFile(configPath)
	} else {
		// Look for config in working directory and /etc.
		v.SetConfigName("config")
		v.SetConfigType("yaml")
		v.AddConfigPath(".")
		v.AddConfigPath("./configs")
		v.AddConfigPath("/etc/dictaphone/")
		v.AddConfigPath("/opt/dictaphone/")
	}

	// Enable environment variables.
	v.AutomaticEnv()
	v.SetEnvPrefix("DICTAPHONE")

	// Read config file.
	if err := v.ReadInConfig(); err != nil {
		if _, ok := err.(viper.ConfigFileNotFoundError); ok {
			// Config file not found, use defaults.
			fmt.Printf("Config file not found, using defaults\n")
		} else {
			return nil, fmt.Errorf("error reading config file: %w", err)
		}
	}

	var cfg Config
	if err := v.Unmarshal(&cfg); err != nil {
		return nil, fmt.Errorf("error unmarshaling config: %w", err)
	}

	// Expand paths.
	cfg.Audio.RecordsDir = expandPath(cfg.Audio.RecordsDir)
	cfg.TTS.CacheDir = expandPath(cfg.TTS.CacheDir)
	if cfg.TTS.CredentialsPath != "" {
		cfg.TTS.CredentialsPath = expandPath(cfg.TTS.CredentialsPath)
	}

	return &cfg, nil
}

// setDefaults sets default configuration values.
func setDefaults(v *viper.Viper) {
	v.SetDefault("app.name", "Raspberry Pi Dictaphone")
	v.SetDefault("app.version", "2.0.0")
	v.SetDefault("app.debug", false)

	v.SetDefault("audio.sample_rate", 44100)
	v.SetDefault("audio.channels", 1)
	v.SetDefault("audio.max_duration", "3h")
	v.SetDefault("audio.min_free_space", "1GB")
	v.SetDefault("audio.records_dir", "/home/aleks/records")

	v.SetDefault("tts.primary_engine", "google_cloud")
	v.SetDefault("tts.fallback_engine", "gtts")
	v.SetDefault("tts.cache_dir", "/home/aleks/cache_tts")
	v.SetDefault("tts.voice", "ru-RU-Standard-A")
	v.SetDefault("tts.language", "ru")

	v.SetDefault("input.device_name", "HAOBO Technology USB Composite Device Keyboard")

	v.SetDefault("usb.monitor_enabled", true)
	v.SetDefault("usb.auto_mount", true)

	v.SetDefault("logging.level", "info")
	v.SetDefault("logging.sentry_enabled", false)

	v.SetDefault("visual_interface.enabled", true)
	v.SetDefault("visual_interface.width", 80)
	v.SetDefault("visual_interface.height", 24)
	v.SetDefault("visual_interface.refresh_rate", "100ms")
}

// expandPath expands ~ to home directory.
func expandPath(path string) string {
	if path == "" {
		return path
	}

	if path[0] == '~' {
		home, err := os.UserHomeDir()
		if err != nil {
			return path
		}
		return filepath.Join(home, path[1:])
	}

	return path
}

// GetMaxDuration parses max duration string to time.Duration.
func (c *AudioConfig) GetMaxDuration() (time.Duration, error) {
	return time.ParseDuration(c.MaxDuration)
}

// GetMinFreeSpaceBytes parses min free space string to bytes.
func (c *AudioConfig) GetMinFreeSpaceBytes() (int64, error) {
	switch c.MinFreeSpace {
	case "1GB":
		return 1 * 1024 * 1024 * 1024, nil
	case "500MB":
		return 500 * 1024 * 1024, nil
	case "100MB":
		return 100 * 1024 * 1024, nil
	default:
		return 0, fmt.Errorf("unsupported free space format: %s", c.MinFreeSpace)
	}
}

// GetRefreshRate parses refresh rate string to time.Duration.
func (c *VisualConfig) GetRefreshRate() (time.Duration, error) {
	return time.ParseDuration(c.RefreshRate)
}

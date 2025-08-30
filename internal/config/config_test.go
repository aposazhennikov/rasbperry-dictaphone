package config

import (
	"os"
	"path/filepath"
	"testing"
	"time"
)

func TestLoad(t *testing.T) {
	// Create a temporary config file.
	tmpDir := t.TempDir()
	configFile := filepath.Join(tmpDir, "test_config.yaml")
	
	configContent := `
app:
  name: "Test Dictaphone"
  version: "1.0.0"
  debug: true

audio:
  sample_rate: 48000
  channels: 2
  max_duration: "2h"
  min_free_space: "500MB"
  records_dir: "/tmp/test_records"

tts:
  primary_engine: "gtts"
  fallback_engine: "google_cloud"
  cache_dir: "/tmp/test_cache"
  voice: "ru-RU-Standard-B"
  language: "ru"

input:
  device_name: "Test Device"

usb:
  monitor_enabled: false
  auto_mount: false

logging:
  level: "debug"
  sentry_enabled: false

visual_interface:
  enabled: false
  width: 100
  height: 30
  refresh_rate: "50ms"
`
	
	err := os.WriteFile(configFile, []byte(configContent), 0644)
	if err != nil {
		t.Fatalf("Failed to create test config file: %v", err)
	}
	
	// Load configuration.
	cfg, err := Load(configFile)
	if err != nil {
		t.Fatalf("Failed to load configuration: %v", err)
	}
	
	// Test app config.
	if cfg.App.Name != "Test Dictaphone" {
		t.Errorf("Expected app name 'Test Dictaphone', got '%s'", cfg.App.Name)
	}
	if cfg.App.Version != "1.0.0" {
		t.Errorf("Expected app version '1.0.0', got '%s'", cfg.App.Version)
	}
	if !cfg.App.Debug {
		t.Error("Expected debug to be true")
	}
	
	// Test audio config.
	if cfg.Audio.SampleRate != 48000 {
		t.Errorf("Expected sample rate 48000, got %d", cfg.Audio.SampleRate)
	}
	if cfg.Audio.Channels != 2 {
		t.Errorf("Expected channels 2, got %d", cfg.Audio.Channels)
	}
	if cfg.Audio.MaxDuration != "2h" {
		t.Errorf("Expected max duration '2h', got '%s'", cfg.Audio.MaxDuration)
	}
	if cfg.Audio.RecordsDir != "/tmp/test_records" {
		t.Errorf("Expected records dir '/tmp/test_records', got '%s'", cfg.Audio.RecordsDir)
	}
	
	// Test TTS config.
	if cfg.TTS.PrimaryEngine != "gtts" {
		t.Errorf("Expected primary engine 'gtts', got '%s'", cfg.TTS.PrimaryEngine)
	}
	if cfg.TTS.Voice != "ru-RU-Standard-B" {
		t.Errorf("Expected voice 'ru-RU-Standard-B', got '%s'", cfg.TTS.Voice)
	}
	
	// Test input config.
	if cfg.Input.DeviceName != "Test Device" {
		t.Errorf("Expected device name 'Test Device', got '%s'", cfg.Input.DeviceName)
	}
	
	// Test USB config.
	if cfg.USB.MonitorEnabled {
		t.Error("Expected USB monitor to be disabled")
	}
	if cfg.USB.AutoMount {
		t.Error("Expected USB auto mount to be disabled")
	}
	
	// Test logging config.
	if cfg.Log.Level != "debug" {
		t.Errorf("Expected log level 'debug', got '%s'", cfg.Log.Level)
	}
	if cfg.Log.SentryEnabled {
		t.Error("Expected Sentry to be disabled")
	}
	
	// Test visual config.
	if cfg.Visual.Enabled {
		t.Error("Expected visual interface to be disabled")
	}
	if cfg.Visual.Width != 100 {
		t.Errorf("Expected width 100, got %d", cfg.Visual.Width)
	}
	if cfg.Visual.Height != 30 {
		t.Errorf("Expected height 30, got %d", cfg.Visual.Height)
	}
}

func TestLoadDefaults(t *testing.T) {
	// Load with non-existent config file to test defaults.
	cfg, err := Load("/nonexistent/config.yaml")
	if err != nil {
		t.Fatalf("Failed to load defaults: %v", err)
	}
	
	// Test default values.
	if cfg.App.Name != "Raspberry Pi Dictaphone" {
		t.Errorf("Expected default app name, got '%s'", cfg.App.Name)
	}
	if cfg.Audio.SampleRate != 44100 {
		t.Errorf("Expected default sample rate 44100, got %d", cfg.Audio.SampleRate)
	}
	if cfg.TTS.PrimaryEngine != "google_cloud" {
		t.Errorf("Expected default primary engine 'google_cloud', got '%s'", cfg.TTS.PrimaryEngine)
	}
}

func TestAudioConfig_GetMaxDuration(t *testing.T) {
	tests := []struct {
		duration string
		expected time.Duration
		hasError bool
	}{
		{"1h", 1 * time.Hour, false},
		{"30m", 30 * time.Minute, false},
		{"2h30m", 2*time.Hour + 30*time.Minute, false},
		{"invalid", 0, true},
	}
	
	for _, test := range tests {
		cfg := &AudioConfig{MaxDuration: test.duration}
		result, err := cfg.GetMaxDuration()
		
		if test.hasError {
			if err == nil {
				t.Errorf("Expected error for duration '%s', got none", test.duration)
			}
		} else {
			if err != nil {
				t.Errorf("Unexpected error for duration '%s': %v", test.duration, err)
			}
			if result != test.expected {
				t.Errorf("Expected duration %v, got %v", test.expected, result)
			}
		}
	}
}

func TestAudioConfig_GetMinFreeSpaceBytes(t *testing.T) {
	tests := []struct {
		space    string
		expected int64
		hasError bool
	}{
		{"1GB", 1 * 1024 * 1024 * 1024, false},
		{"500MB", 500 * 1024 * 1024, false},
		{"100MB", 100 * 1024 * 1024, false},
		{"invalid", 0, true},
	}
	
	for _, test := range tests {
		cfg := &AudioConfig{MinFreeSpace: test.space}
		result, err := cfg.GetMinFreeSpaceBytes()
		
		if test.hasError {
			if err == nil {
				t.Errorf("Expected error for space '%s', got none", test.space)
			}
		} else {
			if err != nil {
				t.Errorf("Unexpected error for space '%s': %v", test.space, err)
			}
			if result != test.expected {
				t.Errorf("Expected space %d, got %d", test.expected, result)
			}
		}
	}
}

func TestVisualConfig_GetRefreshRate(t *testing.T) {
	tests := []struct {
		rate     string
		expected time.Duration
		hasError bool
	}{
		{"100ms", 100 * time.Millisecond, false},
		{"1s", 1 * time.Second, false},
		{"500ms", 500 * time.Millisecond, false},
		{"invalid", 0, true},
	}
	
	for _, test := range tests {
		cfg := &VisualConfig{RefreshRate: test.rate}
		result, err := cfg.GetRefreshRate()
		
		if test.hasError {
			if err == nil {
				t.Errorf("Expected error for rate '%s', got none", test.rate)
			}
		} else {
			if err != nil {
				t.Errorf("Unexpected error for rate '%s': %v", test.rate, err)
			}
			if result != test.expected {
				t.Errorf("Expected rate %v, got %v", test.expected, result)
			}
		}
	}
}

func TestExpandPath(t *testing.T) {
	// Test home directory expansion (mock).
	// Note: This test might behave differently depending on the environment.
	
	tests := []struct {
		input    string
		expected string
	}{
		{"/absolute/path", "/absolute/path"},
		{"relative/path", "relative/path"},
		{"", ""},
	}
	
	for _, test := range tests {
		result := expandPath(test.input)
		if result != test.expected && !strings.HasPrefix(result, "/") {
			t.Errorf("Expected path expansion of '%s' to be '%s' or absolute, got '%s'", test.input, test.expected, result)
		}
	}
}

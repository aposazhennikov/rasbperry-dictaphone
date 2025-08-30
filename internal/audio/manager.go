package audio

import (
	"fmt"
	"os/exec"
	"strconv"
	"strings"
	"time"
)

// AudioManager implements the Manager interface.
type AudioManager struct {
	recorder Recorder
	player   Player
}

// NewAudioManager creates a new AudioManager instance.
func NewAudioManager(recordsDir string, sampleRate, channels uint32, maxDuration time.Duration, minFreeSpaceBytes int64) (*AudioManager, error) {
	// Create recorder.
	recorder, err := NewMalgoRecorder(recordsDir, sampleRate, channels, maxDuration, minFreeSpaceBytes)
	if err != nil {
		return nil, fmt.Errorf("failed to create recorder: %w", err)
	}

	// Create player.
	player := NewSystemPlayer()

	return &AudioManager{
		recorder: recorder,
		player:   player,
	}, nil
}

// GetRecorder returns the audio recorder instance.
func (m *AudioManager) GetRecorder() Recorder {
	return m.recorder
}

// GetPlayer returns the audio player instance.
func (m *AudioManager) GetPlayer() Player {
	return m.player
}

// Initialize initializes the audio manager.
func (m *AudioManager) Initialize() error {
	// Check if required audio utilities are available.
	if err := m.checkAudioUtilities(); err != nil {
		return fmt.Errorf("audio utilities check failed: %w", err)
	}

	return nil
}

// Close closes the audio manager and releases resources.
func (m *AudioManager) Close() error {
	var errors []string

	// Close recorder.
	if recorder, ok := m.recorder.(*MalgoRecorder); ok {
		if err := recorder.Close(); err != nil {
			errors = append(errors, fmt.Sprintf("recorder close error: %v", err))
		}
	}

	// Stop player.
	if err := m.player.Stop(); err != nil {
		errors = append(errors, fmt.Sprintf("player stop error: %v", err))
	}

	if len(errors) > 0 {
		return fmt.Errorf("errors during close: %s", strings.Join(errors, "; "))
	}

	return nil
}

// GetSystemVolume returns the current system volume.
func (m *AudioManager) GetSystemVolume() (int, error) {
	cmd := exec.Command("amixer", "get", "Master")
	output, err := cmd.Output()
	if err != nil {
		return 0, fmt.Errorf("failed to get system volume: %w", err)
	}

	// Parse output to extract volume percentage.
	lines := strings.Split(string(output), "\n")
	for _, line := range lines {
		if strings.Contains(line, "[") && strings.Contains(line, "%]") {
			// Find percentage value.
			start := strings.Index(line, "[") + 1
			end := strings.Index(line, "%]")
			if start < end {
				volumeStr := line[start:end]
				volume, err := strconv.Atoi(volumeStr)
				if err != nil {
					continue
				}
				return volume, nil
			}
		}
	}

	return 0, fmt.Errorf("failed to parse volume from amixer output")
}

// SetSystemVolume sets the system volume (0-100).
func (m *AudioManager) SetSystemVolume(volume int) error {
	if volume < 0 || volume > 100 {
		return fmt.Errorf("invalid volume: %d (must be 0-100)", volume)
	}

	cmd := exec.Command("amixer", "sset", "Master", fmt.Sprintf("%d%%", volume))
	if err := cmd.Run(); err != nil {
		return fmt.Errorf("failed to set system volume: %w", err)
	}

	return nil
}

// checkAudioUtilities checks if required audio utilities are available.
func (m *AudioManager) checkAudioUtilities() error {
	utilities := []string{"aplay", "amixer", "mpg123", "sox"}
	optional := []string{"vlc", "ffprobe", "soxi"}

	// Check required utilities.
	for _, util := range utilities {
		if err := exec.Command("which", util).Run(); err != nil {
			return fmt.Errorf("required utility not found: %s", util)
		}
	}

	// Check optional utilities (warn if missing).
	for _, util := range optional {
		if err := exec.Command("which", util).Run(); err != nil {
			fmt.Printf("Warning: optional utility not found: %s\n", util)
		}
	}

	return nil
}

// GetRecordingDevices returns available recording devices.
func (m *AudioManager) GetRecordingDevices() ([]AudioDevice, error) {
	return m.recorder.GetAvailableDevices()
}

// SetRecordingDevice sets the recording device.
func (m *AudioManager) SetRecordingDevice(deviceID int) error {
	return m.recorder.SetDevice(deviceID)
}

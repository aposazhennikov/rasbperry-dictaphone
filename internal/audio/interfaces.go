package audio

import (
	"context"
	"time"
)

// RecordingState represents the current state of audio recording.
type RecordingState int

const (
	// StateStopped indicates recording is stopped.
	StateStopped RecordingState = iota
	// StateRecording indicates recording is active.
	StateRecording
	// StatePaused indicates recording is paused.
	StatePaused
)

// PlaybackState represents the current state of audio playback.
type PlaybackState int

const (
	// PlaybackStopped indicates playback is stopped.
	PlaybackStopped PlaybackState = iota
	// PlaybackPlaying indicates playback is active.
	PlaybackPlaying
	// PlaybackPaused indicates playback is paused.
	PlaybackPaused
)

// AudioDevice represents an audio input/output device.
type AudioDevice struct {
	ID          int    `json:"id"`
	Name        string `json:"name"`
	IsDefault   bool   `json:"is_default"`
	MaxChannels int    `json:"max_channels"`
	SampleRate  int    `json:"sample_rate"`
}

// RecordingInfo contains information about current recording.
type RecordingInfo struct {
	State     RecordingState `json:"state"`
	Duration  time.Duration  `json:"duration"`
	Folder    string         `json:"folder"`
	Filename  string         `json:"filename"`
	StartTime time.Time      `json:"start_time"`
}

// PlaybackInfo contains information about current playback.
type PlaybackInfo struct {
	State    PlaybackState `json:"state"`
	Duration time.Duration `json:"duration"`
	Position time.Duration `json:"position"`
	Filename string        `json:"filename"`
	Volume   int           `json:"volume"`
	Speed    float64       `json:"speed"`
}

// Recorder defines the interface for audio recording functionality.
type Recorder interface {
	// StartRecording starts recording audio to the specified folder.
	StartRecording(ctx context.Context, folder string) error

	// PauseRecording pauses the current recording.
	PauseRecording() error

	// ResumeRecording resumes the paused recording.
	ResumeRecording() error

	// StopRecording stops recording and returns the filename of the recorded file.
	StopRecording() (string, error)

	// GetRecordingInfo returns current recording information.
	GetRecordingInfo() RecordingInfo

	// GetAvailableDevices returns list of available recording devices.
	GetAvailableDevices() ([]AudioDevice, error)

	// SetDevice sets the recording device by ID.
	SetDevice(deviceID int) error

	// CheckDiskSpace checks if there's enough free disk space for recording.
	CheckDiskSpace() (bool, int64, error)
}

// Player defines the interface for audio playback functionality.
type Player interface {
	// Play starts playing the specified audio file.
	Play(ctx context.Context, filePath string) error

	// Pause pauses the current playback.
	Pause() error

	// Resume resumes the paused playback.
	Resume() error

	// Stop stops the current playback.
	Stop() error

	// Seek seeks to the specified position in the audio file.
	Seek(position time.Duration) error

	// SetVolume sets the playback volume (0-100).
	SetVolume(volume int) error

	// SetSpeed sets the playback speed (0.5-2.0).
	SetSpeed(speed float64) error

	// GetPlaybackInfo returns current playback information.
	GetPlaybackInfo() PlaybackInfo

	// GetDuration returns the total duration of the current audio file.
	GetDuration() (time.Duration, error)
}

// Manager defines the interface for managing audio operations.
type Manager interface {
	// GetRecorder returns the audio recorder instance.
	GetRecorder() Recorder

	// GetPlayer returns the audio player instance.
	GetPlayer() Player

	// Initialize initializes the audio manager.
	Initialize() error

	// Close closes the audio manager and releases resources.
	Close() error

	// GetSystemVolume returns the current system volume.
	GetSystemVolume() (int, error)

	// SetSystemVolume sets the system volume (0-100).
	SetSystemVolume(volume int) error
}

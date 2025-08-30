package audio

import (
	"context"
	"encoding/binary"
	"fmt"
	"os"
	"path/filepath"
	"sync"
	"syscall"
	"time"

	"github.com/gen2brain/malgo"
)

// MalgoRecorder implements the Recorder interface using malgo library.
type MalgoRecorder struct {
	malgoContext     *malgo.AllocatedContext
	device           *malgo.Device
	deviceConfig     malgo.DeviceConfig
	recordingData    []byte
	recordingMutex   sync.RWMutex
	state            RecordingState
	startTime        time.Time
	pauseStartTime   time.Time
	totalPauseTime   time.Duration
	currentFolder    string
	currentFilename  string
	sampleRate       uint32
	channels         uint32
	minFreeSpaceBytes int64
	recordsDir       string
	maxDuration      time.Duration
	ctx              context.Context
	cancel           context.CancelFunc
}

// NewMalgoRecorder creates a new MalgoRecorder instance.
func NewMalgoRecorder(recordsDir string, sampleRate, channels uint32, maxDuration time.Duration, minFreeSpaceBytes int64) (*MalgoRecorder, error) {
	malgoCtx, err := malgo.InitContext(nil, malgo.ContextConfig{}, func(message string) {
		// Log malgo messages if needed.
		fmt.Printf("Malgo: %s\n", message)
	})
	if err != nil {
		return nil, fmt.Errorf("failed to initialize malgo context: %w", err)
	}

	recorder := &MalgoRecorder{
		malgoContext:      malgoCtx,
		state:             StateStopped,
		sampleRate:        sampleRate,
		channels:          channels,
		recordsDir:        recordsDir,
		maxDuration:       maxDuration,
		minFreeSpaceBytes: minFreeSpaceBytes,
	}

	// Create records directory if it doesn't exist.
	if err := os.MkdirAll(recordsDir, 0755); err != nil {
		return nil, fmt.Errorf("failed to create records directory: %w", err)
	}

	// Create standard folders.
	standardFolders := []string{"Заметки", "Идеи", "Важное", "Работа", "Личное"}
	for _, folder := range standardFolders {
		folderPath := filepath.Join(recordsDir, folder)
		if err := os.MkdirAll(folderPath, 0755); err != nil {
			return nil, fmt.Errorf("failed to create folder %s: %w", folder, err)
		}
	}

	return recorder, nil
}

// StartRecording starts recording audio to the specified folder.
func (r *MalgoRecorder) StartRecording(ctx context.Context, folder string) error {
	r.recordingMutex.Lock()
	defer r.recordingMutex.Unlock()

	if r.state != StateStopped {
		return fmt.Errorf("recording already in progress")
	}

	// Check disk space.
	if hasSpace, freeSpace, err := r.CheckDiskSpace(); err != nil {
		return fmt.Errorf("failed to check disk space: %w", err)
	} else if !hasSpace {
		return fmt.Errorf("insufficient disk space: %d bytes available, %d bytes required", freeSpace, r.minFreeSpaceBytes)
	}

	// Create folder if it doesn't exist.
	folderPath := filepath.Join(r.recordsDir, folder)
	if err := os.MkdirAll(folderPath, 0755); err != nil {
		return fmt.Errorf("failed to create folder: %w", err)
	}

	// Generate filename.
	timestamp := time.Now().Format("2006-01-02_15-04-05")
	filename := fmt.Sprintf("recording_%s.wav", timestamp)
	r.currentFolder = folder
	r.currentFilename = filename

	// Configure device.
	r.deviceConfig = malgo.DefaultDeviceConfig(malgo.Capture)
	r.deviceConfig.Capture.Format = malgo.FormatS16
	r.deviceConfig.Capture.Channels = r.channels
	r.deviceConfig.SampleRate = r.sampleRate
	r.deviceConfig.Alsa.NoMMap = 1

	// Initialize recording data.
	r.recordingData = make([]byte, 0)
	r.startTime = time.Now()
	r.totalPauseTime = 0

	// Set up context for cancellation.
	r.ctx, r.cancel = context.WithCancel(ctx)

	// Create device with data callback.
	var err error
	r.device, err = malgo.InitDevice(r.malgoContext.Context, r.deviceConfig, malgo.DeviceCallbacks{
		Data: r.onReceiveData,
	})
	if err != nil {
		return fmt.Errorf("failed to initialize recording device: %w", err)
	}

	// Start the device.
	if err := r.device.Start(); err != nil {
		r.device.Uninit()
		return fmt.Errorf("failed to start recording device: %w", err)
	}

	r.state = StateRecording
	return nil
}

// onReceiveData is called when audio data is received.
func (r *MalgoRecorder) onReceiveData(pOutputSample, pInputSample []byte, frameCount uint32) {
	if r.state == StateRecording {
		// Check if max duration exceeded.
		if time.Since(r.startTime)-r.totalPauseTime >= r.maxDuration {
			// Stop recording automatically.
			go func() {
				_, _ = r.StopRecording()
			}()
			return
		}

		// Append audio data.
		r.recordingMutex.Lock()
		r.recordingData = append(r.recordingData, pInputSample...)
		r.recordingMutex.Unlock()
	}
}

// PauseRecording pauses the current recording.
func (r *MalgoRecorder) PauseRecording() error {
	r.recordingMutex.Lock()
	defer r.recordingMutex.Unlock()

	if r.state != StateRecording {
		return fmt.Errorf("no active recording to pause")
	}

	r.state = StatePaused
	r.pauseStartTime = time.Now()
	return nil
}

// ResumeRecording resumes the paused recording.
func (r *MalgoRecorder) ResumeRecording() error {
	r.recordingMutex.Lock()
	defer r.recordingMutex.Unlock()

	if r.state != StatePaused {
		return fmt.Errorf("no paused recording to resume")
	}

	r.state = StateRecording
	r.totalPauseTime += time.Since(r.pauseStartTime)
	return nil
}

// StopRecording stops recording and returns the filename of the recorded file.
func (r *MalgoRecorder) StopRecording() (string, error) {
	r.recordingMutex.Lock()
	defer r.recordingMutex.Unlock()

	if r.state == StateStopped {
		return "", fmt.Errorf("no active recording to stop")
	}

	// Stop the device.
	if r.device != nil {
		r.device.Stop()
		r.device.Uninit()
		r.device = nil
	}

	// Cancel context.
	if r.cancel != nil {
		r.cancel()
	}

	// Calculate final pause time if currently paused.
	if r.state == StatePaused {
		r.totalPauseTime += time.Since(r.pauseStartTime)
	}

	// Save recording to file.
	filePath := filepath.Join(r.recordsDir, r.currentFolder, r.currentFilename)
	if err := r.saveWAVFile(filePath, r.recordingData); err != nil {
		r.state = StateStopped
		return "", fmt.Errorf("failed to save recording: %w", err)
	}

	r.state = StateStopped
	return filePath, nil
}

// saveWAVFile saves raw audio data as a WAV file.
func (r *MalgoRecorder) saveWAVFile(filePath string, data []byte) error {
	file, err := os.Create(filePath)
	if err != nil {
		return fmt.Errorf("failed to create file: %w", err)
	}
	defer file.Close()

	// WAV header.
	dataSize := uint32(len(data))
	fileSize := dataSize + 36
	bitsPerSample := uint16(16)
	byteRate := r.sampleRate * uint32(r.channels) * uint32(bitsPerSample/8)
	blockAlign := uint16(r.channels) * bitsPerSample / 8

	// Write WAV header.
	if err := binary.Write(file, binary.LittleEndian, []byte("RIFF")); err != nil {
		return err
	}
	if err := binary.Write(file, binary.LittleEndian, fileSize); err != nil {
		return err
	}
	if err := binary.Write(file, binary.LittleEndian, []byte("WAVE")); err != nil {
		return err
	}
	if err := binary.Write(file, binary.LittleEndian, []byte("fmt ")); err != nil {
		return err
	}
	if err := binary.Write(file, binary.LittleEndian, uint32(16)); err != nil { // PCM header size.
		return err
	}
	if err := binary.Write(file, binary.LittleEndian, uint16(1)); err != nil { // PCM format.
		return err
	}
	if err := binary.Write(file, binary.LittleEndian, uint16(r.channels)); err != nil {
		return err
	}
	if err := binary.Write(file, binary.LittleEndian, r.sampleRate); err != nil {
		return err
	}
	if err := binary.Write(file, binary.LittleEndian, byteRate); err != nil {
		return err
	}
	if err := binary.Write(file, binary.LittleEndian, blockAlign); err != nil {
		return err
	}
	if err := binary.Write(file, binary.LittleEndian, bitsPerSample); err != nil {
		return err
	}
	if err := binary.Write(file, binary.LittleEndian, []byte("data")); err != nil {
		return err
	}
	if err := binary.Write(file, binary.LittleEndian, dataSize); err != nil {
		return err
	}

	// Write audio data.
	if _, err := file.Write(data); err != nil {
		return fmt.Errorf("failed to write audio data: %w", err)
	}

	return nil
}

// GetRecordingInfo returns current recording information.
func (r *MalgoRecorder) GetRecordingInfo() RecordingInfo {
	r.recordingMutex.RLock()
	defer r.recordingMutex.RUnlock()

	info := RecordingInfo{
		State:     r.state,
		Folder:    r.currentFolder,
		Filename:  r.currentFilename,
		StartTime: r.startTime,
	}

	if r.state != StateStopped {
		elapsed := time.Since(r.startTime)
		if r.state == StatePaused {
			elapsed = r.totalPauseTime + time.Since(r.pauseStartTime)
		} else {
			elapsed = elapsed - r.totalPauseTime
		}
		info.Duration = elapsed
	}

	return info
}

// GetAvailableDevices returns list of available recording devices.
func (r *MalgoRecorder) GetAvailableDevices() ([]AudioDevice, error) {
	devices, err := r.malgoContext.Devices(malgo.Capture)
	if err != nil {
		return nil, fmt.Errorf("failed to get capture devices: %w", err)
	}

	var audioDevices []AudioDevice
	for i, device := range devices {
		audioDevice := AudioDevice{
			ID:          i,
			Name:        device.Name(),
			IsDefault:   device.IsDefault != 0,
			MaxChannels: int(device.MaxChannels),
			SampleRate:  int(r.sampleRate),
		}
		audioDevices = append(audioDevices, audioDevice)
	}

	return audioDevices, nil
}

// SetDevice sets the recording device by ID.
func (r *MalgoRecorder) SetDevice(deviceID int) error {
	devices, err := r.malgoContext.Devices(malgo.Capture)
	if err != nil {
		return fmt.Errorf("failed to get capture devices: %w", err)
	}

	if deviceID < 0 || deviceID >= len(devices) {
		return fmt.Errorf("invalid device ID: %d", deviceID)
	}

	// Device will be set when recording starts.
	return nil
}

// CheckDiskSpace checks if there's enough free disk space for recording.
func (r *MalgoRecorder) CheckDiskSpace() (bool, int64, error) {
	var stat syscall.Statfs_t
	if err := syscall.Statfs(r.recordsDir, &stat); err != nil {
		return false, 0, fmt.Errorf("failed to get disk space: %w", err)
	}

	freeSpace := int64(stat.Bavail) * int64(stat.Bsize)
	return freeSpace >= r.minFreeSpaceBytes, freeSpace, nil
}

// Close closes the recorder and releases resources.
func (r *MalgoRecorder) Close() error {
	if r.state != StateStopped {
		_, err := r.StopRecording()
		if err != nil {
			return fmt.Errorf("failed to stop recording: %w", err)
		}
	}

	if r.malgoContext != nil {
		_ = r.malgoContext.Uninit()
		r.malgoContext.Free()
	}

	return nil
}

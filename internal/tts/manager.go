package tts

import (
	"context"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"sync"
	"time"
)

// TTSManager implements the Manager interface.
type TTSManager struct {
	primaryEngine   Engine
	fallbackEngine  Engine
	cache           Cache
	currentVoice    string
	currentEngine   string
	audioPlayer     AudioPlayer
	mutex           sync.RWMutex
	isPlaying       bool
	currentProcess  *exec.Cmd
}

// AudioPlayer defines interface for playing audio.
type AudioPlayer interface {
	Play(audioData []byte) error
	PlayFile(filePath string) error
	Stop() error
	IsPlaying() bool
}

// SystemAudioPlayer implements AudioPlayer using system utilities.
type SystemAudioPlayer struct {
	currentProcess *exec.Cmd
	mutex          sync.Mutex
}

// NewSystemAudioPlayer creates a new system audio player.
func NewSystemAudioPlayer() *SystemAudioPlayer {
	return &SystemAudioPlayer{}
}

// Play plays audio data.
func (p *SystemAudioPlayer) Play(audioData []byte) error {
	p.mutex.Lock()
	defer p.mutex.Unlock()

	// Stop current playback.
	p.stopInternal()

	// Create temporary file.
	tempFile, err := os.CreateTemp("", "tts_*.wav")
	if err != nil {
		return fmt.Errorf("failed to create temp file: %w", err)
	}
	defer os.Remove(tempFile.Name())

	// Write audio data to temp file.
	if _, err := tempFile.Write(audioData); err != nil {
		tempFile.Close()
		return fmt.Errorf("failed to write audio data: %w", err)
	}
	tempFile.Close()

	// Play using aplay.
	cmd := exec.Command("aplay", "-D", "pulse", tempFile.Name())
	p.currentProcess = cmd

	if err := cmd.Run(); err != nil {
		return fmt.Errorf("failed to play audio: %w", err)
	}

	return nil
}

// PlayFile plays audio file.
func (p *SystemAudioPlayer) PlayFile(filePath string) error {
	p.mutex.Lock()
	defer p.mutex.Unlock()

	// Stop current playback.
	p.stopInternal()

	// Play using aplay.
	cmd := exec.Command("aplay", "-D", "pulse", filePath)
	p.currentProcess = cmd

	if err := cmd.Run(); err != nil {
		return fmt.Errorf("failed to play audio file: %w", err)
	}

	return nil
}

// Stop stops current playback.
func (p *SystemAudioPlayer) Stop() error {
	p.mutex.Lock()
	defer p.mutex.Unlock()

	return p.stopInternal()
}

// stopInternal stops playback without locking.
func (p *SystemAudioPlayer) stopInternal() error {
	if p.currentProcess != nil && p.currentProcess.Process != nil {
		if err := p.currentProcess.Process.Kill(); err != nil {
			return fmt.Errorf("failed to kill audio process: %w", err)
		}
		p.currentProcess = nil
	}
	return nil
}

// IsPlaying returns true if audio is currently playing.
func (p *SystemAudioPlayer) IsPlaying() bool {
	p.mutex.Lock()
	defer p.mutex.Unlock()

	return p.currentProcess != nil && p.currentProcess.Process != nil
}

// NewTTSManager creates a new TTS manager.
func NewTTSManager(cacheDir, credentialsPath, primaryEngine, fallbackEngine, voice string) (*TTSManager, error) {
	// Create cache.
	cache, err := NewFileCache(cacheDir)
	if err != nil {
		return nil, fmt.Errorf("failed to create cache: %w", err)
	}

	// Create audio player.
	audioPlayer := NewSystemAudioPlayer()

	manager := &TTSManager{
		cache:         cache,
		currentVoice:  voice,
		currentEngine: primaryEngine,
		audioPlayer:   audioPlayer,
	}

	// Initialize engines.
	if err := manager.initializeEngines(credentialsPath, primaryEngine, fallbackEngine); err != nil {
		return nil, fmt.Errorf("failed to initialize engines: %w", err)
	}

	return manager, nil
}

// initializeEngines initializes TTS engines.
func (m *TTSManager) initializeEngines(credentialsPath, primaryEngine, fallbackEngine string) error {
	// Initialize primary engine.
	switch primaryEngine {
	case "google_cloud":
		if credentialsPath == "" {
			return fmt.Errorf("credentials path required for Google Cloud TTS")
		}
		engine, err := NewGoogleCloudEngine(credentialsPath)
		if err != nil {
			return fmt.Errorf("failed to initialize Google Cloud engine: %w", err)
		}
		m.primaryEngine = engine

	case "gtts":
		m.primaryEngine = NewGTTSEngine("ru", "com")

	default:
		return fmt.Errorf("unsupported primary engine: %s", primaryEngine)
	}

	// Initialize fallback engine.
	switch fallbackEngine {
	case "gtts":
		m.fallbackEngine = NewGTTSEngine("ru", "com")

	case "google_cloud":
		if credentialsPath != "" {
			engine, err := NewGoogleCloudEngine(credentialsPath)
			if err != nil {
				// Don't fail if fallback engine can't be initialized.
				m.fallbackEngine = NewGTTSEngine("ru", "com")
			} else {
				m.fallbackEngine = engine
			}
		} else {
			m.fallbackEngine = NewGTTSEngine("ru", "com")
		}

	default:
		// Default to gTTS as fallback.
		m.fallbackEngine = NewGTTSEngine("ru", "com")
	}

	return nil
}

// PlaySpeech plays text as speech (non-blocking).
func (m *TTSManager) PlaySpeech(ctx context.Context, text string) error {
	go func() {
		_ = m.PlaySpeechBlocking(ctx, text)
	}()
	return nil
}

// PlaySpeechBlocking plays text as speech (blocking).
func (m *TTSManager) PlaySpeechBlocking(ctx context.Context, text string) error {
	m.mutex.Lock()
	defer m.mutex.Unlock()

	// Stop current playback.
	m.audioPlayer.Stop()

	// Generate speech.
	audioData, err := m.generateSpeechInternal(ctx, text, m.currentVoice)
	if err != nil {
		return fmt.Errorf("failed to generate speech: %w", err)
	}

	// Play audio.
	m.isPlaying = true
	defer func() { m.isPlaying = false }()

	if err := m.audioPlayer.Play(audioData); err != nil {
		return fmt.Errorf("failed to play speech: %w", err)
	}

	return nil
}

// PlaySpeechWithVoice plays text with specific voice.
func (m *TTSManager) PlaySpeechWithVoice(ctx context.Context, text string, voiceID string) error {
	m.mutex.Lock()
	defer m.mutex.Unlock()

	// Stop current playback.
	m.audioPlayer.Stop()

	// Generate speech.
	audioData, err := m.generateSpeechInternal(ctx, text, voiceID)
	if err != nil {
		return fmt.Errorf("failed to generate speech: %w", err)
	}

	// Play audio.
	m.isPlaying = true
	defer func() { m.isPlaying = false }()

	if err := m.audioPlayer.Play(audioData); err != nil {
		return fmt.Errorf("failed to play speech: %w", err)
	}

	return nil
}

// GenerateSpeech generates speech audio without playing.
func (m *TTSManager) GenerateSpeech(ctx context.Context, text string) ([]byte, error) {
	m.mutex.RLock()
	defer m.mutex.RUnlock()

	return m.generateSpeechInternal(ctx, text, m.currentVoice)
}

// generateSpeechInternal generates speech with caching.
func (m *TTSManager) generateSpeechInternal(ctx context.Context, text string, voice string) ([]byte, error) {
	// Check cache first.
	cacheKey := GenerateCacheKey(text, voice, m.currentEngine)
	if audioData, found := m.cache.Get(cacheKey); found {
		return audioData, nil
	}

	// Try primary engine.
	audioData, err := m.primaryEngine.GenerateSpeech(ctx, text, voice)
	if err != nil {
		// Try fallback engine.
		if m.fallbackEngine != nil {
			audioData, err = m.fallbackEngine.GenerateSpeech(ctx, text, voice)
			if err != nil {
				return nil, fmt.Errorf("both engines failed: primary=%v, fallback=%v", err, err)
			}
		} else {
			return nil, fmt.Errorf("primary engine failed and no fallback: %w", err)
		}
	}

	// Cache the result.
	if err := m.cache.Set(cacheKey, audioData); err != nil {
		// Log error but don't fail.
		fmt.Printf("Warning: failed to cache TTS result: %v\n", err)
	}

	return audioData, nil
}

// SetVoice sets the default voice.
func (m *TTSManager) SetVoice(voiceID string) error {
	m.mutex.Lock()
	defer m.mutex.Unlock()

	// Validate voice exists.
	voices := m.primaryEngine.GetAvailableVoices()
	found := false
	for _, voice := range voices {
		if voice.ID == voiceID {
			found = true
			break
		}
	}

	if !found {
		return fmt.Errorf("voice not found: %s", voiceID)
	}

	m.currentVoice = voiceID
	return nil
}

// GetVoice returns the current voice.
func (m *TTSManager) GetVoice() string {
	m.mutex.RLock()
	defer m.mutex.RUnlock()

	return m.currentVoice
}

// GetAvailableVoices returns available voices.
func (m *TTSManager) GetAvailableVoices() []Voice {
	m.mutex.RLock()
	defer m.mutex.RUnlock()

	return m.primaryEngine.GetAvailableVoices()
}

// SetEngine sets the primary TTS engine.
func (m *TTSManager) SetEngine(engineName string) error {
	m.mutex.Lock()
	defer m.mutex.Unlock()

	if engineName == m.currentEngine {
		return nil
	}

	// Switch engines.
	switch engineName {
	case "google_cloud":
		if m.primaryEngine.GetName() != "google_cloud" {
			// Swap engines if fallback is Google Cloud.
			if m.fallbackEngine != nil && m.fallbackEngine.GetName() == "google_cloud" {
				m.primaryEngine, m.fallbackEngine = m.fallbackEngine, m.primaryEngine
			} else {
				return fmt.Errorf("google_cloud engine not available")
			}
		}

	case "gtts":
		if m.primaryEngine.GetName() != "gtts" {
			// Swap engines if fallback is gTTS.
			if m.fallbackEngine != nil && m.fallbackEngine.GetName() == "gtts" {
				m.primaryEngine, m.fallbackEngine = m.fallbackEngine, m.primaryEngine
			} else {
				return fmt.Errorf("gtts engine not available")
			}
		}

	default:
		return fmt.Errorf("unsupported engine: %s", engineName)
	}

	m.currentEngine = engineName
	return nil
}

// GetEngine returns the current engine name.
func (m *TTSManager) GetEngine() string {
	m.mutex.RLock()
	defer m.mutex.RUnlock()

	return m.currentEngine
}

// GetUsageStats returns usage statistics.
func (m *TTSManager) GetUsageStats() UsageStats {
	m.mutex.RLock()
	defer m.mutex.RUnlock()

	stats := m.primaryEngine.GetUsageStats()
	
	// Add cache stats.
	cacheStats := m.cache.GetStats()
	stats.CacheHits = cacheStats.Hits
	stats.CacheMisses = cacheStats.Misses

	return stats
}

// GetCacheStats returns cache statistics.
func (m *TTSManager) GetCacheStats() CacheStats {
	return m.cache.GetStats()
}

// ClearCache clears the TTS cache.
func (m *TTSManager) ClearCache() error {
	return m.cache.Clear()
}

// PreGenerateTexts pre-generates speech for a list of texts.
func (m *TTSManager) PreGenerateTexts(ctx context.Context, texts []string) error {
	for _, text := range texts {
		if ctx.Err() != nil {
			return ctx.Err()
		}

		// Generate speech for current voice.
		_, err := m.GenerateSpeech(ctx, text)
		if err != nil {
			fmt.Printf("Warning: failed to pre-generate speech for '%s': %v\n", text, err)
		}

		// Small delay to avoid overwhelming the API.
		time.Sleep(100 * time.Millisecond)
	}

	return nil
}

// Stop stops any current playback.
func (m *TTSManager) Stop() error {
	m.mutex.Lock()
	defer m.mutex.Unlock()

	return m.audioPlayer.Stop()
}

// Close closes the TTS manager and releases resources.
func (m *TTSManager) Close() error {
	m.mutex.Lock()
	defer m.mutex.Unlock()

	var errors []string

	// Stop playback.
	if err := m.audioPlayer.Stop(); err != nil {
		errors = append(errors, fmt.Sprintf("audio player stop error: %v", err))
	}

	// Close engines.
	if m.primaryEngine != nil {
		if err := m.primaryEngine.Close(); err != nil {
			errors = append(errors, fmt.Sprintf("primary engine close error: %v", err))
		}
	}

	if m.fallbackEngine != nil {
		if err := m.fallbackEngine.Close(); err != nil {
			errors = append(errors, fmt.Sprintf("fallback engine close error: %v", err))
		}
	}

	if len(errors) > 0 {
		return fmt.Errorf("errors during close: %s", errors)
	}

	return nil
}

// SaveAudioToFile saves audio data to file.
func (m *TTSManager) SaveAudioToFile(audioData []byte, filePath string) error {
	// Create directory if it doesn't exist.
	dir := filepath.Dir(filePath)
	if err := os.MkdirAll(dir, 0755); err != nil {
		return fmt.Errorf("failed to create directory: %w", err)
	}

	// Write audio data to file.
	if err := os.WriteFile(filePath, audioData, 0644); err != nil {
		return fmt.Errorf("failed to write audio file: %w", err)
	}

	return nil
}

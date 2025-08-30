package tts

import (
	"context"
	"time"
)

// Engine represents a text-to-speech engine.
type Engine interface {
	// GenerateSpeech generates speech audio from text.
	GenerateSpeech(ctx context.Context, text string, voice string) ([]byte, error)

	// GetAvailableVoices returns list of available voices.
	GetAvailableVoices() []Voice

	// GetUsageStats returns usage statistics.
	GetUsageStats() UsageStats

	// GetName returns the engine name.
	GetName() string

	// Close closes the engine and releases resources.
	Close() error
}

// Voice represents a TTS voice.
type Voice struct {
	ID          string `json:"id"`
	Name        string `json:"name"`
	Language    string `json:"language"`
	Gender      string `json:"gender"`
	Type        string `json:"type"` // Standard, WaveNet, Neural.
	PricePerMillion float64 `json:"price_per_million"`
}

// UsageStats represents TTS usage statistics.
type UsageStats struct {
	TotalRequests     int64     `json:"total_requests"`
	TodayRequests     int64     `json:"today_requests"`
	TotalCharacters   int64     `json:"total_characters"`
	MonthlyCharacters int64     `json:"monthly_characters"`
	CacheHits         int64     `json:"cache_hits"`
	CacheMisses       int64     `json:"cache_misses"`
	EstimatedCost     float64   `json:"estimated_cost"`
	LastUpdate        time.Time `json:"last_update"`
}

// Cache represents a TTS cache interface.
type Cache interface {
	// Get retrieves cached audio data for the given key.
	Get(key string) ([]byte, bool)

	// Set stores audio data in cache with the given key.
	Set(key string, data []byte) error

	// Delete removes cached data for the given key.
	Delete(key string) error

	// Clear clears all cached data.
	Clear() error

	// GetSize returns the current cache size in bytes.
	GetSize() (int64, error)

	// GetStats returns cache statistics.
	GetStats() CacheStats
}

// CacheStats represents cache statistics.
type CacheStats struct {
	Hits        int64 `json:"hits"`
	Misses      int64 `json:"misses"`
	Size        int64 `json:"size"`
	ItemCount   int   `json:"item_count"`
	HitRate     float64 `json:"hit_rate"`
}

// Manager represents the main TTS manager interface.
type Manager interface {
	// PlaySpeech plays text as speech (non-blocking).
	PlaySpeech(ctx context.Context, text string) error

	// PlaySpeechBlocking plays text as speech (blocking).
	PlaySpeechBlocking(ctx context.Context, text string) error

	// PlaySpeechWithVoice plays text with specific voice.
	PlaySpeechWithVoice(ctx context.Context, text string, voiceID string) error

	// GenerateSpeech generates speech audio without playing.
	GenerateSpeech(ctx context.Context, text string) ([]byte, error)

	// SetVoice sets the default voice.
	SetVoice(voiceID string) error

	// GetVoice returns the current voice.
	GetVoice() string

	// GetAvailableVoices returns available voices.
	GetAvailableVoices() []Voice

	// SetEngine sets the primary TTS engine.
	SetEngine(engineName string) error

	// GetEngine returns the current engine name.
	GetEngine() string

	// GetUsageStats returns usage statistics.
	GetUsageStats() UsageStats

	// GetCacheStats returns cache statistics.
	GetCacheStats() CacheStats

	// ClearCache clears the TTS cache.
	ClearCache() error

	// PreGenerateTexts pre-generates speech for a list of texts.
	PreGenerateTexts(ctx context.Context, texts []string) error

	// Stop stops any current playback.
	Stop() error

	// Close closes the TTS manager and releases resources.
	Close() error
}

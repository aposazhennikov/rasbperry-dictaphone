package tts

import (
	"context"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"sync"
	"time"
)

// GTTSEngine implements the Engine interface for Google Translate TTS.
type GTTSEngine struct {
	client   *http.Client
	stats    UsageStats
	mutex    sync.RWMutex
	voices   []Voice
	language string
	tld      string
}

// NewGTTSEngine creates a new Google Translate TTS engine.
func NewGTTSEngine(language, tld string) *GTTSEngine {
	engine := &GTTSEngine{
		client: &http.Client{
			Timeout: 30 * time.Second,
		},
		stats:    UsageStats{LastUpdate: time.Now()},
		language: language,
		tld:      tld,
	}

	// Set default voices for gTTS.
	engine.setDefaultVoices()

	return engine
}

// GenerateSpeech generates speech audio from text.
func (e *GTTSEngine) GenerateSpeech(ctx context.Context, text string, voice string) ([]byte, error) {
	e.mutex.Lock()
	defer e.mutex.Unlock()

	// Update stats.
	e.stats.TotalRequests++
	e.stats.TotalCharacters += int64(len(text))
	
	// Check if today's date changed.
	now := time.Now()
	if now.Format("2006-01-02") != e.stats.LastUpdate.Format("2006-01-02") {
		e.stats.TodayRequests = 0
	}
	e.stats.TodayRequests++
	e.stats.LastUpdate = now

	// Monthly characters (simplified).
	e.stats.MonthlyCharacters = e.stats.TotalCharacters

	// gTTS is free, so no cost estimation.
	e.stats.EstimatedCost = 0.0

	// Create request URL.
	baseURL := fmt.Sprintf("https://translate.google.%s/translate_tts", e.tld)
	params := url.Values{}
	params.Add("ie", "UTF-8")
	params.Add("q", text)
	params.Add("tl", e.language)
	params.Add("total", "1")
	params.Add("idx", "0")
	params.Add("textlen", fmt.Sprintf("%d", len(text)))
	params.Add("client", "tw-ob")

	requestURL := fmt.Sprintf("%s?%s", baseURL, params.Encode())

	// Create HTTP request.
	req, err := http.NewRequestWithContext(ctx, "GET", requestURL, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}

	// Set user agent to avoid blocking.
	req.Header.Set("User-Agent", "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36")

	// Perform request.
	resp, err := e.client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("failed to perform request: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("gTTS API returned status: %d", resp.StatusCode)
	}

	// Read response body.
	audioData, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("failed to read response body: %w", err)
	}

	return audioData, nil
}

// GetAvailableVoices returns list of available voices.
func (e *GTTSEngine) GetAvailableVoices() []Voice {
	e.mutex.RLock()
	defer e.mutex.RUnlock()

	return e.voices
}

// GetUsageStats returns usage statistics.
func (e *GTTSEngine) GetUsageStats() UsageStats {
	e.mutex.RLock()
	defer e.mutex.RUnlock()

	return e.stats
}

// GetName returns the engine name.
func (e *GTTSEngine) GetName() string {
	return "gtts"
}

// setDefaultVoices sets default voices for gTTS.
func (e *GTTSEngine) setDefaultVoices() {
	// gTTS doesn't have multiple voices per language, just one default voice.
	e.voices = []Voice{
		{
			ID:              "gtts-ru",
			Name:            "Google Translate Russian",
			Language:        "ru",
			Gender:          "NEUTRAL",
			Type:            "Standard",
			PricePerMillion: 0.0, // Free.
		},
	}
}

// Close closes the engine and releases resources.
func (e *GTTSEngine) Close() error {
	// Nothing to close for gTTS.
	return nil
}

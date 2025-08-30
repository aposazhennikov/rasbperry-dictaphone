package tts

import (
	"context"
	"fmt"
	"os"
	"sync"
	"time"

	texttospeech "cloud.google.com/go/texttospeech/apiv1"
	"cloud.google.com/go/texttospeech/apiv1/texttospeechpb"
	"google.golang.org/api/option"
)

// GoogleCloudEngine implements the Engine interface for Google Cloud TTS.
type GoogleCloudEngine struct {
	client          *texttospeech.Client
	credentialsPath string
	stats           UsageStats
	mutex           sync.RWMutex
	voices          []Voice
}

// NewGoogleCloudEngine creates a new Google Cloud TTS engine.
func NewGoogleCloudEngine(credentialsPath string) (*GoogleCloudEngine, error) {
	if credentialsPath == "" {
		return nil, fmt.Errorf("credentials path is required")
	}

	if _, err := os.Stat(credentialsPath); os.IsNotExist(err) {
		return nil, fmt.Errorf("credentials file not found: %s", credentialsPath)
	}

	ctx := context.Background()
	client, err := texttospeech.NewClient(ctx, option.WithCredentialsFile(credentialsPath))
	if err != nil {
		return nil, fmt.Errorf("failed to create Google Cloud TTS client: %w", err)
	}

	engine := &GoogleCloudEngine{
		client:          client,
		credentialsPath: credentialsPath,
		stats:           UsageStats{LastUpdate: time.Now()},
		voices:          make([]Voice, 0),
	}

	// Initialize available voices.
	if err := engine.initializeVoices(ctx); err != nil {
		// Don't fail if we can't get voices, use defaults.
		engine.setDefaultVoices()
	}

	return engine, nil
}

// GenerateSpeech generates speech audio from text.
func (e *GoogleCloudEngine) GenerateSpeech(ctx context.Context, text string, voice string) ([]byte, error) {
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

	// Calculate monthly characters (simplified - just use total for now).
	e.stats.MonthlyCharacters = e.stats.TotalCharacters

	// Estimate cost (Google Cloud pricing: ~$16 per million characters for standard voices).
	voiceType := e.getVoiceType(voice)
	var pricePerMillion float64
	switch voiceType {
	case "Standard":
		pricePerMillion = 4.0 // $4 per million characters.
	case "WaveNet":
		pricePerMillion = 16.0 // $16 per million characters.
	case "Neural2":
		pricePerMillion = 16.0 // $16 per million characters.
	default:
		pricePerMillion = 4.0
	}
	
	e.stats.EstimatedCost = float64(e.stats.TotalCharacters) * pricePerMillion / 1000000.0

	// Create synthesis request.
	req := &texttospeechpb.SynthesizeSpeechRequest{
		Input: &texttospeechpb.SynthesisInput{
			InputSource: &texttospeechpb.SynthesisInput_Text{Text: text},
		},
		Voice: &texttospeechpb.VoiceSelectionParams{
			LanguageCode: "ru-RU",
			Name:         voice,
		},
		AudioConfig: &texttospeechpb.AudioConfig{
			AudioEncoding: texttospeechpb.AudioEncoding_LINEAR16,
			SampleRateHertz: 44100,
		},
	}

	// Perform synthesis.
	resp, err := e.client.SynthesizeSpeech(ctx, req)
	if err != nil {
		return nil, fmt.Errorf("failed to synthesize speech: %w", err)
	}

	return resp.AudioContent, nil
}

// GetAvailableVoices returns list of available voices.
func (e *GoogleCloudEngine) GetAvailableVoices() []Voice {
	e.mutex.RLock()
	defer e.mutex.RUnlock()

	return e.voices
}

// GetUsageStats returns usage statistics.
func (e *GoogleCloudEngine) GetUsageStats() UsageStats {
	e.mutex.RLock()
	defer e.mutex.RUnlock()

	return e.stats
}

// GetName returns the engine name.
func (e *GoogleCloudEngine) GetName() string {
	return "google_cloud"
}

// initializeVoices initializes the list of available voices from Google Cloud.
func (e *GoogleCloudEngine) initializeVoices(ctx context.Context) error {
	req := &texttospeechpb.ListVoicesRequest{
		LanguageCode: "ru-RU",
	}

	resp, err := e.client.ListVoices(ctx, req)
	if err != nil {
		return fmt.Errorf("failed to list voices: %w", err)
	}

	e.voices = make([]Voice, 0, len(resp.Voices))
	for _, voice := range resp.Voices {
		if len(voice.LanguageCodes) > 0 && voice.LanguageCodes[0] == "ru-RU" {
			voiceType := "Standard"
			pricePerMillion := 4.0

			// Determine voice type and pricing.
			if voice.Name != "" {
				if voice.Name[len(voice.Name)-1:] >= "A" && voice.Name[len(voice.Name)-1:] <= "E" {
					voiceType = "Standard"
					pricePerMillion = 4.0
				}
				// Add logic for WaveNet and Neural voices if needed.
			}

			e.voices = append(e.voices, Voice{
				ID:              voice.Name,
				Name:            voice.Name,
				Language:        voice.LanguageCodes[0],
				Gender:          voice.SsmlGender.String(),
				Type:            voiceType,
				PricePerMillion: pricePerMillion,
			})
		}
	}

	return nil
}

// setDefaultVoices sets default Russian voices if we can't get them from API.
func (e *GoogleCloudEngine) setDefaultVoices() {
	e.voices = []Voice{
		{
			ID:              "ru-RU-Standard-A",
			Name:            "ru-RU-Standard-A",
			Language:        "ru-RU",
			Gender:          "FEMALE",
			Type:            "Standard",
			PricePerMillion: 4.0,
		},
		{
			ID:              "ru-RU-Standard-B",
			Name:            "ru-RU-Standard-B",
			Language:        "ru-RU",
			Gender:          "MALE",
			Type:            "Standard",
			PricePerMillion: 4.0,
		},
		{
			ID:              "ru-RU-Standard-C",
			Name:            "ru-RU-Standard-C",
			Language:        "ru-RU",
			Gender:          "FEMALE",
			Type:            "Standard",
			PricePerMillion: 4.0,
		},
		{
			ID:              "ru-RU-Standard-D",
			Name:            "ru-RU-Standard-D",
			Language:        "ru-RU",
			Gender:          "MALE",
			Type:            "Standard",
			PricePerMillion: 4.0,
		},
		{
			ID:              "ru-RU-Standard-E",
			Name:            "ru-RU-Standard-E",
			Language:        "ru-RU",
			Gender:          "FEMALE",
			Type:            "Standard",
			PricePerMillion: 4.0,
		},
	}
}

// getVoiceType determines voice type from voice name.
func (e *GoogleCloudEngine) getVoiceType(voiceName string) string {
	for _, voice := range e.voices {
		if voice.ID == voiceName {
			return voice.Type
		}
	}
	return "Standard"
}

// Close closes the engine and releases resources.
func (e *GoogleCloudEngine) Close() error {
	if e.client != nil {
		return e.client.Close()
	}
	return nil
}

package audio

import (
	"context"
	"fmt"
	"os/exec"
	"path/filepath"
	"strconv"
	"strings"
	"sync"
	"time"
)

// SystemPlayer implements the Player interface using system audio utilities.
type SystemPlayer struct {
	state         PlaybackState
	currentFile   string
	volume        int
	speed         float64
	position      time.Duration
	duration      time.Duration
	process       *exec.Cmd
	mutex         sync.RWMutex
	ctx           context.Context
	cancel        context.CancelFunc
	pausePosition time.Duration
}

// NewSystemPlayer creates a new SystemPlayer instance.
func NewSystemPlayer() *SystemPlayer {
	return &SystemPlayer{
		state:  PlaybackStopped,
		volume: 80,
		speed:  1.0,
	}
}

// Play starts playing the specified audio file.
func (p *SystemPlayer) Play(ctx context.Context, filePath string) error {
	p.mutex.Lock()
	defer p.mutex.Unlock()

	// Stop current playback if any.
	if p.state != PlaybackStopped {
		p.stopInternal()
	}

	// Check if file exists.
	if !p.fileExists(filePath) {
		return fmt.Errorf("file not found: %s", filePath)
	}

	p.currentFile = filePath
	p.position = 0
	p.pausePosition = 0

	// Get file duration.
	duration, err := p.getFileDuration(filePath)
	if err != nil {
		p.duration = 0
	} else {
		p.duration = duration
	}

	// Set up context.
	p.ctx, p.cancel = context.WithCancel(ctx)

	// Start playback based on file type.
	if err := p.startPlayback(); err != nil {
		return fmt.Errorf("failed to start playback: %w", err)
	}

	p.state = PlaybackPlaying
	return nil
}

// startPlayback starts the actual playback process.
func (p *SystemPlayer) startPlayback() error {
	ext := strings.ToLower(filepath.Ext(p.currentFile))
	var cmd *exec.Cmd

	switch ext {
	case ".wav":
		// Use aplay for WAV files.
		args := []string{"-D", "pulse"}
		if p.volume != 80 {
			// Volume control for aplay is limited, use amixer instead.
			_ = p.setSystemVolume(p.volume)
		}
		args = append(args, p.currentFile)
		cmd = exec.CommandContext(p.ctx, "aplay", args...)

	case ".mp3":
		// Use mpg123 for MP3 files.
		args := []string{"-q"} // Quiet mode.
		if p.volume != 80 {
			volumePercent := fmt.Sprintf("%.0f", float64(p.volume))
			args = append(args, "--volume", volumePercent)
		}
		if p.speed != 1.0 {
			speedStr := fmt.Sprintf("%.2f", p.speed)
			args = append(args, "--speed", speedStr)
		}
		args = append(args, p.currentFile)
		cmd = exec.CommandContext(p.ctx, "mpg123", args...)

	default:
		// Use VLC as fallback.
		args := []string{
			"--intf", "dummy",
			"--play-and-exit",
			"--no-video",
		}
		if p.volume != 80 {
			volumePercent := int(float64(p.volume) * 2.56) // Convert to 0-256 range.
			args = append(args, "--volume", strconv.Itoa(volumePercent))
		}
		if p.speed != 1.0 {
			speedStr := fmt.Sprintf("%.2f", p.speed)
			args = append(args, "--rate", speedStr)
		}
		args = append(args, p.currentFile)
		cmd = exec.CommandContext(p.ctx, "vlc", args...)
	}

	p.process = cmd

	// Start the process in background.
	go func() {
		err := cmd.Run()
		p.mutex.Lock()
		defer p.mutex.Unlock()

		if err != nil && p.ctx.Err() == nil {
			// Process ended with error (not cancelled).
			p.state = PlaybackStopped
		} else if p.ctx.Err() == nil {
			// Process ended normally.
			p.state = PlaybackStopped
			p.position = p.duration
		}
	}()

	return nil
}

// Pause pauses the current playback.
func (p *SystemPlayer) Pause() error {
	p.mutex.Lock()
	defer p.mutex.Unlock()

	if p.state != PlaybackPlaying {
		return fmt.Errorf("no active playback to pause")
	}

	// For system players, we need to stop and remember position.
	p.pausePosition = p.getCurrentPosition()
	p.stopInternal()
	p.state = PlaybackPaused

	return nil
}

// Resume resumes the paused playback.
func (p *SystemPlayer) Resume() error {
	p.mutex.Lock()
	defer p.mutex.Unlock()

	if p.state != PlaybackPaused {
		return fmt.Errorf("no paused playback to resume")
	}

	// For system players, we need to restart from pause position.
	if err := p.startPlaybackFromPosition(p.pausePosition); err != nil {
		return fmt.Errorf("failed to resume playback: %w", err)
	}

	p.state = PlaybackPlaying
	return nil
}

// startPlaybackFromPosition starts playback from a specific position.
func (p *SystemPlayer) startPlaybackFromPosition(position time.Duration) error {
	ext := strings.ToLower(filepath.Ext(p.currentFile))
	var cmd *exec.Cmd

	switch ext {
	case ".wav":
		// aplay doesn't support seeking, use sox to trim and pipe to aplay.
		soxArgs := []string{
			p.currentFile,
			"-t", "wav", "-",
			"trim", fmt.Sprintf("%.2f", position.Seconds()),
		}
		soxCmd := exec.CommandContext(p.ctx, "sox", soxArgs...)

		aplayArgs := []string{"-D", "pulse"}
		aplayCmd := exec.CommandContext(p.ctx, "aplay", aplayArgs...)

		// Pipe sox output to aplay.
		aplayCmd.Stdin, _ = soxCmd.StdoutPipe()
		
		if err := soxCmd.Start(); err != nil {
			return fmt.Errorf("failed to start sox: %w", err)
		}
		if err := aplayCmd.Start(); err != nil {
			return fmt.Errorf("failed to start aplay: %w", err)
		}

		p.process = aplayCmd

		go func() {
			_ = soxCmd.Wait()
			_ = aplayCmd.Wait()
		}()

	case ".mp3":
		// mpg123 supports seeking.
		args := []string{"-q"}
		if p.volume != 80 {
			volumePercent := fmt.Sprintf("%.0f", float64(p.volume))
			args = append(args, "--volume", volumePercent)
		}
		if p.speed != 1.0 {
			speedStr := fmt.Sprintf("%.2f", p.speed)
			args = append(args, "--speed", speedStr)
		}
		// Seek to position.
		seekFrames := int64(position.Seconds() * 44100) // Approximate for 44.1kHz.
		args = append(args, "--skip", strconv.FormatInt(seekFrames, 10))
		args = append(args, p.currentFile)
		cmd = exec.CommandContext(p.ctx, "mpg123", args...)

	default:
		// VLC supports seeking.
		args := []string{
			"--intf", "dummy",
			"--play-and-exit",
			"--no-video",
			"--start-time", fmt.Sprintf("%.0f", position.Seconds()),
		}
		if p.volume != 80 {
			volumePercent := int(float64(p.volume) * 2.56)
			args = append(args, "--volume", strconv.Itoa(volumePercent))
		}
		if p.speed != 1.0 {
			speedStr := fmt.Sprintf("%.2f", p.speed)
			args = append(args, "--rate", speedStr)
		}
		args = append(args, p.currentFile)
		cmd = exec.CommandContext(p.ctx, "vlc", args...)
	}

	if cmd != nil {
		p.process = cmd
		go func() {
			err := cmd.Run()
			p.mutex.Lock()
			defer p.mutex.Unlock()
			if err != nil && p.ctx.Err() == nil {
				p.state = PlaybackStopped
			} else if p.ctx.Err() == nil {
				p.state = PlaybackStopped
				p.position = p.duration
			}
		}()
	}

	return nil
}

// Stop stops the current playback.
func (p *SystemPlayer) Stop() error {
	p.mutex.Lock()
	defer p.mutex.Unlock()

	return p.stopInternal()
}

// stopInternal stops playback without locking (internal use).
func (p *SystemPlayer) stopInternal() error {
	if p.cancel != nil {
		p.cancel()
	}

	if p.process != nil {
		if p.process.Process != nil {
			_ = p.process.Process.Kill()
		}
		p.process = nil
	}

	p.state = PlaybackStopped
	p.position = 0
	p.pausePosition = 0

	return nil
}

// Seek seeks to the specified position in the audio file.
func (p *SystemPlayer) Seek(position time.Duration) error {
	p.mutex.Lock()
	defer p.mutex.Unlock()

	if p.state == PlaybackStopped {
		return fmt.Errorf("no active playback to seek")
	}

	if position < 0 || (p.duration > 0 && position > p.duration) {
		return fmt.Errorf("invalid seek position")
	}

	wasPlaying := p.state == PlaybackPlaying
	p.stopInternal()

	if wasPlaying {
		if err := p.startPlaybackFromPosition(position); err != nil {
			return fmt.Errorf("failed to seek: %w", err)
		}
		p.state = PlaybackPlaying
	} else {
		p.pausePosition = position
		p.state = PlaybackPaused
	}

	return nil
}

// SetVolume sets the playback volume (0-100).
func (p *SystemPlayer) SetVolume(volume int) error {
	if volume < 0 || volume > 100 {
		return fmt.Errorf("invalid volume: %d (must be 0-100)", volume)
	}

	p.mutex.Lock()
	p.volume = volume
	p.mutex.Unlock()

	// Apply volume change if currently playing.
	if p.state == PlaybackPlaying {
		return p.setSystemVolume(volume)
	}

	return nil
}

// SetSpeed sets the playback speed (0.5-2.0).
func (p *SystemPlayer) SetSpeed(speed float64) error {
	if speed < 0.5 || speed > 2.0 {
		return fmt.Errorf("invalid speed: %.2f (must be 0.5-2.0)", speed)
	}

	p.mutex.Lock()
	p.speed = speed
	p.mutex.Unlock()

	return nil
}

// GetPlaybackInfo returns current playback information.
func (p *SystemPlayer) GetPlaybackInfo() PlaybackInfo {
	p.mutex.RLock()
	defer p.mutex.RUnlock()

	position := p.position
	if p.state == PlaybackPaused {
		position = p.pausePosition
	} else if p.state == PlaybackPlaying {
		position = p.getCurrentPosition()
	}

	return PlaybackInfo{
		State:    p.state,
		Duration: p.duration,
		Position: position,
		Filename: filepath.Base(p.currentFile),
		Volume:   p.volume,
		Speed:    p.speed,
	}
}

// GetDuration returns the total duration of the current audio file.
func (p *SystemPlayer) GetDuration() (time.Duration, error) {
	p.mutex.RLock()
	defer p.mutex.RUnlock()

	if p.currentFile == "" {
		return 0, fmt.Errorf("no file loaded")
	}

	return p.duration, nil
}

// Helper functions.

// fileExists checks if a file exists.
func (p *SystemPlayer) fileExists(filePath string) bool {
	cmd := exec.Command("test", "-f", filePath)
	return cmd.Run() == nil
}

// getFileDuration gets the duration of an audio file.
func (p *SystemPlayer) getFileDuration(filePath string) (time.Duration, error) {
	// Use ffprobe to get duration.
	cmd := exec.Command("ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", filePath)
	output, err := cmd.Output()
	if err != nil {
		// Fallback: use soxi for WAV files.
		if strings.ToLower(filepath.Ext(filePath)) == ".wav" {
			cmd = exec.Command("soxi", "-D", filePath)
			output, err = cmd.Output()
			if err != nil {
				return 0, fmt.Errorf("failed to get duration: %w", err)
			}
		} else {
			return 0, fmt.Errorf("failed to get duration: %w", err)
		}
	}

	durationStr := strings.TrimSpace(string(output))
	durationFloat, err := strconv.ParseFloat(durationStr, 64)
	if err != nil {
		return 0, fmt.Errorf("failed to parse duration: %w", err)
	}

	return time.Duration(durationFloat * float64(time.Second)), nil
}

// getCurrentPosition estimates current playback position.
func (p *SystemPlayer) getCurrentPosition() time.Duration {
	// This is a simplified estimation.
	// In a real implementation, you might want to use more sophisticated tracking.
	if p.state == PlaybackPlaying {
		// Return estimated position based on time elapsed.
		// This is not accurate but provides a rough estimate.
		return p.pausePosition
	}
	return p.position
}

// setSystemVolume sets system volume using amixer.
func (p *SystemPlayer) setSystemVolume(volume int) error {
	cmd := exec.Command("amixer", "sset", "Master", fmt.Sprintf("%d%%", volume))
	return cmd.Run()
}

package tts

import (
	"crypto/md5"
	"fmt"
	"io/fs"
	"os"
	"path/filepath"
	"strings"
	"sync"
)

// FileCache implements the Cache interface using file system.
type FileCache struct {
	cacheDir string
	mutex    sync.RWMutex
	stats    CacheStats
}

// NewFileCache creates a new file-based cache.
func NewFileCache(cacheDir string) (*FileCache, error) {
	// Create cache directory if it doesn't exist.
	if err := os.MkdirAll(cacheDir, 0755); err != nil {
		return nil, fmt.Errorf("failed to create cache directory: %w", err)
	}

	cache := &FileCache{
		cacheDir: cacheDir,
		stats:    CacheStats{},
	}

	// Initialize stats.
	if err := cache.updateStats(); err != nil {
		return nil, fmt.Errorf("failed to initialize cache stats: %w", err)
	}

	return cache, nil
}

// Get retrieves cached audio data for the given key.
func (c *FileCache) Get(key string) ([]byte, bool) {
	c.mutex.RLock()
	defer c.mutex.RUnlock()

	filePath := c.getFilePath(key)
	data, err := os.ReadFile(filePath)
	if err != nil {
		c.stats.Misses++
		return nil, false
	}

	c.stats.Hits++
	c.updateHitRate()
	return data, true
}

// Set stores audio data in cache with the given key.
func (c *FileCache) Set(key string, data []byte) error {
	c.mutex.Lock()
	defer c.mutex.Unlock()

	filePath := c.getFilePath(key)
	
	// Create directory if it doesn't exist.
	dir := filepath.Dir(filePath)
	if err := os.MkdirAll(dir, 0755); err != nil {
		return fmt.Errorf("failed to create cache subdirectory: %w", err)
	}

	if err := os.WriteFile(filePath, data, 0644); err != nil {
		return fmt.Errorf("failed to write cache file: %w", err)
	}

	// Update stats.
	c.stats.Size += int64(len(data))
	c.stats.ItemCount++

	return nil
}

// Delete removes cached data for the given key.
func (c *FileCache) Delete(key string) error {
	c.mutex.Lock()
	defer c.mutex.Unlock()

	filePath := c.getFilePath(key)
	
	// Get file size before deletion for stats.
	if info, err := os.Stat(filePath); err == nil {
		c.stats.Size -= info.Size()
		c.stats.ItemCount--
	}

	if err := os.Remove(filePath); err != nil && !os.IsNotExist(err) {
		return fmt.Errorf("failed to delete cache file: %w", err)
	}

	return nil
}

// Clear clears all cached data.
func (c *FileCache) Clear() error {
	c.mutex.Lock()
	defer c.mutex.Unlock()

	// Remove all files in cache directory.
	err := filepath.WalkDir(c.cacheDir, func(path string, d fs.DirEntry, err error) error {
		if err != nil {
			return err
		}

		if !d.IsDir() && (strings.HasSuffix(path, ".wav") || strings.HasSuffix(path, ".mp3")) {
			if removeErr := os.Remove(path); removeErr != nil {
				return fmt.Errorf("failed to remove file %s: %w", path, removeErr)
			}
		}

		return nil
	})

	if err != nil {
		return fmt.Errorf("failed to clear cache: %w", err)
	}

	// Reset stats.
	c.stats = CacheStats{}

	return nil
}

// GetSize returns the current cache size in bytes.
func (c *FileCache) GetSize() (int64, error) {
	c.mutex.RLock()
	defer c.mutex.RUnlock()

	return c.stats.Size, nil
}

// GetStats returns cache statistics.
func (c *FileCache) GetStats() CacheStats {
	c.mutex.RLock()
	defer c.mutex.RUnlock()

	return c.stats
}

// getFilePath generates file path for cache key.
func (c *FileCache) getFilePath(key string) string {
	// Create MD5 hash of the key for filename.
	hash := md5.Sum([]byte(key))
	filename := fmt.Sprintf("%x.wav", hash)
	
	// Use first two characters of hash for subdirectory to avoid too many files in one directory.
	subDir := fmt.Sprintf("%x", hash[:1])
	
	return filepath.Join(c.cacheDir, subDir, filename)
}

// updateStats recalculates cache statistics.
func (c *FileCache) updateStats() error {
	var totalSize int64
	var itemCount int

	err := filepath.WalkDir(c.cacheDir, func(path string, d fs.DirEntry, err error) error {
		if err != nil {
			return err
		}

		if !d.IsDir() && (strings.HasSuffix(path, ".wav") || strings.HasSuffix(path, ".mp3")) {
			info, err := d.Info()
			if err != nil {
				return err
			}
			totalSize += info.Size()
			itemCount++
		}

		return nil
	})

	if err != nil {
		return fmt.Errorf("failed to calculate cache stats: %w", err)
	}

	c.stats.Size = totalSize
	c.stats.ItemCount = itemCount
	c.updateHitRate()

	return nil
}

// updateHitRate calculates hit rate.
func (c *FileCache) updateHitRate() {
	total := c.stats.Hits + c.stats.Misses
	if total > 0 {
		c.stats.HitRate = float64(c.stats.Hits) / float64(total)
	}
}

// GenerateCacheKey generates a cache key for text and voice.
func GenerateCacheKey(text, voice, engine string) string {
	// Normalize text for consistent caching.
	normalizedText := strings.TrimSpace(strings.ToLower(text))
	
	// Create key with engine prefix for different engines.
	var prefix string
	switch engine {
	case "google_cloud":
		prefix = "gc"
	case "gtts":
		prefix = "gtts"
	default:
		prefix = "tts"
	}

	return fmt.Sprintf("%s_%s_%s", prefix, voice, normalizedText)
}

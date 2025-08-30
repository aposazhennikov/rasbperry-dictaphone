package menu

import (
	"context"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"time"

	"raspberry-dictaphone-go/internal/audio"
	"raspberry-dictaphone-go/internal/logger"
	"raspberry-dictaphone-go/internal/tts"
	"raspberry-dictaphone-go/internal/usb"
)

// DictaphoneBuilder implements the Builder interface for dictaphone menus.
type DictaphoneBuilder struct {
	audioManager audio.Manager
	ttsManager   tts.Manager
	usbManager   usb.Manager
	logger       *logger.Logger
	recordsDir   string
}

// NewDictaphoneBuilder creates a new dictaphone menu builder.
func NewDictaphoneBuilder(audioMgr audio.Manager, ttsMgr tts.Manager, usbMgr usb.Manager, log *logger.Logger, recordsDir string) *DictaphoneBuilder {
	return &DictaphoneBuilder{
		audioManager: audioMgr,
		ttsManager:   ttsMgr,
		usbManager:   usbMgr,
		logger:       log,
		recordsDir:   recordsDir,
	}
}

// BuildMainMenu builds the main menu structure.
func (b *DictaphoneBuilder) BuildMainMenu() *Menu {
	menu := &Menu{
		ID:           "main",
		Title:        "Главное меню",
		Description:  "Raspberry Pi Диктофон - Главное меню",
		Items:        make([]*Item, 0),
		CurrentIndex: 0,
	}

	// Recording submenu.
	recordingMenu := b.BuildRecordingMenu()
	recordingItem := NewSubmenuItem("recording", "🎙️ Запись", "Записать новую аудиозапись", recordingMenu)
	menu.Items = append(menu.Items, recordingItem)

	// Playback submenu.
	playbackMenu := b.BuildPlaybackMenu()
	playbackItem := NewSubmenuItem("playback", "▶️ Воспроизведение", "Прослушать записи", playbackMenu)
	menu.Items = append(menu.Items, playbackItem)

	// Radio submenu.
	radioMenu := b.BuildRadioMenu()
	radioItem := NewSubmenuItem("radio", "📻 Радио", "Радиостанции и подкасты", radioMenu)
	menu.Items = append(menu.Items, radioItem)

	// USB devices submenu.
	usbMenu := b.BuildUSBMenu()
	usbItem := NewSubmenuItem("usb", "💾 USB устройства", "Управление USB накопителями", usbMenu)
	menu.Items = append(menu.Items, usbItem)

	// Settings submenu.
	settingsMenu := b.BuildSettingsMenu()
	settingsItem := NewSubmenuItem("settings", "⚙️ Настройки", "Настройки системы", settingsMenu)
	menu.Items = append(menu.Items, settingsItem)

	// System submenu.
	systemMenu := b.BuildSystemMenu()
	systemItem := NewSubmenuItem("system", "🖥️ Система", "Системные функции", systemMenu)
	menu.Items = append(menu.Items, systemItem)

	return menu
}

// BuildRecordingMenu builds the recording menu.
func (b *DictaphoneBuilder) BuildRecordingMenu() *Menu {
	menu := &Menu{
		ID:           "recording",
		Title:        "Запись",
		Description:  "Выберите папку для записи",
		Items:        make([]*Item, 0),
		CurrentIndex: 0,
	}

	// Standard folders.
	folders := []struct {
		id, name, desc string
	}{
		{"notes", "📝 Заметки", "Общие заметки и мысли"},
		{"ideas", "💡 Идеи", "Креативные идеи и вдохновение"},
		{"important", "⭐ Важное", "Важные записи"},
		{"work", "💼 Работа", "Рабочие записи"},
		{"personal", "👤 Личное", "Личные записи"},
	}

	for _, folder := range folders {
		item := NewActionItem(folder.id, folder.name, folder.desc, b.createRecordingAction(folder.name))
		menu.Items = append(menu.Items, item)
	}

	// Separator.
	menu.Items = append(menu.Items, NewSeparatorItem("sep1"))

	// Recording status.
	statusItem := NewActionItem("status", "📊 Статус записи", "Показать информацию о текущей записи", b.createRecordingStatusAction())
	menu.Items = append(menu.Items, statusItem)

	// Microphone selection.
	micItem := NewActionItem("microphone", "🎤 Выбор микрофона", "Выбрать устройство записи", b.createMicrophoneSelectionAction())
	menu.Items = append(menu.Items, micItem)

	// Back item.
	menu.Items = append(menu.Items, NewBackItem())

	return menu
}

// BuildPlaybackMenu builds the playback menu.
func (b *DictaphoneBuilder) BuildPlaybackMenu() *Menu {
	menu := &Menu{
		ID:           "playback",
		Title:        "Воспроизведение",
		Description:  "Выберите папку для прослушивания",
		Items:        make([]*Item, 0),
		CurrentIndex: 0,
	}

	// Add dynamic folder items.
	b.AddDynamicItems(menu, "folders")

	// Separator.
	menu.Items = append(menu.Items, NewSeparatorItem("sep1"))

	// Playback controls.
	controlsItem := NewActionItem("controls", "🎛️ Управление", "Управление воспроизведением", b.createPlaybackControlsAction())
	menu.Items = append(menu.Items, controlsItem)

	// Back item.
	menu.Items = append(menu.Items, NewBackItem())

	return menu
}

// BuildSettingsMenu builds the settings menu.
func (b *DictaphoneBuilder) BuildSettingsMenu() *Menu {
	menu := &Menu{
		ID:           "settings",
		Title:        "Настройки",
		Description:  "Настройки системы",
		Items:        make([]*Item, 0),
		CurrentIndex: 0,
	}

	// TTS settings.
	ttsItem := NewActionItem("tts", "🗣️ Настройки голоса", "Настройка синтеза речи", b.createTTSSettingsAction())
	menu.Items = append(menu.Items, ttsItem)

	// Audio settings.
	audioItem := NewActionItem("audio", "🔊 Настройки звука", "Настройка аудиосистемы", b.createAudioSettingsAction())
	menu.Items = append(menu.Items, audioItem)

	// System volume.
	volumeItem := NewActionItem("volume", "🔉 Громкость системы", "Настройка системной громкости", b.createVolumeSettingsAction())
	menu.Items = append(menu.Items, volumeItem)

	// Auto-mount USB.
	usbAutoItem := NewActionItem("usb_auto", "💾 Автомонтирование", "Настройка автомонтирования USB", b.createUSBAutoMountAction())
	menu.Items = append(menu.Items, usbAutoItem)

	// Back item.
	menu.Items = append(menu.Items, NewBackItem())

	return menu
}

// BuildUSBMenu builds the USB devices menu.
func (b *DictaphoneBuilder) BuildUSBMenu() *Menu {
	menu := &Menu{
		ID:           "usb",
		Title:        "USB устройства",
		Description:  "Управление USB накопителями",
		Items:        make([]*Item, 0),
		CurrentIndex: 0,
	}

	// Add dynamic USB device items.
	b.AddDynamicItems(menu, "usb_devices")

	// Separator.
	menu.Items = append(menu.Items, NewSeparatorItem("sep1"))

	// Refresh devices.
	refreshItem := NewActionItem("refresh", "🔄 Обновить", "Обновить список устройств", b.createUSBRefreshAction())
	menu.Items = append(menu.Items, refreshItem)

	// Back item.
	menu.Items = append(menu.Items, NewBackItem())

	return menu
}

// BuildRadioMenu builds the radio stations menu.
func (b *DictaphoneBuilder) BuildRadioMenu() *Menu {
	menu := &Menu{
		ID:           "radio",
		Title:        "Радиостанции",
		Description:  "Радиостанции и подкасты",
		Items:        make([]*Item, 0),
		CurrentIndex: 0,
	}

	// Add dynamic radio station items.
	b.AddDynamicItems(menu, "radio_stations")

	// Back item.
	menu.Items = append(menu.Items, NewBackItem())

	return menu
}

// BuildSystemMenu builds the system menu.
func (b *DictaphoneBuilder) BuildSystemMenu() *Menu {
	menu := &Menu{
		ID:           "system",
		Title:        "Система",
		Description:  "Системные функции",
		Items:        make([]*Item, 0),
		CurrentIndex: 0,
	}

	// System info.
	infoItem := NewActionItem("info", "ℹ️ Информация", "Информация о системе", b.createSystemInfoAction())
	menu.Items = append(menu.Items, infoItem)

	// Disk space.
	diskItem := NewActionItem("disk", "💾 Место на диске", "Информация о свободном месте", b.createDiskSpaceAction())
	menu.Items = append(menu.Items, diskItem)

	// TTS cache management.
	cacheItem := NewActionItem("cache", "🗂️ Кэш TTS", "Управление кэшем синтеза речи", b.createCacheManagementAction())
	menu.Items = append(menu.Items, cacheItem)

	// Separator.
	menu.Items = append(menu.Items, NewSeparatorItem("sep1"))

	// Restart.
	restartItem := NewActionItem("restart", "🔄 Перезапуск", "Перезапустить приложение", b.createRestartAction())
	menu.Items = append(menu.Items, restartItem)

	// Shutdown.
	shutdownItem := NewActionItem("shutdown", "⏻ Выключение", "Выключить систему", b.createShutdownAction())
	menu.Items = append(menu.Items, shutdownItem)

	// Back item.
	menu.Items = append(menu.Items, NewBackItem())

	return menu
}

// AddDynamicItems adds dynamic items to a menu.
func (b *DictaphoneBuilder) AddDynamicItems(menu *Menu, itemType string) error {
	switch itemType {
	case "folders":
		return b.addRecordingFolders(menu)
	case "usb_devices":
		return b.addUSBDevices(menu)
	case "radio_stations":
		return b.addRadioStations(menu)
	default:
		return fmt.Errorf("unsupported dynamic item type: %s", itemType)
	}
}

// RefreshDynamicItems refreshes dynamic menu items.
func (b *DictaphoneBuilder) RefreshDynamicItems(menu *Menu) error {
	// Remove old dynamic items (keep static items).
	var staticItems []*Item
	for _, item := range menu.Items {
		if item.Type == ItemTypeBack || item.Type == ItemTypeSeparator || 
		   strings.HasPrefix(item.ID, "static_") {
			staticItems = append(staticItems, item)
		}
	}

	menu.Items = staticItems

	// Re-add dynamic items based on menu ID.
	switch menu.ID {
	case "playback":
		return b.addRecordingFolders(menu)
	case "usb":
		return b.addUSBDevices(menu)
	case "radio":
		return b.addRadioStations(menu)
	}

	return nil
}

// Helper methods for creating actions.

func (b *DictaphoneBuilder) createRecordingAction(folder string) func(ctx context.Context) error {
	return func(ctx context.Context) error {
		b.logger.Info("Starting recording in folder: %s", folder)
		
		recorder := b.audioManager.GetRecorder()
		if recorder == nil {
			return fmt.Errorf("audio recorder not available")
		}

		// Check if already recording.
		info := recorder.GetRecordingInfo()
		if info.State != audio.StateStopped {
			return fmt.Errorf("recording already in progress")
		}

		// Start recording.
		if err := recorder.StartRecording(ctx, folder); err != nil {
			return fmt.Errorf("failed to start recording: %w", err)
		}

		// Announce start.
		if b.ttsManager != nil {
			go b.ttsManager.PlaySpeech(ctx, fmt.Sprintf("Начинаю запись в папку %s", folder))
		}

		return nil
	}
}

func (b *DictaphoneBuilder) createRecordingStatusAction() func(ctx context.Context) error {
	return func(ctx context.Context) error {
		recorder := b.audioManager.GetRecorder()
		if recorder == nil {
			return fmt.Errorf("audio recorder not available")
		}

		info := recorder.GetRecordingInfo()
		var status string

		switch info.State {
		case audio.StateRecording:
			status = fmt.Sprintf("Идет запись в папку %s. Длительность: %s", 
				info.Folder, formatDuration(info.Duration))
		case audio.StatePaused:
			status = fmt.Sprintf("Запись приостановлена. Папка: %s. Длительность: %s", 
				info.Folder, formatDuration(info.Duration))
		case audio.StateStopped:
			status = "Запись остановлена"
		}

		if b.ttsManager != nil {
			return b.ttsManager.PlaySpeechBlocking(ctx, status)
		}

		return nil
	}
}

func (b *DictaphoneBuilder) createMicrophoneSelectionAction() func(ctx context.Context) error {
	return func(ctx context.Context) error {
		recorder := b.audioManager.GetRecorder()
		if recorder == nil {
			return fmt.Errorf("audio recorder not available")
		}

		devices, err := recorder.GetAvailableDevices()
		if err != nil {
			return fmt.Errorf("failed to get audio devices: %w", err)
		}

		if len(devices) == 0 {
			if b.ttsManager != nil {
				return b.ttsManager.PlaySpeechBlocking(ctx, "Устройства записи не найдены")
			}
			return fmt.Errorf("no recording devices found")
		}

		// Announce available devices.
		var announcement strings.Builder
		announcement.WriteString("Доступные микрофоны: ")
		for i, device := range devices {
			if i > 0 {
				announcement.WriteString(", ")
			}
			announcement.WriteString(fmt.Sprintf("%d: %s", i+1, device.Name))
		}

		if b.ttsManager != nil {
			return b.ttsManager.PlaySpeechBlocking(ctx, announcement.String())
		}

		return nil
	}
}

func (b *DictaphoneBuilder) createPlaybackControlsAction() func(ctx context.Context) error {
	return func(ctx context.Context) error {
		player := b.audioManager.GetPlayer()
		if player == nil {
			return fmt.Errorf("audio player not available")
		}

		info := player.GetPlaybackInfo()
		var status string

		switch info.State {
		case audio.PlaybackPlaying:
			status = fmt.Sprintf("Воспроизводится: %s. Позиция: %s из %s. Громкость: %d%%. Скорость: %.1fx", 
				info.Filename, formatDuration(info.Position), formatDuration(info.Duration), info.Volume, info.Speed)
		case audio.PlaybackPaused:
			status = fmt.Sprintf("Пауза: %s. Позиция: %s из %s", 
				info.Filename, formatDuration(info.Position), formatDuration(info.Duration))
		case audio.PlaybackStopped:
			status = "Воспроизведение остановлено"
		}

		if b.ttsManager != nil {
			return b.ttsManager.PlaySpeechBlocking(ctx, status)
		}

		return nil
	}
}

func (b *DictaphoneBuilder) createTTSSettingsAction() func(ctx context.Context) error {
	return func(ctx context.Context) error {
		if b.ttsManager == nil {
			return fmt.Errorf("TTS manager not available")
		}

		currentVoice := b.ttsManager.GetVoice()
		engine := b.ttsManager.GetEngine()
		voices := b.ttsManager.GetAvailableVoices()

		status := fmt.Sprintf("Текущий голос: %s. Движок: %s. Доступно голосов: %d", 
			currentVoice, engine, len(voices))

		return b.ttsManager.PlaySpeechBlocking(ctx, status)
	}
}

func (b *DictaphoneBuilder) createAudioSettingsAction() func(ctx context.Context) error {
	return func(ctx context.Context) error {
		// Get recording devices.
		recorder := b.audioManager.GetRecorder()
		if recorder == nil {
			return fmt.Errorf("audio recorder not available")
		}

		devices, err := recorder.GetAvailableDevices()
		if err != nil {
			return fmt.Errorf("failed to get audio devices: %w", err)
		}

		status := fmt.Sprintf("Доступно устройств записи: %d", len(devices))

		if b.ttsManager != nil {
			return b.ttsManager.PlaySpeechBlocking(ctx, status)
		}

		return nil
	}
}

func (b *DictaphoneBuilder) createVolumeSettingsAction() func(ctx context.Context) error {
	return func(ctx context.Context) error {
		volume, err := b.audioManager.GetSystemVolume()
		if err != nil {
			return fmt.Errorf("failed to get system volume: %w", err)
		}

		status := fmt.Sprintf("Системная громкость: %d процентов", volume)

		if b.ttsManager != nil {
			return b.ttsManager.PlaySpeechBlocking(ctx, status)
		}

		return nil
	}
}

func (b *DictaphoneBuilder) createUSBAutoMountAction() func(ctx context.Context) error {
	return func(ctx context.Context) error {
		if b.usbManager == nil {
			return fmt.Errorf("USB manager not available")
		}

		autoMount := b.usbManager.IsAutoMount()
		status := fmt.Sprintf("Автомонтирование USB: %s", 
			map[bool]string{true: "включено", false: "выключено"}[autoMount])

		if b.ttsManager != nil {
			return b.ttsManager.PlaySpeechBlocking(ctx, status)
		}

		return nil
	}
}

func (b *DictaphoneBuilder) createUSBRefreshAction() func(ctx context.Context) error {
	return func(ctx context.Context) error {
		if b.ttsManager != nil {
			go b.ttsManager.PlaySpeech(ctx, "Обновляю список устройств")
		}

		// The actual refresh will be handled by the menu refresh mechanism.
		return nil
	}
}

func (b *DictaphoneBuilder) createSystemInfoAction() func(ctx context.Context) error {
	return func(ctx context.Context) error {
		// Get basic system info.
		hostname, _ := os.Hostname()
		
		status := fmt.Sprintf("Система: %s. Диктофон версии 2.0", hostname)

		if b.ttsManager != nil {
			return b.ttsManager.PlaySpeechBlocking(ctx, status)
		}

		return nil
	}
}

func (b *DictaphoneBuilder) createDiskSpaceAction() func(ctx context.Context) error {
	return func(ctx context.Context) error {
		recorder := b.audioManager.GetRecorder()
		if recorder == nil {
			return fmt.Errorf("audio recorder not available")
		}

		hasSpace, freeSpace, err := recorder.CheckDiskSpace()
		if err != nil {
			return fmt.Errorf("failed to check disk space: %w", err)
		}

		freeGB := float64(freeSpace) / (1024 * 1024 * 1024)
		status := fmt.Sprintf("Свободное место: %.1f гигабайт. %s", 
			freeGB, map[bool]string{true: "Достаточно для записи", false: "Мало места для записи"}[hasSpace])

		if b.ttsManager != nil {
			return b.ttsManager.PlaySpeechBlocking(ctx, status)
		}

		return nil
	}
}

func (b *DictaphoneBuilder) createCacheManagementAction() func(ctx context.Context) error {
	return func(ctx context.Context) error {
		if b.ttsManager == nil {
			return fmt.Errorf("TTS manager not available")
		}

		stats := b.ttsManager.GetCacheStats()
		status := fmt.Sprintf("Кэш TTS: %d файлов, размер %.1f мегабайт", 
			stats.ItemCount, float64(stats.Size)/(1024*1024))

		return b.ttsManager.PlaySpeechBlocking(ctx, status)
	}
}

func (b *DictaphoneBuilder) createRestartAction() func(ctx context.Context) error {
	return func(ctx context.Context) error {
		if b.ttsManager != nil {
			b.ttsManager.PlaySpeechBlocking(ctx, "Перезапуск приложения")
		}

		b.logger.Info("Restart requested by user")
		// The actual restart logic would be handled by the main application.
		return fmt.Errorf("restart requested")
	}
}

func (b *DictaphoneBuilder) createShutdownAction() func(ctx context.Context) error {
	return func(ctx context.Context) error {
		if b.ttsManager != nil {
			b.ttsManager.PlaySpeechBlocking(ctx, "Выключение системы")
		}

		b.logger.Info("Shutdown requested by user")
		// The actual shutdown logic would be handled by the main application.
		return fmt.Errorf("shutdown requested")
	}
}

// Helper methods for adding dynamic items.

func (b *DictaphoneBuilder) addRecordingFolders(menu *Menu) error {
	// Get folders from records directory.
	entries, err := os.ReadDir(b.recordsDir)
	if err != nil {
		b.logger.Error("Failed to read records directory: %v", err)
		return err
	}

	var folders []string
	for _, entry := range entries {
		if entry.IsDir() {
			folders = append(folders, entry.Name())
		}
	}

	sort.Strings(folders)

	// Add folder items.
	for _, folder := range folders {
		item := NewActionItem(
			fmt.Sprintf("folder_%s", folder),
			fmt.Sprintf("📁 %s", folder),
			fmt.Sprintf("Записи в папке %s", folder),
			b.createFolderPlaybackAction(folder),
		)
		menu.Items = append(menu.Items, item)
	}

	return nil
}

func (b *DictaphoneBuilder) addUSBDevices(menu *Menu) error {
	if b.usbManager == nil {
		return nil
	}

	devices := b.usbManager.GetMonitor().GetDevices()

	for _, device := range devices {
		var icon string
		var status string

		switch device.State {
		case usb.DeviceMounted:
			icon = "💾"
			status = "подключен"
		case usb.DeviceConnected:
			icon = "🔌"
			status = "не подключен"
		default:
			continue
		}

		item := NewActionItem(
			fmt.Sprintf("usb_%s", strings.ReplaceAll(device.DevicePath, "/", "_")),
			fmt.Sprintf("%s %s (%s)", icon, device.Name, status),
			fmt.Sprintf("Устройство: %s", device.DevicePath),
			b.createUSBDeviceAction(device.DevicePath),
		)
		menu.Items = append(menu.Items, item)
	}

	return nil
}

func (b *DictaphoneBuilder) addRadioStations(menu *Menu) error {
	// This would typically read from a configuration file or directory.
	// For now, we'll add some placeholder items.
	stations := []struct {
		id, name, desc string
	}{
		{"news", "📰 Новости", "Новостные подкасты"},
		{"music", "🎵 Музыка", "Музыкальные станции"},
		{"talk", "🎙️ Разговорные", "Разговорные программы"},
	}

	for _, station := range stations {
		item := NewActionItem(station.id, station.name, station.desc, b.createRadioStationAction(station.id))
		menu.Items = append(menu.Items, item)
	}

	return nil
}

func (b *DictaphoneBuilder) createFolderPlaybackAction(folder string) func(ctx context.Context) error {
	return func(ctx context.Context) error {
		folderPath := filepath.Join(b.recordsDir, folder)
		
		// Get audio files in folder.
		entries, err := os.ReadDir(folderPath)
		if err != nil {
			return fmt.Errorf("failed to read folder: %w", err)
		}

		var audioFiles []string
		for _, entry := range entries {
			if !entry.IsDir() {
				ext := strings.ToLower(filepath.Ext(entry.Name()))
				if ext == ".wav" || ext == ".mp3" {
					audioFiles = append(audioFiles, entry.Name())
				}
			}
		}

		status := fmt.Sprintf("В папке %s найдено %d аудиофайлов", folder, len(audioFiles))

		if b.ttsManager != nil {
			return b.ttsManager.PlaySpeechBlocking(ctx, status)
		}

		return nil
	}
}

func (b *DictaphoneBuilder) createUSBDeviceAction(devicePath string) func(ctx context.Context) error {
	return func(ctx context.Context) error {
		if b.usbManager == nil {
			return fmt.Errorf("USB manager not available")
		}

		info, err := b.usbManager.GetDeviceInfo(devicePath)
		if err != nil {
			return fmt.Errorf("failed to get device info: %w", err)
		}

		status := fmt.Sprintf("Устройство %s. Размер: %s. Состояние: %s", 
			info.Name, usb.FormatSize(info.Size), usb.DeviceStateToString(info.State))

		if b.ttsManager != nil {
			return b.ttsManager.PlaySpeechBlocking(ctx, status)
		}

		return nil
	}
}

func (b *DictaphoneBuilder) createRadioStationAction(stationID string) func(ctx context.Context) error {
	return func(ctx context.Context) error {
		status := fmt.Sprintf("Радиостанция %s пока не реализована", stationID)

		if b.ttsManager != nil {
			return b.ttsManager.PlaySpeechBlocking(ctx, status)
		}

		return nil
	}
}

// Helper functions.

func formatDuration(d time.Duration) string {
	hours := int(d.Hours())
	minutes := int(d.Minutes()) % 60
	seconds := int(d.Seconds()) % 60

	if hours > 0 {
		return fmt.Sprintf("%d:%02d:%02d", hours, minutes, seconds)
	}
	return fmt.Sprintf("%d:%02d", minutes, seconds)
}

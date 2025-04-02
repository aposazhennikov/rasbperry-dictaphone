# Иерархическое меню с озвучкой для незрячих пользователей

Проект представляет собой иерархическое меню с навигацией с помощью клавиш (пульта) и озвучкой всех пунктов меню.

## Требования

Для работы проекта необходимы следующие зависимости:

```
evdev>=1.6.0  # для работы с пультом
gTTS>=2.3.1   # для озвучки текста (бесплатный синтез)
google-cloud-texttospeech>=2.14.1  # для работы с Google Cloud TTS (более качественный)
google-cloud-monitoring>=2.14.1  # для получения статистики использования API
python-vlc>=3.0.20000  # для воспроизведения аудио
python-magic>=0.4.27  # для определения типов файлов
```

Кроме того, проект использует следующие стандартные библиотеки Python:
- os, sys - для работы с файловой системой
- threading, subprocess - для многопоточности и запуска внешних процессов
- hashlib, json - для хеширования и работы с JSON
- datetime - для работы с датами
- glob - для поиска файлов по шаблону
- argparse - для обработки аргументов командной строки

Под Windows для воспроизведения звуков используется PowerShell и System.Media.SoundPlayer.
Под Linux для воспроизведения MP3-файлов требуется `mpg123` и `vlc`.

## Установка

1. Клонируйте репозиторий:
```
git clone <repository-url>
cd <repository-directory>
```

2. Установите зависимости:
```
pip install -r requirements.txt
```

3. Для Linux установите необходимые пакеты:
```
sudo apt-get install mpg123 vlc libmagic1 udisks2  # Debian/Ubuntu
```

4. Установка системной службы для автозапуска:
```bash
# Сделайте скрипт установки исполняемым
chmod +x install_service.sh

# Запустите скрипт установки с правами root
sudo ./install_service.sh
```

После установки служба будет:
- Автоматически запускаться при старте системы
- Автоматически перезапускаться при сбоях
- Использовать виртуальное окружение Python
- Запускать диктофон с настроенными параметрами

### Управление службой

Основные команды для управления службой:
```bash
# Запуск службы
sudo systemctl start dictaphone

# Остановка службы
sudo systemctl stop dictaphone

# Перезапуск службы
sudo systemctl restart dictaphone

# Проверка статуса
sudo systemctl status dictaphone

# Включение автозапуска
sudo systemctl enable dictaphone

# Отключение автозапуска
sudo systemctl disable dictaphone

# Просмотр логов
journalctl -u dictaphone
```

## Использование

### Запуск меню

```
python run_menu.py
```

### Опции командной строки

```
python run_menu.py --help
```

Доступные опции:
- `--no-tts` - отключить озвучку
- `--cache-dir DIR` - указать директорию для кэширования звуков (по умолчанию "/home/aleks/cache_tts")
- `--pre-generate` - предварительно сгенерировать все звуки и выйти
- `--debug` - включить режим отладки с выводом диагностической информации
- `--use-mp3` - использовать MP3 вместо WAV (WAV обычно воспроизводится быстрее)
- `--voice VOICE_ID` - выбрать голос для озвучки (например: ru-RU-Standard-A)
- `--tts-engine {gtts,google_cloud}` - движок для синтеза речи (`gtts` или `google_cloud`)
- `--google-cloud-credentials FILE` - путь к файлу с учетными данными Google Cloud
- `--show-metrics` - показать подробную информацию об использовании Google Cloud API

### Предварительная генерация звуков

Чтобы предварительно сгенерировать все звуки для меню (рекомендуется):

```
python run_menu.py --pre-generate
```

Для генерации озвучки с конкретным голосом:

```
python run_menu.py --pre-generate --voice ru-RU-Standard-B
```

Для генерации озвучки с использованием Google Cloud TTS:

```
python run_menu.py --pre-generate --tts-engine google_cloud --google-cloud-credentials credentials-google-api.json --debug
```

Это создаст все необходимые файлы озвучки в директории `cache_tts`.

## Навигация по меню

- `KEY_UP` - перемещение вверх по меню
- `KEY_DOWN` - перемещение вниз по меню
- `KEY_SELECT` - выбор текущего пункта меню
- `KEY_BACK` - возврат в родительское меню

## Работа с внешними носителями

В меню доступен пункт "Внешний носитель", который позволяет:
- Просматривать подключенные USB-накопители
- Отображать название и размер каждого накопителя
- Просматривать содержимое USB-накопителей
- Копировать файлы на USB-накопители (в разработке)

При отсутствии подключенных USB-накопителей выводится соответствующее сообщение.

### Автоматическое монтирование

Система автоматически монтирует USB-накопители при их подключении, используя `udisks2`. Поддерживаются различные файловые системы:
- FAT32
- NTFS
- exFAT
- ext2/3/4
- и другие

### Безопасное извлечение

Перед физическим отключением USB-накопителя рекомендуется выйти из меню внешнего носителя для корректного размонтирования.

## Доступные голоса

В системе доступны следующие голоса для озвучки:
- `ru-RU-Standard-A` - Женский голос 1 (по умолчанию)
- `ru-RU-Standard-B` - Мужской голос 1
- `ru-RU-Standard-C` - Женский голос 2
- `ru-RU-Standard-D` - Мужской голос 2
- `ru-RU-Standard-E` - Женский голос 3

Выбор голоса доступен через меню: "Настройки" -> "Выбор голоса".
Выбранный голос сохраняется между запусками программы.

## Кастомизация

### Добавление новых пунктов меню

Структура меню задается в методе `create_menu_structure()` класса `MenuManager`. Для добавления новых пунктов измените соответствующий код в файле `menu/menu_manager.py`.

### Настройка озвучки

Для настройки параметров озвучки измените параметры в конструкторе класса `TTSManager` в файле `menu/tts_manager.py`.

### Добавление новых голосов

Для добавления новых голосов измените метод `get_available_voices()` в классе `SettingsManager` в файле `menu/settings_manager.py`.

# Raspberry Dictaphone

Автоматизированная система для записи и воспроизведения голосовых сообщений на Raspberry Pi с поддержкой голосового управления и TTS.

## Основные возможности

- Запись голосовых сообщений с автоматическим сохранением
- Воспроизведение записей с поддержкой навигации
- Голосовое управление через распознавание речи
- Озвучка интерфейса с поддержкой offline режима
- Управление через кнопки и голосовые команды
- Автоматическое сохранение записей с датировкой
- Поддержка различных языков (русский, английский)
- Кэширование TTS для быстрого воспроизведения
- Автоматическое переключение между online и offline TTS

## Требования

- Raspberry Pi (тестировано на Raspberry Pi 4)
- Python 3.7+
- Микрофон USB
- Динамики или наушники
- Кнопки для управления (опционально)
- Интернет-соединение (для online TTS)

## Установка

1. Клонируйте репозиторий:
```bash
git clone https://github.com/yourusername/raspberry-dictaphone.git
cd raspberry-dictaphone
```

2. Установите зависимости:
```bash
pip install -r requirements.txt
```

3. Установите системные зависимости:
```bash
sudo apt-get update
sudo apt-get install -y \
    portaudio19-dev \
    python3-pyaudio \
    espeak-ng \
    sox \
    mpg123 \
    aplay \
    paplay
```

4. Настройте права доступа:
```bash
sudo usermod -a -G audio $USER
sudo usermod -a -G gpio $USER
```

## Настройка

1. Создайте файл конфигурации `config.json`:
```json
{
    "recordings_dir": "/path/to/recordings",
    "cache_dir": "/path/to/cache",
    "language": "ru",
    "voice": "ru-RU-Standard-A",
    "tts_engine": "google_cloud",
    "debug": false
}
```

2. Настройте параметры записи в `config.json`:
```json
{
    "sample_rate": 44100,
    "channels": 1,
    "chunk_size": 1024,
    "format": "wav"
}
```

## Использование

1. Запустите приложение:
```bash
python3 main.py
```

2. Управление:
- Нажмите кнопку записи или скажите "Начать запись" для начала записи
- Нажмите кнопку остановки или скажите "Остановить запись" для остановки
- Используйте кнопки навигации или голосовые команды для управления воспроизведением
- Скажите "Выйти" для завершения работы

## Особенности TTS

Система поддерживает два режима работы TTS:

1. Online режим (по умолчанию):
   - Использует Google Cloud TTS или gTTS
   - Высокое качество озвучки
   - Требует интернет-соединение

2. Offline режим:
   - Использует espeak-ng
   - Автоматически активируется при отсутствии интернета
   - Не требует подключения к интернету

### Кэширование TTS

- Все сгенерированные аудиофайлы кэшируются
- При повторном использовании текста используется кэшированная версия
- Поддерживается кэширование для разных голосов
- Автоматическая валидация кэшированных файлов

## Устранение неполадок

1. Проблемы с записью:
   - Проверьте подключение микрофона
   - Убедитесь, что у пользователя есть права на запись
   - Проверьте настройки аудио в системе

2. Проблемы с воспроизведением:
   - Проверьте подключение динамиков/наушников
   - Убедитесь, что установлены все необходимые аудио-драйверы
   - Проверьте права доступа к файлам

3. Проблемы с TTS:
   - Проверьте подключение к интернету
   - Убедитесь, что установлен espeak-ng
   - Проверьте права доступа к кэш-директории

## Лицензия

MIT License

## Автор

Ваше имя

## Поддержка

При возникновении проблем создавайте issue в репозитории проекта.
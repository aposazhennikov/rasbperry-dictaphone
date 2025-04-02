"""
Модуль для синтеза речи с использованием espeak-ng (offline TTS)
"""
import os
import tempfile
import subprocess

class EspeakTTSManager:
    """
    Менеджер для offline TTS с использованием espeak-ng
    """
    
    def __init__(self, debug=False, settings_manager=None):
        """
        Инициализация менеджера
        
        Args:
            debug (bool): Режим отладки
            settings_manager: Менеджер настроек для получения громкости
        """
        self.debug = debug
        self.settings_manager = settings_manager
        
    def speak(self, text):
        """
        Синтезирует речь из текста используя espeak-ng
        
        Args:
            text (str): Текст для озвучивания
        """
        try:
            # Создаем временный WAV файл
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp:
                temp_wav = temp.name
            
            # Формируем команду для espeak-ng
            cmd = [
                "espeak-ng",
                "-v", "ru",  # Используем русский голос
                "-s", "150",  # Скорость речи
                "-p", "50",  # Высота голоса
                "-a", "200",  # Громкость (0-200)
                "-w", temp_wav,  # Выходной WAV файл
                text
            ]
            
            if self.debug:
                print(f"[ESPEAK] Озвучивание текста: {text}")
            
            # Запускаем espeak-ng для создания WAV файла
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            
            # Воспроизводим WAV файл
            play_cmd = ["aplay", temp_wav]
            subprocess.run(play_cmd, check=True)
            
            # Удаляем временный файл
            if os.path.exists(temp_wav):
                os.remove(temp_wav)
                
        except subprocess.CalledProcessError as e:
            if self.debug:
                print(f"[ESPEAK ERROR] Ошибка при выполнении команды: {e}")
        except Exception as e:
            if self.debug:
                print(f"[ESPEAK ERROR] Ошибка при озвучивании: {e}")
                
    def play_speech_blocking(self, text):
        """
        Синтезирует речь из текста используя espeak-ng
        
        Args:
            text (str): Текст для озвучивания
            
        Returns:
            bool: True если озвучивание успешно, иначе False
        """
        try:
            if self.debug:
                print(f"[ESPEAK] Озвучивание текста: {text}")
            
            # Получаем системную громкость
            volume = 100  # По умолчанию
            if self.settings_manager:
                try:
                    volume = self.settings_manager.get_system_volume()
                    if self.debug:
                        print(f"[ESPEAK] Получена системная громкость: {volume}")
                except Exception as vol_error:
                    if self.debug:
                        print(f"[ESPEAK WARNING] Ошибка при получении громкости: {vol_error}")
            
            # Преобразуем громкость из диапазона 0-100 в диапазон 0-200 для espeak
            espeak_volume = int((volume / 100.0) * 200)
            
            if self.debug:
                print(f"[ESPEAK] Установлена громкость {espeak_volume} (из {volume})")
            
            # Создаем временный WAV файл
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp:
                temp_wav = temp.name
            
            # Формируем команду для espeak-ng
            cmd = [
                "espeak-ng",
                "-v", "ru",  # Используем русский голос
                "-s", "150",  # Скорость речи
                "-p", "50",  # Высота голоса
                "-a", str(espeak_volume),  # Используем системную громкость
                "-w", temp_wav,  # Выходной WAV файл
                text
            ]
            
            if self.debug:
                print(f"[ESPEAK] Команда: {' '.join(cmd)}")
            
            # Запускаем espeak-ng для создания WAV файла
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            
            # Воспроизводим WAV файл
            play_cmd = ["aplay", temp_wav]
            subprocess.run(play_cmd, check=True)
            
            # Удаляем временный файл
            if os.path.exists(temp_wav):
                os.remove(temp_wav)
                
            return True
            
        except Exception as e:
            if self.debug:
                print(f"[ESPEAK ERROR] Ошибка при озвучивании: {e}")
            return False 
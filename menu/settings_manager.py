#!/usr/bin/env python3
import os
import json

class SettingsManager:
    """Управление настройками приложения"""
    
    def __init__(self, settings_dir="/home/aleks/cache_tts"):
        """
        Инициализация менеджера настроек
        
        Args:
            settings_dir (str): Директория для хранения настроек
        """
        self.settings_dir = settings_dir
        self.settings_file = os.path.join(settings_dir, "settings.json")
        
        # Настройки по умолчанию
        self.settings = {
            "voice": "ru-RU-Standard-A",  # женский голос по умолчанию
            "tts_engine": "gtts",  # двигатель синтеза речи (gtts или google_cloud)
            "google_cloud_credentials": "credentials-google-api.json"  # путь к файлу с учетными данными
        }
        
        # Создаем директорию для настроек, если она не существует
        if not os.path.exists(settings_dir):
            os.makedirs(settings_dir)
            
        # Загружаем настройки, если они существуют
        self.load_settings()
    
    def load_settings(self):
        """Загружает настройки из файла"""
        if os.path.exists(self.settings_file):
            try:
                with open(self.settings_file, 'r') as f:
                    loaded_settings = json.load(f)
                    # Обновляем только существующие настройки
                    for key, value in loaded_settings.items():
                        if key in self.settings:
                            self.settings[key] = value
            except Exception as e:
                print(f"Ошибка при загрузке настроек: {e}")
    
    def save_settings(self):
        """Сохраняет настройки в файл"""
        try:
            with open(self.settings_file, 'w') as f:
                json.dump(self.settings, f, indent=2)
        except Exception as e:
            print(f"Ошибка при сохранении настроек: {e}")
    
    def get_voice(self):
        """
        Возвращает текущий выбранный голос
        
        Returns:
            str: Идентификатор голоса
        """
        return self.settings["voice"]
    
    def set_voice(self, voice):
        """
        Устанавливает голос для озвучки
        
        Args:
            voice (str): Идентификатор голоса
        """
        available_voices = self.get_available_voices()
        if voice in available_voices:
            self.settings["voice"] = voice
            self.save_settings()
            return True
        return False
    
    def get_tts_engine(self):
        """
        Возвращает текущий выбранный движок TTS
        
        Returns:
            str: Название движка TTS (gtts или google_cloud)
        """
        return self.settings["tts_engine"]
    
    def set_tts_engine(self, engine):
        """
        Устанавливает движок TTS
        
        Args:
            engine (str): Название движка TTS (gtts или google_cloud)
        
        Returns:
            bool: True если успешно, иначе False
        """
        if engine in ["gtts", "google_cloud"]:
            self.settings["tts_engine"] = engine
            self.save_settings()
            return True
        return False
    
    def get_google_cloud_credentials(self):
        """
        Возвращает путь к файлу с учетными данными Google Cloud
        
        Returns:
            str: Путь к файлу
        """
        return self.settings["google_cloud_credentials"]
    
    def set_google_cloud_credentials(self, credentials_file):
        """
        Устанавливает путь к файлу с учетными данными Google Cloud
        
        Args:
            credentials_file (str): Путь к файлу
        
        Returns:
            bool: True если успешно, иначе False
        """
        if os.path.exists(credentials_file):
            self.settings["google_cloud_credentials"] = credentials_file
            self.save_settings()
            return True
        return False
    
    def get_available_voices(self):
        """
        Возвращает список доступных голосов
        
        Returns:
            dict: Словарь доступных голосов {id: описание}
        """
        return {
            "ru-RU-Standard-A": "Женский голос 1",
            "ru-RU-Standard-B": "Мужской голос 1",
            "ru-RU-Standard-C": "Женский голос 2",
            "ru-RU-Standard-D": "Мужской голос 2",
            "ru-RU-Standard-E": "Женский голос 3"
        } 
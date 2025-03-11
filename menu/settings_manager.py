#!/usr/bin/env python3
import os
import json
import sentry_sdk

class SettingsManager:
    """Класс для управления настройками приложения"""
    
    def __init__(self, settings_file="settings.json", debug=False):
        """
        Инициализация менеджера настроек
        
        Args:
            settings_file (str): Путь к файлу настроек
            debug (bool): Режим отладки
        """
        try:
            self.settings_file = settings_file
            self.debug = debug
            
            # Настройки по умолчанию
            self.settings = {
                "voice": "ru-RU-Standard-A",
                "tts_engine": "gtts",
                "google_cloud_credentials": None
            }
            
            # Создаем директорию для файла настроек, если её нет
            os.makedirs(os.path.dirname(os.path.abspath(settings_file)), exist_ok=True)
            
            # Загружаем настройки из файла, если он существует
            self.load_settings()
            
            if self.debug:
                print("SettingsManager инициализирован")
        except Exception as e:
            error_msg = f"Ошибка при инициализации SettingsManager: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
    
    def load_settings(self):
        """Загружает настройки из файла"""
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    loaded_settings = json.load(f)
                    self.settings.update(loaded_settings)
                    
                if self.debug:
                    print(f"Настройки загружены из файла: {self.settings_file}")
                    print(f"Текущие настройки: {self.settings}")
        except Exception as e:
            error_msg = f"Ошибка при загрузке настроек: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
    
    def save_settings(self):
        """Сохраняет настройки в файл"""
        try:
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, ensure_ascii=False, indent=4)
                
            if self.debug:
                print(f"Настройки сохранены в файл: {self.settings_file}")
        except Exception as e:
            error_msg = f"Ошибка при сохранении настроек: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
            
    def get_voice(self):
        """
        Возвращает текущий голос
        
        Returns:
            str: Идентификатор голоса
        """
        try:
            return self.settings.get("voice", "ru-RU-Standard-A")
        except Exception as e:
            error_msg = f"Ошибка при получении голоса: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
            return "ru-RU-Standard-A"
            
    def set_voice(self, voice):
        """
        Устанавливает голос
        
        Args:
            voice (str): Идентификатор голоса
        """
        try:
            self.settings["voice"] = voice
            self.save_settings()
            
            if self.debug:
                print(f"Установлен голос: {voice}")
        except Exception as e:
            error_msg = f"Ошибка при установке голоса: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
            
    def get_tts_engine(self):
        """
        Возвращает текущий движок TTS
        
        Returns:
            str: Название движка ("gtts" или "google_cloud")
        """
        try:
            return self.settings.get("tts_engine", "gtts")
        except Exception as e:
            error_msg = f"Ошибка при получении движка TTS: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
            return "gtts"
            
    def set_tts_engine(self, engine):
        """
        Устанавливает движок TTS
        
        Args:
            engine (str): Название движка ("gtts" или "google_cloud")
        """
        try:
            if engine in ["gtts", "google_cloud"]:
                self.settings["tts_engine"] = engine
                self.save_settings()
                
                if self.debug:
                    print(f"Установлен движок TTS: {engine}")
        except Exception as e:
            error_msg = f"Ошибка при установке движка TTS: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
    
    def get_google_cloud_credentials(self):
        """
        Возвращает путь к файлу с учетными данными Google Cloud
        
        Returns:
            str: Путь к файлу
        """
        try:
            return self.settings["google_cloud_credentials"]
        except Exception as e:
            error_msg = f"Ошибка при получении учетных данных Google Cloud: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
            return None
    
    def set_google_cloud_credentials(self, credentials_file):
        """
        Устанавливает путь к файлу с учетными данными Google Cloud
        
        Args:
            credentials_file (str): Путь к файлу
        
        Returns:
            bool: True если успешно, иначе False
        """
        try:
            if os.path.exists(credentials_file):
                self.settings["google_cloud_credentials"] = credentials_file
                self.save_settings()
                
                if self.debug:
                    print(f"Установлены учетные данные Google Cloud: {credentials_file}")
                return True
            else:
                if self.debug:
                    print(f"Файл учетных данных не существует: {credentials_file}")
                return False
        except Exception as e:
            error_msg = f"Ошибка при установке учетных данных Google Cloud: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
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
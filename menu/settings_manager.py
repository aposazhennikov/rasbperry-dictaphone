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
                "google_cloud_credentials": None,
                "system_volume": 100,  # Добавляем настройку громкости по умолчанию
                "microphone": "built_in"  # Добавляем настройку микрофона по умолчанию
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
            
        Returns:
            bool: True если успешно, иначе False
        """
        try:
            # Логируем начало процесса
            sentry_sdk.add_breadcrumb(
                category="voice",
                message=f"Settings Manager: Начало установки голоса {voice}",
                level="info"
            )
            print(f"[SETTINGS] Запрос на установку голоса: {voice}")
            
            # Получаем текущий голос для логирования
            current_voice = self.get_voice()
            print(f"[SETTINGS] Текущий голос в настройках: {current_voice}")
            
            # Проверяем, существует ли голос в доступных
            available_voices = self.get_available_voices()
            sentry_sdk.add_breadcrumb(
                category="voice",
                message=f"Settings Manager: Доступные голоса: {available_voices}",
                level="info"
            )
            print(f"[SETTINGS] Доступные голоса: {available_voices}")
            
            if voice not in available_voices:
                error_msg = f"Settings Manager: Голос {voice} не найден в списке доступных голосов"
                print(f"[SETTINGS ERROR] {error_msg}")
                sentry_sdk.capture_message(error_msg, level="error")
                return False
                
            # Устанавливаем голос в настройках
            old_voice = self.settings.get("voice", "ru-RU-Standard-A")
            self.settings["voice"] = voice
            
            # Сохраняем настройки в файл
            try:
                self.save_settings()
                print(f"[SETTINGS] Настройки сохранены в файл")
            except Exception as save_error:
                error_msg = f"Ошибка при сохранении настроек: {save_error}"
                print(f"[SETTINGS ERROR] {error_msg}")
                sentry_sdk.capture_exception(save_error)
                # Восстанавливаем старое значение
                self.settings["voice"] = old_voice
                return False
            
            # Проверяем, что голос действительно установлен
            new_voice = self.get_voice()
            if new_voice != voice:
                error_msg = f"Settings Manager: Голос не был установлен: ожидалось {voice}, получено {new_voice}"
                print(f"[SETTINGS ERROR] {error_msg}")
                sentry_sdk.capture_message(error_msg, level="error")
                return False
            
            print(f"[SETTINGS] Голос успешно установлен: {voice}")
            
            # Логируем успешную установку голоса
            sentry_sdk.add_breadcrumb(
                category="voice",
                message=f"Settings Manager: Голос успешно изменен с {old_voice} на {new_voice}",
                level="info"
            )
            
            return True
        except Exception as e:
            error_msg = f"Критическая ошибка при установке голоса в настройках: {e}"
            print(f"[SETTINGS CRITICAL ERROR] {error_msg}")
            sentry_sdk.capture_exception(e)
            return False
            
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

    def get_system_volume(self):
        """
        Возвращает текущую громкость системных сообщений
        
        Returns:
            int: Уровень громкости в процентах (10-100)
        """
        try:
            volume = self.settings.get("system_volume", 100)
            # Убеждаемся, что значение в допустимом диапазоне
            return max(10, min(100, volume))
        except Exception as e:
            error_msg = f"Ошибка при получении громкости: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
            return 100  # Возвращаем максимальную громкость в случае ошибки
            
    def set_system_volume(self, volume):
        """
        Устанавливает громкость системных сообщений
        
        Args:
            volume (int): Уровень громкости в процентах (10-100)
            
        Returns:
            bool: True если успешно, иначе False
        """
        try:
            # Логируем начало процесса
            sentry_sdk.add_breadcrumb(
                category="volume",
                message=f"Settings Manager: Начало установки громкости {volume}%",
                level="info"
            )
            print(f"[SETTINGS] Запрос на установку громкости: {volume}%")
            
            # Проверяем корректность значения
            if not isinstance(volume, (int, float)) or not (10 <= volume <= 100):
                error_msg = f"Settings Manager: Некорректное значение громкости: {volume}%"
                print(f"[SETTINGS ERROR] {error_msg}")
                sentry_sdk.capture_message(error_msg, level="error")
                return False
            
            # Сохраняем текущее значение для возможного восстановления
            old_volume = self.get_system_volume()
            
            # Устанавливаем новое значение
            self.settings["system_volume"] = int(volume)
            
            # Сохраняем настройки в файл
            try:
                self.save_settings()
                print(f"[SETTINGS] Настройки сохранены в файл")
            except Exception as save_error:
                error_msg = f"Ошибка при сохранении настроек: {save_error}"
                print(f"[SETTINGS ERROR] {error_msg}")
                sentry_sdk.capture_exception(save_error)
                # Восстанавливаем старое значение
                self.settings["system_volume"] = old_volume
                return False
            
            # Проверяем, что громкость действительно установлена
            new_volume = self.get_system_volume()
            if new_volume != volume:
                error_msg = f"Settings Manager: Громкость не была установлена: ожидалось {volume}%, получено {new_volume}%"
                print(f"[SETTINGS ERROR] {error_msg}")
                sentry_sdk.capture_message(error_msg, level="error")
                return False
            
            print(f"[SETTINGS] Громкость успешно установлена: {volume}%")
            
            # Логируем успешную установку громкости
            sentry_sdk.add_breadcrumb(
                category="volume",
                message=f"Settings Manager: Громкость успешно изменена с {old_volume}% на {new_volume}%",
                level="info"
            )
            
            return True
            
        except Exception as e:
            error_msg = f"Критическая ошибка при установке громкости в настройках: {e}"
            print(f"[SETTINGS CRITICAL ERROR] {error_msg}")
            sentry_sdk.capture_exception(e)
            return False
            
    def get_microphone(self):
        """
        Возвращает текущий выбранный микрофон
        
        Returns:
            str: Идентификатор микрофона ("built_in" или "usb")
        """
        try:
            return self.settings.get("microphone", "built_in")
        except Exception as e:
            error_msg = f"Ошибка при получении настройки микрофона: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
            return "built_in"  # По умолчанию используем встроенный микрофон
            
    def set_microphone(self, microphone_id):
        """
        Устанавливает текущий микрофон
        
        Args:
            microphone_id (str): Идентификатор микрофона ("built_in" или "usb")
            
        Returns:
            bool: True если успешно, иначе False
        """
        try:
            # Логируем начало процесса
            sentry_sdk.add_breadcrumb(
                category="microphone",
                message=f"Settings Manager: Начало установки микрофона {microphone_id}",
                level="info"
            )
            print(f"[SETTINGS] Запрос на установку микрофона: {microphone_id}")
            
            # Проверяем корректность значения
            if microphone_id not in ["built_in", "usb"]:
                error_msg = f"Settings Manager: Некорректный идентификатор микрофона: {microphone_id}"
                print(f"[SETTINGS ERROR] {error_msg}")
                sentry_sdk.capture_message(error_msg, level="error")
                return False
            
            # Сохраняем текущее значение для возможного восстановления
            old_microphone = self.get_microphone()
            
            # Устанавливаем новое значение
            self.settings["microphone"] = microphone_id
            
            # Сохраняем настройки в файл
            try:
                self.save_settings()
                print(f"[SETTINGS] Настройки сохранены в файл")
            except Exception as save_error:
                error_msg = f"Ошибка при сохранении настроек: {save_error}"
                print(f"[SETTINGS ERROR] {error_msg}")
                sentry_sdk.capture_exception(save_error)
                # Восстанавливаем старое значение
                self.settings["microphone"] = old_microphone
                return False
            
            # Проверяем, что микрофон действительно установлен
            new_microphone = self.get_microphone()
            if new_microphone != microphone_id:
                error_msg = f"Settings Manager: Микрофон не был установлен: ожидался {microphone_id}, получен {new_microphone}"
                print(f"[SETTINGS ERROR] {error_msg}")
                sentry_sdk.capture_message(error_msg, level="error")
                return False
            
            print(f"[SETTINGS] Микрофон успешно установлен: {microphone_id}")
            
            # Логируем успешную установку микрофона
            sentry_sdk.add_breadcrumb(
                category="microphone",
                message=f"Settings Manager: Микрофон успешно изменен с {old_microphone} на {new_microphone}",
                level="info"
            )
            
            return True
            
        except Exception as e:
            error_msg = f"Критическая ошибка при установке микрофона в настройках: {e}"
            print(f"[SETTINGS CRITICAL ERROR] {error_msg}")
            sentry_sdk.capture_exception(e)
            return False 
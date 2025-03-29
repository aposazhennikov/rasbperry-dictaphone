#!/usr/bin/env python3
import sentry_sdk
from .menu_item import MenuItem, SubMenu

class MicrophoneSelector:
    """Класс для выбора микрофона в настройках"""
    
    def __init__(self, menu_manager, settings_manager, debug=False):
        """
        Инициализация селектора микрофона
        
        Args:
            menu_manager: Ссылка на менеджер меню для обновления интерфейса
            settings_manager: Ссылка на менеджер настроек для сохранения выбора
            debug (bool): Режим отладки
        """
        try:
            self.menu_manager = menu_manager
            self.settings_manager = settings_manager
            self.debug = debug
            
            # Создаем подменю для выбора микрофона
            self.microphone_menu = SubMenu("Выбор микрофона")
            
            # Добавляем пункты меню
            self._setup_menu_items()
            
            if self.debug:
                print("MicrophoneSelector инициализирован")
        except Exception as e:
            error_msg = f"Ошибка при инициализации MicrophoneSelector: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
    
    def _setup_menu_items(self):
        """Настраивает пункты меню для выбора микрофона"""
        try:
            # Очищаем текущие пункты меню
            self.microphone_menu.items = []
            
            # Получаем текущий выбранный микрофон
            current_microphone = self.get_microphone()
            
            # Добавляем пункты меню для каждого типа микрофона
            for mic_id, mic_desc in self.get_available_microphones().items():
                # Создаем обертку для избежания проблем с lambda в цикле
                def create_microphone_action(mic_id=mic_id):
                    return lambda: self.change_microphone(mic_id)
                
                # Добавляем индикатор текущего выбора
                display_name = f"{mic_desc}"
                if mic_id == current_microphone:
                    display_name = f"{mic_desc} ✓"
                
                self.microphone_menu.add_item(MenuItem(
                    display_name,
                    create_microphone_action()
                ))
            
            if self.debug:
                print(f"Настроено меню выбора микрофона: {len(self.microphone_menu.items)} пунктов")
        except Exception as e:
            error_msg = f"Ошибка при настройке пунктов меню микрофона: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
    
    def get_menu(self):
        """
        Возвращает подменю для выбора микрофона
        
        Returns:
            SubMenu: Подменю выбора микрофона
        """
        return self.microphone_menu
    
    def get_available_microphones(self):
        """
        Возвращает словарь доступных микрофонов
        
        Returns:
            dict: Словарь {id_микрофона: описание}
        """
        return {
            "built_in": "Встроенный микрофон в пульте",
            "usb": "USB микрофон"
        }
    
    def get_microphone(self):
        """
        Возвращает идентификатор текущего выбранного микрофона
        
        Returns:
            str: Идентификатор микрофона
        """
        try:
            # Получаем значение из настроек, по умолчанию используем встроенный микрофон
            return self.settings_manager.settings.get("microphone", "built_in")
        except Exception as e:
            error_msg = f"Ошибка при получении текущего микрофона: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
            return "built_in"  # По умолчанию используем встроенный микрофон
    
    def change_microphone(self, microphone_id):
        """
        Изменяет текущий выбранный микрофон
        
        Args:
            microphone_id (str): Идентификатор микрофона
            
        Returns:
            bool: True если успешно, иначе False
        """
        try:
            # Логируем начало процесса
            sentry_sdk.add_breadcrumb(
                category="microphone",
                message=f"MicrophoneSelector: Начало смены микрофона на {microphone_id}",
                level="info"
            )
            print(f"[MICROPHONE] Запрос на изменение микрофона: {microphone_id}")
            
            # Проверяем, существует ли микрофон в доступных
            available_microphones = self.get_available_microphones()
            if microphone_id not in available_microphones:
                error_msg = f"MicrophoneSelector: Микрофон {microphone_id} не найден в списке доступных"
                print(f"[MICROPHONE ERROR] {error_msg}")
                sentry_sdk.capture_message(error_msg, level="error")
                return False
            
            # Запоминаем старое значение для возможного восстановления
            old_microphone = self.get_microphone()
            
            # Устанавливаем новое значение
            self.settings_manager.settings["microphone"] = microphone_id
            
            # Сохраняем настройки
            try:
                self.settings_manager.save_settings()
                print(f"[MICROPHONE] Настройки сохранены в файл")
            except Exception as save_error:
                error_msg = f"Ошибка при сохранении настроек: {save_error}"
                print(f"[MICROPHONE ERROR] {error_msg}")
                sentry_sdk.capture_exception(save_error)
                # Восстанавливаем старое значение
                self.settings_manager.settings["microphone"] = old_microphone
                return False
            
            # Обновляем пункты меню для отображения нового выбора
            self._setup_menu_items()
            
            # Озвучиваем выбор, если доступен TTS
            if hasattr(self.menu_manager, "tts_enabled") and self.menu_manager.tts_enabled:
                mic_desc = available_microphones.get(microphone_id, "Неизвестный микрофон")
                self.menu_manager.say(f"Выбран {mic_desc}")
            
            # Обновляем отображение
            if hasattr(self.menu_manager, "display_current_menu"):
                self.menu_manager.display_current_menu()
            
            # Логируем успешное изменение
            sentry_sdk.add_breadcrumb(
                category="microphone",
                message=f"MicrophoneSelector: Микрофон успешно изменен с {old_microphone} на {microphone_id}",
                level="info"
            )
            
            return True
        except Exception as e:
            error_msg = f"Критическая ошибка при изменении микрофона: {e}"
            print(f"[MICROPHONE CRITICAL ERROR] {error_msg}")
            sentry_sdk.capture_exception(e)
            return False 
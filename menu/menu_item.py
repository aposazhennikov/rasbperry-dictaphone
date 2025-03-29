#!/usr/bin/env python3
import sentry_sdk

class MenuItem:
    """Базовый класс для пунктов меню"""
    
    def __init__(self, name, action=None, speech_text=None):
        """
        Инициализация пункта меню
        
        Args:
            name (str): Название пункта меню
            action (callable, optional): Функция, которая будет вызвана при выборе пункта меню
            speech_text (str, optional): Текст для озвучки, если отличается от name
        """
        try:
            self.name = name
            self.action = action
            # Если текст для озвучки не указан, используем название пункта
            self.speech_text = speech_text if speech_text else name
        except Exception as e:
            error_msg = f"Ошибка при инициализации MenuItem: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
    
    def select(self):
        """Вызывается при выборе пункта меню"""
        try:
            if self.action:
                return self.action()
            return None
        except Exception as e:
            error_msg = f"Ошибка при выборе пункта меню '{self.name}': {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
            return None
    
    def get_speech_text(self):
        """Возвращает текст для озвучки"""
        try:
            return self.speech_text
        except Exception as e:
            error_msg = f"Ошибка при получении текста для озвучки: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
            return self.name if hasattr(self, 'name') else "Ошибка"
    
    def get_tts_text(self):
        """Альтернативный метод для получения текста озвучки (для совместимости)"""
        return self.get_speech_text()


class SubMenu(MenuItem):
    """Класс для подменю, содержащего другие пункты меню"""
    
    def __init__(self, name, parent=None, speech_text=None):
        """
        Инициализация подменю
        
        Args:
            name (str): Название подменю
            parent (SubMenu, optional): Родительское меню
            speech_text (str, optional): Текст для озвучки, если отличается от name
        """
        try:
            super().__init__(name, None, speech_text)
            self.parent = parent
            self.items = []
            self.current_selection = 0
            self.on_enter = None  # Добавляем обработчик события входа в меню
        except Exception as e:
            error_msg = f"Ошибка при инициализации SubMenu: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
    
    def add_item(self, item):
        """Добавляет пункт меню в подменю"""
        try:
            self.items.append(item)
            if isinstance(item, SubMenu):
                item.parent = self
        except Exception as e:
            error_msg = f"Ошибка при добавлении пункта меню: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
    
    def select(self):
        """Вызывается при выборе подменю"""
        try:
            # Вызываем обработчик события входа в меню, если он установлен
            if self.on_enter:
                self.on_enter()
                
            # При выборе подменю мы просто возвращаем его самого,
            # чтобы менеджер меню мог переключиться на него
            return self
        except Exception as e:
            error_msg = f"Ошибка при выборе подменю '{self.name}': {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
            return None
    
    def get_current_item(self):
        """Возвращает текущий выбранный пункт меню"""
        try:
            if not self.items:
                return None
            return self.items[self.current_selection]
        except Exception as e:
            error_msg = f"Ошибка при получении текущего пункта меню: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
            return None
    
    def move_up(self):
        """Перемещение вверх по списку пунктов меню (циклически)"""
        try:
            if not self.items:
                return
            self.current_selection = (self.current_selection - 1) % len(self.items)
        except Exception as e:
            error_msg = f"Ошибка при перемещении вверх по меню: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
    
    def move_down(self):
        """Перемещение вниз по списку пунктов меню (циклически)"""
        try:
            if not self.items:
                return
            self.current_selection = (self.current_selection + 1) % len(self.items)
        except Exception as e:
            error_msg = f"Ошибка при перемещении вниз по меню: {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)

# Добавляем псевдоним для SubMenu, чтобы исправить импорты
Menu = SubMenu
#!/usr/bin/env python3

import logging
import sentry_sdk

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class BaseMenu:
    """Базовый класс для всех меню в системе."""
    
    def __init__(self, title: str):
        """
        Инициализация базового меню.
        
        Args:
            title (str): Название меню
        """
        try:
            self.title = title
            self.parent = None
            self.items = []
            logger.info(f"Создано базовое меню: {title}")
        except Exception as e:
            logger.error(f"Ошибка при создании базового меню: {e}")
            sentry_sdk.capture_exception(e)
            raise

    def __str__(self) -> str:
        """
        Строковое представление меню.
        
        Returns:
            str: Название меню
        """
        try:
            return self.get_tts_text()
        except Exception as e:
            logger.error(f"Ошибка при получении строкового представления меню: {e}")
            sentry_sdk.capture_exception(e)
            return "Ошибка меню"

    def __repr__(self) -> str:
        """
        Подробное строковое представление меню.
        
        Returns:
            str: Подробная информация о меню
        """
        try:
            return f"{self.__class__.__name__}(title='{self.title}')"
        except Exception as e:
            logger.error(f"Ошибка при получении подробного представления меню: {e}")
            sentry_sdk.capture_exception(e)
            return "Ошибка меню"

    def get_tts_text(self) -> str:
        """
        Получение текста для озвучки.
        
        Returns:
            str: Текст для озвучки
        """
        try:
            return self.title
        except Exception as e:
            logger.error(f"Ошибка при получении текста для озвучки: {e}")
            sentry_sdk.capture_exception(e)
            return "Ошибка меню"

    def add_item(self, item):
        """
        Добавление пункта в меню.
        
        Args:
            item: Пункт меню для добавления
        """
        try:
            self.items.append(item)
            logger.debug(f"Добавлен пункт меню: {item}")
        except Exception as e:
            logger.error(f"Ошибка при добавлении пункта меню: {e}")
            sentry_sdk.capture_exception(e)
            raise

    def display(self):
        """
        Отображение меню.
        Этот метод должен быть переопределен в дочерних классах.
        """
        raise NotImplementedError("Метод display() должен быть переопределен в дочернем классе")

    def get_title(self) -> str:
        """
        Получение названия меню.
        
        Returns:
            str: Название меню
        """
        try:
            return self.title
        except Exception as e:
            logger.error(f"Ошибка при получении названия меню: {e}")
            sentry_sdk.capture_exception(e)
            return "Ошибка меню"

    def set_parent(self, parent):
        """
        Установка родительского меню.
        
        Args:
            parent: Родительское меню
        """
        try:
            self.parent = parent
        except Exception as e:
            logger.error(f"Ошибка при установке родительского меню: {e}")
            sentry_sdk.capture_exception(e)
            raise

    def get_parent(self):
        """
        Получение родительского меню.
        
        Returns:
            BaseMenu: Родительское меню или None
        """
        try:
            return self.parent
        except Exception as e:
            logger.error(f"Ошибка при получении родительского меню: {e}")
            sentry_sdk.capture_exception(e)
            return None

    def get_items(self):
        """
        Получение списка пунктов меню.
        
        Returns:
            list: Список пунктов меню
        """
        try:
            return self.items
        except Exception as e:
            logger.error(f"Ошибка при получении списка пунктов меню: {e}")
            sentry_sdk.capture_exception(e)
            return [] 
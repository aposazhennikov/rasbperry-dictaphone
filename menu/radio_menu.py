#!/usr/bin/env python3
"""
Модуль для управления меню радиостанций.
"""
import logging
import sentry_sdk
from .menu_item import MenuItem, SubMenu

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class RadioMenu(SubMenu):
    """Класс для управления меню радиостанций"""
    
    def __init__(self, parent=None):
        """
        Инициализация меню радиостанций
        
        Args:
            parent: Родительское меню
        """
        try:
            super().__init__("Радио", parent=parent)
            self._create_radio_structure()
            logger.info("Создано меню радиостанций")
        except Exception as e:
            logger.error(f"Ошибка при создании меню радиостанций: {e}")
            sentry_sdk.capture_exception(e)
            raise
    
    def _create_radio_structure(self):
        """Создает структуру меню радиостанций"""
        try:
            # Создаем список доступных радиостанций
            stations = ["Юмор", "Наука", "Политика", "Трошин", "Шаов", "Природа"]
            
            # Добавляем каждую радиостанцию в меню
            for station in stations:
                station_menu = SubMenu(f"{station}", parent=self)
                self.add_item(station_menu)
                
                # Добавляем пункты управления для каждой радиостанции
                station_menu.add_item(MenuItem("Что сейчас звучит?", lambda s=station: f"Сейчас на {s} звучит: ..."))
                station_menu.add_item(MenuItem("Начать текущую композицию с начала", lambda s=station: f"Перезапуск композиции на {s}"))
                station_menu.add_item(MenuItem("Переключить на предыдущую композицию", lambda s=station: f"Предыдущая композиция на {s}"))
                station_menu.add_item(MenuItem("Переключить на следующую композицию", lambda s=station: f"Следующая композиция на {s}"))
                
            logger.info(f"Создано {len(stations)} радиостанций в меню")
        except Exception as e:
            logger.error(f"Ошибка при создании структуры меню радиостанций: {e}")
            sentry_sdk.capture_exception(e)
            raise
    
    def add_station(self, station_name):
        """
        Добавляет новую радиостанцию в меню
        
        Args:
            station_name (str): Название радиостанции
        
        Returns:
            SubMenu: Созданное подменю для радиостанции
        """
        try:
            station_menu = SubMenu(f"{station_name}", parent=self)
            self.add_item(station_menu)
            
            # Добавляем стандартные пункты управления
            station_menu.add_item(MenuItem("Что сейчас звучит?", lambda s=station_name: f"Сейчас на {s} звучит: ..."))
            station_menu.add_item(MenuItem("Начать текущую композицию с начала", lambda s=station_name: f"Перезапуск композиции на {s}"))
            station_menu.add_item(MenuItem("Переключить на предыдущую композицию", lambda s=station_name: f"Предыдущая композиция на {s}"))
            station_menu.add_item(MenuItem("Переключить на следующую композицию", lambda s=station_name: f"Следующая композиция на {s}"))
            
            logger.info(f"Добавлена новая радиостанция: {station_name}")
            return station_menu
        except Exception as e:
            logger.error(f"Ошибка при добавлении радиостанции {station_name}: {e}")
            sentry_sdk.capture_exception(e)
            return None
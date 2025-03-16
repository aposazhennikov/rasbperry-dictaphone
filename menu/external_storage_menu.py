#!/usr/bin/env python3

import os
import logging
from typing import List, Dict, Optional
import sentry_sdk

# Интеграция с Sentry для отслеживания ошибок
sentry_sdk.init(
    dsn="https://990b663058427f36a87004fc14319c09@o4508953992101888.ingest.de.sentry.io/4508953994330192",
    # Добавляем данные о пользователе и запросах
    send_default_pii=True,
    # Включаем отслеживание исключений в фоновых потоках
    enable_tracing=True,
)

from menu.base_menu import BaseMenu
from utils.usb_manager import USBDeviceManager

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ExternalStorageMenu(BaseMenu):
    """Меню для работы с внешними носителями."""
    
    def __init__(self):
        """Инициализация меню внешних носителей."""
        try:
            super().__init__("Внешний носитель")
            self.usb_manager = USBDeviceManager()
            logger.info("ExternalStorageMenu инициализирован")
        except Exception as e:
            logger.error(f"Ошибка при инициализации ExternalStorageMenu: {e}")
            sentry_sdk.capture_exception(e)
            raise

    def __str__(self) -> str:
        """
        Строковое представление меню.
        
        Returns:
            str: Название меню
        """
        return "Внешний носитель"

    def __repr__(self) -> str:
        """
        Подробное строковое представление меню.
        
        Returns:
            str: Подробная информация о меню
        """
        return "Внешний носитель"

    def get_tts_text(self) -> str:
        """
        Получение текста для озвучки.
        
        Returns:
            str: Текст для озвучки
        """
        try:
            return "Внешний носитель"
        except Exception as e:
            logger.error(f"Ошибка при получении текста для озвучки: {e}")
            sentry_sdk.capture_exception(e)
            return "Ошибка меню"

    def _get_usb_menu_items(self) -> List[Dict[str, str]]:
        """
        Получение списка подключенных USB-накопителей для меню.
        
        Returns:
            List[Dict[str, str]]: Список пунктов меню для USB-накопителей
        """
        try:
            devices = self.usb_manager.get_mounted_usb_devices()
            menu_items = []
            
            for i, device in enumerate(devices, 1):
                # Получаем информацию об устройстве
                device_name = f"Флешка {i}"
                menu_items.append({
                    'title': f"{device_name} ({device['mount_point']})",
                    'mount_point': device['mount_point']
                })
            
            return menu_items
        except Exception as e:
            logger.error(f"Ошибка при получении списка USB-накопителей: {e}")
            sentry_sdk.capture_exception(e)
            return []

    def show_device_menu(self, mount_point: str) -> None:
        """
        Показать меню для конкретного USB-накопителя.
        
        Args:
            mount_point (str): Точка монтирования USB-накопителя
        """
        try:
            while True:
                print("\nМеню USB-накопителя:")
                print("1. Посмотреть файлы на флешке")
                print("2. Скопировать файлы на флешку")
                print("0. Назад")
                
                choice = input("\nВыберите пункт меню: ")
                
                if choice == "1":
                    self.usb_manager.list_files(mount_point)
                elif choice == "2":
                    print("Функция копирования файлов будет добавлена позже")
                elif choice == "0":
                    break
                else:
                    print("Неверный выбор. Попробуйте снова.")
                    
        except Exception as e:
            logger.error(f"Ошибка при работе с меню USB-накопителя: {e}")
            sentry_sdk.capture_exception(e)
            print("Произошла ошибка при работе с USB-накопителем")

    def display(self) -> None:
        """Отображение меню внешних носителей."""
        try:
            while True:
                # Получаем список USB-накопителей
                usb_devices = self._get_usb_menu_items()
                
                if not usb_devices:
                    print("\nПодключенных флешек нет")
                    input("\nНажмите Enter для возврата в главное меню...")
                    break
                
                print("\nДоступные USB-накопители:")
                for i, device in enumerate(usb_devices, 1):
                    print(f"{i}. {device['title']}")
                print("0. Назад")
                
                choice = input("\nВыберите флешку: ")
                
                if choice == "0":
                    break
                    
                try:
                    choice_idx = int(choice) - 1
                    if 0 <= choice_idx < len(usb_devices):
                        self.show_device_menu(usb_devices[choice_idx]['mount_point'])
                    else:
                        print("Неверный выбор. Попробуйте снова.")
                except ValueError:
                    print("Пожалуйста, введите число.")
                    
        except Exception as e:
            logger.error(f"Ошибка при отображении меню внешних носителей: {e}")
            sentry_sdk.capture_exception(e)
            print("Произошла ошибка при работе с меню") 
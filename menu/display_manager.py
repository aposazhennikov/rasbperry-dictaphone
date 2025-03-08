#!/usr/bin/env python3
import os
import sys

class DisplayManager:
    """Класс для отображения меню на экране"""
    
    def __init__(self, menu_manager):
        """
        Инициализация менеджера отображения
        
        Args:
            menu_manager: Менеджер меню
        """
        self.menu_manager = menu_manager
    
    def clear_screen(self):
        """Очищает экран"""
        os.system('cls' if os.name == 'nt' else 'clear')
    
    def display_menu(self):
        """Отображает текущее меню"""
        self.clear_screen()
        
        current_menu = self.menu_manager.current_menu
        if not current_menu:
            return
            
        # Отображаем заголовок меню
        print(f"=== {current_menu.name} ===\n")
        
        # Отображаем пункты меню
        for i, item in enumerate(current_menu.items):
            # Добавляем маркер для текущего выбранного пункта
            prefix = "> " if i == current_menu.current_selection else "  "
            print(f"{prefix}{item.name}")
            
        # Добавляем подсказку для навигации
        print("\n--- Навигация ---")
        print("↑/↓: Перемещение по меню")
        print("Enter: Выбор")
        print("Back: Возврат в предыдущее меню")
        
        # Если включен режим отладки, выводим отладочную информацию
        if self.menu_manager.debug:
            self.display_debug_info()
    
    def display_message(self, message, title=None):
        """
        Отображает сообщение
        
        Args:
            message (str): Текст сообщения
            title (str, optional): Заголовок сообщения
        """
        self.clear_screen()
        
        if title:
            print(f"=== {title} ===\n")
            
        print(message)
        print("\nНажмите любую клавишу для продолжения...")
        
        # Если включен режим отладки, выводим отладочную информацию
        if self.menu_manager.debug:
            self.display_debug_info()
            
    def display_debug_info(self):
        """Отображает отладочную информацию"""
        try:
            debug_info = self.menu_manager.get_debug_info()
            
            print("\n\n=== ОТЛАДОЧНАЯ ИНФОРМАЦИЯ ===")
            print(f"Текущее меню: {debug_info.get('current_menu', 'Неизвестно')}")
            
            # Здесь может быть проблема, т.к. tts_enabled могло быть удалено
            if 'tts_enabled' in debug_info:
                print(f"Озвучка включена: {debug_info['tts_enabled']}")
            
            # Если есть статистика TTS
            if 'tts' in debug_info and debug_info['tts']:
                tts_stats = debug_info['tts']
                print("\n--- Статистика TTS ---")
                print(f"Всего запросов: {tts_stats.get('total_requests', 'н/д')}")
                print(f"Запросов сегодня: {tts_stats.get('today_requests', 'н/д')}")
                print(f"Примерно осталось запросов: {tts_stats.get('remaining_free_requests', 'н/д')}")
                print(f"Использований кэша: {tts_stats.get('cached_used', 'н/д')}")
                print(f"Текущий голос: {tts_stats.get('current_voice', 'н/д')}")
                print(f"Движок TTS: {tts_stats.get('tts_engine', 'н/д')}")
                
            # Если есть метрики Google Cloud TTS
            if 'google_cloud_tts' in debug_info:
                gc_metrics = debug_info['google_cloud_tts']
                print("\n--- Метрики Google Cloud TTS ---")
                for key, value in gc_metrics.items():
                    print(f"{key}: {value}")
        except Exception as e:
            print("\n=== Ошибка отладочной информации ===")
            print(f"Не удалось показать отладочную информацию: {e}")
        
        print("\n=============================\n") 
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
        debug_info = self.menu_manager.get_debug_info()
        
        print("\n\n=== ОТЛАДОЧНАЯ ИНФОРМАЦИЯ ===")
        print(f"Текущее меню: {debug_info['current_menu']}")
        print(f"Озвучка включена: {debug_info['tts_enabled']}")
        
        # Если есть статистика TTS
        if debug_info['tts_stats']:
            tts_stats = debug_info['tts_stats']
            print("\n--- Статистика TTS ---")
            print(f"Всего запросов: {tts_stats['total_requests']}")
            print(f"Запросов сегодня: {tts_stats['today_requests']}")
            print(f"Примерно осталось бесплатных запросов: {tts_stats['remaining_free_requests']}")
            print(f"Использований кэша: {tts_stats['cached_used']}")
            
            if tts_stats['recent_requests']:
                print("\nПоследние запросы:")
                for req in tts_stats['recent_requests'][-5:]:  # Показываем только 5 последних
                    print(f"  {req}")
        
        print("\n=============================\n") 
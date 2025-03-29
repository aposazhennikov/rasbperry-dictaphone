#!/usr/bin/env python3
import threading
import sentry_sdk
from typing import Dict, List, Callable

class EventBus:
    """
    Простая система событий для связи между компонентами.
    Позволяет компонентам подписываться на события и публиковать их.
    """
    
    _instance = None
    _lock = threading.Lock()
    
    @classmethod
    def get_instance(cls):
        """
        Реализация паттерна Singleton для EventBus
        
        Returns:
            EventBus: Единственный экземпляр EventBus
        """
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance
    
    def __init__(self):
        """Инициализация EventBus"""
        self.subscribers: Dict[str, List[Callable]] = {}
        self.lock = threading.Lock()
        self.debug = False
    
    def set_debug(self, debug: bool):
        """
        Устанавливает режим отладки
        
        Args:
            debug (bool): Включить/выключить режим отладки
        """
        self.debug = debug
    
    def subscribe(self, event_name: str, callback: Callable):
        """
        Подписка на событие
        
        Args:
            event_name (str): Имя события
            callback (Callable): Функция обратного вызова
        """
        try:
            with self.lock:
                if event_name not in self.subscribers:
                    self.subscribers[event_name] = []
                self.subscribers[event_name].append(callback)
                
                if self.debug:
                    print(f"EventBus: Подписка на событие '{event_name}', всего подписчиков: {len(self.subscribers[event_name])}")
        except Exception as e:
            error_msg = f"Ошибка при подписке на событие '{event_name}': {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
    
    def unsubscribe(self, event_name: str, callback: Callable):
        """
        Отписка от события
        
        Args:
            event_name (str): Имя события
            callback (Callable): Функция обратного вызова
        """
        try:
            with self.lock:
                if event_name in self.subscribers and callback in self.subscribers[event_name]:
                    self.subscribers[event_name].remove(callback)
                    
                    if self.debug:
                        print(f"EventBus: Отписка от события '{event_name}', осталось подписчиков: {len(self.subscribers[event_name])}")
        except Exception as e:
            error_msg = f"Ошибка при отписке от события '{event_name}': {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)
    
    def publish(self, event_name: str, **kwargs):
        """
        Публикация события
        
        Args:
            event_name (str): Имя события
            **kwargs: Параметры события
        """
        try:
            callbacks = []
            with self.lock:
                if event_name in self.subscribers:
                    callbacks = self.subscribers[event_name].copy()
            
            if self.debug:
                print(f"EventBus: Публикация события '{event_name}' с параметрами {kwargs}, подписчиков: {len(callbacks)}")
            
            # Вызываем коллбэки вне блокировки
            for callback in callbacks:
                try:
                    callback(**kwargs)
                except Exception as callback_error:
                    error_msg = f"Ошибка при вызове обработчика события '{event_name}': {callback_error}"
                    print(error_msg)
                    sentry_sdk.capture_exception(callback_error)
        except Exception as e:
            error_msg = f"Ошибка при публикации события '{event_name}': {e}"
            print(error_msg)
            sentry_sdk.capture_exception(e)

# Константы для названий событий
EVENT_USB_MIC_DISCONNECTED = "usb_microphone_disconnected"
EVENT_RECORDING_SAVED = "recording_saved"
EVENT_RECORDING_FAILED = "recording_failed" 
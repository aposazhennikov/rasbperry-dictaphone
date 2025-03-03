from evdev import InputDevice, list_devices
from config.constants import TARGET_DEVICE_NAME

class RemoteDevice:
    @staticmethod
    def find_remote_device():
        """Найти USB-пульт среди подключенных устройств"""
        devices = [InputDevice(path) for path in list_devices()]
        for dev in devices:
            if dev.name == TARGET_DEVICE_NAME:
                return dev.path
        return None

    @staticmethod
    def get_device():
        """Получить объект устройства"""
        device_path = RemoteDevice.find_remote_device()
        if device_path is None:
            raise RuntimeError("USB пульт не найден")
        return InputDevice(device_path) 
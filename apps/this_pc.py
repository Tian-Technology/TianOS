"""
TianOS 此电脑
本质上就是文件管理器，作为独立桌面应用入口。
"""

APP_NAME = "此电脑"
APP_ICON = "💻"
APP_ICON_FILE = "imageres 105.png"
APP_COLOR = "#00aaff"

from apps.file_manager import FileManager


class ThisPC(FileManager):
    """此电脑：复用文件管理器的全部功能"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("此电脑")
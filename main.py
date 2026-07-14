"""AI Galgame - 大模型驱动视觉小说

使用方法:
    python main.py

所有配置在 config.py 中修改。
日志文件在 data/game.log，方便查看错误信息。
"""

import sys
from PyQt6.QtWidgets import QApplication
from engine.logger import setup_logging
from ui.main_window import MainWindow


def main():
    # 最先初始化日志，确保后续所有输出都被记录
    setup_logging()

    app = QApplication(sys.argv)
    app.setApplicationName("AI Galgame")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()

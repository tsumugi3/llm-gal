"""可复用的 UI 组件"""

from PyQt6.QtWidgets import QMessageBox
from PyQt6.QtCore import Qt


def show_error(parent, title: str, message: str) -> None:
    """显示可选中、可复制文本的错误弹窗"""
    msg = QMessageBox(parent)
    msg.setIcon(QMessageBox.Icon.Critical)
    msg.setWindowTitle(title)
    msg.setText(message)
    flags = msg.textInteractionFlags()
    flags |= Qt.TextInteractionFlag.TextSelectableByMouse
    flags |= Qt.TextInteractionFlag.TextSelectableByKeyboard
    msg.setTextInteractionFlags(flags)
    msg.exec()


def show_info(parent, title: str, message: str) -> None:
    """显示可选中、可复制文本的信息弹窗"""
    msg = QMessageBox(parent)
    msg.setIcon(QMessageBox.Icon.Information)
    msg.setWindowTitle(title)
    msg.setText(message)
    flags = msg.textInteractionFlags()
    flags |= Qt.TextInteractionFlag.TextSelectableByMouse
    flags |= Qt.TextInteractionFlag.TextSelectableByKeyboard
    msg.setTextInteractionFlags(flags)
    msg.exec()


def show_question(parent, title: str, message: str) -> bool:
    """显示带是否按钮的确认弹窗，返回 True 表示用户选 Yes"""
    msg = QMessageBox(parent)
    msg.setIcon(QMessageBox.Icon.Question)
    msg.setWindowTitle(title)
    msg.setText(message)
    flags = msg.textInteractionFlags()
    flags |= Qt.TextInteractionFlag.TextSelectableByMouse
    flags |= Qt.TextInteractionFlag.TextSelectableByKeyboard
    msg.setTextInteractionFlags(flags)
    msg.setStandardButtons(
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
    )
    msg.setDefaultButton(QMessageBox.StandardButton.No)
    return msg.exec() == QMessageBox.StandardButton.Yes

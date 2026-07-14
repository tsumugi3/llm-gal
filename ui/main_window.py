"""主窗口 —— 管理界面切换（设定页 / 游戏页）"""

from PyQt6.QtWidgets import QMainWindow, QStackedWidget
from engine.story_engine import StoryEngine
from engine.save_manager import SaveManager
from models.game_models import GameState
from ui.settings_screen import SettingsScreen
from ui.game_screen import GameScreen
from config import WINDOW_WIDTH, WINDOW_HEIGHT


class MainWindow(QMainWindow):
    """应用主窗口"""

    def __init__(self):
        super().__init__()
        self.game_state = GameState()
        self.story_engine: StoryEngine | None = None
        self.save_manager = SaveManager()

        self.setWindowTitle("✨ AI Galgame - 大模型驱动视觉小说")
        self.setMinimumSize(WINDOW_WIDTH, WINDOW_HEIGHT)

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        self.settings_screen = SettingsScreen()
        self.game_screen = GameScreen()

        self.stack.addWidget(self.settings_screen)  # index 0
        self.stack.addWidget(self.game_screen)       # index 1

        # 新游戏
        self.settings_screen.game_start_requested.connect(self._on_game_start)
        # 继续游戏
        self.settings_screen.game_continue_requested.connect(self._on_game_continue)
        # 返回主菜单
        self.game_screen.back_to_menu_requested.connect(self._on_back_to_menu)

        self.stack.setCurrentIndex(0)
        self._apply_stylesheet()

    def _on_game_start(self, state: GameState):
        self.game_state = state
        self.story_engine = StoryEngine(state)
        self.stack.setCurrentIndex(1)
        self.game_screen.start_game(self.story_engine, self.save_manager)

    def _on_game_continue(self, filename: str):
        """读档继续游戏"""
        try:
            state, history = self.save_manager.load(filename)
            self.game_state = state
            self.story_engine = StoryEngine(state)
            self.story_engine.history = history
            self.story_engine.prompt_builder = type(self.story_engine.prompt_builder)(state)
            self.story_engine._system_blocks = self.story_engine.prompt_builder.build_system_blocks()
            self.story_engine._system_text = "\n\n".join(
                b["text"] for b in self.story_engine._system_blocks
            )
            self.stack.setCurrentIndex(1)
            self.game_screen.continue_game(self.story_engine, self.save_manager)
        except Exception as e:
            from ui.widgets import show_error
            show_error(self, "读档失败", str(e))

    def _on_back_to_menu(self):
        self.stack.setCurrentIndex(0)

    def _apply_stylesheet(self):
        from ui.design_tokens import build_global_stylesheet
        self.setStyleSheet(build_global_stylesheet())

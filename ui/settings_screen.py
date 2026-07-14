"""设定界面 —— 世界观/角色设定 或 AI自动生成"""

import asyncio
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QTextEdit, QLineEdit, QPushButton, QLabel, QSpinBox,
    QListWidget, QListWidgetItem, QFormLayout,
    QGroupBox, QDialog, QDialogButtonBox,
)
from ui.widgets import show_error, show_info, show_question
from PyQt6.QtCore import pyqtSignal, QThread, pyqtSlot
from models.game_models import GameState, WorldSetting, Character
from engine.story_engine import StoryEngine


class WorldGenThread(QThread):
    """后台线程: AI 生成世界观（流式）"""
    delta = pyqtSignal(str)     # 实时文本块
    finished = pyqtSignal(object)  # GameState
    error = pyqtSignal(str)

    def __init__(self, theme: str):
        super().__init__()
        self.theme = theme

    def run(self):
        async def _stream():
            state = GameState()
            engine = StoryEngine(state)
            async for event in engine.generate_world_stream(self.theme):
                if event["type"] == "delta":
                    self.delta.emit(event["text"])
                elif event["type"] == "done":
                    self.finished.emit(event["state"])
                    return

        try:
            asyncio.run(_stream())
        except Exception as e:
            import traceback
            self.error.emit(f"{e}\n\n{traceback.format_exc()}")


class CharacterEditDialog(QDialog):
    """角色编辑弹窗"""

    def __init__(self, char: Character | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("编辑角色")
        self.setMinimumWidth(420)

        layout = QFormLayout(self)
        self.name_edit = QLineEdit(char.name if char else "")
        self.role_edit = QLineEdit(char.role if char else "")
        self.personality_edit = QTextEdit()
        self.personality_edit.setMaximumHeight(80)
        if char:
            self.personality_edit.setPlainText(char.personality)
        self.appearance_edit = QTextEdit()
        self.appearance_edit.setMaximumHeight(80)
        if char:
            self.appearance_edit.setPlainText(char.appearance)
        self.background_edit = QTextEdit()
        self.background_edit.setMaximumHeight(80)
        if char:
            self.background_edit.setPlainText(char.background)
        self.relation_edit = QLineEdit(char.relationship_to_player if char else "")
        self.affinity_spin = QSpinBox()
        self.affinity_spin.setRange(-100, 100)
        self.affinity_spin.setValue(char.initial_affinity if char else 0)

        layout.addRow("姓名:", self.name_edit)
        layout.addRow("身份:", self.role_edit)
        layout.addRow("性格:", self.personality_edit)
        layout.addRow("外貌:", self.appearance_edit)
        layout.addRow("背景:", self.background_edit)
        layout.addRow("与主角关系:", self.relation_edit)
        layout.addRow("初始好感度:", self.affinity_spin)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def get_character(self) -> Character:
        return Character(
            name=self.name_edit.text(),
            role=self.role_edit.text(),
            personality=self.personality_edit.toPlainText(),
            appearance=self.appearance_edit.toPlainText(),
            background=self.background_edit.toPlainText(),
            relationship_to_player=self.relation_edit.text(),
            initial_affinity=self.affinity_spin.value(),
        )


class SettingsScreen(QWidget):
    """游戏设定页面"""
    game_start_requested = pyqtSignal(GameState)
    game_continue_requested = pyqtSignal(str)  # 存档文件名

    def __init__(self):
        super().__init__()
        self._world_state = GameState()
        self._gen_thread: WorldGenThread | None = None
        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(16)

        # 标题
        title = QLabel("✨ AI Galgame 设定")
        title.setStyleSheet("font-size: 28px; font-weight: bold; color: #c4a35a; padding: 8px;")

        subtitle = QLabel("定义你的故事世界，或让AI为你生成一切")
        subtitle.setStyleSheet("font-size: 14px; color: #8a8a9a; padding: 4px;")

        # 配置状态指示器
        from config import PROVIDER, MODEL_ID, ANTHROPIC_API_KEY
        key_status = "✅ API Key 已配置" if ANTHROPIC_API_KEY else "⚠️ API Key 未设置 (请编辑 config.py)"
        status_text = f"后端: {PROVIDER} | 模型: {MODEL_ID} | {key_status}"
        status_label = QLabel(status_text)
        status_label.setStyleSheet(
            "font-size: 12px; padding: 6px 12px; background-color: #0f0f23; "
            "border: 1px solid #533a5e; border-radius: 4px; "
            f"color: {'#c4a35a' if ANTHROPIC_API_KEY else '#e05555'};"
        )

        main_layout.addWidget(title)
        main_layout.addWidget(subtitle)
        main_layout.addWidget(status_label)

        # 标签页
        tabs = QTabWidget()

        # Tab 1: AI 快速生成
        tabs.addTab(self._create_ai_tab(), "🤖 AI 快速生成")

        # Tab 2: 世界观手动设定
        tabs.addTab(self._create_world_tab(), "🌍 世界观设定")

        # Tab 3: 角色手动设定
        tabs.addTab(self._create_characters_tab(), "👥 角色设定")

        main_layout.addWidget(tabs)

        # 开始 / 继续按钮
        btn_layout = QHBoxLayout()
        btn_style = """
            QPushButton {
                font-size: 18px; font-weight: bold;
                padding: 14px 40px; border-radius: 10px;
            }
        """

        self.continue_btn = QPushButton("📂 继续游戏")
        self.continue_btn.setStyleSheet(btn_style + """
            QPushButton { background-color: #16213e; color: #c4a35a; border: 2px solid #533a5e; }
            QPushButton:hover { background-color: #533a5e; }
        """)
        self.continue_btn.clicked.connect(self._on_continue)

        self.start_btn = QPushButton("🎮 开始游戏")
        self.start_btn.setStyleSheet(btn_style + """
            QPushButton { background-color: #c4a35a; color: #1a1a2e; }
            QPushButton:hover { background-color: #d4b36a; }
        """)
        self.start_btn.clicked.connect(self._on_start)

        btn_layout.addStretch()
        btn_layout.addWidget(self.continue_btn)
        btn_layout.addSpacing(16)
        btn_layout.addWidget(self.start_btn)
        btn_layout.addStretch()
        main_layout.addLayout(btn_layout)

    def _create_ai_tab(self) -> QWidget:
        """AI 生成标签页"""
        w = QWidget()
        layout = QVBoxLayout(w)

        hint = QLabel("输入一个主题或一句话描述，AI将自动生成完整的世界观和角色设定")
        hint.setStyleSheet("color: #8a8a9a; font-size: 13px; padding: 8px;")

        self.theme_input = QLineEdit()
        self.theme_input.setPlaceholderText("例如: 一个魔法学院里，学生们与魔法生物签订契约共同成长的故事")
        self.theme_input.setStyleSheet("font-size: 15px; padding: 12px;")

        self.gen_btn = QPushButton("✨ 生成世界观与角色")
        self.gen_btn.clicked.connect(self._on_generate_world)

        self.gen_status = QLabel("")
        self.gen_status.setStyleSheet("color: #8a8a9a; font-size: 13px;")

        self.gen_preview = QTextEdit()
        self.gen_preview.setReadOnly(True)
        self.gen_preview.setPlaceholderText("生成结果将显示在这里...")

        layout.addWidget(hint)
        layout.addWidget(self.theme_input)
        layout.addWidget(self.gen_btn)
        layout.addWidget(self.gen_status)
        layout.addWidget(self.gen_preview)
        return w

    def _create_world_tab(self) -> QWidget:
        """世界观手动设定标签页"""
        w = QWidget()
        layout = QFormLayout(w)
        layout.setSpacing(10)

        self.world_theme = QTextEdit()
        self.world_theme.setMaximumHeight(60)
        self.world_theme.setPlaceholderText("一句话概括你的故事...")

        self.world_era = QLineEdit()
        self.world_era.setPlaceholderText("近未来 / 异世界中世纪 / 现代都市 ...")

        self.world_location = QTextEdit()
        self.world_location.setMaximumHeight(80)
        self.world_location.setPlaceholderText("故事发生的主要地点...")

        self.world_atmosphere = QLineEdit()
        self.world_atmosphere.setPlaceholderText("温馨治愈 / 悬疑惊悚 / 热血冒险 ...")

        self.world_rules = QTextEdit()
        self.world_rules.setMaximumHeight(80)
        self.world_rules.setPlaceholderText("魔法体系、科技水平、特殊法则...")

        self.world_notes = QTextEdit()
        self.world_notes.setMaximumHeight(80)
        self.world_notes.setPlaceholderText("任何补充说明...")

        layout.addRow("主题:", self.world_theme)
        layout.addRow("时代:", self.world_era)
        layout.addRow("地点:", self.world_location)
        layout.addRow("氛围:", self.world_atmosphere)
        layout.addRow("特殊规则:", self.world_rules)
        layout.addRow("补充:", self.world_notes)
        return w

    def _create_characters_tab(self) -> QWidget:
        """角色设定标签页"""
        w = QWidget()
        layout = QVBoxLayout(w)

        btn_row = QHBoxLayout()
        add_btn = QPushButton("+ 添加角色")
        add_btn.clicked.connect(self._on_add_character)
        edit_btn = QPushButton("✏ 编辑选中")
        edit_btn.clicked.connect(self._on_edit_character)
        del_btn = QPushButton("✕ 删除选中")
        del_btn.clicked.connect(self._on_delete_character)
        btn_row.addWidget(add_btn)
        btn_row.addWidget(edit_btn)
        btn_row.addWidget(del_btn)
        btn_row.addStretch()

        self.char_list = QListWidget()

        layout.addLayout(btn_row)
        layout.addWidget(self.char_list)
        return w

    # ─── 事件处理 ─────────────────────────────────────

    def _on_generate_world(self):
        theme = self.theme_input.text().strip()
        if not theme:
            show_info(self, "提示", "请输入主题后再生成")
            return

        self.gen_btn.setEnabled(False)
        self.gen_status.setText("⏳ AI 正在生成世界观...")
        self.gen_preview.clear()

        self._gen_thread = WorldGenThread(theme)
        self._gen_thread.delta.connect(self._on_gen_delta)
        self._gen_thread.finished.connect(self._on_gen_finished)
        self._gen_thread.error.connect(self._on_gen_error)
        self._gen_thread.start()

    @pyqtSlot(str)
    def _on_gen_delta(self, text: str):
        """实时显示流式生成的文本"""
        cursor = self.gen_preview.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertText(text)
        # 自动滚动
        self.gen_preview.verticalScrollBar().setValue(
            self.gen_preview.verticalScrollBar().maximum()
        )

    @pyqtSlot(object)
    def _on_gen_finished(self, state: GameState):
        self._world_state = state
        self.gen_btn.setEnabled(True)
        self.gen_status.setText("✅ 生成完成！你可以在其他标签页中调整设定")

        # 预览
        w = state.world_setting
        chars_text = "\n".join(
            f"**{c.name}** ({c.role}): {c.personality}"
            for c in state.characters.values()
        )
        self.gen_preview.setMarkdown(
            f"## {w.theme}\n\n"
            f"**时代**: {w.era}\n\n**地点**: {w.location}\n\n"
            f"**氛围**: {w.atmosphere}\n\n**特殊规则**: {w.special_rules}\n\n"
            f"---\n\n### 角色\n\n{chars_text}\n\n"
            f"**主角**: {state.player_name}"
        )

        # 更新角色列表
        self.char_list.clear()
        for char in state.characters.values():
            self.char_list.addItem(f"{char.name} ({char.role})")

    @pyqtSlot(str)
    def _on_gen_error(self, msg: str):
        self.gen_btn.setEnabled(True)
        self.gen_status.setText(f"❌ 生成失败: {msg}")
        show_error(self, "生成失败", f"AI 生成世界观时出错:\n\n{msg}")

    def _on_add_character(self):
        dlg = CharacterEditDialog(parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            char = dlg.get_character()
            if char.name:
                self._world_state.characters[char.name] = char
                self.char_list.addItem(f"{char.name} ({char.role})")

    def _on_edit_character(self):
        item = self.char_list.currentItem()
        if not item:
            return
        name = item.text().split(" (")[0]
        char = self._world_state.characters.get(name)
        if not char:
            return
        dlg = CharacterEditDialog(char, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            new_char = dlg.get_character()
            if new_char.name != name:
                del self._world_state.characters[name]
            self._world_state.characters[new_char.name] = new_char
            item.setText(f"{new_char.name} ({new_char.role})")

    def _on_delete_character(self):
        item = self.char_list.currentItem()
        if item:
            name = item.text().split(" (")[0]
            self._world_state.characters.pop(name, None)
            self.char_list.takeItem(self.char_list.row(item))

    def _on_start(self):
        """收集设定并发出开始信号"""
        # 合并手动设定的世界观
        w = self._world_state.world_setting
        w.theme = self.world_theme.toPlainText().strip() or w.theme or "未命名故事"
        if self.world_era.text().strip():
            w.era = self.world_era.text().strip()
        if self.world_location.toPlainText().strip():
            w.location = self.world_location.toPlainText().strip()
        if self.world_atmosphere.text().strip():
            w.atmosphere = self.world_atmosphere.text().strip()
        if self.world_rules.toPlainText().strip():
            w.special_rules = self.world_rules.toPlainText().strip()
        if self.world_notes.toPlainText().strip():
            w.extra_notes = self.world_notes.toPlainText().strip()

        self._world_state.world_setting = w

        # 验证基本设定
        if not self._world_state.world_setting.theme or self._world_state.world_setting.theme == "未命名故事":
            show_info(self, "提示", "请至少设置一个故事主题或使用AI生成")
            return

        self.game_start_requested.emit(self._world_state)

    def _on_continue(self):
        """显示存档列表，选择后继续游戏"""
        from engine.save_manager import SaveManager
        sm = SaveManager()
        saves = sm.list_saves()

        if not saves:
            show_info(self, "提示", "没有找到存档文件")
            return

        # 构建存档列表弹窗
        dlg = QDialog(self)
        dlg.setWindowTitle("选择存档")
        dlg.setMinimumSize(420, 300)
        layout = QVBoxLayout(dlg)

        label = QLabel("选择一个存档继续游戏:")
        label.setStyleSheet("font-size:14px;color:#e0d8c0;")
        layout.addWidget(label)

        lst = QListWidget()
        for s in saves:
            lst.addItem(
                f"{s['slot_name']}  |  第{s['chapter']}章  回合{s['turn_count']}  |  {s['timestamp']}"
            )
        lst.setCurrentRow(0)
        layout.addWidget(lst)

        btn_row = QHBoxLayout()
        ok_btn = QPushButton("继续")
        ok_btn.setStyleSheet("background-color:#c4a35a;color:#1a1a2e;font-weight:bold;padding:8px 24px;")
        cancel_btn = QPushButton("取消")
        cancel_btn.setStyleSheet("padding:8px 24px;")

        def on_ok():
            idx = lst.currentRow()
            if 0 <= idx < len(saves):
                dlg.accept()

        ok_btn.clicked.connect(on_ok)
        cancel_btn.clicked.connect(dlg.reject)
        lst.itemDoubleClicked.connect(lambda: dlg.accept())

        btn_row.addStretch()
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(ok_btn)
        layout.addLayout(btn_row)

        if dlg.exec() == QDialog.DialogCode.Accepted:
            idx = lst.currentRow()
            if 0 <= idx < len(saves):
                self.game_continue_requested.emit(saves[idx]["filename"])

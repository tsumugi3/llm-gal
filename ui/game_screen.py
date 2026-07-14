"""游戏主界面 —— Galgame 风格: 段落式叙事 + 点击继续 + 底部对话框"""

import re
import asyncio
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QTextBrowser,
    QPushButton, QLineEdit, QLabel, QScrollArea, QFrame, QSizePolicy,
)
from PyQt6.QtCore import pyqtSignal, Qt, QTimer, QThread, pyqtSlot, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QFont, QTextCursor
from engine.story_engine import StoryEngine
from engine.save_manager import SaveManager
from models.game_models import GameTurn, Choice
from ui.widgets import show_error, show_info, show_question


class TurnGenThread(QThread):
    """后台线程: 调用 AI 生成下一回合"""
    delta = pyqtSignal(str, str)
    finished = pyqtSignal(object)

    def __init__(self, engine: StoryEngine, choice_text: str, is_start: bool = False):
        super().__init__()
        self.engine = engine
        self.choice_text = choice_text
        self.is_start = is_start

    def run(self):
        completed = False

        async def _run():
            nonlocal completed
            if self.is_start:
                return await self.engine.start_game()
            else:
                async for event in self.engine.player_action_stream(self.choice_text):
                    if event["type"] == "delta":
                        self.delta.emit("delta", event["text"])
                    elif event["type"] == "complete":
                        completed = True
                        self.finished.emit(event["turn"])
                        return

        try:
            print(f"[Thread] Starting: is_start={self.is_start}, choice={self.choice_text[:30]}")
            result = asyncio.run(_run())
            if result is not None:
                print(f"[Thread] Done (start_game)")
                self.finished.emit(result)
            elif not completed:
                # 流式结束但没有 complete 事件 = 异常
                print(f"[Thread] WARNING: stream ended without complete event")
                self.finished.emit("AI 返回了空响应或格式错误，请重试")
            print(f"[Thread] Exit")
        except Exception as e:
            import traceback
            msg = f"{e}\n\n{traceback.format_exc()}"
            print(f"[Thread] ERROR: {msg}")
            self.finished.emit(msg)


class ChoiceButton(QPushButton):
    """选项按钮"""
    def __init__(self, choice: Choice):
        prefix = {"action": "🎯", "dialogue": "💬", "custom": "✏️"}
        super().__init__(f"{prefix.get(choice.type, '▶')} {choice.text}")
        self.choice = choice
        self.setMinimumHeight(44)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet("""
            QPushButton {
                background-color: rgba(22, 33, 62, 0.92);
                color: #e0d8c0;
                border: 2px solid #533a5e;
                border-radius: 10px;
                padding: 12px 18px;
                font-size: 14px;
                text-align: left;
            }
            QPushButton:hover {
                background-color: #533a5e;
                border-color: #c4a35a;
            }
        """)


class GameScreen(QWidget):
    """Galgame 风格游戏主界面

    布局:
    ┌──────────────────────────────────┐
    │         场景 / 背景区域           │
    │    (剧情文本，逐段显示)           │
    │                                  │
    ├──────────────────────────────────┤
    │  [角色名]                        │
    │  对话文本 / 叙述                  │
    │                          ▼      │
    ├──────────────────────────────────┤
    │  选项区域 (出现选择时)            │
    ├──────────────────────────────────┤
    │  [自定义输入]         [确认]      │
    └──────────────────────────────────┘
    """
    back_to_menu_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.engine: StoryEngine | None = None
        self.save_manager: SaveManager | None = None
        self._gen_thread: TurnGenThread | None = None

        # 段落队列: 当前回合的叙事被分割为多个段落
        self._paragraphs: list[str] = []
        self._para_index: int = 0
        self._current_speaker: str = ""

        # 状态: "idle" | "showing" | "waiting_click" | "choices" | "generating"
        self._state: str = "idle"
        self._branch_point: dict | None = None  # 存档分支点信息

        self._init_ui()

    # ═══════════════════════════════════════════════
    # UI 布局
    # ═══════════════════════════════════════════════

    def _init_ui(self):
        self.setStyleSheet(
            "background-color: #0d0d1a;"
            "font-family: 'Microsoft YaHei', 'SimHei', 'Noto Sans SC', sans-serif;"
        )
        main = QVBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)

        # ── 顶部: 标题栏 + 状态 ─────────────────
        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(16, 8, 16, 4)
        self.chapter_label = QLabel("第1章")
        self.chapter_label.setStyleSheet("color:#c4a35a;font-size:14px;font-weight:bold;background:transparent;")
        self.scene_label = QLabel("📍 opening")
        self.scene_label.setStyleSheet("color:#8a8a9a;font-size:12px;background:transparent;")
        self.turn_label = QLabel("")
        self.turn_label.setStyleSheet("color:#5a5a6a;font-size:11px;background:transparent;")
        top_bar.addWidget(self.chapter_label)
        top_bar.addWidget(self.scene_label)
        top_bar.addStretch()

        # 存档按钮
        btn_style = (
            "QPushButton{background:rgba(22,33,62,0.8);color:#c0b8a8;border:1px solid #3a2a4a;"
            "border-radius:6px;padding:4px 10px;font-size:12px;}"
            "QPushButton:hover{background:#533a5e;color:#c4a35a;border-color:#c4a35a;}"
        )
        for text, tooltip, slot in [
            ("存档", "保存当前进度", self._on_save),
            ("读档", "加载之前的存档", self._on_load),
            ("返回", "返回主菜单", self._on_back),
        ]:
            btn = QPushButton(text)
            btn.setToolTip(tooltip)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(slot)
            btn.setStyleSheet(btn_style)
            top_bar.addWidget(btn)

        top_bar.addWidget(self.turn_label)
        main.addLayout(top_bar)

        # ── 中部: 叙事历史区 ─────────────────────
        self.history_display = QTextBrowser()
        self.history_display.setOpenExternalLinks(False)
        self.history_display.setStyleSheet(
            "QTextBrowser{background-color:#0a0a14;color:#c0b8a8;border:none;"
            "padding:12px 20px;font-size:13px;}QScrollBar:vertical{width:6px;"
            "background:#0a0a14;}QScrollBar::handle:vertical{background:#3a2a4a;border-radius:3px;}"
        )
        self.history_display.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        main.addWidget(self.history_display, stretch=1)

        # ── 底部: 对话框区域 ─────────────────────
        dialog_frame = QFrame()
        dialog_frame.setStyleSheet(
            "QFrame{background-color:rgba(10,10,26,0.95);border-top:2px solid #3a2a4a;}"
        )
        dialog_layout = QVBoxLayout(dialog_frame)
        dialog_layout.setContentsMargins(24, 12, 24, 16)
        dialog_layout.setSpacing(4)

        # 角色名标签
        self.speaker_label = QLabel("")
        self.speaker_label.setStyleSheet(
            "color:#c4a35a;font-size:15px;font-weight:bold;background:transparent;padding:0 4px;"
        )
        self.speaker_label.hide()
        dialog_layout.addWidget(self.speaker_label)

        # 对话文本区
        self.dialogue_text = QTextBrowser()
        self.dialogue_text.setOpenExternalLinks(False)
        self.dialogue_text.setFixedHeight(130)
        self.dialogue_text.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.dialogue_text.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.dialogue_text.setStyleSheet(
            "QTextBrowser{background:transparent;color:#e8e0d0;border:none;"
            "font-size:16px;padding:8px 4px;}QTextBrowser:focus{border:none;}"
        )
        # 点击对话框 = 继续
        self.dialogue_text.viewport().installEventFilter(self)
        dialog_layout.addWidget(self.dialogue_text)

        # 继续指示器
        self.continue_hint = QLabel("▼ 点击继续")
        self.continue_hint.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.continue_hint.setStyleSheet("color:#5a5a6a;font-size:12px;background:transparent;padding:0 4px;")
        self.continue_hint.hide()
        dialog_layout.addWidget(self.continue_hint)

        main.addWidget(dialog_frame)

        # ── 选项区域 ────────────────────────────
        self.choices_widget = QWidget()
        self.choices_widget.setStyleSheet("background-color:rgba(10,10,26,0.95);border-top:1px solid #3a2a4a;")
        self.choices_layout = QVBoxLayout(self.choices_widget)
        self.choices_layout.setContentsMargins(24, 10, 24, 10)
        self.choices_layout.setSpacing(6)
        self.choices_widget.hide()
        main.addWidget(self.choices_widget)

        # ── 自定义输入 ──────────────────────────
        input_row = QHBoxLayout()
        input_row.setContentsMargins(16, 6, 16, 10)
        self.custom_input = QLineEdit()
        self.custom_input.setPlaceholderText("输入你想做的事...")
        self.custom_input.setStyleSheet(
            "QLineEdit{background:#0f0f23;color:#e0d8c0;border:1px solid #533a5e;"
            "border-radius:8px;padding:10px 14px;font-size:14px;}"
            "QLineEdit:focus{border-color:#c4a35a;}"
        )
        self.custom_input.returnPressed.connect(self._on_custom_input)
        self.send_btn = QPushButton("确认")
        self.send_btn.clicked.connect(self._on_custom_input)
        self.send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.send_btn.setStyleSheet(
            "QPushButton{background:#16213e;color:#e0d8c0;border:1px solid #533a5e;"
            "border-radius:8px;padding:10px 20px;font-size:14px;}"
            "QPushButton:hover{background:#533a5e;border-color:#c4a35a;}"
        )
        input_row.addWidget(self.custom_input)
        input_row.addWidget(self.send_btn)
        main.addLayout(input_row)

        self._set_input_enabled(False)

    # ═══════════════════════════════════════════════
    # 事件: 点击对话框 = 继续
    # ═══════════════════════════════════════════════

    def eventFilter(self, obj, event):
        if obj is self.dialogue_text.viewport() and event.type() == event.Type.MouseButtonPress:
            self._on_dialogue_clicked()
        return super().eventFilter(obj, event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Space, Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if self._state == "waiting_click":
                self._on_dialogue_clicked()
                return
        super().keyPressEvent(event)

    # ═══════════════════════════════════════════════
    # 公开方法
    # ═══════════════════════════════════════════════

    def start_game(self, engine: StoryEngine, save_manager: SaveManager):
        self.engine = engine
        self.save_manager = save_manager
        self.history_display.clear()
        self.dialogue_text.clear()
        self.speaker_label.hide()
        self.continue_hint.hide()
        self.choices_widget.hide()
        self._state = "idle"
        self._branch_point = None
        self._set_input_enabled(True)
        self._generate_turn("游戏开始", is_start=True)

    def continue_game(self, engine: StoryEngine, save_manager: SaveManager):
        """从存档继续游戏 —— 显示剧情树，从任意节点重来"""
        self.engine = engine
        self.save_manager = save_manager
        self.history_display.clear()
        self.dialogue_text.clear()
        self.speaker_label.hide()
        self.choices_widget.hide()

        # 构建剧情树
        tree = self._build_story_tree()

        if not tree:
            # 没有决策节点，从最后回合继续
            show_info(self, "提示", "存档中没有可回溯的剧情节点，将从最后回合继续。")
            self._fallback_continue()
            return

        # 显示剧情树弹窗
        node = self._show_story_tree_dialog(tree)
        if node is None:
            self._fallback_continue()
            return

        self._branch_point = node

        # 从选定节点截断历史
        self.engine.history = list(node.get("history_snapshot", []))
        self.engine.state.turn_count = node.get("turn_number", 0)

        # 恢复历史显示
        self._rebuild_history_display(node.get("stop_index", -1))

        # 显示节点信息
        s = engine.state
        info = (
            f'<div style="text-align:center;color:#8a8a9a;padding:20px;">'
            f'📂 回到 回合{node["turn_number"]}<br>'
            f'场景: {node.get("scene", "?")}'
            f'</div>'
        )
        self.dialogue_text.setHtml(info)
        self.chapter_label.setText(getattr(s, 'chapter_title', f"第{s.chapter}章"))
        self.scene_label.setText(f"📍 {node.get('scene', '?')}")
        self._update_sidebar()

        # 恢复叙事段落
        narrative = node.get("narrative", "")
        pars = [p.strip() for p in narrative.split("\n\n") if p.strip()]
        self._paragraphs = pars
        self._para_index = 0

        # 用该节点的选项
        choices_data = node.get("choices", [])
        if choices_data:
            from models.game_models import Choice
            self._pending_choices = [Choice(**c) for c in choices_data]
        else:
            self._pending_choices = []

        # 等待点击继续
        self._state = "waiting_click"
        self.continue_hint.setText("▼ 点击继续故事")
        self.continue_hint.show()
        self._set_input_enabled(True)

    def _fallback_continue(self):
        """兜底：无剧情树时从最后回合继续"""
        s = self.engine.state if self.engine else None
        last = self._parse_last_assistant_turn()
        narrative = last.get("narrative", "") if last else ""
        pars = [p.strip() for p in narrative.split("\n\n") if p.strip()]
        self._paragraphs = pars
        self._para_index = 0
        choices_raw = last.get("choices", []) if last else []
        if choices_raw:
            from models.game_models import Choice
            self._pending_choices = [Choice(**c) for c in choices_raw]
        else:
            self._pending_choices = []

        self._rebuild_history_display()
        self.dialogue_text.setHtml(
            '<div style="text-align:center;color:#8a8a9a;padding:20px;">📂 存档已加载</div>'
        )
        if s:
            self.chapter_label.setText(getattr(s, 'chapter_title', f"第{s.chapter}章"))
            self.scene_label.setText(f"📍 {s.current_scene}")
            self._update_sidebar()
        self._state = "waiting_click"
        self.continue_hint.setText("▼ 点击继续故事")
        self.continue_hint.show()
        self._set_input_enabled(True)

    def _build_story_tree(self) -> list[dict]:
        """扫描全部历史，构建剧情树（所有有选项的决策点）"""
        if not self.engine or not self.engine.history:
            return []

        import json, re
        history = self.engine.history
        nodes = []

        for i, msg in enumerate(history):
            if msg.get("role") != "assistant":
                continue
            try:
                text = msg.get("content", "")
                clean = text.strip()
                if clean.startswith("```"):
                    clean = clean.split("\n", 1)[1] if "\n" in clean else clean[3:]
                    if clean.endswith("```"):
                        clean = clean[:-3]
                data = json.loads(clean)
                choices = data.get("choices", [])
                if not choices:
                    continue

                # 找到玩家当时的选项
                original_choice = None
                if i + 1 < len(history) and history[i + 1].get("role") == "user":
                    m = re.search(r'\*\*玩家行动\*\*:\s*(.+)',
                                  history[i + 1].get("content", ""))
                    if m:
                        original_choice = m.group(1).strip()

                # 找到 AI 的回复
                cached_response = None
                if original_choice and i + 2 < len(history) and history[i + 2].get("role") == "assistant":
                    try:
                        rt = history[i + 2].get("content", "").strip()
                        if rt.startswith("```"):
                            rt = rt.split("\n", 1)[1] if "\n" in rt else rt[3:]
                            if rt.endswith("```"):
                                rt = rt[:-3]
                        from models.game_models import GameTurn
                        cached_response = GameTurn.model_validate_json(rt)
                    except Exception:
                        pass

                # 计算回合号
                turn_num = i // 2  # user/assistant 成对

                nodes.append({
                    "index": i,
                    "turn_number": turn_num,
                    "scene": data.get("state_updates", {}).get("current_scene", "?"),
                    "narrative": data.get("narrative", ""),
                    "choices": choices,
                    "original_choice": original_choice,
                    "cached_response": cached_response,
                    "history_snapshot": list(history[:i + 1]),
                    "stop_index": i,
                })
            except Exception:
                continue

        return nodes

    def _show_story_tree_dialog(self, tree: list[dict]) -> dict | None:
        """显示剧情树选择弹窗，返回选中的节点或 None"""
        if not tree:
            show_info(self, "提示", "存档中没有可回溯的剧情节点")
            return None

        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QListWidget, QPushButton, QHBoxLayout, QListWidgetItem

        dlg = QDialog(self)
        dlg.setWindowTitle("📖 剧情树 — 选择回溯节点")
        dlg.setMinimumSize(500, 400)
        layout = QVBoxLayout(dlg)

        layout.addWidget(QLabel("选择一个剧情节点，从该回合重新开始:"))

        lst = QListWidget()
        for node in tree:
            orig = node.get("original_choice") or "(无)"
            choices_preview = " | ".join(
                f"{'✅' if c.get('text', '') == orig else '⬚'} {c.get('text', '')[:15]}"
                for c in (node.get("choices") or [])
            )
            item = QListWidgetItem(
                f"回合{node.get('turn_number', '?')}  [{node.get('scene', '?')}]  → {str(orig)[:20]}\n"
                f"  选项: {choices_preview}"
            )
            lst.addItem(item)
        lst.setCurrentRow(len(tree) - 1)  # 默认选最后一个
        layout.addWidget(lst)

        btn_row = QHBoxLayout()
        ok_btn = QPushButton("从此节点开始")
        ok_btn.setStyleSheet("background:#c4a35a;color:#1a1a2e;font-weight:bold;padding:8px 20px;")
        cancel_btn = QPushButton("取消")
        btn_row.addStretch()
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(ok_btn)
        layout.addLayout(btn_row)

        ok_btn.clicked.connect(dlg.accept)
        cancel_btn.clicked.connect(dlg.reject)
        lst.itemDoubleClicked.connect(lambda: dlg.accept())

        if dlg.exec() != QDialog.DialogCode.Accepted:
            return None

        idx = lst.currentRow()
        if 0 <= idx < len(tree) and tree[idx] is not None:
            return tree[idx]
        return None

    def _rebuild_history_display(self, stop_index: int = -1):
        """从存档历史重建上方历史显示区。

        stop_index: 在此索引处停止（不包含），默认 -1 表示排除最后一个 assistant
        """
        if not self.engine or not self.engine.history:
            return

        import json
        history = self.engine.history
        # 找到停止点
        if stop_index < 0:
            for i in range(len(history) - 1, -1, -1):
                if history[i].get("role") == "assistant":
                    stop_index = i
                    break

        cursor = self.history_display.textCursor()
        for i, msg in enumerate(history):
            if msg.get("role") != "assistant":
                continue
            # 跳过停止点及之后的回合（将重新播放）
            if i >= stop_index:
                continue
            try:
                text = msg.get("content", "")
                if text.startswith("```"):
                    text = text.split("\n", 1)[1] if "\n" in text else text[3:]
                    if text.endswith("```"):
                        text = text[:-3]
                data = json.loads(text)
                narrative = data.get("narrative", "")
                # 分割段落
                for para in narrative.split("\n\n"):
                    para = para.strip()
                    if not para:
                        continue
                    speaker, body = self._parse_paragraph(para)
                    if speaker:
                        cursor.insertHtml(
                            f'<p style="margin:4px 0;">'
                            f'<span style="color:#c4a35a;font-weight:bold;">{speaker}</span>'
                            f'<span style="color:#c0b8a8;">: {body}</span></p>'
                        )
                    else:
                        body_html = body.replace('\n', '<br>')
                        cursor.insertHtml(
                            f'<p style="margin:6px 0;color:#908880;font-style:italic;">{body_html}</p>'
                        )
                # 回合间分隔
                cursor.insertHtml(
                    '<hr style="border:none;border-top:1px solid #2a2a3a;margin:8px 0;">'
                )
            except Exception:
                continue

        # 滚动到底部
        self.history_display.verticalScrollBar().setValue(
            self.history_display.verticalScrollBar().maximum()
        )

    def _parse_last_assistant_turn(self) -> dict | None:
        """从存档历史中解析最后一个助手回复的完整内容"""
        if not self.engine or not self.engine.history:
            return None
        import json
        for msg in reversed(self.engine.history):
            if msg.get("role") != "assistant":
                continue
            try:
                text = msg.get("content", "")
                if text.startswith("```"):
                    text = text.split("\n", 1)[1] if "\n" in text else text[3:]
                    if text.endswith("```"):
                        text = text[:-3]
                return json.loads(text)
            except Exception:
                continue
        return None

    # ═══════════════════════════════════════════════
    # AI 回合生成
    # ═══════════════════════════════════════════════

    def _generate_turn(self, choice_text: str, is_start: bool = False):
        print(f"[UI] _generate_turn: choice={choice_text[:30]}, is_start={is_start}")
        self._state = "generating"
        self._set_input_enabled(False)
        self._clear_choices()
        self.send_btn.setText("⏳")
        self.dialogue_text.clear()
        self.speaker_label.hide()
        self.continue_hint.hide()

        # 生成中提示
        self.dialogue_text.setHtml(
            '<div style="text-align:center;color:#8a8a9a;padding:20px;">⏳ AI 正在生成剧情...</div>'
        )

        self._gen_thread = TurnGenThread(self.engine, choice_text, is_start)
        self._gen_thread.delta.connect(self._on_delta)
        self._gen_thread.finished.connect(self._on_turn_complete)
        self._gen_thread.start()

    @pyqtSlot(str, str)
    def _on_delta(self, event_type: str, text: str):
        """生成中 - 在对话框显示原始输出（完成后会被替换）"""
        if event_type == "delta":
            cursor = self.dialogue_text.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            cursor.insertText(text)
            self.dialogue_text.verticalScrollBar().setValue(
                self.dialogue_text.verticalScrollBar().maximum()
            )

    @pyqtSlot(object)
    def _on_turn_complete(self, result):
        self._state = "idle"
        self.send_btn.setText("确认")
        self._set_input_enabled(True)

        if isinstance(result, str):
            show_error(self, "生成失败", f"AI 生成出错:\n\n{result}")
            return

        turn: GameTurn = result
        self._current_speaker = turn.character_speaker or ""

        # 更新状态
        if turn.chapter_title:
            self.chapter_label.setText(turn.chapter_title)
            if self.engine:
                self.engine.state.chapter_title = turn.chapter_title
        if self.engine:
            s = self.engine.state
            self.turn_label.setText(f"回合{s.turn_count}")
            self.scene_label.setText(f"📍 {s.current_scene}")

        self._update_sidebar()

        # 将叙事分割为段落，逐段显示
        raw = turn.narrative.strip()
        paragraphs = [p.strip() for p in raw.split('\n\n') if p.strip()]
        self._pending_choices = turn.choices  # 提前存储，段落播完后使用

        if paragraphs:
            self._paragraphs = paragraphs
            self._para_index = 0
            self._show_next_paragraph()
        else:
            # 空叙事直接显示选项
            self._show_choices(turn.choices)

    # ═══════════════════════════════════════════════
    # 段落式叙事显示
    # ═══════════════════════════════════════════════

    def _show_next_paragraph(self):
        """显示下一段叙事"""
        if self._para_index >= len(self._paragraphs):
            # 所有段落显示完毕
            self.dialogue_text.clear()
            self.speaker_label.hide()
            self.continue_hint.hide()
            if self._pending_choices:
                # 有选项 → 显示选项
                self._state = "choices"
                self._show_choices(self._pending_choices)
            else:
                # 无选项 → 自动请求下一回合
                self._generate_turn("继续故事")
            return

        para = self._paragraphs[self._para_index]
        self._para_index += 1
        self._state = "showing"

        # 分析段落类型
        speaker, text = self._parse_paragraph(para)

        # 更新角色名
        if speaker:
            self.speaker_label.setText(speaker)
            self.speaker_label.show()
        else:
            self.speaker_label.hide()

        # 显示对话文本（HTML格式）
        html = self._paragraph_to_html(text)
        self.dialogue_text.setHtml(html)

        # 等待点击
        QTimer.singleShot(100, self._ready_for_click)

    def _ready_for_click(self):
        """文本显示完毕，等待点击继续"""
        self._state = "waiting_click"
        # 还有更多段落？显示"点击继续"提示
        if self._para_index < len(self._paragraphs):
            self.continue_hint.setText("▼ 点击继续")
            self.continue_hint.show()
        else:
            # 最后一段 → 显示"点击查看选项"
            self.continue_hint.setText("▼ 点击查看选项")
            self.continue_hint.show()

    def _on_dialogue_clicked(self):
        """点击对话框"""
        if self._state == "waiting_click":
            if self._paragraphs:
                # 将上一段追加到历史（第一次点击跳过，还没有上一段）
                if self._para_index > 0:
                    self._append_to_history(self._paragraphs[self._para_index - 1])
                self._show_next_paragraph()
            elif self._pending_choices:
                # 从存档继续 —— 上次存档时有选项（无剩余段落），重新显示
                self.continue_hint.hide()
                self.dialogue_text.clear()
                self.speaker_label.hide()
                self._show_choices(self._pending_choices)
            else:
                # 从存档继续 —— 没有选项也没有段落，请求下一回合
                self.continue_hint.hide()
                self.dialogue_text.clear()
                self._generate_turn("继续故事")

    def _parse_paragraph(self, para: str) -> tuple[str, str]:
        """解析段落: 返回 (角色名或空, 纯文本)"""
        # 匹配 **角色名**: 对话内容
        m = re.match(r'\*\*(.+?)\*\*:\s*(.+)', para, re.DOTALL)
        if m:
            return m.group(1), m.group(2)
        return "", para

    def _paragraph_to_html(self, text: str) -> str:
        """将段落文本转换为 HTML"""
        # 内心独白: *text* → 斜体
        text = re.sub(r'\*(.+?)\*', r'<i style="color:#a0a0b0;">\1</i>', text)
        # 换行
        text = text.replace('\n', '<br>')
        return (
            f'<div style="font-size:16px;line-height:1.8;color:#e8e0d0;">'
            f'{text}</div>'
        )

    def _append_to_history(self, para: str):
        """将段落追加到上方历史记录区"""
        speaker, text = self._parse_paragraph(para)
        cursor = self.history_display.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)

        if speaker:
            cursor.insertHtml(
                f'<p style="margin:4px 0;">'
                f'<span style="color:#c4a35a;font-weight:bold;">{speaker}</span>'
                f'<span style="color:#c0b8a8;">: {text}</span></p>'
            )
        else:
            # 叙述 → 灰色
            text_html = text.replace('\n', '<br>')
            cursor.insertHtml(
                f'<p style="margin:6px 0;color:#908880;font-style:italic;">{text_html}</p>'
            )

        # 滚动到底部
        self.history_display.verticalScrollBar().setValue(
            self.history_display.verticalScrollBar().maximum()
        )

    # ═══════════════════════════════════════════════
    # 选项
    # ═══════════════════════════════════════════════

    def _show_choices(self, choices: list[Choice]):
        self._pending_choices = choices
        self._clear_choices()
        self._state = "choices"

        if not choices:
            # 无选项 → 提示自由输入
            self.continue_hint.setText("✏️ 请在下方的输入框中自由行动")
            self.continue_hint.show()
            self.custom_input.setFocus()
            return

        self.continue_hint.hide()
        self.choices_widget.show()

        for choice in choices:
            btn = ChoiceButton(choice)
            btn.clicked.connect(lambda checked, c=choice: self._on_choice_clicked(c))
            self.choices_layout.addWidget(btn)

        # 滚动到选项区域
        QTimer.singleShot(50, lambda: self.choices_widget.setFocus())

    def _on_choice_clicked(self, choice: Choice):
        if choice.type == "custom":
            self.custom_input.setFocus()
            self.custom_input.setPlaceholderText(f"自定义: {choice.text} ...")
            return

        self.choices_widget.hide()

        # 检查是否来自存档"剧情树"分支点
        bp = getattr(self, '_branch_point', None)
        if bp and bp.get("original_choice") and bp.get("cached_response"):
            if choice.text.strip() == bp["original_choice"].strip():
                # 相同选项 → 回放缓存的回复，不调API
                self._replay_cached_turn(bp["cached_response"])
                return
            else:
                # 不同选项 → 历史已截断，直接走生成
                pass

        self._branch_point = None
        self._generate_turn(choice.text)

    def _replay_cached_turn(self, turn: GameTurn):
        """回放缓存的回合（不走API），显示叙事段落和后续选项"""
        self._branch_point = None
        raw = turn.narrative.strip()
        paragraphs = [p.strip() for p in raw.split('\n\n') if p.strip()]
        self._pending_choices = turn.choices

        if self.engine:
            self.engine.state.apply_updates(turn.state_updates)
            self.engine.state.turn_count += 1
            # 把缓存的回复加入历史（JSON格式），确保存档时不会丢失
            self.engine.history.append({
                "role": "assistant",
                "content": turn.model_dump_json(indent=2)
            })
            self.turn_label.setText(f"回合{self.engine.state.turn_count}")
            self.scene_label.setText(f"📍 {self.engine.state.current_scene}")
        self._update_sidebar()

        if paragraphs:
            self._paragraphs = paragraphs
            self._para_index = 0
            self._show_next_paragraph()
        else:
            self._show_choices(turn.choices)

    def _on_custom_input(self):
        text = self.custom_input.text().strip()
        if text and self.engine:
            self.custom_input.clear()
            self.custom_input.setPlaceholderText("输入你想做的事...")
            self.choices_widget.hide()
            self.continue_hint.hide()
            self._generate_turn(text)

    def _clear_choices(self):
        while self.choices_layout.count():
            item = self.choices_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    # ═══════════════════════════════════════════════
    # 状态面板
    # ═══════════════════════════════════════════════

    def _update_sidebar(self):
        """更新标题栏中的好感度等信息（简化版）"""
        if not self.engine:
            return
        s = self.engine.state
        parts = []
        if s.relationships:
            parts.append(" | ".join(f"{n}:{v:+d}" for n, v in list(s.relationships.items())[:3]))
        if s.flags:
            parts.append(" | ".join(f"{k}={v}" for k, v in list(s.flags.items())[:2]))
        if parts:
            self.turn_label.setText(f"回合{s.turn_count} | {' | '.join(parts)}")
        else:
            self.turn_label.setText(f"回合{s.turn_count}")

    # ═══════════════════════════════════════════════
    # 存档 & 输入控制
    # ═══════════════════════════════════════════════

    def _set_input_enabled(self, enabled: bool):
        self.custom_input.setEnabled(enabled)
        self.send_btn.setEnabled(enabled)

    def _on_save(self):
        if not self.engine or not self.save_manager:
            return
        filename = self.save_manager.save(self.engine.state, self.engine.history)
        show_info(self, "存档", f"已保存: {filename}")

    def _on_load(self):
        """游戏内读档 —— 弹出存档列表，选定后走剧情树流程"""
        if not self.save_manager:
            return
        saves = self.save_manager.list_saves()
        if not saves:
            show_info(self, "读档", "没有找到存档文件")
            return

        # 弹出存档选择列表
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QListWidget, QPushButton, QHBoxLayout
        dlg = QDialog(self)
        dlg.setWindowTitle("选择存档")
        dlg.setMinimumSize(420, 300)
        layout = QVBoxLayout(dlg)
        layout.addWidget(QLabel("选择一个存档:"))
        lst = QListWidget()
        for s in saves:
            lst.addItem(f"{s['slot_name']}  |  第{s['chapter']}章 回合{s['turn_count']}  |  {s['timestamp']}")
        lst.setCurrentRow(0)
        layout.addWidget(lst)
        btn_row = QHBoxLayout()
        ok_btn = QPushButton("加载")
        ok_btn.setStyleSheet("background:#c4a35a;color:#1a1a2e;font-weight:bold;padding:8px 24px;")
        cancel_btn = QPushButton("取消")
        ok_btn.clicked.connect(dlg.accept)
        cancel_btn.clicked.connect(dlg.reject)
        lst.itemDoubleClicked.connect(lambda: dlg.accept())
        btn_row.addStretch()
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(ok_btn)
        layout.addLayout(btn_row)

        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        idx = lst.currentRow()
        if idx < 0 or idx >= len(saves):
            return

        try:
            state, history = self.save_manager.load(saves[idx]["filename"])
            # 重建 engine 并用 continue_game 走剧情树流程
            self.engine.state = state
            self.engine.history = history
            self.engine.prompt_builder = type(self.engine.prompt_builder)(state)
            self.engine._system_blocks = self.engine.prompt_builder.build_system_blocks()
            self.engine._system_text = "\n\n".join(
                b["text"] for b in self.engine._system_blocks
            )
            self.continue_game(self.engine, self.save_manager)
        except Exception as e:
            show_error(self, "读档失败", str(e))

    def _on_back(self):
        if show_question(self, "返回", "确定返回主菜单吗？\n（未保存的进度将丢失）"):
            self.back_to_menu_requested.emit()

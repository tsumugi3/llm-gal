"""提示词构建器 —— 系统提示 + 上下文组装 (兼容多后端)"""

from models.game_models import GameState, WorldSetting, Character, GameTurn
from config import MAX_HISTORY_TURNS, PROVIDER


SYSTEM_PROMPT_TEMPLATE = """# 你是 Galgame 叙事引擎

你是一个专业的美少女游戏(Galgame)叙事AI。你的任务是根据玩家选择的行动，生成沉浸式的视觉小说叙事。

## 核心规则

1. **叙事风格**: 使用生动、细腻的中文描写。包含环境描写、角色动作、内心独白、对话。
2. **角色驱动**: 每个角色必须符合自己的性格设定。角色行为应前后一致。
3. **段落控制**: 每个自然段之间用空行(\\n\\n)分隔。一段=一个画面=一次点击。每段控制在1-3句话，不要在一个段落中塞入过多内容。对话和叙述要交替进行。
4. **对话格式**: 角色对话使用 **角色名**: 内容 的格式。叙述和描写直接使用普通文本。
5. **分支设计**: 在关键剧情节点，提供2-4个有意义的选择。选择应有不同的后果。
6. **状态追踪**: 在 state_updates 中记录你做的每个重要决定（flag、好感度变化等）。
7. **章节结构**: 当剧情发生重大转折时，可以设置 chapter_title。
8. **结局触发**: 当故事到达自然终点时，设置 is_ending=true 并给出 ending_title。

## 段落划分示例

以下是好的段落划分:
```
教室的午后阳光透过窗户洒进来，在地板上拉出长长的光影。

**艾拉**: 喂，你这个笨蛋，今天又迟到了。

她虽然嘴上不饶人，但还是把笔记推到了我面前。

*真是个不坦率的家伙...*

**艾拉**: 下次再迟到，我可不管你了。
```

## 选项设计指南

- 每个关键节点提供 2-4 个选项
- 至少包含一个 "custom" 类型的选项（text 为 "自由行动"），让玩家输入自定义行为
- 选项之间应有明显不同的方向（比如: 战斗 vs 对话、信任 vs 怀疑、前进 vs 后退）
- 不要在简单的对话回应处提供过多选项，让叙事流畅进行

## 好感度变化参考

- 小的好感互动: ±1~3
- 重要的好感互动: ±5~10
- 重大事件（表白、背叛等）: ±15~25
- 好感度范围: -100 ~ 100

## 输出格式

你必须严格按以下 JSON Schema 输出，不要包含任何其他文字:"""

# JSON Schema 作为提示词的一部分（DeepSeek 不支持 output_config.format）
OUTPUT_SCHEMA_PROMPT = f"""
```json
{GameTurn.model_json_schema()}
```

字段说明:
- narrative: 叙事文本(支持markdown)。**角色名**:对话 / *斜体*:内心独白 / 普通文本:叙述
- character_speaker: 当前说话的角色名(null表示旁白)
- choices: 选项列表。id唯一标识 / text显示文本 / type为action|dialogue|custom
- state_updates: 状态变更。flags_set设置flag / relationship_changes好感度变化 / current_scene场景 / plot_points_triggered剧情点 / items_gained获得物品 / items_lost失去物品
- is_ending: 是否结局
- ending_title: 结局标题(仅在is_ending=true时)
- chapter_title: 新章节标题(仅在进入新章节时)
"""


class PromptBuilder:
    """构建发送给 LLM 的完整提示词"""

    def __init__(self, state: GameState):
        self.state = state

    def build_system_blocks(self) -> list[dict]:
        """构建系统提示块"""
        blocks = [
            {"type": "text", "text": SYSTEM_PROMPT_TEMPLATE},
            {"type": "text", "text": self._build_world_block()},
            {"type": "text", "text": self._build_characters_block()},
            {"type": "text", "text": OUTPUT_SCHEMA_PROMPT},
        ]
        # 仅 Anthropic 官方 API 使用缓存
        if PROVIDER == "anthropic":
            blocks[-1]["cache_control"] = {"type": "ephemeral"}
        return blocks

    def build_user_prompt(self, content: str) -> str:
        """构建带格式要求的 user prompt"""
        return content + "\n\n请严格按照上述 JSON Schema 输出你的回复。"

    def _build_world_block(self) -> str:
        """构建世界观描述块"""
        w = self.state.world_setting
        lines = ["# 世界观设定", f"**主题**: {w.theme}"]
        if w.era:
            lines.append(f"**时代**: {w.era}")
        if w.location:
            lines.append(f"**地点**: {w.location}")
        if w.atmosphere:
            lines.append(f"**氛围**: {w.atmosphere}")
        if w.special_rules:
            lines.append(f"**特殊规则**: {w.special_rules}")
        if w.extra_notes:
            lines.append(f"**补充**: {w.extra_notes}")
        return "\n".join(lines)

    def _build_characters_block(self) -> str:
        """构建角色档案块"""
        if not self.state.characters:
            return "# 角色\n（由AI根据主题自行创作）"

        lines = ["# 角色档案"]
        for name, char in self.state.characters.items():
            lines.append(f"\n## {name}")
            if char.role:
                lines.append(f"- **身份**: {char.role}")
            if char.personality:
                lines.append(f"- **性格**: {char.personality}")
            if char.appearance:
                lines.append(f"- **外貌**: {char.appearance}")
            if char.background:
                lines.append(f"- **背景**: {char.background}")
            if char.relationship_to_player:
                lines.append(f"- **与{self.state.player_name}的关系**: {char.relationship_to_player}")
        return "\n".join(lines)

    def build_messages(self, history: list[dict]) -> list[dict]:
        """构建 messages 数组: 历史 + 状态注入（深拷贝，不修改原始历史）"""
        import copy
        messages = copy.deepcopy(list(history[-MAX_HISTORY_TURNS * 2:]))

        # 在最后一条 user turn 前注入状态摘要
        state_text = self.state.get_state_summary()
        if messages:
            for m in reversed(messages):
                if m["role"] == "user":
                    m["content"] = state_text + "\n\n---\n\n" + m["content"]
                    break

        return messages

    @staticmethod
    def build_player_turn(choice_text: str) -> str:
        """构建玩家行动的 user message"""
        return f"**玩家行动**: {choice_text}\n\n请继续叙事，并生成下一组选项。"

    @staticmethod
    def build_first_turn() -> str:
        """构建游戏开始的第一条 user message"""
        return "游戏开始！请从opening场景开始叙事，介绍世界观和主要角色的出场，并在关键节点提供选项。"

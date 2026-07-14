"""游戏数据模型 —— Pydantic 定义，用于结构化输出和状态管理"""

from dataclasses import dataclass, field
from typing import Any, Optional
from pydantic import BaseModel


# ─── 结构化输出模型 (Claude API 返回) ───────────────────────

class Choice(BaseModel):
    """单个选项"""
    id: str                                     # 选项唯一ID，如 "choice_a"
    text: str                                   # 选项显示文本
    type: str = "action"                        # "action" | "dialogue" | "custom"
    # action: 行为选项 / dialogue: 对话选项 / custom: 暗示玩家自由输入


class StateUpdates(BaseModel):
    """AI 返回的状态变更"""
    flags_set: dict[str, str] = {}              # 设置/更新 flag，如 {"met_mentor": "true"}
    flags_clear: list[str] = []                 # 清除的 flag
    relationship_changes: dict[str, int] = {}   # 角色好感度变化，如 {"elara": 5, "kane": -3}
    current_scene: Optional[str] = None         # 当前场景标识
    plot_points_triggered: list[str] = []       # 新触发的剧情点
    items_gained: list[str] = []                # 获得的物品
    items_lost: list[str] = []                  # 失去的物品


class GameTurn(BaseModel):
    """每回合 AI 返回的完整结构化数据"""
    narrative: str                              # 叙事文本（支持换行）
    character_speaker: Optional[str] = None     # 当前说话的角色名
    choices: list[Choice] = []                  # 可用选项（空列表 = 需要自由输入）
    state_updates: StateUpdates = StateUpdates()
    is_ending: bool = False                     # 是否为结局
    ending_title: Optional[str] = None          # 结局标题（is_ending=True 时）
    chapter_title: Optional[str] = None         # 章节标题（进入新章节时）


# ─── 输入模型 (玩家设定) ─────────────────────────────────

class Character(BaseModel):
    """角色设定"""
    name: str                                   # 角色名
    role: str = ""                              # 身份/职业
    personality: str = ""                       # 性格描述
    appearance: str = ""                        # 外貌描述
    background: str = ""                        # 背景故事
    relationship_to_player: str = ""            # 与主角的关系
    initial_affinity: int = 0                   # 初始好感度 (-100 ~ 100)


class WorldSetting(BaseModel):
    """世界观设定"""
    theme: str                                  # 主题/一句话概括
    era: str = ""                               # 时代背景
    location: str = ""                          # 主要地点
    atmosphere: str = ""                        # 氛围/基调
    special_rules: str = ""                     # 特殊规则（魔法体系、科技水平等）
    extra_notes: str = ""                       # 补充说明


# ─── 运行时游戏状态 ──────────────────────────────────────

@dataclass
class GameState:
    """完整的运行时游戏状态"""
    # 世界观与角色
    world_setting: WorldSetting = field(default_factory=lambda: WorldSetting(theme=""))
    characters: dict[str, Character] = field(default_factory=dict)
    player_name: str = "主角"

    # 动态状态
    flags: dict[str, str] = field(default_factory=dict)
    relationships: dict[str, int] = field(default_factory=dict)  # name → affinity
    inventory: list[str] = field(default_factory=list)
    current_scene: str = "opening"
    triggered_plot_points: list[str] = field(default_factory=list)
    completed_endings: list[str] = field(default_factory=list)

    # 进程
    chapter: int = 1
    chapter_title: str = "第1章"
    turn_count: int = 0

    def apply_updates(self, updates: StateUpdates) -> None:
        """将 AI 返回的状态更新应用到当前状态"""
        if updates.flags_set:
            self.flags.update(updates.flags_set)
        for key in updates.flags_clear:
            self.flags.pop(key, None)
        for name, delta in updates.relationship_changes.items():
            current = self.relationships.get(name, 0)
            self.relationships[name] = max(-100, min(100, current + delta))
        if updates.current_scene:
            self.current_scene = updates.current_scene
        for pp in updates.plot_points_triggered:
            if pp not in self.triggered_plot_points:
                self.triggered_plot_points.append(pp)
        for item in updates.items_gained:
            if item not in self.inventory:
                self.inventory.append(item)
        for item in updates.items_lost:
            if item in self.inventory:
                self.inventory.remove(item)

    def get_state_summary(self) -> str:
        """生成当前状态的文字摘要，注入到提示词中"""
        lines = [f"## 当前状态\n"]
        lines.append(f"- 场景: {self.current_scene}")
        lines.append(f"- 章节: 第{self.chapter}章")
        lines.append(f"- 回合: {self.turn_count}")

        if self.flags:
            lines.append(f"- 关键标志: {', '.join(f'{k}={v}' for k, v in self.flags.items())}")
        if self.relationships:
            rel_str = ", ".join(f"{name}({val})" for name, val in self.relationships.items())
            lines.append(f"- 好感度: {rel_str}")
        if self.inventory:
            lines.append(f"- 物品: {', '.join(self.inventory)}")
        if self.triggered_plot_points:
            lines.append(f"- 已触发剧情: {', '.join(self.triggered_plot_points)}")

        return "\n".join(lines)

    def to_dict(self) -> dict:
        """序列化为字典（用于存档）"""
        return {
            "world_setting": self.world_setting.model_dump(),
            "characters": {k: v.model_dump() for k, v in self.characters.items()},
            "player_name": self.player_name,
            "flags": self.flags,
            "relationships": self.relationships,
            "inventory": self.inventory,
            "current_scene": self.current_scene,
            "triggered_plot_points": self.triggered_plot_points,
            "completed_endings": self.completed_endings,
            "chapter": self.chapter,
            "chapter_title": self.chapter_title,
            "turn_count": self.turn_count,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "GameState":
        """从字典反序列化"""
        state = cls()
        state.world_setting = WorldSetting(**data.get("world_setting", {}))
        state.characters = {k: Character(**v) for k, v in data.get("characters", {}).items()}
        state.player_name = data.get("player_name", "主角")
        state.flags = data.get("flags", {})
        state.relationships = data.get("relationships", {})
        state.inventory = data.get("inventory", [])
        state.current_scene = data.get("current_scene", "opening")
        state.triggered_plot_points = data.get("triggered_plot_points", [])
        state.completed_endings = data.get("completed_endings", [])
        state.chapter = data.get("chapter", 1)
        state.chapter_title = data.get("chapter_title", f"第{state.chapter}章")
        state.turn_count = data.get("turn_count", 0)
        return state

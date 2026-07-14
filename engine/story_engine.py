"""故事引擎 —— 与 LLM API 交互的核心循环
同时支持 Anthropic 官方 API 和 DeepSeek 兼容接口
"""

import json
import anthropic
from typing import AsyncIterator, Optional
from models.game_models import (
    GameTurn, StateUpdates, Choice, GameState,
    WorldSetting, Character,
)
from engine.prompt_builder import PromptBuilder
from config import (
    MODEL_ID, MAX_TOKENS_PER_TURN, SUMMARIZE_EVERY_N_TURNS,
    ANTHROPIC_BASE_URL, ANTHROPIC_API_KEY, PROVIDER,
)


def _extract_text(response) -> str:
    """从 API 响应中安全提取文本"""
    for block in response.content:
        if block.type == "text":
            return block.text
    return ""


def _extract_json(text: str) -> str:
    """从文本中提取 JSON（处理 markdown 代码块包裹的情况）"""
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()


def _make_client() -> anthropic.Anthropic:
    """创建 API 客户端，使用 config.py 中的配置"""
    kwargs = {
        "api_key": ANTHROPIC_API_KEY,
        "timeout": 120.0,       # 120秒超时，防止网络卡死
        "max_retries": 1,       # 仅重试一次
    }
    if ANTHROPIC_BASE_URL:
        kwargs["base_url"] = ANTHROPIC_BASE_URL
    return anthropic.Anthropic(**kwargs)


class StoryEngine:
    """Galgame 叙事引擎，管理与 LLM 的完整交互循环"""

    def __init__(self, state: GameState):
        self.state = state
        self.client = _make_client()
        self.prompt_builder = PromptBuilder(state)
        self.history: list[dict] = []  # 对话历史
        self._system_text: str = ""    # 系统提示（纯文本）

    # ─── 公开 API ───────────────────────────────────────

    async def start_game(self) -> GameTurn:
        """开始新游戏，返回第一个回合"""
        blocks = self.prompt_builder.build_system_blocks()
        self._system_text = "\n\n".join(b["text"] for b in blocks)
        first_message = self.prompt_builder.build_first_turn()
        self.history = [{"role": "user", "content": first_message}]
        return await self._generate_turn(first_message)

    async def player_action(self, choice_text: str) -> GameTurn:
        """玩家做出选择或输入行动，返回下一回合"""
        turn_message = self.prompt_builder.build_player_turn(choice_text)
        self.history.append({"role": "user", "content": turn_message})

        if self.state.turn_count > 0 and self.state.turn_count % SUMMARIZE_EVERY_N_TURNS == 0:
            await self._compact_history()

        return await self._generate_turn(turn_message)

    async def generate_world(self, theme: str) -> GameState:
        """从一句话主题生成完整的世界观和角色设定（非流式）"""
        prompt = self._build_world_gen_prompt(theme)

        kwargs: dict = {
            "model": MODEL_ID,
            "max_tokens": 8000,
            "messages": [{"role": "user", "content": prompt}],
        }
        if PROVIDER == "anthropic":
            kwargs["thinking"] = {"type": "adaptive"}

        response = self.client.messages.create(**kwargs)
        return self._parse_world_response(response)

    async def generate_world_stream(self, theme: str):
        """从一句话主题生成完整的世界观和角色设定（流式版本）

        逐个产出 token，最后返回 GameState。
        用法: async for event in engine.generate_world_stream(theme):
                  if event["type"] == "delta":  print(event["text"], end="")
                  elif event["type"] == "done": state = event["state"]
        """
        prompt = self._build_world_gen_prompt(theme)

        kwargs: dict = {
            "model": MODEL_ID,
            "max_tokens": 8000,
            "messages": [{"role": "user", "content": prompt}],
        }
        if PROVIDER == "anthropic":
            kwargs["thinking"] = {"type": "adaptive"}

        accumulated = []
        with self.client.messages.stream(**kwargs) as stream:
            for text in stream.text_stream:
                accumulated.append(text)
                yield {"type": "delta", "text": text}

        full_text = "".join(accumulated)
        if not full_text.strip():
            raise RuntimeError("API 返回了空响应，请检查 API Key 和网络连接")

        data = json.loads(_extract_json(full_text))
        state = self._apply_world_data(data)
        yield {"type": "done", "state": state}

    def _build_world_gen_prompt(self, theme: str) -> str:
        """构建世界观生成提示词"""
        return f"""请根据以下主题，生成一个完整的Galgame世界观和角色设定。

**主题**: {theme}

请生成:
1. 详细的世界观（时代、地点、氛围、特殊规则）
2. 3-5个主要角色（姓名、身份、性格、外貌、背景、与主角的关系、初始好感度）
3. 主角的设定建议

请严格按JSON格式输出(不要markdown代码块):
{{"world": {{"theme": "...", "era": "...", "location": "...", "atmosphere": "...", "special_rules": "...", "extra_notes": ""}}, "characters": [{{"name": "...", "role": "...", "personality": "...", "appearance": "...", "background": "...", "relationship_to_player": "...", "initial_affinity": 0}}], "player_suggestion": "建议的主角名字和简要背景"}}"""

    def _parse_world_response(self, response) -> GameState:
        """解析世界观生成响应"""
        text = _extract_text(response)
        if not text:
            raise RuntimeError("API 返回了空响应，请检查 API Key 和网络连接")
        data = json.loads(_extract_json(text))
        return self._apply_world_data(data)

    def _apply_world_data(self, data: dict) -> GameState:
        """将 JSON 数据应用到 GameState"""
        world = WorldSetting(**data["world"])
        characters = {}
        for cdata in data.get("characters", []):
            char = Character(**cdata)
            characters[char.name] = char
            self.state.relationships[char.name] = char.initial_affinity

        self.state.world_setting = world
        self.state.characters = characters
        self.state.player_name = data.get("player_suggestion", "主角")
        return self.state

    # ─── 内部方法 ──────────────────────────────────────

    async def _generate_turn(self, user_message: str) -> GameTurn:
        """调用 API 生成下一回合"""
        messages = self.prompt_builder.build_messages(self.history)
        if not messages or messages[-1]["role"] != "user":
            messages.append({"role": "user", "content": user_message})

        kwargs = self._build_request_kwargs(messages)

        response = self.client.messages.create(**kwargs)

        raw_text = _extract_text(response)
        turn = GameTurn.model_validate_json(_extract_json(raw_text))

        self.state.apply_updates(turn.state_updates)
        self.state.turn_count += 1
        self.history.append({"role": "assistant", "content": raw_text})

        return turn

    async def _compact_history(self) -> None:
        """压缩对话历史：将早期回合总结为摘要"""
        if len(self.history) < SUMMARIZE_EVERY_N_TURNS * 2:
            return

        split_point = len(self.history) // 2
        old_history = self.history[:split_point]
        recent_history = self.history[split_point:]

        history_text = "\n".join(
            f"{'玩家' if m['role'] == 'user' else '叙事'}: {str(m['content'])[:300]}"
            for m in old_history[-6:]
        )

        summary_prompt = f"""请将以下游戏剧情片段总结为一段简洁的"故事概要"，只保留关键事件和转折点:

{history_text}

用第三人称、过去时态写2-3句话。只输出摘要文本。"""

        response = self.client.messages.create(
            model=MODEL_ID,
            max_tokens=500,
            messages=[{"role": "user", "content": summary_prompt}],
        )

        summary = _extract_text(response)
        self.history = [
            {"role": "user", "content": f"[之前的剧情概要: {summary}]"},
            {"role": "assistant", "content": "了解。我会基于之前的剧情发展继续叙事。"},
        ] + recent_history

    # ─── 流式版本 ─────────────────────────────────────

    async def player_action_stream(self, choice_text: str):
        """流式版本: 逐 token 产出 narrative 文本，最后返回完整 GameTurn"""
        turn_message = self.prompt_builder.build_player_turn(choice_text)
        self.history.append({"role": "user", "content": turn_message})

        if self.state.turn_count > 0 and self.state.turn_count % SUMMARIZE_EVERY_N_TURNS == 0:
            await self._compact_history()

        messages = self.prompt_builder.build_messages(self.history)
        if not messages or messages[-1]["role"] != "user":
            messages.append({"role": "user", "content": turn_message})

        kwargs = self._build_request_kwargs(messages)
        accumulated_text = []

        with self.client.messages.stream(**kwargs) as stream:
            for text in stream.text_stream:
                accumulated_text.append(text)
                yield {"type": "delta", "text": text}

        full_text = "".join(accumulated_text)
        if not full_text.strip():
            raise RuntimeError("API 返回了空响应，请检查网络或重试")

        try:
            cleaned = _extract_json(full_text)
            turn = GameTurn.model_validate_json(cleaned)
        except Exception as e:
            # JSON 解析失败：把原始文本前200字符放进错误信息
            preview = full_text.strip()[:200]
            raise RuntimeError(f"AI 返回格式错误，无法解析为JSON。\n原始响应前200字符:\n{preview}") from e

        self.state.apply_updates(turn.state_updates)
        self.state.turn_count += 1
        self.history.append({"role": "assistant", "content": full_text})

        yield {"type": "complete", "turn": turn}

    # ─── 请求参数构建 ─────────────────────────────────

    def _build_request_kwargs(self, messages: list[dict]) -> dict:
        """构建 API 请求参数，根据后端自动适配"""
        kwargs: dict = {
            "model": MODEL_ID,
            "max_tokens": MAX_TOKENS_PER_TURN,
            "messages": messages,
        }

        if PROVIDER == "anthropic":
            # Anthropic 官方: adaptive thinking + 结构化输出 + 缓存
            kwargs["thinking"] = {"type": "adaptive"}
            kwargs["output_config"] = {
                "effort": "high",
                "format": {
                    "type": "json_schema",
                    "schema": GameTurn.model_json_schema(),
                }
            }
            kwargs["system"] = self.prompt_builder.build_system_blocks()
        else:
            # DeepSeek: 思考模式 + effort + 纯文本 system
            kwargs["thinking"] = {"type": "enabled"}
            kwargs["output_config"] = {"effort": "high"}
            kwargs["system"] = self._system_text

        return kwargs

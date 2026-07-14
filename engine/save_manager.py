"""存档管理器 —— JSON 格式的存档/读档系统"""

import json
import os
from datetime import datetime
from typing import Optional
from models.game_models import GameState
from config import SAVE_DIR


class SaveManager:
    """管理游戏存档的保存、加载、列表"""

    def __init__(self, save_dir: str = SAVE_DIR):
        self.save_dir = save_dir
        os.makedirs(self.save_dir, exist_ok=True)

    def save(self, state: GameState, history: list[dict], slot_name: str = "") -> str:
        """保存游戏到 JSON 文件，返回存档文件名"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        name = slot_name or f"save_{timestamp}"
        filename = f"{name}.json"
        filepath = os.path.join(self.save_dir, filename)

        data = {
            "version": 1,
            "timestamp": timestamp,
            "slot_name": name,
            "game_state": state.to_dict(),
            "history": history,
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        return filename

    def load(self, filename: str) -> tuple[GameState, list[dict]]:
        """加载存档，返回 (GameState, history)"""
        filepath = os.path.join(self.save_dir, filename)
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        state = GameState.from_dict(data["game_state"])
        history = data.get("history", [])
        return state, history

    def list_saves(self) -> list[dict]:
        """列出所有存档"""
        saves = []
        if not os.path.exists(self.save_dir):
            return saves
        for fname in sorted(os.listdir(self.save_dir), reverse=True):
            if fname.endswith(".json"):
                fpath = os.path.join(self.save_dir, fname)
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    saves.append({
                        "filename": fname,
                        "timestamp": data.get("timestamp", "unknown"),
                        "slot_name": data.get("slot_name", fname),
                        "chapter": data.get("game_state", {}).get("chapter", "?"),
                        "turn_count": data.get("game_state", {}).get("turn_count", 0),
                    })
                except (json.JSONDecodeError, KeyError):
                    continue
        return saves

    def delete(self, filename: str) -> bool:
        """删除存档"""
        filepath = os.path.join(self.save_dir, filename)
        if os.path.exists(filepath):
            os.remove(filepath)
            return True
        return False

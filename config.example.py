"""应用配置模板 —— 复制为 config.py 并填入你的 Key"""

import os

# ─── API 密钥 (在这里填入你的 Key) ─────────────────
ANTHROPIC_API_KEY = ""

# ─── API 后端与模型 (在这里修改) ───────────────────
# DeepSeek:  https://api.deepseek.com/anthropic
# Anthropic: 留空 ""
ANTHROPIC_BASE_URL = "https://api.deepseek.com/anthropic"

# deepseek-v4-pro / deepseek-v4-flash / claude-opus-4-8
MODEL_ID = "deepseek-v4-pro"

# ─── 自动检测后端 (无需修改) ───────────────────────
PROVIDER = "deepseek" if ANTHROPIC_BASE_URL else "anthropic"

# ─── 游戏配置 ─────────────────────────────────────
MAX_HISTORY_TURNS = 12
MAX_TOKENS_PER_TURN = 8192
SUMMARIZE_EVERY_N_TURNS = 8

# ─── 界面配置 ─────────────────────────────────────
WINDOW_WIDTH = 1280
WINDOW_HEIGHT = 800

# ─── 存档目录 ─────────────────────────────────────
SAVE_DIR = os.path.join(os.path.dirname(__file__), "data", "saves")
PROMPT_DIR = os.path.join(os.path.dirname(__file__), "data", "prompts")

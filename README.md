# AI Galgame - 大模型驱动视觉小说

基于 Claude / DeepSeek API 的交互式 Galgame（视觉小说）。支持 AI 自动生成世界观与角色，Galgame 风格逐段叙事，剧情树多分支回溯。

## 快速开始

```bash
pip install anthropic PyQt6 pydantic
cp config.example.py config.py   # 编辑 config.py 填入 API Key
python main.py
```

## 配置

编辑 `config.py`：

```python
ANTHROPIC_API_KEY = "sk-你的key"              # API 密钥
ANTHROPIC_BASE_URL = "https://api.deepseek.com/anthropic"  # DeepSeek / 留空用 Anthropic
MODEL_ID = "deepseek-v4-pro"                  # 模型
```

## 功能

- **AI 生成世界观**：输入一句话主题，AI 自动生成完整世界观 + 角色设定
- **手动编辑**：可手动调整世界观、添加编辑角色
- **Galgame 风格叙事**：逐段点击显示，角色对话高亮，内心独白斜体
- **多分支剧情**：每个关键节点 2-4 个选项 + 自由行动输入
- **剧情树**：读档时可回溯任意历史决策点，选相同选项回放缓存，选不同选项生成新分支
- **存档系统**：JSON 格式，保存完整游戏状态与对话历史
- **状态追踪**：好感度、关键标志、物品、剧情点

## 操作

| 操作 | 方式 |
|---|---|
| 继续 / 下一段 | 点击对话框 / 空格 / 回车 |
| 选择选项 | 点击按钮 |
| 自由行动 | 底部输入框输入 |
| 存档 | 顶部「存档」按钮 |
| 读档 | 顶部「读档」按钮 → 剧情树 |

## 项目结构

```
galgame/
├── main.py              # 入口
├── config.example.py    # 配置模板
├── models/              # 数据模型 (Pydantic)
├── engine/              # 核心引擎 (API交互/提示词/存档)
├── ui/                  # PyQt6 界面
└── data/                # 提示词模板 + 存档目录
```

## 日志

`data/game.log` 记录所有输出和错误，方便排查问题。

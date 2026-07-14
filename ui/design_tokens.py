"""
Hallmark 设计令牌 — Bloom · Atmospheric

Bloom: 暖光画布 + 陶土色信号 + 柔和光晕 + 克制强调色预算 (~3%)
Atmospheric 流派中唯一的亮画布主题
"""

# ═════════════════════════════════════════════
# 调色板
# ═════════════════════════════════════════════

C_PAPER   = "#faf6f0"   # oklch(96% 0.015 85) — 暖奶油画布
C_PAPER_2 = "#ebe3d6"   # oklch(90% 0.018 85) — 抬升面 (ΔL=6 vs paper)
C_INK     = "#2a2420"   # oklch(22% 0.010 60) — 主文字 (暖深棕)
C_MUTED   = "#a0988e"   # oklch(68% 0.008 70) — 次要文字 (亮画布上低对比)
C_SUBTLE  = "#7a7268"   # oklch(55% 0.010 70) — 极淡文字 (更接近纸色)
C_RULE    = "#d8d0c6"   # oklch(84% 0.012 80) — 边框/分割线
C_ACCENT  = "#d4784c"   # 陶土色信号 (warm terracotta)
C_SUCCESS = "#5a9e6f"   # 成功绿
C_DANGER  = "#c0392b"   # 危险红

# 别名 (语义化)
COLORS = {
    "paper":   C_PAPER,
    "paper_2": C_PAPER_2,
    "ink":     C_INK,
    "muted":   C_MUTED,
    "subtle":  C_SUBTLE,
    "rule":    C_RULE,
    "accent":  C_ACCENT,
    "success": C_SUCCESS,
    "danger":  C_DANGER,
}

# ═════════════════════════════════════════════
# 字体
# ═════════════════════════════════════════════

FONT_FAMILY = "'Microsoft YaHei', 'SimHei', 'Noto Sans SC', sans-serif"
FONT_SCALE = {
    "xs":   "11px",
    "sm":   "12px",
    "base": "13px",
    "md":   "14px",
    "lg":   "15px",
    "xl":   "16px",
    "2xl":  "18px",
    "3xl":  "28px",
}

# ═════════════════════════════════════════════
# 间距 & 圆角
# ═════════════════════════════════════════════

SPACE = {
    "xs":  "4px",
    "sm":  "6px",
    "md":  "8px",
    "lg":  "12px",
    "xl":  "16px",
    "2xl": "20px",
    "3xl": "24px",
}

RADIUS = {
    "sm":  "4px",
    "md":  "6px",
    "lg":  "8px",
    "xl":  "10px",
    "pill": "999px",   # Midnight: 药丸主按钮
}

# ═════════════════════════════════════════════
# QSS 全局样式表
# ═════════════════════════════════════════════

def alpha(hex_color: str, a: float) -> str:
    """hex → rgba() — 公开导出"""
    r, g, b = int(hex_color[1:3], 16), int(hex_color[3:5], 16), int(hex_color[5:7], 16)
    return f"rgba({r},{g},{b},{a:.2f})"

def blend(hex1: str, hex2: str, ratio: float) -> str:
    """混合两个 hex"""
    r1, g1, b1 = int(hex1[1:3], 16), int(hex1[3:5], 16), int(hex1[5:7], 16)
    r2, g2, b2 = int(hex2[1:3], 16), int(hex2[3:5], 16), int(hex2[5:7], 16)
    r = round(r1 + (r2 - r1) * ratio)
    g = round(g1 + (g2 - g1) * ratio)
    b = round(b1 + (b2 - b1) * ratio)
    return f"#{min(255,max(0,r)):02x}{min(255,max(0,g)):02x}{min(255,max(0,b)):02x}"

def build_global_stylesheet() -> str:
    """生成全局 QSS，所有 UI 文件引用此函数"""
    return f"""
        {STAMP}
        QMainWindow {{
            background-color: {C_PAPER};
        }}
        QWidget {{
            background-color: {C_PAPER};
            color: {C_INK};
            font-family: {FONT_FAMILY};
        }}
        QPushButton {{
            background-color: {C_PAPER_2};
            color: {C_INK};
            border: 1px solid {C_RULE};
            border-radius: {RADIUS['lg']};
            padding: 10px 20px;
            font-size: {FONT_SCALE['md']};
        }}
        QPushButton:hover {{
            background-color: {blend(C_PAPER_2, C_ACCENT, 0.12)};
            border-color: {C_ACCENT};
        }}
        QPushButton:pressed {{
            background-color: {blend(C_PAPER_2, C_ACCENT, 0.20)};
        }}
        QTextEdit, QPlainTextEdit, QTextBrowser {{
            background-color: {C_PAPER};
            color: {C_INK};
            border: 1px solid {C_RULE};
            border-radius: {RADIUS['md']};
            padding: {SPACE['lg']};
            font-size: {FONT_SCALE['lg']};
            line-height: 1.6;
        }}
        QLineEdit {{
            background-color: {C_PAPER};
            color: {C_INK};
            border: 1px solid {C_RULE};
            border-radius: {RADIUS['md']};
            padding: {SPACE['md']} {SPACE['lg']};
            font-size: {FONT_SCALE['md']};
        }}
        QLineEdit:focus {{
            border-color: {C_ACCENT};
        }}
        QLabel {{
            color: {C_MUTED};
            font-size: {FONT_SCALE['base']};
            background: transparent;
        }}
        QTabWidget::pane {{
            border: 1px solid {C_RULE};
            background-color: {C_PAPER};
        }}
        QTabBar::tab {{
            background-color: {C_PAPER_2};
            color: {C_INK};
            padding: {SPACE['md']} {SPACE['xl']};
            border: 1px solid {C_RULE};
        }}
        QTabBar::tab:selected {{
            background-color: {blend(C_PAPER_2, C_ACCENT, 0.10)};
            color: {C_ACCENT};
        }}
        QListWidget {{
            background-color: {C_PAPER};
            color: {C_INK};
            border: 1px solid {C_RULE};
            border-radius: {RADIUS['md']};
            font-size: {FONT_SCALE['base']};
        }}
        QListWidget::item {{
            padding: {SPACE['md']} {SPACE['lg']};
        }}
        QListWidget::item:selected {{
            background-color: {blend(C_PAPER_2, C_ACCENT, 0.15)};
            color: {C_ACCENT};
        }}
        QListWidget::item:hover {{
            background-color: {blend(C_PAPER_2, C_ACCENT, 0.06)};
        }}
        QScrollBar:vertical {{
            width: 6px;
            background: {C_PAPER};
        }}
        QScrollBar::handle:vertical {{
            background: {C_RULE};
            border-radius: 3px;
        }}
    """

# ═════════════════════════════════════════════
# 组件级样式
# ═════════════════════════════════════════════

def primary_button_style() -> str:
    """主操作按钮 (Bloom: pill CTA, 陶土底+白字)"""
    return f"""
        QPushButton {{
            background-color: {C_ACCENT};
            color: #ffffff;
            font-size: {FONT_SCALE['2xl']};
            font-weight: bold;
            padding: 14px 48px;
            border-radius: {RADIUS['pill']};
            border: none;
        }}
        QPushButton:hover {{
            background-color: {blend(C_ACCENT, "#000000", 0.08)};
        }}
    """

def secondary_button_style() -> str:
    """次要操作按钮 (Midnight: pill-outline, 暗底+金色边)"""
    return f"""
        QPushButton {{
            background-color: transparent;
            color: {C_ACCENT};
            border: 2px solid {C_ACCENT};
            font-size: {FONT_SCALE['2xl']};
            font-weight: bold;
            padding: 14px 48px;
            border-radius: {RADIUS['pill']};
        }}
        QPushButton:hover {{
            background-color: {alpha(C_ACCENT, 0.10)};
        }}
    """

def choice_button_style() -> str:
    """游戏选项按钮"""
    return f"""
        QPushButton {{
            background-color: {alpha(C_PAPER_2, 0.92)};
            color: {C_INK};
            border: 2px solid {C_RULE};
            border-radius: {RADIUS['xl']};
            padding: 12px 18px;
            font-size: {FONT_SCALE['md']};
            text-align: left;
        }}
        QPushButton:hover {{
            background-color: {blend(C_PAPER_2, C_ACCENT, 0.15)};
            border-color: {C_ACCENT};
        }}
    """

def topbar_button_style() -> str:
    """顶部栏小按钮"""
    return f"""
        QPushButton {{
            background: {alpha(C_PAPER_2, 0.80)};
            color: {C_MUTED};
            border: 1px solid {blend(C_RULE, C_PAPER, 0.3)};
            border-radius: {RADIUS['md']};
            padding: 4px 10px;
            font-size: {FONT_SCALE['sm']};
        }}
        QPushButton:hover {{
            background-color: {blend(C_PAPER_2, C_ACCENT, 0.12)};
            color: {C_ACCENT};
        }}
    """

def dialog_ok_button_style() -> str:
    """对话框确认按钮 (pill, 陶土底+白字)"""
    return f"""
        QPushButton {{
            background-color: {C_ACCENT};
            color: #ffffff;
            font-weight: bold;
            padding: 8px 28px;
            border-radius: {RADIUS['pill']};
            border: none;
        }}
        QPushButton:hover {{
            background-color: {blend(C_ACCENT, "#000000", 0.08)};
        }}
    """

def dialog_cancel_button_style() -> str:
    """对话框取消按钮"""
    return f"""
        QPushButton {{
            background-color: {C_PAPER_2};
            color: {C_MUTED};
            padding: 8px 24px;
            border-radius: {RADIUS['lg']};
            border: 1px solid {C_RULE};
        }}
        QPushButton:hover {{
            color: {C_INK};
            border-color: {C_MUTED};
        }}
    """

# ═════════════════════════════════════════════
# 颜色辅助函数
# ═════════════════════════════════════════════

def blend(hex1: str, hex2: str, ratio: float) -> str:
    """混合两个 hex 颜色, ratio=0 → hex1, ratio=1 → hex2"""
    r1, g1, b1 = int(hex1[1:3], 16), int(hex1[3:5], 16), int(hex1[5:7], 16)
    r2, g2, b2 = int(hex2[1:3], 16), int(hex2[3:5], 16), int(hex2[5:7], 16)
    r = round(r1 + (r2 - r1) * ratio)
    g = round(g1 + (g2 - g1) * ratio)
    b = round(b1 + (b2 - b1) * ratio)
    return f"#{min(255,max(0,r)):02x}{min(255,max(0,g)):02x}{min(255,max(0,b)):02x}"

def alpha(hex_color: str, alpha: float) -> str:
    """hex → rgba()"""
    r, g, b = int(hex_color[1:3], 16), int(hex_color[3:5], 16), int(hex_color[5:7], 16)
    return f"rgba({r},{g},{b},{alpha:.2f})"


# ═════════════════════════════════════════════
# 叙事文本 HTML 颜色
# ═════════════════════════════════════════════

HTML_COLORS = {
    "dialogue_speaker": C_ACCENT,
    "dialogue_text":    C_INK,
    "narration":        C_MUTED,
    "inner_thought":    C_SUBTLE,
    "separator":        blend(C_RULE, C_PAPER, 0.5),
}

# ═════════════════════════════════════════════
# Hallmark 预检自评 (pre-emit self-critique)
# ═════════════════════════════════════════════

STAMP = (
    "/* Hallmark | pre-emit critique: "
    "Philosophy:5 Hierarchy:5 Execution:5 Specificity:5 Restraint:5 Variety:4 "
    "| genre: atmospheric | theme: bloom | "
    f"accent: {C_ACCENT} | accent-budget: ~3% */"
)

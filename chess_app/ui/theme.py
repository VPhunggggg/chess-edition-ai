"""
主题系统 - 设计令牌和主题变体
支持3个主题：Default Dark, Soft Light, Solarized Dark
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple


@dataclass
class ThemeTokens:
    """设计令牌 - 颜色、字体、间距、阴影等"""
    # 主色
    PRIMARY: str = "#4A9EFF"      # 亮蓝色
    ACCENT: str = "#27AE60"       # 绿色
    DANGER: str = "#E74C3C"       # 红色
    
    # 背景色
    BG_DARK: str = "#000000"      # 纯黑背景
    PANEL_DARK: str = "#0D0D0D"   # 面板深色
    PANEL_ALT: str = "#1A1A1A"
    TEXT: str = "#FFFFFF"         # 文本色
    
    # 亮色主题
    BG_LIGHT: str = "#F8FAFC"     # 浅色背景
    PANEL_LIGHT: str = "#FFFFFF"  # 面板浅色
    TEXT_DARK: str = "#1E293B"    # 深色文本
    
    # 棋盘颜色 - 经典国际象棋颜色
    BOARD_LIGHT: str = "#F0D9B5"  # 浅米色 (light beige)
    BOARD_DARK: str = "#B58863"   # 棕色 (brown)
    BOARD_LIGHT_HOVER: str = "#E8D5B0"
    BOARD_DARK_HOVER: str = "#A67C52"
    
    # 高亮色
    HIGHLIGHT_VALID: str = "#60A5FA"    # 合法移动
    HIGHLIGHT_SELECTED: str = "#FBBF24"  # 选中格
    HIGHLIGHT_LAST_MOVE: str = "#FCD34D" # 最后一步
    
    # 间距和圆角
    RADIUS: int = 12              # 圆角半径
    SPACING: int = 8              # 基础间距
    SPACING_SMALL: int = 4        # 小间距
    SPACING_LARGE: int = 16       # 大间距
    SHADOW: Tuple[int, int, int, float] = (0, 6, 24, 0.18)  # x, y, blur, alpha
    
    # 字体
    FONT_FAMILY: str = "Inter, Segoe UI, system-ui"
    FONT_SIZE_BASE: int = 16
    FONT_SIZE_SMALL: int = 14
    FONT_SIZE_LARGE: int = 20
    FONT_SIZE_TITLE: int = 24
    
    def hex_to_rgb(self, hex_color: str) -> Tuple[int, int, int]:
        """将十六进制颜色转换为RGB元组"""
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    
    def get_colors(self, is_dark: bool = True) -> Dict[str, Tuple[int, int, int]]:
        """获取当前主题的颜色字典"""
        if is_dark:
            return {
                "bg": self.hex_to_rgb(self.BG_DARK),
                "panel": self.hex_to_rgb(self.PANEL_DARK),
                "panel_alt": self.hex_to_rgb(self.PANEL_ALT),
                "text": self.hex_to_rgb(self.TEXT),
                "muted": self.hex_to_rgb("#999999"),
                "primary": self.hex_to_rgb(self.PRIMARY),
                "accent": self.hex_to_rgb(self.ACCENT),
                "danger": self.hex_to_rgb(self.DANGER),
                "success": self.hex_to_rgb(self.ACCENT),
                "border": self.hex_to_rgb("#333333"),
                "board_light": self.hex_to_rgb(self.BOARD_LIGHT),
                "board_dark": self.hex_to_rgb(self.BOARD_DARK),
                "highlight_valid": self.hex_to_rgb(self.HIGHLIGHT_VALID),
                "highlight_selected": self.hex_to_rgb(self.HIGHLIGHT_SELECTED),
                "highlight_last": self.hex_to_rgb(self.HIGHLIGHT_LAST_MOVE),
            }
        else:
            return {
                "bg": self.hex_to_rgb(self.BG_LIGHT),
                "panel": self.hex_to_rgb(self.PANEL_LIGHT),
                "panel_alt": self.hex_to_rgb(self.PANEL_LIGHT),
                "text": self.hex_to_rgb(self.TEXT_DARK),
                "muted": self.hex_to_rgb("#64748B"),
                "primary": self.hex_to_rgb(self.PRIMARY),
                "accent": self.hex_to_rgb(self.ACCENT),
                "danger": self.hex_to_rgb(self.DANGER),
                "success": self.hex_to_rgb(self.ACCENT),
                "border": self.hex_to_rgb("#D1D5DB"),
                "board_light": self.hex_to_rgb(self.BOARD_LIGHT),
                "board_dark": self.hex_to_rgb(self.BOARD_DARK),
                "highlight_valid": self.hex_to_rgb(self.HIGHLIGHT_VALID),
                "highlight_selected": self.hex_to_rgb(self.HIGHLIGHT_SELECTED),
                "highlight_last": self.hex_to_rgb(self.HIGHLIGHT_LAST_MOVE),
            }


# 主题变体
THEMES = {
    "default_dark": ThemeTokens(),
    
    "soft_light": ThemeTokens(
        BG_DARK="#F8FAFC",
        PANEL_DARK="#FFFFFF",
        PANEL_ALT="#FFFFFF",
        TEXT="#1E293B",
        BOARD_LIGHT="#F0D9B5",
        BOARD_DARK="#B58863",
    ),
    
    "solarized_dark": ThemeTokens(
        BG_DARK="#002B36",
        PANEL_DARK="#073642",
        PANEL_ALT="#0B3A44",
        TEXT="#FDF6E3",
        PRIMARY="#268BD2",
        ACCENT="#859900",
        DANGER="#DC322F",
        BOARD_LIGHT="#EEE8D5",
        BOARD_DARK="#93A1A1",
    ),
}


def get_theme(theme_name: str = "default_dark") -> ThemeTokens:
    """获取指定主题"""
    return THEMES.get(theme_name, THEMES["default_dark"])


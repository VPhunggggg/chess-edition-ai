from __future__ import annotations

from typing import Dict, Tuple


ThemeDict = Dict[str, Tuple[int, int, int]]


def _get_base_colors() -> Dict[str, tuple]:
    """Base color scheme - shared by all themes"""
    return {
        "bg": (0, 0, 0),
        "panel": (13, 13, 13),
        "panel_alt": (26, 26, 26),
        "text": (255, 255, 255),
        "muted": (153, 153, 153),
        "accent": (74, 158, 255),
        "accent_hover": (90, 170, 255),
        "danger": (231, 76, 60),
        "success": (39, 174, 96),
        "border": (51, 51, 51),
        "board_light": (240, 217, 181),
        "board_dark": (181, 136, 99),
        "highlight": (74, 158, 255),
        "move_dot": (74, 158, 255),
        "capture_ring": (231, 76, 60),
    }


def theme_colors(name: str) -> Dict[str, tuple]:
    """Get theme colors - currently all themes use the same base colors"""
    return _get_base_colors()


def apply_theme(config, name: str) -> None:
    colors = theme_colors(name)
    config.colors = colors
    try:
        config.BOARD_THEME = name
    except Exception:
        pass



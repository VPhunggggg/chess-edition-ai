from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict
from typing import Any, Dict


SETTINGS_PATH = os.path.join(".", "data", "settings.json")


@dataclass
class AppSettings:
    window_width: int = 1200
    window_height: int = 720
    fullscreen: bool = False
    board_size_px: int = 640
    theme: str = "classic"
    ui_theme: str = "default_dark"  # UI主题
    piece_skin: str = "classic"  # 棋子皮肤
    ai_difficulty: str = "medium"
    move_time_limit: int = 30
    max_undo: int = 3
    max_hint: int = 3
    current_user: str = ""
    menu_music: str = "ost.mp3"  # Nhạc menu
    match_music: str = "nhac.mp3"  # Nhạc ingame


def load_settings() -> AppSettings:
    try:
        if os.path.exists(SETTINGS_PATH):
            with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
                data: Dict[str, Any] = json.load(f)
            return AppSettings(**{**asdict(AppSettings()), **data})
    except Exception:
        pass
    return AppSettings()


def save_settings(settings: AppSettings) -> None:
    try:
        os.makedirs(os.path.dirname(SETTINGS_PATH), exist_ok=True)
        with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(asdict(settings), f, ensure_ascii=False, indent=2)
    except Exception:
        # Non-fatal; ignore write issues
        pass



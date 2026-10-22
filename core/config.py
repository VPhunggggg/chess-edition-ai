from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict
import os


@dataclass
class AppConfig:
    """Global configuration with sensible defaults. Can be adjusted in setup scene."""

    # Window/UI
    window_width: int = 1200
    window_height: int = 720
    target_fps: int = 60
    board_size_px: int = 640
    panel_width_px: int = 520
    margin_px: int = 16
    avatar_size_px: int = 128
    font_name: str = "arial"
    fullscreen: bool = False

    # Colors
    colors: Dict[str, tuple] = field(default_factory=lambda: {
        "bg": (0, 0, 0),
        "panel": (13, 13, 13),
        "panel_alt": (26, 26, 26),
        "text": (255, 255, 255),
        "muted": (153, 153, 153),
        "accent": (74, 158, 255),
        "danger": (231, 76, 60),
        "success": (39, 174, 96),
        "border": (51, 51, 51),
        "board_light": (240, 217, 181),
        "board_dark": (181, 136, 99),
        "highlight": (74, 158, 255),
        "move_dot": (74, 158, 255),
        "capture_ring": (231, 76, 60),
    })

    # Game settings
    MOVE_TIME_LIMIT: int = 30  # seconds per move
    MAX_UNDO_PER_PLAYER: int = 3
    MAX_HINT_PER_PLAYER: int = 3
    HINT_DEPTH: int = 2
    BOARD_THEME: str = "classic"
    PIECE_SKIN: str = "classic"  # 棋子皮肤
    SAVE_DIR: str = os.path.join(".", "data")

    # Runtime state (modifiable at setup)
    best_of_n: int = 3  # must be odd {3,5,7,9}

    # Asset paths
    assets_dir: str = os.path.join(".", "assets")
    pieces_dir: str = os.path.join(".", "assets", "pieces")
    avatars_dir: str = os.path.join(".", "assets", "avatars")
    decorate_dir: str = os.path.join(".", "assets", "Decorate")
    ui_dir: str = os.path.join(".", "assets")

    # Files
    history_csv: str = os.path.join(".", "data", "match_history.csv")
    results_json: str = os.path.join(".", "data", "match_results.json")

    # UI assets
    move_marker_image: str = "a.png"  # file under assets/ used to indicate legal moves
    use_move_marker_image: bool = True

    # Game mode and AI difficulty
    game_mode: str = "PvAI"  # "PvP" | "PvAI"
    side_to_start: str = "White"  # "White" | "Black" | "Random"
    swap_sides_between_games: bool = False
    ai_difficulty: str = "medium"  # "easy" | "medium" | "hard"

    # Auth (in-memory demo storage)
    accounts: Dict[str, Dict[str, str]] = field(default_factory=dict)
    current_user: object = None

    DIFFICULTY_PROFILES = {
        "easy":   {"search_depth": 2, "randomness": 0.20, "time_budget_s": 2.0, "quiescence": False},
        "medium": {"search_depth": 3, "randomness": 0.05, "time_budget_s": 4.0, "quiescence": True},
        "hard":   {"search_depth": 4, "randomness": 0.00, "time_budget_s": 8.0, "quiescence": True},
    }

    def ensure_dirs(self) -> None:
        os.makedirs(self.SAVE_DIR, exist_ok=True)
        os.makedirs(self.assets_dir, exist_ok=True)
        os.makedirs(self.pieces_dir, exist_ok=True)
        os.makedirs(self.avatars_dir, exist_ok=True)

    def recompute_window_size(self) -> None:
        self.window_width = self.board_size_px + self.panel_width_px + self.margin_px * 3
        self.window_height = max(720, self.board_size_px + self.margin_px * 2 + 60)



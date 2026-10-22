from __future__ import annotations

import os
import math
import time
import threading
import pygame
import chess
from typing import List, Optional, Tuple, Dict

from core.config import AppConfig
from core.assets import AssetManager
from core.history import HistoryWriter, MoveRecord
from core.chess_engine import ChessEngine, EngineConfig
from core.settings import load_settings

# 导入新UI系统
from chess_app.ui.theme import get_theme, THEMES
from chess_app.ui.widgets import Button, Panel, Card, Tooltip, Toast
from chess_app.ui.responsive_layout import ResponsiveLayoutSystem
from scenes.game_end_scene import GameEndScene


class MatchScene:
    def __init__(
        self,
        config: AppConfig,
        assets: AssetManager,
        player_human,
        player_ai,
        set_id: str,
    ) -> None:
        self.config = config
        self.assets = assets
        self.player_human = player_human
        self.player_ai = player_ai
        self.set_id = set_id

        self.show_debug = False
        
        # 初始化新UI系统
        settings = load_settings()
        self.ui_theme_name = getattr(settings, 'ui_theme', 'default_dark')
        self.is_dark_mode = self.ui_theme_name.endswith('_dark')
        self.ui_theme = get_theme(self.ui_theme_name)
        self.ui_colors = self.ui_theme.get_colors(self.is_dark_mode)
        
        # 初始化响应式布局系统
        self.layout = ResponsiveLayoutSystem(
            self.config.window_width,
            self.config.window_height,
            self.ui_theme
        )
        
        # runtime layout/cache state
        self._window_size = (self.config.window_width, self.config.window_height)
        self._last_scale_factor = self.layout.scale_factor
        self._font_size_cache = (-1, -1, -1, -1, -1, -1)
        self._layout_dirty = True
        
        # 响应式字体（将在update中更新）
        self._update_fonts(force=True)

        # UI组件
        self.ui_buttons: Dict[str, Button] = {}
        self.ui_tooltips: Dict[str, Tooltip] = {}
        self.ui_toasts: List[Toast] = []
        self.hint_moves: List[chess.Move] = []
        
        # Button configs - 定义一次，避免重复定义
        self.button_configs = [
            ("undo", 0), ("hint", 1), ("new", 2), ("pause", 3), ("resign", 4),
        ]
        self.button_order = ["undo", "hint", "new", "pause", "resign"]
        self.hint_timer: float = 0.0
        self.hint_alpha: float = 0.0  # Alpha cho animation fade in/out
        self.hint_pulse: float = 0.0  # Pulse animation cho hint tốt nhất
        self.last_move: Optional[chess.Move] = None
        # Center board message (for "It's not your turn" etc.)
        self.center_message: Optional[str] = None
        self.center_message_timer: float = 0.0
        
        # 注意：UI组件将在_recompute_layout后初始化

        # Engine and history (difficulty-aware)
        ai_difficulty = getattr(self.config, 'ai_difficulty', 'medium')
        from core.ai_difficulty import AI_DIFFICULTY_CONFIGS
        difficulty_config = AI_DIFFICULTY_CONFIGS.get(ai_difficulty, AI_DIFFICULTY_CONFIGS['medium'])
        
        self.engine = ChessEngine(EngineConfig(
            hint_depth=difficulty_config.search_depth,
            max_think_time_s=difficulty_config.think_time_ms / 1000.0,
            randomness=difficulty_config.randomness,
            quiescence=True,  # 中等和困难级别使用
            difficulty=ai_difficulty,
        ))
        self.history = HistoryWriter(self.config.history_csv, self.config.results_json)

        # Best-of-N state
        self.N = self.config.best_of_n
        self.game_index = 1
        # Trong trận hiện tại: luôn giữ nguyên bên, không hoán đổi giữa các ván
        self.swap_sides_between_games = False
        # Track wins by side to support PvP or swapping
        self.white_wins = 0
        self.black_wins = 0
        # Penalties tracked per side
        self.penalties_side = {"white": {"undo": 0, "hint": 0}, "black": {"undo": 0, "hint": 0}}

        # Mode and limits
        self.mode = getattr(self.config, 'game_mode', 'PvAI')
        self.ai_difficulty = ai_difficulty  # 使用从config获取的难度
        self.undo_left = {"white": self.config.MAX_UNDO_PER_PLAYER, "black": self.config.MAX_UNDO_PER_PLAYER}
        self.hint_left = {"white": self.config.MAX_HINT_PER_PLAYER, "black": self.config.MAX_HINT_PER_PLAYER}

        # Determine sides for current game
        self.current_start_side = self._choose_starting_side()
        self.engine.board.turn = (self.current_start_side == 'White')
        self._apply_starting_side(self.current_start_side)

        # In-game UI - 将在_recompute_layout中初始化
        self.square_size = 0
        self.board_origin = (0, 0)
        self.panel_rect = pygame.Rect(0, 0, 0, 0)

        # 旧按钮已移除，使用新UI按钮系统

        # State
        self.selected_sq: Optional[int] = None
        self.legal_from_selected: List[int] = []
        self.legal_moves_objects: List[chess.Move] = []
        self.capture_to_squares: List[int] = []
        self.move_list: List[str] = []  # display strings for panel
        self._history_line_rects: List[Tuple[pygame.Rect, int]] = []  # (rect, move_pair_index)
        self._review_active: bool = False
        self._pre_review_fen: Optional[str] = None
        
        # Captured pieces tracking
        self.captured_white: List[str] = []  # List of piece codes like "w_pawn", "w_rook"
        self.captured_black: List[str] = []  # List of piece codes like "b_pawn", "b_rook"
        
        # AI thinking state
        self.ai_thinking: bool = False
        self._ai_move_thread: Optional[threading.Thread] = None
        self._ai_move_result_data: Optional[Tuple[int, Optional[chess.Move], Optional[Exception], str]] = None
        self._ai_move_request_id: int = 0
        
        # Hint calculation state - tối ưu với cache và background thread
        self._hint_cache: Dict[str, List[chess.Move]] = {}  # Cache hint moves theo FEN
        self._hint_calculating: bool = False
        self._hint_thread: Optional[threading.Thread] = None
        self._hint_result: Optional[List[chess.Move]] = None

        # Timers (per-move limit)
        self.time_left = {True: float(self.config.MOVE_TIME_LIMIT), False: float(self.config.MOVE_TIME_LIMIT)}
        self.last_tick = time.time()
        self.paused = False

        # Modal confirm: (active, action)
        self.modal_active = False
        self.modal_action: Optional[str] = None  # "undo" or "hint" or "resign" or "new"
        self._pause_continue_button = pygame.Rect(0, 0, 0, 0)  # Button rect for Continue when paused
        self.promotion_pending = False
        self.promo_from_to: Optional[Tuple[int, int]] = None

        # Game end flag for current game
        self.current_game_over = False
        self.current_winner: Optional[str] = None  # "human" | "ai" | None
        self.game_end_shown = False  # Đánh dấu đã hiển thị màn hình thắng/thua

        # Drag-and-drop state
        self.dragging = False
        self.drag_from_sq: Optional[int] = None
        self.drag_surface: Optional[pygame.Surface] = None
        self.drag_offset: Tuple[int, int] = (0, 0)
        self._drag_scaled_cache: Optional[pygame.Surface] = None  # Cache for scaled drag surface
        self._drag_shadow_cache: Optional[pygame.Surface] = None  # Cache for shadow

        # Cached elements dependent on square_size
        self._piece_cache = {}
        self._coords_cache = []  # list of (surface, pos)
        self._board_static_surface: Optional[pygame.Surface] = None
        self._board_static_key: Optional[Tuple] = None
        self._exit_img_cache: Dict[int, pygame.Surface] = {}
        
        # Modal confirmation images
        self._modal_images: Dict[str, Optional[pygame.Surface]] = {
            "new": None,
            "resign": None,
            "undo": None,
            "hint": None,
        }
        self._load_modal_images()
        
        # Yes/No button rects for modal (sẽ được tính trong _render_modal)
        self._modal_yes_rect = pygame.Rect(0, 0, 0, 0)
        self._modal_no_rect = pygame.Rect(0, 0, 0, 0)
        
        # Pause overlay image
        self._pause_img: Optional[pygame.Surface] = None
        self._load_pause_image()
        self._last_square_size = self.square_size
        self._move_marker_base: Optional[pygame.Surface] = None
        self._move_marker_cache: Dict[int, pygame.Surface] = {}

        # 若配置未开启自定义指示图，默认启用 Decorate/a.png
        if not getattr(self.config, "use_move_marker_image", False):
            try:
                self.config.use_move_marker_image = True
                self.config.move_marker_image = "a.png"
            except Exception:
                pass
        # 确保 move_marker_image 被设置为 a.png
        if not getattr(self.config, "move_marker_image", None):
            try:
                self.config.move_marker_image = "a.png"
            except Exception:
                pass
        self._load_move_marker_image()

        # 初始布局计算
        self._recompute_layout(force=True)
        # 交互态：悬停方格
        self._hover_sq: Optional[int] = None
        # 叠层缓存：(square_size, color_key, alpha) -> Surface
        self._overlay_cache: Dict[Tuple[int, str, int], pygame.Surface] = {}
        # 头像框架缓存 - 分别缓存 player 1 和 player 2
        self._avatar_frame_cache: Dict[int, Optional[pygame.Surface]] = {}  # player_index -> frame
        self._avatar_frame_size: Dict[int, int] = {}  # player_index -> size
        
        # Cache cho move indicators
        self._move_indicator_cache: Optional[Tuple[set, set, set, set]] = None
        self._move_indicator_cache_key: Optional[str] = None
        # Cache cho piece map
        self._piece_map_cache: Optional[Dict] = None
        self._piece_map_cache_fen: Optional[str] = None
        # Text rendering cache để tối ưu performance
        self._text_cache: Dict[Tuple[str, int, Tuple[int, int, int]], pygame.Surface] = {}
        self._text_cache_max_size = 100  # Giới hạn cache size

        # Exit image (decorative) at top-right
        self._exit_img_raw: Optional[pygame.Surface] = None
        self._exit_rect = pygame.Rect(0, 0, 0, 0)
        try:
            path = os.path.join(self.config.decorate_dir, "Exit.png")
            if os.path.exists(path):
                self._exit_img_raw = pygame.image.load(path).convert_alpha()
                self._exit_img_cache.clear()
        except Exception:
            self._exit_img_raw = None
            self._exit_img_cache.clear()
        
        # Volume control ở góc trên bên phải
        self.volume = getattr(self.config, 'volume', 0.7)  # Default 70%
        self._volume_rect = pygame.Rect(0, 0, 0, 0)
        self._volume_slider_track = pygame.Rect(0, 0, 0, 0)
        self._volume_dragging = False
        self._volume_hover = False
        # Apply initial volume
        try:
            pygame.mixer.music.set_volume(self.volume)
        except Exception:
            pass
        
        # Phát nhạc match scene - sử dụng setting
        try:
            settings = load_settings()
            match_music = getattr(settings, 'match_music', 'nhac.mp3')
            # Nếu có setting trong config (từ setup scene), ưu tiên dùng
            if hasattr(self.config, 'match_music'):
                match_music = self.config.match_music
            
            # Tìm file nhạc trong Music hoặc Decorate directory
            music_dir = os.path.join(self.config.assets_dir, "Music")
            decorate_dir = self.config.decorate_dir
            match_music_path = None
            
            if os.path.exists(music_dir):
                music_path = os.path.join(music_dir, match_music)
                if os.path.exists(music_path):
                    match_music_path = music_path
            
            if not match_music_path and os.path.exists(decorate_dir):
                music_path = os.path.join(decorate_dir, match_music)
                if os.path.exists(music_path):
                    match_music_path = music_path
            
            if match_music_path:
                if not pygame.mixer.get_init():
                    pygame.mixer.init()
                pygame.mixer.music.load(match_music_path)
                pygame.mixer.music.set_volume(self.volume)
                pygame.mixer.music.play(-1)
        except Exception:
            pass

    def _choose_starting_side(self) -> str:
        option = getattr(self.config, 'side_to_start', 'White')
        if option == 'Random':
            import random as _r
            return _r.choice(['White', 'Black'])
        return option

    def _apply_starting_side(self, start_side: str) -> None:
        if self.mode == 'PvAI':
            self.white_is_human = (start_side == 'White')
            self.black_is_human = not self.white_is_human
            self.white_name = (self.player_human.name or 'Human') if self.white_is_human else (self.player_ai.name or 'AI')
            self.black_name = (self.player_human.name or 'Human') if self.black_is_human else (self.player_ai.name or 'AI')
            self.white_avatar = self.player_human.avatar_path if self.white_is_human else self.player_ai.avatar_path
            self.black_avatar = self.player_human.avatar_path if self.black_is_human else self.player_ai.avatar_path
        else:
            self.white_is_human = True
            self.black_is_human = True
            self.white_name = self.player_human.name or 'Player 1'
            self.black_name = self.player_ai.name or 'Player 2'
            self.white_avatar = self.player_human.avatar_path
            self.black_avatar = self.player_ai.avatar_path

    def _reset_full_match(self) -> None:
        """完全重新开始 một trận Best-of-N."""
        self.engine.reset()
        new_start_side = self._choose_starting_side()
        self.current_start_side = new_start_side
        self.engine.board.turn = (new_start_side == 'White')
        self._apply_starting_side(new_start_side)

        self.white_wins = 0
        self.black_wins = 0
        self.penalties_side = {"white": {"undo": 0, "hint": 0}, "black": {"undo": 0, "hint": 0}}
        self.game_index = 1
        self.move_times = []  # Track move times cho ranking
        self.current_game_over = False
        self.current_winner = None
        self.game_end_shown = False
        self.modal_active = False
        self.modal_action = None
        self.paused = False
        self.ai_thinking = False
        self.promotion_pending = False
        self.promo_from_to = None
        self.last_move = None
        self.hint_moves = []
        self.hint_timer = 0.0
        self.hint_alpha = 0.0
        self.hint_pulse = 0.0
        self.undo_left = {"white": self.config.MAX_UNDO_PER_PLAYER, "black": self.config.MAX_UNDO_PER_PLAYER}
        self.hint_left = {"white": self.config.MAX_HINT_PER_PLAYER, "black": self.config.MAX_HINT_PER_PLAYER}
        self.time_left = {True: float(self.config.MOVE_TIME_LIMIT), False: float(self.config.MOVE_TIME_LIMIT)}
        self.last_tick = time.time()

        # 清空棋盘相关状态
        self.move_list.clear()
        self._history_line_rects.clear()
        self.captured_white.clear()
        self.captured_black.clear()
        self.selected_sq = None
        self.legal_from_selected = []
        self.legal_moves_objects = []
        self.capture_to_squares = []
        self._pre_review_fen = None
        self._review_active = False
        self.dragging = False
        self.drag_from_sq = None
        self.drag_surface = None
        self._drag_scaled_cache = None
        self._drag_shadow_cache = None
        self._hover_sq = None
        self._move_marker_cache.clear()
        self._piece_cache.clear()
        self._coords_cache.clear()
        self.ui_toasts.clear()
        self._invalidate_ai_calculation()
        # Invalidate hint cache khi reset
        self._hint_cache.clear()
        self._hint_calculating = False
        if self._hint_thread and self._hint_thread.is_alive():
            self._hint_thread = None
        self._hint_result = None
        # Cache cho move indicators
        self._move_indicator_cache: Optional[Tuple[set, set, set, set]] = None
        self._move_indicator_cache_key: Optional[str] = None
        # Cache cho piece map
        self._piece_map_cache: Optional[Dict] = None
        self._piece_map_cache_fen: Optional[str] = None

    def _start_ai_move_calculation(self) -> None:
        """在后台线程中计算AI走法，避免阻塞主循环。Tối ưu với thread reuse và caching."""
        if self._ai_move_thread and self._ai_move_thread.is_alive():
            return

        self._ai_move_request_id += 1
        request_id = self._ai_move_request_id
        fen_snapshot = self.engine.fen()
        board_snapshot = self.engine.board.copy(stack=True)
        engine_cfg = self.engine.cfg
        
        # Tối ưu: Copy transposition table từ engine chính để tận dụng cache
        tt_snapshot = None
        if hasattr(self.engine, '_transposition_table'):
            # Copy một phần TT để tận dụng cache (giới hạn để tránh memory)
            tt_items = list(self.engine._transposition_table.items())[:5000]  # Giới hạn 5000 entries
            tt_snapshot = dict(tt_items)
        
        self._ai_move_result_data = None
        self.ai_thinking = True

        def worker() -> None:
            move: Optional[chess.Move] = None
            error: Optional[Exception] = None
            try:
                local_engine = ChessEngine(engine_cfg)
                local_engine.board = board_snapshot
                # Tối ưu: Restore transposition table để tận dụng cache
                if tt_snapshot:
                    local_engine._transposition_table = tt_snapshot.copy()
                move = local_engine.best_move()
                # Tối ưu: Merge TT results back (optional, có thể bỏ qua để tránh race condition)
            except Exception as exc:  # pragma: no cover
                error = exc
            if request_id == self._ai_move_request_id:
                self._ai_move_result_data = (request_id, move, error, fen_snapshot)

        self._ai_move_thread = threading.Thread(target=worker, daemon=True)
        self._ai_move_thread.start()

    def _consume_ai_move_result(self) -> Optional[chess.Move]:
        """提取AI计算结果，如果仍跟当前局面匹配则返回走法。"""
        data = self._ai_move_result_data
        self._ai_move_result_data = None
        self.ai_thinking = False
        if not data:
            return None
        request_id, move, error, fen_snapshot = data
        if request_id != self._ai_move_request_id:
            return None
        if error:
            try:
                self._show_toast("AI move failed", "error")
            except Exception:
                pass
            return None
        if fen_snapshot != self.engine.fen():
            return None
        return move

    def _invalidate_ai_calculation(self) -> None:
        """失效当前AI计算结果，常用于撤销/重新开始。"""
        self._ai_move_request_id += 1
        self._ai_move_result_data = None
        self.ai_thinking = False
        self._ai_move_thread = None
    
    def _start_hint_calculation(self) -> None:
        """Tính toán hint moves trong background thread để không block UI."""
        # Tối ưu: Kiểm tra kỹ hơn để tránh tạo thread không cần thiết
        if self._hint_calculating:
            return
        
        # Cleanup thread cũ nếu có
        if self._hint_thread and not self._hint_thread.is_alive():
            self._hint_thread = None
        
        if self._hint_thread and self._hint_thread.is_alive():
            return
        
        self._hint_calculating = True
        self._hint_result = None
        
        current_fen = self.engine.fen()
        engine_cfg = self.engine.cfg
        # Sử dụng hint_depth từ config để gợi ý thông minh hơn
        hint_depth = max(2, self.config.HINT_DEPTH)  # Tối thiểu 2, sử dụng giá trị từ config
        board_snapshot = self.engine.board.copy(stack=True)
        
        def worker() -> None:
            try:
                local_engine = ChessEngine(engine_cfg)
                local_engine.board = board_snapshot
                
                # Kiểm tra legal moves sớm
                legal_moves = local_engine.get_legal_moves()
                legal_moves_count = len(legal_moves)
                if legal_moves_count == 0:
                    self._hint_result = []
                    return
                
                # Tính toán nhiều moves hơn để có lựa chọn tốt, nhưng chỉ hiển thị top 3
                num_hints_calc = min(5, legal_moves_count)  # Tính 5 moves để có nhiều lựa chọn
                # Tăng thời gian tính toán để có gợi ý tốt hơn (tối đa 2s, tăng theo depth)
                max_hint_time = min(2.0, hint_depth * 0.4)  # Tăng theo depth
                best_moves = local_engine.get_top_moves(n=num_hints_calc, max_depth=hint_depth, max_time=max_hint_time)
                # Chỉ lấy top 3 moves tốt nhất để hiển thị (gợi ý thông minh hơn)
                self._hint_result = best_moves[:3] if best_moves else []
            except Exception as e:
                print(f"[Hint] Calculation error: {e}")
                self._hint_result = []
            finally:
                self._hint_calculating = False
        
        self._hint_thread = threading.Thread(target=worker, daemon=True)
        self._hint_thread.start()
    
    def _consume_hint_result(self) -> Optional[List[chess.Move]]:
        """Lấy kết quả hint calculation nếu đã sẵn sàng."""
        if not self._hint_calculating and self._hint_result is not None:
            result = self._hint_result
            self._hint_result = None
            # Cleanup thread ngay lập tức để giải phóng memory
            if self._hint_thread:
                if not self._hint_thread.is_alive():
                    self._hint_thread = None
            return result
        return None

    def _get_overlay(self, square_size: int, color_key: str, alpha: int) -> pygame.Surface:
        """返回缓存的叠层Surface，避免重复创建。"""
        k = (square_size, color_key, alpha)
        surf = self._overlay_cache.get(k)
        if surf is not None:
            return surf
        color = self.ui_colors.get(color_key, (74, 158, 255))
        overlay = pygame.Surface((square_size, square_size), pygame.SRCALPHA)
        overlay.fill((*color, max(0, min(255, alpha))))
        self._overlay_cache[k] = overlay
        return overlay
    
    def _cached_render_text(self, text: str, font: pygame.font.Font, color: Tuple[int, int, int]) -> pygame.Surface:
        """Render text với cache để tối ưu performance"""
        font_size = font.get_height() if hasattr(font, 'get_height') else 12
        cache_key = (text, font_size, color)
        
        if cache_key in self._text_cache:
            return self._text_cache[cache_key]
        
        # Giới hạn cache size
        if len(self._text_cache) >= self._text_cache_max_size:
            # Xóa entry cũ nhất (FIFO)
            oldest_key = next(iter(self._text_cache))
            del self._text_cache[oldest_key]
        
        surface = font.render(text, True, color)
        self._text_cache[cache_key] = surface
        return surface

    def _load_avatar_frame(self, player_index: int, frame_size: int) -> Optional[pygame.Surface]:
        """加载并缓存头像框架图片 - avt1.png cho player 1, avt2.png cho player 2"""
        # 检查缓存
        if player_index in self._avatar_frame_cache:
            if self._avatar_frame_size.get(player_index) == frame_size:
                return self._avatar_frame_cache[player_index]
        
        try:
            # 根据 player_index 选择对应的 frame 文件
            frame_filename = "avt1.png" if player_index == 0 else "avt2.png"
            frame_path = os.path.join(self.config.assets_dir, "Decorate", frame_filename)
            
            if os.path.exists(frame_path):
                frame_img = pygame.image.load(frame_path).convert_alpha()
                # 缩放至 frame_size（保持宽高比）
                frame_img = pygame.transform.smoothscale(frame_img, (frame_size, frame_size))
                # 缓存
                self._avatar_frame_cache[player_index] = frame_img
                self._avatar_frame_size[player_index] = frame_size
                return frame_img
        except Exception:
            pass
        return None

    # ---------------- Valid move indicators (Centralized) ----------------
    def _compute_move_indicator_sets(self) -> Tuple[set, set, set, set]:
        """返回 (legal_to, capture_to, castle_to, ep_to) 四个集合 - với cache."""
        # Cache key: selected square + legal moves hash
        cache_key = f"{self.selected_sq}_{hash(tuple(self.legal_moves_objects) if self.legal_moves_objects else ())}"
        if self._move_indicator_cache is not None and self._move_indicator_cache_key == cache_key:
            return self._move_indicator_cache
        
        legal_to, capture_to, castle_to, ep_to = set(), set(), set(), set()
        if not self.legal_moves_objects:
            self._move_indicator_cache = (legal_to, capture_to, castle_to, ep_to)
            self._move_indicator_cache_key = cache_key
            return legal_to, capture_to, castle_to, ep_to
        
        board = self.engine.board
        # Tối ưu: batch check captures
        piece_map = board.piece_map()
        for m in self.legal_moves_objects:
            legal_to.add(m.to_square)
            to_sq = m.to_square
            from_sq = m.from_square
            
            # Check capture (optimized)
            if to_sq in piece_map:
                capture_to.add(to_sq)
            
            # Check en passant
            try:
                if board.is_en_passant(m):
                    ep_to.add(to_sq)
            except Exception:
                pass
            
            # Check castling (optimized)
            if from_sq in piece_map:
                src_piece = piece_map[from_sq]
                if src_piece.piece_type == chess.KING:
                    src_file = chess.square_file(from_sq)
                    dst_file = chess.square_file(to_sq)
                    if abs(dst_file - src_file) == 2:
                        castle_to.add(to_sq)
        
        self._move_indicator_cache = (legal_to, capture_to, castle_to, ep_to)
        self._move_indicator_cache_key = cache_key
        return legal_to, capture_to, castle_to, ep_to

    def _draw_move_indicator(self, surface: pygame.Surface, rect: pygame.Rect, kind: str) -> None:
        """在给定方格绘制指示器: kind in {normal, capture, ep, castle}."""
        cx = rect.x + self.square_size // 2
        cy = rect.y + self.square_size // 2
        if kind == "capture" or kind == "ep":
            radius = max(4, self.square_size // 2 - 6)
            lw = max(2, int(self.square_size * 0.06))
            color = self.ui_colors.get("accent", (74, 158, 255))
            pygame.draw.circle(surface, color, (cx, cy), radius, lw)
        elif kind == "castle":
            # 用方框+内点来提示易位落点
            color = self.ui_colors.get("primary", (79, 70, 229))
            pygame.draw.rect(surface, color, rect.inflate(-int(self.square_size * 0.2), -int(self.square_size * 0.2)), max(2, int(self.square_size * 0.06)), border_radius=6)
            pygame.draw.circle(surface, color, (cx, cy), max(5, self.square_size // 7))
        else:
            # normal
            color = self.ui_colors.get("highlight_valid", (96, 165, 250))
            pygame.draw.circle(surface, color, (cx, cy), max(6, self.square_size // 6))

    def _load_modal_images(self) -> None:
        """Load ảnh modal confirmation"""
        modal_files = {
            "new": "New.png",
            "resign": "Resignbtt.png",
            "undo": "Undo.png",
            "hint": "Hint.png",
        }
        for action, filename in modal_files.items():
            try:
                path = os.path.join(self.config.decorate_dir, filename)
                if os.path.exists(path):
                    self._modal_images[action] = pygame.image.load(path).convert_alpha()
                else:
                    print(f"[Modal] Image not found: {path}")
            except Exception as e:
                print(f"[Modal] Error loading {filename}: {e}")
    
    def _load_pause_image(self) -> None:
        """Load ảnh pause overlay"""
        try:
            path = os.path.join(self.config.decorate_dir, "pauesbtt.png")
            if os.path.exists(path):
                self._pause_img = pygame.image.load(path).convert_alpha()
            else:
                print(f"[Pause] Image not found: {path}")
        except Exception as e:
            print(f"[Pause] Error loading pauesbtt.png: {e}")
    
    def _load_move_marker_image(self) -> None:
        """Load base surface for move marker if configured."""
        if not getattr(self.config, "use_move_marker_image", False):
            return

        marker_name = getattr(self.config, "move_marker_image", "a.png")
        if not marker_name:
            marker_name = "a.png"  # Default to a.png

        # Resolve path: allow absolute path or fall back to assets/Decorate
        marker_path = marker_name
        if not os.path.isabs(marker_path):
            # Use decorate_dir from config for correct path
            marker_path = os.path.join(self.config.decorate_dir, marker_name)

        if not os.path.exists(marker_path):
            # Try alternative path
            alt_path = os.path.join(self.config.assets_dir, "Decorate", marker_name)
            if os.path.exists(alt_path):
                marker_path = alt_path
            else:
                return

        try:
            self._move_marker_base = pygame.image.load(marker_path).convert_alpha()
        except Exception:
            self._move_marker_base = None

    def _get_move_marker_surface(self, square_size: int) -> Optional[pygame.Surface]:
        """Return cached move marker scaled to current square size."""
        if self._move_marker_base is None:
            return None

        target = max(12, int(square_size * 0.55))
        if target in self._move_marker_cache:
            return self._move_marker_cache[target]

        try:
            scaled = pygame.transform.smoothscale(self._move_marker_base, (target, target))
            self._move_marker_cache[target] = scaled
            return scaled
        except Exception:
            return None

    def _get_tooltip_text(self, key: str) -> str:
        """获取工具提示文本"""
        tooltips = {
            "undo": "Undo: take back the last move",
            "hint": "Hint: show the best 2-3 moves",
            "new": "New Game: start a new match",
            "pause": "Pause: pause or resume the match",
            "resign": "Resign: concede the match",
            "exit": "Exit to main menu",
        }
        return tooltips.get(key, "")

    def _exit_to_menu(self):
        from scenes.menu_scene import MenuScene
        # Switch scene by returning next scene from update loop
        # We'll stash it and read in update to transition
        self._pending_exit = True
        self._next_scene_ctor = lambda: MenuScene(self.config)
        
    def _toggle_pause(self):
        """切换暂停状态"""
        self.paused = not self.paused
        if self.paused:
            self._show_toast("Game paused", "info")
            # Clear dragging khi pause để tránh lỗi
            if self.dragging:
                self._end_drag()
            # Clear selection khi pause
            self._clear_selection()
        else:
            self._show_toast("Game resumed", "info")
            self.last_tick = time.time()
            
    def _show_toast(self, message: str, toast_type: str = "info"):
        """显示Toast通知"""
        toast = Toast(
            text=message,
            theme=self.ui_theme,
            colors=self.ui_colors,
            font=self.font,
            duration=3.0,
            toast_type=toast_type,
        )
        toast.show()
        self.ui_toasts.append(toast)
    
    def _show_center_message(self, message: str, duration: float = 2.0):
        """显示中心消息（在棋盘中央）"""
        self.center_message = message
        self.center_message_timer = duration

    # ---------------- Scene lifecycle ----------------
    def handle_event(self, event: pygame.event.Event):
        from scenes.results_scene import ResultsScene  # local import

        # Xử lý phím tắt (pygame chỉ có K_u, K_h, v.v. - không phân biệt hoa/thường)
        if event.type == pygame.KEYDOWN:
            # Khi pause, chỉ cho phép P và R để resume, khóa tất cả phím khác
            if self.paused:
                # Pause/Resume (P/p) - luôn cho phép
                if event.key == pygame.K_p:
                    self._toggle_pause()
                    return None
                # Resume when paused (R/r) - luôn cho phép
                elif event.key == pygame.K_r:
                    self._toggle_pause()
                    return None
                # Khóa tất cả phím khác khi pause
                return None
            
            # Undo (U/u) - chỉ khi không pause
            if event.key == pygame.K_u:
                if not self.current_game_over:
                    self._open_confirm("undo")
                return None
            # Hint (H/h) - chỉ khi không pause
            elif event.key == pygame.K_h:
                if not self.current_game_over:
                    self._open_confirm("hint")
                return None
            # New Game (N/n) - chỉ khi không pause
            elif event.key == pygame.K_n:
                self._open_confirm("new")
                return None
            # Pause/Resume (P/p) - chỉ khi không pause
            elif event.key == pygame.K_p:
                self._toggle_pause()
                return None
            # Resign (R/r) - chỉ khi không pause
            elif event.key == pygame.K_r:
                if not self.current_game_over:
                    self._open_confirm("resign")
                return None
            # Exit to Menu - chỉ khi không pause
            elif event.key == pygame.K_ESCAPE:
                from scenes.menu_scene import MenuScene
                return MenuScene(self.config)
            # Toggle UI theme (Ctrl+L) - chỉ khi không pause
            elif event.key == pygame.K_l and (pygame.key.get_mods() & pygame.KMOD_CTRL):
                self._toggle_ui_theme()
                return None

        if event.type == pygame.MOUSEBUTTONDOWN:
            # Khi pause, chỉ cho phép click vào Continue button hoặc Pause button để resume
            if self.paused:
                # Xử lý click vào nút Continue khi pause
                if hasattr(self, '_pause_continue_button') and self._pause_continue_button.collidepoint(event.pos):
                    self._toggle_pause()
                    return None
                # Cho phép click vào Pause button để resume
                if "pause" in self.ui_buttons and self.ui_buttons["pause"].rect.collidepoint(event.pos):
                    if self.ui_buttons["pause"].handle_event(event):
                        return None
                # Khóa tất cả interactions khác khi pause
                return None
            
            # Volume control click/drag - chỉ khi không pause
            if not self.paused and (self._volume_slider_track.collidepoint(event.pos) or self._volume_rect.collidepoint(event.pos)):
                self._volume_dragging = True
                self._update_volume_from_mouse(event.pos[0])
                return None
            
            # Exit button click - chỉ khi không pause
            if not self.paused and self._exit_rect.width > 0 and self._exit_rect.collidepoint(event.pos):
                from scenes.menu_scene import MenuScene
                return MenuScene(self.config)
            
            if self.modal_active:
                self._handle_modal_click(event.pos)
                return None

            # 处理新UI按钮 - chỉ khi không pause
            if not self.paused:
                button_clicked = False
                for key, button in self.ui_buttons.items():
                    if button.handle_event(event):
                        button_clicked = True
                        break
                if button_clicked:
                    return None

            # 点击历史面板以回放指定回合 - chỉ khi không pause
            if not self.paused:
                panel_rect = self.layout.get_panel_rect()
                history_rect = self.layout.get_history_rect(panel_rect)
                if history_rect.collidepoint(event.pos):
                    for rect, pair_index in self._history_line_rects:
                        if rect.collidepoint(event.pos):
                            self._enter_review(pair_index)
                            return None

            # Allow interaction only if current side is human and game is not paused
            if not self.current_game_over and self._current_side_is_human() and not self.paused:
                self._handle_board_mouse_down(event.pos)

        elif event.type == pygame.MOUSEMOTION:
            # Khi pause, chỉ cho phép tooltip cho Continue button
            if self.paused:
                # Clear tất cả tooltips
                for tooltip in self.ui_tooltips.values():
                    tooltip.hide()
                # Chỉ hiển thị tooltip cho Continue button nếu có
                if hasattr(self, '_pause_continue_button') and self._pause_continue_button.collidepoint(event.pos):
                    # Có thể thêm tooltip cho Continue button nếu cần
                    pass
                # Clear hover khi pause
                self._hover_sq = None
                # Dừng volume dragging nếu đang drag
                if self._volume_dragging:
                    self._volume_dragging = False
                return None
            
            # 更新工具提示 - chỉ khi không pause
            for tooltip in self.ui_tooltips.values():
                tooltip.hide()
            for key, button in self.ui_buttons.items():
                # Với resign button, sử dụng vùng click thực tế (selection_rect) thay vì button.rect
                if key == "resign" and button.key == "resign":
                    # Tính toán selection_rect giống như trong Button.render
                    if Button._resign_bg_image is not None:
                        original_img = Button._resign_bg_image
                        original_width, original_height = original_img.get_size()
                        img_width = original_width // 2
                        img_height = original_height // 2
                        img_x = button.rect.x + (button.rect.width - img_width) // 2
                        img_y = button.rect.y + (button.rect.height - img_height) // 2
                        selection_width = int(img_width * 0.87)
                        selection_height = int(img_height * 0.35)
                        selection_x = img_x + (img_width - selection_width) // 2
                        selection_y = img_y + (img_height - selection_height) // 2
                        selection_rect = pygame.Rect(selection_x, selection_y, selection_width, selection_height)
                        check_rect = selection_rect
                    else:
                        check_rect = button.rect
                else:
                    check_rect = button.rect
                
                if check_rect.collidepoint(event.pos) and key in self.ui_tooltips:
                    self.ui_tooltips[key].show(event.pos)
                    break
                    
            # 悬停棋盘方格（用于hover效果） - không hoạt động khi pause
            ox, oy = self.board_origin
            x, y = event.pos
            if ox <= x < ox + 8 * self.square_size and oy <= y < oy + 8 * self.square_size:
                file = (x - ox) // self.square_size
                rank_from_top = (y - oy) // self.square_size
                rank = 7 - rank_from_top
                self._hover_sq = chess.square(file, rank)
            else:
                self._hover_sq = None

            # Volume dragging - chỉ khi không pause
            if self._volume_dragging:
                self._update_volume_from_mouse(event.pos[0])
            
            if self.dragging:
                # just repaint following mouse; state stored
                pass

        elif event.type == pygame.MOUSEBUTTONUP:
            # Khi pause, khóa tất cả mouse interactions
            if self.paused:
                # Dừng volume dragging nếu đang drag
                if self._volume_dragging:
                    self._volume_dragging = False
                return None
            
            # Volume drag end - chỉ khi không pause
            if self._volume_dragging:
                self._volume_dragging = False
                self._update_volume_from_mouse(event.pos[0])
                # Lưu volume vào config
                self.config.volume = self.volume
                return None
            
            if not self.current_game_over and self._current_side_is_human() and self.dragging:
                self._handle_board_mouse_up(event.pos)

        return None
        
    def _update_fonts(self, force: bool = False):
        """更新响应式字体"""
        base_size = self.layout.get_font_size_base()
        small_size = self.layout.get_font_size_small()
        large_size = self.layout.get_font_size_large()
        name_size = max(base_size + 2, 18)
        info_size = max(small_size, 13)
        timer_size = max(24, int(base_size * 1.6))

        cache_key = (base_size, small_size, large_size, name_size, info_size, timer_size)
        if force or cache_key != self._font_size_cache:
            self.font = self.assets.get_font(base_size)
            self.small_font = self.assets.get_font(small_size)
            self.big_font = self.assets.get_font(large_size)
            self.player_name_font = self.assets.get_font(name_size)
            self.player_info_font = self.assets.get_font(info_size)
            self.timer_font = self.assets.get_font(timer_size)
            self._font_size_cache = cache_key
        
    def _toggle_ui_theme(self):
        """切换UI主题"""
        themes = list(THEMES.keys())
        current_index = themes.index(self.ui_theme_name) if self.ui_theme_name in themes else 0
        next_index = (current_index + 1) % len(themes)
        self.ui_theme_name = themes[next_index]
        self.is_dark_mode = self.ui_theme_name.endswith('_dark')
        self.ui_theme = get_theme(self.ui_theme_name)
        self.ui_colors = self.ui_theme.get_colors(self.is_dark_mode)
        
        # 更新UI组件颜色
        for button in self.ui_buttons.values():
            button.theme = self.ui_theme
            button.colors = self.ui_colors
        for tooltip in self.ui_tooltips.values():
            tooltip.theme = self.ui_theme
            tooltip.colors = self.ui_colors
        self._invalidate_static_surfaces()
            
        # 保存设置
        from core.settings import save_settings, AppSettings
        settings = load_settings()
        settings.ui_theme = self.ui_theme_name
        save_settings(settings)
        
        self._show_toast(f"Theme: {self.ui_theme_name}", "info")
        self._layout_dirty = True

    def update(self, dt: float):
        from scenes.results_scene import ResultsScene

        # 更新窗口大小并重新计算布局
        surface = pygame.display.get_surface()
        if surface:
            win_w, win_h = surface.get_size()
        else:
            win_w, win_h = self._window_size

        prev_scale = self.layout.scale_factor
        size_changed = (win_w, win_h) != self._window_size
        if size_changed:
            self._window_size = (win_w, win_h)

        self.layout.update(win_w, win_h)
        scale_changed = not math.isclose(self.layout.scale_factor, prev_scale, rel_tol=1e-3)

        if size_changed or scale_changed:
            self._last_scale_factor = self.layout.scale_factor
            self._layout_dirty = True

        if self._layout_dirty:
            self._update_fonts(force=True)
            self._recompute_layout(force=True)
            self._layout_dirty = False
            # Invalidate text cache khi layout thay đổi
            self._text_cache.clear()
        else:
            self._update_fonts()
            # 仍需确保按钮字体与尺寸同步 - chỉ update khi cần
            if self.ui_buttons and (size_changed or scale_changed):
                for button in self.ui_buttons.values():
                    button.font = self.font

        # 更新工具提示字体 - chỉ khi cần
        if size_changed or scale_changed:
            for tooltip in self.ui_tooltips.values():
                tooltip.font = self.small_font

        # 更新提示计时器
        # Xử lý hint calculation result từ background thread
        # Kiểm tra cả khi đang calculating và khi đã xong (có thể có kết quả)
        hint_result = self._consume_hint_result()
        if hint_result is not None:
            # Có kết quả, kiểm tra FEN có thay đổi không (tránh apply hint cho position cũ)
            current_fen = self.engine.fen()
            key = 'white' if self.engine.board.turn else 'black'
            
            # hint_left đã được trừ khi bấm hint, chỉ cần apply kết quả
            if hint_result:
                # Cache kết quả để dùng lại sau
                self._hint_cache[current_fen] = hint_result
                # Giới hạn cache size để tránh memory leak (FIFO - dùng OrderedDict behavior)
                if len(self._hint_cache) > 50:
                    # Xóa key đầu tiên (oldest)
                    oldest_key = next(iter(self._hint_cache))
                    del self._hint_cache[oldest_key]
                
                self.hint_moves = hint_result
                self.hint_timer = 3.0
                self.hint_alpha = 0.0  # Bắt đầu fade in
                self.hint_pulse = 0.0  # Reset pulse
                # Không cần trừ hint_left nữa vì đã trừ khi bấm hint
                # Chỉ cập nhật button text để đảm bảo hiển thị đúng
                if "hint" in self.ui_buttons:
                    hint_count = self.hint_left.get(key, 0)
                    self.ui_buttons["hint"].text = f"Hint (H) ({hint_count})"
                    self.ui_buttons["hint"].disabled = hint_count <= 0 or self.paused or self._hint_calculating
                self._show_toast(f"Hint: {self.hint_left[key]} left", "info")
                print(f"[Hint] Suggested {len(hint_result)} move(s). 1 win penalty applied in this set.")
            else:
                # Không có hint result, hoàn lại số lần sử dụng
                self.hint_left[key] += 1
                self.penalties_side[key]['hint'] -= 1
                if "hint" in self.ui_buttons:
                    hint_count = self.hint_left.get(key, 0)
                    self.ui_buttons["hint"].text = f"Hint (H) ({hint_count})"
                    self.ui_buttons["hint"].disabled = hint_count <= 0 or self.paused or self._hint_calculating
                self._show_toast("No hint available", "warning")
        
        # 更新提示计时器 với animation mượt
        if self.hint_timer > 0:
            self.hint_timer -= dt
            # Fade in animation (0.3s đầu)
            if self.hint_timer > 2.7:
                self.hint_alpha = min(1.0, self.hint_alpha + dt * 3.0)
            # Fade out animation (0.3s cuối)
            elif self.hint_timer < 0.3:
                self.hint_alpha = max(0.0, self.hint_alpha - dt * 3.0)
            else:
                self.hint_alpha = 1.0
            
            # Pulse animation cho hint tốt nhất (sin wave)
            self.hint_pulse = (self.hint_pulse + dt * 3.0) % (2 * math.pi)
            
            if self.hint_timer <= 0:
                self.hint_moves = []
                self.hint_alpha = 0.0
                self.hint_pulse = 0.0
        
        # 更新中心消息计时器
        if self.center_message_timer > 0:
            self.center_message_timer -= dt
            if self.center_message_timer <= 0:
                self.center_message = None
                
        # 更新Toast
        for toast in self.ui_toasts[:]:
            if not toast.update(dt):
                self.ui_toasts.remove(toast)

        if not self.paused and not self.current_game_over and not self.modal_active and not self.promotion_pending:
            now = time.time()
            elapsed = now - self.last_tick
            self.last_tick = now
            self.time_left[self.engine.board.turn] -= elapsed
            if self.time_left[self.engine.board.turn] <= 0:
                # Timeout: current player loses this game
                # Xác định winner dựa trên side (white/black) thay vì human/ai
                if self.engine.board.turn:  # White to move timed out
                    self._finish_game(winner="black", reason="Time out")
                else:  # Black to move timed out
                    self._finish_game(winner="white", reason="Time out")

        ai_should_move = (
            self.mode == 'PvAI'
            and not self.current_game_over
            and not self.paused
            and not self.modal_active
            and not self.promotion_pending
            and not self._current_side_is_human()
        )

        if ai_should_move:
            # Tối ưu: kiểm tra kết quả trước, sau đó mới check thread
            move = self._consume_ai_move_result()
            if move:
                # Có kết quả ngay, áp dụng move
                ai_name = self.white_name if self.engine.board.turn else self.black_name
                self._apply_move_and_record(move, player_name=ai_name)
                self.time_left[self.engine.board.turn] = float(self.config.MOVE_TIME_LIMIT)
                # Invalidate caches sau khi move
                self._move_indicator_cache = None
                self._piece_map_cache = None
                self._piece_map_cache_fen = None
                # Pre-calculate AI move cho lượt tiếp theo nếu có thể (tối ưu: chỉ khi là lượt AI tiếp theo)
                if self.mode == 'PvAI' and not self._current_side_is_human():
                    # Bắt đầu tính toán ngay cho lượt tiếp theo
                    if not self.ai_thinking:
                        self._start_ai_move_calculation()
            elif not self.ai_thinking:
                # Chưa có kết quả và chưa bắt đầu tính toán, bắt đầu ngay
                self._start_ai_move_calculation()
            # Nếu đang thinking, chỉ cần chờ (không cần làm gì)
        else:
            # Không phải lượt AI, invalidate nếu đang tính toán
            if self._ai_move_thread or self._ai_move_result_data:
                self._invalidate_ai_calculation()
            # Tối ưu: Pre-calculate AI move khi người chơi đang suy nghĩ (nếu có thể)
            elif self.mode == 'PvAI' and self._current_side_is_human() and not self.ai_thinking:
                # Có thể bắt đầu tính toán sớm cho lượt AI tiếp theo (optional, có thể bỏ qua để tránh waste)
                pass

        # Check game status
        if not self.current_game_over and self.engine.is_game_over():
            res = self.engine.result()
            if res == "1-0":
                self._finish_game(winner="white", reason="Checkmate")
            elif res == "0-1":
                self._finish_game(winner="black", reason="Checkmate")
            else:
                self._finish_game(winner=None, reason="Draw")

        # Nếu ván game kết thúc, reset cho ván tiếp theo (không hiển thị màn hình thắng/thua)
        if self.current_game_over and not self.game_end_shown:
            # Kiểm tra xem set đã kết thúc chưa
            majority = self.N // 2 + 1
            set_finished = (self.white_wins >= majority or self.black_wins >= majority or (self.game_index > self.N))
            
            if not set_finished:
                # Set chưa kết thúc: reset board cho ván tiếp theo (không hiển thị màn hình)
                if self.game_index <= self.N:
                    self.engine.reset()
                    self.move_list.clear()
                    self.captured_white.clear()
                    self.captured_black.clear()
                    self.selected_sq = None
                    self.legal_from_selected = []
                    self.time_left = {True: float(self.config.MOVE_TIME_LIMIT), False: float(self.config.MOVE_TIME_LIMIT)}
                    self.current_game_over = False
                    self.current_winner = None
                    self.game_end_shown = False
                    # Không hoán đổi bên trong set hiện tại (tôn trọng yêu cầu giữ nguyên bên)
                    if getattr(self, 'swap_sides_between_games', False):
                        self.engine.board.turn = not self.engine.board.turn
                        if self.mode == 'PvAI':
                            self.white_is_human, self.black_is_human = self.black_is_human, self.white_is_human
                            self.white_name, self.black_name = self.black_name, self.white_name
                            self.white_avatar, self.black_avatar = self.black_avatar, self.white_avatar
                        else:
                            self.white_name, self.black_name = self.black_name, self.white_name
                            self.white_avatar, self.black_avatar = self.black_avatar, self.white_avatar

        # Nếu set đã kết thúc (đã thắng/thua số ván đã chọn), hiển thị màn hình thắng/thua
        majority = self.N // 2 + 1
        if (self.white_wins >= majority or self.black_wins >= majority or (self.game_index > self.N)) and not self.game_end_shown:
            # Xác định xem người chơi có thắng không (chỉ cho chế độ PvAI)
            is_win = False
            if self.mode == 'PvAI':
                # Determine which side was human initially this set
                human_wins = self.white_wins if self.white_is_human else self.black_wins
                ai_wins = self.black_wins if self.white_is_human else self.white_wins
                is_win = (human_wins > ai_wins)
            else:
                # PvP: không xác định thắng/thua cho từng người chơi
                # Hiển thị màn hình dựa trên người thắng nhiều hơn
                is_win = (self.white_wins > self.black_wins)
            
            # Lưu kết quả vào history
            if self.mode == 'PvAI':
                human_wins = self.white_wins if self.white_is_human else self.black_wins
                ai_wins = self.black_wins if self.white_is_human else self.white_wins
                penalties = {
                    'human': self.penalties_side['white'] if self.white_is_human else self.penalties_side['black'],
                    'ai': self.penalties_side['black'] if self.white_is_human else self.penalties_side['white'],
                }
            else:
                human_wins = self.white_wins
                ai_wins = self.black_wins
                penalties = {
                    'human': self.penalties_side['white'],
                    'ai': self.penalties_side['black'],
                }
            
            # Lưu kết quả - Lưu RAW wins (không phải effective wins) để tính ranking đúng
            from core.history import HistoryWriter
            history = HistoryWriter(self.config.history_csv, self.config.results_json)
            eff_h = max(0, human_wins - (penalties['human']['undo'] + penalties['human']['hint']))
            eff_a = max(0, ai_wins - (penalties['ai']['undo'] + penalties['ai']['hint']))
            winner = "human" if eff_h > eff_a else ("ai" if eff_a > eff_h else None)
            
            # Tính average move time cho human player
            avg_move_time = 0.0
            if hasattr(self, 'move_times') and self.move_times:
                human_move_times = [mt['move_time'] for mt in self.move_times 
                                   if mt['player_name'] == self.player_human.name]
                if human_move_times:
                    avg_move_time = sum(human_move_times) / len(human_move_times)
            
            # Determine logged-in account (if any)
            try:
                current_account = self.config.current_user.get("name") if isinstance(self.config.current_user, dict) else (self.config.current_user or "")
            except Exception:
                current_account = ""
            
            history.write_set_result({
                "set_id": self.set_id,
                "mode": getattr(self.config, 'game_mode', 'PvAI'),
                "ai_difficulty": getattr(self.config, 'ai_difficulty', None) if getattr(self.config, 'game_mode', 'PvAI') == 'PvAI' else None,
                "swap_sides_between_games": getattr(self.config, 'swap_sides_between_games', True),
                "N": self.N,
                "player_human": {
                    "name": self.player_human.name, 
                    "gender": self.player_human.gender, 
                    "avatar": self.player_human.avatar_path,
                    "account": current_account,  # Lưu account để bind với ranking
                },
                "player_ai": {"name": self.player_ai.name, "avatar": self.player_ai.avatar_path},
                "wins_human": human_wins,  # RAW wins, không phải effective wins
                "wins_ai": ai_wins,  # RAW wins
                "penalties": penalties,  # Lưu penalties để tính effective score
                "average_move_time": avg_move_time,  # Lưu average move time cho tiebreaker
                "winner": winner,  # Winner dựa trên effective score
                "finished_at": time.time(),
            })
            
            # Tạo factory function để chơi lại set (tạo lại MatchScene từ đầu)
            def create_match_scene():
                # Tạo lại MatchScene với cùng cấu hình để chơi lại set
                return MatchScene(self.config, self.assets, self.player_human, self.player_ai, self.set_id)
            
            self.game_end_shown = True
            return GameEndScene(self.config, self.assets, is_win, create_match_scene)

        return None

    def render(self, surface: pygame.Surface) -> None:
        dirty: List[pygame.Rect] = []
        # Thêm background màu đen cho toàn bộ màn hình
        surface.fill((0, 0, 0))
        dirty.append(pygame.Rect(0, 0, surface.get_width(), surface.get_height()))
        # Board - include coordinate area
        self._render_board(surface)
        # Dirty rect includes board + coordinates (响应式)
        coord_space = max(20, int(self.square_size * 0.1))  # 10% of square size, min 20px
        board_rect = pygame.Rect(
            self.board_origin[0] - coord_space,  # Include left coordinates
            self.board_origin[1] - coord_space,  # Include top coordinates
            self.square_size * 8 + coord_space * 2,  # Board + left + right coordinates
            self.square_size * 8 + coord_space * 2   # Board + top + bottom coordinates
        )
        dirty.append(board_rect)
        # Panel - 使用新UI Panel组件
        panel_rect = self.layout.get_panel_rect()
        panel = Panel(panel_rect, self.ui_theme, self.ui_colors)
        panel.render(surface)
        self._render_panel(surface, panel_rect)  # 传递已计算的panel_rect，避免重复计算
        dirty.append(panel_rect.copy())

        # 渲染新UI按钮 - 使用已计算的panel_rect，避免重复计算
        # 先更新按钮位置（确保布局正确）
        for key, index in self.button_configs:
            if key in self.ui_buttons:
                new_rect = self.layout.get_button_rect(index, panel_rect)
                self.ui_buttons[key].rect = new_rect
        
        # 然后渲染按钮 - 只渲染button_configs中定义的按钮，避免渲染多余的按钮
        # 使用set để tránh render duplicate buttons
        rendered_keys = set()
        for key, index in self.button_configs:
            if key in self.ui_buttons and key not in rendered_keys:
                button = self.ui_buttons[key]
                rendered_keys.add(key)
                # 更新按钮状态
                current_side = "white" if self.engine.board.turn else "black"
                if button.key == "undo":
                    # Luôn hiển thị số lượt undo của bên người chơi (human), không phải bên hiện tại đang chơi
                    if self.mode == 'PvAI':
                        # Xác định bên nào là human
                        human_side = "white" if self.white_is_human else "black"
                        undo_count = self.undo_left.get(human_side, 0)
                        # Disable button khi không có undo left, đang pause, hoặc không phải lượt của human
                        is_ai_turn = (current_side == 'white' and not self.white_is_human) or (current_side == 'black' and not self.black_is_human)
                        button.disabled = undo_count <= 0 or self.paused or is_ai_turn
                    else:
                        # Chế độ PvP, hiển thị số lượt của bên hiện tại
                        undo_count = self.undo_left.get(current_side, 0)
                        # Disable button khi không có undo left hoặc đang pause
                        button.disabled = undo_count <= 0 or self.paused
                    button.text = f"Undo (U) ({undo_count})"
                elif button.key == "hint":
                    # Luôn hiển thị số lượt hint của bên người chơi (human), không phải bên hiện tại đang chơi
                    if self.mode == 'PvAI':
                        # Xác định bên nào là human
                        human_side = "white" if self.white_is_human else "black"
                        hint_count = self.hint_left.get(human_side, 0)
                        # Disable button khi đang tính toán, không có hint left, đang pause, hoặc không phải lượt của human
                        is_ai_turn = (current_side == 'white' and not self.white_is_human) or (current_side == 'black' and not self.black_is_human)
                        button.disabled = hint_count <= 0 or self.paused or self._hint_calculating or is_ai_turn
                    else:
                        # Chế độ PvP, hiển thị số lượt của bên hiện tại
                        hint_count = self.hint_left.get(current_side, 0)
                        # Disable button khi đang tính toán hoặc không có hint left hoặc đang pause
                        button.disabled = hint_count <= 0 or self.paused or self._hint_calculating
                    button.text = f"Hint (H) ({hint_count})"
                elif button.key == "pause":
                    button.text = "Resume (P)" if self.paused else "Pause (P)"
                elif button.key == "resign":
                    # Resign按钮使用danger颜色
                    # Kiểm tra xem button resign có nằm trong vùng đúng không (không phải dưới Move History)
                    # Button resign phải nằm trong button area, không phải trong history area
                    history_rect = self.layout.get_history_rect(panel_rect)
                    scoreboard_rect = self.layout.get_scoreboard_rect(panel_rect)
                    # Chỉ render nếu button không nằm trong history_rect hoặc giữa history và scoreboard
                    button_bottom = button.rect.bottom
                    history_bottom = history_rect.bottom
                    scoreboard_top = scoreboard_rect.top
                    # Nếu button nằm giữa history và scoreboard (vùng đánh dấu đỏ), không render
                    if history_bottom < button_bottom < scoreboard_top:
                        continue  # Skip render button resign ở vị trí sai
                    pass
                button.render(surface)
            
        # 渲染Toast
        for toast in self.ui_toasts:
            toast.render(surface)
            
        # 渲染工具提示
        for tooltip in self.ui_tooltips.values():
            tooltip.render(surface)
        
        # 渲染暂停覆盖层 - Sử dụng ảnh pauesbtt.png
        if self.paused:
            # Vẽ overlay tối
            screen_w, screen_h = surface.get_size()
            overlay = pygame.Surface((screen_w, screen_h), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 180))
            surface.blit(overlay, (0, 0))
            
            # Lấy ảnh pause
            if self._pause_img:
                # Scale ảnh để phù hợp với màn hình
                img_w, img_h = self._pause_img.get_size()
                max_width = int(screen_w * 0.6)  # Tối đa 60% chiều rộng
                max_height = int(screen_h * 0.7)  # Tối đa 70% chiều cao
                scale_w = max_width / img_w
                scale_h = max_height / img_h
                scale = min(scale_w, scale_h)
                
                draw_w = int(img_w * scale)
                draw_h = int(img_h * scale)
                
                # Scale ảnh
                if draw_w > 0 and draw_h > 0:
                    scaled_img = pygame.transform.smoothscale(self._pause_img, (draw_w, draw_h))
                else:
                    scaled_img = self._pause_img
                    draw_w, draw_h = scaled_img.get_size()
                
                # Vị trí dialog ở giữa màn hình
                dialog_x = (screen_w - draw_w) // 2
                dialog_y = (screen_h - draw_h) // 2
                
                # Vẽ ảnh pause
                surface.blit(scaled_img, (dialog_x, dialog_y))
                
                # Tính toán vị trí Continue button dựa trên phần trăm của ảnh
                # Continue button thường nằm ở phần dưới của ảnh
                continue_left_pct = 0.31   # 31% từ trái (giảm 1% để mở rộng sang trái 2%)
                continue_top_pct = 0.625    # 62.5% từ trên (tăng 0.5% từ 62% để dời xuống)
                continue_width_pct = 0.3995  # 39.95% chiều rộng dialog (tăng 2% từ 37.95%)
                continue_height_pct = 0.0972 # 9.72% chiều cao dialog
                
                self._pause_continue_button = pygame.Rect(
                    dialog_x + int(draw_w * continue_left_pct),
                    dialog_y + int(draw_h * continue_top_pct),
                    int(draw_w * continue_width_pct),
                    int(draw_h * continue_height_pct)
                )
                
                # Vùng chọn Continue button đã được ẩn (không vẽ border và highlight)
            else:
                # Fallback: dùng code cũ nếu không có ảnh
                center_x = screen_w // 2
                center_y = screen_h // 2
                button_width = 200
                button_height = 50
                button_rect = pygame.Rect(
                    center_x - button_width // 2,
                    center_y + 50,
                    button_width,
                    button_height
                )
                self._pause_continue_button = button_rect
        
        # 渲染中心消息（在棋盘中央）
        if self.center_message and not self.paused and not self.current_game_over:
            # 计算棋盘中心位置
            ox, oy = self.board_origin
            board_center_x = ox + 4 * self.square_size
            board_center_y = oy + 4 * self.square_size
            
            # 创建半透明背景
            message_bg = pygame.Surface((self.square_size * 3, self.square_size * 1.5), pygame.SRCALPHA)
            message_bg.fill((0, 0, 0, 180))
            bg_rect = message_bg.get_rect(center=(board_center_x, board_center_y))
            surface.blit(message_bg, bg_rect)
            
            # 渲染消息文本
            message_text = self.big_font.render(self.center_message, True, (255, 200, 100))
            text_rect = message_text.get_rect(center=(board_center_x, board_center_y))
            # 添加阴影效果
            shadow = self.big_font.render(self.center_message, True, (0, 0, 0))
            surface.blit(shadow, (text_rect.x + 2, text_rect.y + 2))
            surface.blit(message_text, text_rect)

        # Exit button đã được di chuyển vào _render_history_card, ngang với Move History
        # Không cần render ở đây nữa
        
        # Volume control ở góc trên bên phải
        self._render_volume_control(surface)

        # Debug overlay
        if self.show_debug:
            fps = int(pygame.time.get_ticks() % 1000)  # placeholder; real fps overlay can be passed in
            dbg = self.small_font.render(f"Rects: {len(dirty)}", True, (255,255,0))
            surface.blit(dbg, (self.panel_rect.x, self.panel_rect.y - 20))
            dirty.append(dbg.get_rect(topleft=(self.panel_rect.x, self.panel_rect.y - 20)))

        # Render modal và promotion popup CUỐI CÙNG để hiển thị trên cùng tất cả các layer
        if self.modal_active:
            rect = self._modal_rect()
            self._render_modal(surface)
            dirty.append(rect)
        if self.promotion_pending and self.promo_from_to is not None:
            rect = self._modal_rect()
            self._render_promotion(surface)
            dirty.append(rect)

        return dirty

    # ---------------- Board/UI helpers ----------------
    def _invalidate_static_surfaces(self) -> None:
        self._board_static_surface = None
        self._board_static_key = None
        self._exit_img_cache.clear()

    def _get_board_static_surface(self) -> Tuple[pygame.Surface, int]:
        frame_margin = 6
        board_size = self.square_size * 8
        outer_size = board_size + frame_margin * 2
        accent_color = self.ui_colors.get("accent", (74, 158, 255))
        bg_color = self.ui_colors.get("panel_alt", self.ui_colors.get("panel", (13, 13, 13)))
        light = self.ui_colors.get("board_light", (240, 217, 181))
        dark = self.ui_colors.get("board_dark", (181, 136, 99))
        border_color = (60, 70, 90, 150)
        radius = getattr(self.ui_theme, "RADIUS", 0)

        key = (
            self.square_size,
            frame_margin,
            accent_color,
            bg_color,
            light,
            dark,
            border_color,
            radius,
        )
        if self._board_static_surface is not None and self._board_static_key == key:
            return self._board_static_surface, frame_margin

        surf = pygame.Surface((outer_size + 4, outer_size + 4), pygame.SRCALPHA)

        # Shadow
        shadow_surf = pygame.Surface((outer_size, outer_size), pygame.SRCALPHA)
        shadow_surf.fill((0, 0, 0, 100))
        surf.blit(shadow_surf, (4, 4), special_flags=pygame.BLEND_ALPHA_SDL2)

        # Outer background and borders
        outer_rect = pygame.Rect(0, 0, outer_size, outer_size)
        pygame.draw.rect(surf, bg_color, outer_rect, border_radius=radius)
        pygame.draw.rect(surf, accent_color, outer_rect, 4, border_radius=radius)
        inner_rect = pygame.Rect(outer_rect.x + 2, outer_rect.y + 2, outer_rect.width - 4, outer_rect.height - 4)
        try:
            pygame.draw.rect(surf, border_color, inner_rect, 1, border_radius=max(0, radius - 1))
        except TypeError:
            pygame.draw.rect(surf, border_color, inner_rect, 1)
        highlight_rect = pygame.Rect(outer_rect.x, outer_rect.y, outer_rect.width, 3)
        highlight_color = tuple(min(255, c + 60) for c in accent_color[:3])
        pygame.draw.rect(surf, highlight_color, highlight_rect, border_radius=radius)

        # Board squares
        board_origin_local = frame_margin
        for rank in range(8):
            for file in range(8):
                x = board_origin_local + file * self.square_size
                y = board_origin_local + (7 - rank) * self.square_size
                rect = pygame.Rect(x, y, self.square_size, self.square_size)
                color = light if (file + rank) % 2 == 0 else dark
                pygame.draw.rect(surf, color, rect)
                pygame.draw.rect(surf, (80, 60, 40), rect, 1)

        self._board_static_surface = surf
        self._board_static_key = key
        return self._board_static_surface, frame_margin

    def _render_board(self, surface: pygame.Surface) -> None:
        """使用新UI系统渲染棋盘"""
        ox, oy = self.board_origin
        board_surface, frame_margin = self._get_board_static_surface()
        surface.blit(board_surface, (ox - frame_margin, oy - frame_margin))

        # 预计算集合（集中渲染）
        legal_to_set, capture_to_set, castle_to_set, ep_to_set = self._compute_move_indicator_sets()
        hint_to_set = set(m.to_square for m in self.hint_moves) if self.hint_moves else set()

        for rank in range(8):
            for file in range(8):
                x = ox + file * self.square_size
                y = oy + (7 - rank) * self.square_size
                rect = pygame.Rect(x, y, self.square_size, self.square_size)

                # Highlight selected and legal
                sq_index = chess.square(file, rank)
                if self.selected_sq == sq_index:
                    pygame.draw.rect(surface, self.ui_colors.get("accent", (74, 158, 255)), rect, 4)
                    # 选中背景轻微叠层
                    surface.blit(self._get_overlay(self.square_size, "accent", 40), rect.topleft)
                else:
                    if sq_index in legal_to_set:
                        if sq_index in ep_to_set or sq_index in capture_to_set:
                            self._draw_move_indicator(surface, rect, "ep" if sq_index in ep_to_set else "capture")
                        elif sq_index in castle_to_set:
                            self._draw_move_indicator(surface, rect, "castle")
                        else:
                            # 如果存在自定义指示图片，则优先使用图片代替圆点
                            marker = self._get_move_marker_surface(self.square_size)
                            if marker is not None:
                                marker_rect = marker.get_rect(center=(rect.x + self.square_size // 2, rect.y + self.square_size // 2))
                                surface.blit(marker, marker_rect)
                            else:
                                self._draw_move_indicator(surface, rect, "normal")
                    # 高亮提示移动 - 优化显示效果 với animation mượt
                    if sq_index in hint_to_set:
                        # Tìm nước đi tương ứng và vẽ với màu sắc khác nhau cho từng nước
                        hint_index = None
                        for i, hint_move in enumerate(self.hint_moves):
                            if hint_move.to_square == sq_index:
                                hint_index = i
                                break
                        
                        # Áp dụng alpha animation
                        base_alpha = 100 - (hint_index * 15) if hint_index is not None else 80
                        base_alpha = max(60, base_alpha)  # Đảm bảo tối thiểu 60
                        animated_alpha = int(base_alpha * self.hint_alpha)
                        
                        # Pulse effect cho hint tốt nhất (hint_index == 0)
                        if hint_index == 0:
                            pulse_factor = 1.0 + 0.15 * abs(math.sin(self.hint_pulse))
                            animated_alpha = int(animated_alpha * pulse_factor)
                            animated_alpha = min(120, animated_alpha)  # Giới hạn tối đa
                        
                        # Vẽ overlay với alpha animation
                        overlay = self._get_overlay(self.square_size, "accent", animated_alpha)
                        surface.blit(overlay, rect.topleft)
                        
                        # Vẽ border với animation
                        hint_color = self.ui_colors.get("accent", (74, 158, 255))
                        # Áp dụng alpha cho border color
                        border_alpha = int(255 * self.hint_alpha)
                        if hint_index == 0:
                            # Hint tốt nhất - border dày hơn với pulse effect
                            border_width = int(3 + 1 * abs(math.sin(self.hint_pulse)))
                            # Tạo color với alpha
                            border_color = (*hint_color[:3], border_alpha) if len(hint_color) > 3 else hint_color
                            pygame.draw.rect(surface, hint_color, rect, border_width)
                        else:
                            # Các hint khác - border mỏng hơn
                            border_width = int(2 * self.hint_alpha)
                            if border_width > 0:
                                pygame.draw.rect(surface, hint_color, rect, border_width)
                        
                    # 高亮最后一步
                    if self.last_move and (self.last_move.from_square == sq_index or self.last_move.to_square == sq_index):
                        surface.blit(self._get_overlay(self.square_size, "highlight_last", 100), rect.topleft)

                # 悬停在合法目标上的轻微加亮 - 优化效果
                if self._hover_sq is not None and sq_index == self._hover_sq and (sq_index in legal_to_set):
                    # Tăng độ sáng khi hover để dễ nhìn hơn
                    surface.blit(self._get_overlay(self.square_size, "accent", 70), rect.topleft)
                    # Thêm border để làm nổi bật ô được hover
                    pygame.draw.rect(surface, self.ui_colors.get("accent", (74, 158, 255)), rect, 3)

        # Draw pieces - use cached piece_map() to ensure no duplicates
        current_fen = self.engine.fen()
        if self._piece_map_cache is None or self._piece_map_cache_fen != current_fen:
            self._piece_map_cache = self.engine.board.piece_map()
            self._piece_map_cache_fen = current_fen
        piece_map = self._piece_map_cache
        
        # Tối ưu: pre-calculate target size và piece code mapping
        is_dark_fantasy = getattr(self.config, "PIECE_SKIN", "").lower() == "dark fantasy"
        target_size = max(12, int(self.square_size * 1.25)) if is_dark_fantasy else max(12, self.square_size - 8)
        piece_type_map = {
            chess.KING: "king",
            chess.QUEEN: "queen",
            chess.ROOK: "rook",
            chess.BISHOP: "bishop",
            chess.KNIGHT: "knight",
            chess.PAWN: "pawn",
        }
        center_x_offset = self.square_size // 2
        center_y_offset = self.square_size // 2
        
        for sq, piece in piece_map.items():
            # Skip drawing origin square for dragged piece; it will be drawn following cursor
            if self.dragging and self.drag_from_sq == sq:
                continue
            
            file = chess.square_file(sq)
            rank = chess.square_rank(sq)
            x = ox + file * self.square_size
            y = oy + (7 - rank) * self.square_size
            code = ("w_" if piece.color else "b_") + piece_type_map[piece.piece_type]
            
            # Cache piece images nếu có thể
            cache_key = (code, target_size)
            if cache_key in self._piece_cache:
                img = self._piece_cache[cache_key]
            else:
                img = self.assets.get_piece_image(code, target_size)
                # Giới hạn cache size
                if len(self._piece_cache) < 50:  # Cache tối đa 50 pieces
                    self._piece_cache[cache_key] = img
            
            # Center piece in square - pre-calculated offsets
            piece_rect = img.get_rect(center=(x + center_x_offset, y + center_y_offset))
            surface.blit(img, piece_rect)

        # Coordinates (a-h, 1-8) - pre-rendered cache with responsive font, 修复对齐问题
        coord_font_size = self.layout.get_coord_font_size()
        coord_font = self.assets.get_font(coord_font_size)
        
        if self._last_square_size != self.square_size or not self._coords_cache:
            self._coords_cache = []
            # Files (a-h) - bottom and top
            for i in range(8):
                file_char = chr(ord('a') + i)  # lowercase a-h
                # Bottom coordinates - 使用对比度更高的颜色确保可读性
                bottom_sq_is_dark = (i + 7) % 2 == 1
                txt_b = coord_font.render(file_char, True, (255, 255, 255) if bottom_sq_is_dark else (40, 40, 40))
                # Top coordinates
                top_sq_is_dark = i % 2 == 1
                txt_t = coord_font.render(file_char, True, (255, 255, 255) if top_sq_is_dark else (40, 40, 40))
                self._coords_cache.append((txt_b, (i, 'b')))
                self._coords_cache.append((txt_t, (i, 't')))
            # Ranks (1-8) - left and right
            for i in range(8):
                rank_char = str(8 - i)  # 8 at top, 1 at bottom
                # Left coordinates - 使用对比度更高的颜色
                left_sq_is_dark = i % 2 == 0
                txt_l = coord_font.render(rank_char, True, (255, 255, 255) if left_sq_is_dark else (40, 40, 40))
                # Right coordinates
                right_sq_is_dark = (7 - i) % 2 == 0
                txt_r = coord_font.render(rank_char, True, (255, 255, 255) if right_sq_is_dark else (40, 40, 40))
                self._coords_cache.append((txt_l, (i, 'l')))
                self._coords_cache.append((txt_r, (i, 'r')))
            self._last_square_size = self.square_size
        
        # Render coordinates - 响应式位置，精确对齐
        # 使用clamp确保偏移量在所有缩放级别下合适
        coord_offset = max(3, min(int(self.square_size * 0.06), 8))  # 6% of square size, clamped
        
        for surf_txt, (i, poscode) in self._coords_cache:
            if poscode == 'b':  # Bottom files (a-h) - 精确居中
                x = ox + i * self.square_size + (self.square_size - surf_txt.get_width()) // 2
                y = oy + 8 * self.square_size + coord_offset
                surface.blit(surf_txt, (x, y))
            elif poscode == 't':  # Top files (a-h) - 精确居中
                x = ox + i * self.square_size + (self.square_size - surf_txt.get_width()) // 2
                y = oy - surf_txt.get_height() - coord_offset
                surface.blit(surf_txt, (x, y))
            elif poscode == 'l':  # Left ranks (8-1) - 垂直居中
                x = ox - surf_txt.get_width() - coord_offset
                y = oy + i * self.square_size + (self.square_size - surf_txt.get_height()) // 2
                surface.blit(surf_txt, (x, y))
            else:  # Right ranks (8-1) - 垂直居中
                x = ox + 8 * self.square_size + coord_offset
                y = oy + i * self.square_size + (self.square_size - surf_txt.get_height()) // 2
                surface.blit(surf_txt, (x, y))

        # 将军高亮（当前走子方王被将军）
        try:
            if self.engine.board.is_check():
                king_sq = self.engine.board.king(self.engine.board.turn)
                if king_sq is not None:
                    k_file = chess.square_file(king_sq)
                    k_rank = chess.square_rank(king_sq)
                    kx = ox + k_file * self.square_size
                    ky = oy + (7 - k_rank) * self.square_size
                    surface.blit(self._get_overlay(self.square_size, "danger", 100), (kx, ky))
                    pygame.draw.rect(surface, self.ui_colors.get("danger", (239, 68, 68)), pygame.Rect(kx, ky, self.square_size, self.square_size), 3)
        except Exception:
            pass

    def _square_center(self, square: int) -> Tuple[float, float]:
        file = chess.square_file(square)
        rank = chess.square_rank(square)
        cx = self.board_origin[0] + file * self.square_size + self.square_size / 2
        cy = self.board_origin[1] + (7 - rank) * self.square_size + self.square_size / 2
        return float(cx), float(cy)

    def _update_volume_from_mouse(self, mouse_x: int) -> None:
        """Cập nhật volume dựa trên vị trí chuột"""
        if self._volume_slider_track.width == 0:
            return
        
        # Tính toán volume từ vị trí chuột
        track_x = self._volume_slider_track.x
        track_width = self._volume_slider_track.width
        
        # Clamp mouse position to track bounds
        relative_x = max(0, min(mouse_x - track_x, track_width))
        new_volume = relative_x / track_width
        
        # Clamp volume to 0-1
        self.volume = max(0.0, min(1.0, new_volume))
        
        # Apply volume to pygame mixer
        try:
            pygame.mixer.music.set_volume(self.volume)
        except Exception:
            pass
    
    def _render_volume_control(self, surface: pygame.Surface) -> None:
        """Render volume control ở góc trên bên phải"""
        screen_w, screen_h = surface.get_size()
        
        # Tính toán vị trí ở góc trên bên phải
        margin = 20
        control_width = 180
        control_height = 40
        control_x = screen_w - control_width - margin
        control_y = margin
        
        # Container cho volume control
        container_rect = pygame.Rect(control_x, control_y, control_width, control_height)
        self._volume_rect = container_rect
        
        # Check hover
        mouse_pos = pygame.mouse.get_pos()
        is_hovered = container_rect.collidepoint(mouse_pos) or self._volume_dragging
        
        # Background với glass effect
        bg_alpha = 200 if is_hovered else 160
        bg_surf = pygame.Surface((control_width, control_height), pygame.SRCALPHA)
        bg_surf.fill((28, 32, 40, bg_alpha))
        surface.blit(bg_surf, container_rect, special_flags=pygame.BLEND_ALPHA_SDL2)
        
        # Border
        border_color = (70, 140, 210) if is_hovered else (60, 70, 85)
        pygame.draw.rect(surface, border_color, container_rect, 2, border_radius=10)
        
        # Icon loa (volume icon)
        icon_x = control_x + 10
        icon_y = control_y + control_height // 2
        icon_size = 20
        
        # Vẽ icon loa đơn giản
        if self.volume > 0:
            # Loa có âm thanh
            speaker_points = [
                (icon_x, icon_y - 6),
                (icon_x + 8, icon_y - 6),
                (icon_x + 14, icon_y - 12),
                (icon_x + 14, icon_y + 12),
                (icon_x + 8, icon_y + 6),
                (icon_x, icon_y + 6),
            ]
            pygame.draw.polygon(surface, (255, 255, 255), speaker_points)
            # Sound waves
            if self.volume > 0.3:
                pygame.draw.arc(surface, (255, 255, 255), 
                               pygame.Rect(icon_x + 12, icon_y - 8, 12, 16), 
                               -0.5, 0.5, 2)
            if self.volume > 0.6:
                pygame.draw.arc(surface, (255, 255, 255), 
                               pygame.Rect(icon_x + 16, icon_y - 10, 14, 20), 
                               -0.5, 0.5, 2)
        else:
            # Loa bị tắt (muted)
            speaker_points = [
                (icon_x, icon_y - 6),
                (icon_x + 8, icon_y - 6),
                (icon_x + 14, icon_y - 12),
                (icon_x + 14, icon_y + 12),
                (icon_x + 8, icon_y + 6),
                (icon_x, icon_y + 6),
            ]
            pygame.draw.polygon(surface, (150, 150, 150), speaker_points)
            # X mark
            pygame.draw.line(surface, (255, 100, 100), 
                           (icon_x + 16, icon_y - 6), 
                           (icon_x + 24, icon_y + 6), 3)
            pygame.draw.line(surface, (255, 100, 100), 
                           (icon_x + 16, icon_y + 6), 
                           (icon_x + 24, icon_y - 6), 3)
        
        # Slider track
        slider_x = icon_x + 35
        slider_y = control_y + control_height // 2
        slider_width = control_width - 60
        slider_height = 6
        
        track_rect = pygame.Rect(slider_x, slider_y - slider_height // 2, 
                                slider_width, slider_height)
        self._volume_slider_track = track_rect
        
        # Track background
        pygame.draw.rect(surface, (60, 60, 70), track_rect, border_radius=3)
        
        # Fill (volume level)
        fill_width = int(slider_width * self.volume)
        if fill_width > 0:
            fill_rect = pygame.Rect(slider_x, slider_y - slider_height // 2, 
                                   fill_width, slider_height)
            pygame.draw.rect(surface, (70, 140, 210), fill_rect, border_radius=3)
        
        # Knob (slider handle)
        knob_x = slider_x + int(slider_width * self.volume)
        knob_radius = 8 if is_hovered else 6
        knob_color = (90, 160, 230) if is_hovered else (70, 140, 210)
        pygame.draw.circle(surface, knob_color, (knob_x, slider_y), knob_radius)
        pygame.draw.circle(surface, (255, 255, 255), (knob_x, slider_y), knob_radius, 2)
        
        # Volume percentage text
        if is_hovered:
            vol_text = self.small_font.render(f"{int(self.volume * 100)}%", True, (255, 255, 255))
            text_rect = vol_text.get_rect(center=(control_x + control_width // 2, control_y - 12))
            # Background for text
            text_bg = pygame.Rect(text_rect.x - 4, text_rect.y - 2, 
                                 text_rect.width + 8, text_rect.height + 4)
            bg_surf = pygame.Surface((text_bg.width, text_bg.height), pygame.SRCALPHA)
            bg_surf.fill((28, 32, 40, 200))
            surface.blit(bg_surf, text_bg, special_flags=pygame.BLEND_ALPHA_SDL2)
            pygame.draw.rect(surface, (70, 140, 210), text_bg, 1, border_radius=5)
            surface.blit(vol_text, text_rect)

    def _recompute_layout(self, force: bool = False) -> None:
        """重新计算布局 - 使用响应式布局系统"""
        board_rect = self.layout.get_board_rect()
        new_board_origin = (board_rect.x, board_rect.y)
        new_square_size = self.layout.get_square_size()
        new_panel_rect = self.layout.get_panel_rect()

        layout_changed = force or new_board_origin != getattr(self, "board_origin", None) or new_square_size != getattr(self, "square_size", None) or new_panel_rect != getattr(self, "panel_rect", None)

        self.board_origin = new_board_origin
        self.panel_rect = new_panel_rect

        if layout_changed:
            if new_square_size != getattr(self, "square_size", None):
                self._coords_cache = []
                self._last_square_size = 0
                self._invalidate_static_surfaces()
            self.square_size = new_square_size

        if force or layout_changed or not self.ui_buttons:
            if not self.ui_buttons:
                self._init_ui_components()
            else:
                panel_rect = self.panel_rect
                for i, key in enumerate(self.button_order):
                    if key in self.ui_buttons:
                        button_rect = self.layout.get_button_rect(i, panel_rect)
                        self.ui_buttons[key].rect = button_rect
                        self.ui_buttons[key].font = self.font  # 更新字体
        
    def _init_ui_components(self):
        """初始化UI组件"""
        # Xóa tất cả buttons cũ để tránh trùng lặp
        self.ui_buttons.clear()
        self.ui_tooltips.clear()
        
        # Đảm bảo không có button resign cũ nào còn sót lại
        # Xóa tất cả buttons có key chứa "resign" (case-insensitive)
        keys_to_remove = [k for k in self.ui_buttons.keys() if k and "resign" in k.lower()]
        for k in keys_to_remove:
            del self.ui_buttons[k]
        
        panel_rect = self.layout.get_panel_rect()
        
        # 创建按钮 - 使用统一的button_configs定义
        button_texts = {
            "undo": "Undo (U)",
            "hint": "Hint (H)",
            "new": "New Game (N)",
            "pause": "Pause (P)",
            "resign": "Resign (R)",
        }
        button_callbacks = {
            "undo": lambda: self._open_confirm("undo"),
            "hint": lambda: self._open_confirm("hint"),
            "new": lambda: self._open_confirm("new"),
            "pause": lambda: self._toggle_pause(),
            "resign": lambda: self._open_confirm("resign"),
        }
        
        # Đảm bảo chỉ tạo một button resign
        resign_created = False
        for key, index in self.button_configs:
            text = button_texts.get(key, "")
            callback = button_callbacks.get(key)
            if callback:
                # Kiểm tra nếu đã có button resign và đang tạo lại -> skip để tránh duplicate
                if key == "resign" and resign_created:
                    continue
                if key == "resign":
                    resign_created = True
                rect = self.layout.get_button_rect(index, panel_rect)
                self.ui_buttons[key] = Button(
                    rect=rect,
                    text=text,
                    theme=self.ui_theme,
                    colors=self.ui_colors,
                    font=self.font,
                    callback=callback,
                    tooltip=self._get_tooltip_text(key),
                    key=key,
                )
            
        # 创建工具提示
        for key, button in self.ui_buttons.items():
            if button.tooltip:
                self.ui_tooltips[key] = Tooltip(
                    text=button.tooltip,
                    theme=self.ui_theme,
                    colors=self.ui_colors,
                    font=self.small_font,
                )

    def _render_panel(self, surface: pygame.Surface, panel_rect: Optional[pygame.Rect] = None) -> None:
        """使用新UI系统渲染控制面板"""
        # 使用已传入的panel_rect或重新计算，避免重复计算
        if panel_rect is None:
            panel_rect = self.layout.get_panel_rect()
        margin = self.ui_theme.SPACING
        
        # 渲染玩家资料卡片
        self._render_player_profiles(surface, panel_rect, margin)
        
        # 渲染限制信息卡片
        self._render_limits_card(surface, panel_rect, margin)
        
        # 渲染历史记录卡片
        self._render_history_card(surface, panel_rect, margin)
        
        # 渲染记分板卡片
        self._render_scoreboard_card(surface, panel_rect, margin)
        
        # 渲染游戏结束消息
        if self.current_game_over:
            self._render_game_over_message(surface, panel_rect, margin)
        
        # 绘制拖拽的棋子 - 优化的视觉效果 với cache
        if self.dragging and self._drag_scaled_cache is not None:
            mx, my = pygame.mouse.get_pos()
            # 应用offset - 让quân cờ跟随鼠标更自然
            center_x = mx + self.drag_offset[0]
            center_y = my + self.drag_offset[1]
            
            # Sử dụng cached scaled surface thay vì scale mỗi frame
            rect = self._drag_scaled_cache.get_rect(center=(center_x, center_y))
            
            # Vẽ shadow cho quân cờ đang kéo để nổi bật hơn (sử dụng cache)
            shadow_offset = 4
            if self._drag_shadow_cache is not None:
                shadow_rect = rect.copy()
                shadow_rect.x += shadow_offset
                shadow_rect.y += shadow_offset
                surface.blit(self._drag_shadow_cache, shadow_rect, special_flags=pygame.BLEND_ALPHA_SDL2)
            
            # Vẽ quân cờ chính
            surface.blit(self._drag_scaled_cache, rect)
            
    def _render_player_profiles(self, surface: pygame.Surface, panel_rect: pygame.Rect, margin: int):
        """渲染玩家资料 - 改进的设计，更美观和现代化"""
        import os
        
        is_white_turn = self.engine.board.turn
        
        # 渲染两个玩家卡片 - 并排显示
        for player_index, (is_white, player_name, player_avatar, is_human) in enumerate([
            (True, self.white_name, self.white_avatar, self.white_is_human),
            (False, self.black_name, self.black_avatar, self.black_is_human)
        ]):
            profile_rect = self.layout.get_player_profile_rect(player_index, panel_rect)
            
            # 改进的卡片设计 - 添加阴影和渐变
            # 外阴影
            shadow_rect = profile_rect.copy()
            shadow_rect.x += 3
            shadow_rect.y += 3
            shadow_surf = pygame.Surface((profile_rect.width, profile_rect.height), pygame.SRCALPHA)
            shadow_surf.fill((0, 0, 0, 100))
            surface.blit(shadow_surf, shadow_rect, special_flags=pygame.BLEND_ALPHA_SDL2)
            
            # 高亮当前玩家 - 改进的效果
            is_active = (is_white and is_white_turn) or (not is_white and not is_white_turn)
            
            # 卡片背景 - 优化颜色，更好的对比度和视觉层次
            if is_active and not self.current_game_over:
                card_bg_color = (48, 55, 72)  # 更亮的背景突出active状态
            else:
                card_bg_color = (32, 38, 50)  # 较暗的背景
            pygame.draw.rect(surface, card_bg_color, profile_rect, border_radius=self.ui_theme.RADIUS)
            
            # 添加渐变效果增强视觉效果
            if is_active and not self.current_game_over:
                # 顶部高光带
                highlight_height = profile_rect.height // 4
                for i in range(highlight_height):
                    alpha = int(30 * (1 - i / highlight_height))
                    if alpha > 0:
                        highlight_color = tuple(min(255, c + alpha) for c in card_bg_color[:3])
                        highlight_line = pygame.Rect(
                            profile_rect.x,
                            profile_rect.y + i,
                            profile_rect.width,
                            1
                        )
                        pygame.draw.rect(surface, highlight_color, highlight_line)
            
            # 卡片边框 - 优化，更清晰的视觉层次
            border_color = self.ui_colors.get("border", (70, 80, 95))
            border_width = 1 if not is_active or self.current_game_over else 3
            pygame.draw.rect(surface, border_color, profile_rect, border_width, border_radius=self.ui_theme.RADIUS)
            if is_active and not self.current_game_over:
                # 外发光
                glow = pygame.Surface((profile_rect.width + 8, profile_rect.height + 8), pygame.SRCALPHA)
                glow_rect = pygame.Rect(4, 4, profile_rect.width, profile_rect.height)
                accent_color = self.ui_colors.get("accent", (74, 158, 255))
                glow_color = (*accent_color[:3], 80)
                try:
                    pygame.draw.rect(glow, glow_color, glow_rect, border_radius=self.ui_theme.RADIUS)
                except TypeError:
                    pygame.draw.rect(glow, accent_color, glow_rect, border_radius=self.ui_theme.RADIUS)
                surface.blit(glow, (profile_rect.x - 4, profile_rect.y - 4), special_flags=pygame.BLEND_ALPHA_SDL2)
                
                # 高亮边框
                pygame.draw.rect(surface, accent_color, profile_rect, 3, border_radius=self.ui_theme.RADIUS)
                
                # 顶部高光条
                highlight_rect = pygame.Rect(profile_rect.x, profile_rect.y, profile_rect.width, 3)
                highlight_color = tuple(min(255, c + 50) for c in accent_color[:3])
                pygame.draw.rect(surface, highlight_color, highlight_rect, border_radius=self.ui_theme.RADIUS)
            
            # 使用布局系统优化的头像大小 - Layout dọc
            avatar_size = self.layout.get_avatar_size(profile_rect)
            # Layout dọc: avatar nằm bên trái card, căn giữa theo chiều cao
            avatar_x = profile_rect.x + int(margin * 1.2)
            avatar_y = profile_rect.y + (profile_rect.height - avatar_size) // 2
            
            # 加载并缩放头像 - 优化设计，现代化
            avatar_filename = os.path.basename(player_avatar or ("human_male.png" if is_human else "ai_bot.png"))
            avatar_img = self.assets.get_avatar(avatar_filename, avatar_size)
            avatar_rect = pygame.Rect(avatar_x, avatar_y, avatar_size, avatar_size)
            
            # 创建圆形mask用于头像
            mask_size = avatar_size - 8
            mask_surface = pygame.Surface((mask_size, mask_size), pygame.SRCALPHA)
            mask_center = (mask_size // 2, mask_size // 2)
            mask_radius = mask_size // 2
            pygame.draw.circle(mask_surface, (255, 255, 255, 255), mask_center, mask_radius)
            
            # 头像阴影 - 优化版，单层阴影（避免lag）
            shadow_offset = 5
            shadow_rect = avatar_rect.copy()
            shadow_rect.x += shadow_offset
            shadow_rect.y += shadow_offset
            shadow_surf = pygame.Surface((avatar_size, avatar_size), pygame.SRCALPHA)
            shadow_surf.fill((0, 0, 0, 100))
            # 应用圆形mask到阴影
            shadow_mask = pygame.Surface((avatar_size, avatar_size), pygame.SRCALPHA)
            pygame.draw.circle(shadow_mask, (255, 255, 255, 255), (avatar_size // 2, avatar_size // 2), avatar_size // 2 - 2)
            shadow_surf.blit(shadow_mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
            surface.blit(shadow_surf, shadow_rect, special_flags=pygame.BLEND_ALPHA_SDL2)
            
            # 头像背景 - 优化版，避免lag
            avatar_bg = pygame.Surface((avatar_size, avatar_size), pygame.SRCALPHA)
            bg_color = (25, 30, 45, 240)
            # 使用简单填充 + highlight
            pygame.draw.circle(avatar_bg, bg_color, (avatar_size // 2, avatar_size // 2), avatar_size // 2 - 2)
            # Top highlight
            highlight_rect = pygame.Rect(0, 0, avatar_size, avatar_size // 3)
            highlight_color = (35, 40, 55, 200)
            highlight_mask = pygame.Surface((avatar_size, avatar_size), pygame.SRCALPHA)
            pygame.draw.ellipse(highlight_mask, highlight_color, highlight_rect)
            avatar_bg.blit(highlight_mask, (0, 0), special_flags=pygame.BLEND_ALPHA_SDL2)
            surface.blit(avatar_bg, avatar_rect.topleft)
            
            # 头像图片 - 圆形裁剪
            avatar_img_scaled = pygame.transform.smoothscale(avatar_img, (mask_size, mask_size))
            # 创建临时surface并应用mask
            avatar_masked = pygame.Surface((mask_size, mask_size), pygame.SRCALPHA)
            avatar_masked.blit(avatar_img_scaled, (0, 0))
            avatar_masked.blit(mask_surface, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
            surface.blit(avatar_masked, (avatar_rect.x + 4, avatar_rect.y + 4))
            
            # Active glow effect - 外发光，优化版（避免lag）
            # 先绘制 glow effect（在 frame 后面）
            if is_active and not self.current_game_over:
                border_color = self.ui_colors.get("accent", (74, 158, 255))
                glow_radius = avatar_size // 2 + 8
                glow_surf = pygame.Surface((glow_radius * 2, glow_radius * 2), pygame.SRCALPHA)
                # 使用简单的glow effect，避免loop
                glow_color = (*border_color[:3], 40)
                pygame.draw.circle(glow_surf, glow_color, (glow_radius, glow_radius), glow_radius)
                # 内圈glow
                inner_glow_radius = glow_radius - 3
                inner_glow_color = (*border_color[:3], 60)
                pygame.draw.circle(glow_surf, inner_glow_color, (glow_radius, glow_radius), inner_glow_radius)
                surface.blit(glow_surf, (avatar_rect.centerx - glow_radius, avatar_rect.centery - glow_radius), special_flags=pygame.BLEND_ALPHA_SDL2)
            
            # 为 Player 1 和 Player 2 使用 ornate frame
            # Player 1: avt1.png, Player 2: avt2.png
            # Frame 绘制在 glow effect 之后，确保 frame 在最上层
            # Layout dọc: avatar nhỏ hơn nên frame cũng điều chỉnh tỷ lệ
            if player_index == 0:
                frame_scale_factor = 1.65  # Player 1: avt1.png - tăng lên vì avatar nhỏ
            else:
                frame_scale_factor = 1.45  # Player 2: avt2.png - tăng lên vì avatar nhỏ
            frame_size = int(avatar_size * frame_scale_factor)
            
            frame_img = self._load_avatar_frame(player_index, frame_size)
            if frame_img is not None:
                # Tính toán vị trí để khung căn giữa với avatar
                frame_x = avatar_rect.centerx - frame_size // 2
                frame_y = avatar_rect.centery - frame_size // 2
                # 使用 ornate frame 替换默认边框，frame 会覆盖在 avatar 和 glow 之上
                surface.blit(frame_img, (frame_x, frame_y))
            else:
                # 回退到默认边框
                border_color = self.ui_colors.get("accent", (74, 158, 255)) if is_active and not self.current_game_over else (100, 110, 130)
                border_width = 4 if (is_active and not self.current_game_over) else 2
                pygame.draw.circle(surface, border_color, avatar_rect.center, avatar_size // 2, border_width)
                inner_border_radius = avatar_size // 2 - border_width - 2
                pygame.draw.circle(surface, (60, 70, 90, 180), avatar_rect.center, inner_border_radius, 1)
            
            # 玩家信息区域 - Layout dọc: nhiều không gian ngang hơn
            # Text area bắt đầu ngay sau avatar với spacing vừa phải
            info_x = avatar_x + avatar_size + int(margin * 1.5)
            info_y = profile_rect.y + int(margin * 1.2)
            # 计时器 - 响应式字体大小
            time_left = self.time_left[is_white]
            t = max(0, int(time_left))
            minutes = int(t // 60)
            seconds = int(t % 60)
            time_str = f"{minutes}:{seconds:02d}"
            
            # 计时器颜色 - 低时间警告
            if t < 30:
                time_color = self.ui_colors.get("danger", (239, 68, 68))
            elif is_active:
                time_color = self.ui_colors.get("accent", (34, 197, 94))
            else:
                time_color = self.ui_colors.get("text", (226, 232, 240))
            
            # 使用响应式字体大小渲染计时器 - 改进的设计，优化padding
            # 增加timer字体大小，让它更显眼
            timer_font = getattr(self, "timer_font", self.big_font)
            try:
                # 使用更大的字体让timer更清晰
                timer_font_size = int(timer_font.get_height() * 1.3)
                timer_font_large = pygame.font.SysFont(self.config.font_name, timer_font_size, bold=True)
            except:
                timer_font_large = timer_font
            
            time_surf = timer_font_large.render(time_str, True, time_color)
            # Layout dọc: timer padding nhỏ hơn vì card thấp hơn
            timer_padding_h = max(12, int(margin * 0.8))
            timer_padding_v = max(8, int(margin * 0.5))
            
            # Đặt timer ở góc trên bên phải, căn giữa theo chiều cao card
            timer_bg_rect = pygame.Rect(
                profile_rect.right - time_surf.get_width() - timer_padding_h * 2 - margin,
                profile_rect.y + (profile_rect.height - time_surf.get_height() - timer_padding_v * 2) // 2,
                time_surf.get_width() + timer_padding_h * 2,
                time_surf.get_height() + timer_padding_v * 2,
            )
            timer_bg_rect.y = max(profile_rect.y + margin, min(profile_rect.bottom - margin - timer_bg_rect.height, timer_bg_rect.y))
            
            # 计时器背景 - 改进的设计，优化颜色
            timer_bg = pygame.Surface(timer_bg_rect.size, pygame.SRCALPHA)
            timer_bg_color = (22, 28, 40, 240)  # 稍微亮一点，更好的对比度
            pygame.draw.rect(timer_bg, timer_bg_color, timer_bg.get_rect(), border_radius=12)
            
            # 边框 - 使用计时器颜色，优化
            pygame.draw.rect(timer_bg, (*time_color, 220), timer_bg.get_rect(), 2, border_radius=12)
            # 内发光 - 优化
            inner_glow = pygame.Rect(2, 2, timer_bg_rect.width - 4, timer_bg_rect.height - 4)
            pygame.draw.rect(timer_bg, (*time_color, 80), inner_glow, 1, border_radius=10)
            
            surface.blit(timer_bg, timer_bg_rect.topleft)
            # 文本阴影 - 多层增强可读性
            time_shadow = timer_font_large.render(time_str, True, (0, 0, 0))
            surface.blit(time_shadow, (timer_bg_rect.x + timer_padding_h + 2, timer_bg_rect.y + timer_padding_v + 2))
            surface.blit(time_shadow, (timer_bg_rect.x + timer_padding_h + 1, timer_bg_rect.y + timer_padding_v + 1))
            surface.blit(time_surf, (timer_bg_rect.x + timer_padding_h, timer_bg_rect.y + timer_padding_v))
            
            # Xóa timer icon vì bị lỗi hiển thị
            # Icon đã được xóa để tránh lỗi render

            # Layout dọc: có nhiều không gian ngang hơn cho text
            # Đảm bảo text không chạm vào timer
            info_max_width = max(100, timer_bg_rect.x - margin - info_x)

            # 玩家名称和类型
            # Xóa difficulty icons vì bị lỗi hiển thị
            player_label = player_name
            if self.mode == 'PvAI' and not is_human:
                player_type = "AI"
            else:
                player_type = "Human"

            # 渲染名称 - Layout dọc: hiển thị toàn bộ tên, không truncate
            name_font = getattr(self, "player_name_font", self.font)
            try:
                # Font size vừa phải cho layout dọc
                name_font_size = int(name_font.get_height() * 1.0)
                name_font_medium = pygame.font.SysFont(self.config.font_name, name_font_size, bold=True)
            except:
                name_font_medium = name_font
            
            # 优化颜色对比度
            if is_active and not self.current_game_over:
                name_color = (255, 255, 255)
            else:
                name_color = (220, 225, 235)
            
            # Hiển thị toàn bộ tên, không cắt ngắn
            # Nếu tên quá dài, wrap sang dòng thứ 2
            full_name_text = name_font_medium.render(player_label, True, name_color)
            
            if full_name_text.get_width() > info_max_width:
                # Wrap text: chia thành 2 dòng nếu cần
                words = player_label.split()
                line1 = ""
                line2 = ""
                
                for word in words:
                    test_line = (line1 + " " + word).strip()
                    test_surf = name_font_medium.render(test_line, True, name_color)
                    if test_surf.get_width() <= info_max_width:
                        line1 = test_line
                    else:
                        line2 = (line2 + " " + word).strip()
                
                # Nếu không có line2, tức là từ đầu tiên đã quá dài
                if not line2 and line1:
                    # Cắt bớt và thêm ...
                    while name_font_medium.render(line1 + "...", True, name_color).get_width() > info_max_width and len(line1) > 3:
                        line1 = line1[:-1]
                    line1 = line1 + "..."
                
                # Vẽ line 1
                name_text1 = name_font_medium.render(line1, True, name_color)
                name_shadow1 = name_font_medium.render(line1, True, (0, 0, 0))
                surface.blit(name_shadow1, (info_x + 1, info_y + 1))
                surface.blit(name_text1, (info_x, info_y))
                
                # Vẽ line 2 nếu có
                if line2:
                    line2_y = info_y + name_text1.get_height() + 2
                    # Cắt line2 nếu quá dài
                    while name_font_medium.render(line2 + "...", True, name_color).get_width() > info_max_width and len(line2) > 3:
                        line2 = line2[:-1]
                    if len(line2) < len((line2 + " ").join(words[len(line1.split()):])):
                        line2 = line2 + "..."
                    
                    name_text2 = name_font_medium.render(line2, True, name_color)
                    name_shadow2 = name_font_medium.render(line2, True, (0, 0, 0))
                    surface.blit(name_shadow2, (info_x + 1, line2_y + 1))
                    surface.blit(name_text2, (info_x, line2_y))
                    name_text = name_text2  # For type_y calculation
                else:
                    name_text = name_text1
            else:
                # Tên vừa vặn, hiển thị bình thường
                name_shadow = name_font_medium.render(player_label, True, (0, 0, 0))
                surface.blit(name_shadow, (info_x + 1, info_y + 1))
                surface.blit(full_name_text, (info_x, info_y))
                name_text = full_name_text

            # 玩家类型标签 - Layout dọc: nằm trên cùng dòng với tên hoặc dưới
            # Nếu tên ngắn, đặt role cùng dòng; nếu dài thì xuống dòng
            if full_name_text.get_width() <= info_max_width:
                # Tên ngắn: đặt role bên phải tên
                type_x = info_x + full_name_text.get_width() + int(margin * 1.5)
                type_y = info_y
            else:
                # Tên dài: đặt role xuống dưới
                type_x = info_x
                type_y = info_y + name_text.get_height() + 4
            
            # Xóa emoji icons, chỉ hiển thị text
            if is_human:
                type_color = (100, 210, 255)  # 亮蓝色更易识别
            else:
                type_color = (255, 180, 50)  # 橙色更易识别
            
            type_font = getattr(self, "player_info_font", self.small_font)
            # Chỉ hiển thị text role, không có icon
            role_display = player_type
            type_text = type_font.render(role_display, True, type_color)
            
            # 添加背景框增强可读性
            type_bg_padding = 5
            type_bg_rect = pygame.Rect(
                type_x - type_bg_padding,
                type_y - 2,
                type_text.get_width() + type_bg_padding * 2,
                type_text.get_height() + 4
            )
            # 半透明背景
            type_bg_surface = pygame.Surface(type_bg_rect.size, pygame.SRCALPHA)
            bg_alpha = 120 if is_active else 80
            pygame.draw.rect(type_bg_surface, (*type_color[:3], bg_alpha), type_bg_surface.get_rect(), border_radius=4)
            surface.blit(type_bg_surface, type_bg_rect.topleft)
            
            # 绘制文字
            surface.blit(type_text, (type_x, type_y))
            # Badge vị trí: bên phải role badge
            badge_x = type_x + type_text.get_width() + int(margin * 0.8)
            if not is_human:
                diff_color_map = {
                    "easy": ((39, 174, 96), (34, 153, 84)),
                    "medium": ((243, 156, 18), (230, 126, 34)),
                    "hard": ((231, 76, 60), (192, 57, 43)),
                }
                gradient_colors = diff_color_map.get(self.ai_difficulty, ((88, 166, 255), (74, 144, 226)))
                # 使用更醒目的难度显示
                difficulty_display = self.ai_difficulty.upper()
                badge_text = type_font.render(difficulty_display, True, (255, 255, 255))
                badge_padding = (10, 5)
                badge_rect = pygame.Rect(
                    badge_x,
                    type_y - 2,
                    badge_text.get_width() + badge_padding[0] * 2,
                    badge_text.get_height() + badge_padding[1] * 2,
                )
                # Badge background - 使用 màu đơn giản thay vì gradient để tránh lag
                badge_surface = pygame.Surface(badge_rect.size, pygame.SRCALPHA)
                badge_bg_color = (*gradient_colors[0][:3], 215)  # Dùng màu đầu tiên
                pygame.draw.rect(badge_surface, badge_bg_color, badge_surface.get_rect(), border_radius=6)
                # Top highlight
                highlight = pygame.Rect(0, 0, badge_rect.width, badge_rect.height // 3)
                highlight_color = tuple(min(255, c + 30) for c in gradient_colors[0][:3])
                pygame.draw.rect(badge_surface, (*highlight_color, 180), highlight, border_radius=6)
                pygame.draw.rect(badge_surface, (255, 255, 255, 120), badge_surface.get_rect(), 1, border_radius=6)
                surface.blit(badge_surface, badge_rect.topleft)
                surface.blit(badge_text, (badge_rect.x + badge_padding[0], badge_rect.y + badge_padding[1]))

            # AI思考指示器 - Layout dọc: đặt ở dưới role/difficulty badge
            if self.mode == 'PvAI' and not is_human and self.ai_thinking and is_active:
                thinking_y = type_y + type_text.get_height() + int(margin * 0.5)
                thinking_rect = pygame.Rect(
                    info_x,
                    thinking_y,
                    min(profile_rect.right - margin - info_x, 150),
                    getattr(self, "player_info_font", self.small_font).get_height() + int(margin * 0.4),
                )
                thinking_surface = pygame.Surface(thinking_rect.size, pygame.SRCALPHA)
                pygame.draw.rect(thinking_surface, (58, 166, 255, 60), thinking_surface.get_rect(), border_radius=6)
                surface.blit(thinking_surface, thinking_rect.topleft)
                thinking_text = getattr(self, "player_info_font", self.small_font).render("Thinking...", True, self.ui_colors.get("accent", (34, 197, 94)))
                surface.blit(thinking_text, (thinking_rect.x + int(margin * 0.4), thinking_rect.y + int(margin * 0.2)))
        
    def _render_limits_card(self, surface: pygame.Surface, panel_rect: pygame.Rect, margin: int):
        """渲染限制信息卡片 - 响应式布局"""
        # 获取窗口大小
        win_w, win_h = pygame.display.get_surface().get_size()
        
        # 使用布局系统计算按钮区域高度
        container_rect = self.layout.get_players_container_rect(panel_rect)
        button_height = max(28, min(self.layout.scale(36), int(win_h * 0.04)))
        spacing = self.layout.get_spacing()
        button_area_height = 3 * (button_height + spacing) + spacing
        
        # 计算限制卡片位置（按钮区域下方）
        limits_y = container_rect.bottom + margin + spacing + button_area_height + spacing
        limits_height = max(50, min(self.layout.scale(60), int(win_h * 0.08)))
        limits_rect = pygame.Rect(panel_rect.x + margin, limits_y, panel_rect.width - margin * 2, limits_height)
        
        limits_card = Card(limits_rect, self.ui_theme, self.ui_colors)
        limits_card.render(surface)
        
        # 显示限制信息 - 响应式字体
        current_side = "white" if self.engine.board.turn else "black"
        
        # Chỉ hiển thị số lần Undo và Hint của người chơi (human), không hiển thị của đối thủ/AI
        # Kiểm tra xem current_side có phải là AI không
        is_ai_side = False
        if self.mode == 'PvAI':
            is_ai_side = (current_side == 'white' and not self.white_is_human) or (current_side == 'black' and not self.black_is_human)
            # Trong PvAI, luôn hiển thị số lượt của bên human
            human_side = "white" if self.white_is_human else "black"
            undo_text = f"Undos: {self.undo_left.get(human_side, 0)}"
            hint_text = None if is_ai_side else f"Hints: {self.hint_left.get(human_side, 0)}"
        else:
            # Chế độ PvP, hiển thị số lượt của bên hiện tại
            undo_text = f"Undos: {self.undo_left.get(current_side, 0)}"
            hint_text = f"Hints: {self.hint_left.get(current_side, 0)}"
        
        # 使用响应式字体大小
        limits_font_size = max(10, min(int(self.small_font.get_height() * 0.9), 12))
        try:
            limits_font = self.assets.get_font(limits_font_size)
        except:
            limits_font = self.small_font
        
        undo_surf = limits_font.render(undo_text, True, self.ui_colors.get("text", (226, 232, 240)))
        
        # 垂直居中显示
        if hint_text:
            hint_surf = limits_font.render(hint_text, True, self.ui_colors.get("text", (226, 232, 240)))
            # Có cả undo và hint
            text_start_y = limits_rect.y + (limits_rect.height - (undo_surf.get_height() + hint_surf.get_height() + margin // 2)) // 2
            surface.blit(undo_surf, (limits_rect.x + margin, text_start_y))
            surface.blit(hint_surf, (limits_rect.x + margin, text_start_y + undo_surf.get_height() + margin // 2))
        else:
            # Chỉ có undo, căn giữa theo chiều dọc
            text_start_y = limits_rect.y + (limits_rect.height - undo_surf.get_height()) // 2
            surface.blit(undo_surf, (limits_rect.x + margin, text_start_y))
        
    def _render_history_card(self, surface: pygame.Surface, panel_rect: pygame.Rect, margin: int):
        """渲染历史记录卡片 - 改进的设计，更美观"""
        history_rect = self.layout.get_history_rect(panel_rect)
        
        # Bỏ shadow để tránh vẽ 2 lần - Card component đã có nền đen
        history_card = Card(history_rect, self.ui_theme, self.ui_colors)
        history_card.render(surface)
        
        # 标题 - 改进的设计
        title_label = "Move History"
        # Dành chỗ cho Exit button bên phải (phóng to x6)
        exit_button_width = 0
        if self._exit_img_raw is not None:
            screen_w, screen_h = surface.get_size()
            target_h = max(180, int(screen_h * 0.30))  # Phóng to x6 lần (3×2)
            iw, ih = self._exit_img_raw.get_size()
            scale = target_h / max(1, ih)
            exit_button_width = int(iw * scale) + margin
        
        max_title_width = history_rect.width - margin * 2 - exit_button_width
        title_text = self.font.render(title_label, True, (240, 240, 250))
        if title_text.get_width() > max_title_width:
            title_text = self.small_font.render(title_label, True, (240, 240, 250))
        
        # 标题下划线装饰
        title_y = history_rect.y + margin
        surface.blit(title_text, (history_rect.x + margin, title_y))
        underline_y = title_y + title_text.get_height() + 4
        underline_width = min(title_text.get_width(), max_title_width)
        underline_rect = pygame.Rect(history_rect.x + margin, underline_y, underline_width, 2)
        pygame.draw.rect(surface, self.ui_colors.get("accent", (74, 158, 255)), underline_rect)
        
        # Exit button ngang với Move History title - bên phải
        if self._exit_img_raw is not None:
            screen_w, screen_h = surface.get_size()
            # Phóng to x6 lần (3×2)
            target_h = max(180, min(int(screen_h * 0.30), int(title_text.get_height() * 9.0)))
            cached = self._exit_img_cache.get(target_h)
            if cached is None:
                iw, ih = self._exit_img_raw.get_size()
                scale = target_h / max(1, ih)
                draw_w = max(1, int(iw * scale))
                draw_h = max(1, int(ih * scale))
                cached = pygame.transform.smoothscale(self._exit_img_raw, (draw_w, draw_h))
                self._exit_img_cache[target_h] = cached
            img = cached
            # Position: ngang với title, bên phải history card
            exit_x = history_rect.right - img.get_width() - margin
            exit_y = title_y + (title_text.get_height() - img.get_height()) // 2  # Căn giữa theo chiều cao title
            
            # Thu nhỏ vùng click xuống chỉ còn phần chữ "Exit To Menu" (khoảng 50% chiều rộng và 35% chiều cao)
            # và đặt ở phần dưới của button
            click_width_scale = 0.50  # 50% chiều rộng
            click_height_scale = 0.35  # 35% chiều cao (chỉ phần chữ)
            click_width = int(img.get_width() * click_width_scale)
            click_height = int(img.get_height() * click_height_scale)
            
            # Căn giữa theo chiều ngang, nhưng đặt ở 60% chiều cao (phần dưới có chữ)
            click_x = exit_x + (img.get_width() - click_width) // 2
            click_y = exit_y + int(img.get_height() * 0.55)  # Bắt đầu từ 55% chiều cao
            
            self._exit_rect = pygame.Rect(click_x, click_y, click_width, click_height)
            
            # Vẽ ảnh đầy đủ
            surface.blit(img, (exit_x, exit_y))
        else:
            # Nếu không có image, reset exit rect
            self._exit_rect = pygame.Rect(0, 0, 0, 0)
        
        # 被吃掉的棋子显示区域
        captured_y = underline_y + 6 + margin
        captured_height = 40
        
        # 白方被吃掉的棋子
        if self.captured_white:
            white_captured_text = self.small_font.render("Captured white pieces:", True, self.ui_colors.get("muted", (148, 163, 184)))
            surface.blit(white_captured_text, (history_rect.x + margin, captured_y))
            piece_size = 24
            x_offset = history_rect.x + margin + white_captured_text.get_width() + margin
            for i, piece_code in enumerate(self.captured_white[:10]):  # 最多显示10个
                piece_img = self.assets.get_piece_image(piece_code, piece_size)
                surface.blit(piece_img, (x_offset + i * (piece_size + 2), captured_y))
        
        # 黑方被吃掉的棋子
        if self.captured_black:
            black_captured_y = captured_y + 20
            black_captured_text = self.small_font.render("Captured black pieces:", True, self.ui_colors.get("muted", (148, 163, 184)))
            surface.blit(black_captured_text, (history_rect.x + margin, black_captured_y))
            piece_size = 24
            x_offset = history_rect.x + margin + black_captured_text.get_width() + margin
            for i, piece_code in enumerate(self.captured_black[:10]):  # 最多显示10个
                piece_img = self.assets.get_piece_image(piece_code, piece_size)
                surface.blit(piece_img, (x_offset + i * (piece_size + 2), black_captured_y))
        
        # 历史记录列表（可滚动，防止溢出，响应式字体）
        history_start_y = captured_y + (40 if (self.captured_white or self.captured_black) else 0) + margin
        history_y = history_start_y
        # 响应式行高 - 使用clamp确保在所有缩放级别下合适
        line_height = max(18, min(int(self.small_font.get_height() * 1.5), 24))
        max_lines = max(1, (history_rect.bottom - history_y - margin) // line_height)

        # 生成“1. Nf3 Nc6”格式
        pairs = self._get_move_pairs_for_display()
        visible_pairs = pairs[-max_lines:]
        self._history_line_rects = []

        for i, text in enumerate(visible_pairs):
            y = history_y + i * line_height
            if y > history_rect.bottom - margin:
                break
            is_last_row = (i == len(visible_pairs) - 1)
            color = self.ui_colors.get("accent", (34, 197, 94)) if is_last_row and not self._review_active else self.ui_colors.get("muted", (148, 163, 184))
            max_line_width = history_rect.width - margin * 2 - 4
            line_surf = self.small_font.render(text, True, color)
            if line_surf.get_width() > max_line_width:
                try:
                    tiny_font = self.assets.get_font(max(9, int(self.small_font.get_height() * 0.9)))
                    line_surf = tiny_font.render(text, True, color)
                except Exception:
                    pass
            surface.blit(line_surf, (history_rect.x + margin, y))
            # 可点击区域
            line_rect = pygame.Rect(history_rect.x + margin, y, max_line_width, line_height)
            pair_global_index = len(pairs) - len(visible_pairs) + i
            self._history_line_rects.append((line_rect, pair_global_index))

        # 回放中当前选中行高亮边框
        if self._review_active and self._history_line_rects:
            idx = min(len(pairs) - 1, getattr(self, "_review_pair_index", len(pairs) - 1))
            for rect, pair_index in self._history_line_rects:
                if pair_index == idx:
                    pygame.draw.rect(surface, self.ui_colors.get("primary", (74, 158, 255)), rect, 2, border_radius=6)
                    break
        
    def _render_scoreboard_card(self, surface: pygame.Surface, panel_rect: pygame.Rect, margin: int):
        """渲染记分板卡片 - 改进的设计，更美观"""
        scoreboard_rect = self.layout.get_scoreboard_rect(panel_rect)
        
        # 卡片阴影
        shadow_rect = scoreboard_rect.copy()
        shadow_rect.x += 2
        shadow_rect.y += 2
        shadow_surf = pygame.Surface((scoreboard_rect.width, scoreboard_rect.height), pygame.SRCALPHA)
        shadow_surf.fill((0, 0, 0, 80))
        surface.blit(shadow_surf, shadow_rect, special_flags=pygame.BLEND_ALPHA_SDL2)
        
        scoreboard_card = Card(scoreboard_rect, self.ui_theme, self.ui_colors)
        scoreboard_card.render(surface)
        
        # 计算有效分数（扣除惩罚）
        eff_w = max(0, self.white_wins - (self.penalties_side['white']['undo'] + self.penalties_side['white']['hint']))
        eff_b = max(0, self.black_wins - (self.penalties_side['black']['undo'] + self.penalties_side['black']['hint']))
        total_played = self.game_index - 1
        
        # 标题 - 改进的设计
        title_text = self.font.render(f"Best of {self.N}", True, (240, 240, 250))
        title_y = scoreboard_rect.y + margin
        surface.blit(title_text, (scoreboard_rect.x + margin, title_y))
        
        # 标题下划线装饰
        underline_y = title_y + title_text.get_height() + 4
        underline_width = min(title_text.get_width(), scoreboard_rect.width - margin * 2)
        underline_rect = pygame.Rect(scoreboard_rect.x + margin, underline_y, underline_width, 2)
        pygame.draw.rect(surface, self.ui_colors.get("accent", (74, 158, 255)), underline_rect)
        
        # 游戏进度 - 改进的显示
        progress_text = self.small_font.render(f"Played: {total_played}/{self.N}", True, (200, 200, 210))
        progress_y = underline_y + 6 + margin // 2
        surface.blit(progress_text, (scoreboard_rect.x + margin, progress_y))
        
        # 分数显示 - 并排显示，响应式布局
        score_y = progress_y + progress_text.get_height() + margin // 2
        score_font_size = max(11, min(int(self.small_font.get_height() * 1.1), 14))
        try:
            score_font = self.assets.get_font(score_font_size)
        except:
            score_font = self.small_font
        
        white_score_text = score_font.render(f"White: {eff_w}", True, self.ui_colors.get("accent", (34, 197, 94)))
        black_score_text = score_font.render(f"Black: {eff_b}", True, self.ui_colors.get("primary", (79, 70, 229)))
        
        # 并排显示分数
        score_spacing = (scoreboard_rect.width - margin * 2 - white_score_text.get_width() - black_score_text.get_width()) // 3
        surface.blit(white_score_text, (scoreboard_rect.x + margin + score_spacing, score_y))
        surface.blit(black_score_text, (scoreboard_rect.x + margin + score_spacing * 2 + white_score_text.get_width(), score_y))
        
        # 进度条 - 改进的设计
        progress_width = scoreboard_rect.width - margin * 2
        progress_height = max(8, min(int(scoreboard_rect.height * 0.12), 12))
        progress_y_pos = scoreboard_rect.bottom - margin - progress_height
        progress_rect = pygame.Rect(scoreboard_rect.x + margin, progress_y_pos, progress_width, progress_height)
        
        # 背景 - 改进的设计
        pygame.draw.rect(surface, (25, 30, 40), progress_rect, border_radius=6)
        pygame.draw.rect(surface, (50, 55, 65), progress_rect, 1, border_radius=6)
        
        # 进度 - 确保不重叠，改进的样式
        if self.N > 0:
            white_progress = min(1.0, eff_w / self.N) if self.N > 0 else 0.0
            black_progress = min(1.0, eff_b / self.N) if self.N > 0 else 0.0
            
            # 白方进度（从左开始）- 改进的设计
            if white_progress > 0:
                white_prog_width = int(progress_width * white_progress)
                white_prog_rect = pygame.Rect(progress_rect.left, progress_rect.top, white_prog_width, progress_height)
                white_color = self.ui_colors.get("accent", (34, 197, 94))
                pygame.draw.rect(surface, white_color, white_prog_rect, border_radius=6)
                # Top highlight
                highlight = pygame.Rect(white_prog_rect.x, white_prog_rect.y, white_prog_rect.width, white_prog_rect.height // 3)
                highlight_color = tuple(min(255, c + 40) for c in white_color[:3])
                pygame.draw.rect(surface, highlight_color, highlight, border_radius=6)
                
            # 黑方进度（从右开始）- 改进的设计
            if black_progress > 0:
                black_prog_width = int(progress_width * black_progress)
                black_prog_rect = pygame.Rect(progress_rect.right - black_prog_width, progress_rect.top, black_prog_width, progress_height)
                black_color = self.ui_colors.get("primary", (79, 70, 229))
                pygame.draw.rect(surface, black_color, black_prog_rect, border_radius=6)
                # Top highlight
                highlight = pygame.Rect(black_prog_rect.x, black_prog_rect.y, black_prog_rect.width, black_prog_rect.height // 3)
                highlight_color = tuple(min(255, c + 40) for c in black_color[:3])
                pygame.draw.rect(surface, highlight_color, highlight, border_radius=6)
                
    def _render_game_over_message(self, surface: pygame.Surface, panel_rect: pygame.Rect, margin: int):
        """渲染游戏结束消息 - 在右侧面板中显示，不遮挡棋盘"""
        if not self.current_game_over:
            return
            
        # 在面板顶部显示游戏结束消息
        message_rect = pygame.Rect(
            panel_rect.x + margin,
            panel_rect.y + margin,
            panel_rect.width - margin * 2,
            80
        )
        
        # 创建卡片背景
        message_card = Card(message_rect, self.ui_theme, self.ui_colors)
        message_card.render(surface)
        
        if self.current_winner is None:
            msg = "Draw!"
            color = self.ui_colors.get("muted", (148, 163, 184))
        else:
            winner_name = "White" if self.current_winner == 'white' else "Black"
            msg = f"Game {self.game_index} finished: {winner_name} wins!"
            color = self.ui_colors.get("success", (34, 197, 94))
            
        msg_surf = self.font.render(msg, True, color)
        msg_rect = msg_surf.get_rect(center=message_rect.center)
        surface.blit(msg_surf, msg_rect)

    # ---------------- Interaction ----------------
    def _clear_selection(self) -> None:
        self.selected_sq = None
        self.legal_from_selected = []
        self.legal_moves_objects = []
        self.capture_to_squares = []
        # Invalidate move indicator cache khi clear selection
        self._move_indicator_cache = None

    def _select_square(self, sq: int) -> None:
        piece = self.engine.board.piece_at(sq)
        if piece is None:
            self._clear_selection()
            return
        moves = [m for m in self.engine.get_legal_moves() if m.from_square == sq]
        self.selected_sq = sq
        self.legal_moves_objects = moves
        # Invalidate move indicator cache khi selection thay đổi
        self._move_indicator_cache = None
        self.legal_from_selected = [m.to_square for m in moves]
        try:
            self.capture_to_squares = [m.to_square for m in moves if self.engine.board.is_capture(m)]
        except Exception:
            self.capture_to_squares = []

    def _start_piece_drag(self, sq: int, pos: Tuple[int, int], piece: chess.Piece) -> None:
        code = ("w_" if piece.color else "b_") + {
            chess.KING: "king",
            chess.QUEEN: "queen",
            chess.ROOK: "rook",
            chess.BISHOP: "bishop",
            chess.KNIGHT: "knight",
            chess.PAWN: "pawn",
        }[piece.piece_type]
        if getattr(self.config, "PIECE_SKIN", "").lower() == "dark fantasy":
            drag_size = max(12, int(self.square_size * 1.25))
        else:
            drag_size = max(12, self.square_size - 6)
        img = self.assets.get_piece_image(code, drag_size)
        self.dragging = True
        self.drag_from_sq = sq
        self.drag_surface = img
        
        # Pre-cache scaled surface để tránh scale mỗi frame (tối ưu hiệu năng)
        drag_scale = 1.1
        scaled_width = int(img.get_width() * drag_scale)
        scaled_height = int(img.get_height() * drag_scale)
        self._drag_scaled_cache = pygame.transform.smoothscale(img, (scaled_width, scaled_height))
        
        # Pre-cache shadow surface
        self._drag_shadow_cache = pygame.Surface((scaled_width, scaled_height), pygame.SRCALPHA)
        self._drag_shadow_cache.fill((0, 0, 0, 0))
        self._drag_shadow_cache.blit(self._drag_scaled_cache, (0, 0))
        self._drag_shadow_cache.set_alpha(80)
        
        # Tính toán tâm của ô vuông chứa quân cờ
        sx = self.board_origin[0] + chess.square_file(sq) * self.square_size + self.square_size // 2
        sy = self.board_origin[1] + (7 - chess.square_rank(sq)) * self.square_size + self.square_size // 2
        mx, my = pos
        # Offset để quân cờ luôn theo con trỏ chuột chính xác
        # Sử dụng negative offset để quân cờ di chuyển mượt mà hơn
        self.drag_offset = (sx - mx, sy - my)

    def _process_player_move(self, from_sq: int, to_sq: int) -> str:
        piece = self.engine.board.piece_at(from_sq)
        if piece is None:
            return "invalid"
        moves = self.legal_moves_objects if (self.legal_moves_objects and self.selected_sq == from_sq) else [
            m for m in self.engine.get_legal_moves() if m.from_square == from_sq
        ]
        for move in moves:
            if move.from_square == from_sq and move.to_square == to_sq:
                if move.promotion is not None or (piece.piece_type == chess.PAWN and chess.square_rank(to_sq) in (0, 7)):
                    self.promotion_pending = True
                    self.promo_from_to = (from_sq, to_sq)
                    self._clear_selection()
                    return "promotion"
                mover_name = self.white_name if self.engine.board.turn else self.black_name
                self._apply_move_and_record(move, player_name=mover_name)
                self.time_left[self.engine.board.turn] = float(self.config.MOVE_TIME_LIMIT)
                self._clear_selection()
                return "moved"
        return "invalid"

    def _handle_board_mouse_down(self, pos: Tuple[int, int]) -> None:
        ox, oy = self.board_origin
        x, y = pos
        if not (ox <= x < ox + 8 * self.square_size and oy <= y < oy + 8 * self.square_size):
            return
        file = (x - ox) // self.square_size
        rank_from_top = (y - oy) // self.square_size
        rank = 7 - rank_from_top
        sq = chess.square(file, rank)

        prev_selected = self.selected_sq
        if prev_selected is not None and prev_selected != sq and sq in self.legal_from_selected:
            result = self._process_player_move(prev_selected, sq)
            if result != "invalid":
                self._end_drag()
            return

        piece = self.engine.board.piece_at(sq)
        if piece is None:
            if self.selected_sq is not None and sq not in self.legal_from_selected:
                self._clear_selection()
            return

        is_player_piece = (
            (piece.color is True and self.engine.board.turn is True)
            or (piece.color is False and self.engine.board.turn is False)
        )

        if is_player_piece:
            self._select_square(sq)
            self._start_piece_drag(sq, pos, piece)
        else:
            if prev_selected == sq:
                return
            if self.selected_sq is not None and sq in self.legal_from_selected:
                result = self._process_player_move(self.selected_sq, sq)
                if result != "invalid":
                    self._end_drag()
                return
            # Xóa thông báo "It's not your turn"
            # self._show_center_message("It's not your turn")

    def _handle_board_mouse_up(self, pos: Tuple[int, int]) -> None:
        ox, oy = self.board_origin
        x, y = pos
        file = max(0, min(7, (x - ox) // self.square_size))
        rank_from_top = max(0, min(7, (y - oy) // self.square_size))
        rank = 7 - rank_from_top
        target_sq = chess.square(file, rank)

        original_from_sq = self.drag_from_sq
        result = "invalid"
        if original_from_sq is not None:
            result = self._process_player_move(original_from_sq, target_sq)
        self._end_drag()
        if result == "invalid" and original_from_sq is not None and not self.promotion_pending:
            self._select_square(original_from_sq)

    def _end_drag(self) -> None:
        self.dragging = False
        self.drag_from_sq = None
        self.drag_surface = None
        self.drag_offset = (0, 0)
        # Clear cached drag surfaces
        self._drag_scaled_cache = None
        self._drag_shadow_cache = None

    def _apply_move_and_record(self, move: chess.Move, player_name: str) -> None:
        piece = self.engine.board.piece_at(move.from_square)
        piece_name = "Unknown"
        if piece:
            piece_name = {
                chess.KING: "King",
                chess.QUEEN: "Queen",
                chess.ROOK: "Rook",
                chess.BISHOP: "Bishop",
                chess.KNIGHT: "Knight",
                chess.PAWN: "Pawn",
            }[piece.piece_type]
        
        # Check if a piece was captured BEFORE applying the move
        captured_piece = self.engine.board.piece_at(move.to_square)
        if captured_piece:
            piece_code = ("w_" if captured_piece.color else "b_") + {
                chess.KING: "king",
                chess.QUEEN: "queen",
                chess.ROOK: "rook",
                chess.BISHOP: "bishop",
                chess.KNIGHT: "knight",
                chess.PAWN: "pawn",
            }[captured_piece.piece_type]
            if captured_piece.color:  # White piece captured
                self.captured_white.append(piece_code)
            else:  # Black piece captured
                self.captured_black.append(piece_code)
        
        # Precompute coordinate strings for logging/records
        from_sq_str = chess.square_name(move.from_square).upper()
        to_sq_str = chess.square_name(move.to_square).upper()

        # Use SAN notation for clearer, correct move display (e.g., Nf3, exd5, O-O)
        try:
            san_notation = self.engine.board.san(move)
        except Exception:
            san_notation = f"{from_sq_str}-{to_sq_str}"

        # Tính move_time: thời gian thực tế để thực hiện move
        move_time = float(self.config.MOVE_TIME_LIMIT) - self.time_left[self.engine.board.turn]
        move_time = max(0.0, move_time)  # Đảm bảo không âm
        
        self.engine.push_move(move)
        self.last_move = move  # 保存最后一步用于高亮
        # 仅保存SAN；显示时组合为成对格式
        self.move_list.append(f"{san_notation}")
        # Invalidate caches sau khi move
        self._move_indicator_cache = None
        self._piece_map_cache = None
        
        # 显示Toast通知
        if self.engine.board.is_check():
            self._show_toast("Check!", "warning")
        if self.engine.is_game_over():
            result = self.engine.result()
            if result == "1-0":
                self._show_toast("White wins!", "success")
            elif result == "0-1":
                self._show_toast("Black wins!", "success")
            else:
                self._show_toast("Draw!", "info")
        # Write CSV line
        record = MoveRecord(
            set_id=self.set_id,
            game_index=self.game_index,
            move_index=len(self.move_list),
            player_name=player_name,
            piece=piece_name,
            from_sq=from_sq_str,
            to_sq=to_sq_str,
            fen_after=self.engine.fen(),
            timestamp=time.time(),
        )
        self.history.append_move(record)
        
        # Track move_time cho ranking (lưu vào instance variable)
        if not hasattr(self, 'move_times'):
            self.move_times = []
        self.move_times.append({
            'player_name': player_name,
            'move_time': move_time,
            'timestamp': time.time()
        })

        # 若在回放模式，退出回放并恢复最新局面
        if self._review_active:
            self._exit_review()

    def _get_move_pairs_for_display(self) -> List[str]:
        """返回 '1. Nf3 Nc6' 的行列表，基于当前棋局堆栈。"""
        pairs: List[str] = []
        try:
            board = chess.Board()
            moves = list(self.engine.board.move_stack)
            for i in range(0, len(moves), 2):
                white_move = moves[i]
                white_san = board.san(white_move)
                board.push(white_move)
                black_san = None
                if i + 1 < len(moves):
                    black_move = moves[i + 1]
                    black_san = board.san(black_move)
                    board.push(black_move)
                move_no = i // 2 + 1
                text = f"{move_no}. {white_san} {black_san or ''}".rstrip()
                pairs.append(text)
        except Exception:
            # Fallback to simple pairing of saved SAN strings
            for i in range(0, len(self.move_list), 2):
                move_no = i // 2 + 1
                w = self.move_list[i] if i < len(self.move_list) else ""
                b = self.move_list[i + 1] if i + 1 < len(self.move_list) else ""
                pairs.append(f"{move_no}. {w} {b}".rstrip())
        return pairs

    def _enter_review(self, pair_index: int) -> None:
        """进入历史回放：保存当前FEN并重放到所选回合末尾。再次点击最后一行可退出。"""
        self._review_pair_index = max(0, pair_index)
        self._pre_review_fen = self.engine.fen()
        self._review_active = True
        # 目标步数（回合索引从0开始，每回合2步）
        target_plies = min(len(self.engine.board.move_stack), (pair_index + 1) * 2)
        plies = list(self.engine.board.move_stack)
        self.engine.reset()
        for i, mv in enumerate(plies):
            if i >= target_plies:
                break
            self.engine.push_move(mv)
        self.last_move = self.engine.board.move_stack[-1] if self.engine.board.move_stack else None
        self.paused = True

    def _exit_review(self) -> None:
        if not self._review_active:
            return
        try:
            if self._pre_review_fen:
                self.engine.set_fen(self._pre_review_fen)
        except Exception:
            pass
        self._review_active = False
        self._pre_review_fen = None
        self.paused = False

    # ---------------- Modal & actions ----------------
    def _open_confirm(self, action: str) -> None:
        self.modal_active = True
        self.modal_action = action

    def _handle_modal_click(self, pos: Tuple[int, int]) -> None:
        """Xử lý click trên modal - sử dụng rect đã tính từ ảnh"""
        if self._modal_yes_rect.width > 0 and self._modal_yes_rect.collidepoint(pos):
            self._confirm_yes()
        elif self._modal_no_rect.width > 0 and self._modal_no_rect.collidepoint(pos):
            self.modal_active = False
            self.modal_action = None

    def _confirm_yes(self) -> None:
        action = self.modal_action
        self.modal_active = False
        self.modal_action = None
        if action == "undo":
            key = 'white' if self.engine.board.turn else 'black'
            # Disallow undo for AI side in PvAI
            if self.mode == 'PvAI':
                is_ai_side = (key == 'white' and not self.white_is_human) or (key == 'black' and not self.black_is_human)
                if is_ai_side:
                    print("[Undo] Not allowed for AI.")
                    return
            if self.undo_left[key] <= 0:
                print("[Undo] No uses left.")
                return
            # pop last ply if last move was by human, otherwise pop two to undo human's last
            if self.engine.board.move_stack:
                self._invalidate_ai_calculation()
                last_move_by_human = (len(self.engine.board.move_stack) % 2 == 1)  # human moves on even indices 0-based since human is white
                if last_move_by_human:
                    self.engine.pop_move()
                    if self.move_list:
                        self.move_list.pop()
                        # Remove last captured piece if any
                        if self.captured_white:
                            self.captured_white.pop()
                        elif self.captured_black:
                            self.captured_black.pop()
                else:
                    # pop AI then human
                    self.engine.pop_move()
                    if self.move_list:
                        self.move_list.pop()
                        # Remove captured piece
                        if self.captured_white:
                            self.captured_white.pop()
                        elif self.captured_black:
                            self.captured_black.pop()
                    if self.engine.board.move_stack:
                        self.engine.pop_move()
                        if self.move_list:
                            self.move_list.pop()
                            # Remove captured piece
                            if self.captured_white:
                                self.captured_white.pop()
                            elif self.captured_black:
                                self.captured_black.pop()
                self.undo_left[key] -= 1
                self.penalties_side[key]['undo'] += 1
                # Cập nhật button text ngay lập tức
                if "undo" in self.ui_buttons:
                    # Trong PvAI, luôn hiển thị số lượt của bên human
                    if self.mode == 'PvAI':
                        human_side = "white" if self.white_is_human else "black"
                        undo_count = self.undo_left.get(human_side, 0)
                    else:
                        undo_count = self.undo_left.get(key, 0)
                    self.ui_buttons["undo"].text = f"Undo (U) ({undo_count})"
                    # Cập nhật disabled state
                    current_side = "white" if self.engine.board.turn else "black"
                    if self.mode == 'PvAI':
                        is_ai_turn = (current_side == 'white' and not self.white_is_human) or (current_side == 'black' and not self.black_is_human)
                        self.ui_buttons["undo"].disabled = undo_count <= 0 or self.paused or is_ai_turn
                    else:
                        self.ui_buttons["undo"].disabled = undo_count <= 0 or self.paused
                # Do not allow negative effective wins; we apply at display by max(0,...)
                print("[Undo] Undone. 1 win penalty applied in this set.")
        elif action == "hint":
            key = 'white' if self.engine.board.turn else 'black'
            if self.mode == 'PvAI':
                is_ai_side = (key == 'white' and not self.white_is_human) or (key == 'black' and not self.black_is_human)
                if is_ai_side:
                    print("[Hint] Not allowed for AI.")
                    return
            if self.hint_left[key] <= 0:
                print("[Hint] No uses left.")
                return
            
            # Trừ số lần sử dụng ngay khi bấm hint
            self.hint_left[key] -= 1
            self.penalties_side[key]['hint'] += 1
            # Cập nhật button text ngay lập tức
            if "hint" in self.ui_buttons:
                hint_count = self.hint_left.get(key, 0)
                self.ui_buttons["hint"].text = f"Hint (H) ({hint_count})"
                self.ui_buttons["hint"].disabled = hint_count <= 0 or self.paused or self._hint_calculating
            
            # Tối ưu: Kiểm tra cache trước (dùng get() để tránh double lookup)
            current_fen = self.engine.fen()
            best_moves = self._hint_cache.get(current_fen)
            
            if best_moves is not None:
                # Có cache, apply hint moves ngay - không mất thời gian tính toán
                self.hint_moves = best_moves
                self.hint_timer = 3.0  # Hiển thị 3 giây
                self.hint_alpha = 0.0  # Bắt đầu fade in
                self.hint_pulse = 0.0  # Reset pulse
                self._show_toast(f"Hint: {self.hint_left[key]} left", "info")
                print(f"[Hint] Suggested {len(best_moves)} move(s) from cache. 1 win penalty applied in this set.")
                return
            else:
                # Không có cache, kiểm tra legal moves trước khi tạo thread
                legal_moves = self.engine.get_legal_moves()
                legal_moves_count = len(legal_moves)
                if legal_moves_count == 0:
                    # Không có legal moves, hoàn lại số lần sử dụng
                    self.hint_left[key] += 1
                    self.penalties_side[key]['hint'] -= 1
                    if "hint" in self.ui_buttons:
                        hint_count = self.hint_left.get(key, 0)
                        self.ui_buttons["hint"].text = f"Hint (H) ({hint_count})"
                        self.ui_buttons["hint"].disabled = hint_count <= 0 or self.paused or self._hint_calculating
                    print("[Hint] No legal moves available.")
                    self._show_toast("No legal moves available", "warning")
                    return
                
                # Tính toán hint trong background thread
                if not self._hint_calculating and (not self._hint_thread or not self._hint_thread.is_alive()):
                    self._start_hint_calculation()
                    # Hiển thị loading message
                    self._show_toast("Calculating hint...", "info")
                    return  # Sẽ apply hint trong update() khi có kết quả
                else:
                    # Đang tính toán, chờ kết quả
                    if not self._hint_calculating:
                        # Thread đã chết nhưng chưa có kết quả, thử lại
                        self._start_hint_calculation()
                        self._show_toast("Calculating hint...", "info")
                    return
        elif action == "resign":
            # Current side resigns -> opponent wins
            winner = 'black' if self.engine.board.turn else 'white'
            self._finish_game(winner=winner, reason="Resign")
        elif action == "new":
            print("[New Game] Start a fresh match.")
            self._reset_full_match()

    def _render_modal(self, surface: pygame.Surface) -> None:
        """Render modal confirmation với ảnh thay vì text"""
        if not self.modal_action:
            return
        
        # Vẽ overlay tối
        screen_w, screen_h = surface.get_size()
        overlay = pygame.Surface((screen_w, screen_h), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        surface.blit(overlay, (0, 0))
        
        # Lấy ảnh modal tương ứng
        modal_img = self._modal_images.get(self.modal_action)
        if not modal_img:
            # Fallback: dùng Panel nếu không có ảnh
            rect = self._modal_rect()
            modal_panel = Panel(rect, self.ui_theme, self.ui_colors)
            modal_panel.render(surface)
            title = {"undo": "Confirm UNDO", "hint": "Confirm HINT", "resign": "Confirm Resign", "new": "Confirm New Game"}.get(self.modal_action or "", "Confirm")
            surface.blit(self.big_font.render(title, True, self.ui_colors.get("text", (226, 232, 240))), (rect.x + 12, rect.y + 12))
            yes_rect = pygame.Rect(rect.x + 16, rect.bottom - 50, 90, 34)
            no_rect = pygame.Rect(rect.x + 116, rect.bottom - 50, 90, 34)
            self._modal_yes_rect = yes_rect
            self._modal_no_rect = no_rect
            return
        
        # Scale ảnh để phù hợp với màn hình
        img_w, img_h = modal_img.get_size()
        max_width = int(screen_w * 0.6)  # Tối đa 60% chiều rộng
        max_height = int(screen_h * 0.7)  # Tối đa 70% chiều cao
        scale_w = max_width / img_w
        scale_h = max_height / img_h
        scale = min(scale_w, scale_h)
        
        draw_w = int(img_w * scale)
        draw_h = int(img_h * scale)
        
        # Scale ảnh
        if draw_w > 0 and draw_h > 0:
            scaled_img = pygame.transform.smoothscale(modal_img, (draw_w, draw_h))
        else:
            scaled_img = modal_img
            draw_w, draw_h = scaled_img.get_size()
        
        # Vị trí dialog ở giữa màn hình
        dialog_x = (screen_w - draw_w) // 2
        dialog_y = (screen_h - draw_h) // 2
        
        # Vẽ ảnh dialog
        surface.blit(scaled_img, (dialog_x, dialog_y))
        
        # Tính toán vị trí Yes/No buttons dựa trên phần trăm của ảnh (giống nhau cho tất cả modal)
        # Yes button (bên trái)
        yes_left_pct = 0.22  # 22% từ trái
        yes_top_pct = 0.65   # 65% từ trên
        yes_width_pct = 0.236  # 23.6% chiều rộng dialog
        yes_height_pct = 0.09  # 9% chiều cao dialog
        
        self._modal_yes_rect = pygame.Rect(
            dialog_x + int(draw_w * yes_left_pct),
            dialog_y + int(draw_h * yes_top_pct),
            int(draw_w * yes_width_pct),
            int(draw_h * yes_height_pct)
        )
        
        # No button (bên phải)
        no_left_pct = 0.55  # 55% từ trái
        no_top_pct = 0.65   # 65% từ trên
        no_width_pct = 0.236  # 23.6% chiều rộng dialog
        no_height_pct = 0.09  # 9% chiều cao dialog
        
        self._modal_no_rect = pygame.Rect(
            dialog_x + int(draw_w * no_left_pct),
            dialog_y + int(draw_h * no_top_pct),
            int(draw_w * no_width_pct),
            int(draw_h * no_height_pct)
        )

    # Promotion popup
    def _render_promotion(self, surface: pygame.Surface) -> None:
        rect = self._modal_rect()
        # 使用新UI Panel
        promo_panel = Panel(rect, self.ui_theme, self.ui_colors)
        promo_panel.render(surface)
        surface.blit(self.big_font.render("Choose promotion piece", True, self.ui_colors.get("text", (226, 232, 240))), (rect.x + 12, rect.y + 12))

        # Option buttons - 使用新UI按钮
        opts = [("Queen", chess.QUEEN), ("Rook", chess.ROOK), ("Bishop", chess.BISHOP), ("Knight", chess.KNIGHT)]
        for i, (label, _) in enumerate(opts):
            b = pygame.Rect(rect.x + 16 + i * 84, rect.y + 70, 80, 40)
            promo_button = Button(b, label, self.ui_theme, self.ui_colors, self.small_font, key=f"promo_{label}")
            promo_button.render(surface)

        # Handle click
        if pygame.mouse.get_pressed()[0]:
            mx, my = pygame.mouse.get_pos()
            for i, (label, promo) in enumerate(opts):
                b = pygame.Rect(rect.x + 16 + i * 84, rect.y + 70, 80, 40)
                if b.collidepoint((mx, my)):
                    self._confirm_promotion(promo)
                    break

    def _confirm_promotion(self, promo_piece: int) -> None:
        if not self.promotion_pending or self.promo_from_to is None:
            return
        from_sq, to_sq = self.promo_from_to
        move = chess.Move(from_sq, to_sq, promotion=promo_piece)
        if move in self.engine.board.legal_moves:
            self._apply_move_and_record(move, player_name=self.player_human.name or "Human")
            self.time_left[self.engine.board.turn] = float(self.config.MOVE_TIME_LIMIT)
        self.promotion_pending = False
        self.promo_from_to = None

    def _modal_rect(self) -> pygame.Rect:
        w, h = 360, 140
        cx = self.config.margin_px + self.config.board_size_px // 2
        cy = self.config.margin_px + self.config.board_size_px // 2
        return pygame.Rect(cx - w // 2, cy - h // 2, w, h)

    # ---------------- Game finish & set control ----------------
    def _finish_game(self, winner: Optional[str], reason: str) -> None:
        self._invalidate_ai_calculation()
        self.current_game_over = True
        self.current_winner = winner
        self.game_end_shown = False  # Reset flag khi game mới kết thúc
        if winner == "white":
            self.white_wins += 1
        elif winner == "black":
            self.black_wins += 1

        print(f"[Game] Game {self.game_index} finished - {reason}. Winner: {winner}")

        # Prepare next game or continue set
        self.game_index += 1
        # Lưu ý: Không reset current_game_over và current_winner ngay
        # Chúng sẽ được reset khi người chơi chọn Replay hoặc tiếp tục từ GameEndScene

    def _current_side_is_human(self) -> bool:
        return self.white_is_human if self.engine.board.turn else self.black_is_human



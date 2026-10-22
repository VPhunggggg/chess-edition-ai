"""
README (Run the application)
============================

- Requires Python 3.11.
- Install dependencies:
    pip install pygame python-chess
- Run:
    python main.py

The app runs offline and supports Windows/macOS/Linux. Missing images fall back to a placeholder.
"""

from __future__ import annotations

import os
import sys
import pygame
from typing import Optional


# Ensure working directory is project root
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)


from core.config import AppConfig
from scenes.setup_scene import SetupScene
from scenes.menu_scene import MenuScene
from core.telemetry import Telemetry
from core.settings import load_settings, save_settings, AppSettings
from core.ui_theme import apply_theme
from scenes.match_scene import MatchScene
from scenes.results_scene import ResultsScene


class Scene:
    """Base class for scenes."""

    def handle_event(self, event: pygame.event.Event) -> Optional["Scene"]:
        return None

    def update(self, dt: float) -> Optional["Scene"]:
        return None

    def render(self, surface: pygame.Surface) -> None:
        pass


class App:
    def __init__(self) -> None:
        pygame.init()
        pygame.display.set_caption("Chess Edition")
        self.config = AppConfig()
        # Load and set window icon
        self._load_window_icon()
        # Load persisted settings and apply
        settings = load_settings()
        self.config.window_width = settings.window_width
        self.config.window_height = settings.window_height
        self.config.board_size_px = settings.board_size_px
        self.config.BOARD_THEME = settings.theme
        self.config.PIECE_SKIN = settings.piece_skin
        # Map piece skin to folder under assets/pieces
        try:
            skin_folder = getattr(settings, "piece_skin", "classic")
            pieces_root = os.path.join(self.config.assets_dir, "pieces")
            candidate = os.path.join(pieces_root, skin_folder)
            if os.path.exists(candidate):
                self.config.pieces_dir = candidate
            else:
                self.config.pieces_dir = pieces_root
        except Exception:
            pass
        # Restore last logged-in user
        try:
            if getattr(settings, "current_user", ""):
                self.config.current_user = {"name": settings.current_user}
        except Exception:
            pass
        apply_theme(self.config, settings.theme)
        self.clock = pygame.time.Clock()
        self.screen = pygame.display.set_mode((self.config.window_width, self.config.window_height), pygame.RESIZABLE)
        self.is_fullscreen = False
        self.telemetry = Telemetry(pygame.font.SysFont(self.config.font_name, 14))
        self.running = True

        # Scenes
        self.current_scene: Scene = MenuScene(self.config)
        self.music_enabled = False
        self._init_background_music()

    def _render_frame(self) -> None:
        """Helper function to render a frame with telemetry"""
        self.telemetry.begin_frame()
        ret = self.current_scene.render(self.screen)
        overlay_rect = self.telemetry.end_frame(self.screen, len(ret) if isinstance(ret, list) else 1)
        if isinstance(ret, list) and len(ret) > 0:
            if overlay_rect is not None:
                ret.append(overlay_rect)
            pygame.display.update(ret)
        else:
            pygame.display.flip()

    def _load_window_icon(self) -> None:
        """Load và set icon cho cửa sổ game từ file icongame.ico"""
        try:
            # Thử load từ decorate_dir trong config
            icon_path = os.path.join(self.config.decorate_dir, "icongame.ico")
            if not os.path.exists(icon_path):
                # Fallback: thử với đường dẫn tương đối
                icon_path = os.path.join(".", "assets", "Decorate", "icongame.ico")
            
            if os.path.exists(icon_path):
                # Thử load trực tiếp với pygame (có thể không hỗ trợ .ico trên một số hệ thống)
                try:
                    icon_surface = pygame.image.load(icon_path)
                    pygame.display.set_icon(icon_surface)
                    return
                except Exception:
                    pass
                
                # Nếu pygame không hỗ trợ .ico, thử dùng PIL
                try:
                    from PIL import Image
                    img = Image.open(icon_path)
                    # Convert sang RGBA nếu cần
                    if img.mode != 'RGBA':
                        img = img.convert('RGBA')
                    
                    # Lấy kích thước và dữ liệu
                    size = img.size
                    data = img.tobytes()
                    
                    # Tạo pygame Surface từ dữ liệu
                    # Sử dụng frombuffer thay vì fromstring (deprecated)
                    try:
                        icon_surface = pygame.image.frombuffer(data, size, 'RGBA')
                    except AttributeError:
                        # Fallback cho pygame cũ
                        icon_surface = pygame.image.fromstring(data, size, 'RGBA')
                    
                    pygame.display.set_icon(icon_surface)
                except ImportError:
                    # Nếu không có PIL, bỏ qua
                    pass
                except Exception:
                    # Bỏ qua nếu có lỗi
                    pass
        except Exception:
            # Bỏ qua nếu có lỗi khi load icon
            pass
    
    def _find_music_file(self, filename: str) -> Optional[str]:
        """Tìm file nhạc trong thư mục Music hoặc Decorate"""
        music_dir = os.path.join(self.config.assets_dir, "Music")
        decorate_dir = self.config.decorate_dir
        
        # Thử tìm trong Music directory trước
        if os.path.exists(music_dir):
            music_path = os.path.join(music_dir, filename)
            if os.path.exists(music_path):
                return music_path
        
        # Thử tìm trong Decorate directory
        if os.path.exists(decorate_dir):
            music_path = os.path.join(decorate_dir, filename)
            if os.path.exists(music_path):
                return music_path
        
        return None
    
    def _init_background_music(self) -> None:
        # Load music setting from saved settings
        settings = load_settings()
        menu_music = getattr(settings, 'menu_music', 'ost.mp3')
        music_path = self._find_music_file(menu_music)
        if not music_path:
            return
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            pygame.mixer.music.load(music_path)
            pygame.mixer.music.set_volume(0.4)
            pygame.mixer.music.play(-1)
            self.music_enabled = True
        except Exception:
            self.music_enabled = False

    def change_scene(self, scene: Scene) -> None:
        self.current_scene = scene

    def run(self) -> None:
        while self.running:
            dt = self.clock.tick(self.config.target_fps) / 1000.0
            skip_render = False  # Flag to skip render if already rendered immediately
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.TEXTINPUT:
                    # Handle TEXTINPUT first for immediate text display
                    next_scene = self.current_scene.handle_event(event)
                    if next_scene is not None:
                        self.current_scene = next_scene
                    # Force immediate render for real-time text display
                    self.screen.fill(self.config.colors["bg"])
                    self._render_frame()
                    skip_render = True
                elif event.type == pygame.KEYDOWN:
                    # Xử lý các phím tắt toàn cục trước
                    handled = False
                    
                    # Toggle fullscreen: F11 or Alt+Enter
                    if event.key == pygame.K_F11 or (event.key == pygame.K_RETURN and (pygame.key.get_mods() & pygame.KMOD_ALT)):
                        self.is_fullscreen = not self.is_fullscreen
                        self.config.fullscreen = self.is_fullscreen
                        if self.is_fullscreen:
                            self.screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
                        else:
                            self.screen = pygame.display.set_mode((self.config.window_width, self.config.window_height), pygame.RESIZABLE)
                        handled = True
                    # Zoom board: Ctrl + +/-
                    elif (pygame.key.get_mods() & pygame.KMOD_CTRL) and event.key in (pygame.K_PLUS, pygame.K_EQUALS):
                        self.config.board_size_px = min(1024, self.config.board_size_px + 40)
                        self.config.recompute_window_size()
                        handled = True
                    elif (pygame.key.get_mods() & pygame.KMOD_CTRL) and event.key in (pygame.K_MINUS,):
                        self.config.board_size_px = max(480, self.config.board_size_px - 40)
                        self.config.recompute_window_size()
                        handled = True
                    elif event.key == pygame.K_F9:
                        self.telemetry.toggle_overlay()
                        handled = True
                    elif event.key == pygame.K_F10:
                        self.telemetry.toggle_logging()
                        handled = True
                    elif (pygame.key.get_mods() & pygame.KMOD_CTRL) and event.key == pygame.K_t:
                        # Toggle theme
                        new_theme = "high_contrast" if getattr(self.config, 'BOARD_THEME', 'classic') == 'classic' else 'classic'
                        apply_theme(self.config, new_theme)
                        self.config.BOARD_THEME = new_theme
                        handled = True
                    
                    # Nếu không phải phím tắt toàn cục, chuyển đến scene để xử lý
                    if not handled:
                        next_scene = self.current_scene.handle_event(event)
                        if next_scene is not None:
                            self.current_scene = next_scene
                        # Force immediate update for BACKSPACE to show text changes instantly
                        if event.key == pygame.K_BACKSPACE:
                            self.screen.fill(self.config.colors["bg"])
                            self._render_frame()
                            skip_render = True
                elif event.type == pygame.VIDEORESIZE and not self.is_fullscreen:
                    # Update config with new window size - enforce minimum
                    min_width = 1024
                    min_height = 768
                    display_info = pygame.display.Info()
                    screen_w = getattr(display_info, 'current_w', event.w)
                    screen_h = getattr(display_info, 'current_h', event.h)
                    new_width = max(min_width, min(event.w, screen_w))
                    new_height = max(min_height, min(event.h, screen_h))
                    self.config.window_width = new_width
                    self.config.window_height = new_height
                    # Resize window to enforce minimum
                    if (
                        event.w < min_width or event.h < min_height
                        or event.w > screen_w or event.h > screen_h
                    ):
                        self.screen = pygame.display.set_mode((new_width, new_height), pygame.RESIZABLE)
                else:
                    next_scene = self.current_scene.handle_event(event)
                    if next_scene is not None:
                        self.current_scene = next_scene

            # Sync window size with config (e.g., after setup size change)
            if not self.is_fullscreen:
                current_size = self.screen.get_size()
                # Clamp desired size to physical screen to avoid bottom overflow/black bars
                info = pygame.display.Info()
                max_w = getattr(info, 'current_w', self.config.window_width)
                max_h = getattr(info, 'current_h', self.config.window_height)
                desired = (
                    min(self.config.window_width, max_w),
                    min(self.config.window_height, max_h),
                )
                if current_size != desired:
                    self.screen = pygame.display.set_mode(desired, pygame.RESIZABLE)

            next_scene = self.current_scene.update(dt)
            if next_scene is not None:
                self.current_scene = next_scene

            # Only render if not already rendered immediately (for TEXTINPUT/BACKSPACE)
            if not skip_render:
                # Mỗi scene đã tự vẽ background đầy đủ
                self._render_frame()

        # Save settings on exit
        try:
            # Load current settings để giữ lại các giá trị cũ
            current_settings = load_settings()
            save_settings(AppSettings(
                window_width=self.config.window_width,
                window_height=self.config.window_height,
                fullscreen=self.is_fullscreen,
                board_size_px=self.config.board_size_px,
                theme=getattr(self.config, 'BOARD_THEME', 'classic'),
                piece_skin=getattr(self.config, 'PIECE_SKIN', 'classic'),
                ai_difficulty=getattr(self.config, 'ai_difficulty', 'medium'),
                move_time_limit=self.config.MOVE_TIME_LIMIT,
                max_undo=self.config.MAX_UNDO_PER_PLAYER,
                max_hint=self.config.MAX_HINT_PER_PLAYER,
                current_user=(self.config.current_user.get("name") if isinstance(self.config.current_user, dict) else (self.config.current_user or "")) if getattr(self.config, "current_user", None) else "",
                menu_music=getattr(self.config, 'menu_music', getattr(current_settings, 'menu_music', 'ost.mp3')),
                match_music=getattr(self.config, 'match_music', getattr(current_settings, 'match_music', 'nhac.mp3')),
            ))
        except Exception:
            pass
        try:
            if pygame.mixer.get_init():
                pygame.mixer.music.stop()
                pygame.mixer.quit()
        except Exception:
            pass
        pygame.quit()


if __name__ == "__main__":
    App().run()

from __future__ import annotations

import os
import sys
import pygame
from typing import Optional, Tuple, TYPE_CHECKING

# Ensure working directory is project root
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

if TYPE_CHECKING:
    from main import Scene

from core.config import AppConfig
from core.assets import AssetManager
from scenes.menu_scene import MenuScene


class GameEndScene:
    """Scene hiển thị màn hình thắng/thua với ảnh và các vùng click vô hình."""
    
    def __init__(
        self,
        config: AppConfig,
        assets: AssetManager,
        is_win: bool,
        match_scene_factory,  # Hàm để tạo lại MatchScene
    ) -> None:
        self.config = config
        self.assets = assets
        self.is_win = is_win
        self.match_scene_factory = match_scene_factory
        
        # Load ảnh gốc (không scale)
        self._load_original_image()
        
        # Vị trí buttons dựa trên tỷ lệ phần trăm (đã điều chỉnh cho khớp với ảnh)
        # REPLAY: left: 9%, top: 45%, width: 31%, height: 11%
        # EXIT: left: 9%, top: 62%, width: 31%, height: 11%
        self.replay_percent = (0.09, 0.45, 0.31, 0.11)  # (left, top, width, height)
        self.exit_percent = (0.09, 0.62, 0.31, 0.11)    # (left, top, width, height)
        
        # Font cho text khi hover
        self.font = self.assets.get_font(28)
        
        # Trạng thái hover
        self.hover_replay = False
        self.hover_exit = False
        
        # Cache để tối ưu hiệu suất
        self._cached_screen_size = None
        self._cached_background = None
        
        # Cập nhật kích thước và vị trí buttons
        self._update_layout()
    
    def _load_original_image(self) -> None:
        """Load ảnh gốc từ thư mục Decorate."""
        import os
        
        filename = "win.png" if self.is_win else "loss.png"
        decorate_dir = os.path.join(".", "assets", "Decorate")
        path = os.path.join(decorate_dir, filename)
        
        if not os.path.exists(path):
            # Fallback: tạo nền mặc định
            self.original_image = None
            self.original_size = (1920, 1080)  # Giả định kích thước mặc định
            return
        
        try:
            self.original_image = pygame.image.load(path).convert_alpha()
            self.original_size = self.original_image.get_size()
        except Exception:
            self.original_image = None
            self.original_size = (1920, 1080)
    
    def _scale_image_to_fit(self, target_size: Tuple[int, int]) -> pygame.Surface:
        """Scale ảnh để fit màn hình nhưng giữ aspect ratio (cover mode - responsive).
        Sử dụng cache để tối ưu hiệu suất."""
        # Kiểm tra cache - chỉ scale lại nếu kích thước thay đổi
        if (self._cached_screen_size == target_size and 
            self._cached_background is not None):
            return self._cached_background
        
        if self.original_image is None:
            # Tạo nền mặc định
            surf = pygame.Surface(target_size)
            surf.fill((20, 20, 20))
            self._cached_screen_size = target_size
            self._cached_background = surf
            return surf
        
        target_w, target_h = target_size
        orig_w, orig_h = self.original_size
        
        # Tính scale để cover toàn màn hình (giữ aspect ratio)
        scale_w = target_w / orig_w
        scale_h = target_h / orig_h
        scale = max(scale_w, scale_h)  # Cover mode - đảm bảo không có khoảng trống
        
        new_w = int(orig_w * scale)
        new_h = int(orig_h * scale)
        
        # Scale ảnh với smoothscale để chất lượng tốt hơn
        scaled = pygame.transform.smoothscale(self.original_image, (new_w, new_h))
        
        # Crop từ center nếu ảnh lớn hơn màn hình (giữ tỷ lệ)
        if new_w > target_w or new_h > target_h:
            x = (new_w - target_w) // 2
            y = (new_h - target_h) // 2
            scaled = scaled.subsurface((x, y, target_w, target_h))
        
        # Lưu vào cache
        self._cached_screen_size = target_size
        self._cached_background = scaled
        
        return scaled
    
    def _update_layout(self, screen_size: Optional[Tuple[int, int]] = None) -> None:
        """Cập nhật kích thước ảnh và vị trí các button areas.
        Chỉ cập nhật khi kích thước cửa sổ thay đổi để tối ưu hiệu suất."""
        if screen_size is None:
            screen_size = (self.config.window_width, self.config.window_height)
        
        # Clear cache nếu kích thước thay đổi
        if self._cached_screen_size != screen_size:
            self._cached_screen_size = None
            self._cached_background = None
        
        # Scale ảnh để fit màn hình (cache sẽ xử lý việc tái sử dụng)
        self.background_image = self._scale_image_to_fit(screen_size)
        self.image_size = self.background_image.get_size()
        self.image_pos = (0, 0)  # Ảnh luôn bắt đầu từ (0, 0)
        
        # Tính toán vị trí buttons dựa trên tỷ lệ phần trăm của ảnh
        img_w, img_h = self.image_size
        
        # REPLAY button area
        replay_left_pct, replay_top_pct, replay_width_pct, replay_height_pct = self.replay_percent
        replay_x = int(img_w * replay_left_pct)
        replay_y = int(img_h * replay_top_pct)
        replay_w = int(img_w * replay_width_pct)
        replay_h = int(img_h * replay_height_pct)
        self.btn_replay = pygame.Rect(replay_x, replay_y, replay_w, replay_h)
        
        # EXIT button area
        exit_left_pct, exit_top_pct, exit_width_pct, exit_height_pct = self.exit_percent
        exit_x = int(img_w * exit_left_pct)
        exit_y = int(img_h * exit_top_pct)
        exit_w = int(img_w * exit_width_pct)
        exit_h = int(img_h * exit_height_pct)
        self.btn_exit = pygame.Rect(exit_x, exit_y, exit_w, exit_h)
    
    def handle_event(self, event: pygame.event.Event) -> Optional["Scene"]:
        """Xử lý sự kiện."""
        # Xử lý sự kiện resize cửa sổ - lấy kích thước thực tế từ event
        if event.type == pygame.VIDEORESIZE:
            # Lấy kích thước thực tế từ event
            actual_size = (event.w, event.h)
            self._update_layout(actual_size)
            self.last_window_size = actual_size
        
        # Cập nhật layout nếu kích thước cửa sổ thay đổi (responsive)
        current_size = (self.config.window_width, self.config.window_height)
        if not hasattr(self, 'last_window_size'):
            self.last_window_size = current_size
        elif self.last_window_size != current_size:
            self._update_layout(current_size)
            self.last_window_size = current_size
        
        if event.type == pygame.MOUSEMOTION:
            # Kiểm tra hover (tọa độ chuột so với ảnh)
            mouse_pos = event.pos
            self.hover_replay = self.btn_replay.collidepoint(mouse_pos)
            self.hover_exit = self.btn_exit.collidepoint(mouse_pos)
        
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:  # Left click
                mouse_pos = event.pos
                if self.btn_replay.collidepoint(mouse_pos):
                    # Tạo lại MatchScene để chơi lại (từ factory function)
                    return self.match_scene_factory()
                elif self.btn_exit.collidepoint(mouse_pos):
                    # Quay lại menu
                    return MenuScene(self.config)
        
        elif event.type == pygame.KEYDOWN:
            # Phím tắt cho REPLAY: R hoặc Enter
            if event.key in (pygame.K_r, pygame.K_RETURN, pygame.K_KP_ENTER):
                return self.match_scene_factory()
            # Phím tắt cho EXIT: E hoặc Escape
            elif event.key in (pygame.K_e, pygame.K_ESCAPE):
                return MenuScene(self.config)
        
        return None
    
    def update(self, dt: float) -> Optional["Scene"]:
        """Cập nhật scene - kiểm tra thay đổi kích thước cửa sổ để responsive."""
        # Kiểm tra thay đổi kích thước cửa sổ (responsive)
        current_size = (self.config.window_width, self.config.window_height)
        if not hasattr(self, 'last_window_size'):
            self.last_window_size = current_size
        elif self.last_window_size != current_size:
            self._update_layout(current_size)
            self.last_window_size = current_size
        return None
    
    def _draw_glow_effect(self, surface: pygame.Surface, rect: pygame.Rect, color: Tuple[int, int, int], intensity: int = 30) -> None:
        """Vẽ glow effect mềm mại xung quanh vùng button (không có border)."""
        # Tạo nhiều lớp glow để tạo hiệu ứng mềm mại
        glow_layers = [
            (intensity * 2, 10),  # Lớp ngoài cùng, mờ nhất
            (intensity, 20),      # Lớp giữa
            (intensity // 2, 30), # Lớp trong, sáng hơn
        ]
        
        for glow_size, alpha in glow_layers:
            if glow_size <= 0:
                continue
            glow_surf = pygame.Surface((rect.width + glow_size * 2, rect.height + glow_size * 2), pygame.SRCALPHA)
            # Vẽ rounded rectangle mờ để tạo glow
            glow_rect = pygame.Rect(glow_size, glow_size, rect.width, rect.height)
            try:
                # Vẽ với alpha
                glow_color = (*color, alpha)
                pygame.draw.rect(glow_surf, glow_color, glow_rect, border_radius=8)
            except (TypeError, ValueError):
                # Fallback: vẽ không có alpha (sẽ mờ hơn)
                pygame.draw.rect(glow_surf, color, glow_rect, border_radius=8)
            # Blit với blend mode
            try:
                surface.blit(glow_surf, (rect.x - glow_size, rect.y - glow_size), special_flags=pygame.BLEND_ALPHA_SDL2)
            except (AttributeError, TypeError):
                # Fallback cho pygame cũ
                surface.blit(glow_surf, (rect.x - glow_size, rect.y - glow_size))
    
    def render(self, surface: pygame.Surface) -> None:
        """Vẽ scene - chỉ vẽ ảnh nền, không hiển thị gì khi hover."""
        # Lấy kích thước thực tế từ surface để đảm bảo scale đúng
        actual_screen_size = surface.get_size()
        
        # Kiểm tra và cập nhật layout nếu kích thước thực tế khác với cache
        if (self._cached_screen_size != actual_screen_size or 
            self.background_image.get_size() != actual_screen_size):
            self._update_layout(actual_screen_size)
        
        # Vẽ ảnh nền - đảm bảo ảnh luôn fit đúng kích thước surface
        surface.blit(self.background_image, self.image_pos)
        
        # Không vẽ gì khi hover - hoàn toàn ẩn, chỉ giữ chức năng click


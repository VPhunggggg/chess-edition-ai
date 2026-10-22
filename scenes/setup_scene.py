from __future__ import annotations

import os
import sys
import uuid
import pygame
from dataclasses import dataclass
from typing import Optional, Tuple

# Ensure working directory is project root
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from core.config import AppConfig
from core.assets import AssetManager
from chess_app.ui.setup_layout import SetupLayoutSystem
from chess_app.ui.theme import get_theme


@dataclass
class PlayerProfile:
    name: str
    gender: str  # "Male" | "Female" | "Other"
    role: str    # "Human" | "AI"
    avatar_path: Optional[str]


class SetupScene:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.config.ensure_dirs()
        self.assets = AssetManager(
            avatars_dir=self.config.avatars_dir,
            pieces_dir=self.config.pieces_dir,
            avatar_size=self.config.avatar_size_px,
            font_name=self.config.font_name,
        )
        # 初始化响应式布局系统
        self.layout = SetupLayoutSystem(
            self.config.window_width,
            self.config.window_height,
            get_theme("default_dark")
        )
        
        # 响应式字体
        self._update_fonts()

        # Defaults
        default_name = getattr(self.config, 'current_user', "")
        # Normalize to string: accept dict {"name": "..."} or direct string
        try:
            if isinstance(default_name, dict):
                default_name = str(default_name.get("name", "") or "")
            else:
                default_name = str(default_name or "")
        except Exception:
            default_name = ""
        self.human = PlayerProfile(name=default_name, gender="Male", role="Human", avatar_path=None)
        self.ai = PlayerProfile(name="Machine/AI", gender="Other", role="AI", avatar_path=os.path.join(self.config.avatars_dir, "ai_bot.png"))
        self.best_of_n = 3
        self.validation_message = ""

        # Text input state
        self.input_active = False
        self.input_rect = pygame.Rect(0, 0, 0, 0)  # 将在render中计算

        # Simple buttons - 将在render中计算
        self.btn_start = pygame.Rect(0, 0, 0, 0)  # Vùng clickable nhỏ hơn
        self.btn_start_full_area = pygame.Rect(0, 0, 0, 0)  # Vùng lớn hơn để check click ở ngoài
        self.btn_bon_rects = []  # 将在render中计算

        # Avatar preview rects - 将在render中计算
        self.avatar_preview_rects = (pygame.Rect(0, 0, 0, 0), pygame.Rect(0, 0, 0, 0))

        # Music scroll area rects - 将在render中计算
        self.menu_music_scroll_area_rect = pygame.Rect(0, 0, 0, 0)
        self.match_music_scroll_area_rect = pygame.Rect(0, 0, 0, 0)

        # Sliders - 将在render中计算
        self.slider_tracks = {}
        self.slider_dragging: Optional[str] = None
        
        # Counter cho số lần đã thay đổi setting
        self.setting_change_count = 0
        
        # Cache cho button surfaces để tối ưu performance
        self._button_shadow_cache = {}  # Cache cho shadow surfaces
        self._button_gradient_cache = {}  # Cache cho gradient surfaces
        self._text_cache = {}  # Cache cho text surfaces
        self._last_window_size = (self.config.window_width, self.config.window_height)  # Track window size changes

        # Gender radio
        self.gender_opts = ["Male", "Female", "Other"]
        self.gender_idx = 0

        # Match mode and options (must exist before first event)
        self.mode_opts = ["PvP", "PvAI"]; self.mode_idx = 1
        # Đảm bảo role đúng khi khởi tạo (mặc định là PvAI nên ai.role = "AI" là đúng)
        self.side_opts = ["White", "Black", "Random"]; self.side_idx = 0
        self.swap_sides = False
        self.ai_diff_opts = ["easy", "medium", "hard"]; self.ai_diff_idx = 1
        # Available piece skins map to folders under assets/pieces/
        # - "classic" -> assets/pieces/classic
        # - "dark fantasy" -> assets/pieces/dark fantasy
        self.piece_skin_opts = ["classic", "dark fantasy"]
        # 从配置中加载棋子皮肤设置
        current_skin = getattr(self.config, 'PIECE_SKIN', 'classic')
        self.piece_skin_idx = self.piece_skin_opts.index(current_skin) if current_skin in self.piece_skin_opts else 0

        # Music selection - Load from settings and scan music files
        from core.settings import load_settings
        settings = load_settings()
        
        # Scan music files from Music and Decorate directories
        music_files = []
        music_dir = os.path.join(self.config.assets_dir, "Music")
        decorate_dir = self.config.decorate_dir
        
        # Load from Music directory
        if os.path.exists(music_dir):
            for f in os.listdir(music_dir):
                if f.lower().endswith((".mp3", ".ogg", ".wav")):
                    music_files.append(os.path.join("Music", f))
        
        # Load from Decorate directory
        if os.path.exists(decorate_dir):
            for f in os.listdir(decorate_dir):
                if f.lower().endswith((".mp3", ".ogg", ".wav")):
                    music_files.append(os.path.join("Decorate", f))
        
        # Sort và loại bỏ trùng lặp (chỉ lấy tên file)
        music_file_names = []
        seen = set()
        for path in sorted(music_files):
            filename = os.path.basename(path)
            if filename not in seen:
                music_file_names.append(filename)
                seen.add(filename)
        
        # Nếu không có file nhạc, dùng mặc định
        if not music_file_names:
            music_file_names = ["ost.mp3", "nhac.mp3"]
        
        self.menu_music_opts = music_file_names
        self.match_music_opts = music_file_names.copy()
        
        menu_music = getattr(settings, 'menu_music', music_file_names[0] if music_file_names else 'ost.mp3')
        match_music = getattr(settings, 'match_music', music_file_names[0] if music_file_names else 'nhac.mp3')
        self.menu_music_idx = self.menu_music_opts.index(menu_music) if menu_music in self.menu_music_opts else 0
        self.match_music_idx = self.match_music_opts.index(match_music) if match_music in self.match_music_opts else 0
        
        # Dropdown state
        self.menu_music_dropdown_open = False
        self.match_music_dropdown_open = False
        
        # Scroll state cho dropdown lists
        self.menu_music_scroll_offset = 0
        self.match_music_scroll_offset = 0
        self.menu_music_scroll_dragging = False
        self.match_music_scroll_dragging = False
        # Flag để ngăn selection khi wheel scroll
        self._wheel_scrolling_menu = False
        self._wheel_scrolling_match = False

        # Decorative Play button image
        self.play_img_raw: Optional[pygame.Surface] = self._load_play_image()
        # Advanced config (simple labels for now)
        self.move_time_limit = self.config.MOVE_TIME_LIMIT
        self.max_undo = self.config.MAX_UNDO_PER_PLAYER
        self.max_hint = self.config.MAX_HINT_PER_PLAYER
        self.hint_depth = self.config.HINT_DEPTH

        # Set ID
        self.set_id = str(uuid.uuid4())

        # Avatar file lists (include png/jpg/jpeg)
        def list_avatars(dir_path: str):
            try:
                return [f for f in os.listdir(dir_path) if f.lower().endswith((".png", ".jpg", ".jpeg"))]
            except Exception:
                return []
        self.available_avatars = list_avatars(self.config.avatars_dir)
        self.human_cycle_idx = 0
        self.ai_cycle_idx = 0
        # Logout button rect
        self.btn_logout = pygame.Rect(0, 0, 0, 0)
        # Exit decorative image
        self._exit_img_raw = None
        self._exit_rect = pygame.Rect(0, 0, 0, 0)
        try:
            path = os.path.join(self.config.decorate_dir, "Exit.png")
            if os.path.exists(path):
                self._exit_img_raw = pygame.image.load(path).convert_alpha()
        except Exception:
            self._exit_img_raw = None
        
        # Background image cho Game Settings
        self._bg_setting_img = None
        self._bg_setting_cache = {}  # Cache cho scaled background
        try:
            bg_path = os.path.join(self.config.decorate_dir, "bgsetting.jpg")
            if os.path.exists(bg_path):
                self._bg_setting_img = pygame.image.load(bg_path).convert()
        except Exception:
            self._bg_setting_img = None
        
        # Frame image cho Game Settings container
        self._frame_setting_img = None
        self._frame_setting_cache = {}  # Cache cho scaled frame
        try:
            frame_path = os.path.join(self.config.decorate_dir, "framesett.png")
            if os.path.exists(frame_path):
                self._frame_setting_img = pygame.image.load(frame_path).convert_alpha()
        except Exception:
            self._frame_setting_img = None
        
        # Game Settings title image
        self._gamestt_img_raw = None
        self._gamestt_cache = {}  # Cache cho scaled title image
        self._gamestt_rect = pygame.Rect(0, 0, 0, 0)  # Rect của ảnh
        self._gamestt_title_img = None  # Ảnh đã scale để vẽ
        self._gamestt_title_x = 0  # Vị trí x của ảnh
        self._gamestt_title_y = 0  # Vị trí y của ảnh
        try:
            gamestt_path = os.path.join(self.config.decorate_dir, "gamestt.png")
            if os.path.exists(gamestt_path):
                self._gamestt_img_raw = pygame.image.load(gamestt_path).convert_alpha()
        except Exception:
            self._gamestt_img_raw = None
        
        # Volume control
        self.volume = getattr(self.config, 'volume', 0.7)  # Default 70%
        self._volume_rect = pygame.Rect(0, 0, 0, 0)
        self._volume_slider_track = pygame.Rect(0, 0, 0, 0)
        self._volume_dragging = False
        # Apply initial volume
        try:
            pygame.mixer.music.set_volume(self.volume)
        except Exception:
            pass

    def _load_play_image(self) -> Optional[pygame.Surface]:
        try:
            path = os.path.join(".", "assets", "Decorate", "play.png")
            if os.path.exists(path):
                return pygame.image.load(path).convert_alpha()
        except Exception:
            pass
        return None


    def _update_fonts(self):
        """更新响应式字体"""
        self.title_font = self.assets.get_font(self.layout.get_font_size_title())
        self.text_font = self.assets.get_font(self.layout.get_font_size_text())
        self.small_font = self.assets.get_font(self.layout.get_font_size_small())
    
    def _get_cached_shadow(self, width: int, height: int, alpha: int) -> pygame.Surface:
        """Lấy shadow surface từ cache để tối ưu performance"""
        cache_key = (width, height, alpha)
        if cache_key not in self._button_shadow_cache:
            shadow_surf = pygame.Surface((width, height), pygame.SRCALPHA)
            shadow_surf.fill((0, 0, 0, alpha))
            self._button_shadow_cache[cache_key] = shadow_surf
        return self._button_shadow_cache[cache_key]
    
    def _get_cached_gradient(self, width: int, height: int, bg_color: tuple, factor: float = 0.3) -> pygame.Surface:
        """Lấy gradient surface từ cache để tối ưu performance - Hỗ trợ alpha channel"""
        cache_key = (width, height, bg_color, factor)
        if cache_key not in self._button_gradient_cache:
            bg_surf = pygame.Surface((width, height), pygame.SRCALPHA)
            # Tối ưu: chỉ tính gradient cho mỗi step pixels để giảm số lần vẽ
            step = max(1, height // 100)  # Tối đa 100 dòng
            # Xử lý alpha nếu có trong bg_color (RGBA)
            has_alpha = len(bg_color) == 4
            base_alpha = bg_color[3] if has_alpha else 255
            base_rgb = bg_color[:3] if has_alpha else bg_color
            
            for y in range(0, height, step):
                grad_factor = 1.0 - (y / height) * factor
                # Tính toán RGB
                rgb = tuple(min(255, int(c * grad_factor)) for c in base_rgb)
                # Tính toán alpha nếu có
                if has_alpha:
                    alpha = int(base_alpha * grad_factor)
                    gradient_color = (*rgb, alpha)
                else:
                    gradient_color = rgb
                # Vẽ một dải thay vì một dòng
                end_y = min(y + step, height)
                pygame.draw.rect(bg_surf, gradient_color, (0, y, width, end_y - y))
            self._button_gradient_cache[cache_key] = bg_surf
        return self._button_gradient_cache[cache_key]
    
    def _get_cached_text(self, text: str, font, color: tuple, cache_key_suffix: str = "") -> pygame.Surface:
        """Lấy text surface từ cache để tối ưu performance"""
        cache_key = (text, id(font), color, cache_key_suffix)
        if cache_key not in self._text_cache:
            self._text_cache[cache_key] = font.render(text, True, color)
            # Giới hạn cache size để tránh memory overflow
            if len(self._text_cache) > 500:
                # Xóa 50% cache cũ nhất (FIFO)
                keys_to_remove = list(self._text_cache.keys())[:250]
                for key in keys_to_remove:
                    del self._text_cache[key]
        return self._text_cache[cache_key]
        
    def _recompute_layout(self):
        """重新计算所有布局元素 - Tối ưu: chỉ update khi window size thay đổi"""
        try:
            win_w, win_h = pygame.display.get_surface().get_size()
            # Chỉ update layout nếu window size thay đổi
            if (win_w, win_h) != self._last_window_size:
                self._last_window_size = (win_w, win_h)
                self.layout.update(win_w, win_h)
                self._update_fonts()
                # Clear text cache khi layout thay đổi
                self._text_cache.clear()
        except Exception:
            # Fallback nếu không lấy được surface size
            pass

    def update(self, dt: float):
        # 更新布局
        self._recompute_layout()
        
        # Default avatar based on gender if none chosen
        if not self.human.avatar_path:
            default_file = "human_male.png" if self.human.gender == "Male" else ("human_female.png" if self.human.gender == "Female" else "human_male.png")
            self.human.avatar_path = os.path.join(self.config.avatars_dir, default_file)
        return None

    def render(self, surface: pygame.Surface) -> None:
        """完全响应式渲染 - 改进的现代化设计"""
        # 获取容器和列
        container = self.layout.get_container_rect()
        left_col = self.layout.get_left_column_rect(container)
        right_col = self.layout.get_right_column_rect(container)
        
        margin = self.layout.get_margin()
        spacing = self.layout.get_spacing()
        
        # 绘制背景 - Sử dụng background image nếu có
        if self._bg_setting_img is not None:
            screen_w, screen_h = surface.get_size()
            cache_key = (screen_w, screen_h)
            
            # Kiểm tra cache
            if cache_key not in self._bg_setting_cache:
                # Scale background để fit màn hình
                bg_scaled = pygame.transform.smoothscale(self._bg_setting_img, (screen_w, screen_h))
                self._bg_setting_cache[cache_key] = bg_scaled
            
            # Vẽ background
            surface.blit(self._bg_setting_cache[cache_key], (0, 0))
            
            # Bỏ overlay tối thừa - các phần tử phía trên đã có đủ độ tương phản
        else:
            # Fallback: Vẽ background màu đơn giản
            surface.fill((15, 15, 20))
        
        # Vẽ frame mờ (framesett.png) với hiệu ứng glass nếu có
        if self._frame_setting_img is not None:
            screen_w, screen_h = surface.get_size()
            cache_key = (container.width, container.height)
            
            # Kiểm tra cache
            if cache_key not in self._frame_setting_cache:
                # Scale frame để fit với container, giữ tỷ lệ
                frame_w, frame_h = self._frame_setting_img.get_size()
                scale_w = container.width / max(1, frame_w)
                scale_h = container.height / max(1, frame_h)
                scale = max(scale_w, scale_h) * 1.1  # Scale lớn hơn một chút để đảm bảo cover
                scaled_w = int(frame_w * scale)
                scaled_h = int(frame_h * scale)
                frame_scaled = pygame.transform.smoothscale(self._frame_setting_img, (scaled_w, scaled_h))
                self._frame_setting_cache[cache_key] = frame_scaled
            
            # Lấy frame từ cache
            frame_scaled = self._frame_setting_cache[cache_key]
            frame_w, frame_h = frame_scaled.get_size()
            
            # Căn giữa frame với container
            frame_x = container.centerx - frame_w // 2
            frame_y = container.centery - frame_h // 2
            
            # Tạo surface với alpha để làm mờ - tăng độ mờ
            frame_surf = pygame.Surface((frame_w, frame_h), pygame.SRCALPHA)
            frame_surf.blit(frame_scaled, (0, 0))
            
            # Áp dụng alpha để tạo hiệu ứng mờ/glass - giảm alpha để mờ hơn
            frame_alpha = pygame.Surface((frame_w, frame_h), pygame.SRCALPHA)
            frame_alpha.fill((255, 255, 255, 120))  # Giảm alpha xuống 120 để mờ hơn
            frame_surf.blit(frame_alpha, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
            
            # Thêm overlay tối để tạo hiệu ứng mờ hơn nữa
            frame_overlay = pygame.Surface((frame_w, frame_h), pygame.SRCALPHA)
            frame_overlay.fill((0, 0, 0, 80))  # Overlay tối thêm
            frame_surf.blit(frame_overlay, (0, 0), special_flags=pygame.BLEND_ALPHA_SDL2)
            
            # Vẽ frame với hiệu ứng mờ
            surface.blit(frame_surf, (frame_x, frame_y), special_flags=pygame.BLEND_ALPHA_SDL2)
        else:
            # Fallback: container với glass effect nếu không có frame image
            # 外阴影
            shadow_rect = container.copy()
            shadow_rect.x += 6
            shadow_rect.y += 6
            shadow_surf = pygame.Surface((container.width, container.height), pygame.SRCALPHA)
            shadow_surf.fill((0, 0, 0, 120))
            surface.blit(shadow_surf, shadow_rect, special_flags=pygame.BLEND_ALPHA_SDL2)
            
            # 主容器 - 深色玻璃态
            pygame.draw.rect(surface, (28, 28, 32), container, border_radius=20)
            # 顶部高光条
            highlight_rect = pygame.Rect(container.x, container.y, container.width, 3)
            pygame.draw.rect(surface, (60, 130, 200), highlight_rect, border_radius=20)
            # 外边框 - 更柔和的渐变
            pygame.draw.rect(surface, (55, 55, 60), container, 2, border_radius=20)
            # 内发光
            inner_glow = pygame.Rect(container.x + 2, container.y + 2, container.width - 4, container.height - 4)
            pygame.draw.rect(surface, (40, 40, 45), inner_glow, 1, border_radius=18)
        
        # 标题 - Sử dụng ảnh gamestt.png thay thế text, giữ nguyên vị trí
        title_y = container.y + int(margin * 1.2)
        
        # Tính chiều cao text để làm chuẩn (giữ nguyên vị trí các phần tử bên dưới)
        title_text_temp = self.title_font.render("GAME SETTINGS", True, (255, 255, 255))
        title_text_height = title_text_temp.get_height()
        
        if self._gamestt_img_raw is not None:
            # Scale ảnh title phóng to 150% (x6.75), cho phép đè lên các phần khác, nhưng vẫn giữ nguyên vị trí
            img_w, img_h = self._gamestt_img_raw.get_size()
            # Tính scale ban đầu dựa trên chiều cao text
            base_scale_h = title_text_height / max(1, img_h)
            # Phóng to 150% so với x4.5 (tức là 4.5 * 1.5 = 6.75x)
            scale_factor = base_scale_h * 6.75
            scaled_w = int(img_w * scale_factor)
            scaled_h = int(img_h * scale_factor)
            
            cache_key = (scaled_w, scaled_h)
            if cache_key not in self._gamestt_cache:
                if scaled_w > 0 and scaled_h > 0:
                    scaled_img = pygame.transform.smoothscale(self._gamestt_img_raw, (scaled_w, scaled_h))
                    self._gamestt_cache[cache_key] = scaled_img
                else:
                    self._gamestt_cache[cache_key] = self._gamestt_img_raw
            
            title_img = self._gamestt_cache[cache_key]
            title_x = container.centerx - title_img.get_width() // 2
            # Dời ảnh lên trên 30% chiều cao của ảnh
            title_y_actual = -int(title_img.get_height() * 0.3)
            # Lưu rect của ảnh để kiểm tra hover
            self._gamestt_rect = pygame.Rect(title_x, title_y_actual, title_img.get_width(), title_img.get_height())
            # Lưu thông tin ảnh để vẽ sau cùng (đè lên trên cùng)
            self._gamestt_title_img = title_img
            self._gamestt_title_x = title_x
            self._gamestt_title_y = title_y_actual
            # Vẫn dùng chiều cao text và title_y gốc để tính underline_y, không dùng chiều cao ảnh (giữ nguyên vị trí các phần tử)
            underline_y = title_y + title_text_height + 8
        else:
            # Fallback: Vẽ text nếu không có ảnh
            # Reset rect khi không có ảnh
            self._gamestt_rect = pygame.Rect(0, 0, 0, 0)
            self._gamestt_title_img = None
            self._gamestt_title_x = 0
            self._gamestt_title_y = 0
            
            title = title_text_temp
            title_x = container.centerx - title.get_width() // 2
            
            # Text shadow cho title với hiệu ứng nổi bật hơn
            title_shadow = self.title_font.render("GAME SETTINGS", True, (0, 0, 0))
            surface.blit(title_shadow, (title_x + 3, title_y + 3))
            # Thêm glow effect cho title
            title_glow = self.title_font.render("GAME SETTINGS", True, (100, 150, 255))
            surface.blit(title_glow, (title_x + 1, title_y + 1))
            surface.blit(title, (title_x, title_y))
            underline_y = title_y + title_text_height + 8
        
        # Bỏ underline màu xanh - không vẽ gì cả
        # if self._gamestt_img_raw is not None:
        #     title_max_width = int(container.width * 0.6)
        #     title_target_height = title_text_height
        #     cache_key = (title_max_width, title_target_height)
        #     title_img = self._gamestt_cache.get(cache_key, self._gamestt_img_raw)
        #     underline_width = min(title_img.get_width() + 60, container.width - margin * 2)
        # else:
        #     underline_width = min(title_text_temp.get_width() + 60, container.width - margin * 2)
        # underline_rect = pygame.Rect(container.centerx - underline_width // 2, underline_y, underline_width, 3)
        # pygame.draw.rect(surface, (80, 150, 220), underline_rect, border_radius=2)
        # # Thêm highlight trên underline
        # highlight_rect = pygame.Rect(underline_rect.x, underline_rect.y, underline_rect.width, 1)
        # pygame.draw.rect(surface, (120, 180, 255), highlight_rect, border_radius=2)
        # underline_y = underline_rect.bottom
        
        # Cập nhật underline_y để các phần tử bên dưới không bị lệch
        underline_y = title_y + title_text_height + 8

        # Exit to menu button sẽ được vẽ trong _render_volume_control phía dưới volume control
        self._exit_rect = pygame.Rect(0, 0, 0, 0)

        # Draw user info box with logout button when logged in (cải thiện với red gradient accents)
        # Tính toán vị trí để tránh đè lên exit button và volume control
        username = ""
        try:
            username = self.config.current_user.get("name") if isinstance(self.config.current_user, dict) else (self.config.current_user or "")
        except Exception:
            username = ""
        if username:
            # Tạo box chứa thông tin đăng nhập với thiết kế đẹp hơn
            padding = 10
            box_margin = margin
            
            # Render text để tính toán kích thước box
            user_text = self.small_font.render(f"User: {username}", True, (255, 240, 220))  # Light gold
            logout_text = self.small_font.render("Log out", True, (255, 180, 150))
            
            # Tính toán kích thước box
            box_width = max(user_text.get_width(), logout_text.get_width()) + padding * 2 + 8
            box_height = user_text.get_height() + logout_text.get_height() + padding * 2 + 6
            
            # Vị trí box - Điều chỉnh để tránh đè lên exit/volume control
            # Exit button và volume control ở góc trên bên phải màn hình (không phải container)
            # User box đặt bên trong container, cách lề trái một chút để tránh đè
            screen_w, screen_h = surface.get_size()
            control_width = 180
            control_margin = 20
            # Tính toán vị trí an toàn: bên trái của vùng exit/volume control
            safe_x = screen_w - control_width - control_margin - box_width - margin * 2
            # Đảm bảo không ra ngoài container
            box_x = min(safe_x, container.right - box_width - box_margin)
            box_x = max(container.x + box_margin, box_x)  # Không được nhỏ hơn lề trái container
            box_y = container.y + margin
            user_box = pygame.Rect(box_x, box_y, box_width, box_height)
            
            # Vẽ shadow cho box
            shadow_rect = user_box.copy()
            shadow_rect.x += 3
            shadow_rect.y += 3
            shadow_surf = pygame.Surface((user_box.width, user_box.height), pygame.SRCALPHA)
            shadow_surf.fill((0, 0, 0, 100))
            surface.blit(shadow_surf, shadow_rect, special_flags=pygame.BLEND_ALPHA_SDL2)
            
            # Vẽ background box với dark red gradient
            panel_bg_user = pygame.Surface((user_box.width, user_box.height), pygame.SRCALPHA)
            panel_bg_user.fill((40, 25, 30, 220))  # Dark red semi-transparent
            surface.blit(panel_bg_user, user_box, special_flags=pygame.BLEND_ALPHA_SDL2)
            # Border với red accent
            pygame.draw.rect(surface, (120, 60, 60), user_box, 2, border_radius=10)
            # Inner highlight
            inner_rect = pygame.Rect(user_box.x + 1, user_box.y + 1, user_box.width - 2, user_box.height // 3)
            pygame.draw.rect(surface, (60, 40, 45), inner_rect, border_radius=10)
            
            # Vẽ text thông tin người dùng
            user_text_y = box_y + padding
            surface.blit(user_text, (box_x + padding, user_text_y))
            
            # Vẽ button logout (có thể click)
            logout_y = user_text_y + user_text.get_height() + 6
            logout_rect = pygame.Rect(box_x + padding, logout_y, logout_text.get_width() + 6, logout_text.get_height() + 4)
            
            # Hover effect cho logout button
            mouse_pos = pygame.mouse.get_pos()
            is_hovered = logout_rect.collidepoint(mouse_pos)
            
            # Vẽ logout button background với red accent
            logout_bg = (80, 40, 40) if is_hovered else (60, 30, 30)
            pygame.draw.rect(surface, logout_bg, logout_rect, border_radius=6)
            pygame.draw.rect(surface, (220, 120, 120) if is_hovered else (180, 90, 90), logout_rect, 1, border_radius=6)
            
            # Vẽ logout text
            surface.blit(logout_text, (logout_rect.x + 3, logout_rect.y + 2))
            
            # Set clickable area cho logout
            self.btn_logout = logout_rect
        else:
            self.btn_logout = pygame.Rect(0, 0, 0, 0)
        
        current_y = underline_y + spacing * 1.5  # Tối ưu: spacing hợp lý để vừa khung

        # ========== Vẽ divider rõ ràng giữa 2 cột ==========
        divider_x = container.centerx
        divider_top = current_y
        divider_bottom = container.bottom - margin * 3
        divider_width = 2
        
        # Divider với gradient effect
        divider_rect = pygame.Rect(divider_x - divider_width // 2, divider_top, divider_width, divider_bottom - divider_top)
        # Shadow cho divider
        divider_shadow = divider_rect.copy()
        divider_shadow.x += 1
        shadow_surf = pygame.Surface((divider_width + 2, divider_rect.height), pygame.SRCALPHA)
        shadow_surf.fill((0, 0, 0, 80))
        surface.blit(shadow_surf, divider_shadow, special_flags=pygame.BLEND_ALPHA_SDL2)
        # Divider chính với gradient
        pygame.draw.rect(surface, (120, 80, 60), divider_rect, border_radius=1)
        # Highlight trên divider
        highlight_divider = pygame.Rect(divider_rect.x, divider_rect.y, divider_rect.width, 1)
        pygame.draw.rect(surface, (180, 120, 80), highlight_divider, border_radius=1)

        # ========== 左列内容 - Player & Match Settings với Panel Container ==========
        
        # Panel container cho cột trái với background semi-transparent - Improved design
        left_panel_rect = pygame.Rect(
            left_col.x + spacing // 2, 
            current_y - spacing // 2,
            left_col.width - spacing,
            container.bottom - current_y - margin * 2
        )
        # Panel shadow với depth
        panel_shadow = left_panel_rect.copy()
        panel_shadow.x += 4
        panel_shadow.y += 4
        shadow_surf = pygame.Surface((left_panel_rect.width, left_panel_rect.height), pygame.SRCALPHA)
        shadow_surf.fill((0, 0, 0, 100))
        surface.blit(shadow_surf, panel_shadow, special_flags=pygame.BLEND_ALPHA_SDL2)
        
        # Panel background với red gradient accents - Tối ưu với cache
        panel_bg = self._get_cached_gradient(
            left_panel_rect.width, 
            left_panel_rect.height, 
            (30, 20, 25, 200), 
            factor=0.2
        )
        surface.blit(panel_bg, left_panel_rect, special_flags=pygame.BLEND_ALPHA_SDL2)
        
        # Panel border với red accent và highlight
        pygame.draw.rect(surface, (100, 50, 50), left_panel_rect, 2, border_radius=12)
        # Top highlight
        top_highlight = pygame.Rect(left_panel_rect.x, left_panel_rect.y, left_panel_rect.width, 2)
        pygame.draw.rect(surface, (150, 80, 80), top_highlight, border_radius=12)
        # Inner glow với gradient
        inner_glow = pygame.Rect(left_panel_rect.x + 1, left_panel_rect.y + 1, left_panel_rect.width - 2, left_panel_rect.height - 2)
        pygame.draw.rect(surface, (50, 30, 35), inner_glow, 1, border_radius=11)
        
        # Section header với styling đẹp hơn - Tối ưu với cache
        section_title_left = self._get_cached_text("Player & Match Settings", self.text_font, (255, 220, 180))
        title_bg_rect = pygame.Rect(
            left_col.x + spacing,
            current_y - 4,
            section_title_left.get_width() + spacing,
            section_title_left.get_height() + 8
        )
        # Header background với gradient
        header_bg = pygame.Surface((title_bg_rect.width, title_bg_rect.height), pygame.SRCALPHA)
        header_bg.fill((60, 30, 20, 180))  # Dark red-orange
        surface.blit(header_bg, title_bg_rect, special_flags=pygame.BLEND_ALPHA_SDL2)
        pygame.draw.rect(surface, (150, 100, 60), title_bg_rect, 1, border_radius=6)
        surface.blit(section_title_left, (left_col.x + spacing + spacing // 2, current_y))
        
        # Vẽ line dưới tiêu đề với gradient effect
        section_line = pygame.Rect(left_col.x + spacing, current_y + section_title_left.get_height() + 8, left_col.width - spacing * 2, 2)
        pygame.draw.rect(surface, (120, 80, 60), section_line, border_radius=1)
        # Highlight trên line
        highlight_line = pygame.Rect(section_line.x, section_line.y, section_line.width, 1)
        pygame.draw.rect(surface, (180, 120, 80), highlight_line, border_radius=1)
        current_y += section_title_left.get_height() + spacing * 1.2  # Tối ưu: spacing hợp lý
        
        # Name input - 改进的设计
        label = self.small_font.render("Full name / Nickname:", True, (220, 220, 230))
        surface.blit(label, (left_col.x + spacing, current_y))
        current_y += label.get_height() + spacing // 3  # Tối ưu: spacing hợp lý
        
        # Tính toán input rect với kích thước tối ưu
        input_width = left_col.width - spacing * 2
        input_height = self.layout.scale(44)  # Tối ưu: 44px để vừa khung
        self.input_rect = pygame.Rect(left_col.x + spacing, current_y, input_width, input_height)
        # 输入框 - 更现代的设计 (thiết kế lại đẹp hơn)
        input_bg = (42, 42, 50) if not self.input_active else (52, 52, 60)
        # Shadow cho input
        input_shadow = self.input_rect.copy()
        input_shadow.x += 2
        input_shadow.y += 2
        shadow_surf = pygame.Surface((self.input_rect.width, self.input_rect.height), pygame.SRCALPHA)
        shadow_surf.fill((0, 0, 0, 60))
        surface.blit(shadow_surf, input_shadow, special_flags=pygame.BLEND_ALPHA_SDL2)
        pygame.draw.rect(surface, input_bg, self.input_rect, border_radius=10)
        # Inner highlight
        inner_highlight = pygame.Rect(self.input_rect.x + 1, self.input_rect.y + 1, self.input_rect.width - 2, self.input_rect.height // 3)
        pygame.draw.rect(surface, (55, 55, 63), inner_highlight, border_radius=10)
        
        # 激活时的发光效果
        if self.input_active:
            glow_surf = pygame.Surface((self.input_rect.width + 12, self.input_rect.height + 12), pygame.SRCALPHA)
            glow_rect = pygame.Rect(6, 6, self.input_rect.width, self.input_rect.height)
            accent = self.config.colors["accent"]
            glow_color = (*accent[:3], 40)
            try:
                pygame.draw.rect(glow_surf, glow_color, glow_rect, border_radius=12)
            except TypeError:
                pygame.draw.rect(glow_surf, accent, glow_rect, border_radius=12)
            surface.blit(glow_surf, (self.input_rect.x - 6, self.input_rect.y - 6), special_flags=pygame.BLEND_ALPHA_SDL2)
        
        # 边框 - 激活时使用强调色 (thiết kế lại)
        border_color = self.config.colors["accent"] if self.input_active else (80, 80, 90)
        border_width = 2 if self.input_active else 1
        pygame.draw.rect(surface, border_color, self.input_rect, border_width, border_radius=10)
        
        # 输入文本
        name_txt = self.text_font.render(self.human.name or "", True, (255, 255, 255))
        if name_txt.get_width() > self.input_rect.width - 20:
            truncated = self.human.name
            while truncated and self.text_font.size(truncated + "...")[0] > self.input_rect.width - 20:
                truncated = truncated[:-1]
            name_txt = self.text_font.render(truncated + "..." if truncated != self.human.name else self.human.name, True, (255, 255, 255))
        surface.blit(name_txt, (self.input_rect.x + 12, self.input_rect.y + (self.input_rect.height - name_txt.get_height()) // 2))
        current_y += self.input_rect.height + spacing * 0.8  # Tối ưu: spacing hợp lý

        # Best-of-N buttons - Kích thước vừa phải
        bon_label = self.small_font.render("Number of rounds:", True, (220, 230, 240))
        surface.blit(bon_label, (left_col.x + spacing, current_y))
        current_y += bon_label.get_height() + spacing // 3  # Tối ưu: spacing hợp lý
        
        bon_values = [3, 5, 7, 9]
        
        # Tính toán chiều rộng và vị trí buttons để vừa khít trong left_col
        btn_spacing = spacing // 2
        total_btn_spacing = btn_spacing * (len(bon_values) - 1)
        available_width = left_col.width - spacing * 2  # margin 2 bên
        btn_width = (available_width - total_btn_spacing) // len(bon_values)
        btn_height = self.layout.scale(44)  # Tối ưu: 44px để vừa khung
        
        self.btn_bon_rects = []
        x_start = left_col.x + spacing
        for i, n in enumerate(bon_values):
            btn_x = x_start + i * (btn_width + btn_spacing)
            rect = pygame.Rect(btn_x, current_y, btn_width, btn_height)
            self.btn_bon_rects.append(rect)
            
            is_selected = self.best_of_n == n
            # 按钮设计 - Blue cho selections (thiết kế lại)
            if is_selected:
                # 选中状态 - Blue color cho selections
                bg_color = (70, 130, 200)  # Blue
                # 阴影 - sử dụng cache
                shadow_rect = rect.copy()
                shadow_rect.x += 2
                shadow_rect.y += 2
                shadow_surf = self._get_cached_shadow(rect.width, rect.height, 100)
                surface.blit(shadow_surf, shadow_rect, special_flags=pygame.BLEND_ALPHA_SDL2)
                pygame.draw.rect(surface, bg_color, rect, border_radius=10)
                # 顶部高光
                highlight = pygame.Rect(rect.x + 1, rect.y + 1, rect.width - 2, rect.height // 3)
                highlight_color = (100, 160, 230)
                pygame.draw.rect(surface, highlight_color, highlight, border_radius=10)
                # 白色边框
                pygame.draw.rect(surface, (255, 255, 255), rect, 2, border_radius=10)
            else:
                # 未选中状态 - Dark gray
                pygame.draw.rect(surface, (48, 48, 55), rect, border_radius=10)
                pygame.draw.rect(surface, (82, 82, 92), rect, 1, border_radius=10)
            
            # 文本
            txt = self.small_font.render(str(n), True, (255, 255, 255) if is_selected else (180, 180, 190))
            txt_rect = txt.get_rect(center=rect.center)
            surface.blit(txt, txt_rect)
        current_y += self.btn_bon_rects[0].height + spacing * 0.8  # Tối ưu: spacing hợp lý
        
        # Gender selection - Kích thước vừa phải
        g_label = self.small_font.render("Gender:", True, (220, 230, 240))
        surface.blit(g_label, (left_col.x + spacing, current_y))
        current_y += g_label.get_height() + spacing // 3  # Tối ưu: spacing hợp lý
        
        # Tạo 3 buttons cho Male, Female, Other
        self.gender_button_rects = []
        # Tính toán chiều rộng button để vừa khít trong left_col
        button_spacing = spacing // 2
        total_spacing = button_spacing * 2  # 2 khoảng cách giữa 3 buttons
        available_width = left_col.width - spacing * 2  # margin 2 bên
        button_width = (available_width - total_spacing) // 3
        button_height = self.layout.scale(44)  # Tối ưu: 44px để vừa khung
        
        for i, gender_option in enumerate(self.gender_opts):
            button_x = left_col.x + spacing + i * (button_width + button_spacing)
            button_rect = pygame.Rect(button_x, current_y, button_width, button_height)
            self.gender_button_rects.append(button_rect)
            
            # Button background với shadow
            is_selected = (i == self.gender_idx)
            
            if is_selected:
                bg_color = (70, 130, 200)  # Màu xanh khi được chọn
                border_color = (100, 160, 230)
                border_width = 2
                # Shadow - sử dụng cache
                shadow_rect = button_rect.copy()
                shadow_rect.x += 2
                shadow_rect.y += 2
                shadow_surf = self._get_cached_shadow(button_rect.width, button_rect.height, 100)
                surface.blit(shadow_surf, shadow_rect, special_flags=pygame.BLEND_ALPHA_SDL2)
                # Inner glow
                inner_rect = pygame.Rect(button_rect.x + 1, button_rect.y + 1, button_rect.width - 2, button_rect.height // 3)
                pygame.draw.rect(surface, (90, 150, 220), inner_rect, border_radius=10)
            else:
                bg_color = (46, 50, 60)
                border_color = (82, 88, 98)
                border_width = 1
            
            pygame.draw.rect(surface, bg_color, button_rect, border_radius=10)
            pygame.draw.rect(surface, border_color, button_rect, border_width, border_radius=10)
            
            # Button text với shadow
            text_color = (255, 255, 255) if is_selected else (180, 185, 195)
            gender_text = self.text_font.render(gender_option, True, text_color)
            text_rect = gender_text.get_rect(center=button_rect.center)
            if is_selected:
                shadow_text = self.text_font.render(gender_option, True, (0, 0, 0))
                surface.blit(shadow_text, (text_rect.x + 1, text_rect.y + 1))
            surface.blit(gender_text, text_rect)
        
        current_y += button_height + spacing * 0.8  # Tối ưu: spacing hợp lý
        
        # Music Selection - Dropdown style ở cột trái (đặt trước avatar) - Ngang hàng
        music_section_y = current_y
        
        # Tính toán width cho 2 dropdowns ngang hàng
        dropdown_spacing = spacing // 2
        dropdown_width = (left_col.width - spacing * 2 - dropdown_spacing) // 2
        dropdown_height = self.layout.scale(44)
        
        # Menu Music - Bên trái
        menu_music_label = self.small_font.render("Menu Music:", True, (220, 230, 240))
        surface.blit(menu_music_label, (left_col.x + spacing, music_section_y))
        menu_dropdown_y = music_section_y + menu_music_label.get_height() + spacing // 3
        self.menu_music_dropdown_rect = pygame.Rect(left_col.x + spacing, menu_dropdown_y, dropdown_width, dropdown_height)
        # Tạo vùng scroll mở rộng bao gồm cả label và dropdown button
        menu_label_height = menu_music_label.get_height()
        self.menu_music_scroll_area_rect = pygame.Rect(
            left_col.x + spacing,
            music_section_y,
            dropdown_width,
            menu_label_height + spacing // 3 + dropdown_height
        )
        
        # Check hover state
        is_hovered = self.menu_music_dropdown_rect.collidepoint(pygame.mouse.get_pos())
        is_open = self.menu_music_dropdown_open
        
        # Shadow effect
        shadow_rect = self.menu_music_dropdown_rect.copy()
        shadow_rect.x += 2
        shadow_rect.y += 2
        shadow_surf = self._get_cached_shadow(dropdown_width, dropdown_height, 120 if is_hovered or is_open else 80)
        surface.blit(shadow_surf, shadow_rect, special_flags=pygame.BLEND_ALPHA_SDL2)
        
        # Background với gradient effect
        if is_open or is_hovered:
            bg_color = (55, 55, 65)  # Sáng hơn khi hover/open
            border_color = (100, 150, 220)  # Blue accent khi active
            border_width = 2
        else:
            bg_color = (43, 43, 50)
            border_color = (80, 80, 90)
            border_width = 1
        
        pygame.draw.rect(surface, bg_color, self.menu_music_dropdown_rect, border_radius=10)
        
        # Top highlight gradient
        highlight_rect = pygame.Rect(
            self.menu_music_dropdown_rect.x + 1,
            self.menu_music_dropdown_rect.y + 1,
            self.menu_music_dropdown_rect.width - 2,
            self.menu_music_dropdown_rect.height // 3
        )
        highlight_color = (65, 65, 75) if is_open or is_hovered else (50, 50, 58)
        pygame.draw.rect(surface, highlight_color, highlight_rect, border_radius=10)
        
        # Border
        pygame.draw.rect(surface, border_color, self.menu_music_dropdown_rect, border_width, border_radius=10)
        
        # Glow effect khi mở
        if is_open:
            glow_surf = pygame.Surface((dropdown_width + 8, dropdown_height + 8), pygame.SRCALPHA)
            glow_rect = pygame.Rect(4, 4, dropdown_width, dropdown_height)
            glow_color = (*border_color[:3], 60)
            pygame.draw.rect(glow_surf, glow_color, glow_rect, border_radius=12)
            surface.blit(glow_surf, (self.menu_music_dropdown_rect.x - 4, self.menu_music_dropdown_rect.y - 4), special_flags=pygame.BLEND_ALPHA_SDL2)
        
        # Selected music name với better typography
        selected_menu_music = self.menu_music_opts[self.menu_music_idx] if self.menu_music_idx < len(self.menu_music_opts) else ""
        music_display_name = selected_menu_music.replace(".mp3", "").replace(".ogg", "").replace(".wav", "").strip()
        music_text = self.small_font.render(music_display_name, True, (255, 255, 255))
        # Text shadow
        shadow_text = self.small_font.render(music_display_name, True, (0, 0, 0))
        surface.blit(shadow_text, (self.menu_music_dropdown_rect.x + 13, self.menu_music_dropdown_rect.centery - music_text.get_height() // 2 + 1))
        surface.blit(music_text, (self.menu_music_dropdown_rect.x + 12, self.menu_music_dropdown_rect.centery - music_text.get_height() // 2))
        
        # Dropdown arrow với better styling
        arrow_size = 10
        arrow_x = self.menu_music_dropdown_rect.right - 24
        arrow_y = self.menu_music_dropdown_rect.centery
        arrow_color = (180, 200, 255) if is_open or is_hovered else (180, 180, 200)
        
        if is_open:
            # Arrow up
            pygame.draw.polygon(surface, arrow_color, [
                (arrow_x, arrow_y - arrow_size // 2),
                (arrow_x - arrow_size, arrow_y + arrow_size // 2),
                (arrow_x + arrow_size, arrow_y + arrow_size // 2)
            ])
        else:
            # Arrow down
            pygame.draw.polygon(surface, arrow_color, [
                (arrow_x, arrow_y + arrow_size // 2),
                (arrow_x - arrow_size, arrow_y - arrow_size // 2),
                (arrow_x + arrow_size, arrow_y - arrow_size // 2)
            ])
        
        # Dropdown list (nếu mở) - Improved design với scrollbar
        if self.menu_music_dropdown_open:
            list_y = menu_dropdown_y + dropdown_height + 4
            # Hiển thị tối đa 4 items
            max_visible_items = 4
            list_height = max_visible_items * dropdown_height + 6
            scrollbar_width = 8
            item_area_width = dropdown_width - scrollbar_width - 4
            self.menu_music_list_rect = pygame.Rect(left_col.x + spacing, list_y, dropdown_width, list_height)
            
            # Tính toán scroll
            total_items = len(self.menu_music_opts)
            max_scroll = max(0, total_items - max_visible_items)
            self.menu_music_scroll_offset = max(0, min(self.menu_music_scroll_offset, max_scroll))
            
            # List shadow
            list_shadow = self.menu_music_list_rect.copy()
            list_shadow.x += 3
            list_shadow.y += 3
            list_shadow_surf = self._get_cached_shadow(dropdown_width, list_height, 150)
            surface.blit(list_shadow_surf, list_shadow, special_flags=pygame.BLEND_ALPHA_SDL2)
            
            # List background với gradient - Tối ưu với cache
            list_bg = self._get_cached_gradient(
                self.menu_music_list_rect.width,
                self.menu_music_list_rect.height,
                (30, 32, 38, 240),
                factor=0.1
            )
            surface.blit(list_bg, self.menu_music_list_rect, special_flags=pygame.BLEND_ALPHA_SDL2)
            
            # Border với accent
            pygame.draw.rect(surface, (100, 150, 220), self.menu_music_list_rect, 2, border_radius=10)
            # Inner border
            inner_border = pygame.Rect(
                self.menu_music_list_rect.x + 1,
                self.menu_music_list_rect.y + 1,
                self.menu_music_list_rect.width - 2,
                self.menu_music_list_rect.height - 2
            )
            pygame.draw.rect(surface, (50, 50, 60), inner_border, 1, border_radius=9)
            
            # List items với scroll
            self.menu_music_item_rects = []
            mouse_pos = pygame.mouse.get_pos()
            visible_start = self.menu_music_scroll_offset
            visible_end = min(visible_start + max_visible_items, total_items)
            
            for idx in range(visible_start, visible_end):
                i = idx - visible_start
                music_file = self.menu_music_opts[idx]
                item_rect = pygame.Rect(
                    self.menu_music_list_rect.x + 3,
                    self.menu_music_list_rect.y + 3 + i * dropdown_height,
                    item_area_width,
                    dropdown_height - 2
                )
                self.menu_music_item_rects.append((item_rect, idx))
                
                is_selected = idx == self.menu_music_idx
                is_hovered_item = item_rect.collidepoint(mouse_pos)
                
                # Item background
                if is_selected:
                    # Selected item với gradient
                    item_bg = pygame.Surface((item_rect.width, item_rect.height), pygame.SRCALPHA)
                    for y in range(item_rect.height):
                        factor = 1.0 - (y / item_rect.height) * 0.3
                        alpha = int(255 * factor)
                        color = (int(70 * factor), int(130 * factor), int(200 * factor), alpha)
                        pygame.draw.line(item_bg, color, (0, y), (item_rect.width, y))
                    surface.blit(item_bg, item_rect, special_flags=pygame.BLEND_ALPHA_SDL2)
                    pygame.draw.rect(surface, (100, 160, 230), item_rect, 2, border_radius=8)
                elif is_hovered_item:
                    pygame.draw.rect(surface, (60, 60, 75), item_rect, border_radius=8)
                    pygame.draw.rect(surface, (80, 80, 95), item_rect, 1, border_radius=8)
                
                # Item text với better styling
                item_name = music_file.replace(".mp3", "").replace(".ogg", "").replace(".wav", "").strip()
                text_color = (255, 255, 255) if is_selected else (220, 220, 230)
                item_text = self.small_font.render(item_name, True, text_color)
                # Text shadow cho selected item
                if is_selected:
                    shadow_item_text = self.small_font.render(item_name, True, (0, 0, 0))
                    surface.blit(shadow_item_text, (item_rect.x + 13, item_rect.centery - item_text.get_height() // 2 + 1))
                surface.blit(item_text, (item_rect.x + 12, item_rect.centery - item_text.get_height() // 2))
            
            # Scrollbar (nếu cần) - Improved design với hover effects
            if total_items > max_visible_items:
                scrollbar_x = self.menu_music_list_rect.right - scrollbar_width - 2
                scrollbar_y = self.menu_music_list_rect.y + 2
                scrollbar_height = self.menu_music_list_rect.height - 4
                self.menu_music_scrollbar_rect = pygame.Rect(scrollbar_x, scrollbar_y, scrollbar_width, scrollbar_height)
                
                # Scrollbar track với gradient và shadow
                track_shadow = self.menu_music_scrollbar_rect.copy()
                track_shadow.x += 1
                track_shadow.y += 1
                shadow_surf = pygame.Surface((scrollbar_width, scrollbar_height), pygame.SRCALPHA)
                shadow_surf.fill((0, 0, 0, 100))
                surface.blit(shadow_surf, track_shadow, special_flags=pygame.BLEND_ALPHA_SDL2)
                
                # Track background với gradient
                track_bg = pygame.Surface((scrollbar_width, scrollbar_height), pygame.SRCALPHA)
                for y in range(scrollbar_height):
                    factor = 1.0 - (y / scrollbar_height) * 0.2
                    alpha = int(200 * factor)
                    color = (int(40 * factor), int(40 * factor), int(50 * factor), alpha)
                    pygame.draw.line(track_bg, color, (0, y), (scrollbar_width, y))
                surface.blit(track_bg, self.menu_music_scrollbar_rect, special_flags=pygame.BLEND_ALPHA_SDL2)
                pygame.draw.rect(surface, (60, 60, 75), self.menu_music_scrollbar_rect, border_radius=4)
                # Inner border
                inner_track = pygame.Rect(scrollbar_x + 1, scrollbar_y + 1, scrollbar_width - 2, scrollbar_height - 2)
                pygame.draw.rect(surface, (35, 35, 45), inner_track, border_radius=3)
                
                # Scrollbar thumb với hover effect
                thumb_height = max(24, int(scrollbar_height * max_visible_items / total_items))
                thumb_y_range = scrollbar_height - thumb_height
                thumb_y = scrollbar_y + int(thumb_y_range * (self.menu_music_scroll_offset / max_scroll)) if max_scroll > 0 else scrollbar_y
                self.menu_music_scrollbar_thumb_rect = pygame.Rect(scrollbar_x, thumb_y, scrollbar_width, thumb_height)
                
                # Check hover state
                mouse_pos = pygame.mouse.get_pos()
                is_thumb_hovered = self.menu_music_scrollbar_thumb_rect.collidepoint(mouse_pos)
                is_track_hovered = self.menu_music_scrollbar_rect.collidepoint(mouse_pos)
                is_dragging = self.menu_music_scroll_dragging
                
                # Thumb shadow
                thumb_shadow = self.menu_music_scrollbar_thumb_rect.copy()
                thumb_shadow.x += 1
                thumb_shadow.y += 1
                thumb_shadow_surf = pygame.Surface((scrollbar_width, thumb_height), pygame.SRCALPHA)
                thumb_shadow_surf.fill((0, 0, 0, 120 if (is_thumb_hovered or is_dragging) else 80))
                surface.blit(thumb_shadow_surf, thumb_shadow, special_flags=pygame.BLEND_ALPHA_SDL2)
                
                # Thumb background với gradient
                thumb_bg = pygame.Surface((scrollbar_width, thumb_height), pygame.SRCALPHA)
                if is_thumb_hovered or is_dragging:
                    # Hover/drag state - sáng hơn
                    for y in range(thumb_height):
                        factor = 1.0 - (y / thumb_height) * 0.3
                        alpha = int(255 * factor)
                        color = (int(120 * factor), int(170 * factor), int(250 * factor), alpha)
                        pygame.draw.line(thumb_bg, color, (0, y), (scrollbar_width, y))
                else:
                    # Normal state
                    for y in range(thumb_height):
                        factor = 1.0 - (y / thumb_height) * 0.2
                        alpha = int(255 * factor)
                        color = (int(100 * factor), int(150 * factor), int(220 * factor), alpha)
                        pygame.draw.line(thumb_bg, color, (0, y), (scrollbar_width, y))
                surface.blit(thumb_bg, self.menu_music_scrollbar_thumb_rect, special_flags=pygame.BLEND_ALPHA_SDL2)
                
                # Thumb border
                border_color = (140, 190, 255) if (is_thumb_hovered or is_dragging) else (120, 170, 240)
                border_width = 2 if (is_thumb_hovered or is_dragging) else 1
                pygame.draw.rect(surface, border_color, self.menu_music_scrollbar_thumb_rect, border_width, border_radius=4)
                
                # Thumb highlight (top)
                if thumb_height > 4:
                    highlight_rect = pygame.Rect(scrollbar_x, thumb_y, scrollbar_width, max(2, thumb_height // 4))
                    highlight_color = (180, 220, 255) if (is_thumb_hovered or is_dragging) else (150, 200, 255)
                    pygame.draw.rect(surface, highlight_color, highlight_rect, border_radius=4)
            else:
                self.menu_music_scrollbar_rect = pygame.Rect(0, 0, 0, 0)
                self.menu_music_scrollbar_thumb_rect = pygame.Rect(0, 0, 0, 0)
        else:
            self.menu_music_list_rect = pygame.Rect(0, 0, 0, 0)
            self.menu_music_item_rects = []
            self.menu_music_scrollbar_rect = pygame.Rect(0, 0, 0, 0)
            self.menu_music_scrollbar_thumb_rect = pygame.Rect(0, 0, 0, 0)
        
        # Match Music - Bên phải (ngang hàng với Menu Music)
        match_music_label = self.small_font.render("Match Music:", True, (220, 230, 240))
        match_label_x = left_col.x + spacing + dropdown_width + dropdown_spacing
        surface.blit(match_music_label, (match_label_x, music_section_y))
        match_dropdown_y = music_section_y + match_music_label.get_height() + spacing // 3
        self.match_music_dropdown_rect = pygame.Rect(match_label_x, match_dropdown_y, dropdown_width, dropdown_height)
        # Tạo vùng scroll mở rộng bao gồm cả label và dropdown button
        match_label_height = match_music_label.get_height()
        self.match_music_scroll_area_rect = pygame.Rect(
            match_label_x,
            music_section_y,
            dropdown_width,
            match_label_height + spacing // 3 + dropdown_height
        )
        
        # Check hover state
        is_hovered = self.match_music_dropdown_rect.collidepoint(pygame.mouse.get_pos())
        is_open = self.match_music_dropdown_open
        
        # Shadow effect
        shadow_rect = self.match_music_dropdown_rect.copy()
        shadow_rect.x += 2
        shadow_rect.y += 2
        shadow_surf = self._get_cached_shadow(dropdown_width, dropdown_height, 120 if is_hovered or is_open else 80)
        surface.blit(shadow_surf, shadow_rect, special_flags=pygame.BLEND_ALPHA_SDL2)
        
        # Background với gradient effect
        if is_open or is_hovered:
            bg_color = (55, 55, 65)  # Sáng hơn khi hover/open
            border_color = (100, 150, 220)  # Blue accent khi active
            border_width = 2
        else:
            bg_color = (43, 43, 50)
            border_color = (80, 80, 90)
            border_width = 1
        
        pygame.draw.rect(surface, bg_color, self.match_music_dropdown_rect, border_radius=10)
        
        # Top highlight gradient
        highlight_rect = pygame.Rect(
            self.match_music_dropdown_rect.x + 1,
            self.match_music_dropdown_rect.y + 1,
            self.match_music_dropdown_rect.width - 2,
            self.match_music_dropdown_rect.height // 3
        )
        highlight_color = (65, 65, 75) if is_open or is_hovered else (50, 50, 58)
        pygame.draw.rect(surface, highlight_color, highlight_rect, border_radius=10)
        
        # Border
        pygame.draw.rect(surface, border_color, self.match_music_dropdown_rect, border_width, border_radius=10)
        
        # Glow effect khi mở
        if is_open:
            glow_surf = pygame.Surface((dropdown_width + 8, dropdown_height + 8), pygame.SRCALPHA)
            glow_rect = pygame.Rect(4, 4, dropdown_width, dropdown_height)
            glow_color = (*border_color[:3], 60)
            pygame.draw.rect(glow_surf, glow_color, glow_rect, border_radius=12)
            surface.blit(glow_surf, (self.match_music_dropdown_rect.x - 4, self.match_music_dropdown_rect.y - 4), special_flags=pygame.BLEND_ALPHA_SDL2)
        
        # Selected music name với better typography
        selected_match_music = self.match_music_opts[self.match_music_idx] if self.match_music_idx < len(self.match_music_opts) else ""
        match_music_display_name = selected_match_music.replace(".mp3", "").replace(".ogg", "").replace(".wav", "").strip()
        match_music_text = self.small_font.render(match_music_display_name, True, (255, 255, 255))
        # Text shadow
        shadow_text = self.small_font.render(match_music_display_name, True, (0, 0, 0))
        surface.blit(shadow_text, (self.match_music_dropdown_rect.x + 13, self.match_music_dropdown_rect.centery - match_music_text.get_height() // 2 + 1))
        surface.blit(match_music_text, (self.match_music_dropdown_rect.x + 12, self.match_music_dropdown_rect.centery - match_music_text.get_height() // 2))
        
        # Dropdown arrow với better styling
        arrow_size = 10
        arrow_x = self.match_music_dropdown_rect.right - 24
        arrow_y = self.match_music_dropdown_rect.centery
        arrow_color = (180, 200, 255) if is_open or is_hovered else (180, 180, 200)
        
        if is_open:
            # Arrow up
            pygame.draw.polygon(surface, arrow_color, [
                (arrow_x, arrow_y - arrow_size // 2),
                (arrow_x - arrow_size, arrow_y + arrow_size // 2),
                (arrow_x + arrow_size, arrow_y + arrow_size // 2)
            ])
        else:
            # Arrow down
            pygame.draw.polygon(surface, arrow_color, [
                (arrow_x, arrow_y + arrow_size // 2),
                (arrow_x - arrow_size, arrow_y - arrow_size // 2),
                (arrow_x + arrow_size, arrow_y - arrow_size // 2)
            ])
        
        # Dropdown list (nếu mở) - Improved design với scrollbar
        if self.match_music_dropdown_open:
            list_y = match_dropdown_y + dropdown_height + 4
            # Hiển thị tối đa 4 items
            max_visible_items = 4
            list_height = max_visible_items * dropdown_height + 6
            scrollbar_width = 8
            item_area_width = dropdown_width - scrollbar_width - 4
            self.match_music_list_rect = pygame.Rect(match_label_x, list_y, dropdown_width, list_height)
            
            # Tính toán scroll
            total_items = len(self.match_music_opts)
            max_scroll = max(0, total_items - max_visible_items)
            self.match_music_scroll_offset = max(0, min(self.match_music_scroll_offset, max_scroll))
            
            # List shadow
            list_shadow = self.match_music_list_rect.copy()
            list_shadow.x += 3
            list_shadow.y += 3
            list_shadow_surf = self._get_cached_shadow(dropdown_width, list_height, 150)
            surface.blit(list_shadow_surf, list_shadow, special_flags=pygame.BLEND_ALPHA_SDL2)
            
            # List background với gradient - Tối ưu với cache
            list_bg = self._get_cached_gradient(
                self.match_music_list_rect.width,
                self.match_music_list_rect.height,
                (30, 32, 38, 240),
                factor=0.1
            )
            surface.blit(list_bg, self.match_music_list_rect, special_flags=pygame.BLEND_ALPHA_SDL2)
            
            # Border với accent
            pygame.draw.rect(surface, (100, 150, 220), self.match_music_list_rect, 2, border_radius=10)
            # Inner border
            inner_border = pygame.Rect(
                self.match_music_list_rect.x + 1,
                self.match_music_list_rect.y + 1,
                self.match_music_list_rect.width - 2,
                self.match_music_list_rect.height - 2
            )
            pygame.draw.rect(surface, (50, 50, 60), inner_border, 1, border_radius=9)
            
            # List items với scroll
            self.match_music_item_rects = []
            mouse_pos = pygame.mouse.get_pos()
            visible_start = self.match_music_scroll_offset
            visible_end = min(visible_start + max_visible_items, total_items)
            
            for idx in range(visible_start, visible_end):
                i = idx - visible_start
                music_file = self.match_music_opts[idx]
                item_rect = pygame.Rect(
                    self.match_music_list_rect.x + 3,
                    self.match_music_list_rect.y + 3 + i * dropdown_height,
                    item_area_width,
                    dropdown_height - 2
                )
                self.match_music_item_rects.append((item_rect, idx))
                
                is_selected = idx == self.match_music_idx
                is_hovered_item = item_rect.collidepoint(mouse_pos)
                
                # Item background
                if is_selected:
                    # Selected item với gradient
                    item_bg = pygame.Surface((item_rect.width, item_rect.height), pygame.SRCALPHA)
                    for y in range(item_rect.height):
                        factor = 1.0 - (y / item_rect.height) * 0.3
                        alpha = int(255 * factor)
                        color = (int(70 * factor), int(130 * factor), int(200 * factor), alpha)
                        pygame.draw.line(item_bg, color, (0, y), (item_rect.width, y))
                    surface.blit(item_bg, item_rect, special_flags=pygame.BLEND_ALPHA_SDL2)
                    pygame.draw.rect(surface, (100, 160, 230), item_rect, 2, border_radius=8)
                elif is_hovered_item:
                    pygame.draw.rect(surface, (60, 60, 75), item_rect, border_radius=8)
                    pygame.draw.rect(surface, (80, 80, 95), item_rect, 1, border_radius=8)
                
                # Item text với better styling
                item_name = music_file.replace(".mp3", "").replace(".ogg", "").replace(".wav", "").strip()
                text_color = (255, 255, 255) if is_selected else (220, 220, 230)
                item_text = self.small_font.render(item_name, True, text_color)
                # Text shadow cho selected item
                if is_selected:
                    shadow_item_text = self.small_font.render(item_name, True, (0, 0, 0))
                    surface.blit(shadow_item_text, (item_rect.x + 13, item_rect.centery - item_text.get_height() // 2 + 1))
                surface.blit(item_text, (item_rect.x + 12, item_rect.centery - item_text.get_height() // 2))
            
            # Scrollbar (nếu cần) - Improved design với hover effects
            if total_items > max_visible_items:
                scrollbar_x = self.match_music_list_rect.right - scrollbar_width - 2
                scrollbar_y = self.match_music_list_rect.y + 2
                scrollbar_height = self.match_music_list_rect.height - 4
                self.match_music_scrollbar_rect = pygame.Rect(scrollbar_x, scrollbar_y, scrollbar_width, scrollbar_height)
                
                # Scrollbar track với gradient và shadow
                track_shadow = self.match_music_scrollbar_rect.copy()
                track_shadow.x += 1
                track_shadow.y += 1
                shadow_surf = pygame.Surface((scrollbar_width, scrollbar_height), pygame.SRCALPHA)
                shadow_surf.fill((0, 0, 0, 100))
                surface.blit(shadow_surf, track_shadow, special_flags=pygame.BLEND_ALPHA_SDL2)
                
                # Track background với gradient
                track_bg = pygame.Surface((scrollbar_width, scrollbar_height), pygame.SRCALPHA)
                for y in range(scrollbar_height):
                    factor = 1.0 - (y / scrollbar_height) * 0.2
                    alpha = int(200 * factor)
                    color = (int(40 * factor), int(40 * factor), int(50 * factor), alpha)
                    pygame.draw.line(track_bg, color, (0, y), (scrollbar_width, y))
                surface.blit(track_bg, self.match_music_scrollbar_rect, special_flags=pygame.BLEND_ALPHA_SDL2)
                pygame.draw.rect(surface, (60, 60, 75), self.match_music_scrollbar_rect, border_radius=4)
                # Inner border
                inner_track = pygame.Rect(scrollbar_x + 1, scrollbar_y + 1, scrollbar_width - 2, scrollbar_height - 2)
                pygame.draw.rect(surface, (35, 35, 45), inner_track, border_radius=3)
                
                # Scrollbar thumb với hover effect
                thumb_height = max(24, int(scrollbar_height * max_visible_items / total_items))
                thumb_y_range = scrollbar_height - thumb_height
                thumb_y = scrollbar_y + int(thumb_y_range * (self.match_music_scroll_offset / max_scroll)) if max_scroll > 0 else scrollbar_y
                self.match_music_scrollbar_thumb_rect = pygame.Rect(scrollbar_x, thumb_y, scrollbar_width, thumb_height)
                
                # Check hover state
                mouse_pos = pygame.mouse.get_pos()
                is_thumb_hovered = self.match_music_scrollbar_thumb_rect.collidepoint(mouse_pos)
                is_track_hovered = self.match_music_scrollbar_rect.collidepoint(mouse_pos)
                is_dragging = self.match_music_scroll_dragging
                
                # Thumb shadow
                thumb_shadow = self.match_music_scrollbar_thumb_rect.copy()
                thumb_shadow.x += 1
                thumb_shadow.y += 1
                thumb_shadow_surf = pygame.Surface((scrollbar_width, thumb_height), pygame.SRCALPHA)
                thumb_shadow_surf.fill((0, 0, 0, 120 if (is_thumb_hovered or is_dragging) else 80))
                surface.blit(thumb_shadow_surf, thumb_shadow, special_flags=pygame.BLEND_ALPHA_SDL2)
                
                # Thumb background với gradient
                thumb_bg = pygame.Surface((scrollbar_width, thumb_height), pygame.SRCALPHA)
                if is_thumb_hovered or is_dragging:
                    # Hover/drag state - sáng hơn
                    for y in range(thumb_height):
                        factor = 1.0 - (y / thumb_height) * 0.3
                        alpha = int(255 * factor)
                        color = (int(120 * factor), int(170 * factor), int(250 * factor), alpha)
                        pygame.draw.line(thumb_bg, color, (0, y), (scrollbar_width, y))
                else:
                    # Normal state
                    for y in range(thumb_height):
                        factor = 1.0 - (y / thumb_height) * 0.2
                        alpha = int(255 * factor)
                        color = (int(100 * factor), int(150 * factor), int(220 * factor), alpha)
                        pygame.draw.line(thumb_bg, color, (0, y), (scrollbar_width, y))
                surface.blit(thumb_bg, self.match_music_scrollbar_thumb_rect, special_flags=pygame.BLEND_ALPHA_SDL2)
                
                # Thumb border
                border_color = (140, 190, 255) if (is_thumb_hovered or is_dragging) else (120, 170, 240)
                border_width = 2 if (is_thumb_hovered or is_dragging) else 1
                pygame.draw.rect(surface, border_color, self.match_music_scrollbar_thumb_rect, border_width, border_radius=4)
                
                # Thumb highlight (top)
                if thumb_height > 4:
                    highlight_rect = pygame.Rect(scrollbar_x, thumb_y, scrollbar_width, max(2, thumb_height // 4))
                    highlight_color = (180, 220, 255) if (is_thumb_hovered or is_dragging) else (150, 200, 255)
                    pygame.draw.rect(surface, highlight_color, highlight_rect, border_radius=4)
            else:
                self.match_music_scrollbar_rect = pygame.Rect(0, 0, 0, 0)
                self.match_music_scrollbar_thumb_rect = pygame.Rect(0, 0, 0, 0)
        else:
            self.match_music_list_rect = pygame.Rect(0, 0, 0, 0)
            self.match_music_item_rects = []
            self.match_music_scrollbar_rect = pygame.Rect(0, 0, 0, 0)
            self.match_music_scrollbar_thumb_rect = pygame.Rect(0, 0, 0, 0)
        
        # Choose Avatars - Đặt sau phần Music Selection
        # Lấy vị trí y thấp nhất giữa 2 dropdowns (bao gồm cả list nếu mở)
        max_dropdown_bottom = max(
            menu_dropdown_y + dropdown_height,
            match_dropdown_y + dropdown_height
        )
        if self.menu_music_dropdown_open and hasattr(self, 'menu_music_list_rect'):
            max_dropdown_bottom = max(max_dropdown_bottom, self.menu_music_list_rect.bottom)
        if self.match_music_dropdown_open and hasattr(self, 'match_music_list_rect'):
            max_dropdown_bottom = max(max_dropdown_bottom, self.match_music_list_rect.bottom)
        current_y = max_dropdown_bottom + spacing * 1.2
        
        avatar_label = self.small_font.render("Choose Avatars:", True, (220, 230, 240))
        surface.blit(avatar_label, (left_col.x + spacing, current_y))
        current_y += avatar_label.get_height() + spacing // 3
        
        # Avatar previews - Kích thước vừa phải để cân đối
        # Tính toán lại vị trí avatar
        avatar_size = min(
            (left_col.width - spacing * 3) // 2,  # Chia đều cho 2 avatars
            self.layout.scale(100)  # Tối ưu: 100px để vừa khung
        )
        avatar_spacing = spacing
        
        # Tính toán vị trí để căn giữa 2 avatars
        total_width = avatar_size * 2 + avatar_spacing
        start_x = left_col.x + (left_col.width - total_width) // 2
        
        human_avatar_rect = pygame.Rect(start_x, current_y, avatar_size, avatar_size)
        ai_avatar_rect = pygame.Rect(start_x + avatar_size + avatar_spacing, current_y, avatar_size, avatar_size)
        self.avatar_preview_rects = (human_avatar_rect, ai_avatar_rect)
        
        # 绘制头像预览框 - Thiết kế lại với hover effect
        mouse_pos = pygame.mouse.get_pos()
        for i, rect in enumerate([human_avatar_rect, ai_avatar_rect]):
            is_hovered = rect.collidepoint(mouse_pos)
            
            # Shadow - Tăng shadow khi hover
            shadow_rect = rect.copy()
            shadow_rect.x += 2
            shadow_rect.y += 2
            shadow_alpha = 120 if is_hovered else 90
            shadow_surf = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
            shadow_surf.fill((0, 0, 0, shadow_alpha))
            surface.blit(shadow_surf, shadow_rect, special_flags=pygame.BLEND_ALPHA_SDL2)
            
            # Glow effect khi hover
            if is_hovered:
                glow_surf = pygame.Surface((rect.width + 8, rect.height + 8), pygame.SRCALPHA)
                glow_rect = pygame.Rect(4, 4, rect.width, rect.height)
                border_color = (110, 160, 220) if i == 0 else (180, 120, 220)
                glow_color = (*border_color[:3], 80)
                pygame.draw.rect(glow_surf, glow_color, glow_rect, border_radius=12)
                surface.blit(glow_surf, (rect.x - 4, rect.y - 4), special_flags=pygame.BLEND_ALPHA_SDL2)
            
            # 主框架 - Sáng hơn khi hover
            bg_color = (45, 45, 55) if is_hovered else (38, 38, 46)
            pygame.draw.rect(surface, bg_color, rect, border_radius=10)
            
            # 外边框 - Đậm hơn khi hover
            border_color = (110, 160, 220) if i == 0 else (180, 120, 220)
            border_width = 3 if is_hovered else 2
            border_color_hover = (130, 180, 250) if i == 0 else (200, 140, 250)
            final_border_color = border_color_hover if is_hovered else border_color
            pygame.draw.rect(surface, final_border_color, rect, border_width, border_radius=10)
            
            # Inner highlight - Sáng hơn khi hover
            inner_rect = pygame.Rect(rect.x + 1, rect.y + 1, rect.width - 2, rect.height // 3)
            inner_color = (60, 60, 72) if is_hovered else (52, 52, 62)
            pygame.draw.rect(surface, inner_color, inner_rect, border_radius=10)
        
        # 绘制头像 - 带圆角裁剪
        human_avatar = self.assets.get_avatar(os.path.basename(self.human.avatar_path or "human_male.png"))
        ai_avatar = self.assets.get_avatar(os.path.basename(self.ai.avatar_path or "ai_bot.png"))
        
        # 创建圆角遮罩
        def create_rounded_surface(size, radius):
            surf = pygame.Surface(size, pygame.SRCALPHA)
            pygame.draw.rect(surf, (255, 255, 255), (0, 0, *size), border_radius=radius)
            return surf
        
        # 缩放并应用圆角
        avatar_size_scaled = (human_avatar_rect.width - 6, human_avatar_rect.height - 6)
        human_avatar_scaled = pygame.transform.scale(human_avatar, avatar_size_scaled)
        ai_avatar_scaled = pygame.transform.scale(ai_avatar, avatar_size_scaled)
        
        # 使用遮罩创建圆角效果
        mask = create_rounded_surface(avatar_size_scaled, 10)
        human_avatar_scaled.set_colorkey((0, 0, 0))
        ai_avatar_scaled.set_colorkey((0, 0, 0))
        
        surface.blit(human_avatar_scaled, (human_avatar_rect.x + 3, human_avatar_rect.y + 3))
        surface.blit(ai_avatar_scaled, (ai_avatar_rect.x + 3, ai_avatar_rect.y + 3))
        
        # 头像标签 - 改进的样式 - Hiển thị dựa trên mode với click hint
        is_pvp = self.mode_opts[self.mode_idx] == "PvP"
        human_label = self.small_font.render("Human", True, (200, 200, 210))
        second_label_text = "Human" if is_pvp else "AI"
        second_label = self.small_font.render(second_label_text, True, (200, 200, 210))
        surface.blit(human_label, (human_avatar_rect.centerx - human_label.get_width() // 2, human_avatar_rect.bottom + spacing // 3))
        surface.blit(second_label, (ai_avatar_rect.centerx - second_label.get_width() // 2, ai_avatar_rect.bottom + spacing // 3))
        
        # Click hint - Hiển thị khi hover
        if human_avatar_rect.collidepoint(mouse_pos):
            hint_text = self.small_font.render("Click to choose", True, (150, 200, 255))
            hint_bg = pygame.Rect(
                human_avatar_rect.centerx - hint_text.get_width() // 2 - 6,
                human_avatar_rect.y - hint_text.get_height() - 8,
                hint_text.get_width() + 12,
                hint_text.get_height() + 6
            )
            # Hint background với shadow
            hint_shadow = hint_bg.copy()
            hint_shadow.x += 1
            hint_shadow.y += 1
            shadow_surf = pygame.Surface((hint_bg.width, hint_bg.height), pygame.SRCALPHA)
            shadow_surf.fill((0, 0, 0, 150))
            surface.blit(shadow_surf, hint_shadow, special_flags=pygame.BLEND_ALPHA_SDL2)
            # Hint background
            hint_bg_surf = pygame.Surface((hint_bg.width, hint_bg.height), pygame.SRCALPHA)
            hint_bg_surf.fill((30, 35, 45, 240))
            surface.blit(hint_bg_surf, hint_bg, special_flags=pygame.BLEND_ALPHA_SDL2)
            pygame.draw.rect(surface, (110, 160, 220), hint_bg, 1, border_radius=4)
            surface.blit(hint_text, (hint_bg.centerx - hint_text.get_width() // 2, hint_bg.centery - hint_text.get_height() // 2))
        elif ai_avatar_rect.collidepoint(mouse_pos):
            hint_text = self.small_font.render("Click to cycle", True, (200, 150, 255))
            hint_bg = pygame.Rect(
                ai_avatar_rect.centerx - hint_text.get_width() // 2 - 6,
                ai_avatar_rect.y - hint_text.get_height() - 8,
                hint_text.get_width() + 12,
                hint_text.get_height() + 6
            )
            # Hint background với shadow
            hint_shadow = hint_bg.copy()
            hint_shadow.x += 1
            hint_shadow.y += 1
            shadow_surf = pygame.Surface((hint_bg.width, hint_bg.height), pygame.SRCALPHA)
            shadow_surf.fill((0, 0, 0, 150))
            surface.blit(shadow_surf, hint_shadow, special_flags=pygame.BLEND_ALPHA_SDL2)
            # Hint background
            hint_bg_surf = pygame.Surface((hint_bg.width, hint_bg.height), pygame.SRCALPHA)
            hint_bg_surf.fill((30, 35, 45, 240))
            surface.blit(hint_bg_surf, hint_bg, special_flags=pygame.BLEND_ALPHA_SDL2)
            pygame.draw.rect(surface, (180, 120, 220), hint_bg, 1, border_radius=4)
            surface.blit(hint_text, (hint_bg.centerx - hint_text.get_width() // 2, hint_bg.centery - hint_text.get_height() // 2))
        
        # ========== 右列内容 - Game Configuration với Panel Container ==========
        right_y = underline_y + spacing * 1.5  # Tối ưu: spacing hợp lý để vừa khung
        
        # Panel container cho cột phải với background semi-transparent
        right_panel_rect = pygame.Rect(
            right_col.x + spacing // 2,
            right_y - spacing // 2,
            right_col.width - spacing,
            container.bottom - right_y - margin * 2
        )
        # Panel shadow với depth
        panel_shadow_right = right_panel_rect.copy()
        panel_shadow_right.x += 4
        panel_shadow_right.y += 4
        shadow_surf = pygame.Surface((right_panel_rect.width, right_panel_rect.height), pygame.SRCALPHA)
        shadow_surf.fill((0, 0, 0, 100))
        surface.blit(shadow_surf, panel_shadow_right, special_flags=pygame.BLEND_ALPHA_SDL2)
        
        # Panel background với red gradient accents - Tối ưu với cache
        panel_bg_right = self._get_cached_gradient(
            right_panel_rect.width, 
            right_panel_rect.height, 
            (30, 20, 25, 200), 
            factor=0.2
        )
        surface.blit(panel_bg_right, right_panel_rect, special_flags=pygame.BLEND_ALPHA_SDL2)
        
        # Panel border với red accent và highlight
        pygame.draw.rect(surface, (100, 50, 50), right_panel_rect, 2, border_radius=12)
        # Top highlight
        top_highlight_right = pygame.Rect(right_panel_rect.x, right_panel_rect.y, right_panel_rect.width, 2)
        pygame.draw.rect(surface, (150, 80, 80), top_highlight_right, border_radius=12)
        # Inner glow với gradient
        inner_glow_right = pygame.Rect(right_panel_rect.x + 1, right_panel_rect.y + 1, right_panel_rect.width - 2, right_panel_rect.height - 2)
        pygame.draw.rect(surface, (50, 30, 35), inner_glow_right, 1, border_radius=11)
        
        # Section header với styling đẹp hơn - Tối ưu với cache
        section_title_right = self._get_cached_text("Game Configuration", self.text_font, (255, 220, 180))
        title_bg_rect_right = pygame.Rect(
            right_col.x + spacing,
            right_y - 4,
            section_title_right.get_width() + spacing,
            section_title_right.get_height() + 8
        )
        # Header background với gradient
        header_bg_right = pygame.Surface((title_bg_rect_right.width, title_bg_rect_right.height), pygame.SRCALPHA)
        header_bg_right.fill((60, 30, 20, 180))  # Dark red-orange
        surface.blit(header_bg_right, title_bg_rect_right, special_flags=pygame.BLEND_ALPHA_SDL2)
        pygame.draw.rect(surface, (150, 100, 60), title_bg_rect_right, 1, border_radius=6)
        surface.blit(section_title_right, (right_col.x + spacing + spacing // 2, right_y))
        
        # Vẽ line dưới tiêu đề với gradient effect
        section_line_right = pygame.Rect(right_col.x + spacing, right_y + section_title_right.get_height() + 8, right_col.width - spacing * 2, 2)
        pygame.draw.rect(surface, (120, 80, 60), section_line_right, border_radius=1)
        # Highlight trên line
        highlight_line_right = pygame.Rect(section_line_right.x, section_line_right.y, section_line_right.width, 1)
        pygame.draw.rect(surface, (180, 120, 80), highlight_line_right, border_radius=1)
        right_y += section_title_right.get_height() + spacing * 1.2  # Tối ưu: spacing hợp lý
        
        # Option rows - Kích thước và spacing tối ưu
        row_spacing = self.layout.scale(50)  # Tăng spacing lên 50px để các button cách xa nhau hơn
        option_rows = [
            ("Mode", f"{self.mode_opts[self.mode_idx]}"),
            ("Side to start", f"{self.side_opts[self.side_idx]}"),
            ("Swap sides", "✓" if self.swap_sides else "○"),
        ]
        
        # Tính toán chiều rộng và vị trí option rows để không tràn
        row_width = right_col.width - spacing * 2
        row_height = self.layout.scale(44)  # Tối ưu: 44px để vừa khung
        
        self.option_row_rects = []
        for i, (label, value) in enumerate(option_rows):
            row_y = right_y + i * row_spacing
            row_rect = pygame.Rect(right_col.x + spacing, row_y, row_width, row_height)
            self.option_row_rects.append((row_rect, label, value))
            
            # 选项行 - 更现代的设计 (thiết kế lại đẹp hơn)
            # Shadow
            row_shadow = row_rect.copy()
            row_shadow.x += 1
            row_shadow.y += 1
            shadow_surf = pygame.Surface((row_rect.width, row_rect.height), pygame.SRCALPHA)
            shadow_surf.fill((0, 0, 0, 50))
            surface.blit(shadow_surf, row_shadow, special_flags=pygame.BLEND_ALPHA_SDL2)
            pygame.draw.rect(surface, (43, 43, 50), row_rect, border_radius=10)
            # 内高光
            inner_rect = pygame.Rect(row_rect.x + 1, row_rect.y + 1, row_rect.width - 2, row_rect.height // 3)
            pygame.draw.rect(surface, (58, 58, 66), inner_rect, border_radius=10)
            # 边框
            pygame.draw.rect(surface, (80, 80, 90), row_rect, 1, border_radius=10)
            
            # 文本 - 标签和值分开显示
            label_text = self.small_font.render(f"{label}:", True, (180, 180, 190))
            value_text = self.small_font.render(str(value), True, (255, 255, 255))
            surface.blit(label_text, (row_rect.x + 12, row_rect.y + (row_rect.height - label_text.get_height()) // 2))
            surface.blit(value_text, (row_rect.right - value_text.get_width() - 12, row_rect.y + (row_rect.height - value_text.get_height()) // 2))
        
        # AI Difficulty section - 改进的难度选择器 (loại bỏ emoji)
        if self.mode_opts[self.mode_idx] == "PvAI":
            diff_section_y = right_y + len(option_rows) * row_spacing + spacing * 0.8  # Di chuyển lên một chút
            diff_label = self.small_font.render("AI Difficulty:", True, (220, 220, 230))
            surface.blit(diff_label, (right_col.x + spacing, diff_section_y))
            
            # Tính toán difficulty buttons - Kích thước tối ưu
            btn_spacing_h = spacing // 2
            total_btn_spacing = btn_spacing_h * 2  # 2 khoảng cách giữa 3 buttons
            available_width = right_col.width - spacing * 2
            diff_btn_width = (available_width - total_btn_spacing) // 3
            diff_btn_height = self.layout.scale(44)  # Tối ưu: 44px để vừa khung
            
            self.difficulty_button_rects = []
            difficulty_configs = {
                "easy": {"color": (39, 174, 96), "name": "Easy"},
                "medium": {"color": (243, 156, 18), "name": "Medium"},
                "hard": {"color": (231, 76, 60), "name": "Hard"},
            }
            
            # Tạo và căn chỉnh đều các difficulty buttons
            btn_y = diff_section_y + diff_label.get_height() + spacing // 2
            x_start = right_col.x + spacing
            for i in range(len(self.ai_diff_opts)):
                btn_x = x_start + i * (diff_btn_width + btn_spacing_h)
                btn_rect = pygame.Rect(btn_x, btn_y, diff_btn_width, diff_btn_height)
                self.difficulty_button_rects.append(btn_rect)
            
            for i, (diff_key, btn_rect) in enumerate(zip(self.ai_diff_opts, self.difficulty_button_rects)):
                config = difficulty_configs.get(diff_key, difficulty_configs["medium"])
                is_selected = self.ai_diff_idx == i
                
                # 按钮设计 - Orange cho Medium (thiết kế lại)
                if is_selected:
                    bg_color = config["color"]
                    # Orange cho Medium difficulty
                    if diff_key == "medium":
                        bg_color = (255, 165, 0)  # Orange
                    # 阴影 - sử dụng cache
                    shadow_rect = btn_rect.copy()
                    shadow_rect.x += 2
                    shadow_rect.y += 2
                    shadow_surf = self._get_cached_shadow(btn_rect.width, btn_rect.height, 110)
                    surface.blit(shadow_surf, shadow_rect, special_flags=pygame.BLEND_ALPHA_SDL2)
                    # 背景
                    pygame.draw.rect(surface, bg_color, btn_rect, border_radius=10)
                    # 顶部高光
                    highlight = pygame.Rect(btn_rect.x + 1, btn_rect.y + 1, btn_rect.width - 2, btn_rect.height // 3)
                    highlight_color = tuple(min(255, c + 40) for c in bg_color[:3])
                    pygame.draw.rect(surface, highlight_color, highlight, border_radius=10)
                    # 白色边框
                    pygame.draw.rect(surface, (255, 255, 255), btn_rect, 2, border_radius=10)
                else:
                    # 未选中状态
                    pygame.draw.rect(surface, (50, 50, 56), btn_rect, border_radius=10)
                    pygame.draw.rect(surface, (85, 85, 95), btn_rect, 1, border_radius=10)
                
                # Chỉ hiển thị text, bỏ icon emoji
                name_text = self.small_font.render(config['name'], True, (255, 255, 255) if is_selected else (180, 180, 190))
                name_rect = name_text.get_rect(center=btn_rect.center)
                surface.blit(name_text, name_rect)
        
        # Piece Skin selection - đặt ngay dưới các option và khó khăn AI
        if self.mode_opts[self.mode_idx] == "PvAI":
            base_y = diff_section_y + diff_btn_height + spacing * 1.5  # Tối ưu: spacing hợp lý
        else:
            base_y = right_y + len(option_rows) * row_spacing + spacing * 1.2  # Tối ưu: spacing hợp lý
        skin_section_y = base_y
        
        skin_label = self.small_font.render("Piece Skin:", True, self.config.colors["text"])
        surface.blit(skin_label, (right_col.x + spacing, skin_section_y))
        
        # Tính toán piece skin buttons - Kích thước tối ưu
        skin_btn_spacing = spacing // 2
        num_skins = len(self.piece_skin_opts)
        total_skin_spacing = skin_btn_spacing * (num_skins - 1)
        available_width = right_col.width - spacing * 2
        skin_btn_width = (available_width - total_skin_spacing) // num_skins
        skin_btn_height = self.layout.scale(44)  # Tối ưu: 44px để vừa khung
        
        self.piece_skin_button_rects = []
        skin_configs = {
            "classic": {"name": "Classic"},
            "dark fantasy": {"name": "Dark Fantasy"},
        }
        
        # Tạo và căn chỉnh đều các piece skin buttons
        skin_btn_y = skin_section_y + skin_label.get_height() + spacing // 3
        x_start = right_col.x + spacing
        for i in range(num_skins):
            skin_btn_x = x_start + i * (skin_btn_width + skin_btn_spacing)
            btn_rect = pygame.Rect(skin_btn_x, skin_btn_y, skin_btn_width, skin_btn_height)
            self.piece_skin_button_rects.append(btn_rect)
        
        for i, (skin_key, btn_rect) in enumerate(zip(self.piece_skin_opts, self.piece_skin_button_rects)):
            config = skin_configs.get(skin_key, skin_configs["classic"])
            is_selected = self.piece_skin_idx == i
            
            # Piece skin button - Blue cho selections (thiết kế lại)
            if is_selected:
                bg_color = (70, 130, 200)  # Blue cho selections
                # Shadow - sử dụng cache
                shadow_rect = btn_rect.copy()
                shadow_rect.x += 2
                shadow_rect.y += 2
                shadow_surf = self._get_cached_shadow(btn_rect.width, btn_rect.height, 100)
                surface.blit(shadow_surf, shadow_rect, special_flags=pygame.BLEND_ALPHA_SDL2)
                pygame.draw.rect(surface, bg_color, btn_rect, border_radius=10)
                # Top highlight
                highlight = pygame.Rect(btn_rect.x + 1, btn_rect.y + 1, btn_rect.width - 2, btn_rect.height // 2)
                highlight_color = (100, 160, 230)
                pygame.draw.rect(surface, highlight_color, highlight, border_radius=10)
                pygame.draw.rect(surface, (255, 255, 255), btn_rect, 2, border_radius=10)
            else:
                pygame.draw.rect(surface, (50, 50, 56), btn_rect, border_radius=10)
                pygame.draw.rect(surface, (88, 88, 98), btn_rect, 1, border_radius=10)
            
            # 显示皮肤名称
            name_text = self.small_font.render(config['name'], True, (255, 255, 255) if is_selected else (200, 200, 200))
            name_rect = name_text.get_rect(center=btn_rect.center)
            surface.blit(name_text, name_rect)
        
        # ========== Sliders - Di chuyển sang cột phải với improved styling ==========
        # Tính toán vị trí bắt đầu cho sliders ở cột phải
        slider_section_y = skin_btn_y + skin_btn_height + spacing * 1.2
        
        # Section header cho sliders
        slider_header = self.small_font.render("Advanced Settings", True, (255, 220, 180))  # Gold color
        header_bg_rect = pygame.Rect(
            right_col.x + spacing,
            slider_section_y - 6,
            slider_header.get_width() + spacing,
            slider_header.get_height() + 8
        )
        # Header background với gradient
        header_bg = pygame.Surface((header_bg_rect.width, header_bg_rect.height), pygame.SRCALPHA)
        header_bg.fill((60, 30, 20, 180))  # Dark red-orange
        surface.blit(header_bg, header_bg_rect, special_flags=pygame.BLEND_ALPHA_SDL2)
        pygame.draw.rect(surface, (150, 100, 60), header_bg_rect, 1, border_radius=6)
        surface.blit(slider_header, (right_col.x + spacing + spacing // 2, slider_section_y))
        
        # Line dưới header
        slider_line = pygame.Rect(right_col.x + spacing, slider_section_y + slider_header.get_height() + 6, right_col.width - spacing * 2, 2)
        pygame.draw.rect(surface, (120, 80, 60), slider_line, border_radius=1)
        highlight_line = pygame.Rect(slider_line.x, slider_line.y, slider_line.width, 1)
        pygame.draw.rect(surface, (180, 120, 80), highlight_line, border_radius=1)
        
        slider_section_y += slider_header.get_height() + spacing * 0.8
        
        slider_labels = ["Move time (s)", "Max undos", "Max hints", "Hint depth"]
        slider_keys = ["move_time", "undo", "hint", "depth"]
        slider_values = [self.move_time_limit, self.max_undo, self.max_hint, self.hint_depth]
        # Chỉnh 3 slider cuối (Max undos, Max hints, Hint depth) cho cùng range (0, 10)
        slider_ranges = [(5, 300), (0, 10), (0, 10), (0, 10)]
        
        slider_spacing = self.layout.scale(36)  # Tăng spacing để đẹp hơn
        
        # Tính toán chiều rộng slider cho cột phải
        slider_width = right_col.width - spacing * 2 - self.layout.scale(50)  # Để chỗ cho value label
        
        # Tính toán vị trí slider cuối cùng để đảm bảo spacing với button
        last_slider_bottom = 0
        for i, (label_text, key, value, (vmin, vmax)) in enumerate(zip(slider_labels, slider_keys, slider_values, slider_ranges)):
            y_pos = slider_section_y + i * slider_spacing
                
            # Label với improved styling
            label = self.small_font.render(label_text, True, (240, 240, 250))  # Sáng hơn
            # Label shadow
            label_shadow = self.small_font.render(label_text, True, (0, 0, 0))
            surface.blit(label_shadow, (right_col.x + spacing + 1, y_pos + 1))
            surface.blit(label, (right_col.x + spacing, y_pos))
            
            # Tạo slider track với chiều rộng đã tính toán và height lớn hơn một chút
            track_y = y_pos + label.get_height() + 6
            track = pygame.Rect(right_col.x + spacing, track_y, slider_width, self.layout.scale(10))  # Tăng height
            self.slider_tracks[key] = track
            
            # Tính toán bottom của slider (bao gồm knob có thể mở rộng ra ngoài track)
            # Knob có thể cao hơn track, ước tính khoảng 16px (8px mỗi bên trên/dưới track)
            knob_extension = 8  # Knob có thể mở rộng 8px ra ngoài track
            slider_bottom = track.bottom + knob_extension
            last_slider_bottom = max(last_slider_bottom, slider_bottom)
            
            # 绘制滑块
            self._render_slider(surface, key, int(value), vmin, vmax)

        # Start button - PLAY GAME với glow effect (gold/orange cho primary action)
        # Điều chỉnh vị trí để đảm bảo có đủ spacing với slider cuối cùng
        base_rect = self.layout.get_start_button_rect(container)
        
        # Tính toán spacing tối thiểu giữa slider cuối và button
        # Tăng spacing để tránh đè lên nhau, đặc biệt là phần decorative element của button
        min_spacing = self.layout.scale(60)  # Tăng lên 60px để đảm bảo không đè
        slider_to_button_gap = base_rect.top - last_slider_bottom
        
        # Nếu spacing quá nhỏ, điều chỉnh vị trí button xuống dưới
        if slider_to_button_gap < min_spacing:
            adjustment = min_spacing - slider_to_button_gap
            base_rect = base_rect.move(0, adjustment)
        if self.play_img_raw is not None:
            # Áp dụng kích thước cố định từ CSS: 450x180px
            target_width = 450
            target_height = 180
            
            iw, ih = self.play_img_raw.get_size()
            screen_w, screen_h = surface.get_size()
            
            # Tính scale để đạt kích thước target, giữ tỷ lệ
            scale_w = target_width / max(1, iw)
            scale_h = target_height / max(1, ih)
            scale = min(scale_w, scale_h)  # Giữ tỷ lệ, lấy scale nhỏ hơn
            
            draw_w = int(iw * scale)
            draw_h = int(ih * scale)
            
            # Không kiểm tra hover - ẩn hover effect
            img = pygame.transform.smoothscale(self.play_img_raw, (draw_w, draw_h))
            # Di chuyển xuống thêm 5% - từ 1% xuống -4% (button sẽ xuống thấp hơn)
            bottom_margin = int(screen_h * -0.04)  # -4% để button xuống thấp hơn (1% - 5% = -4%)
            img_rect = img.get_rect(centerx=base_rect.centerx, bottom=screen_h - bottom_margin)
            
            # Không có hover effect và không vẽ shadow
            # Vẽ button trực tiếp không có shadow
            surface.blit(img, img_rect)
            # Thu nhỏ vùng chọn - chỉ 70% kích thước, căn giữa (nhỏ hơn để tránh conflict với slider)
            clickable_width = int(draw_w * 0.7)
            clickable_height = int(draw_h * 0.7)
            clickable_x = img_rect.centerx - clickable_width // 2
            clickable_y = img_rect.centery - clickable_height // 2
            self.btn_start = pygame.Rect(clickable_x, clickable_y, clickable_width, clickable_height)
            # Vùng lớn hơn chỉ mở rộng một chút (10px mỗi bên) để tránh conflict với slider
            self.btn_start_full_area = self.btn_start.inflate(10, 10)
            surface.blit(img, img_rect)
        else:
            # Styled button với gold/orange và glow effect
            # Thu nhỏ vùng chọn hiển thị - chỉ 70% kích thước, căn giữa (nhỏ hơn để tránh conflict với slider)
            clickable_width = int(base_rect.width * 0.7)
            clickable_height = int(base_rect.height * 0.7)
            clickable_x = base_rect.centerx - clickable_width // 2
            clickable_y = base_rect.centery - clickable_height // 2
            self.btn_start = pygame.Rect(clickable_x, clickable_y, clickable_width, clickable_height)
            # Vùng lớn hơn chỉ mở rộng một chút (10px mỗi bên) để tránh conflict với slider
            # Không mở rộng lên trên để tránh conflict với slider hint
            self.btn_start_full_area = self.btn_start.inflate(10, 5)  # 10px ngang, 5px dọc (chỉ xuống dưới)
            # Gold/orange color cho primary action
            primary_color = (255, 180, 60)  # Gold/Orange
            primary_dark = (200, 140, 40)
            
            # Outer glow effect (multiple layers)
            for i in range(3, 0, -1):
                glow_rect = base_rect.inflate(i * 8, i * 8)
                glow_surf = pygame.Surface((glow_rect.width, glow_rect.height), pygame.SRCALPHA)
                glow_alpha = 20 * i
                glow_color = (*primary_color[:3], glow_alpha)
                try:
                    pygame.draw.rect(glow_surf, glow_color, (0, 0, glow_rect.width, glow_rect.height), border_radius=16 + i)
                except TypeError:
                    pygame.draw.rect(glow_surf, primary_color, (0, 0, glow_rect.width, glow_rect.height), border_radius=16 + i)
                surface.blit(glow_surf, glow_rect, special_flags=pygame.BLEND_ALPHA_SDL2)
            
            # Shadow
            shadow_rect = self.btn_start.copy()
            shadow_rect.x += 6
            shadow_rect.y += 6
            shadow_surf = pygame.Surface((self.btn_start.width, self.btn_start.height), pygame.SRCALPHA)
            shadow_surf.fill((0, 0, 0, 180))
            surface.blit(shadow_surf, shadow_rect, special_flags=pygame.BLEND_ALPHA_SDL2)
            
            # Main button background với gradient
            pygame.draw.rect(surface, primary_color, self.btn_start, border_radius=14)
            # Top highlight
            highlight = pygame.Rect(self.btn_start.x + 2, self.btn_start.y + 2, self.btn_start.width - 4, self.btn_start.height // 2)
            highlight_color = (255, 220, 100)
            pygame.draw.rect(surface, highlight_color, highlight, border_radius=14)
            # Gold border
            pygame.draw.rect(surface, (255, 215, 0), self.btn_start, 3, border_radius=14)
            # Inner glow
            inner_glow = pygame.Rect(self.btn_start.x + 3, self.btn_start.y + 3, self.btn_start.width - 6, self.btn_start.height - 6)
            pygame.draw.rect(surface, (255, 200, 80), inner_glow, 1, border_radius=11)
            
            # Text với shadow và glow
            start_text = self.text_font.render("PLAY GAME", True, (255, 255, 255))
            start_rect = start_text.get_rect(center=self.btn_start.center)
            # Text shadow
            start_shadow = self.text_font.render("PLAY GAME", True, (0, 0, 0))
            surface.blit(start_shadow, (start_rect.x + 3, start_rect.y + 3))
            # Text glow
            start_glow = self.text_font.render("PLAY GAME", True, (255, 240, 180))
            surface.blit(start_glow, (start_rect.x + 1, start_rect.y + 1))
            # Main text
            surface.blit(start_text, start_rect)
        
        # Validation message
        if self.validation_message:
            warn = self.small_font.render(self.validation_message, True, self.config.colors.get("danger", (220, 84, 84)))
            warn_y = self.btn_start.y - warn.get_height() - spacing
            surface.blit(warn, (container.centerx - warn.get_width() // 2, warn_y))
        
        # Volume control và Exit button ở góc trên bên phải - Vẽ cuối cùng để ở trên cùng (z-order cao nhất)
        # Đảm bảo không bị các phần tử khác đè lên
        self._render_volume_control(surface)
        
        # Vẽ ảnh Game Settings cuối cùng để đè lên trên cùng (z-order cao nhất)
        if self._gamestt_title_img is not None:
            # Vẽ ảnh ở vị trí Game Settings - đè lên tất cả các phần khác
            surface.blit(self._gamestt_title_img, (self._gamestt_title_x, self._gamestt_title_y))
    
    def _update_volume_from_mouse(self, mouse_x: int) -> None:
        """Cập nhật volume dựa trên vị trí chuột"""
        if self._volume_slider_track.width == 0:
            return
        
        track_x = self._volume_slider_track.x
        track_width = self._volume_slider_track.width
        relative_x = max(0, min(mouse_x - track_x, track_width))
        new_volume = relative_x / track_width
        self.volume = max(0.0, min(1.0, new_volume))
        
        try:
            pygame.mixer.music.set_volume(self.volume)
        except Exception:
            pass
    
    def _render_volume_control(self, surface: pygame.Surface) -> None:
        """Render volume control ở góc trên bên phải"""
        screen_w, screen_h = surface.get_size()
        margin = 20
        control_width = 180
        control_height = 40
        exit_spacing = 4
        
        # Exit button phía trên volume control - Vẽ trước, sát mép trên
        # Điều chỉnh để không bị cắt quá nhiều ở mép trên
        exit_y = max(0, -int(screen_h * 0.02))  # Tối đa lên trên 2% hoặc sát mép (0)
        exit_x = screen_w - control_width - margin
        
        if self._exit_img_raw is not None:
            # Tính toán kích thước để vừa với control_width
            iw, ih = self._exit_img_raw.get_size()
            # Scale để fit với control_width, giữ tỷ lệ
            target_width = min(control_width, 180)  # Max width 180px
            scale = target_width / max(1, iw)
            draw_w = int(iw * scale)
            draw_h = int(ih * scale)
            
            # Căn giữa theo control_x và control_width
            exit_x_centered = exit_x + (control_width - draw_w) // 2
            img = pygame.transform.smoothscale(self._exit_img_raw, (draw_w, draw_h))
            exit_rect = pygame.Rect(exit_x_centered, exit_y, draw_w, draw_h)
            # Thu nhỏ vùng chọn - chỉ 60% kích thước, căn giữa
            clickable_width = int(draw_w * 0.6)
            clickable_height = int(draw_h * 0.6)
            clickable_x = exit_x_centered + (draw_w - clickable_width) // 2
            clickable_y = exit_y + (draw_h - clickable_height) // 2
            self._exit_rect = pygame.Rect(clickable_x, clickable_y, clickable_width, clickable_height)
            
            # Ẩn hover effect - không vẽ glow khi hover
            # Không check hover và không vẽ glow effect
            
            surface.blit(img, exit_rect)
        else:
            # Fallback: text button nếu không có ảnh
            exit_width = control_width
            exit_height = 32
            exit_rect = pygame.Rect(exit_x, exit_y, exit_width, exit_height)
            # Thu nhỏ vùng chọn - chỉ 60% kích thước, căn giữa
            clickable_width = int(exit_width * 0.6)
            clickable_height = int(exit_height * 0.6)
            clickable_x = exit_x + (exit_width - clickable_width) // 2
            clickable_y = exit_y + (exit_height - clickable_height) // 2
            self._exit_rect = pygame.Rect(clickable_x, clickable_y, clickable_width, clickable_height)
            
            # Ẩn hover effect - không thay đổi màu khi hover
            # Background với dark red gradient accents (không đổi khi hover)
            exit_bg_alpha = 180
            exit_bg_surf = pygame.Surface((exit_width, exit_height), pygame.SRCALPHA)
            exit_bg_surf.fill((40, 25, 30, exit_bg_alpha))  # Dark red semi-transparent
            surface.blit(exit_bg_surf, exit_rect, special_flags=pygame.BLEND_ALPHA_SDL2)
            
            exit_border_color = (120, 70, 50)  # Gold/orange border (không đổi khi hover)
            pygame.draw.rect(surface, exit_border_color, exit_rect, 2, border_radius=8)
            
            # Exit text
            exit_text = self.small_font.render("Exit To Menu", True, (255, 240, 220))  # Light gold
            exit_text_rect = exit_text.get_rect(center=exit_rect.center)
            surface.blit(exit_text, exit_text_rect)
        
        # Volume control đặt phía dưới exit button
        exit_bottom = exit_y + (exit_rect.height if self._exit_img_raw is not None else exit_height)
        control_x = screen_w - control_width - margin
        control_y = exit_bottom + exit_spacing
        
        container_rect = pygame.Rect(control_x, control_y, control_width, control_height)
        self._volume_rect = container_rect
        
        mouse_pos = pygame.mouse.get_pos()
        is_hovered = container_rect.collidepoint(mouse_pos) or self._volume_dragging
        
        # Background với dark red gradient accents
        bg_alpha = 220 if is_hovered else 180
        bg_surf = pygame.Surface((control_width, control_height), pygame.SRCALPHA)
        bg_surf.fill((40, 25, 30, bg_alpha))  # Dark red semi-transparent
        surface.blit(bg_surf, container_rect, special_flags=pygame.BLEND_ALPHA_SDL2)
        
        border_color = (150, 100, 60) if is_hovered else (120, 70, 50)  # Gold/orange border
        pygame.draw.rect(surface, border_color, container_rect, 2, border_radius=10)
        
        # Icon loa
        icon_x = control_x + 10
        icon_y = control_y + control_height // 2
        
        if self.volume > 0:
            speaker_points = [
                (icon_x, icon_y - 6), (icon_x + 8, icon_y - 6),
                (icon_x + 14, icon_y - 12), (icon_x + 14, icon_y + 12),
                (icon_x + 8, icon_y + 6), (icon_x, icon_y + 6),
            ]
            pygame.draw.polygon(surface, (255, 255, 255), speaker_points)
            if self.volume > 0.3:
                pygame.draw.arc(surface, (255, 255, 255), 
                               pygame.Rect(icon_x + 12, icon_y - 8, 12, 16), -0.5, 0.5, 2)
            if self.volume > 0.6:
                pygame.draw.arc(surface, (255, 255, 255), 
                               pygame.Rect(icon_x + 16, icon_y - 10, 14, 20), -0.5, 0.5, 2)
        else:
            speaker_points = [
                (icon_x, icon_y - 6), (icon_x + 8, icon_y - 6),
                (icon_x + 14, icon_y - 12), (icon_x + 14, icon_y + 12),
                (icon_x + 8, icon_y + 6), (icon_x, icon_y + 6),
            ]
            pygame.draw.polygon(surface, (150, 150, 150), speaker_points)
            pygame.draw.line(surface, (255, 100, 100), 
                           (icon_x + 16, icon_y - 6), (icon_x + 24, icon_y + 6), 3)
            pygame.draw.line(surface, (255, 100, 100), 
                           (icon_x + 16, icon_y + 6), (icon_x + 24, icon_y - 6), 3)
        
        # Slider
        slider_x = icon_x + 35
        slider_y = control_y + control_height // 2
        slider_width = control_width - 60
        slider_height = 6
        
        track_rect = pygame.Rect(slider_x, slider_y - slider_height // 2, slider_width, slider_height)
        self._volume_slider_track = track_rect
        pygame.draw.rect(surface, (60, 60, 70), track_rect, border_radius=3)
        
        fill_width = int(slider_width * self.volume)
        if fill_width > 0:
            fill_rect = pygame.Rect(slider_x, slider_y - slider_height // 2, fill_width, slider_height)
            pygame.draw.rect(surface, (70, 140, 210), fill_rect, border_radius=3)
        
        knob_x = slider_x + int(slider_width * self.volume)
        knob_radius = 8 if is_hovered else 6
        knob_color = (90, 160, 230) if is_hovered else (70, 140, 210)
        pygame.draw.circle(surface, knob_color, (knob_x, slider_y), knob_radius)
        pygame.draw.circle(surface, (255, 255, 255), (knob_x, slider_y), knob_radius, 2)
        
        if is_hovered:
            vol_text = self.small_font.render(f"{int(self.volume * 100)}%", True, (255, 255, 255))
            text_rect = vol_text.get_rect(center=(control_x + control_width // 2, control_y - 12))
            text_bg = pygame.Rect(text_rect.x - 4, text_rect.y - 2, 
                                 text_rect.width + 8, text_rect.height + 4)
            bg_surf = pygame.Surface((text_bg.width, text_bg.height), pygame.SRCALPHA)
            bg_surf.fill((28, 32, 40, 200))
            surface.blit(bg_surf, text_bg, special_flags=pygame.BLEND_ALPHA_SDL2)
            pygame.draw.rect(surface, (70, 140, 210), text_bg, 1, border_radius=5)
            surface.blit(vol_text, text_rect)

    def _render_slider(self, surface: pygame.Surface, key: str, value: int, vmin: int, vmax: int) -> None:
        """渲染滑块 - Modern design với gradient và glow effects"""
        if key not in self.slider_tracks:
            return
        track = self.slider_tracks[key]
        mouse_pos = pygame.mouse.get_pos()
        is_hovered = track.collidepoint(mouse_pos) or (key == self.slider_dragging)
        
        # Track background với gradient effect
        # Outer shadow cho track
        track_shadow = track.copy()
        track_shadow.y += 2
        shadow_surf = pygame.Surface((track.width, track.height + 4), pygame.SRCALPHA)
        shadow_surf.fill((0, 0, 0, 80))
        surface.blit(shadow_surf, (track_shadow.x, track_shadow.y), special_flags=pygame.BLEND_ALPHA_SDL2)
        
        # Track background - Dark với subtle gradient - Tối ưu với cache
        # Tính toán gradient với alpha giảm dần
        track_bg = self._get_cached_gradient(
            track.width,
            track.height,
            (45, 45, 55, 200),
            factor=0.1  # Alpha giảm 10% từ trên xuống
        )
        surface.blit(track_bg, track, special_flags=pygame.BLEND_ALPHA_SDL2)
        pygame.draw.rect(surface, (60, 60, 70), track, border_radius=4)
        # Inner highlight
        highlight_rect = pygame.Rect(track.x + 1, track.y + 1, track.width - 2, 1)
        pygame.draw.rect(surface, (80, 80, 90), highlight_rect, border_radius=2)
        
        # Fill according to value với gradient và glow
        t = (value - vmin) / (vmax - vmin) if vmax > vmin else 0
        fill_width = max(4, int(track.width * t))
        fill = pygame.Rect(track.x, track.y, fill_width, track.height)
        
        if fill_width > 0:
            # Fill gradient - từ sáng đến tối
            fill_surf = pygame.Surface((fill_width, track.height), pygame.SRCALPHA)
            accent = self.config.colors["accent"]
            accent_rgb = accent[:3] if len(accent) >= 3 else (70, 140, 210)
            for y in range(track.height):
                # Gradient từ trên xuống
                factor = 1.0 - (y / track.height) * 0.3
                color = tuple(min(255, int(c * factor)) for c in accent_rgb)
                pygame.draw.line(fill_surf, color, (0, y), (fill_width, y))
            surface.blit(fill_surf, fill, special_flags=pygame.BLEND_ALPHA_SDL2)
            
            # Glow effect cho fill khi hover
            if is_hovered:
                glow_surf = pygame.Surface((fill_width + 8, track.height + 8), pygame.SRCALPHA)
                glow_rect = pygame.Rect(4, 4, fill_width, track.height)
                glow_color = (*accent_rgb, 60)
                try:
                    pygame.draw.rect(glow_surf, glow_color, glow_rect, border_radius=4)
                except TypeError:
                    pygame.draw.rect(glow_surf, accent_rgb, glow_rect, border_radius=4)
                surface.blit(glow_surf, (fill.x - 4, fill.y - 4), special_flags=pygame.BLEND_ALPHA_SDL2)
            
            # Border cho fill
            pygame.draw.rect(surface, accent_rgb, fill, border_radius=4)
            # Top highlight
            fill_highlight = pygame.Rect(fill.x, fill.y, fill.width, 1)
            highlight_color = tuple(min(255, c + 40) for c in accent_rgb)
            pygame.draw.rect(surface, highlight_color, fill_highlight, border_radius=2)
        
        # Knob với modern design
        knob = self._slider_knob_rect(key)
        # Knob shadow
        knob_shadow = knob.copy()
        knob_shadow.x += 2
        knob_shadow.y += 2
        shadow_surf = pygame.Surface((knob.width + 4, knob.height + 4), pygame.SRCALPHA)
        shadow_surf.fill((0, 0, 0, 120))
        surface.blit(shadow_surf, (knob_shadow.x - 2, knob_shadow.y - 2), special_flags=pygame.BLEND_ALPHA_SDL2)
        
        # Knob gradient background
        knob_surf = pygame.Surface((knob.width, knob.height), pygame.SRCALPHA)
        for y in range(knob.height):
            factor = 1.0 - (y / knob.height) * 0.4
            color = tuple(min(255, int(c * factor)) for c in (240, 240, 250))
            pygame.draw.line(knob_surf, color, (0, y), (knob.width, y))
        surface.blit(knob_surf, knob, special_flags=pygame.BLEND_ALPHA_SDL2)
        
        # Knob border
        border_color = accent_rgb if is_hovered else (100, 100, 120)
        border_width = 3 if is_hovered else 2
        pygame.draw.rect(surface, border_color, knob, border_width, border_radius=8)
        
        # Knob inner highlight
        highlight_knob = pygame.Rect(knob.x + 2, knob.y + 2, knob.width - 4, knob.height // 2)
        pygame.draw.rect(surface, (255, 255, 255), highlight_knob, border_radius=6)
        
        # Glow effect cho knob khi hover
        if is_hovered:
            glow_surf = pygame.Surface((knob.width + 12, knob.height + 12), pygame.SRCALPHA)
            glow_rect = pygame.Rect(6, 6, knob.width, knob.height)
            glow_color = (*accent_rgb, 80)
            try:
                pygame.draw.rect(glow_surf, glow_color, glow_rect, border_radius=10)
            except TypeError:
                pygame.draw.rect(glow_surf, accent_rgb, glow_rect, border_radius=10)
            surface.blit(glow_surf, (knob.x - 6, knob.y - 6), special_flags=pygame.BLEND_ALPHA_SDL2)
        
        # Value label với improved styling - chỉ hiển thị giá trị, bỏ phần trong ngoặc đơn
        value_text = str(value)
        
        lbl = self.small_font.render(value_text, True, (255, 255, 255))
        lbl_x = min(track.right + 12, surface.get_width() - lbl.get_width() - 8)
        lbl_y = track.centery - lbl.get_height() // 2
        
        # Label background với shadow
        lbl_bg = pygame.Rect(lbl_x - 6, lbl_y - 2, lbl.get_width() + 12, lbl.get_height() + 4)
        lbl_shadow = lbl_bg.copy()
        lbl_shadow.x += 1
        lbl_shadow.y += 1
        shadow_surf = pygame.Surface((lbl_bg.width, lbl_bg.height), pygame.SRCALPHA)
        shadow_surf.fill((0, 0, 0, 150))
        surface.blit(shadow_surf, lbl_shadow, special_flags=pygame.BLEND_ALPHA_SDL2)
        
        # Label background
        lbl_bg_surf = pygame.Surface((lbl_bg.width, lbl_bg.height), pygame.SRCALPHA)
        lbl_bg_surf.fill((35, 35, 45, 220))
        surface.blit(lbl_bg_surf, lbl_bg, special_flags=pygame.BLEND_ALPHA_SDL2)
        pygame.draw.rect(surface, accent_rgb, lbl_bg, 1, border_radius=6)
        
        # Label text với shadow
        lbl_shadow_text = self.small_font.render(value_text, True, (0, 0, 0))
        surface.blit(lbl_shadow_text, (lbl_x + 1, lbl_y + 1))
        surface.blit(lbl, (lbl_x, lbl_y))

    def _slider_knob_rect(self, key: str) -> pygame.Rect:
        """获取滑块旋钮矩形"""
        if key not in self.slider_tracks:
            return pygame.Rect(0, 0, 0, 0)
        track = self.slider_tracks[key]
        value, vmin, vmax, step = self._slider_get_range(key)
        t = (value - vmin) / (vmax - vmin) if vmax > vmin else 0
        cx = track.x + int(track.width * t)
        return pygame.Rect(cx - 8, track.y - 6, 16, 16)

    def _slider_get_range(self, key: str):
        """获取滑块范围"""
        if key == "move_time":
            return int(self.move_time_limit), 5, 300, 5
        if key == "undo":
            return int(self.max_undo), 0, 10, 1
        if key == "hint":
            return int(self.max_hint), 0, 10, 1
        if key == "depth":
            # Chỉnh Hint depth cho cùng range (0, 10) như Max undos và Max hints
            return int(self.hint_depth), 0, 10, 1
        return 0, 0, 1, 1

    def _slider_update_value_by_pos(self, key: str, mouse_x: int) -> None:
        """根据鼠标位置更新滑块值"""
        if key not in self.slider_tracks:
            return
        track = self.slider_tracks[key]
        value, vmin, vmax, step = self._slider_get_range(key)
        t = (mouse_x - track.x) / track.width
        t = max(0.0, min(1.0, t))
        raw = vmin + t * (vmax - vmin)
        snapped = int(round(raw / step) * step)
        snapped = max(vmin, min(vmax, snapped))
        
        # Kiểm tra xem giá trị có thay đổi không
        old_value = None
        if key == "move_time":
            old_value = self.move_time_limit
            self.move_time_limit = snapped
        elif key == "undo":
            old_value = self.max_undo
            self.max_undo = snapped
        elif key == "hint":
            old_value = self.max_hint
            self.max_hint = snapped
        elif key == "depth":
            old_value = self.hint_depth
            self.hint_depth = snapped
        
        # Tăng counter nếu giá trị thay đổi
        if old_value is not None and old_value != snapped:
            self.setting_change_count += 1

    def handle_event(self, event: pygame.event.Event):
        from scenes.match_scene import MatchScene  # local import to avoid cycle

        # Xử lý wheel scroll TRƯỚC để ưu tiên và tránh trigger selection
        if event.type == pygame.MOUSEWHEEL:
            # Wheel scroll CHỈ để LƯỚT qua danh sách nhạc, KHÔNG chọn nhạc
            # QUAN TRỌNG: Wheel scroll KHÔNG BAO GIỜ thay đổi selection index
            mouse_pos = pygame.mouse.get_pos()
            max_visible_items = 4
            
            # Helper function để xử lý wheel scroll cho một dropdown
            def handle_music_wheel_scroll(scroll_area_rect, dropdown_rect, list_rect, 
                                         dropdown_open, scroll_offset, music_idx, music_opts, 
                                         is_menu=True):
                """Xử lý wheel scroll cho music dropdown - chỉ scroll, không chọn"""
                # Kiểm tra mouse có trong vùng scroll (label + dropdown button) hoặc list
                in_area = False
                if scroll_area_rect and scroll_area_rect.width > 0:
                    in_area = scroll_area_rect.collidepoint(mouse_pos)
                if not in_area and dropdown_open and list_rect and list_rect.width > 0:
                    in_area = list_rect.collidepoint(mouse_pos)
                
                if not in_area:
                    return False
                
                # Đặt flag để ngăn selection khi wheel scroll
                # QUAN TRỌNG: Flag này ngăn mọi selection khi đang wheel scroll
                # Chỉ có click trực tiếp vào item mới được chọn nhạc
                if is_menu:
                    self._wheel_scrolling_menu = True
                else:
                    self._wheel_scrolling_match = True
                
                # Nếu dropdown chưa mở, mở nó trước
                if not dropdown_open:
                    if is_menu:
                        self.menu_music_dropdown_open = True
                        self.match_music_dropdown_open = False
                        self.match_music_scroll_offset = 0
                        self._wheel_scrolling_match = False
                    else:
                        self.match_music_dropdown_open = True
                        self.menu_music_dropdown_open = False
                        self.menu_music_scroll_offset = 0
                        self._wheel_scrolling_menu = False
                    
                    # Scroll đến item được chọn khi mở
                    total_items = len(music_opts)
                    max_scroll = max(0, total_items - max_visible_items)
                    if max_scroll > 0:
                        new_offset = scroll_offset
                        if music_idx < new_offset:
                            new_offset = music_idx
                        elif music_idx >= new_offset + max_visible_items:
                            new_offset = max(0, music_idx - max_visible_items + 1)
                        new_offset = min(new_offset, max_scroll)
                        if is_menu:
                            self.menu_music_scroll_offset = new_offset
                        else:
                            self.match_music_scroll_offset = new_offset
                
                # Scroll danh sách (nếu dropdown đã mở)
                if (is_menu and self.menu_music_dropdown_open) or (not is_menu and self.match_music_dropdown_open):
                    total_items = len(music_opts)
                    max_scroll = max(0, total_items - max_visible_items)
                    if max_scroll > 0:
                        current_offset = self.menu_music_scroll_offset if is_menu else self.match_music_scroll_offset
                        new_offset = current_offset - event.y
                        new_offset = max(0, min(max_scroll, new_offset))
                        if is_menu:
                            self.menu_music_scroll_offset = new_offset
                        else:
                            self.match_music_scroll_offset = new_offset
                
                return True
            
            # Xử lý wheel scroll cho Menu Music
            if hasattr(self, 'menu_music_scroll_area_rect'):
                if handle_music_wheel_scroll(
                    self.menu_music_scroll_area_rect,
                    getattr(self, 'menu_music_dropdown_rect', None),
                    getattr(self, 'menu_music_list_rect', None),
                    self.menu_music_dropdown_open,
                    self.menu_music_scroll_offset,
                    self.menu_music_idx,
                    self.menu_music_opts,
                    is_menu=True
                ):
                    return None  # Return sớm để không trigger logic khác
            
            # Xử lý wheel scroll cho Match Music
            if hasattr(self, 'match_music_scroll_area_rect'):
                if handle_music_wheel_scroll(
                    self.match_music_scroll_area_rect,
                    getattr(self, 'match_music_dropdown_rect', None),
                    getattr(self, 'match_music_list_rect', None),
                    self.match_music_dropdown_open,
                    self.match_music_scroll_offset,
                    self.match_music_idx,
                    self.match_music_opts,
                    is_menu=False
                ):
                    return None  # Return sớm để không trigger logic khác
            
            # Block wheel scroll trên avatar để tránh avatar nhảy
            if hasattr(self, 'avatar_preview_rects'):
                human_avatar_rect, ai_avatar_rect = self.avatar_preview_rects
                if (human_avatar_rect.width > 0 and human_avatar_rect.collidepoint(mouse_pos)) or \
                   (ai_avatar_rect.width > 0 and ai_avatar_rect.collidepoint(mouse_pos)):
                    return None  # Block wheel scroll trên avatar

        if event.type == pygame.MOUSEBUTTONDOWN:
            # Volume control click/drag
            if self._volume_slider_track.collidepoint(event.pos) or self._volume_rect.collidepoint(event.pos):
                self._volume_dragging = True
                self._update_volume_from_mouse(event.pos[0])
                return None
            
            # Exit image click -> back to menu
            if self._exit_rect.width > 0 and self._exit_rect.collidepoint(event.pos):
                from scenes.menu_scene import MenuScene
                return MenuScene(self.config)
            # Logout
            if self.btn_logout.width > 0 and self.btn_logout.collidepoint(event.pos):
                self.config.current_user = None
                from scenes.menu_scene import LoginScene
                return LoginScene(self.config, self.assets)
            if self.input_rect.width > 0 and self.input_rect.collidepoint(event.pos):
                self.input_active = True
            else:
                self.input_active = False

            # Best-of-N selection
            for i, (n, rect) in enumerate(zip([3, 5, 7, 9], self.btn_bon_rects)):
                if rect.width > 0 and rect.collidepoint(event.pos):
                    self.best_of_n = n
                    self.validation_message = ""

            # Option rows
            if hasattr(self, 'option_row_rects'):
                for i, (row_rect, label, value) in enumerate(self.option_row_rects):
                    if row_rect.width > 0 and row_rect.collidepoint(event.pos):
                        if i == 0:  # Mode
                            self.mode_idx = (self.mode_idx + 1) % len(self.mode_opts)
                            # Cập nhật role của player 2 dựa trên mode
                            if self.mode_opts[self.mode_idx] == "PvP":
                                self.ai.role = "Human"
                                if not self.ai.name or self.ai.name == "Machine/AI":
                                    self.ai.name = "Player 2"
                            else:  # PvAI
                                self.ai.role = "AI"
                                if self.ai.name == "Player 2":
                                    self.ai.name = "Machine/AI"
                        elif i == 1:  # Side
                            self.side_idx = (self.side_idx + 1) % len(self.side_opts)
                        elif i == 2:  # Swap sides
                            self.swap_sides = not self.swap_sides
                        self.validation_message = ""

            # Difficulty buttons
            if self.mode_opts[self.mode_idx] == "PvAI" and hasattr(self, 'difficulty_button_rects'):
                for i, btn_rect in enumerate(self.difficulty_button_rects):
                    if btn_rect.width > 0 and btn_rect.collidepoint(event.pos):
                        self.ai_diff_idx = i
                        break
            
            # Piece skin buttons
            if hasattr(self, 'piece_skin_button_rects'):
                for i, btn_rect in enumerate(self.piece_skin_button_rects):
                    if btn_rect.width > 0 and btn_rect.collidepoint(event.pos):
                        self.piece_skin_idx = i
                        self.config.PIECE_SKIN = self.piece_skin_opts[i]
                        break
            
            # Menu music dropdown
            menu_music_handled = False
            if hasattr(self, 'menu_music_dropdown_rect') and self.menu_music_dropdown_rect.width > 0:
                if self.menu_music_dropdown_rect.collidepoint(event.pos):
                    # Toggle dropdown
                    self.menu_music_dropdown_open = not self.menu_music_dropdown_open
                    # Reset scroll khi đóng
                    if not self.menu_music_dropdown_open:
                        self.menu_music_scroll_offset = 0
                    # Khi mở, scroll đến item được chọn
                    elif self.menu_music_dropdown_open:
                        max_visible_items = 4
                        total_items = len(self.menu_music_opts)
                        max_scroll = max(0, total_items - max_visible_items)
                        # Đảm bảo item được chọn nằm trong view
                        if self.menu_music_idx < self.menu_music_scroll_offset:
                            self.menu_music_scroll_offset = self.menu_music_idx
                        elif self.menu_music_idx >= self.menu_music_scroll_offset + max_visible_items:
                            self.menu_music_scroll_offset = max(0, self.menu_music_idx - max_visible_items + 1)
                        self.menu_music_scroll_offset = min(self.menu_music_scroll_offset, max_scroll)
                    # Đóng match music dropdown nếu đang mở
                    if self.menu_music_dropdown_open:
                        self.match_music_dropdown_open = False
                        self.match_music_scroll_offset = 0
                    menu_music_handled = True
                elif self.menu_music_dropdown_open:
                    # Click vào scrollbar
                    if hasattr(self, 'menu_music_scrollbar_rect') and self.menu_music_scrollbar_rect.width > 0:
                        if self.menu_music_scrollbar_rect.collidepoint(event.pos):
                            # Click vào scrollbar track hoặc thumb
                            total_items = len(self.menu_music_opts)
                            max_visible_items = 4
                            max_scroll = max(0, total_items - max_visible_items)
                            if max_scroll > 0:
                                scrollbar_height = self.menu_music_scrollbar_rect.height
                                relative_y = event.pos[1] - self.menu_music_scrollbar_rect.y
                                t = max(0.0, min(1.0, relative_y / scrollbar_height))
                                self.menu_music_scroll_offset = int(t * max_scroll)
                                self.menu_music_scroll_dragging = True
                                menu_music_handled = True
                    # Click vào item trong list - CHỈ CÁCH DUY NHẤT để chọn nhạc
                    # QUAN TRỌNG: Chỉ cho phép chọn khi:
                    # 1. Không đang wheel scrolling
                    # 2. Click trực tiếp vào item rect (không phải scrollbar hoặc dropdown button)
                    # 3. Event là MOUSEBUTTONDOWN với button 1 (left click)
                    if (not menu_music_handled and 
                        not self._wheel_scrolling_menu and 
                        event.button == 1 and  # Chỉ left click
                        hasattr(self, 'menu_music_item_rects')):
                        for item_rect, idx in self.menu_music_item_rects:
                            if item_rect.collidepoint(event.pos):
                                # CHỈ Ở ĐÂY mới được thay đổi menu_music_idx
                                self.menu_music_idx = idx
                                self.menu_music_dropdown_open = False
                                self.menu_music_scroll_offset = 0
                                # Reset flag ngay sau khi chọn
                                self._wheel_scrolling_menu = False
                                menu_music_handled = True
                                break
            
            # Match music dropdown
            match_music_handled = False
            if hasattr(self, 'match_music_dropdown_rect') and self.match_music_dropdown_rect.width > 0:
                if self.match_music_dropdown_rect.collidepoint(event.pos):
                    # Toggle dropdown
                    self.match_music_dropdown_open = not self.match_music_dropdown_open
                    # Reset scroll khi đóng
                    if not self.match_music_dropdown_open:
                        self.match_music_scroll_offset = 0
                    # Khi mở, scroll đến item được chọn
                    elif self.match_music_dropdown_open:
                        max_visible_items = 4
                        total_items = len(self.match_music_opts)
                        max_scroll = max(0, total_items - max_visible_items)
                        # Đảm bảo item được chọn nằm trong view
                        if self.match_music_idx < self.match_music_scroll_offset:
                            self.match_music_scroll_offset = self.match_music_idx
                        elif self.match_music_idx >= self.match_music_scroll_offset + max_visible_items:
                            self.match_music_scroll_offset = max(0, self.match_music_idx - max_visible_items + 1)
                        self.match_music_scroll_offset = min(self.match_music_scroll_offset, max_scroll)
                    # Đóng menu music dropdown nếu đang mở
                    if self.match_music_dropdown_open:
                        self.menu_music_dropdown_open = False
                        self.menu_music_scroll_offset = 0
                    match_music_handled = True
                elif self.match_music_dropdown_open:
                    # Click vào scrollbar
                    if hasattr(self, 'match_music_scrollbar_rect') and self.match_music_scrollbar_rect.width > 0:
                        if self.match_music_scrollbar_rect.collidepoint(event.pos):
                            # Click vào scrollbar track hoặc thumb
                            total_items = len(self.match_music_opts)
                            max_visible_items = 4
                            max_scroll = max(0, total_items - max_visible_items)
                            if max_scroll > 0:
                                scrollbar_height = self.match_music_scrollbar_rect.height
                                relative_y = event.pos[1] - self.match_music_scrollbar_rect.y
                                t = max(0.0, min(1.0, relative_y / scrollbar_height))
                                self.match_music_scroll_offset = int(t * max_scroll)
                                self.match_music_scroll_dragging = True
                                match_music_handled = True
                    # Click vào item trong list - CHỈ CÁCH DUY NHẤT để chọn nhạc
                    # QUAN TRỌNG: Chỉ cho phép chọn khi:
                    # 1. Không đang wheel scrolling
                    # 2. Click trực tiếp vào item rect (không phải scrollbar hoặc dropdown button)
                    # 3. Event là MOUSEBUTTONDOWN với button 1 (left click)
                    if (not match_music_handled and 
                        not self._wheel_scrolling_match and 
                        event.button == 1 and  # Chỉ left click
                        hasattr(self, 'match_music_item_rects')):
                        for item_rect, idx in self.match_music_item_rects:
                            if item_rect.collidepoint(event.pos):
                                # CHỈ Ở ĐÂY mới được thay đổi match_music_idx
                                self.match_music_idx = idx
                                self.match_music_dropdown_open = False
                                self.match_music_scroll_offset = 0
                                # Reset flag ngay sau khi chọn
                                self._wheel_scrolling_match = False
                                match_music_handled = True
                                break
            
            # Đóng dropdown nếu click ngoài
            if not menu_music_handled and not match_music_handled:
                if self.menu_music_dropdown_open:
                    if hasattr(self, 'menu_music_list_rect') and not self.menu_music_list_rect.collidepoint(event.pos):
                        if hasattr(self, 'menu_music_dropdown_rect') and not self.menu_music_dropdown_rect.collidepoint(event.pos):
                            self.menu_music_dropdown_open = False
                if self.match_music_dropdown_open:
                    if hasattr(self, 'match_music_list_rect') and not self.match_music_list_rect.collidepoint(event.pos):
                        if hasattr(self, 'match_music_dropdown_rect') and not self.match_music_dropdown_rect.collidepoint(event.pos):
                            self.match_music_dropdown_open = False

            # Gender buttons - click để chọn giới tính
            if hasattr(self, 'gender_button_rects'):
                for i, button_rect in enumerate(self.gender_button_rects):
                    if button_rect.collidepoint(event.pos):
                        self.gender_idx = i
                        self.human.gender = self.gender_opts[self.gender_idx]
                        self.validation_message = ""
                        break

            # Avatar preview boxes - CHỈ cho phép LEFT CLICK, không cho phép wheel scroll hoặc các nút khác
            if hasattr(self, 'avatar_preview_rects') and event.button == 1:  # Chỉ left click (button 1)
                human_avatar_rect, ai_avatar_rect = self.avatar_preview_rects
                # Click vào Human avatar box -> mở file dialog
                if human_avatar_rect.width > 0 and human_avatar_rect.collidepoint(event.pos):
                    root = None
                    try:
                        import tkinter as tk
                        from tkinter import filedialog
                        root = tk.Tk()
                        root.withdraw()
                        root.attributes('-topmost', True)
                        root.update()
                        
                        fp = filedialog.askopenfilename(
                            title="Choose avatar image", 
                            initialdir=self.config.avatars_dir, 
                            filetypes=[("Images", "*.png;*.jpg;*.jpeg;*.bmp;*.gif")]
                        )
                        
                        if fp and isinstance(fp, str) and len(fp.strip()) > 0:
                            self.human.avatar_path = fp
                    except Exception as e:
                        pass
                    finally:
                        if root is not None:
                            try:
                                root.quit()
                                root.destroy()
                            except:
                                pass
                
                # Click vào AI avatar box -> cycle AI avatar
                elif ai_avatar_rect.width > 0 and ai_avatar_rect.collidepoint(event.pos):
                    opts = self.available_avatars or ["ai_bot.png", "server.png", "pc.png"]
                    self.ai_cycle_idx = (self.ai_cycle_idx + 1) % len(opts)
                    self.ai.avatar_path = os.path.join(self.config.avatars_dir, opts[self.ai_cycle_idx])


            # Sliders - Xử lý trước để ưu tiên slider
            slider_clicked = False
            for key, track in self.slider_tracks.items():
                if track.width > 0:
                    knob = self._slider_knob_rect(key)
                    if knob.width > 0 and knob.collidepoint(event.pos):
                        self.slider_dragging = key
                        slider_clicked = True
                        break
                    elif track.collidepoint(event.pos):
                        self.slider_dragging = key
                        self._slider_update_value_by_pos(key, event.pos[0])
                        slider_clicked = True
                        break

            # Start button - Chỉ check nếu không click vào slider, và chỉ check vùng clickable nhỏ
            if not slider_clicked and self.btn_start.width > 0 and self.btn_start.collidepoint(event.pos):
                if self.best_of_n not in (3, 5, 7, 9):
                    self.validation_message = "N must be odd in {3,5,7,9}."
                else:
                    # Apply advanced config to app config
                    self.config.MOVE_TIME_LIMIT = int(self.move_time_limit)
                    self.config.MAX_UNDO_PER_PLAYER = int(self.max_undo)
                    self.config.MAX_HINT_PER_PLAYER = int(self.max_hint)
                    self.config.HINT_DEPTH = int(self.hint_depth)
                    self.config.best_of_n = self.best_of_n
                    # Apply mode selections
                    try:
                        self.config.game_mode = self.mode_opts[self.mode_idx]
                        self.config.side_to_start = self.side_opts[self.side_idx]
                        self.config.swap_sides_between_games = self.swap_sides
                        self.config.ai_difficulty = self.ai_diff_opts[self.ai_diff_idx]
                        # Apply piece skin
                        self.config.PIECE_SKIN = self.piece_skin_opts[self.piece_skin_idx]
                        # Update pieces_dir to selected skin folder if exists
                        pieces_root = os.path.join(self.config.assets_dir, "pieces")
                        selected_dir = os.path.join(pieces_root, self.config.PIECE_SKIN)
                        self.config.pieces_dir = selected_dir if os.path.exists(selected_dir) else pieces_root
                        # Apply music settings
                        self.config.menu_music = self.menu_music_opts[self.menu_music_idx]
                        self.config.match_music = self.match_music_opts[self.match_music_idx]
                        # Save music settings immediately
                        try:
                            from core.settings import load_settings, save_settings, AppSettings
                            current_settings = load_settings()
                            save_settings(AppSettings(
                                window_width=current_settings.window_width,
                                window_height=current_settings.window_height,
                                fullscreen=current_settings.fullscreen,
                                board_size_px=current_settings.board_size_px,
                                theme=current_settings.theme,
                                piece_skin=current_settings.piece_skin,
                                ai_difficulty=current_settings.ai_difficulty,
                                move_time_limit=current_settings.move_time_limit,
                                max_undo=current_settings.max_undo,
                                max_hint=current_settings.max_hint,
                                current_user=current_settings.current_user,
                                menu_music=self.config.menu_music,
                                match_music=self.config.match_music,
                            ))
                        except Exception:
                            pass
                        # Also update current AssetManager and reset its cache to reflect skin change
                        try:
                            self.assets.pieces_dir = self.config.pieces_dir
                            # clear cached piece images so new skin loads
                            if hasattr(self.assets, "_image_cache"):
                                self.assets._image_cache.clear()
                        except Exception:
                            pass
                    except Exception:
                        pass
                    # Ensure second player's label in PvP
                    if self.config.game_mode == "PvP":
                        if not self.ai.name or self.ai.name == "Machine/AI":
                            self.ai.name = "Player 2"
                        self.ai.role = "Human"
                    return MatchScene(self.config, self.assets, self.human, self.ai, self.set_id)

        elif event.type == pygame.MOUSEMOTION:
            # Volume dragging
            if self._volume_dragging:
                self._update_volume_from_mouse(event.pos[0])
            
            if self.slider_dragging is not None:
                self._slider_update_value_by_pos(self.slider_dragging, event.pos[0])
            
            # Menu music scrollbar dragging
            if self.menu_music_scroll_dragging and self.menu_music_dropdown_open:
                if hasattr(self, 'menu_music_scrollbar_rect') and self.menu_music_scrollbar_rect.width > 0:
                    total_items = len(self.menu_music_opts)
                    max_visible_items = 4
                    max_scroll = max(0, total_items - max_visible_items)
                    if max_scroll > 0:
                        scrollbar_height = self.menu_music_scrollbar_rect.height
                        relative_y = event.pos[1] - self.menu_music_scrollbar_rect.y
                        t = max(0.0, min(1.0, relative_y / scrollbar_height))
                        self.menu_music_scroll_offset = int(t * max_scroll)
            
            # Match music scrollbar dragging
            if self.match_music_scroll_dragging and self.match_music_dropdown_open:
                if hasattr(self, 'match_music_scrollbar_rect') and self.match_music_scrollbar_rect.width > 0:
                    total_items = len(self.match_music_opts)
                    max_visible_items = 4
                    max_scroll = max(0, total_items - max_visible_items)
                    if max_scroll > 0:
                        scrollbar_height = self.match_music_scrollbar_rect.height
                        relative_y = event.pos[1] - self.match_music_scrollbar_rect.y
                        t = max(0.0, min(1.0, relative_y / scrollbar_height))
                        self.match_music_scroll_offset = int(t * max_scroll)
            

        elif event.type == pygame.MOUSEBUTTONUP:
            # Stop scrollbar dragging
            if self.menu_music_scroll_dragging:
                self.menu_music_scroll_dragging = False
            if self.match_music_scroll_dragging:
                self.match_music_scroll_dragging = False
            # Reset wheel scrolling flags
            self._wheel_scrolling_menu = False
            self._wheel_scrolling_match = False
            # Volume drag end
            if self._volume_dragging:
                self._volume_dragging = False
                self._update_volume_from_mouse(event.pos[0])
                self.config.volume = self.volume
                return None
            
            if self.slider_dragging is not None:
                self._slider_update_value_by_pos(self.slider_dragging, event.pos[0])
                self.slider_dragging = None

        elif event.type == pygame.KEYDOWN and self.input_active:
            if event.key == pygame.K_RETURN:
                self.input_active = False
            elif event.key == pygame.K_BACKSPACE:
                self.human.name = self.human.name[:-1]
            else:
                if len(self.human.name) < 24 and (32 <= event.key <= 126):
                    self.human.name += event.unicode

        return None

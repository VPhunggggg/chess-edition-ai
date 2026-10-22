from __future__ import annotations

import os
import sys
import pygame
from typing import Optional, List, Dict, Tuple

# Ensure working directory is project root (for running as script)
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from core.config import AppConfig
from core.assets import AssetManager
from core.history import HistoryWriter
from core.auth import show_login_dialog
import json


class LoginScene:
    def __init__(self, config: AppConfig, assets: AssetManager) -> None:
        self.config = config
        self.assets = assets
        # Background: use provided login.png from Decorate, cover entire screen
        self.bg_raw = self._load_login_bg()
        self._last_size = (self.config.window_width, self.config.window_height)

        # Fonts
        self.title_font = self.assets.get_font(66)
        self.input_font = self.assets.get_font(26)
        self.button_font = self.assets.get_font(28)
        self.link_font = self.assets.get_font(20)

        # State
        self.active_field: Optional[str] = None  # "account" | "password"
        self.account_text: str = ""
        self.password_text: str = ""
        # Title image (replace text)
        self.title_img_raw: Optional[pygame.Surface] = self._load_title_image()
        self._login_rect = pygame.Rect(0, 0, 0, 0)
        self._account_rect = pygame.Rect(0, 0, 0, 0)
        self._password_rect = pygame.Rect(0, 0, 0, 0)
        self._register_rect = pygame.Rect(0, 0, 0, 0)
        self._hover_login = False
        self._hover_register = False
        # Optional ornate login button image
        self.login_img_raw: Optional[pygame.Surface] = self._load_login_button()
        # Feedback message
        self.login_message: str = ""
        self.login_error: bool = False
        # Cursor blink timer for real-time text display
        self.cursor_timer: float = 0.0
        self.cursor_visible: bool = True

    def _load_login_bg(self) -> Optional[pygame.Surface]:
        try:
            path = os.path.join(".", "assets", "Decorate", "login.png")
            if os.path.exists(path):
                return pygame.image.load(path).convert_alpha()
        except Exception:
            pass
        return None

    def handle_event(self, event: pygame.event.Event) -> Optional["MenuScene"]:
        from scenes.setup_scene import SetupScene
        if event.type == pygame.VIDEORESIZE:
            self._last_size = (event.w, event.h)
        elif event.type == pygame.MOUSEMOTION:
            pos = event.pos
            self._hover_login = self._login_rect.collidepoint(pos)
            self._hover_register = self._register_rect.collidepoint(pos)
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if self._account_rect.collidepoint(event.pos):
                self.active_field = "account"
                # Reset cursor when clicking on field
                self.cursor_timer = 0.0
                self.cursor_visible = True
                # Enable text input for better real-time display
                try:
                    pygame.key.start_text_input()
                except:
                    pass
            elif self._password_rect.collidepoint(event.pos):
                self.active_field = "password"
                # Reset cursor when clicking on field
                self.cursor_timer = 0.0
                self.cursor_visible = True
                # Enable text input for better real-time display
                try:
                    pygame.key.start_text_input()
                except:
                    pass
            elif self._login_rect.collidepoint(event.pos):
                # Validation: if has registered accounts, require correct credentials.
                username = self.account_text.strip()
                password = self.password_text.strip()
                # Use persistent auth
                from core.auth import authenticate
                can_login = bool(username and password and authenticate(username, password))
                if can_login:
                    try:
                        self.config.current_user = {"name": username}
                    except Exception:
                        pass
                    self.login_message = ""
                    self.login_error = False
                    return SetupScene(self.config)
                else:
                    self.login_message = "Incorrect username or password."
                    self.login_error = True
            elif self._register_rect.collidepoint(event.pos):
                from scenes.menu_scene import RegisterScene
                return RegisterScene(self.config, self.assets)
            else:
                # Click outside fields - deactivate
                self.active_field = None
                # Stop text input when deactivating
                try:
                    pygame.key.stop_text_input()
                except:
                    pass
        elif event.type == pygame.TEXTINPUT:
            # Handle text input for better real-time display
            if self.active_field in ("account", "password"):
                ch = event.text
                if ch:
                    if self.active_field == "account":
                        self.account_text += ch
                    else:
                        self.password_text += ch
                    # Reset cursor to visible when typing
                    self.cursor_timer = 0.0
                    self.cursor_visible = True
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_TAB:
                self.active_field = "password" if self.active_field == "account" else "account"
                # Reset cursor when switching fields
                self.cursor_timer = 0.0
                self.cursor_visible = True
                # Keep text input enabled when switching
                try:
                    pygame.key.start_text_input()
                except:
                    pass
            elif event.key == pygame.K_RETURN:
                username = self.account_text.strip()
                password = self.password_text.strip()
                from core.auth import authenticate
                can_login = bool(username and password and authenticate(username, password))
                if can_login:
                    try:
                        self.config.current_user = {"name": username}
                    except Exception:
                        pass
                    self.login_message = ""
                    self.login_error = False
                    return SetupScene(self.config)
                else:
                    self.login_message = "Incorrect username or password."
                    self.login_error = True
            elif event.key == pygame.K_ESCAPE:
                from scenes.menu_scene import MenuScene
                return MenuScene(self.config)
            elif event.key == pygame.K_BACKSPACE:
                # Chỉ xử lý BACKSPACE, text input được xử lý bởi TEXTINPUT event
                if self.active_field in ("account", "password"):
                    if self.active_field == "account":
                        self.account_text = self.account_text[:-1] if self.account_text else ""
                    else:
                        self.password_text = self.password_text[:-1] if self.password_text else ""
                    # Reset cursor when deleting
                    self.cursor_timer = 0.0
                    self.cursor_visible = True
        return None

    def update(self, dt: float):
        """Refresh cached layout info when窗口尺寸变化."""
        surface = pygame.display.get_surface()
        if surface:
            size = surface.get_size()
            if size != self._last_size:
                self._last_size = size
        
        # Update cursor blink for real-time text display
        if self.active_field:
            self.cursor_timer += dt
            if self.cursor_timer >= 0.5:  # Blink every 0.5 seconds
                self.cursor_timer = 0.0
                self.cursor_visible = not self.cursor_visible
        else:
            self.cursor_timer = 0.0
            self.cursor_visible = True
        
        return None

    def _load_title_image(self) -> Optional[pygame.Surface]:
        """Load 'name.png' to replace CHESS EDITION text."""
        try:
            path = os.path.join(".", "assets", "Decorate", "name.png")
            if os.path.exists(path):
                return pygame.image.load(path).convert_alpha()
        except Exception:
            pass
        return None

    def _draw_frame(self, surface: pygame.Surface, rect: pygame.Rect, hovered: bool, inner_pad: int = 6) -> None:
        base = (90, 96, 110) if hovered else (70, 76, 90)
        border = (180, 190, 210) if hovered else (130, 140, 160)
        pygame.draw.rect(surface, base, rect, border_radius=10)
        pygame.draw.rect(surface, border, rect, width=3, border_radius=10)
        # inner highlight
        inner = rect.inflate(-inner_pad, -inner_pad)
        pygame.draw.rect(surface, (30, 30, 36), inner, width=1, border_radius=8)

    def _load_login_button(self) -> Optional[pygame.Surface]:
        """Load optional decorative login button image."""
        try:
            path = os.path.join(".", "assets", "Decorate", "Loginbutton.png")
            if os.path.exists(path):
                return pygame.image.load(path).convert_alpha()
        except Exception:
            pass
        return None

    def render(self, surface: pygame.Surface) -> None:
        w, h = surface.get_size()
        # Background cover
        if self.bg_raw:
            bw, bh = self.bg_raw.get_size()
            scale = max(w / bw, h / bh)
            scaled = pygame.transform.smoothscale(self.bg_raw, (int(bw * scale), int(bh * scale)))
            surface.blit(scaled, scaled.get_rect(center=(w // 2, h // 2)))
        else:
            surface.fill((15, 15, 18))

        # Bỏ tiêu đề hoàn toàn để không chồng lên background

        # Hot areas mapped to the single background image (no extra UI chrome)
        # These percentages come from the reference layout of login.png (approximate).
        # Account field (fit inner dark slot of the stone frame)
        acct_w = int(w * 0.275)   # extend a bit wider
        acct_h = int(h * 0.056)   # slightly shorter
        acct_cx = int(w * 0.768)
        acct_cy = int(h * 0.400)  # move further downward
        self._account_rect = pygame.Rect(0, 0, acct_w, acct_h)
        self._account_rect.center = (acct_cx, acct_cy)

        # Password field
        pwd_w = int(w * 0.275)
        pwd_h = int(h * 0.056)
        pwd_cx = int(w * 0.768)
        pwd_cy = int(h * 0.535)  # move further downward
        self._password_rect = pygame.Rect(0, 0, pwd_w, pwd_h)
        self._password_rect.center = (pwd_cx, pwd_cy)

        # Login button (blue circular orb)
        login_w = int(w * 0.11)
        login_h = int(h * 0.14)
        login_cx = int(w * 0.743)
        login_cy = int(h * 0.742)
        self._login_rect = pygame.Rect(0, 0, login_w, login_h)
        self._login_rect.center = (login_cx, login_cy)

        # Register now clickable text area
        reg_w = int(w * 0.30)
        reg_h = int(h * 0.05)
        reg_cx = int(w * 0.760)
        reg_cy = int(h * 0.627)  # move a bit up to the marked underline
        self._register_rect = pygame.Rect(0, 0, reg_w, reg_h)
        self._register_rect.center = (reg_cx, reg_cy)

        # Draw login button: prefer image if available
        if self.login_img_raw is not None:
            img_w, img_h = self.login_img_raw.get_size()
            scale = self._login_rect.height / max(1, img_h)
            draw_w = int(img_w * scale)
            draw_h = self._login_rect.height
            scaled = pygame.transform.smoothscale(self.login_img_raw, (draw_w, draw_h))
            img_rect = scaled.get_rect(center=self._login_rect.center)
            # Update clickable rect to match image bounds
            self._login_rect = img_rect
            surface.blit(scaled, img_rect)
        # 不绘制任何额外背景/边框，让 login.png 完整呈现

        # Text values (仅文本，透明叠加到图片上的输入槽) - Real-time display with cursor
        val_color = (240, 240, 245)
        # Account value or placeholder
        text_x = self._account_rect.x + 18
        text_y = self._account_rect.centery
        if self.account_text:
            acct_val = self.input_font.render(self.account_text, True, val_color)
            acct_rect = acct_val.get_rect(midleft=(text_x, text_y))
            surface.blit(acct_val, acct_rect)
            # Draw blinking cursor if account field is active
            if self.active_field == "account" and self.cursor_visible:
                cursor_x = acct_rect.right + 2
                cursor_y = text_y
                pygame.draw.line(surface, val_color, (cursor_x, cursor_y - 12), (cursor_x, cursor_y + 12), 2)
        else:
            hint = self.input_font.render("Account", True, (220, 210, 195))
            hint.set_alpha(120)
            hint_rect = hint.get_rect(midleft=(text_x, text_y))
            surface.blit(hint, hint_rect)
            # Draw blinking cursor if account field is active and empty
            if self.active_field == "account" and self.cursor_visible:
                cursor_x = hint_rect.left
                cursor_y = text_y
                pygame.draw.line(surface, val_color, (cursor_x, cursor_y - 12), (cursor_x, cursor_y + 12), 2)
        
        # Password value or placeholder bullets/hint
        pwd_x = self._password_rect.x + 18
        pwd_y = self._password_rect.centery
        if self.password_text:
            pwd_masked = "•" * len(self.password_text)
            pwd_val = self.input_font.render(pwd_masked, True, val_color)
            pwd_rect = pwd_val.get_rect(midleft=(pwd_x, pwd_y))
            surface.blit(pwd_val, pwd_rect)
            # Draw blinking cursor if password field is active
            if self.active_field == "password" and self.cursor_visible:
                cursor_x = pwd_rect.right + 2
                cursor_y = pwd_y
                pygame.draw.line(surface, val_color, (cursor_x, cursor_y - 12), (cursor_x, cursor_y + 12), 2)
        else:
            hint = self.input_font.render("Password", True, (220, 210, 195))
            hint.set_alpha(120)
            hint_rect = hint.get_rect(midleft=(pwd_x, pwd_y))
            surface.blit(hint, hint_rect)
            # Draw blinking cursor if password field is active and empty
            if self.active_field == "password" and self.cursor_visible:
                cursor_x = hint_rect.left
                cursor_y = pwd_y
                pygame.draw.line(surface, val_color, (cursor_x, cursor_y - 12), (cursor_x, cursor_y + 12), 2)

        # Hiển thị thông báo lỗi nổi bật
        if self.login_message:
            if self.login_error:
                # Thông báo lỗi - làm nổi bật với background và glow
                error_font = self.assets.get_font(18)  # Font nhỏ hơn để vùng đỏ gọn
                msg = error_font.render(self.login_message, True, (255, 255, 255))
                msg_rect = msg.get_rect(center=(
                    int(self._register_rect.centerx - surface.get_width() * 0.05),
                    int(self._register_rect.centery - surface.get_height() * 0.03),
                ))
                
                # Background box với màu đỏ nổi bật - sát chữ tối đa
                padding_h = 1  # Horizontal padding
                padding_v = 1  # Vertical padding
                bg_rect = pygame.Rect(
                    msg_rect.x - padding_h,
                    msg_rect.y - padding_v,
                    msg_rect.width + padding_h * 2,
                    msg_rect.height + padding_v * 2
                )
                
                # Shadow - nhỏ và nhẹ hơn
                shadow_rect = bg_rect.copy()
                shadow_rect.x += 1
                shadow_rect.y += 1
                shadow_surf = pygame.Surface((bg_rect.width, bg_rect.height), pygame.SRCALPHA)
                shadow_surf.fill((0, 0, 0, 80))
                surface.blit(shadow_surf, shadow_rect, special_flags=pygame.BLEND_ALPHA_SDL2)
                
                # Background đỏ với gradient effect - tối giản
                pygame.draw.rect(surface, (200, 40, 40), bg_rect, border_radius=3)
                # Inner glow nhẹ
                inner_rect = pygame.Rect(bg_rect.x + 1, bg_rect.y + 1, bg_rect.width - 2, bg_rect.height - 2)
                pygame.draw.rect(surface, (240, 60, 60), inner_rect, border_radius=2)
                # Border sáng mỏng
                pygame.draw.rect(surface, (255, 100, 100), bg_rect, 1, border_radius=3)
                
                # Text shadow để dễ đọc
                shadow_text = error_font.render(self.login_message, True, (0, 0, 0))
                surface.blit(shadow_text, (msg_rect.x + 1, msg_rect.y + 1))
                surface.blit(msg, msg_rect)
            else:
                # Thông báo thông thường
                color = (200, 230, 255)
                msg = self.link_font.render(self.login_message, True, color)
                msg_rect = msg.get_rect(center=(
                    int(self._register_rect.centerx - surface.get_width() * 0.05),
                    int(self._register_rect.centery - surface.get_height() * 0.03),
                ))
                surface.blit(msg, msg_rect)

class StaticImageScene:
    def __init__(self, config: AppConfig, assets: AssetManager, image_name: str) -> None:
        self.config = config
        self.assets = assets
        self.image_name = image_name
        self.bg = self.assets.get_decorate_image("dragon-background.jpg", (self.config.window_width, self.config.window_height))
        if self.bg is None:
            self.bg = self.assets.get_menu_image("Background.png", (self.config.window_width, self.config.window_height))
        self.image = self.assets.get_menu_image(image_name, (int(self.config.window_width * 0.6), 160))
        self.font = self.assets.get_font(18)
        self._last_size = (self.config.window_width, self.config.window_height)

    def handle_event(self, event: pygame.event.Event) -> Optional["MenuScene"]:
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_ESCAPE, pygame.K_BACKSPACE):
            from scenes.menu_scene import MenuScene
            return MenuScene(self.config)
        if event.type == pygame.MOUSEBUTTONDOWN:
            from scenes.menu_scene import MenuScene
            return MenuScene(self.config)
        return None

    def update(self, dt: float):
        # 只有在尺寸变化时才重新缩放背景/图片，避免每帧缩放
        surface = pygame.display.get_surface()
        if surface:
            size = surface.get_size()
            if size != self._last_size:
                self._last_size = size
                w, h = size
                self.bg = self.assets.get_decorate_image("dragon-background.jpg", (w, h)) or \
                          self.assets.get_menu_image("Background.png", (w, h))
                self.image = self.assets.get_menu_image(self.image_name, (int(w * 0.6), 160))
        return None

    def render(self, surface: pygame.Surface) -> None:
        if self.bg:
            # Scale background to fill entire screen (cover mode)
            bg_rect = self.bg.get_rect()
            screen_w, screen_h = surface.get_size()
            scale_w = screen_w / bg_rect.width
            scale_h = screen_h / bg_rect.height
            scale = max(scale_w, scale_h)
            scaled_bg = pygame.transform.smoothscale(self.bg, 
                (int(bg_rect.width * scale), int(bg_rect.height * scale)))
            scaled_rect = scaled_bg.get_rect(center=(screen_w // 2, screen_h // 2))
            surface.blit(scaled_bg, scaled_rect)
        if self.image:
            rect = self.image.get_rect(center=(self.config.window_width // 2, self.config.window_height // 2))
            surface.blit(self.image, rect)
        hint = self.font.render("Click or Press Esc to go back", True, (230, 230, 230))
        surface.blit(hint, (self.config.margin_px, self.config.window_height - 30))


class AboutUsScene:
    def __init__(self, config: AppConfig, assets: AssetManager) -> None:
        self.config = config
        self.assets = assets
        self.bg = self.assets.get_decorate_image("dragon-background.jpg", (self.config.window_width, self.config.window_height))
        if self.bg is None:
            self.bg = self.assets.get_menu_image("Background.png", (self.config.window_width, self.config.window_height))
        # Load aboutus.jpg image from Decorate directory (raw, will scale in render)
        self.about_image_raw = self._load_about_image()
        self.font = self.assets.get_font(20)
        self.small = self.assets.get_font(16)
        self._last_size = (self.config.window_width, self.config.window_height)
        self._exit_button_rect = pygame.Rect(0, 0, 0, 0)
        self._exit_button_hovered = False
        # Back to menu decorative image (raw)
        self._back_img_raw: Optional[pygame.Surface] = self._load_back_image()
        # 缩放缓存，按窗口尺寸缓存一次，避免每帧 smoothscale
        self._about_scaled_cache: Optional[Tuple[Tuple[int, int], pygame.Surface]] = None

    def _load_about_image(self) -> Optional[pygame.Surface]:
        """Load the About Us artwork from Decorate directory."""
        import os
        decorate_dir = os.path.join(".", "assets", "Decorate")
        candidates = ["aboutus.png", "aboutus.jpg"]
        for filename in candidates:
            path = os.path.join(decorate_dir, filename)
            if not os.path.exists(path):
                continue
            try:
                img = pygame.image.load(path)
                if img.get_flags() & pygame.SRCALPHA or img.get_alpha() is not None:
                    return img.convert_alpha()
                return img.convert()
            except Exception:
                continue
        return None

    def _load_back_image(self) -> Optional[pygame.Surface]:
        import os
        path = os.path.join(".", "assets", "Decorate", "backtomenu.png")
        if not os.path.exists(path):
            return None
        try:
            return pygame.image.load(path).convert_alpha()
        except Exception:
            return None

    def handle_event(self, event: pygame.event.Event):
        from scenes.menu_scene import MenuScene

        if event.type == pygame.MOUSEBUTTONDOWN:
            # Check if exit button is clicked
            if self._exit_button_rect.collidepoint(event.pos):
                return MenuScene(self.config)
            # Also allow clicking anywhere to go back (optional - can remove if only want button)
            # return MenuScene(self.config)
        elif event.type == pygame.MOUSEMOTION:
            # Update hover state for exit button
            self._exit_button_hovered = self._exit_button_rect.collidepoint(event.pos)
        elif event.type == pygame.KEYDOWN:
            # ESC key to go back
            if event.key == pygame.K_ESCAPE:
                return MenuScene(self.config)
        return None

    def update(self, dt: float):
        # Update image size if window resized
        surface = pygame.display.get_surface()
        if surface:
            w, h = surface.get_size()
            if (w, h) != self._last_size:
                self._last_size = (w, h)
                # Resize background
                self.bg = self.assets.get_decorate_image("dragon-background.jpg", (w, h))
                if self.bg is None:
                    self.bg = self.assets.get_menu_image("Background.png", (w, h))
                # 失效缩放缓存
                self._about_scaled_cache = None
        return None

    def _draw_button(self, surface: pygame.Surface, rect: pygame.Rect, text: str, hovered: bool) -> None:
        """Draw a styled button with hover effect."""
        # Button colors
        bg_color = (100, 150, 200) if hovered else (70, 100, 140)
        border_color = (150, 200, 255) if hovered else (100, 140, 180)
        text_color = (255, 255, 255)
        
        # Draw button background with rounded corners effect (using border)
        pygame.draw.rect(surface, bg_color, rect, border_radius=8)
        pygame.draw.rect(surface, border_color, rect, width=3, border_radius=8)
        
        # Draw text centered
        text_surf = self.font.render(text, True, text_color)
        text_rect = text_surf.get_rect(center=rect.center)
        surface.blit(text_surf, text_rect)
        
        # Add subtle shadow/glow effect when hovered
        if hovered:
            glow_rect = rect.inflate(4, 4)
            glow_surf = pygame.Surface((glow_rect.width, glow_rect.height), pygame.SRCALPHA)
            glow_color = (*border_color[:3], 30)
            pygame.draw.rect(glow_surf, glow_color, glow_surf.get_rect(), border_radius=10)
            surface.blit(glow_surf, glow_rect, special_flags=pygame.BLEND_ALPHA_SDL2)

    def render(self, surface: pygame.Surface) -> None:
        screen_w, screen_h = surface.get_size()
        
        # Display aboutus.jpg image full screen (cover mode)
        if self.about_image_raw:
            cache = self._about_scaled_cache
            if not cache or cache[0] != (screen_w, screen_h):
                img_w, img_h = self.about_image_raw.get_size()
                scale_w = screen_w / img_w
                scale_h = screen_h / img_h
                scale = max(scale_w, scale_h)
                new_w = max(1, int(img_w * scale))
                new_h = max(1, int(img_h * scale))
                scaled_img = pygame.transform.smoothscale(self.about_image_raw, (new_w, new_h))
                self._about_scaled_cache = ((screen_w, screen_h), scaled_img)
            scaled = self._about_scaled_cache[1]
            img_rect = scaled.get_rect(center=(screen_w // 2, screen_h // 2))
            surface.blit(scaled, img_rect)
        else:
            # Fallback to background if image not found
            if self.bg:
                bg_rect = self.bg.get_rect()
                scale_w = screen_w / bg_rect.width
                scale_h = screen_h / bg_rect.height
                scale = max(scale_w, scale_h)
                scaled_bg = pygame.transform.smoothscale(self.bg, 
                    (int(bg_rect.width * scale), int(bg_rect.height * scale)))
                scaled_rect = scaled_bg.get_rect(center=(screen_w // 2, screen_h // 2))
                surface.blit(scaled_bg, scaled_rect)
        
        # Draw Exit/Back button at bottom right corner
        # Prefer decorative image if available
        if self._back_img_raw is not None:
            # Scale by height to look good across resolutions
            target_h = max(60, int(screen_h * 0.24))  # x2 kích thước
            iw, ih = self._back_img_raw.get_size()
            scale = target_h / max(1, ih)
            draw_w = int(iw * scale)
            draw_h = int(ih * scale)
            img = pygame.transform.smoothscale(self._back_img_raw, (draw_w, draw_h))
            # Position button at bottom right corner
            margin = int(screen_h * 0.03)  # 3% of screen height from edge
            rect = img.get_rect(bottomright=(screen_w - margin, screen_h - margin))
            self._exit_button_rect = rect
            surface.blit(img, rect)
        else:
            button_width = max(200, int(screen_w * 0.15))
            button_height = 50
            # Position button at bottom right corner
            margin = int(screen_h * 0.03)  # 3% of screen height from edge
            button_x = screen_w - button_width - margin
            button_y = screen_h - button_height - margin
            self._exit_button_rect = pygame.Rect(button_x, button_y, button_width, button_height)
            self._draw_button(surface, self._exit_button_rect, "Back to Menu", self._exit_button_hovered)


class HowToPlayScene:
    def __init__(self, config: AppConfig, assets: AssetManager) -> None:
        self.config = config
        self.assets = assets
        # Load all HowToPlay images (1-4)
        self.howtoplay_images = self._load_all_howtoplay_images()
        self.current_image_index = 0  # Start with first image
        self._last_size = (self.config.window_width, self.config.window_height)
        self._exit_button_rect = pygame.Rect(0, 0, 0, 0)
        self._exit_button_hovered = False
        self._next_button_rect = pygame.Rect(0, 0, 0, 0)
        self._next_button_hovered = False
        self._prev_button_rect = pygame.Rect(0, 0, 0, 0)
        self._prev_button_hovered = False
        # Back to menu decorative image (raw)
        self._back_img_raw: Optional[pygame.Surface] = self._load_back_image()
        # Font for navigation buttons
        self.button_font = self.assets.get_font(18)
        # 按 (index, size) 缓存缩放结果，避免每帧 smoothscale
        self._scaled_cache: Dict[Tuple[int, int, int], pygame.Surface] = {}

    def _load_all_howtoplay_images(self) -> List[Optional[pygame.Surface]]:
        """Load all HowToPlay images (1-4) from Decorate directory with high quality."""
        import os
        images = []
        decorate_dir = os.path.join(".", "assets", "Decorate")
        
        for i in range(1, 5):  # Load HowToPlay1.jpg through HowToPlay4.jpg
            path = os.path.join(decorate_dir, f"HowToPlay{i}.jpg")
            if os.path.exists(path):
                try:
                    # Load image and convert for better quality
                    img = pygame.image.load(path)
                    # Convert to display format for better performance and quality
                    if img.get_flags() & pygame.SRCALPHA:
                        img = img.convert_alpha()
                    else:
                        img = img.convert()
                    images.append(img)
                except Exception:
                    images.append(None)
            else:
                images.append(None)
        
        # Filter out None values, keep only valid images
        return [img for img in images if img is not None]

    def _get_current_image(self) -> Optional[pygame.Surface]:
        """Get the current image based on index."""
        if not self.howtoplay_images or self.current_image_index >= len(self.howtoplay_images):
            return None
        return self.howtoplay_images[self.current_image_index]

    def _load_back_image(self) -> Optional[pygame.Surface]:
        import os
        # Thử load Exit.png trước, nếu không có thì dùng backtomenu.png
        path = os.path.join(".", "assets", "Decorate", "Exit.png")
        if not os.path.exists(path):
            path = os.path.join(".", "assets", "Decorate", "backtomenu.png")
        if not os.path.exists(path):
            return None
        try:
            return pygame.image.load(path).convert_alpha()
        except Exception:
            return None

    def handle_event(self, event: pygame.event.Event):
        from scenes.menu_scene import MenuScene

        if event.type == pygame.MOUSEBUTTONDOWN:
            # Check if exit button is clicked
            if self._exit_button_rect.collidepoint(event.pos):
                return MenuScene(self.config)
            # Check if next button is clicked
            elif self._next_button_rect.collidepoint(event.pos):
                if self.current_image_index < len(self.howtoplay_images) - 1:
                    self.current_image_index += 1
            # Check if previous button is clicked
            elif self._prev_button_rect.collidepoint(event.pos):
                if self.current_image_index > 0:
                    self.current_image_index -= 1
        elif event.type == pygame.MOUSEMOTION:
            # Update hover state for buttons
            self._exit_button_hovered = self._exit_button_rect.collidepoint(event.pos)
            self._next_button_hovered = self._next_button_rect.collidepoint(event.pos)
            self._prev_button_hovered = self._prev_button_rect.collidepoint(event.pos)
        elif event.type == pygame.KEYDOWN:
            # ESC key to go back
            if event.key == pygame.K_ESCAPE:
                return MenuScene(self.config)
            # Arrow keys to navigate
            elif event.key == pygame.K_RIGHT or event.key == pygame.K_n:
                if self.current_image_index < len(self.howtoplay_images) - 1:
                    self.current_image_index += 1
            elif event.key == pygame.K_LEFT or event.key == pygame.K_p:
                if self.current_image_index > 0:
                    self.current_image_index -= 1
        return None

    def update(self, dt: float):
        # Update image size if window resized
        surface = pygame.display.get_surface()
        if surface:
            w, h = surface.get_size()
            if (w, h) != self._last_size:
                self._last_size = (w, h)
                # 尺寸变化时清理缓存
                self._scaled_cache.clear()
        return None

    def render(self, surface: pygame.Surface) -> None:
        screen_w, screen_h = surface.get_size()
        
        # Display current HowToPlay image (fit mode - no overflow) with high quality
        current_image = self._get_current_image()
        img_rect = None  # Lưu rect của ảnh để dùng cho vị trí button Exit
        if current_image:
            key = (self.current_image_index, screen_w, screen_h)
            scaled_img = self._scaled_cache.get(key)
            if scaled_img is None:
                img_w, img_h = current_image.get_size()
                scale_w = screen_w / img_w
                scale_h = screen_h / img_h
                scale = min(scale_w, scale_h)
                new_w = max(1, int(img_w * scale))
                new_h = max(1, int(img_h * scale))
                scaled_img = pygame.transform.smoothscale(current_image, (new_w, new_h))
                self._scaled_cache[key] = scaled_img
            img_rect = scaled_img.get_rect(center=(screen_w // 2, screen_h // 2))
            surface.blit(scaled_img, img_rect)
        else:
            # Fallback to background if image not found
            bg = self.assets.get_decorate_image("dragon-background.jpg", (screen_w, screen_h))
            if bg is None:
                bg = self.assets.get_menu_image("Background.png", (screen_w, screen_h))
            if bg:
                bg_rect = bg.get_rect()
                scale_w = screen_w / bg_rect.width
                scale_h = screen_h / bg_rect.height
                scale = max(scale_w, scale_h)
                scaled_bg = pygame.transform.smoothscale(bg, 
                    (int(bg_rect.width * scale), int(bg_rect.height * scale)))
                scaled_rect = scaled_bg.get_rect(center=(screen_w // 2, screen_h // 2))
                surface.blit(scaled_bg, scaled_rect)
        
        # Draw navigation buttons (Next/Previous) at bottom center
        button_height = 35
        button_width = 80
        button_y = screen_h - 50
        button_spacing = 100  # Tăng khoảng cách giữa 2 nút
        
        # Previous button (only show if not on first image)
        if self.current_image_index > 0:
            prev_x = screen_w // 2 - button_width - button_spacing // 2
            self._prev_button_rect = pygame.Rect(prev_x, button_y, button_width, button_height)
            prev_color = (100, 150, 200) if self._prev_button_hovered else (70, 100, 140)
            pygame.draw.rect(surface, prev_color, self._prev_button_rect, border_radius=5)
            pygame.draw.rect(surface, (150, 200, 255), self._prev_button_rect, width=2, border_radius=5)
            prev_text = self.button_font.render("Prev", True, (255, 255, 255))
            prev_text_rect = prev_text.get_rect(center=self._prev_button_rect.center)
            surface.blit(prev_text, prev_text_rect)
        else:
            self._prev_button_rect = pygame.Rect(0, 0, 0, 0)
        
        # Next button (only show if not on last image)
        if self.current_image_index < len(self.howtoplay_images) - 1:
            next_x = screen_w // 2 + button_spacing // 2
            self._next_button_rect = pygame.Rect(next_x, button_y, button_width, button_height)
            next_color = (100, 150, 200) if self._next_button_hovered else (70, 100, 140)
            pygame.draw.rect(surface, next_color, self._next_button_rect, border_radius=5)
            pygame.draw.rect(surface, (150, 200, 255), self._next_button_rect, width=2, border_radius=5)
            next_text = self.button_font.render("Next", True, (255, 255, 255))
            next_text_rect = next_text.get_rect(center=self._next_button_rect.center)
            surface.blit(next_text, next_text_rect)
        else:
            self._next_button_rect = pygame.Rect(0, 0, 0, 0)
        
        # Draw page indicator in the center between Prev and Next buttons
        if len(self.howtoplay_images) > 1:
            page_text = self.button_font.render(
                f"{self.current_image_index + 1}/{len(self.howtoplay_images)}", 
                True, (200, 200, 200)
            )
            # Position at center of screen, between the two buttons
            page_x = screen_w // 2
            page_y = button_y + button_height // 2
            page_rect = page_text.get_rect(center=(page_x, page_y))
            surface.blit(page_text, page_rect)
        
        # Draw Exit/Back button at top center, phía trên giữa ảnh, trên tất cả các trang
        if self._back_img_raw is not None and len(self.howtoplay_images) > 0:
            target_h = max(60, int(screen_h * 0.24))
            iw, ih = self._back_img_raw.get_size()
            scale = target_h / max(1, ih)
            draw_w = int(iw * scale)
            draw_h = int(ih * scale)
            # Use smoothscale for better quality
            if draw_w > 0 and draw_h > 0:
                img = pygame.transform.smoothscale(self._back_img_raw, (draw_w, draw_h))
            else:
                img = self._back_img_raw
            
            # Position at top center, dời lên 40% chiều cao button, dời sang trái 5%
            # Đặt button căn giữa theo chiều ngang, dời lên 40% so với mép trên, dời sang trái 5%
            margin_top = -int(draw_h * 0.4)  # Dời lên 40% chiều cao button (thêm 30%)
            margin_left = -int(screen_w * 0.05)  # Dời sang trái 5% chiều rộng màn hình
            
            # Vùng chọn button thu nhỏ hơn ảnh để dễ click chính xác
            rect = img.get_rect(midtop=(screen_w // 2 + margin_left, margin_top))
            # Thu nhỏ vùng chọn: chỉ lấy phần text panel ở giữa (khoảng 35% chiều cao)
            button_click_height = int(draw_h * 0.35)  # 35% chiều cao (giảm 25% so với 60%)
            button_click_y_offset = int(draw_h * 0.38)  # Bắt đầu từ 38% từ trên xuống (dời xuống thêm 0.5%)
            button_click_width = int(draw_w * 0.8)  # Thu nhỏ chiều rộng xuống 80%
            self._exit_button_rect = pygame.Rect(
                rect.centerx - button_click_width // 2,  # Căn giữa với chiều rộng mới
                rect.top + button_click_y_offset,  # Bắt đầu từ phần text panel
                button_click_width,  # Chiều rộng thu nhỏ
                button_click_height  # Chỉ phần text panel, bỏ phần dưới
            )
            surface.blit(img, rect)
            
            # Ẩn highlight khi hover - không vẽ gì cả
            # if self._exit_button_hovered:
            #     highlight = pygame.Surface((self._exit_button_rect.width, self._exit_button_rect.height), pygame.SRCALPHA)
            #     highlight.fill((255, 255, 255, 40))  # Màu trắng mờ với độ trong suốt
            #     surface.blit(highlight, self._exit_button_rect)
        else:
            # Hide exit button if image not loaded
            self._exit_button_rect = pygame.Rect(0, 0, 0, 0)


def calculate_rankings(results_file: str) -> List[Dict[str, any]]:
    """Tính toán ranking theo quy tắc mới:
    - Ranking Points = TotalWins × 100
    - EffectiveScore = max(0, TotalWins − (TotalUndo + TotalHint))
    - Tiebreakers: Higher EffectiveScore, Fewer Undo/Hint, Faster avg time, Earlier registration
    """
    import os
    import json
    
    player_stats: Dict[str, Dict[str, any]] = {}
    # Load registered users
    users_path = os.path.join(".", "data", "users.json")
    users = {}
    registered_users = set()
    
    try:
        if os.path.exists(users_path):
            with open(users_path, "r", encoding="utf-8") as f:
                users = json.load(f)
                registered_users = set(users.keys())
                # Initialize stats for all registered users if not exists
                for username in registered_users:
                    if 'wins' not in users[username]:
                        users[username]['wins'] = 0
                        users[username]['total_games'] = 0
                        users[username]['win_rate'] = 0.0
                    if 'registration_date' not in users[username]:
                        # Nếu không có registration_date, dùng thời gian hiện tại (người chơi cũ)
                        import time
                        users[username]['registration_date'] = time.time()
    except Exception as e:
        print(f"Error loading users.json: {e}")
        users = {}
        registered_users = set()
    
    # Calculate stats from match results
    try:
        if os.path.exists(results_file):
            with open(results_file, 'r', encoding='utf-8') as f:
                matches = json.load(f)
                
            for match in matches:
                # 只统计已完成的比赛（有winner）
                if match.get('winner') is None:
                    continue
                    
                # Get account (preferred) or name as fallback
                account = match.get('player_human', {}).get('account', '').strip()
                player_name = match.get('player_human', {}).get('name', '').strip()
                
                # Determine the username to use: prioritize account, fallback to name if it's a registered user
                username = None
                if account and account in registered_users:
                    username = account
                elif player_name and player_name in registered_users:
                    username = player_name
                
                # Skip if not a registered user
                if not username:
                    continue
                
                # Initialize player stats if not exists
                if username not in player_stats:
                    player_stats[username] = {
                        'total_wins': 0,  # RAW wins (không phải effective)
                        'total_undo': 0,
                        'total_hint': 0,
                        'total_move_times': [],  # List để tính average
                        'total_sets': 0,
                    }
                
                # Lấy RAW wins (không phải effective wins)
                wins_human = match.get('wins_human', 0)
                player_stats[username]['total_wins'] += wins_human
                
                # Lấy penalties
                penalties = match.get('penalties', {})
                human_penalties = penalties.get('human', {})
                player_stats[username]['total_undo'] += human_penalties.get('undo', 0)
                player_stats[username]['total_hint'] += human_penalties.get('hint', 0)
                
                # Lấy average move time (nếu có)
                avg_move_time = match.get('average_move_time', 0.0)
                if avg_move_time > 0:
                    player_stats[username]['total_move_times'].append(avg_move_time)
                
                player_stats[username]['total_sets'] += 1
                    
    except Exception as e:
        print(f"Error calculating rankings: {e}")
    
    # Tính toán ranking points và effective scores
    rankings = []
    for username, stats in player_stats.items():
        total_wins = stats['total_wins']
        total_undo = stats['total_undo']
        total_hint = stats['total_hint']
        
        # Ranking Points = TotalWins × 100
        ranking_points = total_wins * 100
        
        # EffectiveScore = max(0, TotalWins − (TotalUndo + TotalHint))
        effective_score = max(0, total_wins - (total_undo + total_hint))
        
        # Tính average move time
        move_times = stats['total_move_times']
        avg_move_time = sum(move_times) / len(move_times) if move_times else None
        
        # Lấy registration date
        registration_date = users.get(username, {}).get('registration_date', None)
        
        rankings.append({
            'name': username,
            'wins': total_wins,  # RAW wins
            'undo_used': total_undo,
            'hint_used': total_hint,
            'effective_score': effective_score,
            'ranking_points': ranking_points,
            'average_move_time': avg_move_time,
            'registration_date': registration_date,
            'total_sets': stats['total_sets'],
        })
    
    # Sort theo quy tắc:
    # 1. Ranking Points (descending)
    # 2. Effective Score (descending)
    # 3. Fewer Undo/Hint (ascending - ít hơn tốt hơn)
    # 4. Faster average move time (ascending - nhanh hơn tốt hơn)
    # 5. Earlier registration date (ascending - đăng ký sớm hơn tốt hơn)
    rankings.sort(key=lambda x: (
        -x['ranking_points'],  # Descending
        -x['effective_score'],  # Descending
        x['undo_used'] + x['hint_used'],  # Ascending (ít hơn tốt hơn)
        x['average_move_time'] if x['average_move_time'] is not None else float('inf'),  # Ascending (nhanh hơn tốt hơn)
        x['registration_date'] if x['registration_date'] is not None else float('inf'),  # Ascending (sớm hơn tốt hơn)
    ))
    
    # Update users.json với ranking points và effective score
    try:
        updated = False
        for rank_data in rankings:
            username = rank_data['name']
            if username in users:
                users[username]['ranking_points'] = rank_data['ranking_points']
                users[username]['effective_score'] = rank_data['effective_score']
                users[username]['total_undo'] = rank_data['undo_used']
                users[username]['total_hint'] = rank_data['hint_used']
                users[username]['average_move_time'] = rank_data['average_move_time']
                updated = True
        
        if updated and os.path.exists(users_path):
            # Thay thế Infinity/None bằng null trước khi lưu JSON
            for username in users:
                if 'average_move_time' in users[username]:
                    if users[username]['average_move_time'] == float('inf') or users[username]['average_move_time'] is None:
                        users[username]['average_move_time'] = None
            with open(users_path, 'w', encoding='utf-8') as f:
                json.dump(users, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error updating users.json: {e}")
    
    return rankings[:10]  # 只返回前10名


class RankingsScene:
    def __init__(self, config: AppConfig, assets: AssetManager) -> None:
        self.config = config
        self.assets = assets
        self.bg = self.assets.get_decorate_image("dragon-background.jpg", (self.config.window_width, self.config.window_height))
        if self.bg is None:
            self.bg = self.assets.get_menu_image("Background.png", (self.config.window_width, self.config.window_height))
        # Load Ranking.png image from Decorate directory (raw, will scale in render)
        self.ranking_image_raw = self._load_ranking_image()
        # 字体设置 - 使用更大的字体用于排名显示
        self.title_font = self.assets.get_font(32)
        self.rank_font = self.assets.get_font(22)   # slightly larger
        self.player_font = self.assets.get_font(20) # slightly larger
        self.stats_font = self.assets.get_font(18)  # slightly larger
        self.small = self.assets.get_font(16)
        self._last_size = (self.config.window_width, self.config.window_height)
        self._exit_button_rect = pygame.Rect(0, 0, 0, 0)
        self._exit_button_hovered = False
        # 计算排名数据
        self.rankings = calculate_rankings(self.config.results_json)
        # Back to menu decorative image (raw)
        self._back_img_raw: Optional[pygame.Surface] = self._load_back_image()

        # Cache cho rendering optimization
        self._text_cache: dict = {}  # Cache cho text surfaces
        self._header_cache: Optional[pygame.Surface] = None  # Cache cho header
        self._layout_cache: Optional[dict] = None  # Cache cho layout positions
        self._cached_screen_size: Optional[tuple] = None  # Track screen size for cache invalidation
        self._scaled_bg_cache: Optional[pygame.Surface] = None  # Cache cho scaled background
        self._scaled_ranking_img_cache: Optional[pygame.Surface] = None  # Cache cho scaled ranking image
        self._scaled_back_img_cache: Optional[pygame.Surface] = None  # Cache cho scaled back button image
        self._ranking_rows_cache: dict = {}  # Cache cho ranking row surfaces
        self._gradient_cache: dict = {}  # Cache cho gradient surfaces
        self._row_bg_cache: dict = {}  # Cache cho row background surfaces

    def _get_cached_text(self, font: pygame.font.Font, text: str, color: Tuple[int,int,int]) -> Tuple[pygame.Surface, pygame.Surface]:
        """Get cached text surfaces (shadow and main)."""
        cache_key = (id(font), text, color)
        if cache_key not in self._text_cache:
            shadow = font.render(text, True, (0, 0, 0))
            main = font.render(text, True, color)
            self._text_cache[cache_key] = (shadow, main)
        return self._text_cache[cache_key]
    
    def _blit_emphasized_text(self, surface: pygame.Surface, font: pygame.font.Font, text: str, color: Tuple[int,int,int], x: int, y: int, align_right: bool = False, align_center: bool = False) -> None:
        """Draw readable, standout text: subtle shadow + soft glow. Optimized with caching."""
        shadow, main = self._get_cached_text(font, text, color)
        
        if align_right:
            # Right-align: adjust x position
            x = x - main.get_width()
        elif align_center:
            # Center-align: adjust x position
            x = x - main.get_width() // 2
        
        surface.blit(shadow, (x + 2, y + 2))
        surface.blit(main, (x, y))
    
    def _draw_gradient_rect(self, surface: pygame.Surface, rect: pygame.Rect, color1: Tuple[int,int,int], color2: Tuple[int,int,int], vertical: bool = True) -> None:
        """Draw a gradient rectangle. Cached for performance."""
        cache_key = (rect.width, rect.height, color1, color2, vertical)
        if cache_key not in self._gradient_cache:
            grad_surf = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
            if vertical:
                for y in range(rect.height):
                    ratio = y / max(1, rect.height - 1)
                    r = int(color1[0] * (1 - ratio) + color2[0] * ratio)
                    g = int(color1[1] * (1 - ratio) + color2[1] * ratio)
                    b = int(color1[2] * (1 - ratio) + color2[2] * ratio)
                    pygame.draw.line(grad_surf, (r, g, b), (0, y), (rect.width, y))
            else:
                for x in range(rect.width):
                    ratio = x / max(1, rect.width - 1)
                    r = int(color1[0] * (1 - ratio) + color2[0] * ratio)
                    g = int(color1[1] * (1 - ratio) + color2[1] * ratio)
                    b = int(color1[2] * (1 - ratio) + color2[2] * ratio)
                    pygame.draw.line(grad_surf, (r, g, b), (x, 0), (x, rect.height))
            self._gradient_cache[cache_key] = grad_surf
        surface.blit(self._gradient_cache[cache_key], rect)
    
    def _get_row_background(self, rank: int, width: int, height: int) -> pygame.Surface:
        """Get cached row background surface - đơn giản hóa để dễ đọc."""
        cache_key = (rank, width, height)
        if cache_key not in self._row_bg_cache:
            row_surf = pygame.Surface((width, height), pygame.SRCALPHA)
            
            if rank == 1:  # Gold - solid color nhẹ
                row_surf.fill((255, 240, 200, 220))  # Light gold với opacity
                border_color = (255, 200, 100)
            elif rank == 2:  # Silver - solid color nhẹ
                row_surf.fill((240, 240, 240, 220))  # Light silver với opacity
                border_color = (200, 200, 200)
            elif rank == 3:  # Bronze - solid color nhẹ
                row_surf.fill((255, 220, 180, 220))  # Light bronze với opacity
                border_color = (255, 180, 120)
            else:  # White với opacity cao hơn
                row_surf.fill((255, 255, 255, 240))  # White với opacity cao
                border_color = (220, 220, 220)
            
            # Draw border nhẹ
            pygame.draw.rect(row_surf, border_color, row_surf.get_rect(), width=1, border_radius=6)
            
            self._row_bg_cache[cache_key] = row_surf
        return self._row_bg_cache[cache_key]
    
    def _get_cached_layout(self, screen_w: int, screen_h: int) -> dict:
        """Get cached layout positions."""
        if self._layout_cache is None or self._cached_screen_size != (screen_w, screen_h):
            ranking_area_x = int(screen_w * 0.63)  # Vị trí ranking (63% chiều rộng màn hình)
            ranking_area_y = int(screen_h * 0.35)
            ranking_area_width = int(screen_w * 0.30)
            ranking_area_height = int(screen_h * 0.56)
            
            # Tính toán center positions cho các cột - sát lại cột số thứ tự
            col_width_1 = 30   # Rank column width
            col_width_2 = 100  # Name column width
            col_width_3 = 60   # Point column width
            col_width_4 = 50   # Match column width
            col_width_5 = 50   # Win column width
            
            # Các cột sát nhau, bắt đầu từ ranking_area_x + 10
            col1_center = ranking_area_x + 10 + col_width_1 // 2   # Rank center
            col2_center = ranking_area_x + 10 + col_width_1 + 5 + col_width_2 // 2  # Name center (sát Rank)
            col3_center = ranking_area_x + 10 + col_width_1 + 5 + col_width_2 + 5 + col_width_3 // 2 # Point center
            col4_center = ranking_area_x + 10 + col_width_1 + 5 + col_width_2 + 5 + col_width_3 + 5 + col_width_4 // 2 # Match center
            col5_center = ranking_area_x + 10 + col_width_1 + 5 + col_width_2 + 5 + col_width_3 + 5 + col_width_4 + 5 + col_width_5 // 2 # Win center
            
            self._layout_cache = {
                'ranking_area_x': ranking_area_x,
                'ranking_area_y': ranking_area_y,
                'ranking_area_width': ranking_area_width,
                'ranking_area_height': ranking_area_height,
                'col1_x': col1_center,  # Center position
                'col2_x': col2_center,  # Center position
                'col3_x': col3_center,  # Center position
                'col4_x': col4_center,  # Center position
                'col5_x': col5_center,  # Center position
            }
            self._cached_screen_size = (screen_w, screen_h)
        return self._layout_cache
    
    def _get_cached_header(self, screen_w: int, screen_h: int) -> Optional[pygame.Surface]:
        """Get cached header surface với highlight effect và hover cho "Win"."""
        # Cache key bao gồm hover state
        cache_key = (screen_w, screen_h)
        if self._header_cache is None or self._cached_screen_size != cache_key:
            layout = self._get_cached_layout(screen_w, screen_h)
            header_font = self.rank_font  # Dùng font lớn hơn để nổi bật
            header_color = (255, 255, 100)  # Vàng sáng để nổi bật
            header_texts = ["", "Name", "Point", "Match", "Win"]
            header_positions = [layout['col1_x'], layout['col2_x'], layout['col3_x'], layout['col4_x'], layout['col5_x']]
            
            # Tạo header surface với width đủ lớn và padding
            max_width = max(layout['col5_x'] + 100, 400)
            header_height = header_font.get_height() + 20  # Extra padding for highlight
            self._header_cache = pygame.Surface((max_width, header_height), pygame.SRCALPHA)
            
            # Vẽ header text nổi bật với shadow đậm và glow effect
            for text, x_pos in zip(header_texts, header_positions):
                if text:
                    # x_pos đã là center position từ layout
                    offset_x = x_pos - layout['ranking_area_x']
                    # Tạo text với shadow đậm hơn và glow effect
                    # Shadow layer 1 (đậm nhất, xa nhất)
                    shadow1_surf = header_font.render(text, True, (0, 0, 0))
                    # Shadow layer 2 (trung bình)
                    shadow2_surf = header_font.render(text, True, (50, 50, 50))
                    # Main text với màu vàng sáng
                    main_surf = header_font.render(text, True, header_color)
                    # Center align
                    text_width = main_surf.get_width()
                    text_x = offset_x - text_width // 2
                    # Vẽ nhiều lớp shadow để tạo hiệu ứng nổi bật
                    # Shadow layer 1 (đen, xa nhất)
                    self._header_cache.blit(shadow1_surf, (text_x + 3, 12))
                    # Shadow layer 2 (xám đậm)
                    self._header_cache.blit(shadow2_surf, (text_x + 2, 11))
                    # Main text (vàng sáng)
                    self._header_cache.blit(main_surf, (text_x, 9))
            
            self._cached_screen_size = cache_key
        return self._header_cache

    def _load_ranking_image(self) -> Optional[pygame.Surface]:
        """Load Ranking.png from Decorate directory."""
        import os
        decorate_dir = os.path.join(".", "assets", "Decorate")
        path = os.path.join(decorate_dir, "Ranking.png")
        if not os.path.exists(path):
            return None
        try:
            img = pygame.image.load(path).convert_alpha()
            return img
        except Exception:
            return None

    def _load_back_image(self) -> Optional[pygame.Surface]:
        import os
        path = os.path.join(".", "assets", "Decorate", "backtomenu.png")
        if not os.path.exists(path):
            return None
        try:
            return pygame.image.load(path).convert_alpha()
        except Exception:
            return None

    def handle_event(self, event: pygame.event.Event):
        from scenes.menu_scene import MenuScene

        if event.type == pygame.MOUSEBUTTONDOWN:
            # Check if exit button is clicked
            if self._exit_button_rect.collidepoint(event.pos):
                return MenuScene(self.config)
        elif event.type == pygame.MOUSEMOTION:
            # Update hover state for exit button
            self._exit_button_hovered = self._exit_button_rect.collidepoint(event.pos)
        elif event.type == pygame.KEYDOWN:
            # ESC key to go back
            if event.key == pygame.K_ESCAPE:
                return MenuScene(self.config)
        return None

    def update(self, dt: float):
        # Update image size if window resized
        surface = pygame.display.get_surface()
        if surface:
            w, h = surface.get_size()
            if (w, h) != self._last_size:
                self._last_size = (w, h)
                # Resize background
                self.bg = self.assets.get_decorate_image("dragon-background.jpg", (w, h))
                if self.bg is None:
                    self.bg = self.assets.get_menu_image("Background.png", (w, h))
                # 重新加载排名图片
                self.ranking_image_raw = self._load_ranking_image()
                # 重新计算排名
                self.rankings = calculate_rankings(self.config.results_json)
                # Invalidate caches khi screen size thay đổi
                self._scaled_bg_cache = None
                self._scaled_ranking_img_cache = None
                self._scaled_back_img_cache = None
                self._header_cache = None
                self._layout_cache = None
                self._ranking_rows_cache = {}
                self._cached_screen_size = None
        return None

    def _draw_button(self, surface: pygame.Surface, rect: pygame.Rect, text: str, hovered: bool) -> None:
        """Draw a styled button with hover effect."""
        # Button colors
        bg_color = (100, 150, 200) if hovered else (70, 100, 140)
        border_color = (150, 200, 255) if hovered else (100, 140, 180)
        text_color = (255, 255, 255)
        
        # Draw button background with rounded corners effect (using border)
        pygame.draw.rect(surface, bg_color, rect, border_radius=8)
        pygame.draw.rect(surface, border_color, rect, width=3, border_radius=8)
        
        # Draw text centered - 使用 player_font
        text_surf = self.player_font.render(text, True, text_color)
        text_rect = text_surf.get_rect(center=rect.center)
        surface.blit(text_surf, text_rect)
        
        # Add subtle shadow/glow effect when hovered
        if hovered:
            glow_rect = rect.inflate(4, 4)
            glow_surf = pygame.Surface((glow_rect.width, glow_rect.height), pygame.SRCALPHA)
            glow_color = (*border_color[:3], 30)
            pygame.draw.rect(glow_surf, glow_color, glow_surf.get_rect(), border_radius=10)
            surface.blit(glow_surf, glow_rect, special_flags=pygame.BLEND_ALPHA_SDL2)

    def render(self, surface: pygame.Surface) -> None:
        screen_w, screen_h = surface.get_size()
        
        # Cache và hiển thị background image (cover mode)
        if self.ranking_image_raw:
            if self._scaled_ranking_img_cache is None or self._cached_screen_size != (screen_w, screen_h):
                img_w, img_h = self.ranking_image_raw.get_size()
                scale_w = screen_w / img_w
                scale_h = screen_h / img_h
                scale = max(scale_w, scale_h)
                new_w = int(img_w * scale)
                new_h = int(img_h * scale)
                self._scaled_ranking_img_cache = pygame.transform.smoothscale(self.ranking_image_raw, (new_w, new_h))
                self._cached_screen_size = (screen_w, screen_h)
            
            img_rect = self._scaled_ranking_img_cache.get_rect(center=(screen_w // 2, screen_h // 2))
            surface.blit(self._scaled_ranking_img_cache, img_rect)
        else:
            # Fallback to background if image not found
            if self.bg:
                if self._scaled_bg_cache is None or self._cached_screen_size != (screen_w, screen_h):
                    bg_rect = self.bg.get_rect()
                    scale_w = screen_w / bg_rect.width
                    scale_h = screen_h / bg_rect.height
                    scale = max(scale_w, scale_h)
                    self._scaled_bg_cache = pygame.transform.smoothscale(self.bg, 
                        (int(bg_rect.width * scale), int(bg_rect.height * scale)))
                    self._cached_screen_size = (screen_w, screen_h)
                scaled_rect = self._scaled_bg_cache.get_rect(center=(screen_w // 2, screen_h // 2))
                surface.blit(self._scaled_bg_cache, scaled_rect)
        
        # Lấy cached layout positions
        layout = self._get_cached_layout(screen_w, screen_h)
        ranking_area_x = layout['ranking_area_x']
        ranking_area_y = layout['ranking_area_y']
        ranking_area_width = layout['ranking_area_width']
        ranking_area_height = layout['ranking_area_height']
        col1_x = layout['col1_x']
        col2_x = layout['col2_x']
        col3_x = layout['col3_x']
        col4_x = layout['col4_x']
        col5_x = layout['col5_x']
        
        # Vẽ cached header
        header_y = ranking_area_y
        header_font = self.stats_font
        header_surf = self._get_cached_header(screen_w, screen_h)
        if header_surf:
            surface.blit(header_surf, (ranking_area_x, header_y))
        
        # 绘制排名列表
        y_offset = header_y + header_font.get_height() + 10  # Spacing sau header
        row_height = (ranking_area_height - (y_offset - ranking_area_y)) // 10  # 为10个玩家留空间
        
        # 绘制排名条目 - Format: Rank | Name | Point | Match | Win
        for idx, player in enumerate(self.rankings[:10], 1):
            if y_offset + row_height > ranking_area_y + ranking_area_height:
                break
                
            # Text colors - Hạng 1 vàng đầy đủ, Hạng 2 bạc, Hạng 3 đồng
            if idx == 1:  # Top 1 - Gold (tất cả thông tin vàng)
                rank_color = (255, 215, 0)  # Gold
                name_color = (255, 215, 0)  # Gold
                text_color = (255, 215, 0)  # Gold
                points_color = (255, 215, 0)  # Gold
                match_color = (255, 215, 0)  # Gold
                win_color = (255, 215, 0)  # Gold
            elif idx == 2:  # Top 2 - Silver (tất cả thông tin bạc)
                rank_color = (192, 192, 192)  # Silver
                name_color = (192, 192, 192)  # Silver
                text_color = (192, 192, 192)  # Silver
                points_color = (192, 192, 192)  # Silver
                match_color = (192, 192, 192)  # Silver
                win_color = (192, 192, 192)  # Silver
            elif idx == 3:  # Top 3 - Bronze (tất cả thông tin đồng)
                rank_color = (205, 127, 50)  # Bronze
                name_color = (205, 127, 50)  # Bronze
                text_color = (205, 127, 50)  # Bronze
                points_color = (205, 127, 50)  # Bronze
                match_color = (205, 127, 50)  # Bronze
                win_color = (205, 127, 50)  # Bronze
            else:  # Các rank khác
                rank_color = (200, 200, 200)  # Light gray
                name_color = (255, 255, 255)  # White
                text_color = (255, 255, 255)  # White
                points_color = (220, 180, 0)  # Yellow đậm cho dễ đọc
                match_color = (255, 255, 255)  # White
                win_color = (0, 180, 0)  # Green đậm cho dễ đọc
            
            # 1. Rank (center-aligned, larger font for top 3)
            rank_text = str(idx)
            rank_font_to_use = self.rank_font if idx <= 3 else self.stats_font
            self._blit_emphasized_text(surface, rank_font_to_use, rank_text, rank_color, col1_x, y_offset, align_center=True)
            
            # 2. Name (center-aligned)
            name_text = player.get('name', 'Unknown')[:12]  # 限制长度
            self._blit_emphasized_text(surface, self.player_font, name_text, name_color, col2_x, y_offset, align_center=True)
            
            # 3. Point (Ranking Points) - center-aligned
            points = player.get('ranking_points', 0)
            points_text = str(points)
            self._blit_emphasized_text(surface, self.stats_font, points_text, points_color, col3_x, y_offset, align_center=True)
            
            # 4. Match (Total Sets) - center-aligned
            total_sets = player.get('total_sets', 0)
            match_text = str(total_sets)
            self._blit_emphasized_text(surface, self.stats_font, match_text, match_color, col4_x, y_offset, align_center=True)
            
            # 5. Win (Total Wins) - center-aligned
            wins = player.get('wins', 0)
            win_text = str(wins)
            self._blit_emphasized_text(surface, self.stats_font, win_text, win_color, col5_x, y_offset, align_center=True)
            
            y_offset += row_height
        
        # 如果没有排名数据，显示提示
        if not self.rankings:
            no_data_text = "No ranking data yet"
            no_data_surf = self.player_font.render(no_data_text, True, (180, 150, 120))
            text_rect = no_data_surf.get_rect(center=(ranking_area_x + ranking_area_width // 2, 
                                                       ranking_area_y + ranking_area_height // 2))
            surface.blit(no_data_surf, text_rect)
        
        # Draw Exit/Back button với cache
        if self._back_img_raw is not None:
            target_h = max(60, int(screen_h * 0.291))
            if self._scaled_back_img_cache is None or self._cached_screen_size != (screen_w, screen_h):
                iw, ih = self._back_img_raw.get_size()
                scale = target_h / max(1, ih)
                draw_w = int(iw * scale)
                draw_h = int(ih * scale)
                self._scaled_back_img_cache = pygame.transform.smoothscale(self._back_img_raw, (draw_w, draw_h))
                self._cached_screen_size = (screen_w, screen_h)
            
            rect = self._scaled_back_img_cache.get_rect(midbottom=(int(screen_w * 0.77), screen_h - 20))
            self._exit_button_rect = rect
            surface.blit(self._scaled_back_img_cache, rect)
        else:
            button_width = max(200, int(screen_w * 0.182))
            button_height = int(50 * 1.213)
            button_x = int(screen_w * 0.77) - button_width // 2
            button_y = screen_h - 80
            self._exit_button_rect = pygame.Rect(button_x, button_y, button_width, button_height)
            self._draw_button(surface, self._exit_button_rect, "Back to Menu", self._exit_button_hovered)


class RegisterScene:
    def __init__(self, config: AppConfig, assets: AssetManager) -> None:
        self.config = config
        self.assets = assets
        # Background: use Register.png full image (button + bg are one image)
        self.bg = None
        try:
            path = os.path.join(".", "assets", "Decorate", "Register.png")
            if os.path.exists(path):
                self.bg = pygame.image.load(path).convert()
        except Exception:
            self.bg = None
        self.font = assets.get_font(28)
        self.small = assets.get_font(20)
        self._last_size = (config.window_width, config.window_height)
        # Fields
        self.active_field = None  # "account"|"password"|"confirm"|"email"
        self.account = ""
        self.password = ""
        self.confirm = ""
        self.email = ""
        # Rects
        self._rects = {
            "account": pygame.Rect(0, 0, 0, 0),
            "password": pygame.Rect(0, 0, 0, 0),
            "confirm": pygame.Rect(0, 0, 0, 0),
            "submit": pygame.Rect(0, 0, 0, 0),
            "back": pygame.Rect(0, 0, 0, 0),
        }
        # Cursor blink timer for real-time text display
        self.cursor_timer: float = 0.0
        self.cursor_visible: bool = True

    def handle_event(self, event: pygame.event.Event):
        from scenes.menu_scene import LoginScene
        if event.type == pygame.VIDEORESIZE:
            self._last_size = (event.w, event.h)
        elif event.type == pygame.MOUSEBUTTONDOWN:
            pos = event.pos
            field_clicked = False
            for key, rect in self._rects.items():
                if rect.collidepoint(pos):
                    if key in ("submit", "back"):
                        break
                    self.active_field = key
                    # Reset cursor when clicking on field
                    self.cursor_timer = 0.0
                    self.cursor_visible = True
                    # Enable text input for better real-time display
                    try:
                        pygame.key.start_text_input()
                    except:
                        pass
                    field_clicked = True
                    return None
            if self._rects["submit"].collidepoint(pos):
                # Persist account using core.auth
                if self.account.strip() and self.password and self.password == self.confirm:
                    try:
                        from core.auth import register
                        register(self.account.strip(), self.password)
                    except Exception:
                        pass
                return LoginScene(self.config, self.assets)
            if self._rects["back"].collidepoint(pos):
                return LoginScene(self.config, self.assets)
            if not field_clicked:
                # Click outside fields - deactivate
                self.active_field = None
                # Stop text input when deactivating
                try:
                    pygame.key.stop_text_input()
                except:
                    pass
        elif event.type == pygame.TEXTINPUT:
            # Handle text input for better real-time display
            if self.active_field in ("account", "password", "confirm"):
                ch = event.text
                if ch:
                    if self.active_field == "account":
                        self.account += ch
                    elif self.active_field == "password":
                        self.password += ch
                    elif self.active_field == "confirm":
                        self.confirm += ch
                    # Reset cursor to visible when typing
                    self.cursor_timer = 0.0
                    self.cursor_visible = True
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                return LoginScene(self.config, self.assets)
            elif event.key == pygame.K_BACKSPACE:
                # Chỉ xử lý BACKSPACE, text input được xử lý bởi TEXTINPUT event
                if self.active_field in ("account", "password", "confirm"):
                    if self.active_field == "account":
                        self.account = self.account[:-1] if self.account else ""
                    elif self.active_field == "password":
                        self.password = self.password[:-1] if self.password else ""
                    elif self.active_field == "confirm":
                        self.confirm = self.confirm[:-1] if self.confirm else ""
                    # Reset cursor when deleting
                    self.cursor_timer = 0.0
                    self.cursor_visible = True
        return None

    def update(self, dt: float):
        # Update cursor blink for real-time text display
        if self.active_field:
            self.cursor_timer += dt
            if self.cursor_timer >= 0.5:  # Blink every 0.5 seconds
                self.cursor_timer = 0.0
                self.cursor_visible = not self.cursor_visible
        else:
            self.cursor_timer = 0.0
            self.cursor_visible = True
        return None

    def render(self, surface: pygame.Surface) -> None:
        w, h = surface.get_size()
        if self.bg:
            bw, bh = self.bg.get_size()
            scale = max(w / bw, h / bh)
            scaled = pygame.transform.smoothscale(self.bg, (int(bw * scale), int(bh * scale)))
            surface.blit(scaled, scaled.get_rect(center=(w // 2, h // 2)))
        else:
            surface.fill((12, 12, 16))
        # Hot areas matching Register.png layout (all UI is inside the image)
        panel_cx = int(w * 0.755)
        field_w = int(w * 0.30)
        field_h = int(h * 0.058)
        # Centers estimated from the mock: Account / Password / Confirm password
        centers = {
            "account": (panel_cx, int(h * 0.360)),   # move up additional 1%
            "password": (panel_cx, int(h * 0.495)),  # -1.5% (move up)
            "confirm": (panel_cx, int(h * 0.635)),   # giữ nguyên
        }
        for key, (cx, cy) in centers.items():
            rect = pygame.Rect(0, 0, field_w, field_h)
            rect.center = (cx, cy)
            self._rects[key] = rect

        # Draw values/placeholder only (no frames) - Real-time display with cursor
        val_color = (240, 240, 245)
        # Account
        acct_x = self._rects["account"].x + 18
        acct_y = self._rects["account"].centery
        if self.account:
            txt = self.small.render(self.account, True, val_color)
            txt_rect = txt.get_rect(midleft=(acct_x, acct_y))
            surface.blit(txt, txt_rect)
            # Draw blinking cursor if account field is active
            if self.active_field == "account" and self.cursor_visible:
                cursor_x = txt_rect.right + 2
                pygame.draw.line(surface, val_color, (cursor_x, acct_y - 10), (cursor_x, acct_y + 10), 2)
        else:
            txt = self.small.render("Account", True, (220, 210, 195))
            txt.set_alpha(120)
            txt_rect = txt.get_rect(midleft=(acct_x, acct_y))
            surface.blit(txt, txt_rect)
            # Draw blinking cursor if account field is active and empty
            if self.active_field == "account" and self.cursor_visible:
                cursor_x = txt_rect.left
                pygame.draw.line(surface, val_color, (cursor_x, acct_y - 10), (cursor_x, acct_y + 10), 2)
        
        # Password
        pwd_x = self._rects["password"].x + 18
        pwd_y = self._rects["password"].centery
        if self.password:
            txt = self.small.render("•" * len(self.password), True, val_color)
            txt_rect = txt.get_rect(midleft=(pwd_x, pwd_y))
            surface.blit(txt, txt_rect)
            # Draw blinking cursor if password field is active
            if self.active_field == "password" and self.cursor_visible:
                cursor_x = txt_rect.right + 2
                pygame.draw.line(surface, val_color, (cursor_x, pwd_y - 10), (cursor_x, pwd_y + 10), 2)
        else:
            txt = self.small.render("Password", True, (220, 210, 195))
            txt.set_alpha(120)
            txt_rect = txt.get_rect(midleft=(pwd_x, pwd_y))
            surface.blit(txt, txt_rect)
            # Draw blinking cursor if password field is active and empty
            if self.active_field == "password" and self.cursor_visible:
                cursor_x = txt_rect.left
                pygame.draw.line(surface, val_color, (cursor_x, pwd_y - 10), (cursor_x, pwd_y + 10), 2)
        
        # Confirm
        conf_x = self._rects["confirm"].x + 18
        conf_y = self._rects["confirm"].centery
        if self.confirm:
            txt = self.small.render("•" * len(self.confirm), True, val_color)
            txt_rect = txt.get_rect(midleft=(conf_x, conf_y))
            surface.blit(txt, txt_rect)
            # Draw blinking cursor if confirm field is active
            if self.active_field == "confirm" and self.cursor_visible:
                cursor_x = txt_rect.right + 2
                pygame.draw.line(surface, val_color, (cursor_x, conf_y - 10), (cursor_x, conf_y + 10), 2)
        else:
            txt = self.small.render("Confirm password", True, (220, 210, 195))
            txt.set_alpha(120)
            txt_rect = txt.get_rect(midleft=(conf_x, conf_y))
            surface.blit(txt, txt_rect)
            # Draw blinking cursor if confirm field is active and empty
            if self.active_field == "confirm" and self.cursor_visible:
                cursor_x = txt_rect.left
                pygame.draw.line(surface, val_color, (cursor_x, conf_y - 10), (cursor_x, conf_y + 10), 2)

        # Click areas: blue orb "REGISTER" and optional back area (text)
        submit = pygame.Rect(0, 0, int(w * 0.14), int(h * 0.14))
        back = pygame.Rect(0, 0, int(w * 0.12), int(h * 0.06))
        submit.center = (int(w * 0.742), int(h * 0.745))
        back.center = (int(w * 0.67), int(h * 0.745))
        self._rects["submit"] = submit
        self._rects["back"] = back
        # Không vẽ thêm gì để giữ đúng "1 ảnh"

class MenuScene:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.assets = AssetManager(
            avatars_dir=self.config.avatars_dir,
            pieces_dir=self.config.pieces_dir,
            avatar_size=self.config.avatar_size_px,
            font_name=self.config.font_name,
        )
        self.font = self.assets.get_font(22)
        self.small_font = self.assets.get_font(16)

        # Background (will be resized per-frame responsively)
        # Use new dragon background from Decorate directory
        self.bg = self.assets.get_decorate_image("dragon-background.jpg", (self.config.window_width, self.config.window_height))
        # Fallback to old background if new one doesn't exist
        if self.bg is None:
            self.bg = self.assets.get_menu_image("Background.png", (self.config.window_width, self.config.window_height))

        # Buttons (text label + target scene key) — ornate buttons on the left
        self._labels = [
            ("PLAY", "play"),
            ("HOW TO PLAY", "how"),
            ("RANKINGS", "ranking"),
            ("ABOUT US", "about"),
            ("QUIT", "quit"),
        ]
        self.buttons = []  # list of tuples: (rect, key, hover_state)
        self._hovered_button = None
        self._last_size = (self.config.window_width, self.config.window_height)
        self._recompute_layout()
        # Logout button rect
        self._logout_rect = pygame.Rect(0, 0, 0, 0)
        # Load user name image
        self._user_name_img_raw: Optional[pygame.Surface] = self._load_user_name_image()
        
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
        
        # Phát nhạc menu scene - sử dụng setting
        try:
            from core.settings import load_settings
            settings = load_settings()
            menu_music = getattr(settings, 'menu_music', 'ost.mp3')
            # Nếu có setting trong config (từ setup scene), ưu tiên dùng
            if hasattr(self.config, 'menu_music'):
                menu_music = self.config.menu_music
            
            # Tìm file nhạc trong Music hoặc Decorate directory
            music_dir = os.path.join(self.config.assets_dir, "Music")
            decorate_dir = self.config.decorate_dir
            menu_music_path = None
            
            if os.path.exists(music_dir):
                music_path = os.path.join(music_dir, menu_music)
                if os.path.exists(music_path):
                    menu_music_path = music_path
            
            if not menu_music_path and os.path.exists(decorate_dir):
                music_path = os.path.join(decorate_dir, menu_music)
                if os.path.exists(music_path):
                    menu_music_path = music_path
            
            if menu_music_path:
                if not pygame.mixer.get_init():
                    pygame.mixer.init()
                pygame.mixer.music.load(menu_music_path)
                pygame.mixer.music.set_volume(self.volume)
                pygame.mixer.music.play(-1)
        except Exception:
            pass
        
        # Quit dialog state
        self._quit_dialog_active = False
        self._quit_img_raw: Optional[pygame.Surface] = self._load_quit_image()
        self._quit_yes_rect = pygame.Rect(0, 0, 0, 0)
        self._quit_no_rect = pygame.Rect(0, 0, 0, 0)
        self._quit_yes_hovered = False
        self._quit_no_hovered = False

    def handle_event(self, event: pygame.event.Event) -> Optional[object]:
        from scenes.setup_scene import SetupScene
        
        # Xử lý quit dialog trước (ưu tiên cao nhất)
        if self._quit_dialog_active:
            if event.type == pygame.MOUSEBUTTONDOWN:
                pos = event.pos
                if self._quit_yes_rect.collidepoint(pos):
                    # Yes: Quit game
                    pygame.event.post(pygame.event.Event(pygame.QUIT))
                elif self._quit_no_rect.collidepoint(pos):
                    # No: Đóng dialog
                    self._quit_dialog_active = False
                # Không xử lý các click khác khi dialog đang active
                return None
            elif event.type == pygame.MOUSEMOTION:
                # Track hover state cho quit dialog buttons
                pos = event.pos
                self._quit_yes_hovered = self._quit_yes_rect.collidepoint(pos)
                self._quit_no_hovered = self._quit_no_rect.collidepoint(pos)
            return None
        
        if event.type == pygame.MOUSEBUTTONDOWN:
            pos = event.pos
            # Volume control click/drag
            if self._volume_slider_track.collidepoint(pos) or self._volume_rect.collidepoint(pos):
                self._volume_dragging = True
                self._update_volume_from_mouse(pos[0])
                return None
            
            # Logout click
            if self._logout_rect.width > 0 and self._logout_rect.collidepoint(pos):
                self.config.current_user = None
                return LoginScene(self.config, self.assets)
            for rect, key, _ in self.buttons:
                if rect.collidepoint(pos):
                    if key == "play":
                        # Open new in-game Login screen
                        if getattr(self.config, "current_user", None):
                            return SetupScene(self.config)
                        else:
                            return LoginScene(self.config, self.assets)
                    if key == "how":
                        return HowToPlayScene(self.config, self.assets)
                    if key == "ranking":
                        return RankingsScene(self.config, self.assets)
                    if key == "about":
                        return AboutUsScene(self.config, self.assets)
                    if key == "quit":
                        # Hiển thị quit dialog thay vì quit ngay
                        self._quit_dialog_active = True
                        return None
        elif event.type == pygame.MOUSEMOTION:
            # Volume dragging
            if self._volume_dragging:
                self._update_volume_from_mouse(event.pos[0])
            
            # Track hover state for button highlighting
            pos = event.pos
            self._hovered_button = None
            for rect, key, _ in self.buttons:
                if rect.collidepoint(pos):
                    self._hovered_button = key
                    break
        elif event.type == pygame.MOUSEBUTTONUP:
            # Volume drag end
            if self._volume_dragging:
                self._volume_dragging = False
                self._update_volume_from_mouse(event.pos[0])
                self.config.volume = self.volume
                return None
        return None

    def update(self, dt: float):
        # Recompute responsive layout if window size changed
        surface = pygame.display.get_surface()
        if surface:
            w, h = surface.get_size()
            if (w, h) != self._last_size:
                self._last_size = (w, h)
                # Resize background to cover
                self.bg = self.assets.get_decorate_image("dragon-background.jpg", (w, h))
                # Fallback to old background if new one doesn't exist
                if self.bg is None:
                    self.bg = self.assets.get_menu_image("Background.png", (w, h))
                self._recompute_layout()
        return None
    
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
        control_x = screen_w - control_width - margin
        control_y = margin
        
        container_rect = pygame.Rect(control_x, control_y, control_width, control_height)
        self._volume_rect = container_rect
        
        mouse_pos = pygame.mouse.get_pos()
        is_hovered = container_rect.collidepoint(mouse_pos) or self._volume_dragging
        
        # Background với glass effect
        bg_alpha = 200 if is_hovered else 160
        bg_surf = pygame.Surface((control_width, control_height), pygame.SRCALPHA)
        bg_surf.fill((28, 32, 40, bg_alpha))
        surface.blit(bg_surf, container_rect, special_flags=pygame.BLEND_ALPHA_SDL2)
        
        border_color = (70, 140, 210) if is_hovered else (60, 70, 85)
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

    def render(self, surface: pygame.Surface) -> None:
        # Background cover - fill entire screen
        if self.bg:
            # Scale background to fill entire screen (cover mode)
            bg_rect = self.bg.get_rect()
            screen_w, screen_h = surface.get_size()
            # Calculate scale to cover
            scale_w = screen_w / bg_rect.width
            scale_h = screen_h / bg_rect.height
            scale = max(scale_w, scale_h)
            scaled_bg = pygame.transform.smoothscale(self.bg, 
                (int(bg_rect.width * scale), int(bg_rect.height * scale)))
            # Center the scaled background
            scaled_rect = scaled_bg.get_rect(center=(screen_w // 2, screen_h // 2))
            surface.blit(scaled_bg, scaled_rect)

        # Không vẽ gì khi hover - hoàn toàn ẩn, chỉ giữ chức năng click
        # Các button areas là vô hình, chỉ có chức năng click
        # Draw username using User_name.png image at bottom-right corner
        username = ""
        try:
            username = self.config.current_user.get("name") if isinstance(self.config.current_user, dict) else (self.config.current_user or "")
        except Exception:
            username = ""
        if username and self._user_name_img_raw:
            screen_w, screen_h = surface.get_size()
            margin = 20
            
            # Scale ảnh để phù hợp với màn hình (giữ tỷ lệ)
            img_w, img_h = self._user_name_img_raw.get_size()
            # Scale theo chiều cao để phù hợp với góc dưới bên phải
            target_height = min(int(screen_h * 0.15), img_h)  # Tối đa 15% chiều cao màn hình
            scale = target_height / max(1, img_h)
            scaled_w = int(img_w * scale)
            scaled_h = int(img_h * scale)
            
            # Scale ảnh
            if scaled_w > 0 and scaled_h > 0:
                scaled_img = pygame.transform.smoothscale(self._user_name_img_raw, (scaled_w, scaled_h))
            else:
                scaled_img = self._user_name_img_raw
            
            # Vị trí ảnh ở góc dưới bên phải
            img_x = screen_w - scaled_w - margin
            img_y = screen_h - scaled_h - margin
            
            # Đảm bảo ảnh không tràn ra ngoài màn hình
            img_x = max(margin, img_x)
            img_y = max(margin, img_y)
            
            # Vẽ ảnh
            img_rect = scaled_img.get_rect(topleft=(img_x, img_y))
            surface.blit(scaled_img, img_rect)
            
            # Vẽ tên user vào oval lớn (phần trên của ảnh)
            # Căn giữa chính xác trong oval lớn với font đậm
            # Tạo font đậm cho tên user
            username_font = pygame.font.SysFont(self.config.font_name, 18, bold=True)
            username_display = username
            
            # Giới hạn độ dài tên để vừa với oval
            max_username_width = scaled_w * 0.75  # 75% chiều rộng ảnh
            user_text = username_font.render(username_display, True, (255, 255, 255))
            
            # Nếu tên quá dài, cắt ngắn lại
            while user_text.get_width() > max_username_width and len(username_display) > 1:
                username_display = username_display[:-1]
                user_text = username_font.render(username_display + "...", True, (255, 255, 255))
            
            # Vị trí tên trong oval lớn - căn giữa chính xác (cả ngang và dọc)
            # Khung "Hello" là khung lớn ở trên, cần căn giữa tên trong toàn bộ khung oval lớn
            # Tính tâm của khung oval lớn dựa trên kích thước thực tế của khung
            # Khung "Hello" thường chiếm khoảng 60-65% chiều cao của ảnh User_name.png
            oval_top = img_y
            oval_bottom = img_y + int(scaled_h * 0.62)  # Khung "Hello" chiếm khoảng 62% chiều cao
            oval_center_y = oval_top + (oval_bottom - oval_top) // 2  # Chính giữa khung theo chiều dọc
            username_y = oval_center_y - user_text.get_height() // 2  # Căn giữa dọc chính xác
            username_x = img_x + (scaled_w - user_text.get_width()) // 2  # Căn giữa ngang chính xác
            
            # Vẽ shadow cho tên để dễ đọc (đậm hơn)
            shadow_text = username_font.render(username_display + ("..." if len(username_display) < len(username) else ""), True, (0, 0, 0))
            surface.blit(shadow_text, (username_x + 2, username_y + 2))
            surface.blit(user_text, (username_x, username_y))
            
            # Vẽ nút logout (phần oval nhỏ ở dưới)
            # Ước tính vị trí oval nhỏ (khoảng 70% từ trên xuống)
            logout_font = self.assets.get_font(16)
            logout_text = logout_font.render("Logout", True, (255, 255, 255))
            
            logout_y = img_y + int(scaled_h * 0.70)
            logout_x = img_x + (scaled_w - logout_text.get_width()) // 2
            
            # Vẽ text logout
            surface.blit(logout_text, (logout_x, logout_y))
            
            # Set clickable area cho logout (khoảng 60-85% chiều cao ảnh)
            logout_rect = pygame.Rect(
                img_x + int(scaled_w * 0.1),  # 10% từ trái
                img_y + int(scaled_h * 0.60),  # 60% từ trên
                int(scaled_w * 0.8),  # 80% chiều rộng
                int(scaled_h * 0.25)  # 25% chiều cao
            )
            
            # Set clickable area cho logout
            self._logout_rect = logout_rect
        elif username:
            # Fallback nếu không có ảnh: hiển thị text đơn giản
            margin = 20
            user_text = self.small_font.render(username, True, (240, 240, 250))
            logout_text = self.small_font.render("Log out", True, (255, 150, 150))
            
            text_x = surface.get_width() - max(user_text.get_width(), logout_text.get_width()) - margin
            text_y = surface.get_height() - user_text.get_height() - logout_text.get_height() - 30 - margin
            
            surface.blit(user_text, (text_x, text_y))
            
            logout_y = text_y + user_text.get_height() + 10
            logout_rect = pygame.Rect(text_x, logout_y, logout_text.get_width() + 8, logout_text.get_height() + 4)
            
            mouse_pos = pygame.mouse.get_pos()
            is_hovered = logout_rect.collidepoint(mouse_pos)
            logout_bg = (60, 40, 40) if is_hovered else (45, 35, 35)
            pygame.draw.rect(surface, logout_bg, logout_rect, border_radius=6)
            pygame.draw.rect(surface, (200, 100, 100) if is_hovered else (150, 80, 80), logout_rect, 1, border_radius=6)
            surface.blit(logout_text, (logout_rect.x + 4, logout_rect.y + 2))
            
            self._logout_rect = logout_rect
        else:
            self._logout_rect = pygame.Rect(0, 0, 0, 0)
        
        # Render quit dialog nếu đang active
        if self._quit_dialog_active and self._quit_img_raw is not None:
            self._render_quit_dialog(surface)
        
        # Volume control ở góc trên bên phải
        self._render_volume_control(surface)

    def _load_user_name_image(self) -> Optional[pygame.Surface]:
        """Load User_name.png from Decorate directory."""
        import os
        path = os.path.join(".", "assets", "Decorate", "User_name.png")
        if not os.path.exists(path):
            return None
        try:
            return pygame.image.load(path).convert_alpha()
        except Exception:
            return None
    
    def _load_quit_image(self) -> Optional[pygame.Surface]:
        """Load quit.png from Decorate directory."""
        import os
        path = os.path.join(".", "assets", "Decorate", "quit.png")
        if not os.path.exists(path):
            return None
        try:
            return pygame.image.load(path).convert_alpha()
        except Exception:
            return None
    
    def _render_quit_dialog(self, surface: pygame.Surface) -> None:
        """Render quit dialog với ảnh quit.png và các nút Yes/No."""
        screen_w, screen_h = surface.get_size()
        
        # Vẽ overlay tối để làm nổi bật dialog
        overlay = pygame.Surface((screen_w, screen_h), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))  # Đen với alpha 180
        surface.blit(overlay, (0, 0))
        
        # Scale ảnh quit.png để phù hợp với màn hình
        img_w, img_h = self._quit_img_raw.get_size()
        # Scale theo chiều rộng hoặc chiều cao, giữ tỷ lệ
        max_width = int(screen_w * 0.6)  # Tối đa 60% chiều rộng màn hình
        max_height = int(screen_h * 0.7)  # Tối đa 70% chiều cao màn hình
        scale_w = max_width / img_w
        scale_h = max_height / img_h
        scale = min(scale_w, scale_h)
        
        draw_w = int(img_w * scale)
        draw_h = int(img_h * scale)
        
        # Scale ảnh
        if draw_w > 0 and draw_h > 0:
            scaled_img = pygame.transform.smoothscale(self._quit_img_raw, (draw_w, draw_h))
        else:
            scaled_img = self._quit_img_raw
            draw_w, draw_h = scaled_img.get_size()
        
        # Vị trí dialog ở giữa màn hình
        dialog_x = (screen_w - draw_w) // 2
        dialog_y = (screen_h - draw_h) // 2
        dialog_rect = pygame.Rect(dialog_x, dialog_y, draw_w, draw_h)
        
        # Vẽ ảnh dialog
        surface.blit(scaled_img, dialog_rect)
        
        # Xác định vị trí Yes/No buttons dựa trên tỷ lệ của ảnh
        # Từ mô tả ảnh: Yes ở bên trái, No ở bên phải, nằm dưới phần text "QUIT GAME"
        # Ước tính: Yes button ở khoảng 30-45% từ trái, 70-85% từ trên
        # No button ở khoảng 55-70% từ trái, 70-85% từ trên
        
        # Yes button (bên trái) - dài 3% sang bên trái
        yes_left_pct = 0.22  # 22% từ trái (giảm 3% để dài sang trái)
        yes_top_pct = 0.65   # 65% từ trên (di chuyển lên trên thêm 5%)
        yes_width_pct = 0.236  # 23.6% chiều rộng dialog (tăng 3% để dài sang trái)
        yes_height_pct = 0.09  # 9% chiều cao dialog (tăng 4% từ 8.652%)
        
        self._quit_yes_rect = pygame.Rect(
            dialog_x + int(draw_w * yes_left_pct),
            dialog_y + int(draw_h * yes_top_pct),
            int(draw_w * yes_width_pct),
            int(draw_h * yes_height_pct)
        )
        
        # No button (bên phải) - dài 3% sang bên phải
        no_left_pct = 0.55  # 55% từ trái (giữ nguyên)
        no_top_pct = 0.65   # 65% từ trên (di chuyển lên trên thêm 5%)
        no_width_pct = 0.236  # 23.6% chiều rộng dialog (tăng 3% để dài sang phải)
        no_height_pct = 0.09  # 9% chiều cao dialog (tăng 4% từ 8.652%)
        
        self._quit_no_rect = pygame.Rect(
            dialog_x + int(draw_w * no_left_pct),
            dialog_y + int(draw_h * no_top_pct),
            int(draw_w * no_width_pct),
            int(draw_h * no_height_pct)
        )
        
        # Ẩn highlight khi hover - không vẽ gì cả

    def _recompute_layout(self) -> None:
        """Responsive layout for clickable button areas: left side, matching background image (1920x1080)."""
        w, h = self._last_size

        # Button positions theo JSON - background size: 1920x1080
        # Tất cả buttons có cùng left (5.99%) và width (35.47%), height (11.02%)
        # Chỉ khác nhau về top position
        button_configs = [
            ("play", 0.0599, 0.1796, 0.3547, 0.1102),      # PLAY
            ("how", 0.0599, 0.3343, 0.3547, 0.1102),       # HOW TO PLAY
            ("ranking", 0.0599, 0.4889, 0.3547, 0.1102),   # RANKINGS
            ("about", 0.0599, 0.6435, 0.3547, 0.1102),     # ABOUT US
            ("quit", 0.0599, 0.7981, 0.3547, 0.1102),      # QUITS
        ]

        # Rebuild buttons list - invisible clickable areas
        self.buttons = []
        for key, left_pct, top_pct, width_pct, height_pct in button_configs:
            left_x = int(w * left_pct)
            top_y = int(h * top_pct)
            btn_width = int(w * width_pct)
            btn_height = int(h * height_pct)
            
            rect = pygame.Rect(left_x, top_y, btn_width, btn_height)
            self.buttons.append((rect, key, None))



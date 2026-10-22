"""
UI组件 - Button, Panel, Card, Tooltip, Toast
"""
from __future__ import annotations

import pygame
import os
from typing import Optional, Callable, Tuple, List
from .theme import ThemeTokens


class Button:
    """按钮组件 - 支持normal/hover/disabled状态 - 优化版本"""
    
    # Class variable để cache ảnh nền button
    _button_bg_image: Optional[pygame.Surface] = None
    _resign_bg_image: Optional[pygame.Surface] = None  # Ảnh nền riêng cho resign button
    _button_bg_cache: dict = {}  # Cache cho các kích thước khác nhau
    _resign_bg_cache: dict = {}  # Cache riêng cho resign image
    _shadow_cache: dict = {}  # Cache cho shadow surfaces
    _gradient_cache: dict = {}  # Cache cho gradient surfaces
    
    def __init__(
        self,
        rect: pygame.Rect,
        text: str,
        theme: ThemeTokens,
        colors: dict,
        font: pygame.font.Font,
        callback: Optional[Callable] = None,
        tooltip: Optional[str] = None,
        disabled: bool = False,
        key: Optional[str] = None,
    ):
        self.rect = rect
        self.text = text
        self.theme = theme
        self.colors = colors
        self.font = font
        self.callback = callback
        self.tooltip = tooltip
        self.disabled = disabled
        self.key = key
        self.hovered = False
        self.pressed = False
        
        # Cache surfaces để tối ưu performance
        self._cached_text_surf = None
        self._cached_text_shadow = None
        self._cached_display_text = None
        self._last_state = None  # Track state changes để invalidate cache
        
        # Load ảnh nền button nếu chưa load
        if Button._button_bg_image is None:
            Button._load_button_bg_image()
        # Load ảnh nền resign nếu chưa load
        if Button._resign_bg_image is None:
            Button._load_resign_bg_image()
    
    @classmethod
    def _load_button_bg_image(cls):
        """Load ảnh nền button từ btt4.png"""
        try:
            path = os.path.join(".", "assets", "Decorate", "btt4.png")
            if os.path.exists(path):
                cls._button_bg_image = pygame.image.load(path).convert_alpha()
        except Exception as e:
            print(f"Error loading button background image: {e}")
            cls._button_bg_image = None
    
    @classmethod
    def _load_resign_bg_image(cls):
        """Load ảnh nền resign button từ bttresign.png"""
        try:
            path = os.path.join(".", "assets", "Decorate", "bttresign.png")
            if os.path.exists(path):
                cls._resign_bg_image = pygame.image.load(path).convert_alpha()
                # Clear cache khi load ảnh mới
                cls._resign_bg_cache.clear()
        except Exception as e:
            print(f"Error loading resign background image: {e}")
            cls._resign_bg_image = None
            cls._resign_bg_cache.clear()
        
    def handle_event(self, event: pygame.event.Event) -> bool:
        """处理事件，返回是否被点击 - 优化版本"""
        if self.disabled:
            return False
        
        # Với resign button, sử dụng vùng chọn đã điều chỉnh (giảm chiều cao 50%, giảm chiều ngang 10%)
        use_resign_image = self.key == "resign" and Button._resign_bg_image is not None
        if use_resign_image:
            # Tính toán vùng ảnh thực tế
            original_img = Button._resign_bg_image
            original_width, original_height = original_img.get_size()
            img_width = original_width // 2
            img_height = original_height // 2
            img_x = self.rect.x + (self.rect.width - img_width) // 2
            img_y = self.rect.y + (self.rect.height - img_height) // 2
            
            # Tính toán vùng chọn (giảm chiều cao 35%, giảm chiều ngang 2 bên 13%)
            selection_width = int(img_width * 0.87)  # Giảm 13% chiều ngang (từ 90% xuống 87%)
            selection_height = int(img_height * 0.35)  # Giảm 35% chiều cao (từ 50% xuống 35%)
            selection_x = img_x + (img_width - selection_width) // 2  # Căn giữa theo chiều ngang
            selection_y = img_y + (img_height - selection_height) // 2  # Căn giữa theo chiều cao
            check_rect = pygame.Rect(selection_x, selection_y, selection_width, selection_height)
        else:
            check_rect = self.rect
            
        if event.type == pygame.MOUSEMOTION:
            new_hovered = check_rect.collidepoint(event.pos)
            if new_hovered != self.hovered:
                self.hovered = new_hovered
                self._last_state = None  # Invalidate cache khi hover state thay đổi
            return False
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if check_rect.collidepoint(event.pos):
                self.pressed = True
                self._last_state = None  # Invalidate cache khi pressed
                # 立即调用callback（更直接的响应）
                if self.callback:
                    try:
                        self.callback()
                    except Exception as e:
                        print(f"Button callback error: {e}")
                return True
        elif event.type == pygame.MOUSEBUTTONUP:
            if self.pressed:
                self.pressed = False
                self._last_state = None  # Invalidate cache khi released
                # 如果鼠标仍在按钮上，再次确认点击
                if check_rect.collidepoint(event.pos) and self.callback:
                    return True
        return False
    
    def _get_cached_shadow(self, width: int, height: int, alpha: int) -> pygame.Surface:
        """Lấy shadow surface từ cache để tối ưu performance"""
        cache_key = (width, height, alpha)
        if cache_key not in Button._shadow_cache:
            shadow_surf = pygame.Surface((width, height), pygame.SRCALPHA)
            shadow_surf.fill((0, 0, 0, alpha))
            Button._shadow_cache[cache_key] = shadow_surf
        return Button._shadow_cache[cache_key]
    
    def _get_cached_gradient(self, width: int, height: int, bg_color: Tuple[int, int, int], factor: float = 0.3) -> pygame.Surface:
        """Lấy gradient surface từ cache để tối ưu performance"""
        cache_key = (width, height, bg_color, factor)
        if cache_key not in Button._gradient_cache:
            bg_surf = pygame.Surface((width, height), pygame.SRCALPHA)
            for y in range(height):
                grad_factor = 1.0 - (y / height) * factor
                gradient_color = tuple(min(255, int(c * grad_factor)) for c in bg_color)
                pygame.draw.line(bg_surf, gradient_color, (0, y), (width, y))
            Button._gradient_cache[cache_key] = bg_surf
        return Button._gradient_cache[cache_key]
    
    def render(self, surface: pygame.Surface) -> None:
        """渲染按钮 - 使用btt4.png作为背景 - 优化版本 với cache"""
        # Kiểm tra state changes để invalidate cache
        current_state = (self.hovered, self.pressed, self.disabled, self.text, self.rect.size)
        if current_state != self._last_state:
            self._cached_text_surf = None
            self._cached_text_shadow = None
            self._cached_display_text = None
            self._last_state = current_state
        
        text_color = self.colors.get("text", (255, 255, 255))

        if self.disabled:
            text_color = self.colors.get("muted", (120, 120, 120))
        
        # Kiểm tra xem có phải button cần dùng ảnh nền không
        use_bg_image = self.key in ("undo", "hint", "new", "pause") and Button._button_bg_image is not None
        use_resign_image = self.key == "resign" and Button._resign_bg_image is not None
        
        if use_bg_image:
            # Sử dụng ảnh nền từ btt4.png
            # Cache theo kích thước để tối ưu performance
            cache_key = (self.rect.width, self.rect.height)
            if cache_key not in Button._button_bg_cache:
                # Scale ảnh để fit với button rect
                scaled_img = pygame.transform.smoothscale(
                    Button._button_bg_image, 
                    (self.rect.width, self.rect.height)
                )
                Button._button_bg_cache[cache_key] = scaled_img
            
            bg_img = Button._button_bg_cache[cache_key]
            
            # Vẽ shadow trước - sử dụng cache
            shadow_rect = self.rect.copy()
            shadow_rect.x += 3
            shadow_rect.y += 3
            shadow_surf = self._get_cached_shadow(self.rect.width, self.rect.height, 100)
            surface.blit(shadow_surf, shadow_rect, special_flags=pygame.BLEND_ALPHA_SDL2)
            
            # Vẽ ảnh nền
            surface.blit(bg_img, self.rect)
            
            # Hover effect - thêm glow khi hover
            if self.hovered and not self.disabled:
                glow_surf = pygame.Surface((self.rect.width + 6, self.rect.height + 6), pygame.SRCALPHA)
                glow_rect = pygame.Rect(3, 3, self.rect.width, self.rect.height)
                glow_color = (255, 255, 255, 40)
                try:
                    pygame.draw.rect(glow_surf, glow_color, glow_rect, border_radius=self.theme.RADIUS)
                except TypeError:
                    pygame.draw.rect(glow_surf, (255, 255, 255), glow_rect, border_radius=self.theme.RADIUS)
                surface.blit(glow_surf, (self.rect.x - 3, self.rect.y - 3), special_flags=pygame.BLEND_ALPHA_SDL2)
        elif use_resign_image:
            # Sử dụng ảnh nền từ bttresign.png cho resign button
            # Thu nhỏ ảnh xuống 50% kích cỡ gốc
            original_img = Button._resign_bg_image
            original_width, original_height = original_img.get_size()
            
            # Tính kích cỡ mới (50%)
            img_width = original_width // 2
            img_height = original_height // 2
            
            # Cache theo kích thước để tối ưu performance
            cache_key = (img_width, img_height)
            if cache_key not in Button._resign_bg_cache:
                # Scale ảnh xuống 50%
                bg_img = pygame.transform.smoothscale(original_img, (img_width, img_height))
                Button._resign_bg_cache[cache_key] = bg_img
            else:
                bg_img = Button._resign_bg_cache[cache_key]
            
            # Tính toán vị trí để căn giữa ảnh trong button rect
            img_x = self.rect.x + (self.rect.width - img_width) // 2
            img_y = self.rect.y + (self.rect.height - img_height) // 2
            img_rect = pygame.Rect(img_x, img_y, img_width, img_height)
            
            # Vẽ ảnh nền với kích cỡ đã scale (không có shadow)
            surface.blit(bg_img, img_rect)
            
            # Tính toán vùng chọn Resign button (giảm chiều cao 35%, giảm chiều ngang 2 bên 13%)
            selection_width = int(img_width * 0.87)  # Giảm 13% chiều ngang (từ 90% xuống 87%)
            selection_height = int(img_height * 0.35)  # Giảm 35% chiều cao (từ 50% xuống 35%)
            selection_x = img_x + (img_width - selection_width) // 2  # Căn giữa theo chiều ngang
            selection_y = img_y + (img_height - selection_height) // 2  # Căn giữa theo chiều cao
            selection_rect = pygame.Rect(selection_x, selection_y, selection_width, selection_height)
            
            # Vùng chọn Resign button đã được ẩn (không vẽ border và highlight)
            
            # Hover effect đã được ẩn cho Resign button
            
        else:
            # Fallback: sử dụng code cũ cho các button khác (không dùng ảnh nền)
            base_primary = self.colors.get("primary", (74, 158, 255))
            base_danger = self.colors.get("danger", (231, 76, 60))

            if self.disabled:
                bg_color = self.colors.get("border", (51, 51, 51))
            else:
                bg_color = base_danger if getattr(self, "key", "") == "resign" else base_primary
                bg_color = tuple(min(255, int(c * 1.2)) for c in bg_color)
                if self.pressed:
                    bg_color = tuple(max(0, int(c * 0.85)) for c in bg_color)
                elif self.hovered:
                    bg_color = tuple(min(255, int(c * 1.3)) for c in bg_color)

            # 外阴影 - tối ưu với cache
            shadow_rect = self.rect.copy()
            shadow_rect.x += 4
            shadow_rect.y += 4
            # Chỉ vẽ 2 layer shadow thay vì 3 để tối ưu performance
            for i in range(2):
                shadow_alpha = 100 - i * 30
                shadow_offset = i * 2
                shadow_temp = self._get_cached_shadow(self.rect.width, self.rect.height, shadow_alpha)
                surface.blit(shadow_temp, (shadow_rect.x + shadow_offset, shadow_rect.y + shadow_offset), special_flags=pygame.BLEND_ALPHA_SDL2)
            
            # 绘制按钮背景 - sử dụng cache gradient
            bg_surf = self._get_cached_gradient(self.rect.width, self.rect.height, bg_color, 0.3)
            surface.blit(bg_surf, self.rect, special_flags=pygame.BLEND_ALPHA_SDL2)
            
            # Hover glow - tối ưu chỉ vẽ 2 layer thay vì 3
            if self.hovered and not self.disabled:
                for i in range(2):  # Giảm từ 3 xuống 2 để tối ưu
                    glow_size = 8 + i * 4
                    glow_surf = pygame.Surface((self.rect.width + glow_size * 2, self.rect.height + glow_size * 2), pygame.SRCALPHA)
                    glow_rect = pygame.Rect(glow_size, glow_size, self.rect.width, self.rect.height)
                    glow_alpha = 80 - i * 30  # Tăng alpha step để vẫn có hiệu ứng tốt
                    glow_color = (*bg_color[:3], glow_alpha)
                    try:
                        pygame.draw.rect(glow_surf, glow_color, glow_rect, border_radius=self.theme.RADIUS)
                    except TypeError:
                        pygame.draw.rect(glow_surf, bg_color, glow_rect, border_radius=self.theme.RADIUS)
                    surface.blit(glow_surf, (self.rect.x - glow_size, self.rect.y - glow_size), special_flags=pygame.BLEND_ALPHA_SDL2)
        
        # 绘制文本（处理文本过长的情况）- 优化版本 với cache
        # Không hiển thị text cho resign button khi dùng ảnh nền
        if not use_resign_image:
            display_text = self.text
            
            # Sử dụng cached text nếu có
            if self._cached_display_text is None or self._cached_text_surf is None:
                text_color = self.colors.get("text", (255, 255, 255))
                # 确保文本颜色足够亮 - 让文字清晰可见
                if not self.disabled:
                    # 增强文本颜色亮度，但确保不超过255
                    text_color = tuple(min(255, int(c * 1.2)) for c in text_color)
                else:
                    # Disabled状态使用muted颜色
                    text_color = self.colors.get("muted", (120, 120, 120))
                
                text_surf = self.font.render(display_text, True, text_color)

                max_width = self.rect.width - 16
                if text_surf.get_width() > max_width:
                    ellipsis = "..."
                    while text_surf.get_width() > max_width and len(display_text) > 1:
                        display_text = display_text[:-1]
                        text_surf = self.font.render(display_text + ellipsis, True, text_color)
                    display_text = display_text + ellipsis if text_surf.get_width() <= max_width else display_text
                    text_surf = self.font.render(display_text, True, text_color)
                
                # Cache text surfaces
                self._cached_display_text = display_text
                self._cached_text_surf = text_surf
                self._cached_text_shadow = self.font.render(display_text, True, (0, 0, 0))
            else:
                # Sử dụng cached surfaces
                display_text = self._cached_display_text
                text_surf = self._cached_text_surf
                text_color = self.colors.get("text", (255, 255, 255))
                if self.disabled:
                    text_color = self.colors.get("muted", (120, 120, 120))
                else:
                    text_color = tuple(min(255, int(c * 1.2)) for c in text_color)
            
            text_rect = text_surf.get_rect(center=self.rect.center)
            
            # 文本阴影 - sử dụng cached shadow
            text_shadow = self._cached_text_shadow
            # 绘制阴影（偏移2px）
            surface.blit(text_shadow, (text_rect.x + 2, text_rect.y + 2))
            # 绘制文本主体
            surface.blit(text_surf, text_rect)
        
        # 绘制边框 - 增强边框
        if use_bg_image or use_resign_image:
            # Khi dùng ảnh nền, không cần vẽ border vì ảnh đã có border
            pass
        else:
            # Chỉ vẽ border cho button không dùng ảnh nền
            border_color = tuple(min(255, c + 50) for c in bg_color) if not self.disabled else self.colors.get("border", (51, 51, 51))
            border_width = 3 if self.hovered and not self.disabled else 2  # 增加边框宽度
            pygame.draw.rect(surface, border_color, self.rect, border_width, border_radius=self.theme.RADIUS)
            
            # Hover时添加accent边框 - 增强accent
            if self.hovered and not self.disabled:
                accent_color = self.colors.get("accent", (39, 174, 96))
                accent_color = tuple(min(255, int(c * 1.3)) for c in accent_color)  # 增强accent亮度
                pygame.draw.rect(surface, accent_color, self.rect, 3, border_radius=self.theme.RADIUS)


class Panel:
    """面板组件 - 深色面板，圆角，阴影"""
    
    def __init__(
        self,
        rect: pygame.Rect,
        theme: ThemeTokens,
        colors: dict,
        title: Optional[str] = None,
        font: Optional[pygame.font.Font] = None,
    ):
        self.rect = rect
        self.theme = theme
        self.colors = colors
        self.title = title
        self.font = font
        
    def render(self, surface: pygame.Surface) -> None:
        """渲染面板 - 优化版本"""
        # Thêm nền đen đậm trước khi vẽ panel
        black_bg = pygame.Surface((self.rect.width, self.rect.height), pygame.SRCALPHA)
        black_bg.fill((0, 0, 0, 255))  # Nền đen đậm
        surface.blit(black_bg, self.rect)
        
        panel_color = self.colors.get("panel", (13, 13, 13))
        border_color = self.colors.get("border", (51, 51, 51))
        
        # 绘制面板背景
        pygame.draw.rect(surface, panel_color, self.rect, border_radius=self.theme.RADIUS)
        
        # 添加微妙的阴影效果
        shadow_rect = pygame.Rect(
            self.rect.x + 2, self.rect.y + 2,
            self.rect.width, self.rect.height
        )
        shadow_color = tuple(max(0, c - 10) for c in panel_color)
        pygame.draw.rect(surface, shadow_color, shadow_rect, border_radius=self.theme.RADIUS)
        
        # 绘制主面板
        pygame.draw.rect(surface, panel_color, self.rect, border_radius=self.theme.RADIUS)
        pygame.draw.rect(surface, border_color, self.rect, 1, border_radius=self.theme.RADIUS)
        
        # 绘制标题（带下划线装饰）
        if self.title and self.font:
            title_surf = self.font.render(self.title, True, self.colors.get("text", (226, 232, 240)))
            title_rect = title_surf.get_rect(
                topleft=(self.rect.x + self.theme.SPACING, self.rect.y + self.theme.SPACING)
            )
            surface.blit(title_surf, title_rect)
            
            # 添加装饰性下划线
            underline_y = title_rect.bottom + 4
            underline_width = min(title_rect.width, self.rect.width - self.theme.SPACING * 2)
            underline_rect = pygame.Rect(
                self.rect.x + self.theme.SPACING,
                underline_y,
                underline_width,
                2
            )
            accent_color = self.colors.get("primary", (74, 158, 255))
            pygame.draw.rect(surface, accent_color, underline_rect)


class Card:
    """卡片组件 - 用于显示信息块"""
    
    def __init__(
        self,
        rect: pygame.Rect,
        theme: ThemeTokens,
        colors: dict,
        content: Optional[str] = None,
        font: Optional[pygame.font.Font] = None,
    ):
        self.rect = rect
        self.theme = theme
        self.colors = colors
        self.content = content
        self.font = font
        
    def render(self, surface: pygame.Surface) -> None:
        """渲染卡片 - 改进的设计，更美观和现代化，更突出"""
        # Thêm nền đen đậm trước khi vẽ card
        black_bg = pygame.Surface((self.rect.width, self.rect.height), pygame.SRCALPHA)
        black_bg.fill((0, 0, 0, 255))  # Nền đen đậm
        surface.blit(black_bg, self.rect)
        
        card_color = self.colors.get("panel_alt", self.colors.get("panel", (13, 13, 13)))
        border_color = self.colors.get("border", (51, 51, 51))
        
        # 增强卡片颜色亮度 - 让卡片更突出
        card_color = tuple(min(255, int(c * 1.15)) for c in card_color)
        
        # 外阴影 - 增强阴影效果
        shadow_rect = self.rect.copy()
        shadow_rect.x += 3
        shadow_rect.y += 3
        # 多层阴影效果
        for i in range(2):
            shadow_alpha = 100 - i * 30
            shadow_offset = i * 2
            shadow_surf = pygame.Surface((self.rect.width, self.rect.height), pygame.SRCALPHA)
            shadow_surf.fill((0, 0, 0, shadow_alpha))
            surface.blit(shadow_surf, (shadow_rect.x + shadow_offset, shadow_rect.y + shadow_offset), special_flags=pygame.BLEND_ALPHA_SDL2)
        
        # 绘制卡片背景（带渐变效果） - 增强渐变
        bg_surf = pygame.Surface((self.rect.width, self.rect.height), pygame.SRCALPHA)
        # 渐变背景 - 从上到下，增强对比度
        for y in range(self.rect.height):
            factor = 1.0 - (y / self.rect.height) * 0.25  # 增强渐变
            gradient_color = tuple(min(255, int(c * factor)) for c in card_color)
            pygame.draw.line(bg_surf, gradient_color, (0, y), (self.rect.width, y))
        surface.blit(bg_surf, self.rect, special_flags=pygame.BLEND_ALPHA_SDL2)
        
        # 添加顶部高光 - 增强高光
        highlight_rect = pygame.Rect(
            self.rect.x, self.rect.y,
            self.rect.width, self.rect.height // 2  # 增加高光区域
        )
        highlight_color = tuple(min(255, c + 40) for c in card_color)  # 增强高光亮度
        highlight_surf = pygame.Surface((self.rect.width, highlight_rect.height), pygame.SRCALPHA)
        for y in range(highlight_rect.height):
            alpha = int(80 * (1 - y / highlight_rect.height))  # 增强alpha
            if alpha > 0:
                highlight_line_color = (*highlight_color[:3], alpha)
                try:
                    pygame.draw.line(highlight_surf, highlight_line_color, (0, y), (self.rect.width, y))
                except TypeError:
                    pygame.draw.line(highlight_surf, highlight_color, (0, y), (self.rect.width, y))
        surface.blit(highlight_surf, highlight_rect, special_flags=pygame.BLEND_ALPHA_SDL2)
        
        # 绘制边框 - 增强边框
        border_color = tuple(min(255, c + 30) for c in card_color)  # 增强边框亮度
        pygame.draw.rect(surface, border_color, self.rect, 2, border_radius=self.theme.RADIUS)  # 增加边框宽度
        
        # 内发光效果 - 增强内发光
        inner_glow = pygame.Rect(
            self.rect.x + 2, self.rect.y + 2,
            self.rect.width - 4, self.rect.height - 4
        )
        inner_color = tuple(max(0, c - 15) for c in card_color)  # 增强对比度
        pygame.draw.rect(surface, inner_color, inner_glow, 2, border_radius=self.theme.RADIUS)  # 增加边框宽度
        
        # 绘制内容 - 改进的设计，确保清晰可见
        if self.content and self.font:
            text_color = self.colors.get("text", (226, 232, 240))
            # 增强文本颜色亮度，确保清晰可见
            text_color = tuple(min(255, int(c * 1.2)) for c in text_color)
            
            text_surf = self.font.render(self.content, True, text_color)
            text_rect = text_surf.get_rect(center=self.rect.center)
            
            # 文本阴影 - 简单有效的阴影效果
            text_shadow = self.font.render(self.content, True, (0, 0, 0))
            # 绘制阴影（偏移2px）
            surface.blit(text_shadow, (text_rect.x + 2, text_rect.y + 2))
            # 绘制文本主体
            surface.blit(text_surf, text_rect)


class Tooltip:
    """工具提示组件"""
    
    def __init__(
        self,
        text: str,
        theme: ThemeTokens,
        colors: dict,
        font: pygame.font.Font,
        max_width: int = 200,
    ):
        self.text = text
        self.theme = theme
        self.colors = colors
        self.font = font
        self.max_width = max_width
        self.visible = False
        self.pos: Optional[Tuple[int, int]] = None
        
    def show(self, pos: Tuple[int, int]) -> None:
        """显示工具提示"""
        self.visible = True
        self.pos = pos
        
    def hide(self) -> None:
        """隐藏工具提示"""
        self.visible = False
        self.pos = None
        
    def render(self, surface: pygame.Surface) -> None:
        """渲染工具提示"""
        if not self.visible or not self.pos:
            return
            
        # 包装文本
        words = self.text.split()
        lines: List[str] = []
        current_line = ""
        
        for word in words:
            test_line = current_line + (" " if current_line else "") + word
            if self.font.size(test_line)[0] <= self.max_width:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word
        if current_line:
            lines.append(current_line)
        
        # 计算尺寸
        line_height = self.font.get_height()
        padding = self.theme.SPACING
        width = max(self.max_width, max(self.font.size(line)[0] for line in lines)) + padding * 2
        height = line_height * len(lines) + padding * 2
        
        # 创建工具提示表面
        tooltip_rect = pygame.Rect(self.pos[0], self.pos[1] - height - 10, width, height)
        
        # 确保不超出屏幕
        screen_width, screen_height = surface.get_size()
        if tooltip_rect.right > screen_width:
            tooltip_rect.right = screen_width - 10
        if tooltip_rect.top < 0:
            tooltip_rect.top = self.pos[1] + 10
        
        # 绘制背景
        pygame.draw.rect(
            surface,
            self.colors.get("panel_alt", self.colors.get("panel", (13, 13, 13))),
            tooltip_rect,
            border_radius=self.theme.RADIUS // 2
        )
        pygame.draw.rect(
            surface,
            self.colors.get("border", (51, 51, 51)),
            tooltip_rect,
            1,
            border_radius=self.theme.RADIUS // 2
        )
        
        # 绘制文本
        y = tooltip_rect.y + padding
        for line in lines:
            text_surf = self.font.render(line, True, self.colors.get("text", (226, 232, 240)))
            surface.blit(text_surf, (tooltip_rect.x + padding, y))
            y += line_height


class Toast:
    """Toast通知组件 - 显示在右上角"""
    
    def __init__(
        self,
        text: str,
        theme: ThemeTokens,
        colors: dict,
        font: pygame.font.Font,
        duration: float = 3.0,
        toast_type: str = "info",  # "info", "success", "warning", "error"
    ):
        self.text = text
        self.theme = theme
        self.colors = colors
        self.font = font
        self.duration = duration
        self.toast_type = toast_type
        self.visible = False
        self.timer = 0.0
        
    def show(self) -> None:
        """显示Toast"""
        self.visible = True
        self.timer = 0.0
        
    def update(self, dt: float) -> bool:
        """更新计时器，返回是否仍可见"""
        if not self.visible:
            return False
        self.timer += dt
        if self.timer >= self.duration:
            self.visible = False
            return False
        return True
        
    def render(self, surface: pygame.Surface) -> None:
        """渲染Toast"""
        if not self.visible:
            return
            
        # 确定颜色
        type_colors = {
            "info": self.colors.get("primary", (79, 70, 229)),
            "success": self.colors.get("accent", (34, 197, 94)),
            "warning": (255, 193, 7),
            "error": self.colors.get("danger", (239, 68, 68)),
        }
        bg_color = type_colors.get(self.toast_type, type_colors["info"])
        
        # 计算尺寸
        padding = self.theme.SPACING * 2
        text_surf = self.font.render(self.text, True, self.colors.get("text", (255, 255, 255)))
        width = text_surf.get_width() + padding * 2
        height = text_surf.get_height() + padding
        
        # 位置（右上角）
        screen_width, screen_height = surface.get_size()
        margin = self.theme.SPACING * 2
        x = screen_width - width - margin
        y = margin
        
        # 动画：从右侧滑入
        progress = min(1.0, self.timer / 0.3)  # 0.3秒动画
        offset_x = int((1 - progress) * width)
        x -= offset_x
        
        toast_rect = pygame.Rect(x, y, width, height)
        
        # 绘制背景
        pygame.draw.rect(surface, bg_color, toast_rect, border_radius=self.theme.RADIUS)
        
        # 绘制文本
        text_rect = text_surf.get_rect(center=toast_rect.center)
        surface.blit(text_surf, text_rect)
        
        # 绘制阴影
        pygame.draw.rect(surface, self.colors.get("border", (51, 51, 51)), toast_rect, 1, border_radius=self.theme.RADIUS)


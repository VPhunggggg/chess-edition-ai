"""
设置场景响应式布局系统
"""
from __future__ import annotations

import pygame
from typing import Tuple
from .theme import ThemeTokens


class SetupLayoutSystem:
    """设置场景响应式布局系统"""
    
    MIN_WINDOW_WIDTH = 1024
    MIN_WINDOW_HEIGHT = 768
    
    def __init__(
        self,
        window_width: int,
        window_height: int,
        theme: ThemeTokens,
    ):
        self.window_width = max(self.MIN_WINDOW_WIDTH, window_width)
        self.window_height = max(self.MIN_WINDOW_HEIGHT, window_height)
        self.theme = theme
        self._scale_factor = self._calculate_scale_factor()
        
    def _calculate_scale_factor(self) -> float:
        """计算缩放因子"""
        base_width = self.MIN_WINDOW_WIDTH
        base_height = self.MIN_WINDOW_HEIGHT
        scale_w = self.window_width / base_width
        scale_h = self.window_height / base_height
        return min(scale_w, scale_h, 1.5)  # 最大1.5倍缩放
        
    def update(self, width: int, height: int) -> None:
        """更新窗口大小"""
        self.window_width = max(self.MIN_WINDOW_WIDTH, width)
        self.window_height = max(self.MIN_WINDOW_HEIGHT, height)
        self._scale_factor = self._calculate_scale_factor()
        
    def scale(self, value: float) -> int:
        """缩放值"""
        return int(value * self._scale_factor)
        
    def clamp_font_size(self, base_size: int, min_size: int, max_size: int) -> int:
        """响应式字体大小"""
        size = int(base_size * self._scale_factor)
        return max(min_size, min(size, max_size))
        
    def get_font_size_title(self) -> int:
        return self.clamp_font_size(36, 24, 48)
        
    def get_font_size_text(self) -> int:
        return self.clamp_font_size(22, 16, 28)
        
    def get_font_size_small(self) -> int:
        return self.clamp_font_size(18, 14, 22)
        
    def get_margin(self) -> int:
        """响应式边距"""
        return self.scale(20)
        
    def get_spacing(self) -> int:
        """响应式间距"""
        return self.scale(15)
        
    def get_container_rect(self) -> pygame.Rect:
        """获取主容器矩形 - Tăng kích thước để khung lớn hơn"""
        margin = self.get_margin()
        # Tăng kích thước container lên 95% màn hình và tăng max size
        max_width = min(int(self.window_width * 0.95), 1000)
        max_height = min(int(self.window_height * 0.95), 1100)
        
        x = (self.window_width - max_width) // 2
        y = (self.window_height - max_height) // 2
        
        return pygame.Rect(x, y, max_width, max_height)
        
    def get_left_column_rect(self, container: pygame.Rect) -> pygame.Rect:
        """获取左列矩形"""
        margin = self.get_margin()
        spacing = self.get_spacing()
        width = (container.width - margin * 3) // 2
        return pygame.Rect(container.x + margin, container.y + margin, width, container.height - margin * 2)
        
    def get_right_column_rect(self, container: pygame.Rect) -> pygame.Rect:
        """获取右列矩形"""
        margin = self.get_margin()
        left_col = self.get_left_column_rect(container)
        width = container.width - left_col.width - margin * 3
        return pygame.Rect(left_col.right + margin, container.y + margin, width, container.height - margin * 2)
        
    def get_input_rect(self, left_col: pygame.Rect, y_offset: int) -> pygame.Rect:
        """获取输入框矩形"""
        margin = self.get_margin()
        height = self.scale(36)
        return pygame.Rect(left_col.x, left_col.y + y_offset, left_col.width - margin * 2, height)
        
    def get_best_of_n_buttons(self, left_col: pygame.Rect, y_offset: int) -> list[pygame.Rect]:
        """获取Best-of-N按钮矩形列表"""
        margin = self.get_margin()
        spacing = self.scale(10)
        button_size = min((left_col.width - margin * 2 - spacing * 3) // 4, self.scale(60))
        
        buttons = []
        for i in range(4):
            x = left_col.x + margin + i * (button_size + spacing)
            y = left_col.y + y_offset
            buttons.append(pygame.Rect(x, y, button_size, button_size))
        return buttons
        
    def get_avatar_preview_rects(self, left_col: pygame.Rect, y_offset: int) -> Tuple[pygame.Rect, pygame.Rect]:
        """获取头像预览矩形 - 增大尺寸"""
        margin = self.get_margin()
        spacing = self.scale(15)
        # 增大头像预览框，最小120px
        size = max(self.scale(120), min((left_col.width - margin * 2 - spacing) // 2, self.scale(180)))
        
        x1 = left_col.x + margin
        x2 = x1 + size + spacing
        y = left_col.y + y_offset
        
        return (
            pygame.Rect(x1, y, size, size),
            pygame.Rect(x2, y, size, size)
        )
        
    def get_slider_rect(self, left_col: pygame.Rect, y_offset: int, index: int) -> pygame.Rect:
        """获取滑块轨道矩形"""
        margin = self.get_margin()
        width = left_col.width - margin * 2
        height = self.scale(6)
        spacing = self.scale(34)
        y = left_col.y + y_offset + index * spacing
        return pygame.Rect(left_col.x + margin, y, width, height)
        
    def get_start_button_rect(self, container: pygame.Rect) -> pygame.Rect:
        """获取开始按钮矩形 - Tối ưu để hiển thị đầy đủ button (phóng to x4)"""
        margin = self.get_margin()
        # Tăng width và height để có đủ không gian cho button lớn (x4)
        width = min(int(container.width * 0.95), self.scale(600))  # Tăng width lên 95% để fit button x4
        height = self.scale(250)  # Tăng height lên 250px để có đủ không gian cho button lớn
        x = container.centerx - width // 2
        # Đặt button gần bottom hơn nhưng vẫn để margin
        y = container.bottom - height - margin
        return pygame.Rect(x, y, width, height)
        
    def get_option_row_rect(self, right_col: pygame.Rect, y_offset: int) -> pygame.Rect:
        """获取选项行矩形"""
        margin = self.get_spacing()
        height = self.scale(32)
        return pygame.Rect(right_col.x, right_col.y + y_offset, right_col.width - margin * 2, height)
        
    def get_difficulty_button_rects(self, right_col: pygame.Rect, y_offset: int) -> list[pygame.Rect]:
        """获取难度按钮矩形列表 - 防止重叠"""
        margin = self.get_spacing()
        spacing = self.scale(8)  # 减小间距防止重叠
        # 确保按钮有足够空间，最小宽度70px
        available_width = right_col.width - margin * 2 - spacing * 2
        button_width = max(self.scale(70), available_width // 3)
        button_height = self.scale(70)  # 增大高度以容纳图标和文本
        
        buttons = []
        for i in range(3):
            x = right_col.x + margin + i * (button_width + spacing)
            y = right_col.y + y_offset
            buttons.append(pygame.Rect(x, y, button_width, button_height))
        return buttons
    
    def get_piece_skin_button_rects(self, right_col: pygame.Rect, y_offset: int, num_skins: int = 3) -> list[pygame.Rect]:
        """获取棋子皮肤按钮矩形列表"""
        margin = self.get_spacing()
        spacing = self.scale(8)
        available_width = right_col.width - margin * 2 - spacing * (num_skins - 1)
        button_width = max(self.scale(80), available_width // num_skins)
        button_height = self.scale(50)
        
        buttons = []
        for i in range(num_skins):
            x = right_col.x + margin + i * (button_width + spacing)
            y = right_col.y + y_offset
            buttons.append(pygame.Rect(x, y, button_width, button_height))
        return buttons


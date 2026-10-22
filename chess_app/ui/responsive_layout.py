"""
完全响应式布局系统 - 使用比例和约束，类似CSS Flexbox
支持最小窗口大小、最大尺寸限制、响应式字体
"""
from __future__ import annotations

import pygame
from typing import Tuple
from .theme import ThemeTokens


class ResponsiveLayoutSystem:
    """完全响应式布局系统 - 类似CSS Flexbox的行为"""
    
    # 最小和最大窗口尺寸
    MIN_WINDOW_WIDTH = 1024
    MIN_WINDOW_HEIGHT = 768
    MAX_BOARD_SIZE = 1200  # 最大棋盘尺寸（4K显示器）
    
    # 响应式字体大小范围
    FONT_SIZE_BASE_MIN = 12
    FONT_SIZE_BASE_MAX = 18
    FONT_SIZE_SMALL_MIN = 10
    FONT_SIZE_SMALL_MAX = 14
    FONT_SIZE_LARGE_MIN = 16
    FONT_SIZE_LARGE_MAX = 24
    
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
        """计算缩放因子（基于最小窗口大小）"""
        base_width = self.MIN_WINDOW_WIDTH
        base_height = self.MIN_WINDOW_HEIGHT
        scale_w = self.window_width / base_width
        scale_h = self.window_height / base_height
        # 使用较小的缩放因子，确保内容不会过大
        return min(scale_w, scale_h, 2.0)  # 最大2倍缩放
        
    def update(self, width: int, height: int) -> None:
        """更新窗口大小"""
        self.window_width = max(self.MIN_WINDOW_WIDTH, width)
        self.window_height = max(self.MIN_WINDOW_HEIGHT, height)
        self._scale_factor = self._calculate_scale_factor()

    @property
    def scale_factor(self) -> float:
        """当前缩放因子，供外部比较变化"""
        return self._scale_factor
        
    def scale(self, value: float) -> int:
        """缩放值（响应式）"""
        return int(value * self._scale_factor)
        
    def clamp_font_size(self, base_size: int, min_size: int, max_size: int) -> int:
        """响应式字体大小"""
        size = int(base_size * self._scale_factor)
        return max(min_size, min(size, max_size))
        
    def get_font_size_base(self) -> int:
        """基础字体大小（响应式）"""
        return self.clamp_font_size(14, self.FONT_SIZE_BASE_MIN, self.FONT_SIZE_BASE_MAX)
        
    def get_font_size_small(self) -> int:
        """小字体大小（响应式）"""
        return self.clamp_font_size(12, self.FONT_SIZE_SMALL_MIN, self.FONT_SIZE_SMALL_MAX)
        
    def get_font_size_large(self) -> int:
        """大字体大小（响应式）"""
        return self.clamp_font_size(20, self.FONT_SIZE_LARGE_MIN, self.FONT_SIZE_LARGE_MAX)
        
    def get_margin(self) -> int:
        """响应式边距"""
        return self.scale(16)
        
    def get_spacing(self) -> int:
        """响应式间距"""
        return self.scale(8)
        
    def get_board_size(self) -> int:
        """计算棋盘大小 - 保持正方形，响应式，确保不溢出"""
        margin = self.get_margin()
        coord_space = self.scale(40)  # 坐标空间
        
        # 计算面板宽度（右侧）
        min_panel_width = self.scale(350)
        max_panel_width = int(self.window_width * 0.40)
        estimated_panel_width = max(min_panel_width, min(max_panel_width, int(self.window_width * 0.30)))
        
        # 计算可用空间（考虑面板）
        available_width = self.window_width - estimated_panel_width - margin * 2 - coord_space
        available_height = self.window_height - margin * 2 - coord_space
        
        # 取较小值以确保正方形
        board_size = min(available_width, available_height)
        
        # 确保是8的倍数
        board_size = (board_size // 8) * 8
        
        # 应用最小和最大限制
        min_board = self.scale(400)  # 降低最小值以适应小屏幕
        max_board = min(self.scale(1000), self.MAX_BOARD_SIZE)
        board_size = max(min_board, min(board_size, max_board))
        
        return board_size
        
    def get_board_rect(self) -> pygame.Rect:
        """获取棋盘矩形 - 居中在左侧"""
        board_size = self.get_board_size()
        margin = self.get_margin()
        coord_space = self.scale(20)
        
        # 计算位置
        board_x = margin + coord_space
        # 垂直居中
        board_y = (self.window_height - board_size - coord_space * 2) // 2 + coord_space
        
        return pygame.Rect(board_x, board_y, board_size, board_size)
        
    def get_panel_rect(self) -> pygame.Rect:
        """获取控制面板矩形 - 位于右侧，响应式宽度，确保不溢出"""
        board_rect = self.get_board_rect()
        margin = self.get_margin()
        coord_space = self.scale(20)
        
        # 面板宽度：最小320px，最大40%窗口宽度
        min_panel_width = self.scale(320)
        max_panel_width = int(self.window_width * 0.40)
        
        # 计算可用宽度（确保不超出窗口）
        available_width = self.window_width - board_rect.right - coord_space - margin * 2
        panel_width = max(min_panel_width, min(max_panel_width, available_width))
        
        # 确保面板不超出窗口
        panel_x = board_rect.right + coord_space + margin
        if panel_x + panel_width > self.window_width - margin:
            panel_width = self.window_width - panel_x - margin
        
        panel_y = margin
        panel_height = self.window_height - margin * 2
        
        return pygame.Rect(panel_x, panel_y, panel_width, panel_height)
        
    def get_square_size(self) -> int:
        """获取棋盘格子大小"""
        return self.get_board_size() // 8
        
    def get_players_container_rect(self, panel_rect: pygame.Rect) -> pygame.Rect:
        """获取玩家容器矩形 - 包含两个垂直堆叠的玩家卡片"""
        margin = self.get_margin()
        spacing = self.get_spacing()
        
        # Layout dọc: tổng chiều cao cho 2 cards + spacing
        # Mỗi card khoảng 100-140px, tổng cộng với spacing
        single_card_height = max(100, min(self.scale(140), int(self.window_height * 0.16)))
        container_height = single_card_height * 2 + spacing
        container_width = panel_rect.width - margin * 2
        container_y = panel_rect.y + margin

        return pygame.Rect(panel_rect.x + margin, container_y, container_width, container_height)
    
    def get_player_profile_rect(self, index: int, panel_rect: pygame.Rect) -> pygame.Rect:
        """获取玩家资料矩形 - 垂直堆叠显示，响应式尺寸"""
        container_rect = self.get_players_container_rect(panel_rect)
        margin = self.get_margin()
        spacing = self.get_spacing()
        
        # Layout dọc: mỗi card chiếm toàn bộ chiều rộng
        profile_width = container_rect.width
        profile_height = max(100, min(self.scale(140), int(self.window_height * 0.16)))
        
        # Vị trí: card thứ 2 ở dưới card thứ 1
        x = container_rect.x
        y = container_rect.y + index * (profile_height + spacing)
        
        return pygame.Rect(x, y, profile_width, profile_height)
        
    def get_button_rect(self, index: int, panel_rect: pygame.Rect) -> pygame.Rect:
        """获取按钮矩形 - 响应式网格布局"""
        margin = self.get_margin()
        spacing = self.get_spacing()
        buttons_per_row = 2
        
        # 响应式按钮尺寸 - 使用clamp确保在所有缩放级别下合适
        button_height = max(34, min(self.scale(42), int(self.window_height * 0.05)))
        min_button_width = max(96, min(self.scale(120), int(self.window_width * 0.1)))
        
        # 计算可用宽度
        available_width = panel_rect.width - margin * 2
        button_width = (available_width - spacing) // buttons_per_row
        button_width = max(min_button_width, button_width)
        
        # 计算位置
        row = index // buttons_per_row
        col = index % buttons_per_row
        
        # 起始位置（玩家容器下方）
        container_rect = self.get_players_container_rect(panel_rect)
        start_x = panel_rect.x + margin
        start_y = container_rect.bottom + margin + spacing
        
        x = start_x + col * (button_width + spacing)
        y = start_y + row * (button_height + spacing)
        
        # 第5个按钮（resign）占据整行
        if index == 4:
            button_width = available_width
            x = panel_rect.x + margin
            
        return pygame.Rect(x, y, button_width, button_height)
        
    def get_history_rect(self, panel_rect: pygame.Rect) -> pygame.Rect:
        """获取历史记录矩形 - 响应式高度"""
        margin = self.get_margin()
        spacing = self.get_spacing()
        
        # 计算可用空间 - 使用实际的容器高度
        container_rect = self.get_players_container_rect(panel_rect)
        last_button_rect = self.get_button_rect(4, panel_rect)
        scoreboard_rect = self.get_scoreboard_rect(panel_rect)

        available_height = max(60, scoreboard_rect.top - spacing - (last_button_rect.bottom + spacing))

        # 使用clamp确保历史记录区域有合理的高度
        history_height = max(self.scale(160), min(available_height, int(self.window_height * 0.4)))
        history_width = panel_rect.width - margin * 2
        
        # 计算Y位置（按钮区域下方）
        start_y = last_button_rect.bottom + spacing
        
        return pygame.Rect(panel_rect.x + margin, start_y, history_width, history_height)
        
    def get_scoreboard_rect(self, panel_rect: pygame.Rect) -> pygame.Rect:
        """获取记分板矩形 - 固定在底部"""
        margin = self.get_margin()
        # 响应式高度 - 使用clamp确保在所有缩放级别下合适
        scoreboard_height = max(96, min(self.scale(140), int(self.window_height * 0.16)))
        scoreboard_width = panel_rect.width - margin * 2
        scoreboard_y = panel_rect.bottom - scoreboard_height - margin
        
        return pygame.Rect(panel_rect.x + margin, scoreboard_y, scoreboard_width, scoreboard_height)
        
    def get_coord_font_size(self) -> int:
        """坐标字体大小 - 响应式，使用clamp确保在所有缩放级别下正确对齐"""
        square_size = self.get_square_size()
        # 坐标字体约为格子大小的12-18%，使用clamp确保可读性
        coord_size = max(8, min(int(square_size * 0.15), 14))
        return coord_size
    
    def get_avatar_size(self, profile_rect: pygame.Rect) -> int:
        """获取头像大小 - 响应式，优化空间使用 - Layout dọc"""
        # Layout dọc: avatar nhỏ hơn vì card thấp hơn, khoảng 70-80% chiều cao
        # Card thấp hơn nên avatar cũng nhỏ hơn để cân đối
        avatar_size = max(70, min(int(profile_rect.height * 0.72), 110))
        return avatar_size

    def get_footer_rect(self) -> pygame.Rect:
        """底部装饰背景区域"""
        footer_height = max(self.scale(90), int(self.window_height * 0.12))
        return pygame.Rect(0, self.window_height - footer_height, self.window_width, footer_height)


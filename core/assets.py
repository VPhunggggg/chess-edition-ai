from __future__ import annotations

import os
import pygame
from typing import Dict, Optional, Tuple


class AssetManager:
    """Loads and caches images/fonts; provides fallbacks when files are missing."""

    def __init__(self, avatars_dir: str, pieces_dir: str, avatar_size: int, font_name: str) -> None:
        self.avatars_dir = avatars_dir
        self.pieces_dir = pieces_dir
        self.avatar_size = avatar_size
        self.font_name = font_name
        self._image_cache: Dict[tuple, pygame.Surface] = {}
        self._font_cache: Dict[Tuple[str, int], pygame.font.Font] = {}

    def get_font(self, size: int) -> pygame.font.Font:
        key = (self.font_name, size)
        if key not in self._font_cache:
            self._font_cache[key] = pygame.font.SysFont(self.font_name, size)
        return self._font_cache[key]

    def _load_and_scale(self, path: str, size: Optional[Tuple[int, int]] = None) -> pygame.Surface:
        key = (path, size if size else (0, 0))
        if key in self._image_cache:
            return self._image_cache[key]
        try:
            image = pygame.image.load(path).convert_alpha()
            if size is not None:
                image = self._scale_keep_ratio(image, size)
            self._image_cache[key] = image
            return image
        except Exception:
            # Fallback placeholder
            w, h = size if size else (128, 128)
            placeholder = pygame.Surface((w, h), pygame.SRCALPHA)
            placeholder.fill((60, 60, 60, 255))
            pygame.draw.rect(placeholder, (100, 100, 100), placeholder.get_rect(), 4)
            return placeholder

    def _scale_keep_ratio(self, surf: pygame.Surface, target: Tuple[int, int]) -> pygame.Surface:
        tw, th = target
        sw, sh = surf.get_size()
        scale = min(tw / sw, th / sh)
        new_size = (max(1, int(sw * scale)), max(1, int(sh * scale)))
        return pygame.transform.smoothscale(surf, new_size)

    def get_avatar(self, name: str, size: Optional[int] = None) -> pygame.Surface:
        """Return avatar surface scaled to requested size (defaults to manager avatar size)."""
        path = name
        if not os.path.isabs(path):
            path = os.path.join(self.avatars_dir, name)
        target = size if size is not None else self.avatar_size
        return self._load_and_scale(path, (target, target))

    def get_piece_image(self, code: str, size: int) -> pygame.Surface:
        """Get piece image by code like 'w_king', 'b_queen'. If missing, draw letter fallback."""
        filename = f"{code}.png"
        path = os.path.join(self.pieces_dir, filename)
        if os.path.exists(path):
            return self._load_and_scale(path, (size, size))
        # Fallback: draw letter
        surf = pygame.Surface((size, size), pygame.SRCALPHA)
        bg = (238, 238, 210) if code.startswith("w_") else (118, 150, 86)
        fg = (10, 10, 10) if code.startswith("w_") else (240, 240, 240)
        surf.fill(bg)
        letter_map = {
            "king": "K",
            "queen": "Q",
            "rook": "R",
            "bishop": "B",
            "knight": "N",
            "pawn": "P",
        }
        key = code.split("_", 1)[1] if "_" in code else code
        text = letter_map.get(key, "?")
        font = self.get_font(int(size * 0.6))
        txt = font.render(text, True, fg)
        rect = txt.get_rect(center=(size // 2, size // 2))
        surf.blit(txt, rect)
        pygame.draw.rect(surf, (0, 0, 0), surf.get_rect(), 1)
        return surf

    def get_ui_image(self, filename: str, size: Tuple[int, int]) -> Optional[pygame.Surface]:
        """Load an arbitrary UI image from assets root (not pieces/avatars). Returns scaled image or None if missing."""
        path = filename
        if not os.path.isabs(path):
            # default to project assets root
            root = os.path.dirname(self.avatars_dir)
            path = os.path.join(root, filename)
        if not os.path.exists(path):
            return None
        try:
            img = pygame.image.load(path).convert_alpha()
            img = self._scale_keep_ratio(img, size)
            return img
        except Exception:
            return None

    def get_menu_image(self, filename: str, size: Tuple[int, int]) -> Optional[pygame.Surface]:
        """Load an image from the pieces directory (used for menu art)."""
        path = filename
        if not os.path.isabs(path):
            path = os.path.join(self.pieces_dir, filename)
        if not os.path.exists(path):
            return None
        try:
            img = pygame.image.load(path).convert_alpha()
            img = self._scale_keep_ratio(img, size)
            return img
        except Exception:
            return None

    def get_decorate_image(self, filename: str, size: Tuple[int, int]) -> Optional[pygame.Surface]:
        """Load an image from the Decorate directory (used for backgrounds and decorations)."""
        # Get decorate directory from config
        decorate_dir = os.path.join(".", "assets", "Decorate")
        path = filename
        if not os.path.isabs(path):
            path = os.path.join(decorate_dir, filename)
        if not os.path.exists(path):
            return None
        try:
            img = pygame.image.load(path).convert()
            # For backgrounds, use scale to fill instead of keep ratio
            if size:
                img = pygame.transform.smoothscale(img, size)
            return img
        except Exception:
            return None



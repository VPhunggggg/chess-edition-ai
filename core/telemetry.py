from __future__ import annotations

import csv
import os
import time
from dataclasses import dataclass
from typing import List, Optional

import pygame


LOG_PATH = os.path.join(".", "data", "perf_log.csv")


@dataclass
class FrameStats:
    fps: float
    frame_ms: float
    rects: int
    ai_ms: float


class Telemetry:
    def __init__(self, font: pygame.font.Font) -> None:
        self.font = font
        self.enabled_overlay = False
        self.enabled_logging = False
        self.samples: List[float] = []
        self.last_time = time.perf_counter()
        self.last_log = time.time()
        self.ai_ms_current = 0.0

        # Prepare CSV header if logging enabled later
        os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)

    def toggle_overlay(self) -> None:
        self.enabled_overlay = not self.enabled_overlay

    def toggle_logging(self) -> None:
        self.enabled_logging = not self.enabled_logging
        if self.enabled_logging and not os.path.exists(LOG_PATH):
            with open(LOG_PATH, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["ts", "fps", "avg_ms", "ai_ms"])  # 1s buckets

    def begin_frame(self) -> None:
        self.frame_start = time.perf_counter()

    def end_frame(self, surface: pygame.Surface, num_rects: int) -> Optional[pygame.Rect]:
        now = time.perf_counter()
        dt = (now - self.frame_start) * 1000.0
        self.samples.append(dt)
        if len(self.samples) > 120:  # ~2 seconds window
            self.samples.pop(0)
        avg_ms = sum(self.samples) / len(self.samples)
        fps = 1000.0 / avg_ms if avg_ms > 0 else 0.0

        overlay_rect: Optional[pygame.Rect] = None
        if self.enabled_overlay:
            overlay = self.font.render(f"FPS:{fps:5.1f}  ms:{avg_ms:4.1f}  rects:{num_rects}  AI:{self.ai_ms_current:4.1f}ms", True, (255, 255, 0))
            overlay_rect = overlay.get_rect(topleft=(8, 6))
            surface.blit(overlay, overlay_rect)

        if self.enabled_logging and (time.time() - self.last_log) >= 1.0:
            with open(LOG_PATH, "a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([int(time.time()), f"{fps:.1f}", f"{avg_ms:.2f}", f"{self.ai_ms_current:.2f}"])
            self.last_log = time.time()

        return overlay_rect

    def set_ai_ms(self, ms: float) -> None:
        self.ai_ms_current = ms



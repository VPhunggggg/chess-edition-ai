from __future__ import annotations

import time
import pygame
from typing import Optional

from core.config import AppConfig
from core.assets import AssetManager
from core.history import HistoryWriter


class ResultsScene:
    def __init__(self, config: AppConfig, assets: AssetManager, set_id: str, N: int, player_human, player_ai, wins_human: int, wins_ai: int, penalties) -> None:
        self.config = config
        self.assets = assets
        self.set_id = set_id
        self.N = N
        self.player_human = player_human
        self.player_ai = player_ai
        self.wins_human_raw = wins_human
        self.wins_ai_raw = wins_ai
        self.penalties = penalties

        self.font = self.assets.get_font(28)
        self.small = self.assets.get_font(18)
        self.btn_quit = pygame.Rect(self.config.margin_px, self.config.window_height - 80, 200, 44)

        # Compute effective wins and winner
        eff_h = max(0, wins_human - (penalties['human']['undo'] + penalties['human']['hint']))
        eff_a = max(0, wins_ai - (penalties['ai']['undo'] + penalties['ai']['hint']))
        if eff_h > eff_a:
            self.winner = "human"
        elif eff_a > eff_h:
            self.winner = "ai"
        else:
            self.winner = None

        # Persist results.json entry
        self.history = HistoryWriter(self.config.history_csv, self.config.results_json)
        # Determine logged-in account (if any)
        try:
            current_account = self.config.current_user.get("name") if isinstance(self.config.current_user, dict) else (self.config.current_user or "")
        except Exception:
            current_account = ""
        self.history.write_set_result({
            "set_id": set_id,
            "mode": getattr(self.config, 'game_mode', 'PvAI'),
            "ai_difficulty": getattr(self.config, 'ai_difficulty', None) if getattr(self.config, 'game_mode', 'PvAI') == 'PvAI' else None,
            "swap_sides_between_games": getattr(self.config, 'swap_sides_between_games', True),
            "N": N,
            "player_human": {
                "name": player_human.name,
                "gender": player_human.gender,
                "avatar": player_human.avatar_path,
                # Persist account username to bind rankings to registered users
                "account": current_account,
            },
            "player_ai": {"name": player_ai.name, "avatar": player_ai.avatar_path},
            "wins_human": self.wins_human_raw,  # Lưu RAW wins, không phải effective wins
            "wins_ai": self.wins_ai_raw,  # Lưu RAW wins
            "penalties": penalties,
            "winner": self.winner,  # Winner dựa trên effective score
            "finished_at": time.time(),
        })

    def handle_event(self, event: pygame.event.Event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            if self.btn_quit.collidepoint(event.pos):
                pygame.event.post(pygame.event.Event(pygame.QUIT))
        return None

    def update(self, dt: float):
        return None

    def render(self, surface: pygame.Surface) -> None:
        msg = "SET Finished" if self.winner is not None else "SET Draw"
        surface.blit(self.font.render(msg, True, self.config.colors["text"]), (self.config.margin_px, self.config.margin_px))
        eff_h = max(0, self.wins_human_raw - (self.penalties['human']['undo'] + self.penalties['human']['hint']))
        eff_a = max(0, self.wins_ai_raw - (self.penalties['ai']['undo'] + self.penalties['ai']['hint']))
        surface.blit(self.small.render(f"Best-of-{self.N}", True, self.config.colors["text"]), (self.config.margin_px, 80))
        # Label adapt by mode
        mode = getattr(self.config, 'game_mode', 'PvAI')
        if mode == 'PvP':
            surface.blit(self.small.render(f"White: {eff_h} | Black: {eff_a}", True, self.config.colors["text"]), (self.config.margin_px, 110))
            if eff_h > eff_a:
                surface.blit(self.small.render("White wins the set!", True, self.config.colors["success"]), (self.config.margin_px, 140))
            elif eff_a > eff_h:
                surface.blit(self.small.render("Black wins the set!", True, self.config.colors["success"]), (self.config.margin_px, 140))
            else:
                surface.blit(self.small.render("Set drawn.", True, self.config.colors["muted"]), (self.config.margin_px, 140))
            return
        surface.blit(self.small.render(f"Human: {eff_h} | AI: {eff_a}", True, self.config.colors["text"]), (self.config.margin_px, 110))
        if self.winner == "human":
            surface.blit(self.small.render("Human wins the set!", True, self.config.colors["success"]), (self.config.margin_px, 140))
        elif self.winner == "ai":
            surface.blit(self.small.render("AI wins the set!", True, self.config.colors["success"]), (self.config.margin_px, 140))
        else:
            surface.blit(self.small.render("Set drawn.", True, self.config.colors["muted"]), (self.config.margin_px, 140))

        # Quit button
        pygame.draw.rect(surface, (70, 70, 70), self.btn_quit, 0, border_radius=8)
        pygame.draw.rect(surface, self.config.colors["accent"], self.btn_quit, 2, border_radius=8)
        surface.blit(self.small.render("Quit", True, self.config.colors["text"]), (self.btn_quit.x + 12, self.btn_quit.y + 12))



"""Persistência e aplicação de volumes de música e efeitos sonoros."""

import json
import os

import pygame

from src.config.paths import SETTINGS_PATH

DEFAULT_MUSIC_VOLUME = 0.2
DEFAULT_SFX_VOLUME = 1.0
VOLUME_STEP = 0.05


class AudioSettings:
    def __init__(self, music_volume: float = DEFAULT_MUSIC_VOLUME,
                 sfx_volume: float = DEFAULT_SFX_VOLUME):
        self.music_volume = self._clamp(music_volume)
        self.sfx_volume = self._clamp(sfx_volume)

    @staticmethod
    def _clamp(value: float) -> float:
        return max(0.0, min(1.0, float(value)))

    @classmethod
    def load(cls) -> "AudioSettings":
        if not os.path.exists(SETTINGS_PATH):
            return cls()
        try:
            with open(SETTINGS_PATH, encoding="utf-8") as f:
                data = json.load(f)
            return cls(
                music_volume=data.get("music_volume", DEFAULT_MUSIC_VOLUME),
                sfx_volume=data.get("sfx_volume", DEFAULT_SFX_VOLUME),
            )
        except (json.JSONDecodeError, OSError, TypeError, ValueError):
            return cls()

    def save(self):
        data = {
            "music_volume": round(self.music_volume, 3),
            "sfx_volume": round(self.sfx_volume, 3),
        }
        with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f)

    def adjust_music(self, delta: float) -> bool:
        prev = self.music_volume
        self.music_volume = self._clamp(self.music_volume + delta)
        return self.music_volume != prev

    def adjust_sfx(self, delta: float) -> bool:
        prev = self.sfx_volume
        self.sfx_volume = self._clamp(self.sfx_volume + delta)
        return self.sfx_volume != prev

    def apply(self, game):
        """Aplica volumes ao mixer de música e ao gerenciador de SFX."""
        pygame.mixer.music.set_volume(self.music_volume)
        sounds = getattr(game, "sounds", None)
        if sounds is not None:
            sounds.set_master_volume(self.sfx_volume)

    def music_percent(self) -> int:
        return int(round(self.music_volume * 100))

    def sfx_percent(self) -> int:
        return int(round(self.sfx_volume * 100))

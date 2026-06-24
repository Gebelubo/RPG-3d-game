from dataclasses import dataclass, field
from typing import Optional, List
import random
import math

@dataclass
class Stats:
    name:     str = "Unknown"
    level:    int = 1
    max_hp:   int = 100
    hp:       int = 100
    max_mp:   int = 50
    mp:       int = 50
    atk:      int = 10
    defense:  int = 5
    spd:      int = 10
    xp:       int = 0
    xp_next:  int = 100
    shield_time: float = 0.0

    def is_alive(self): return self.hp > 0

    @property
    def is_shielded(self) -> bool:
        return self.shield_time > 0.0

    def take_damage(self, amount: int) -> int:
        eff = max(1, amount - self.defense)
        self.hp = max(0, self.hp - eff)
        return eff

    def heal(self, amount: int):
        self.hp = min(self.max_hp, self.hp + amount)

    def restore_mp(self, amount: int):
        self.mp = min(self.max_mp, self.mp + amount)

    def use_mp(self, amount: int) -> bool:
        if self.mp >= amount:
            self.mp -= amount
            return True
        return False

    def gain_xp(self, amount: int) -> bool:
        self.xp += amount
        if self.xp >= self.xp_next:
            self._level_up(); return True
        return False

    def _level_up(self):
        self.level += 1
        self.xp -= self.xp_next
        self.xp_next = int(self.xp_next * 1.5)
        self.max_hp += 20; self.max_mp += 10
        self.hp = self.max_hp; self.mp = self.max_mp
        self.atk += 3; self.defense += 2; self.spd += 1


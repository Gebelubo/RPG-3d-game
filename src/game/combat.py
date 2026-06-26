from dataclasses import dataclass, field
from typing import Optional, List
import random
import math

from src.entities.stats import Stats
from src.entities.inventory import Inventory

from src.db.item import ITEM_DB
from src.db.spell import SPELL_DB

@dataclass
class CombatLog:
    messages: list = field(default_factory=list)
    def add(self, msg): self.messages.append(msg)
    def clear(self): self.messages.clear()
    def recent(self, n=5): return self.messages[-n:]

class CombatSystem:
    def __init__(self, player: Stats, enemy: Stats):
        self.player = player; self.enemy = enemy
        self.log = CombatLog(); self._turn = "player"; self.result = None

    def is_over(self): return self.result is not None

    def player_attack(self):
        if self._turn != "player" or self.is_over(): return
        dmg = max(1, self.player.atk + random.randint(-2,2))
        actual = self.enemy.take_damage(dmg)
        self.log.add(f"Você acertou {self.enemy.name} causando {actual} de dano.")
        self._check_end()
        if not self.is_over(): self._enemy_turn()

    def player_cast(self, spell_id: str):
        if self._turn != "player" or self.is_over(): return False
        sp = SPELL_DB.get(spell_id)
        if not sp or not self.player.use_mp(sp.mp_cost): return False
        actual = self.enemy.take_damage(sp.damage)
        self.log.add(f"{sp.name}! {self.enemy.name} recebeu {actual} de dano ({sp.element}).")
        self._check_end()
        if not self.is_over(): self._enemy_turn()
        return True

    def player_use_item(self, item_id: str, inventory: Inventory) -> bool:
        if self._turn != "player" or self.is_over(): return False
        item = ITEM_DB.get(item_id)
        if not item or not inventory.remove(item_id): return False
        if item.heal_hp > 0:
            self.player.heal(item.heal_hp)
            self.log.add(f"Você usou {item.name} e recuperou {item.heal_hp} HP.")
        if item.heal_mp > 0:
            self.player.restore_mp(item.heal_mp)
            self.log.add(f"Você usou {item.name} e recuperou {item.heal_mp} MP.")
        self._enemy_turn()
        return True

    def player_flee(self) -> bool:
        chance = 50 + (self.player.spd - self.enemy.spd) * 5
        if random.randint(1,100) <= chance:
            self.result = "fled"; self.log.add("Você fugiu!"); return True
        self.log.add("Não conseguiu escapar!"); self._enemy_turn(); return False

    def _enemy_turn(self):
        if self.enemy.is_alive():
            dmg = max(1, self.enemy.atk + random.randint(-2,2))
            actual = self.player.take_damage(dmg)
            self.log.add(f"{self.enemy.name} te atacou causando {actual} de dano.")
            self._check_end()
        self._turn = "player"

    def _check_end(self):
        if not self.enemy.is_alive():
            self.result = "win"
            xp = self.enemy.level * 20 + random.randint(5,15)
            leveled = self.player.gain_xp(xp)
            self.log.add(f"{self.enemy.name} derrotado! +{xp} XP")
            if leveled: self.log.add(f"*** LEVEL UP! Nível {self.player.level} ***")
        elif not self.player.is_alive():
            self.result = "lose"; self.log.add("Você foi derrotado...")



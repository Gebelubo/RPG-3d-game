"""
rpg_data.py  –  Pure-Python RPG data model.
No rendering code here – only game logic data structures.
"""

from dataclasses import dataclass, field
from typing import Optional
import random


# ─────────────────────────────────────────────────────────────────────────────
# Stats
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class Stats:
    name:     str   = "Unknown"
    level:    int   = 1
    max_hp:   int   = 100
    hp:       int   = 100
    atk:      int   = 10
    defense:  int   = 5
    spd:      int   = 10
    xp:       int   = 0
    xp_next:  int   = 100

    def is_alive(self) -> bool:
        return self.hp > 0

    def take_damage(self, amount: int) -> int:
        effective = max(1, amount - self.defense)
        self.hp   = max(0, self.hp - effective)
        return effective

    def heal(self, amount: int):
        self.hp = min(self.max_hp, self.hp + amount)

    def gain_xp(self, amount: int) -> bool:
        """Returns True if leveled up."""
        self.xp += amount
        if self.xp >= self.xp_next:
            self._level_up()
            return True
        return False

    def _level_up(self):
        self.level   += 1
        self.xp      -= self.xp_next
        self.xp_next  = int(self.xp_next * 1.5)
        self.max_hp  += 20
        self.hp       = self.max_hp
        self.atk     += 3
        self.defense += 2
        self.spd     += 1


# ─────────────────────────────────────────────────────────────────────────────
# Items
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class Item:
    id:          str
    name:        str
    description: str
    item_type:   str   = "consumable"   # consumable / weapon / armor / key
    value:       int   = 0              # gold value
    heal_hp:     int   = 0
    atk_bonus:   int   = 0
    def_bonus:   int   = 0


ITEM_DB: dict[str, Item] = {
    "health_potion_s": Item("health_potion_s", "Small Potion",
                            "Restores 30 HP.", heal_hp=30, value=10),
    "health_potion_l": Item("health_potion_l", "Large Potion",
                            "Restores 80 HP.", heal_hp=80, value=30),
    "iron_sword": Item("iron_sword", "Iron Sword",
                       "A sturdy iron sword.", item_type="weapon",
                       atk_bonus=8, value=50),
    "leather_armor": Item("leather_armor", "Leather Armor",
                          "Basic leather protection.", item_type="armor",
                          def_bonus=5, value=40),
}


@dataclass
class Inventory:
    items:  dict[str, int] = field(default_factory=dict)   # item_id → qty
    gold:   int             = 0

    def add(self, item_id: str, qty: int = 1):
        self.items[item_id] = self.items.get(item_id, 0) + qty

    def remove(self, item_id: str, qty: int = 1) -> bool:
        if self.items.get(item_id, 0) >= qty:
            self.items[item_id] -= qty
            if self.items[item_id] == 0:
                del self.items[item_id]
            return True
        return False

    def has(self, item_id: str, qty: int = 1) -> bool:
        return self.items.get(item_id, 0) >= qty


# ─────────────────────────────────────────────────────────────────────────────
# Combat
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class CombatLog:
    messages: list[str] = field(default_factory=list)

    def add(self, msg: str):
        self.messages.append(msg)

    def clear(self):
        self.messages.clear()

    def recent(self, n: int = 5) -> list[str]:
        return self.messages[-n:]


class CombatSystem:
    """
    Turn-based combat engine.
    Call start(), then actions each turn until is_over().
    """

    def __init__(self, player: Stats, enemy: Stats):
        self.player  = player
        self.enemy   = enemy
        self.log     = CombatLog()
        self._turn   = "player"   # "player" | "enemy"
        self.result  = None       # None | "win" | "lose" | "fled"

    def is_over(self) -> bool:
        return self.result is not None

    # ── Player actions ────────────────────────────────────────────────────────

    def player_attack(self):
        if self._turn != "player" or self.is_over():
            return
        dmg = self._calc_damage(self.player, self.enemy)
        actual = self.enemy.take_damage(dmg)
        self.log.add(f"You hit {self.enemy.name} for {actual} damage.")
        self._check_end()
        if not self.is_over():
            self._enemy_turn()

    def player_use_item(self, item_id: str, inventory: Inventory) -> bool:
        if self._turn != "player" or self.is_over():
            return False
        item = ITEM_DB.get(item_id)
        if not item or not inventory.remove(item_id):
            return False
        if item.heal_hp > 0:
            self.player.heal(item.heal_hp)
            self.log.add(f"You use {item.name} and recover {item.heal_hp} HP.")
        self._enemy_turn()
        return True

    def player_flee(self) -> bool:
        """50 + (spd_diff * 5) % chance to flee."""
        chance = 50 + (self.player.spd - self.enemy.spd) * 5
        if random.randint(1, 100) <= chance:
            self.result = "fled"
            self.log.add("You fled successfully!")
            return True
        self.log.add("Couldn't escape!")
        self._enemy_turn()
        return False

    # ── Internal ──────────────────────────────────────────────────────────────

    def _calc_damage(self, attacker: Stats, defender: Stats) -> int:
        base = attacker.atk + random.randint(-2, 2)
        return max(1, base)

    def _enemy_turn(self):
        if self.enemy.is_alive():
            dmg = self._calc_damage(self.enemy, self.player)
            actual = self.player.take_damage(dmg)
            self.log.add(f"{self.enemy.name} hits you for {actual} damage.")
            self._check_end()
        self._turn = "player"

    def _check_end(self):
        if not self.enemy.is_alive():
            self.result = "win"
            xp_gain = self.enemy.level * 20 + random.randint(5, 15)
            leveled = self.player.gain_xp(xp_gain)
            self.log.add(f"{self.enemy.name} defeated! +{xp_gain} XP")
            if leveled:
                self.log.add(f"*** LEVEL UP! Now level {self.player.level} ***")
        elif not self.player.is_alive():
            self.result = "lose"
            self.log.add("You have been defeated...")


# ─────────────────────────────────────────────────────────────────────────────
# Player entity
# ─────────────────────────────────────────────────────────────────────────────

class Player:
    def __init__(self, name: str = "Hero"):
        self.stats      = Stats(name=name, level=1, max_hp=100, hp=100,
                                atk=12, defense=5, spd=10)
        self.inventory  = Inventory(gold=50)
        self.inventory.add("health_potion_s", 3)
        self.inventory.add("iron_sword",      1)

        # world position (separate from camera, for 3rd-person use)
        self.world_pos  = [0.0, 0.0, 0.0]
        self.facing_deg = 0.0

    def start_combat(self, enemy: Stats) -> CombatSystem:
        return CombatSystem(self.stats, enemy)

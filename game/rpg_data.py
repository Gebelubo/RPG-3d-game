"""
rpg_data.py  –  RPG data model for Pleiades Tower (Re:Zero).
"""
from dataclasses import dataclass, field
from typing import Optional, List
import random
import math

# ── Stats ─────────────────────────────────────────────────────────────────────

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

# ── Spells ────────────────────────────────────────────────────────────────────

@dataclass
class Spell:
    id: str; name: str; description: str
    mp_cost: int = 10; damage: int = 0; heal_hp: int = 0
    element: str = "none"; icon_color: tuple = (0.5, 0.5, 1.0)

SPELL_DB = {
    "shamac":    Spell("shamac",    "Shamac",              "Faz o inimigo perder sua pista por 10 segundos.",     mp_cost=15, damage=0,  element="dark", icon_color=(0.4,0.1,0.6)),
    "minya":     Spell("minya",     "Minya",              "Ataca o inimigo com a mão sombria.",                mp_cost=18, damage=40, element="dark", icon_color=(0.3,0.0,0.5)),
    "invisible_providence": Spell("invisible_providence", "Invisible Providence", "Ataca o inimigo de forma invisível.",       mp_cost=30, damage=60, element="light", icon_color=(0.8,0.8,0.4)),
    "emt":       Spell("emt",       "EMT",                "Protege contra ataques inimigos por 10 segundos.",  mp_cost=20, damage=0,  element="none", icon_color=(0.2,0.7,0.8)),
}
SPELL_LIST = ["shamac", "minya", "invisible_providence", "emt"]

# ── Items ────────────────────────────────────────────────────────────────────

@dataclass
class Item:
    id: str; name: str; description: str
    item_type: str = "consumable"; value: int = 0
    heal_hp: int = 0; heal_mp: int = 0
    atk_bonus: int = 0; def_bonus: int = 0

ITEM_DB = {
    "health_potion_s": Item("health_potion_s", "Amor de Emilia",   "Recupera vida.",  heal_hp=30,  value=10),
    "health_potion_l": Item("health_potion_l", "Amor de Emilia",   "Recupera vida.",  heal_hp=80,  value=30),
    "mana_potion":     Item("mana_potion",     "Confiança de Beatrice",    "Recupera mana.",  heal_mp=40,  value=20),
    "iron_sword":      Item("iron_sword",      "Iron Sword",     "Espada de ferro.", item_type="weapon", atk_bonus=8, value=50),
    "tracksuit":       Item("tracksuit",       "Agasalho do Subaru", "Icônico agasalho.", item_type="armor", def_bonus=3, value=0),
}

@dataclass
class Inventory:
    items: dict = field(default_factory=dict)
    gold: int = 0

    def add(self, item_id, qty=1):
        self.items[item_id] = self.items.get(item_id, 0) + qty

    def remove(self, item_id, qty=1) -> bool:
        if self.items.get(item_id, 0) >= qty:
            self.items[item_id] -= qty
            if self.items[item_id] == 0: del self.items[item_id]
            return True
        return False

    def has(self, item_id, qty=1) -> bool:
        return self.items.get(item_id, 0) >= qty

    def list_consumables(self):
        return [(ITEM_DB[iid], qty) for iid, qty in self.items.items()
                if iid in ITEM_DB and ITEM_DB[iid].item_type == "consumable"]

# ── Combat ────────────────────────────────────────────────────────────────────

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

# ── Enemy (real-time) ─────────────────────────────────────────────────────────

class Enemy:
    def __init__(self, name, level=1, world_pos=None, stationary: bool = False):
        hp = 40 + level * 15
        self.stats = Stats(name=name, level=level, max_hp=hp, hp=hp,
                           atk=6+level*2, defense=2, spd=8)
        self.world_pos = list(world_pos or [0,0,0])
        self.aggro = False; self.aggro_range = 6.0; self.attack_range = 1.8
        self.attack_cooldown = 0.0; self.dead = False; self.facing_deg = 0.0
        self.blind_time = 0.0
        self.stationary = stationary

    def update(self, player_pos, dt):
        if self.dead: return
        if self.blind_time > 0.0:
            self.blind_time = max(0.0, self.blind_time - dt)
            self.aggro = False
            self.attack_cooldown = max(0.0, self.attack_cooldown - dt)
            return
        dx = player_pos[0] - self.world_pos[0]
        dz = player_pos[2] - self.world_pos[2]
        dist = math.sqrt(dx*dx + dz*dz)
        # Stationary enemies do not move towards the player; they only attack when in range
        if self.stationary:
            self.aggro = dist < self.aggro_range
            if dist > 0.001:
                self.facing_deg = math.degrees(math.atan2(dx, dz))
            self.attack_cooldown = max(0.0, self.attack_cooldown - dt)
            return

        if dist < self.aggro_range:
            self.aggro = True
        if self.aggro and dist > 0.1:
            self.facing_deg = math.degrees(math.atan2(dx, dz))
            if dist > self.attack_range:
                spd = 2.5 * dt
                self.world_pos[0] += (dx/dist)*spd
                self.world_pos[2] += (dz/dist)*spd
        self.attack_cooldown = max(0.0, self.attack_cooldown - dt)

    def try_attack(self, player_stats) -> int:
        if self.dead or self.attack_cooldown > 0: return 0
        if getattr(player_stats, 'is_shielded', False):
            self.attack_cooldown = 1.8
            return 0
        self.attack_cooldown = 1.8
        dmg = max(1, self.stats.atk + random.randint(-2,2) - player_stats.defense)
        player_stats.hp = max(0, player_stats.hp - dmg)
        return dmg

# ── Player ────────────────────────────────────────────────────────────────────

class Player:
    WALK_SPEED  = 5.0
    JUMP_FORCE  = 12.0
    GRAVITY     = -18.0
    ROLL_SPEED  = 9.0
    ROLL_TIME   = 0.45

    def __init__(self, name="Natsuki Subaru"):
        self.stats = Stats(name=name, level=1, max_hp=400, hp=400,
                           max_mp=60, mp=60, atk=12, defense=4, spd=10)
        self.inventory = Inventory(gold=0)
        self.inventory.add("health_potion_s", 3)
        self.inventory.add("mana_potion", 2)
        self.inventory.add("tracksuit", 1)

        self.world_pos   = [0.0, 0.0, 0.0]
        self.velocity    = [0.0, 0.0, 0.0]
        self.facing_deg  = 0.0
        self.on_ground   = True

        # States
        self.is_rolling    = False
        self.roll_timer    = 0.0
        self.roll_dir      = [0.0, 0.0]
        self.is_attacking  = False
        self.attack_timer  = 0.0
        self.attack_cd     = 0.0
        self.combo_count   = 0
        self.combo_timer   = 0.0
        self.invincible    = 0.0  # i-frames

    @property
    def is_dead(self): return not self.stats.is_alive()

    def start_combat(self, enemy_stats): return CombatSystem(self.stats, enemy_stats)

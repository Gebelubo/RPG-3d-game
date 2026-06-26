from dataclasses import dataclass, field
from typing import Optional, List
import random
import math

from src.entities.stats import Stats
from src.entities.inventory import Inventory
from src.game.combat import CombatSystem

class Player:
    WALK_SPEED  = 5.0
    JUMP_FORCE  = 8.0
    GRAVITY     = -18.0
    ROLL_SPEED  = 9.0
    ROLL_TIME   = 0.45

    def __init__(self, name="Natsuki Subaru"):
        self.stats = Stats(name=name, level=1, max_hp=600, hp=600,
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

        # Animação de reação a dano (Reaction clip)
        self.is_taking_damage = False
        self.reaction_timer   = 0.0
        self.REACTION_TIME    = 0.5  # duração da animação de reação, em segundos

    @property
    def is_dead(self): return not self.stats.is_alive()

    def start_combat(self, enemy_stats): return CombatSystem(self.stats, enemy_stats)

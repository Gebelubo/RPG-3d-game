from dataclasses import dataclass, field
from typing import Optional, List
import random
import math

from src.entities.stats import Stats

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
import math
import random

class Boss(Enemy):

    def __init__(self, name, level=1, world_pos=None):

        super().__init__(name, level, world_pos)

        # chefe possui mais vida
        self.stats.max_hp *= 3
        self.stats.hp = self.stats.max_hp
        self.stats.atk *= 2

        self.phase = 1

        self.state = "idle"

        self.is_attacking = False

        self.current_attack = None

        self.move_speed = 3.5

        self.attack_patterns = [
            {
                "animation": "attack_1",
                "range": 2.0,
                "cooldown": 1.5,
                "damage_bonus": 5,
            },
            {
                "animation": "attack_2",
                "range": 3.0,
                "cooldown": 2.5,
                "damage_bonus": 10,
            }
        ]

    def update(self, player_pos, dt):

        if self.dead:
            return

        self.attack_cooldown = max(
            0.0,
            self.attack_cooldown - dt
        )

        dx = player_pos[0] - self.world_pos[0]
        dz = player_pos[2] - self.world_pos[2]

        dist = math.sqrt(dx * dx + dz * dz)

        self.aggro = dist < self.aggro_range

        if dist > 0.001:
            self.facing_deg = math.degrees(
                math.atan2(dx, dz)
            )

        # fase 2
        if (
            self.phase == 1 and
            self.stats.hp <= self.stats.max_hp * 0.5
        ):
            self.phase = 2
            self.move_speed = 4.5

        # se estiver atacando, espera o Game executar o ataque
        if self.is_attacking:
            return

        # movimentação
        if dist > self.attack_range:

            if self.aggro:

                self.state = "walking"

                speed = self.move_speed * dt

                self.world_pos[0] += (dx / dist) * speed
                self.world_pos[2] += (dz / dist) * speed

        else:

            self.state = "idle"

            if self.attack_cooldown <= 0:

                self.current_attack = random.choice(
                    self.attack_patterns
                )

                self.state = self.current_attack["animation"]

                self.is_attacking = True

    def try_attack(self, player_stats):

        if self.dead:
            return 0

        if not self.is_attacking:
            return 0

        if self.current_attack is None:
            return 0

        if getattr(player_stats, "is_shielded", False):

            self.is_attacking = False

            self.attack_cooldown = (
                self.current_attack["cooldown"]
            )

            return 0

        dmg = max(
            1,
            self.stats.atk
            + self.current_attack["damage_bonus"]
            + random.randint(-2, 2)
            - player_stats.defense
        )

        player_stats.hp = max(
            0,
            player_stats.hp - dmg
        )

        self.is_attacking = False

        self.attack_cooldown = (
            self.current_attack["cooldown"]
        )

        return dmg
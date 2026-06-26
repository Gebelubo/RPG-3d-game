from dataclasses import dataclass, field
from typing import Optional, List
import random
import math

from src.entities.stats import Stats

class Enemy:
    def __init__(self, name, level=1, world_pos=None, stationary: bool = False, can_windup: bool = False):
        hp = 40 + level * 30
        self.stats = Stats(name=name, level=level, max_hp=hp, hp=hp,
                           atk=6+level*2, defense=2, spd=8)
        self.world_pos = list(world_pos or [0,0,0])
        self.aggro = False
        self.aggro_range = 6.0
        self.attack_range = 1.1
        self.attack_cooldown = 0.0
        self.dead = False
        self.facing_deg = 0.0
        self.blind_time = 0.0
        self.stationary = stationary
        
        # ── Sistema de ataques ──
        self.attack_type = "light"  # "light" ou "heavy"
        self.light_attack_damage_mult = 1.0
        self.heavy_attack_damage_mult = 4
        self.light_attack_cooldown = 2
        self.heavy_attack_cooldown = 5
        self.heavy_attack_windup = 0.6
        self.light_attack_range = 1.8
        self.heavy_attack_range = 2.2
        
        # ── Sistema de wind-up ──
        self.can_windup = can_windup
        self.windup_duration = 0.6
        self.windup_timer = 0.0
        self.is_winding_up = False
        self._windup_cooldown = 2.5
        self._pending_damage = 0
        
        # ── Sistema de Parry ──
        self.parry_window_open = False
        self.parry_successful = False
        self.parry_window_timer = 0.0
        
        # ── Controle de ataque ──
        self.is_attacking = False
        self.attack_timer = 0.0
        self.current_attack_type = None

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

    def try_attack(self, player_stats, player_pos, attack_type="light") -> int:
        """
        Tenta atacar com o tipo especificado.
        player_pos: posição do player (lista [x, y, z])
        attack_type: "light" ou "heavy"
        Retorna o dano ou 0 se não atacou.
        """
        if self.dead or self.attack_cooldown > 0:
            return 0
        
        # Verifica se está em range para o tipo de ataque
        dx = player_pos[0] - self.world_pos[0]
        dz = player_pos[2] - self.world_pos[2]
        dist = math.sqrt(dx*dx + dz*dz)
        
        if attack_type == "light" and dist > self.light_attack_range:
            return 0
        if attack_type == "heavy" and dist > self.heavy_attack_range:
            return 0
        shielded = getattr(player_stats, 'is_shielded', False)
        if shielded:
            self.attack_cooldown = self.light_attack_cooldown
            self.is_attacking = False
            self.attack_timer = 0.0
            self._pending_damage = 0
            return 0
        
        # ── ATAQUE LEVE (sem wind-up, sem parry) ──
        if attack_type == "light":
            self.current_attack_type = "light"
            
            # Dano reduzido
            base_dmg = self.stats.atk
            dmg = max(1, base_dmg + random.randint(-2, 2) - player_stats.defense)
            dmg = int(dmg * self.light_attack_damage_mult)
            
            # Verifica escudo
            self.attack_cooldown = self.light_attack_cooldown
            self.is_attacking = True
            self.attack_timer = 0.3
            
            # Toca animação de ataque leve
            anim = getattr(self, '_anim', None)
            if anim is not None:
                anim.play("lightattack")
                self._anim_state = "lightattack"
            
            return dmg
        
        # ── ATAQUE PESADO (com wind-up e parry) ──
        elif attack_type == "heavy":
            self.current_attack_type = "heavy"
            
            # Inicia wind-up se não estiver em andamento
            if not self.is_winding_up:
                self.is_winding_up = True
                self.can_windup = True
                self.windup_timer = self.heavy_attack_windup
                self._windup_cooldown = self.heavy_attack_cooldown
                self.attack_cooldown = 999.0
                
                # Abre a janela de parry
                self.parry_window_open = True
                self.parry_successful = False
                self.parry_window_timer = self.heavy_attack_windup
                
                # Calcula o dano (alto)
                base_dmg = self.stats.atk * 2
                dmg = max(1, base_dmg + random.randint(-3, 3) - player_stats.defense)
                dmg = int(dmg * self.heavy_attack_damage_mult)
                self._pending_damage = dmg
                
                # Toca animação de windup
                anim = getattr(self, '_anim', None)
                if anim is not None:
                    anim.play("heavywindup")
                    self._anim_state = "heavywindup"
                
                return 0  # Ainda não causou dano
            
            return 0
    
    def execute_windup_attack(self, player_stats) -> int:
        """Executa o ataque pesado após o wind-up terminar."""
        if self.dead:
            return 0
        shielded = getattr(player_stats, 'is_shielded', False)
        if shielded:
            self.attack_cooldown = self.light_attack_cooldown
            self.is_attacking = False
            self.attack_timer = 0.0
            self._pending_damage = 0
            return 0
        
        # Fecha a janela de parry
        self.parry_window_open = False
        
        # Se o parry foi bem sucedido, NÃO aplica dano
        if self.parry_successful:
            self._pending_damage = 0
            self.parry_successful = False
            self.is_winding_up = False
            self.can_windup = False
            self.attack_cooldown = self._windup_cooldown
            self.is_attacking = True
            self.attack_timer = 0.5
            self.stats.take_damage(22.2)            
            # Toca animação de stun/parry
            anim = getattr(self, '_anim', None)
            if anim is not None:
                anim.play("stun")
                self._anim_state = "stun"
            return 0
        
        # Aplica o dano
        dmg = self._pending_damage
        self._pending_damage = 0
        
        if dmg > 0:
            player_stats.hp = max(0, player_stats.hp - dmg)
        
        # Toca animação de ataque pesado
        anim = getattr(self, '_anim', None)
        if anim is not None:
            anim.play("heavyattack")
            self._anim_state = "heavyattack"
        
        self.attack_cooldown = self._windup_cooldown
        self.is_winding_up = False
        self.can_windup = False
        self.is_attacking = True
        self.attack_timer = 0.6
        
        return dmg
    
    def attempt_parry(self) -> bool:
        """Tenta fazer parry. Retorna True se bem sucedido."""
        if not self.parry_window_open:
            return False
        
        self.parry_successful = True
        self.parry_window_open = False
        self.attack_cooldown = max(self.attack_cooldown, 0.5)
        
        return True
    
    def finish_attack_animation(self):
        """Finaliza a animação de ataque."""
        self.is_attacking = False
        self.attack_timer = 0.0
        self.current_attack_type = None
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
        
        # Stationary enemies do not move towards the player
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


    
import math
import random

class Boss(Enemy):
    """Boss genérico. Herdado por MarluxiaBoss."""

class MarluxiaBoss(Enemy):
    """
    Boss final — Marluxia.

    Estados de animação (espelhados em self.state):
        idle, walking, hit, death,
        normalattack, heavyattack, roundattack,
        taunt, groundmagic, shoot, curse, invincible

    Fases:
        1  – HP normal
        2  – HP <= 50% → velocidade +25%
        3  – HP <= 20% → lança curse (uma vez)
        4  – HP <= 10% → fica invencível 10 s, invoca buracos negros
    """

    # ── Limites de fase ─────────────────────────────────────────────────────
    PHASE2_THRESH     = 0.50
    PHASE_ATK_THRESH  = 0.60   # 60% HP → cooldown de ataque reduzido à metade
    PHASE3_THRESH     = 0.20
    PHASE4_THRESH     = 0.10

    # ── Limites da sala (ROOM_W=20, ROOM_D=30, centro em 0,0) ───────────────
    ROOM_X_LIMIT = 8.5   # metade da largura menos margem
    ROOM_Z_MIN   = -13.0 # parede norte
    ROOM_Z_MAX   =  13.0 # parede sul

    # ── Timings ─────────────────────────────────────────────────────────────
    INVINCIBLE_DURATION = 15.0   # segundos de invencibilidade na fase 4
    TAUNT_IDLE_TIME     = 6.0    # segundos longe do player antes de provocar
    TAUNT_COOLDOWN      = 20.0   # mínimo entre provocações
    TAUNT_HEAL          = 20     # HP recuperado na provocação
    BLACKHOLE_INTERVAL  = 1.2    # segundos entre invocar buraco negro
    SHOOT_RANGE         = 7.0    # distância mínima para atirar à distância
    ROUND_RANGE         = 2.5    # raio do ataque giratório
    CURSE_DURATION      = 30.0   # segundos com controles invertidos no player

    def __init__(self, name="Marluxia", level=8, world_pos=None):
        super().__init__(name, level, world_pos)

        # Stats base sobrescritos em game_main._build_floor_boss
        self.stats.max_hp *= 3
        self.stats.hp      = self.stats.max_hp
        self.stats.atk    *= 4

        # Fases
        self.phase            = 1
        self.curse_done       = False
        self.invincible_timer = 0.0   # > 0 enquanto fase 4 ativa
        self.invincible_active = False

        # Estado de animação / lógica
        self.state            = "idle"
        self.is_attacking     = False   # bloqueia o update enquanto o ataque está ativo
        self.current_attack   = None    # dict do padrão atual
        self.move_speed       = 3.5
        self.curse_active     = False   # True após fase 3: IA muda permanentemente
        self.atk_boost_active = False   # True abaixo de 60% HP

        # Taunt
        self.far_timer        = 0.0    # acumulado longe do player
        self.taunt_cooldown   = 0.0

        # Buracos negros (fase 4 / groundmagic)
        self.blackhole_timer  = 0.0
        # Lista de dicts: {"pos": [x,z], "timer": float}  — consumida por game_main
        self.blackholes: list = []

        self.can_windup = True  # Boss sempre pode ter wind-up
        self.windup_duration = 0.6  # Duração do wind-up
        self.windup_timer = 0.0
        self.is_winding_up = False
        self._windup_cooldown = 2.0
        self._pending_damage = 0
        
        # ── Sistema de Parry ──
        self.parry_window_open = False
        self.parry_successful = False
        self.parry_window_timer = 0.0
        
        # ── Controle de ataque ──
        self.attack_timer = 0.0
        self.current_attack_type = None

        # Padrões de ataque
        self.attack_patterns = {
            "normalattack": {
                "animation": "normalattack",
                "range":      2.2,
                "cooldown":   1.5,
                "damage_bonus": 5,
                "weight":     50,
            },
            "heavyattack": {
                "animation": "heavyattack",
                "range":      2.2,
                "cooldown":   3.0,
                "damage_bonus": 35,
                "weight":     20,
            },
            "roundattack": {
                "animation": "roundattack",
                "range":      self.ROUND_RANGE,
                "cooldown":   4.0,
                "damage_bonus": 18,
                "weight":     15,
                "aoe":        True,
            },
            "shoot": {
                "animation": "shoot",
                "range":      self.SHOOT_RANGE,
                "cooldown":   2.5,
                "damage_bonus": 10,
                "weight":     15,
            },
        }

    # ── Helpers internos ────────────────────────────────────────────────────

    def _pick_attack(self, dist: float) -> dict:
        """Escolhe um padrão de ataque levando em conta a distância."""
        candidates = []
        weights    = []
        for key, pat in self.attack_patterns.items():
            if dist <= pat["range"]:
                candidates.append(pat)
                weights.append(pat["weight"])
            elif key == "shoot" and dist > self.SHOOT_RANGE * 0.5:
                candidates.append(pat)
                weights.append(pat["weight"])
        if not candidates:
            candidates = [self.attack_patterns["normalattack"]]
            weights    = [1]
        return random.choices(candidates, weights=weights, k=1)[0]

    def _spawn_blackhole(self):
        """Adiciona um buraco negro espalhado pela sala."""
        import random as _r
        # Posição aleatória na sala (não centrada no boss)
        bx = _r.uniform(-7.5, 7.5)
        bz = _r.uniform(-11.0, 11.0)
        bh = {
            "pos":    [bx, bz],
            "timer":  5.0,
            "damage": max(1, self.stats.atk // 3),
            "radius": 2.0,   # range maior
        }
        self.blackholes.append(bh)

    # ── Update principal ─────────────────────────────────────────────────────

    def update(self, player_pos, dt):
        if self.dead:
            return

        # Timers globais
        self.attack_cooldown = max(0.0, self.attack_cooldown - dt)
        self.taunt_cooldown  = max(0.0, self.taunt_cooldown  - dt)

        # Distância ao player
        dx   = player_pos[0] - self.world_pos[0]
        dz   = player_pos[2] - self.world_pos[2]
        dist = math.sqrt(dx * dx + dz * dz)

        self.aggro = dist < self.aggro_range

        if dist > 0.001:
            self.facing_deg = math.degrees(math.atan2(dx, dz))

        # ── Checar transições de fase ────────────────────────────────────────
        hp_pct = self.stats.hp / self.stats.max_hp

        # 60% HP: cooldown de ataque reduzido à metade (uma só vez)
        if not self.atk_boost_active and hp_pct <= self.PHASE_ATK_THRESH:
            self.atk_boost_active = True
            for pat in self.attack_patterns.values():
                pat["cooldown"] = pat["cooldown"] * 0.5

        if self.phase == 1 and hp_pct <= self.PHASE2_THRESH:
            self.phase      = 2
            self.move_speed = 4.5          # 25% mais rápido

        if self.phase == 2 and hp_pct <= self.PHASE3_THRESH and not self.curse_done:
            self.phase        = 3
            self.curse_active = True          # IA muda permanentemente
            self.move_speed   = self.move_speed * 2   # dobra velocidade
            self.state        = "curse"
            self.is_attacking = True          # congela até game_main liberar
            self.curse_done   = True
            return

        if (self.phase == 3 and hp_pct <= self.PHASE4_THRESH
                and not self.invincible_active
                and self.stats.hp > 1):
            self.phase             = 4
            self.invincible_active = True
            self.invincible_timer  = self.INVINCIBLE_DURATION  # 15s
            self.blackhole_timer   = 0.0   # invoca primeiro buraco imediatamente
            self.dead              = False
            self.state             = "invincible"
            self.is_attacking      = False  # não bloqueia update de buracos
            return

        # ── Fase 4 invencível ────────────────────────────────────────────────
        if self.invincible_active:
            self.invincible_timer -= dt
            self.blackhole_timer  -= dt
            if self.blackhole_timer <= 0.0:
                self._spawn_blackhole()
                self.blackhole_timer = self.BLACKHOLE_INTERVAL
            if self.invincible_timer <= 0.0:
                self.invincible_active = False
                self.is_attacking      = False
                self.state             = "idle"
            return

        # ── Aguarda game_main terminar o ataque atual ────────────────────────
        if self.is_attacking:
            return

        # ── Longe do player: taunt? ──────────────────────────────────────────
        if dist > self.aggro_range * 0.8:
            self.far_timer += dt
        else:
            self.far_timer = 0.0

        if (self.far_timer >= self.TAUNT_IDLE_TIME
                and self.taunt_cooldown <= 0.0
                and not self.is_attacking):
            self.state         = "taunt"
            self.is_attacking  = True
            self.current_attack = {
                "animation":    "taunt",
                "range":        999.0,
                "cooldown":     self.TAUNT_COOLDOWN,
                "damage_bonus": 0,
                "taunt":        True,
            }
            self.far_timer     = 0.0
            self.taunt_cooldown = self.TAUNT_COOLDOWN
            return

        # ── Movimento / ataque normal ────────────────────────────────────────
        if self.curse_active:
            # Fase curse: mantém distância e usa só shoot/groundmagic
            PREFERRED_DIST = self.SHOOT_RANGE * 0.7
            self.state = "idle"
            if dist < PREFERRED_DIST:
                # Recua do player
                speed = self.move_speed * dt
                self.world_pos[0] -= (dx / dist) * speed
                self.world_pos[2] -= (dz / dist) * speed
            elif dist > PREFERRED_DIST * 1.4:
                # Aproxima um pouco para manter no range de shoot
                speed = self.move_speed * 0.5 * dt
                self.world_pos[0] += (dx / dist) * speed
                self.world_pos[2] += (dz / dist) * speed
            # Clamp dentro da sala
            self.world_pos[0] = max(-self.ROOM_X_LIMIT, min(self.ROOM_X_LIMIT, self.world_pos[0]))
            self.world_pos[2] = max(self.ROOM_Z_MIN,    min(self.ROOM_Z_MAX,   self.world_pos[2]))
            if self.attack_cooldown <= 0.0:
                # 60% groundmagic, 40% shoot
                if random.random() < 0.6:
                    pat = {
                        "animation":    "groundmagic",
                        "range":        999.0,
                        "cooldown":     4.0,
                        "damage_bonus": 0,
                        "groundmagic":  True,
                    }
                else:
                    pat = self.attack_patterns["shoot"]
                self.current_attack = pat
                self.state          = pat["animation"]
                self.is_attacking   = True
        elif dist > self.attack_range:
            if self.aggro:
                self.state = "idle"   # walking == idle no Marluxia (mesmo clipe)
                speed = self.move_speed * dt
                self.world_pos[0] += (dx / dist) * speed
                self.world_pos[2] += (dz / dist) * speed
                # Clamp dentro da sala
                self.world_pos[0] = max(-self.ROOM_X_LIMIT, min(self.ROOM_X_LIMIT, self.world_pos[0]))
                self.world_pos[2] = max(self.ROOM_Z_MIN,    min(self.ROOM_Z_MAX,   self.world_pos[2]))
        else:
            self.state = "idle"
            if self.attack_cooldown <= 0.0:
                pat = self._pick_attack(dist)
                # Ataque de solo (groundmagic) — chance extra na fase 2+
                if self.phase >= 2 and random.random() < 0.15:
                    pat = {
                        "animation":    "groundmagic",
                        "range":        999.0,
                        "cooldown":     5.0,
                        "damage_bonus": 0,
                        "groundmagic":  True,
                    }
                self.current_attack = pat
                self.state          = pat["animation"]
                self.is_attacking   = True

    # ── Try attack (chamado por game_main quando o boss está em is_attacking) ─

    def try_attack(self, player_stats) -> int:
        """Retorna dano causado (0 = nenhum)."""
        if self.dead:
            return 0
        if not self.is_attacking:
            return 0
        if self.current_attack is None:
            return 0
        shielded = getattr(player_stats, 'is_shielded', False)
        if shielded:
            self.attack_cooldown = self.light_attack_cooldown
            return 0

        pat = self.current_attack

        # Taunt — cura, sem dano
        if pat.get("taunt"):
            self.stats.hp = min(self.stats.max_hp,
                                self.stats.hp + self.TAUNT_HEAL)
            # Finaliza o taunt sem sobrescrever o attack_cooldown normal:
            # apenas reseta o estado de ataque; o taunt_cooldown já foi
            # setado em update() antes de entrar aqui.
            self.is_attacking   = False
            self.current_attack = None
            self.state          = "idle"
            # Garante que o boss pode atacar imediatamente após o taunt
            # (não penaliza o attack_cooldown com os 20s do taunt).
            # O attack_cooldown já em curso (de ataque anterior) é mantido.
            return 0

        # groundmagic — sem dano direto; buracos negros são tratados por game_main
        if pat.get("groundmagic"):
            for _ in range(4):
                self._spawn_blackhole()
            self._finish_attack()
            return 0

        # Escudo do player
        if getattr(player_stats, "is_shielded", False):
            self._finish_attack()
            return 0

        bonus = pat.get("damage_bonus", 0)
        dmg   = max(1, self.stats.atk + bonus
                        + random.randint(-2, 2)
                        - player_stats.defense)
        player_stats.hp = max(0, player_stats.hp - dmg)
        self._finish_attack()
        return dmg

    def _finish_attack(self):
        cooldown            = (self.current_attack or {}).get("cooldown", 1.5)
        self.is_attacking   = False
        self.attack_cooldown = cooldown
        self.current_attack = None
        self.state          = "idle"

    # ── Receber hit ──────────────────────────────────────────────────────────

    def receive_hit(self, dmg: int) -> int:
        """Aplica dano. Retorna o dano real (0 se invencível)."""
        if self.invincible_active:
            return 0

        # Fase 5 (enrage ativo): completamente imune
        if self.phase >= 5:
            return 0

        # already_enraged: True depois que o boss já passou pelo enrage de 1 HP
        # uma vez (flag setada pelo game_main). Enquanto isso não acontecer,
        # travamos o HP em 1 pra impedir kill instantâneo (o game_main ativa
        # o enrage no próximo frame). Depois do enrage já ter ocorrido, o boss
        # pode (e deve) morrer normalmente — senão ele fica travado em 1 HP
        # pra sempre, tomando 0 de dano em todo hit.
        already_enraged = getattr(self, '_enrage_triggered', False)
        if self.stats.hp <= 1 and not already_enraged:
            return 0

        min_hp = 0 if already_enraged else 1
        new_hp = max(min_hp, self.stats.hp - dmg)
        actual = self.stats.hp - new_hp
        self.stats.hp = new_hp

        if not self.is_attacking:
            self.state = "hit"
        # Boss só morre de verdade quando game_main liberar após o enrage
        return actual

# Alias para retrocompatibilidade com game_main (usa Boss("Marluxia"))
Boss = MarluxiaBoss

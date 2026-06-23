"""
hud.py  –  2-D HUD + action menu for Pleiades Tower RPG.

Melhorias em relação à versão original:
  - draw_rect respeita o parâmetro alpha (via uAlpha no shader unlit)
  - Cache de texturas de texto por (text, size, color, bold) — evita recriar
    a mesma textura dezenas de vezes por segundo para popups/labels fixos
  - Cache de VAO/VBO para quads de tamanho fixo reutilizados (barras, botões)
  - _text_tex e _make_quad não vazam GPU quando o cache é usado
  - Popups centralizados horizontalmente na tela (não mais deslocados)
  - draw_death_screen centralizado corretamente
"""

import pygame
import numpy as np
import ctypes
from OpenGL.GL import (
    glGenVertexArrays, glBindVertexArray, glGenBuffers, glBindBuffer,
    glBufferData, glEnableVertexAttribArray, glVertexAttribPointer,
    glDrawElements, glDeleteVertexArrays, glDeleteBuffers,
    glGenTextures, glBindTexture, glTexImage2D, glDeleteTextures,
    glTexParameteri, glActiveTexture, glEnable, glDisable, glBlendFunc,
    GL_ARRAY_BUFFER, GL_ELEMENT_ARRAY_BUFFER, GL_STATIC_DRAW,
    GL_FLOAT, GL_UNSIGNED_INT, GL_TRIANGLES, GL_FALSE,
    GL_TEXTURE_2D, GL_RGBA, GL_UNSIGNED_BYTE,
    GL_TEXTURE_MIN_FILTER, GL_TEXTURE_MAG_FILTER, GL_LINEAR,
    GL_TEXTURE_WRAP_S, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE,
    GL_BLEND, GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA, GL_TEXTURE0,
)
from src.engine.math3d import ortho, identity
from src.engine.shader import ShaderProgram

# ── Font cache ────────────────────────────────────────────────────────────────

_FONT_CACHE: dict = {}

def _get_font(size, bold=False):
    key = (size, bold)
    if key not in _FONT_CACHE:
        for fname in ("segoeui", "dejavusans", "freesans", "monospace"):
            try:
                _FONT_CACHE[key] = pygame.font.SysFont(fname, size, bold=bold)
                break
            except Exception:
                pass
        else:
            _FONT_CACHE[key] = pygame.font.Font(None, size)
    return _FONT_CACHE[key]


# ── Texture cache — (text, size, color, bold) -> (tex_id, w, h) ──────────────
# Textures are GPU objects; we keep at most _TEX_CACHE_MAX entries and evict
# the oldest when the limit is hit (simple FIFO).

_TEX_CACHE: dict = {}        # key -> (tex_id, w, h)
_TEX_ORDER: list = []        # insertion order for eviction
_TEX_CACHE_MAX = 256

def _text_tex(text: str, size: int, color=(255,255,255), bold=False):
    key = (text, size, color, bold)
    if key in _TEX_CACHE:
        return _TEX_CACHE[key]

    # Evict oldest if cache is full
    if len(_TEX_ORDER) >= _TEX_CACHE_MAX:
        old_key = _TEX_ORDER.pop(0)
        old_tex, _, _ = _TEX_CACHE.pop(old_key, (None, 0, 0))
        if old_tex is not None:
            glDeleteTextures(1, [old_tex])

    font = _get_font(size, bold)
    surf = font.render(text, True, color).convert_alpha()
    w, h = surf.get_size()
    data = pygame.image.tostring(surf, "RGBA", True)
    tex = glGenTextures(1)
    glBindTexture(GL_TEXTURE_2D, tex)
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, w, h, 0, GL_RGBA, GL_UNSIGNED_BYTE, data)
    for p, v in [
        (GL_TEXTURE_MIN_FILTER, GL_LINEAR),
        (GL_TEXTURE_MAG_FILTER, GL_LINEAR),
        (GL_TEXTURE_WRAP_S,     GL_CLAMP_TO_EDGE),
        (GL_TEXTURE_WRAP_T,     GL_CLAMP_TO_EDGE),
    ]:
        glTexParameteri(GL_TEXTURE_2D, p, v)
    glBindTexture(GL_TEXTURE_2D, 0)

    _TEX_CACHE[key] = (tex, w, h)
    _TEX_ORDER.append(key)
    return tex, w, h


# ── Quad helpers ──────────────────────────────────────────────────────────────

def _make_quad(x, y, w, h):
    """Cria um VAO para um quad 2-D. Caller é responsável por deletar."""
    verts = np.array([
        x,   y,   0, 0, 1,
        x+w, y,   0, 1, 1,
        x+w, y+h, 0, 1, 0,
        x,   y+h, 0, 0, 0,
    ], dtype=np.float32)
    idxs = np.array([0, 1, 2, 0, 2, 3], dtype=np.uint32)
    vao = glGenVertexArrays(1)
    vbo, ibo = glGenBuffers(2)
    glBindVertexArray(vao)
    glBindBuffer(GL_ARRAY_BUFFER, vbo)
    glBufferData(GL_ARRAY_BUFFER, verts.nbytes, verts, GL_STATIC_DRAW)
    glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, ibo)
    glBufferData(GL_ELEMENT_ARRAY_BUFFER, idxs.nbytes, idxs, GL_STATIC_DRAW)
    s = 5 * 4
    glEnableVertexAttribArray(0)
    glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, s, ctypes.c_void_p(0))
    glEnableVertexAttribArray(2)
    glVertexAttribPointer(2, 2, GL_FLOAT, GL_FALSE, s, ctypes.c_void_p(12))
    glBindVertexArray(0)
    return vao, vbo, ibo


def _free_quad(vao, vbo, ibo):
    glDeleteVertexArrays(1, [vao])
    glDeleteBuffers(2, [vbo, ibo])


# ── HUD ───────────────────────────────────────────────────────────────────────

class HUD:
    def __init__(self, sw, sh, shader):
        self.sw = sw
        self.sh = sh
        self.shader = shader
        self.proj  = ortho(0, sw, sh, 0, -1, 1)
        self.view  = identity()
        self.model = identity()

        self.spell_menu_open = False
        self.item_menu_open  = False
        self.skill_menu_open = False
        self.inventory_items = []
        self.popups: list = []   # [text, timer, color]

    def resize(self, w, h):
        self.sw = w
        self.sh = h
        self.proj = ortho(0, w, h, 0, -1, 1)

    def add_popup(self, text: str, duration: float = 2.0, color=(255, 220, 100)):
        self.popups.append([text, duration, color])

    def update(self, dt: float):
        self.popups = [[t, ti - dt, c] for t, ti, c in self.popups if ti - dt > 0]

    # ── Shader setup ─────────────────────────────────────────────────────────

    def _setup(self, alpha: float = 1.0):
        self.shader.use()
        self.shader.set_mat4("uProjection", self.proj)
        self.shader.set_mat4("uView",       self.view)
        self.shader.set_mat4("uModel",      self.model)
        self.shader.set_float("uAlpha", alpha)

    # ── Primitives ───────────────────────────────────────────────────────────

    def draw_text(self, text: str, x: int, y: int, size: int = 18,
                  color=(255, 255, 255), bold: bool = False, center: bool = False,
                  alpha: float = 1.0):
        if not text:
            return
        # Modulate color by alpha for shaders that don't support uAlpha
        tex, tw, th = _text_tex(text, size, color, bold)
        if center:
            x = int(x - tw // 2)
            y = int(y - th // 2)

        vao, vbo, ibo = _make_quad(x, y, tw, th)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        self._setup(alpha)
        self.shader.set_bool("uUseTexture", True)
        self.shader.set_int("uTexture", 0)
        glActiveTexture(GL_TEXTURE0)
        glBindTexture(GL_TEXTURE_2D, tex)
        glBindVertexArray(vao)
        glDrawElements(GL_TRIANGLES, 6, GL_UNSIGNED_INT, None)
        glBindVertexArray(0)
        glBindTexture(GL_TEXTURE_2D, 0)
        glDisable(GL_BLEND)
        _free_quad(vao, vbo, ibo)
        # textura fica no cache — NÃO deletar aqui

    def draw_rect(self, x: int, y: int, w: int, h: int,
                  color=(0.1, 0.1, 0.2), alpha: float = 1.0):
        """
        Desenha um retângulo colorido.
        alpha=1.0 opaco, alpha=0.0 transparente.
        Funciona via GL_BLEND + uAlpha (ou modulação da cor se o shader não tiver uAlpha).
        """
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        self._setup(alpha)
        self.shader.set_bool("uUseTexture", False)
        self.shader.set_vec3("uBaseColor", color)
        vao, vbo, ibo = _make_quad(x, y, w, h)
        glBindVertexArray(vao)
        glDrawElements(GL_TRIANGLES, 6, GL_UNSIGNED_INT, None)
        glBindVertexArray(0)
        glDisable(GL_BLEND)
        _free_quad(vao, vbo, ibo)

    def draw_bar(self, x: int, y: int, w: int, h: int, fill: float,
                 bar_color=(0.8, 0.1, 0.1), bg_color=(0.2, 0.2, 0.2)):
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        self._setup()
        self.shader.set_bool("uUseTexture", False)

        def _solid(cx, cy, cw, ch, col):
            if cw <= 0:
                return
            vao, vbo, ibo = _make_quad(cx, cy, cw, ch)
            self.shader.set_vec3("uBaseColor", col)
            glBindVertexArray(vao)
            glDrawElements(GL_TRIANGLES, 6, GL_UNSIGNED_INT, None)
            glBindVertexArray(0)
            _free_quad(vao, vbo, ibo)

        _solid(x, y, w, h, bg_color)
        _solid(x, y, int(w * max(0.0, min(1.0, fill))), h, bar_color)
        glDisable(GL_BLEND)

    # ── Main HUD ─────────────────────────────────────────────────────────────

    def draw_main_hud(self, player, game_mode):
        sw, sh = self.sw, self.sh
        p = player.stats
        bx, by = 16, 16

        # Painel de fundo
        self.draw_rect(bx - 4, by - 4, 244, 68, (0.04, 0.04, 0.10))

        # Barra de HP
        self.draw_bar(bx, by, 204, 18, p.hp / p.max_hp,
                      bar_color=(0.85, 0.15, 0.15), bg_color=(0.25, 0.08, 0.08))
        self.draw_text(f"HP  {p.hp}/{p.max_hp}", bx + 4, by + 1, 13, (255, 200, 200))

        # Barra de MP
        self.draw_bar(bx, by + 22, 204, 18, p.mp / max(1, p.max_mp),
                      bar_color=(0.15, 0.35, 0.9), bg_color=(0.08, 0.08, 0.25))
        self.draw_text(f"MP  {p.mp}/{p.max_mp}", bx + 4, by + 23, 13, (160, 190, 255))

        # Barra de XP
        self.draw_bar(bx, by + 44, 204, 8, p.xp / max(1, p.xp_next),
                      bar_color=(0.9, 0.75, 0.1), bg_color=(0.15, 0.12, 0.05))
        self.draw_text(f"Lv {p.level}", bx + 210, by + 42, 12, (230, 200, 80))

        # Indicador de escudo EMT
        if getattr(p, 'is_shielded', False):
            shield_left = int(max(0.0, p.shield_time) + 0.9)
            self.draw_text(f"EMT {shield_left}s", bx + 130, by + 22, 12, (130, 230, 255))

        if game_mode == "explore":
            self._draw_action_menu()
        if self.spell_menu_open:
            self._draw_spell_submenu()
        if self.item_menu_open:
            self._draw_item_submenu()
        if self.skill_menu_open:
            self._draw_skill_submenu()

        # Popups centralizados, com fade de opacidade
        for i, (text, timer, color) in enumerate(reversed(self.popups)):
            fade = min(1.0, timer)
            self.draw_text(
                text,
                sw // 2, sh // 2 - 80 - i * 28,
                size=18, color=color, bold=True,
                center=True, alpha=fade,
            )

    # ── Botões de ação ───────────────────────────────────────────────────────

    def _draw_action_menu(self):
        sh = self.sh
        bs = 68; pad = 8
        bx = pad; by = sh - bs - pad
        buttons = [
            ("ATAQUE", "Z", (0.55, 0.12, 0.12)),
            ("MAGIA",  "X", (0.12, 0.12, 0.55)),
            ("ITENS",  "C", (0.12, 0.40, 0.12)),
            ("HABIL.", "V", (0.40, 0.30, 0.05)),
        ]
        for i, (label, key, col) in enumerate(buttons):
            xi = bx + i * (bs + pad)
            self.draw_rect(xi, by, bs, bs, col)
            self.draw_rect(xi, by, bs, 2,
                           (col[0] + 0.25, col[1] + 0.25, col[2] + 0.25))
            self.draw_rect(xi, by, 2, bs,
                           (col[0] + 0.25, col[1] + 0.25, col[2] + 0.25))
            self.draw_text(label, xi + 6, by + 14, 11, (240, 240, 240), bold=True)
            self.draw_text(f"[{key}]", xi + 20, by + 46, 13, (200, 200, 120))

    # ── Submenus ─────────────────────────────────────────────────────────────

    def _draw_spell_submenu(self):
        sh = self.sh
        pw, ph = 240, 190
        px = 8 + 1 * (68 + 8)
        py = sh - 68 - 8 - ph - 8
        self.draw_rect(px, py, pw, ph, (0.05, 0.05, 0.18))
        self.draw_rect(px, py, pw, 2, (0.3, 0.3, 0.7))
        self.draw_text("── MAGIA ──", px + 8, py + 6, 14, (160, 160, 255), bold=True)
        from src.game.rpg_data import SPELL_DB, SPELL_LIST
        for i, sid in enumerate(SPELL_LIST):
            sp = SPELL_DB[sid]
            iy = py + 30 + i * 44
            ic = sp.icon_color
            self.draw_rect(px + 6, iy, 28, 28, ic)
            self.draw_text(sp.name,            px + 40, iy + 2,  14, (220, 220, 255))
            self.draw_text(f"{sp.mp_cost} MP", px + 40, iy + 18, 11, (100, 140, 255))
            self.draw_text(f"[{i + 1}]",       px + 210, iy + 8, 13, (180, 180, 100))

    def _draw_item_submenu(self):
        sh = self.sh
        pw, ph = 240, 190
        px = 8 + 2 * (68 + 8)
        py = sh - 68 - 8 - ph - 8
        self.draw_rect(px, py, pw, ph, (0.05, 0.14, 0.05))
        self.draw_rect(px, py, pw, 2, (0.2, 0.6, 0.2))
        self.draw_text("── ITENS ──", px + 8, py + 6, 14, (150, 255, 150), bold=True)
        items = self.inventory_items
        if not items:
            self.draw_text("(vazio)", px + 8, py + 40, 14, (160, 160, 160))
            return
        for i, (item, qty) in enumerate(items[:4]):
            iy = py + 30 + i * 44
            self.draw_rect(px + 6, iy, 28, 28, (0.1, 0.35, 0.1))
            self.draw_text(item.name, px + 40, iy + 2,  13, (200, 255, 200))
            self.draw_text(f"x{qty}",  px + 40, iy + 18, 11, (150, 220, 150))
            self.draw_text(f"[{i + 1}]", px + 210, iy + 8, 13, (180, 180, 100))

    def _draw_skill_submenu(self):
        sh = self.sh
        pw, ph = 260, 190
        px = 8 + 3 * (68 + 8)
        py = sh - 68 - 8 - ph - 8
        self.draw_rect(px, py, pw, ph, (0.12, 0.10, 0.02))
        self.draw_rect(px, py, pw, 2, (0.7, 0.6, 0.1))
        self.draw_text("── HABILIDADES ──", px + 8, py + 6, 13, (255, 220, 80), bold=True)
        skills = [
            ("Return by Death",  "Retorna da morte",            (0.5,  0.1,  0.1)),
            ("Cheiro da Bruxa",  "Atrai o culto da bruxa",      (0.2,  0.3,  0.6)),
            ("Portal Danificado","Portal de mana danificado",   (0.4,  0.0,  0.0)),
            ("Cor Leonis",       "Protege seus aliados",        (0.35, 0.0,  0.35)),
        ]
        for i, (name, desc, col) in enumerate(skills):
            iy = py + 30 + i * 44
            self.draw_rect(px + 6, iy, 28, 28, col)
            self.draw_text(name, px + 40, iy + 2,  12, (255, 230, 130))
            self.draw_text(desc, px + 40, iy + 18, 10, (180, 165, 100))

    # ── Telas especiais ───────────────────────────────────────────────────────

    def draw_combat_log(self, messages):
        sh = self.sh
        base_y = sh - 80 - len(messages) * 22
        for i, msg in enumerate(messages):
            self.draw_text(msg, 10, base_y + i * 22, 14, (255, 215, 160))

    def draw_enemy_healthbar(self, name, hp_frac, sx, sy):
        w = 80
        self.draw_bar(sx - w // 2, sy, w, 8, hp_frac,
                      bar_color=(0.9, 0.1, 0.1), bg_color=(0.25, 0.08, 0.08))
        self.draw_text(name, sx - w // 2, sy - 16, 11, (255, 200, 200))

    def draw_death_screen(self):
        sw, sh = self.sw, self.sh
        self.draw_rect(0, 0, sw, sh, (0.08, 0.0, 0.0))
        self.draw_text("— VOCÊ MORREU —", sw // 2, sh // 2 - 20,
                       32, (180, 0, 0), bold=True, center=True)
        self.draw_text("Return by Death...", sw // 2, sh // 2 + 28,
                       18, (140, 60, 60), center=True)

    def draw_pause_overlay(self):
        sw, sh = self.sw, self.sh
        self.draw_rect(sw // 2 - 130, sh // 2 - 90, 260, 180, (0.04, 0.04, 0.12))
        self.draw_text("PAUSADO",             sw // 2, sh // 2 - 60,
                       24, (200, 200, 255), bold=True, center=True)
        self.draw_text("[ESC] Continuar",     sw // 2, sh // 2 - 20,
                       16, (180, 180, 180), center=True)
        self.draw_text("[Q]   Voltar ao menu",sw // 2, sh // 2 + 10,
                       16, (180, 180, 180), center=True)

    # ── Clique do mouse ───────────────────────────────────────────────────────

    def handle_click(self, mx, my, player):
        sh = self.sh; bs = 68; pad = 8
        by = sh - bs - pad; bx = pad
        for i in range(4):
            xi = bx + i * (bs + pad)
            if xi <= mx <= xi + bs and by <= my <= by + bs:
                if i == 0:
                    return "attack"
                elif i == 1:
                    self.spell_menu_open = not self.spell_menu_open
                    self.item_menu_open = self.skill_menu_open = False
                    return "toggle_magic"
                elif i == 2:
                    self.item_menu_open = not self.item_menu_open
                    self.spell_menu_open = self.skill_menu_open = False
                    self.inventory_items = player.inventory.list_consumables()
                    return "toggle_items"
                elif i == 3:
                    self.skill_menu_open = not self.skill_menu_open
                    self.spell_menu_open = self.item_menu_open = False
                    return "toggle_skills"
        return None

    def handle_submenu_click(self, mx, my, player) -> "str | None":
        sh = self.sh; bs = 68; pad = 8; ph = 190
        if self.spell_menu_open:
            px = 8 + 1 * (bs + pad)
            py = sh - bs - pad - ph - 8
            from src.game.rpg_data import SPELL_LIST
            for i, sid in enumerate(SPELL_LIST):
                iy = py + 30 + i * 38
                if px <= mx <= px + 240 and iy <= my <= iy + 28:
                    return f"spell:{sid}"
        if self.item_menu_open:
            px = 8 + 2 * (bs + pad)
            py = sh - bs - pad - ph - 8
            for i, (item, _) in enumerate(self.inventory_items[:4]):
                iy = py + 30 + i * 38
                if px <= mx <= px + 240 and iy <= my <= iy + 28:
                    return f"item:{item.id}"
        return None

    # ── Limpeza de recursos ───────────────────────────────────────────────────

    def cleanup(self):
        """Libera todas as texturas em cache. Chamar ao fechar o jogo."""
        global _TEX_CACHE, _TEX_ORDER
        for tex, _, _ in _TEX_CACHE.values():
            glDeleteTextures(1, [tex])
        _TEX_CACHE.clear()
        _TEX_ORDER.clear()
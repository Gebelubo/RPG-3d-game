import math

from OpenGL.GL import (
    glBindVertexArray,
    glDrawElements, glBindTexture,
    glActiveTexture, glEnable, glDisable, glBlendFunc,
    GL_UNSIGNED_INT, GL_TRIANGLES,
    GL_TEXTURE_2D,
    GL_BLEND, GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA, GL_TEXTURE0, glUseProgram, glDrawArrays,
    glTexParameteri, glGenerateMipmap,
    GL_TEXTURE_MIN_FILTER, GL_TEXTURE_MAG_FILTER,
    GL_LINEAR, GL_LINEAR_MIPMAP_LINEAR,
)
from src.engine.math3d import ortho, identity

from src.db.spell import SPELL_DB, SPELL_LIST

from src.hud.utils import (
    _make_quad, _text_tex, _free_quad,
    _make_poly, _ngon_points, _banner_points,
    clear_text_cache,
)



def _c(rgb):
    return (rgb[0] / 255.0, rgb[1] / 255.0, rgb[2] / 255.0)


def _lighten(color, amt=0.15):
    return tuple(min(1.0, v + amt) for v in color)


def _darken(color, amt=0.15):
    return tuple(max(0.0, v - amt) for v in color)


PARCHMENT_DK = (42, 30, 20)
IRON_DARK    = (20, 20, 26)
GOLD         = (220, 178, 76)
GOLD_DARK    = (118, 88, 34)
BRONZE       = (150, 105, 55)
CRIMSON      = (170, 28, 32)
CRIMSON_DK   = (70, 10, 14)
SAPPHIRE     = (44, 98, 198)
SAPPHIRE_DK  = (14, 30, 68)
EMERALD      = (36, 150, 84)
EMERALD_DK   = (10, 56, 32)
AMETHYST     = (138, 64, 176)
AMETHYST_DK  = (52, 20, 68)

PARCHMENT_DK_F = _c(PARCHMENT_DK)
IRON_DARK_F    = _c(IRON_DARK)
GOLD_F         = _c(GOLD)
GOLD_DARK_F    = _c(GOLD_DARK)
BRONZE_F       = _c(BRONZE)
CRIMSON_F      = _c(CRIMSON)
CRIMSON_DK_F   = _c(CRIMSON_DK)
SAPPHIRE_F     = _c(SAPPHIRE)
SAPPHIRE_DK_F  = _c(SAPPHIRE_DK)
EMERALD_F      = _c(EMERALD)
EMERALD_DK_F   = _c(EMERALD_DK)
AMETHYST_F     = _c(AMETHYST)
AMETHYST_DK_F  = _c(AMETHYST_DK)


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
        self.popups: list = []   

    def resize(self, w, h):
        self.sw = w
        self.sh = h
        self.proj = ortho(0, w, h, 0, -1, 1)

    def add_popup(self, text: str, duration: float = 2.0, color=(255, 220, 100), y_offset: int = 0):
        self.popups.append([text, duration, color, y_offset])

    def update(self, dt: float):
        self.popups = [[t, ti - dt, c, yo] for t, ti, c, yo in self.popups if ti - dt > 0]


    def _setup(self, alpha: float = 1.0):
        self.shader.use()
        self.shader.set_mat4("uProjection", self.proj)
        self.shader.set_mat4("uView",       self.view)
        self.shader.set_mat4("uModel",      self.model)
        self.shader.set_float("uAlpha", alpha)


    def draw_text(self, text: str, x: int, y: int, size: int = 18,
                  color=(255, 255, 255), bold: bool = False, center: bool = False,
                  alpha: float = 1.0, outline: bool = True, shadow: bool = False):
        if not text:
            return

        tex, tw, th = _text_tex(text, size, color, bold, outline=outline, shadow=shadow)
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

    def draw_rect(self, x: int, y: int, w: int, h: int,
                  color=(0.1, 0.1, 0.2), alpha: float = 1.0):
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

    def draw_poly(self, points, color=(0.1, 0.1, 0.2), alpha: float = 1.0):
        if len(points) < 3:
            return
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        self._setup(alpha)
        self.shader.set_bool("uUseTexture", False)
        self.shader.set_vec3("uBaseColor", color)
        vao, vbo, ibo, n_idx = _make_poly(points)
        glBindVertexArray(vao)
        glDrawElements(GL_TRIANGLES, n_idx, GL_UNSIGNED_INT, None)
        glBindVertexArray(0)
        glDisable(GL_BLEND)
        _free_quad(vao, vbo, ibo)

    def draw_gradient_rect(self, x, y, w, h, top_color, bottom_color,
                           alpha: float = 1.0, steps: int = 8):
        steps = max(2, int(steps))
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        self._setup(alpha)
        self.shader.set_bool("uUseTexture", False)
        strip_h = h / steps
        for i in range(steps):
            t = i / (steps - 1)
            col = tuple(top_color[k] + (bottom_color[k] - top_color[k]) * t for k in range(3))
            sy = y + i * strip_h
            vao, vbo, ibo = _make_quad(x, sy, w, strip_h + 1)
            self.shader.set_vec3("uBaseColor", col)
            glBindVertexArray(vao)
            glDrawElements(GL_TRIANGLES, 6, GL_UNSIGNED_INT, None)
            glBindVertexArray(0)
            _free_quad(vao, vbo, ibo)
        glDisable(GL_BLEND)


    def draw_gem(self, cx, cy, r, color, sides=4, rotation=math.pi / 4, highlight=True):
        pts = _ngon_points(cx, cy, r, sides=sides, rotation=rotation)
        self.draw_poly(pts, color)
        if highlight:
            hl_pts = _ngon_points(cx - r * 0.28, cy - r * 0.28, r * 0.4,
                                  sides=max(6, sides), rotation=rotation)
            self.draw_poly(hl_pts, _lighten(color, 0.35), 0.8)

    def draw_medallion(self, cx, cy, r, color, ring_color=None, alpha: float = 1.0):
        ring_color = ring_color or _darken(color, 0.35)
        self.draw_poly(_ngon_points(cx, cy, r + 3, sides=14), ring_color, alpha)
        self.draw_poly(_ngon_points(cx, cy, r, sides=14), color, alpha)
        hl = _ngon_points(cx - r * 0.3, cy - r * 0.35, r * 0.45, sides=10)
        self.draw_poly(hl, _lighten(color, 0.3), alpha * 0.6)

    def draw_frame(self, x, y, w, h, bg_color=PARCHMENT_DK_F, border_color=GOLD_F,
                   border_dark=GOLD_DARK_F, thickness=3, corner_gems=True,
                   gem_color=BRONZE_F, alpha: float = 1.0):
        t = thickness
        self.draw_rect(x - t - 2, y - t - 2, w + (t + 2) * 2, h + (t + 2) * 2,
                       IRON_DARK_F, alpha)
        self.draw_rect(x - t, y - t, w + t * 2, h + t * 2, border_dark, alpha)
        self.draw_rect(x - t + 1, y - t + 1, w + (t - 1) * 2, h + (t - 1) * 2,
                       border_color, alpha)
        self.draw_gradient_rect(x, y, w, h, _lighten(bg_color, 0.06), bg_color,
                                alpha, steps=6)
        if corner_gems:
            r = t + 3
            for gx, gy in ((x, y), (x + w, y), (x, y + h), (x + w, y + h)):
                self.draw_gem(gx, gy, r, gem_color, sides=8, rotation=0.0)

    def draw_banner(self, text, cx, y, w=200, h=26, base_color=CRIMSON_F,
                    edge_color=CRIMSON_DK_F, text_color=(255, 230, 190),
                    text_size=14, notch=14, alpha: float = 1.0):
        x = cx - w / 2
        outer = _banner_points(x, y, w, h, notch=notch)
        self.draw_poly(outer, edge_color, alpha)
        inset = 3
        inner = _banner_points(x + inset, y + inset, max(2, w - inset * 2),
                               max(2, h - inset * 2), notch=max(2, notch - inset))
        self.draw_poly(inner, base_color, alpha)
        self.draw_text(text, cx, y + h / 2, text_size, text_color, bold=True, center=True)

    def draw_bar(self, x: int, y: int, w: int, h: int, fill: float,
                 bar_color=(0.8, 0.1, 0.1), bg_color=(0.2, 0.2, 0.2)):

        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        self._setup()
        self.shader.set_bool("uUseTexture", False)

        def _solid(cx, cy, cw, ch, col):
            if cw <= 0 or ch <= 0:
                return
            vao, vbo, ibo = _make_quad(cx, cy, cw, ch)
            self.shader.set_vec3("uBaseColor", col)
            glBindVertexArray(vao)
            glDrawElements(GL_TRIANGLES, 6, GL_UNSIGNED_INT, None)
            glBindVertexArray(0)
            _free_quad(vao, vbo, ibo)

        _solid(x - 3, y - 3, w + 6, h + 6, IRON_DARK_F)
        _solid(x - 1, y - 1, w + 2, h + 2, BRONZE_F)

        _solid(x, y, w, h, bg_color)

        fill = max(0.0, min(1.0, fill))
        fw = int(w * fill)
        if fw > 0:
            steps = max(3, min(10, int(h)))
            bottom = _darken(bar_color, 0.35)
            for i in range(steps):
                t = i / (steps - 1)
                col = tuple(bar_color[k] + (bottom[k] - bar_color[k]) * t for k in range(3))
                sy = y + (h * i) / steps
                sh = h / steps + 1
                _solid(x, sy, fw, sh, col)
            _solid(x, y, fw, max(1, int(h * 0.3)), _lighten(bar_color, 0.25))

        glDisable(GL_BLEND)

        if w > 6:
            r = max(2.2, h * 0.32)
            self.draw_gem(x, y + h / 2, r, BRONZE_F, sides=8)
            self.draw_gem(x + w, y + h / 2, r, BRONZE_F, sides=8)


    def draw_main_hud(self, player, game_mode):
        sw, sh = self.sw, self.sh
        p = player.stats
        bx, by = 16, 16

        panel_w, panel_h = 252, 88
        self.draw_frame(bx - 8, by - 8, panel_w, panel_h,
                        bg_color=PARCHMENT_DK_F, border_color=GOLD_F,
                        border_dark=GOLD_DARK_F, thickness=3, gem_color=BRONZE_F)

        lvl_cx = bx - 8 + panel_w - 24
        lvl_cy = by - 8 + 18
        self.draw_medallion(lvl_cx, lvl_cy, 15, AMETHYST_F)
        self.draw_text(f"{p.level}", lvl_cx, lvl_cy + 1, 15, (255, 235, 190), bold=True, center=True)
        self.draw_text("NV", lvl_cx, lvl_cy + 15, 9, (225, 205, 255), bold=True, center=True)

        self.draw_bar(bx, by + 14, 196, 16, p.hp / p.max_hp,
                      bar_color=(0.88, 0.16, 0.18), bg_color=(0.16, 0.04, 0.05))
        self.draw_text(f"HP  {p.hp}/{p.max_hp}", bx + 6, by + 15, 12, (255, 225, 215), bold=True)

        self.draw_bar(bx, by + 38, 196, 16, p.mp / max(1, p.max_mp),
                      bar_color=(0.22, 0.46, 0.95), bg_color=(0.05, 0.07, 0.20))
        self.draw_text(f"MP  {p.mp}/{p.max_mp}", bx + 6, by + 39, 12, (210, 225, 255), bold=True)

        self.draw_bar(bx, by + 60, 196, 10, p.xp / max(1, p.xp_next),
                      bar_color=(0.95, 0.78, 0.16), bg_color=(0.14, 0.11, 0.03))

        if getattr(p, 'is_shielded', False):
            shield_left = int(max(0.0, p.shield_time) + 0.9)
            self.draw_gem(bx + 222, by + 45, 10, SAPPHIRE_F, sides=6)
            self.draw_text(f"{shield_left}s", bx + 216, by + 40, 11, (175, 225, 255),
                           bold=True, center=True)
            
        self.player = player
        if game_mode == "explore":
            self._draw_action_menu()
        if self.spell_menu_open:
            self._draw_spell_submenu()
        if self.item_menu_open:
            self._draw_item_submenu()
        if self.skill_menu_open:
            self._draw_skill_submenu()

        for i, (text, timer, color, y_offset) in enumerate(reversed(self.popups)):
            fade = min(1.0, timer)
            self.draw_text(
                text,
                sw // 2, sh // 2 - 80 - i * 28 + y_offset,
                size=19, color=color, bold=True,
                center=True, alpha=fade, shadow=True,
            )


    def _draw_action_menu(self):
        sh = self.sh
        bs = 68; pad = 8
        bx = pad; by = sh - bs - pad
        buttons = [
            ("ATAQUE", "Z", CRIMSON_F,  CRIMSON_DK_F),
            ("MAGIA",  "X", SAPPHIRE_F, SAPPHIRE_DK_F),
            ("ITENS",  "C", EMERALD_F,  EMERALD_DK_F),
            ("HABIL.", "V", AMETHYST_F, AMETHYST_DK_F),
        ]
        active_states = [False, self.spell_menu_open, self.item_menu_open, self.skill_menu_open]
        for i, (label, key, col, col_dk) in enumerate(buttons):
            xi = bx + i * (bs + pad)
            active = active_states[i]

            self.draw_rect(xi - 3, by - 3, bs + 6, bs + 6, IRON_DARK_F)
            frame_col = GOLD_F if active else BRONZE_F
            self.draw_rect(xi - 1, by - 1, bs + 2, bs + 2, frame_col)

            self.draw_gradient_rect(xi, by, bs, bs, _lighten(col, 0.08), col_dk)

            self.draw_medallion(xi + bs / 2, by + 22, 14, col)
            self.draw_text(label, xi + bs / 2, by + 46, 11, (250, 235, 200),
                           bold=True, center=True)

            tag_w, tag_h = 22, 14
            tx = xi + bs / 2 - tag_w / 2
            ty = by + bs - tag_h - 3
            self.draw_rect(tx, ty, tag_w, tag_h, IRON_DARK_F)
            self.draw_rect(tx, ty, tag_w, 1, frame_col)
            self.draw_text(key, xi + bs / 2, ty + tag_h / 2, 11, (230, 210, 130),
                           bold=True, center=True)


    def _draw_spell_submenu(self):
        sh = self.sh
        pw, ph = 240, 190
        px = 8 + 1 * (68 + 8)
        py = sh - 68 - 8 - ph - 8
        self.draw_frame(px, py, pw, ph, bg_color=(0.05, 0.05, 0.17),
                        border_color=GOLD_F, border_dark=SAPPHIRE_DK_F,
                        gem_color=SAPPHIRE_F, thickness=3)
        self.draw_banner("MAGIA", px + pw / 2, py - 6, w=130, h=24,
                         base_color=SAPPHIRE_F, edge_color=SAPPHIRE_DK_F,
                         text_color=(255, 255, 255))
        for i, sid in enumerate(SPELL_LIST):
            sp = SPELL_DB[sid]
            iy = py + 30 + i * 44
            ic = sp.icon_color
            if i % 2 == 0:
                self.draw_rect(px + 4, iy - 4, pw - 8, 38, (1, 1, 1), alpha=0.04)
            self.draw_medallion(px + 20, iy + 12, 14, ic)
            self.draw_text(sp.name,            px + 40, iy-2,  14, (225, 230, 255))
            if sp.name == "invisible_providence":
                self.draw_text(f"{sp.mp_cost} MP", px + 40, iy + 14, 11, (135, 175, 255))
            else:
                self.draw_text(f"{sp.mp_cost} MP", px + 40, iy + 14, 11, (135, 175, 255))
            self.draw_text(f"[{i + 1}]",       px + 210, iy + 8, 13, (230, 210, 130), bold=True)

    def _draw_item_submenu(self):
        self.inventory_items = self.player.inventory.list_consumables() if hasattr(self, 'player') else []
        
        sh = self.sh
        pw, ph = 240, 190
        px = 8 + 2 * (68 + 8)
        py = sh - 68 - 8 - ph - 8
        self.draw_frame(px, py, pw, ph, bg_color=(0.04, 0.13, 0.05),
                        border_color=GOLD_F, border_dark=EMERALD_DK_F,
                        gem_color=EMERALD_F, thickness=3)
        self.draw_banner("ITENS", px + pw / 2, py - 6, w=130, h=24,
                        base_color=EMERALD_F, edge_color=EMERALD_DK_F,
                        text_color=(255, 255, 255))
        items = self.inventory_items
        if not items:
            self.draw_text("(vazio)", px + pw / 2, py + 60, 14, (175, 205, 175), center=True)
            return
        for i, (item, qty) in enumerate(items[:4]):
            iy = py + 30 + i * 44
            if i % 2 == 0:
                self.draw_rect(px + 4, iy - 4, pw - 8, 38, (1, 1, 1), alpha=0.04)
            self.draw_medallion(px + 20, iy + 12, 14, EMERALD_F)
            self.draw_text(item.name,    px + 40, iy + 2,  13, (215, 255, 215))
            self.draw_text(f"x{qty}",    px + 40, iy + 18, 11, (160, 230, 160))
            self.draw_text(f"[{i + 1}]", px + 210, iy + 8, 13, (230, 210, 130), bold=True)
            
    def _draw_skill_submenu(self):
        sh = self.sh
        pw, ph = 260, 190
        px = 8 + 3 * (68 + 8)
        py = sh - 68 - 8 - ph - 8
        self.draw_frame(px, py, pw, ph, bg_color=(0.12, 0.09, 0.02),
                        border_color=GOLD_F, border_dark=BRONZE_F,
                        gem_color=GOLD_F, thickness=3)
        self.draw_banner("HABILIDADES", px + pw / 2, py - 6, w=190, h=24,
                         base_color=BRONZE_F, edge_color=IRON_DARK_F,
                         text_color=(255, 235, 180), text_size=12)
        skills = [
            ("Return by Death",   "Retorna da morte",          CRIMSON_F),
            ("Cheiro da Bruxa",   "Atrai o culto da bruxa",    SAPPHIRE_F),
            ("Portal Danificado", "Portal de mana danificado", CRIMSON_DK_F),
            ("Cor Leonis",        "Protege seus aliados",      AMETHYST_F),
        ]
        for i, (name, desc, col) in enumerate(skills):
            iy = py + 30 + i * 44
            if i % 2 == 0:
                self.draw_rect(px + 4, iy - 4, pw - 8, 38, (1, 1, 1), alpha=0.04)
            self.draw_medallion(px + 20, iy + 12, 14, col)
            self.draw_text(name, px + 40, iy -2,  12, (255, 230, 150))
            self.draw_text(desc, px + 40, iy + 14, 10, (205, 185, 125))


    def draw_combat_log(self, messages):
        if not messages:
            return
        sh = self.sh
        base_y = sh - 80 - len(messages) * 22
        self.draw_rect(6, base_y - 6, 340, len(messages) * 22 + 12, IRON_DARK_F, alpha=0.55)
        self.draw_rect(6, base_y - 6, 3, len(messages) * 22 + 12, GOLD_F)
        for i, msg in enumerate(messages):
            self.draw_text(msg, 16, base_y + i * 22, 14, (255, 225, 180))

    def draw_enemy_healthbar(self, name, hp_frac, sx, sy):
        w = 84
        self.draw_bar(sx - w // 2, sy, w, 9, hp_frac,
                      bar_color=(0.92, 0.13, 0.13), bg_color=(0.17, 0.05, 0.05))
        self.draw_text(name, sx, sy - 15, 12, (255, 215, 180), bold=True, center=True)

    def draw_death_screen(self):
        sw, sh = self.sw, self.sh
        self.draw_gradient_rect(0, 0, sw, sh, (0.18, 0.0, 0.0), (0.02, 0.0, 0.0), steps=12)
        self.draw_banner("VOCÊ MORREU", sw / 2, sh / 2 - 46, w=380, h=56,
                         base_color=CRIMSON_F, edge_color=IRON_DARK_F,
                         text_color=(255, 210, 210), text_size=30, notch=22)
        self.draw_text("Retorno da morte...", sw // 2, sh // 2 + 30,
                       18, (205, 140, 140), center=True, shadow=True)

    def draw_pause_overlay(self):
        sw, sh = self.sw, self.sh
        w, h = 280, 190
        x, y = sw / 2 - w / 2, sh / 2 - h / 2
        self.draw_frame(x, y, w, h, bg_color=(0.05, 0.05, 0.12),
                        border_color=GOLD_F, border_dark=SAPPHIRE_DK_F,
                        gem_color=SAPPHIRE_F, thickness=4)
        self.draw_banner("PAUSADO", sw / 2, y - 8, w=160, h=28,
                         base_color=SAPPHIRE_F, edge_color=SAPPHIRE_DK_F,
                         text_color=(255, 255, 255), text_size=18)
        self.draw_text("[ESC] Continuar",      sw / 2, sh / 2 - 6, 15, (225, 225, 235), center=True)
        self.draw_text("[Q]   Voltar ao menu", sw / 2, sh / 2 + 24, 15, (225, 225, 235), center=True)


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
            from src.game.combat import SPELL_LIST
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


    def cleanup(self):
        clear_text_cache()

    def draw_image(self, texture,
                x: int, y: int,
                w: int, h: int,
                alpha: float = 1.0):


        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

        self._setup(alpha)

        self.shader.set_bool("uUseTexture", True)
        self.shader.set_vec3("uBaseColor", (1.0, 1.0, 1.0))

        glActiveTexture(GL_TEXTURE0)
        glBindTexture(GL_TEXTURE_2D, texture.id)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR_MIPMAP_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        glGenerateMipmap(GL_TEXTURE_2D)

        vao, vbo, ibo = _make_quad(x, y, w, h)

        glBindVertexArray(vao)
        glDrawElements(
            GL_TRIANGLES,
            6,
            GL_UNSIGNED_INT,
            None
        )

        glBindVertexArray(0)
        glBindTexture(GL_TEXTURE_2D, 0)

        glDisable(GL_BLEND)

        _free_quad(vao, vbo, ibo)
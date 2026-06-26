from dataclasses import dataclass
from typing import Callable, List, Optional

import pygame

from src.hud.hud import (
    AMETHYST_F, BRONZE_F, CRIMSON_F, EMERALD_F, GOLD_DARK_F, GOLD_F,
    PARCHMENT_DK_F, SAPPHIRE_F,
)


@dataclass
class MenuItem:
    label: str
    action: Callable[[], None]


class Menu:
    def __init__(self, title: str, items: List[MenuItem]):
        self.title = title
        self.items = list(items)


_ITEM_HINTS = {
    "Nova Partida": "Inicie sua jornada em Castle Oblivion do zero.",
    "Continuar":    "Retome a jornada a partir do último save.",
    "Controles":      "Consulte teclas, magias e mecânicas do jogo.",
    "Configurações":  "Ajuste o volume da música e dos efeitos sonoros.",
    "Sair":           "Encerrar Re:Oblivion of Memories.",
    "Salvar":       "Gravar progresso no slot atual.",
    "Menu Principal": "Voltar à tela de título.",
}

_ITEM_GEM = {
    "Nova Partida":   EMERALD_F,
    "Continuar":      SAPPHIRE_F,
    "Controles":      AMETHYST_F,
    "Configurações":  (0.72, 0.58, 0.22),
    "Sair":           CRIMSON_F,
    "Salvar":         SAPPHIRE_F,
    "Menu Principal": AMETHYST_F,
}


class MenuManager:
    def __init__(self):
        self._stack: List[Menu] = []
        self._sel_stack: List[int] = []

    def push(self, menu: Menu):
        self._stack.append(menu)
        self._sel_stack.append(0)

    def pop(self):
        if self._stack:
            self._stack.pop()
            self._sel_stack.pop()

    def clear(self):
        self._stack.clear()
        self._sel_stack.clear()

    def top(self) -> Optional[Menu]:
        return self._stack[-1] if self._stack else None

    def selection_index(self) -> int:
        return self._sel_stack[-1] if self._sel_stack else 0

    def handle_input(self, inp):
        if not self._stack:
            return
        sel = self._sel_stack[-1]
        if inp.key_pressed("up") or inp.key_pressed("w"):
            sel = max(0, sel - 1)
            self._sel_stack[-1] = sel
        if inp.key_pressed("down") or inp.key_pressed("s"):
            sel = min(len(self._stack[-1].items) - 1, sel + 1)
            self._sel_stack[-1] = sel
        if inp.key_pressed("return") or inp.key_pressed("enter"):
            cur = self._stack[-1].items[sel]
            try:
                cur.action()
            except Exception:
                pass
        if inp.key_pressed("escape"):
            if len(self._stack) > 1:
                self.pop()

    def draw(self, hud, px: int, py: int, pw: int = 400, ph: int = 375, anim_t: float = 0.0):
        menu = self.top()
        if not menu:
            return

        hud.draw_frame(
            px, py, pw, ph,
            bg_color=PARCHMENT_DK_F,
            border_color=GOLD_F,
            border_dark=GOLD_DARK_F,
            thickness=3,
            gem_color=BRONZE_F,
        )

        banner_h = 32
        banner_y = py + 10
        hud.draw_banner(
            menu.title, px + pw / 2, banner_y,
            w=min(pw - 40, 340), h=banner_h,
            base_color=(0.14, 0.08, 0.26),
            edge_color=(0.42, 0.12, 0.38),
            text_color=(235, 220, 255),
            text_size=15,
            notch=12,
        )

        div_y = banner_y + banner_h + 10
        hud.draw_rect(px + 24, div_y, pw - 48, 1, GOLD_DARK_F, alpha=0.85)
        hud.draw_gem(px + 24, div_y, 3, GOLD_F, sides=4, highlight=False)
        hud.draw_gem(px + pw - 24, div_y, 3, GOLD_F, sides=4, highlight=False)

        item_y = div_y + 16
        item_h = 42
        sel_idx = self.selection_index()

        for i, it in enumerate(menu.items):
            is_sel = i == sel_idx
            row_x = px + 18
            row_w = pw - 36
            row_y = item_y - 4

            if is_sel:
                pulse = 0.55 + 0.12 * abs((anim_t * 2.5) % 2.0 - 1.0)
                hud.draw_rect(row_x, row_y, row_w, item_h, (0.22, 0.14, 0.38), alpha=pulse)
                hud.draw_rect(row_x, row_y, 3, item_h, GOLD_F, alpha=0.95)
                hud.draw_rect(row_x + row_w - 3, row_y, 3, item_h, GOLD_F, alpha=0.95)
            else:
                hud.draw_rect(row_x, row_y, row_w, item_h, (0.10, 0.08, 0.14), alpha=0.65)

            gem_col = _ITEM_GEM.get(it.label, BRONZE_F)
            gem_cx = row_x + 22
            gem_cy = row_y + item_h / 2
            hud.draw_medallion(gem_cx, gem_cy, 11, gem_col)

            if is_sel:
                hud.draw_text("›", row_x + 38, item_y + 2, 20, (255, 220, 140), bold=True)
                label_col = (255, 248, 230)
            else:
                label_col = (195, 190, 210)

            hud.draw_text(it.label, row_x + 52, item_y + 4, 17, label_col, bold=is_sel)
            item_y += item_h + 4

        hint_y = item_y + 6
        hint_box_h = py + ph - hint_y - 36
        if hint_box_h > 20:
            hud.draw_rect(px + 22, hint_y, pw - 44, hint_box_h, (0.06, 0.05, 0.10), alpha=0.55)
            hud.draw_rect(px + 22, hint_y, pw - 44, 1, GOLD_DARK_F, alpha=0.5)

            sel_label = menu.items[sel_idx].label
            hint = _ITEM_HINTS.get(sel_label, "")
            if hint:
                hud.draw_text(hint, px + pw // 2, hint_y + hint_box_h // 2 - 4,
                              13, (180, 175, 200), center=True)

        hud.draw_text(
            "↑ ↓ navegar  ·  Enter confirmar  ·  Esc voltar",
            px + pw // 2, py + ph - 18, 11, (140, 135, 160), center=True,
        )


__all__ = ["Menu", "MenuItem", "MenuManager"]

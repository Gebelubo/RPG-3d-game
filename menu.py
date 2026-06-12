"""
Lightweight menu system adapted for the Pleiades Tower RPG.
Provides `Menu`, `MenuItem` and `MenuManager` expected by `main.py`.
Rendered using the existing `HUD` drawing helpers so it integrates with
OpenGL-based UI already present in the project.
"""
from dataclasses import dataclass
from typing import Callable, List, Optional

import pygame


@dataclass
class MenuItem:
    label: str
    action: Callable[[], None]


class Menu:
    def __init__(self, title: str, items: List[MenuItem]):
        self.title = title
        self.items = list(items)


class MenuManager:
    def __init__(self):
        self._stack: List[Menu] = []
        self._sel_stack: List[int] = []

    # ── Stack ops
    def push(self, menu: Menu):
        self._stack.append(menu)
        self._sel_stack.append(0)

    def pop(self):
        if self._stack:
            self._stack.pop(); self._sel_stack.pop()

    def clear(self):
        self._stack.clear(); self._sel_stack.clear()

    def top(self) -> Optional[Menu]:
        return self._stack[-1] if self._stack else None

    def selection_index(self) -> int:
        return self._sel_stack[-1] if self._sel_stack else 0

    # ── Input handling (expects `engine.input_manager.InputManager` instance)
    def handle_input(self, inp):
        if not self._stack: return
        sel = self._sel_stack[-1]
        # navigate
        if inp.key_pressed("up") or inp.key_pressed("w"):
            sel = max(0, sel - 1)
            self._sel_stack[-1] = sel
        if inp.key_pressed("down") or inp.key_pressed("s"):
            sel = min(len(self._stack[-1].items) - 1, sel + 1)
            self._sel_stack[-1] = sel
        # activate
        if inp.key_pressed("return") or inp.key_pressed("enter"):
            cur = self._stack[-1].items[sel]
            try:
                cur.action()
            except Exception:
                pass
        # cancel/back
        if inp.key_pressed("escape"):
            # if stack has more than one menu, pop; otherwise do nothing here
            if len(self._stack) > 1:
                self.pop()

    # ── Drawing (uses `HUD` instance to render into the existing GL HUD)
    def draw(self, hud, px: int, py: int, pw: int = 340, ph: int = 240):
        # background panel
        hud.draw_rect(px, py, pw, ph, (0.06, 0.06, 0.10))
        hud.draw_rect(px, py, pw, 2, (0.25, 0.18, 0.4))

        menu = self.top()
        if not menu:
            return

        title = menu.title
        hud.draw_text(title, px + 16, py + 8, 20, (240, 240, 255), bold=True)

        # draw items
        item_y = py + 44
        for i, it in enumerate(menu.items):
            is_sel = (i == self.selection_index())
            color_bg = (0.12, 0.12, 0.18) if not is_sel else (0.22, 0.16, 0.36)
            hud.draw_rect(px + 12, item_y - 6, pw - 24, 36, color_bg)
            hud.draw_text(it.label, px + 24, item_y, 16, (230, 230, 240) if is_sel else (200, 200, 210))
            item_y += 44

        # footer
        hud.draw_text("Use ↑/↓ e Enter para selecionar. ESC volta.", px + 16, py + ph - 28, 12, (170, 170, 190))


# convenience exports
__all__ = ["Menu", "MenuItem", "MenuManager"]

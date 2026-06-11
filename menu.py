"""
menu.py  –  Stack-based menu system.
Menus are drawn via HUD (OpenGL quads/text). No pygame.draw calls.
"""

from typing import Callable


class MenuItem:
    def __init__(self, label: str, action: Callable):
        self.label  = label
        self.action = action


class Menu:
    def __init__(self, title: str, items: list):
        self.title  = title
        self.items  = items
        self.cursor = 0

    def move_up(self):
        self.cursor = (self.cursor - 1) % len(self.items)

    def move_down(self):
        self.cursor = (self.cursor + 1) % len(self.items)

    def confirm(self):
        self.items[self.cursor].action()

    def draw(self, hud, x: float, y: float, line_h: float = 32):
        hud.draw_text(self.title, x, y, font_size=24, color=(255, 220, 100))
        for i, item in enumerate(self.items):
            prefix = "> " if i == self.cursor else "  "
            color  = (255, 255, 100) if i == self.cursor else (200, 200, 200)
            hud.draw_text(f"{prefix}{item.label}",
                          x, y + line_h * (i + 1.6),
                          font_size=20, color=color)


class MenuManager:
    def __init__(self):
        self._stack: list = []

    def push(self, menu: Menu):
        self._stack.append(menu)

    def pop(self):
        if self._stack:
            return self._stack.pop()

    def current(self):
        return self._stack[-1] if self._stack else None

    def is_empty(self) -> bool:
        return not self._stack

    def clear(self):
        self._stack.clear()

    def handle_input(self, inp):
        m = self.current()
        if m is None:
            return
        if inp.key_pressed("up"):
            m.move_up()
        elif inp.key_pressed("down"):
            m.move_down()
        elif inp.key_pressed("return") or inp.key_pressed("space"):
            m.confirm()
        elif inp.key_pressed("escape"):
            self.pop()

    def draw(self, hud, x: float, y: float):
        m = self.current()
        if m:
            m.draw(hud, x, y)

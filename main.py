from src.engine.input_manager import InputManager
from src.game.game_main import Game
import pygame


if __name__ == "__main__":
    game = Game()
    game.input.__class__ = InputManager
    game.input.mouse_clicked = False
    game.input.mouse_pos = (0, 0)
    _orig_update = game.input.update
    def _patched_update():
        _orig_update()
        game.input.mouse_clicked = False
        for event in pygame.event.get(pygame.MOUSEBUTTONDOWN):
            if event.button == 1:
                game.input.mouse_clicked = True
                game.input.mouse_pos = event.pos
    game.input.update = _patched_update
    game.run()
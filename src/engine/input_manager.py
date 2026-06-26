import pygame


class InputManager:
    def __init__(self):
        self._keys_held:    set[str] = set()
        self._keys_pressed: set[str] = set()   
        self._keys_released:set[str] = set()
        self._mouse_buttons: dict[int, bool] = {}
        self._mouse_dx = 0
        self._mouse_dy = 0
        self._mouse_pos = (0, 0)
        self._scroll = 0
        self._quit  = False
        self.mouse_captured = False
        
        self.mouse_clicked = False
        self.resize_event = None


    def update(self):
        self._keys_pressed.clear()
        self._keys_released.clear()
        self._mouse_dx = 0
        self._mouse_dy = 0
        self._scroll   = 0
        self.mouse_clicked = False
        self.resize_event = None

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self._quit = True

            elif event.type == pygame.KEYDOWN:
                name = pygame.key.name(event.key)
                self._keys_held.add(name)
                self._keys_pressed.add(name)

            elif event.type == pygame.KEYUP:
                name = pygame.key.name(event.key)
                self._keys_held.discard(name)
                self._keys_released.add(name)

            elif event.type == pygame.MOUSEMOTION:
                if self.mouse_captured:
                    self._mouse_dx += event.rel[0]
                    self._mouse_dy += event.rel[1]
                self._mouse_pos = event.pos

            elif event.type == pygame.MOUSEBUTTONDOWN:
                self._mouse_buttons[event.button] = True
                if event.button == 1:
                    self.mouse_clicked = True
                    self._mouse_pos = event.pos

            elif event.type == pygame.MOUSEBUTTONUP:
                self._mouse_buttons[event.button] = False

            elif event.type == pygame.MOUSEWHEEL:
                self._scroll = event.y

            elif event.type == pygame.VIDEORESIZE:
                self.resize_event = (event.w, event.h)


    def key_held(self, *names) -> bool:
        return any(n in self._keys_held for n in names)

    def key_pressed(self, *names) -> bool:
        return any(n in self._keys_pressed for n in names)

    def key_released(self, *names) -> bool:
        return any(n in self._keys_released for n in names)

    @property
    def held_keys(self) -> set:
        return self._keys_held

    @property
    def mouse_delta(self) -> tuple[int, int]:
        return (self._mouse_dx, self._mouse_dy)

    @property
    def mouse_pos(self) -> tuple[int, int]:
        return self._mouse_pos

    @mouse_pos.setter
    def mouse_pos(self, value: tuple[int, int]):
        self._mouse_pos = value

    @property
    def scroll(self) -> int:
        return self._scroll

    def mouse_button(self, btn: int) -> bool:
        return self._mouse_buttons.get(btn, False)

    @property
    def should_quit(self) -> bool:
        return self._quit


    def capture_mouse(self, capture: bool):
        self.mouse_captured = capture
        pygame.event.set_grab(capture)
        pygame.mouse.set_visible(not capture)
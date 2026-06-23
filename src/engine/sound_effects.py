from src.here import _HERE
import os
import pygame
    
class SoundEffect:

    def __init__(self, file):
        self.file = file
        self.sfx = pygame.mixer.Sound(
            os.path.join(_HERE, "assets", "sfx", file)
        )
        self.channel = None

    def play(self, loops=0, maxtime=0, fade_ms=0):
        self.channel = self.sfx.play(
            loops=loops,
            maxtime=maxtime,
            fade_ms=fade_ms
        )
        return self.channel

    def is_playing(self):
        if self.channel is None:
            return False

        return self.channel.get_busy()

    def stop(self):
        if self.channel:
            self.channel.stop()

class Effects:
    def __init__(self):
        self.attack_sfx = SoundEffect('punch.wav')
        self.hit_sfx = SoundEffect('hit.wav')
        self.walk_sfx = SoundEffect('walk.wav')
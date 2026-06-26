from src.here import _HERE
import os
import time
import pygame

PRIORITY_MARLUXIA_TOP = 5
PRIORITY_SPELL        = 4
PRIORITY_MARLUXIA     = 3
PRIORITY_VOICE        = 2
PRIORITY_ENEMY        = 2
PRIORITY_WALK         = 1
PRIORITY_NONE         = 0  


class SoundEffect:
    """
    Agora cada SoundEffect pode pertencer a uma "categoria" de prioridade.
    Em vez de deixar o pygame.mixer escolher um canal qualquer (o que faz
    sons importantes (voiceline de magia) às vezes não tocarem porque não
    achou canal livre, ou serem cortados por outro som que caiu no mesmo
    canal por acaso), sons com categoria reservam um CANAL DEDICADO
    (via ChannelManager) e podem interromper canais de prioridade menor.
    """

    def __init__(self, file_path, cooldown: float = 0.0, priority: int = PRIORITY_NONE):
        self.file_path = file_path
        self.sfx = pygame.mixer.Sound(
            os.path.join(_HERE, "assets", "sfx", file_path)
        )
        self.channel = None
        self.cooldown = cooldown
        self._last_played = -999.0  
        self.priority = priority

    def play(self, loops=0, maxtime=0, fade_ms=0):
        now = time.monotonic()
        if self.cooldown > 0.0 and (now - self._last_played) < self.cooldown:
            return None  

        if self.priority > PRIORITY_NONE:

            channel = ChannelManager.play_priority(
                self.sfx, self.priority, loops=loops, maxtime=maxtime, fade_ms=fade_ms
            )
        else:
  
            channel = self.sfx.play(loops=loops, maxtime=maxtime, fade_ms=fade_ms)
            if channel is None:
  
                forced = pygame.mixer.find_channel(True)
                if forced is not None:
                    forced.play(self.sfx, loops=loops, maxtime=maxtime, fade_ms=fade_ms)
                    channel = forced

        if channel is None:
            return None

        self._last_played = now
        self.channel = channel
        return self.channel

    def is_playing(self):
        if self.channel is None:
            return False
        return self.channel.get_busy()

    def stop(self):
        if self.channel:
            self.channel.stop()


class ChannelManager:

    _initialized = False
    _channel_by_priority = {}  

    MARLUXIA_TOP_CHANNEL_ID = 0
    SPELL_CHANNEL_ID        = 1
    MARLUXIA_CHANNEL_ID     = 2
    VOICE_CHANNEL_ID        = 3
    ENEMY_CHANNEL_ID        = 4
    WALK_CHANNEL_ID         = 5

    _PRIORITY_ORDER = (
        PRIORITY_MARLUXIA_TOP, PRIORITY_SPELL, PRIORITY_MARLUXIA,
        PRIORITY_VOICE, PRIORITY_ENEMY, PRIORITY_WALK,
    )

    @classmethod
    def _ensure_init(cls):
        if cls._initialized:
            return

        if pygame.mixer.get_num_channels() < 10:
            pygame.mixer.set_num_channels(10)

        cls._channel_by_priority = {
            PRIORITY_MARLUXIA_TOP: pygame.mixer.Channel(cls.MARLUXIA_TOP_CHANNEL_ID),
            PRIORITY_SPELL:        pygame.mixer.Channel(cls.SPELL_CHANNEL_ID),
            PRIORITY_MARLUXIA:     pygame.mixer.Channel(cls.MARLUXIA_CHANNEL_ID),
            PRIORITY_VOICE:        pygame.mixer.Channel(cls.VOICE_CHANNEL_ID),
            PRIORITY_ENEMY:        pygame.mixer.Channel(cls.ENEMY_CHANNEL_ID),
            PRIORITY_WALK:         pygame.mixer.Channel(cls.WALK_CHANNEL_ID),
        }

        try:
            pygame.mixer.set_reserved(cls.WALK_CHANNEL_ID + 1)
        except Exception:
            pass
        cls._initialized = True

    @classmethod
    def play_priority(cls, sfx, priority, loops=0, maxtime=0, fade_ms=0):
        cls._ensure_init()
        channel = cls._channel_by_priority.get(priority)
        if channel is None:
            return sfx.play(loops=loops, maxtime=maxtime, fade_ms=fade_ms)


        for other_priority in cls._PRIORITY_ORDER:
            if other_priority >= priority:
                continue
            other_ch = cls._channel_by_priority.get(other_priority)
            if other_ch is not None and other_ch.get_busy():
                other_ch.stop()


        for other_priority in cls._PRIORITY_ORDER:
            if other_priority <= priority:
                continue
            other_ch = cls._channel_by_priority.get(other_priority)
            if other_ch is not None and other_ch.get_busy():
                return None

        channel.play(sfx, loops=loops, maxtime=maxtime, fade_ms=fade_ms)
        return channel


class Effects:
    def __init__(self):
        ChannelManager._ensure_init()


        self.emilia_thankyou = SoundEffect('emilia_sfx/thankyou.mp3', priority=PRIORITY_MARLUXIA_TOP)


        self.heartless_attack = SoundEffect('heartless_sfx/heartless_attack.mp3', priority=PRIORITY_ENEMY)
        self.heartless_death  = SoundEffect('heartless_sfx/heartless_death.mp3',  priority=PRIORITY_ENEMY)


        self.marluxia_curse        = SoundEffect('marluxia_sfx/curse.mp3',          priority=PRIORITY_MARLUXIA_TOP)
        self.marluxia_death        = SoundEffect('marluxia_sfx/marluxia_death.mp3', priority=PRIORITY_MARLUXIA_TOP)
        self.marluxia_fase4        = SoundEffect('marluxia_sfx/marluxia_fase4.mp3', priority=PRIORITY_MARLUXIA_TOP)
        self.marluxia_fase5        = SoundEffect('marluxia_sfx/marluxia_fase5.mp3', priority=PRIORITY_MARLUXIA_TOP)


        self.marluxia_heavy_attack = SoundEffect('marluxia_sfx/heavy_attack.mp3',  priority=PRIORITY_MARLUXIA)
        self.marluxia_hit          = SoundEffect('marluxia_sfx/marluxia_hit.mp3',   priority=PRIORITY_MARLUXIA)
        self.marluxia_shoot        = SoundEffect('marluxia_sfx/marluxia_shoot.mp3', priority=PRIORITY_MARLUXIA)
        self.marluxia_normal_attack= SoundEffect('marluxia_sfx/normal_attack.mp3',  priority=PRIORITY_MARLUXIA)
        self.marluxia_round_attack = SoundEffect('marluxia_sfx/round_attack.mp3',   priority=PRIORITY_MARLUXIA)
        self.marluxia_taunt        = SoundEffect('marluxia_sfx/taunt.mp3',          priority=PRIORITY_MARLUXIA)

        self.subaru_hit      = SoundEffect('subaru_sfx/hit.wav',  cooldown=2.0, priority=PRIORITY_VOICE)
        self.subaru_myname   = SoundEffect('subaru_sfx/mynameisnatsukisubaru.mp3', priority=PRIORITY_VOICE)
        self.subaru_parry    = SoundEffect('subaru_sfx/parry.mp3', priority=PRIORITY_VOICE)
        self.subaru_punch    = SoundEffect('subaru_sfx/punch.wav', cooldown=0.5, priority=PRIORITY_VOICE)

  
        self.subaru_emt       = SoundEffect('subaru_sfx/subaru_EMT.mp3', priority=PRIORITY_SPELL)
        self.subaru_invisible = SoundEffect('subaru_sfx/subaru_invisibleprovidence.mp3', priority=PRIORITY_SPELL)
        self.subaru_minya     = SoundEffect('subaru_sfx/subaru_minya.mp3', priority=PRIORITY_SPELL)
        self.subaru_shamac    = SoundEffect('subaru_sfx/subaru_shamac.mp3', priority=PRIORITY_SPELL)
        self.subaru_death     = SoundEffect('subaru_sfx/subaru_death.mp3', priority=PRIORITY_SPELL)

        self.subaru_walk = SoundEffect('subaru_sfx/walk.wav', priority=PRIORITY_WALK)

        self._master_volume = 1.0
        self._collect_effects()

    def _collect_effects(self):
        self._effects = [
            v for v in self.__dict__.values()
            if isinstance(v, SoundEffect)
        ]

    def set_master_volume(self, volume: float):
        self._master_volume = max(0.0, min(1.0, float(volume)))
        for fx in self._effects:
            fx.sfx.set_volume(self._master_volume)
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
        self._last_played = -999.0  # nunca tocou
        self.priority = priority

    def play(self, loops=0, maxtime=0, fade_ms=0):
        now = time.monotonic()
        if self.cooldown > 0.0 and (now - self._last_played) < self.cooldown:
            return None  # ainda em cooldown

        if self.priority > PRIORITY_NONE:
            # Sons "importantes" passam pelo gerenciador de canais dedicados,
            # que garante um canal próprio e pode silenciar canais de menor
            # prioridade (ex: spell corta voice/walk).
            channel = ChannelManager.play_priority(
                self.sfx, self.priority, loops=loops, maxtime=maxtime, fade_ms=fade_ms
            )
        else:
            # Sons "soltos": deixa o mixer escolher um canal qualquer,
            # mas com fallback se não achar nenhum livre.
            channel = self.sfx.play(loops=loops, maxtime=maxtime, fade_ms=fade_ms)
            if channel is None:
                # Não achou canal livre — força um canal genérico
                # (find_channel(True) força a criação/reaproveitamento de um)
                forced = pygame.mixer.find_channel(True)
                if forced is not None:
                    forced.play(self.sfx, loops=loops, maxtime=maxtime, fade_ms=fade_ms)
                    channel = forced

        if channel is None:
            # Mesmo com fallback não conseguiu canal (extremamente raro) —
            # não trava o jogo, só não toca. Mas NÃO marca _last_played,
            # pra próxima tentativa não cair em cooldown sem nunca ter tocado.
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
    """
    Reserva canais fixos por categoria de prioridade, pra:
    - voicelines do Marluxia NUNCA serem cortadas por nada (prioridade máxima
      — é o boss, sua voz tem que ser sempre ouvida);
    - voicelines de magia do Subaru se sobressaírem a hit/punch/walk;
    - heartless/aerialknocker terem canal garantido (antes competiam por
      canal "solto" e podiam simplesmente não tocar);
    - cada categoria mais "alta" poder cortar as mais "baixas" quando precisa
      tocar, e nunca o contrário.

    Layout de canais reservados (pygame.mixer.set_num_channels(32) já é
    chamado em _init_window, então sobra canal de sobra pro resto dos sons
    "soltos" tocarem em paralelo sem conflitar com esses).
    """

    _initialized = False
    _channel_by_priority = {}  # priority -> pygame.mixer.Channel

    MARLUXIA_TOP_CHANNEL_ID = 0
    SPELL_CHANNEL_ID        = 1
    MARLUXIA_CHANNEL_ID     = 2
    VOICE_CHANNEL_ID        = 3
    ENEMY_CHANNEL_ID        = 4
    WALK_CHANNEL_ID         = 5

    # Ordem de prioridade do maior pro menor — usada pra decidir quem corta quem.
    _PRIORITY_ORDER = (
        PRIORITY_MARLUXIA_TOP, PRIORITY_SPELL, PRIORITY_MARLUXIA,
        PRIORITY_VOICE, PRIORITY_ENEMY, PRIORITY_WALK,
    )

    @classmethod
    def _ensure_init(cls):
        if cls._initialized:
            return
        # Garante que existem canais suficientes pra reservar os fixos
        # (não reduz o total já configurado, só garante o mínimo).
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
        # Esses 6 canais ficam reservados — o mixer nunca os usa
        # automaticamente para sons "soltos" (sem prioridade), então eles
        # nunca são "roubados" por engano.
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

        # Regra central: qualquer categoria corta TODAS as categorias de
        # prioridade menor que estejam tocando no momento. Isso garante,
        # por exemplo, que o Marluxia (prioridade máxima) sempre seja
        # ouvido por cima de spell/voice/enemy/walk, sem exceção.
        for other_priority in cls._PRIORITY_ORDER:
            if other_priority >= priority:
                continue
            other_ch = cls._channel_by_priority.get(other_priority)
            if other_ch is not None and other_ch.get_busy():
                other_ch.stop()

        # Uma categoria não toca por cima de uma categoria de prioridade MAIOR
        # que já esteja em andamento — ela cede e espera a vez (em vez de
        # tentar tocar e ser imediatamente cortada/sobreposta de forma feia).
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

        # Emilia — fala dela fica no topo (mesmo nível das voicelines
        # mais importantes do Marluxia).
        self.emilia_thankyou = SoundEffect('emilia_sfx/thankyou.mp3', priority=PRIORITY_MARLUXIA_TOP)

        # Heartless / AerialKnocker — canal dedicado (PRIORITY_ENEMY) pra
        # garantir que sempre toquem, independente de quantos outros sons
        # estejam disputando canal "solto" no momento. Cooldown removido do
        # attack: agora que o canal é garantido, o cooldown só causava
        # silêncio sem necessidade (o corte em cascata já evita sobreposição
        # ruim entre ataques rápidos).
        self.heartless_attack = SoundEffect('heartless_sfx/heartless_attack.mp3', priority=PRIORITY_ENEMY)
        self.heartless_death  = SoundEffect('heartless_sfx/heartless_death.mp3',  priority=PRIORITY_ENEMY)

        # Marluxia — topo absoluto de prioridade: curse / death / fase4 / fase5.
        # São os momentos mais importantes da luta (transições de fase e morte),
        # então cortam tudo, inclusive as próprias magias do Subaru.
        self.marluxia_curse        = SoundEffect('marluxia_sfx/curse.mp3',          priority=PRIORITY_MARLUXIA_TOP)
        self.marluxia_death        = SoundEffect('marluxia_sfx/marluxia_death.mp3', priority=PRIORITY_MARLUXIA_TOP)
        self.marluxia_fase4        = SoundEffect('marluxia_sfx/marluxia_fase4.mp3', priority=PRIORITY_MARLUXIA_TOP)
        self.marluxia_fase5        = SoundEffect('marluxia_sfx/marluxia_fase5.mp3', priority=PRIORITY_MARLUXIA_TOP)

        # Marluxia — ataques de combate "normais": ficam um nível abaixo das
        # magias do Subaru (cedem pra elas), mas ainda acima da voz geral
        # do Subaru/heartless/walk.
        self.marluxia_heavy_attack = SoundEffect('marluxia_sfx/heavy_attack.mp3',  priority=PRIORITY_MARLUXIA)
        self.marluxia_hit          = SoundEffect('marluxia_sfx/marluxia_hit.mp3',   priority=PRIORITY_MARLUXIA)
        self.marluxia_shoot        = SoundEffect('marluxia_sfx/marluxia_shoot.mp3', priority=PRIORITY_MARLUXIA)
        self.marluxia_normal_attack= SoundEffect('marluxia_sfx/normal_attack.mp3',  priority=PRIORITY_MARLUXIA)
        self.marluxia_round_attack = SoundEffect('marluxia_sfx/round_attack.mp3',   priority=PRIORITY_MARLUXIA)
        self.marluxia_taunt        = SoundEffect('marluxia_sfx/taunt.mp3',          priority=PRIORITY_MARLUXIA)

        # Subaru — voz geral (hit/punch/myname/parry): prioridade VOICE
        self.subaru_hit      = SoundEffect('subaru_sfx/hit.wav',  cooldown=2.0, priority=PRIORITY_VOICE)
        self.subaru_myname   = SoundEffect('subaru_sfx/mynameisnatsukisubaru.mp3', priority=PRIORITY_VOICE)
        self.subaru_parry    = SoundEffect('subaru_sfx/parry.mp3', priority=PRIORITY_VOICE)
        self.subaru_punch    = SoundEffect('subaru_sfx/punch.wav', cooldown=0.5, priority=PRIORITY_VOICE)

        # Subaru — voicelines de MAGIA + morte: prioridade SPELL (alta, só
        # cede pro topo do Marluxia/Emilia).
        self.subaru_emt       = SoundEffect('subaru_sfx/subaru_EMT.mp3', priority=PRIORITY_SPELL)
        self.subaru_invisible = SoundEffect('subaru_sfx/subaru_invisibleprovidence.mp3', priority=PRIORITY_SPELL)
        self.subaru_minya     = SoundEffect('subaru_sfx/subaru_minya.mp3', priority=PRIORITY_SPELL)
        self.subaru_shamac    = SoundEffect('subaru_sfx/subaru_shamac.mp3', priority=PRIORITY_SPELL)
        self.subaru_death     = SoundEffect('subaru_sfx/subaru_death.mp3', priority=PRIORITY_SPELL)

        # Subaru — passos: prioridade WALK (a mais baixa, cede pra tudo)
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
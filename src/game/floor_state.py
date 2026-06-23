from src.engine.obstacle import Hitbox


class FloorState:
    def __init__(self):
        self.enemies         = []   # lista de (Enemy, SceneNode)
        self.barrier_active  = False
        self.barrier_node    = None
        self.door_node       = None
        self.stair_locked    = True
        self.has_stairs      = False
        self.puzzle_solved   = False
        self.rhythm_done     = False
        # Lista de obstáculos decorativos: (cx, cz, raio) para colisão push-out
        self.obstacles: list[Hitbox] = []
        self.combat_wave     = 0    # qual onda de combate estamos
        self.all_clear       = False
        # ── Puzzle extras ──────────────────────────────────────────────────
        self.puzzle_guards:   list = []   # list[(Enemy, node)] guardando peça 1
        self.push_box         = None      # dict com estado da caixa empurrável
        self.in_parkour_room  = False     # True enquanto sub-sala parkour ativa
        self.parkour_pieces_state = []    # snapshot de collected p/ restaurar
        # Boss
        self.boss            = None
        self.boss_node       = None
        self.emilia_node     = None
        # Corredor final
        self.gauntlet_waves  = []
        self.gauntlet_idx    = 0
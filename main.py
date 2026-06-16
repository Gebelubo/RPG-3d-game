"""
main.py  –  Torre de Plêiades RPG (Re:Zero)
Natsuki Subaru sobe a torre para salvar Emilia.

Controles:
  WASD          – mover
  Mouse         – girar câmera
  Espaço        – pular
  Shift         – rolar (dodge)
  Z             – atacar
  X             – abrir menu de magias
  C             – abrir menu de itens
  V             – abrir habilidades
  1-4           – usar magia/item do submenu aberto
  ESC           – pausar / soltar mouse
  F1            – wireframe (debug)

Andares da torre:
  0 - Corredor de entrada  (tutorial: porta + barreira + heartless básicos)
  1 - Primeiro andar       (puzzle + escada trancada)
  2 - Segundo andar        (combate aéreo: heartless voadores)
  3 - Terceiro andar       (minigame de ritmo)
  4 - Corredor final       (gauntlet – todos os tipos de heartless)
  5 - Sala de descanso     (save + recuperação)
  6 - Sala do boss         (Marluxia + Emilia inconsciente)
"""

import time

import os, sys, math, random, json
import pygame
from pygame.locals import DOUBLEBUF, OPENGL, RESIZABLE
from OpenGL.GL import (
    glViewport, glEnable, glDisable, glClearColor, glClear,
    glDepthFunc, glPolygonMode, glLineWidth,
    GL_DEPTH_TEST, GL_LEQUAL, GL_COLOR_BUFFER_BIT, GL_DEPTH_BUFFER_BIT,
    GL_FRONT_AND_BACK, GL_FILL, GL_LINE,
)
import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

from engine.math3d     import vec3
from engine.shader     import ShaderProgram
from engine.mesh       import Mesh, ProceduralMesh, make_cube, make_plane, make_sphere
from engine.texture    import Texture, ProceduralTexture
from engine.obj_loader import OBJLoader
from engine.camera     import Camera
from engine.scene      import Scene, SceneNode, PointLight
from engine.input_manager import InputManager
from game.rpg_data     import Player, Stats, Enemy, SPELL_DB, SPELL_LIST, ITEM_DB
from hud               import HUD
from menu              import Menu, MenuItem, MenuManager

SCREEN_W, SCREEN_H = 1280, 720
TITLE = "Torre de Plêiades – Re:Zero RPG"
SHADER_DIR = os.path.join(_HERE, "assets", "shaders")
SAVE_PATH  = os.path.join(_HERE, "savegame.json")

ROOM_W = 20.0
ROOM_D = 30.0
ROOM_H = 8.0

STAIR_COUNT     = 5
STAIR_WIDTH     = 3.0
STAIR_STEP_H    = 0.4
STAIR_STEP_D    = 1.2
STAIR_Z_START   = -10.5
STAIR_Z_SPACING = 1.0

# ── Helpers ───────────────────────────────────────────────────────────────────

def make_box_mesh(name, w, h, d, color, ka=0.2, kd=0.8, ks=0.2, shin=16):
    verts, idxs = make_cube(1.0)
    verts = verts.copy()
    verts[:, 0] *= w / 2.0
    verts[:, 1] *= h / 2.0
    verts[:, 2] *= d / 2.0
    return ProceduralMesh(name, verts, idxs, base_color=color, ka=ka, kd=kd, ks=ks, shininess=shin)


def _stair_step_bounds(i: int) -> dict:
    y_bot = i * STAIR_STEP_H
    y_top = (i + 1) * STAIR_STEP_H
    zc = STAIR_Z_START - i * STAIR_Z_SPACING
    half_w = STAIR_WIDTH / 2.0
    half_d = STAIR_STEP_D / 2.0
    return {
        "x0": -half_w, "x1": half_w,
        "z0": zc - half_d, "z1": zc + half_d,
        "y0": y_bot, "y1": y_top,
    }


def _build_stairs(scene, floor_state):
    """Cria degraus visuais e marca o andar como tendo escada com colisão."""
    for i in range(STAIR_COUNT):
        y_center = i * STAIR_STEP_H + STAIR_STEP_H / 2.0
        z_center = STAIR_Z_START - i * STAIR_Z_SPACING
        sm = make_box_mesh(
            f"stair_{i}", STAIR_WIDTH, STAIR_STEP_H, STAIR_STEP_D,
            color=(0.50, 0.45, 0.40),
        )
        scene.add(SceneNode(f"stair_{i}", mesh=sm, position=(0, y_center, z_center)))
    floor_state.has_stairs = True


def _collect_meshes(node):
    """Retorna lista de objetos mesh do node e de todos os seus children (modelos .obj
    carregam como um parent sem mesh + vários children com mesh)."""
    meshes = []
    if getattr(node, "mesh", None) is not None:
        meshes.append(node.mesh)
    for child in getattr(node, "children", []):
        meshes.extend(_collect_meshes(child))
    return meshes


def _restore_colors(re_):
    for m, c in zip(re_["meshes"], re_["orig_colors"]):
        m.base_color = c


def _flash_color(re_, color):
    for m in re_["meshes"]:
        m.base_color = color


# Cache global de MeshData por caminho — evita re-parse de .obj a cada spawn
_OBJ_CACHE: dict[str, list] = {}

# Pasta dos modelos da torre
MODEL_TOWER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "models", "tower")


def _load_tower_model(name, position=(0,0,0), rotation=(0,0,0), scale=(1,1,1)):
    """Atalho para carregar modelos .obj da pasta assets/models/tower."""
    path = os.path.join(MODEL_TOWER, f"{name}.obj")
    return _load_obj_model(path, position=position, rotation=rotation, scale=scale)


def _add_tower_deco(scene, floor_state, name, position, scale=(1,1,1), rotation=(0,0,0), collision_radius=1.0):
    """Cria decoração procedural da torre (obelisk, crystal, platform, tower) com caminhos de textura corrigidos.
    Não depende dos .obj — gera geometria interna para evitar cubos pretos sem física."""
    x, y, z = position
    sx, sy, sz = scale

    node_texture = None
    # Definindo a pasta base correta para as texturas
    base_path = os.path.join(_HERE, "assets", "models", "tower") + os.sep

    if name == "obelisk":
        # Pilar fino e alto
        verts, idxs = make_cube(1.0)
        mesh = ProceduralMesh("obelisk", verts, idxs,
                              base_color=(0.25, 0.20, 0.35),
                              ka=0.3, kd=0.7, ks=0.4, shininess=32)
        
        # Caminho corrigido: assets/models/tower/obsidian.png
        node_texture = Texture(f"{base_path}obsidian.png")
        
        node = SceneNode("obelisk", mesh=mesh, texture=node_texture,
                         position=[x, y + 2.0 * sy, z],
                         scale=[0.4 * sx, 4.0 * sy, 0.4 * sz])

    elif name == "crystal":
        # Cristal: esfera achatada verticalmente com cor esverdeada
        verts, idxs = make_sphere(0.5, 8, 8)
        mesh = ProceduralMesh("crystal", verts, idxs,
                              base_color=(0.15, 0.60, 0.55),
                              ka=0.4, kd=0.6, ks=0.9, shininess=80)
        
        # Caminho corrigido: assets/models/tower/rune_crystal.png
        node_texture = Texture(f"{base_path}rune_crystal.png")
        
        node = SceneNode("crystal", mesh=mesh, texture=node_texture,
                         position=[x, y + 0.6 * sy, z],
                         scale=[0.5 * sx, 1.2 * sy, 0.5 * sz])

    elif name == "platform":
        # Plataforma: cubo largo e baixo
        verts, idxs = make_cube(1.0)
        mesh = ProceduralMesh("platform", verts, idxs,
                              base_color=(0.45, 0.40, 0.35),
                              ka=0.3, kd=0.8, ks=0.2, shininess=12)
        
        # Caminho corrigido: assets/models/tower/tower_stone.png
        node_texture = Texture(f"{base_path}tower_stone.png")
        
        node = SceneNode("platform", mesh=mesh, texture=node_texture,
                         position=[x, y + 0.2 * sy, z],
                         scale=[2.5 * sx, 0.4 * sy, 2.5 * sz])

    elif name == "tower":
        # Torre: cubo alto e estreito
        verts, idxs = make_cube(1.0)
        mesh = ProceduralMesh("tower", verts, idxs,
                              base_color=(0.30, 0.25, 0.40),
                              ka=0.3, kd=0.7, ks=0.3, shininess=16)
        
        # Caminho corrigido: assets/models/tower/tower_stone.png
        node_texture = Texture(f"{base_path}tower_stone.png")
        
        node = SceneNode("tower", mesh=mesh, texture=node_texture,
                         position=[x, y + 3.0 * sy, z],
                         scale=[1.5 * sx, 6.0 * sy, 1.5 * sz])
    else:
        return None

    scene.add(node)
    floor_state.obstacles.append((x, z, collision_radius))
    return node

def _load_obj_model(path, position=(0,0,0), rotation=(0,0,0), scale=(1,1,1)):
    #is_heartless = os.path.basename(path) == "Heartless.obj"
    model_dir    = os.path.dirname(os.path.abspath(path))
    if path not in _OBJ_CACHE:
        try:
            _OBJ_CACHE[path] = OBJLoader().load(path) or []
        except Exception as exc:
            print(f"OBJ load failed for {path}: {exc}")
            _OBJ_CACHE[path] = []
    mesh_data_list = _OBJ_CACHE[path]
    if not mesh_data_list:
        return None
    parent = SceneNode(
        os.path.splitext(os.path.basename(path))[0],
        position=list(position), rotation=list(rotation), scale=list(scale)
    )
    for md in mesh_data_list:
        mesh = Mesh(md)

        texture = None
        if mesh.texture_path:
            # Sempre resolve pela pasta do .obj — ignora qualquer prefixo de caminho
            # que o loader possa ter adicionado com base no cwd errado
            tex_name = os.path.basename(mesh.texture_path)
            tex_path = os.path.join(model_dir, tex_name)
            if not os.path.exists(tex_path):
                # Fallback: tenta o caminho original caso já seja absoluto e correto
                tex_path = mesh.texture_path
            try:
                texture = Texture(tex_path)
            except Exception as exc:
                print(f"Failed to load texture {tex_path}: {exc}")
        child = SceneNode(mesh.name, mesh=mesh, texture=texture)
        #if is_heartless:
        #    child.position[1] -= 1.5
        #    child.rotation = [0.0, 180.0, 180.0]
        #else:
        child.position[1] = -0.5

        parent.children.append(child)

    return parent


def _spawn_heartless(scene, pos, scale=(0.012,0.012,0.012), level=2, stationary=False, flying=False):
    """Spawna um heartless no mundo e retorna (enemy, node)."""
    if flying:
        model_path = os.path.join(_HERE, "assets", "models", "AerialKnocker", "AerialKnocker.obj")
        model_scale = (scale[0] * 0.8, scale[1] * 0.8, scale[2] * 0.8)  # ajuste fino se necessário
        rotation = (0, 180, 0)
    else:
        model_path = os.path.join(_HERE, "assets", "models", "Heartless", "Heartless.obj")
        model_scale = scale
        pos = (pos[0], pos[1] - 0.5, pos[2])  # ajuste para alinhar com o chão
        rotation = (180, 0, 0)

    node = _load_obj_model(model_path, position=pos, rotation=rotation, scale=model_scale)

    if node is None:
        ev, ei = make_sphere(0.45, 10, 10)
        color = (0.3, 0.3, 0.9) if flying else (0.7, 0.1, 0.1)
        em = ProceduralMesh("heartless", ev, ei, base_color=color,
                            ka=0.3, kd=0.8, ks=0.3, shininess=16)
        node = SceneNode("heartless", mesh=em, position=list(pos))
    scene.add(node)
    e = Enemy("Heartless", level=level, world_pos=list(pos), stationary=stationary)
    e.spawn_pos = list(pos)
    return e, node


# ── Save / Load ───────────────────────────────────────────────────────────────

def save_game(floor: int, player: Player):
    data = {
        "floor": floor,
        "hp": player.stats.hp,
        "mp": player.stats.mp,
        "max_hp": player.stats.max_hp,
        "max_mp": player.stats.max_mp,
        "level": player.stats.level,
        "xp": player.stats.xp,
        "xp_next": player.stats.xp_next,
        "atk": player.stats.atk,
        "defense": player.stats.defense,
        "inventory": player.inventory.items,
        "gold": player.inventory.gold,
    }
    with open(SAVE_PATH, "w") as f:
        json.dump(data, f)


def load_game(player: Player):
    if not os.path.exists(SAVE_PATH):
        return None
    with open(SAVE_PATH) as f:
        data = json.load(f)
    player.stats.hp      = data.get("hp", player.stats.max_hp)
    player.stats.mp      = data.get("mp", player.stats.max_mp)
    player.stats.max_hp  = data.get("max_hp", player.stats.max_hp)
    player.stats.max_mp  = data.get("max_mp", player.stats.max_mp)
    player.stats.level   = data.get("level", 1)
    player.stats.xp      = data.get("xp", 0)
    player.stats.xp_next = data.get("xp_next", 100)
    player.stats.atk     = data.get("atk", player.stats.atk)
    player.stats.defense = data.get("defense", player.stats.defense)
    player.inventory.items = {k: v for k, v in data.get("inventory", {}).items()}
    player.inventory.gold  = data.get("gold", 0)
    return data.get("floor", 0)


# ── Floor builders ────────────────────────────────────────────────────────────

class FloorState:
    """Estado específico de cada andar."""
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
        self.obstacles       = []
        self.combat_wave     = 0    # qual onda de combate estamos
        self.all_clear       = False
        # Boss
        self.boss            = None
        self.boss_node       = None
        self.emilia_node     = None
        # Corredor final
        self.gauntlet_waves  = []
        self.gauntlet_idx    = 0


class Game:
    # Andares
    FLOOR_ENTRY   = 0   # Corredor de entrada + tutorial
    FLOOR_PUZZLE  = 1   # Puzzle
    FLOOR_AERIAL  = 2   # Heartless voadores
    FLOOR_RHYTHM  = 3   # Minigame de ritmo
    FLOOR_GAUNTLET= 4   # Corredor final
    FLOOR_REST    = 5   # Sala de descanso
    FLOOR_BOSS    = 6   # Marluxia + Emilia

    def __init__(self):
        self._init_window()
        self._init_gl()
        self._init_shaders()
        self._init_game_state()
        # Não carrega nenhum andar aqui — o menu já foi empurrado por _init_game_state.
        # _build_floor só roda quando o jogador escolhe Nova Partida ou Continuar.

    # ── Init ─────────────────────────────────────────────────────────────────

    def _init_window(self):
        pygame.init(); pygame.font.init()
        # Música de fundo
        pygame.mixer.music.load(os.path.join(_HERE, "assets", "music", "trilha.mp3"))
        pygame.mixer.music.set_volume(0.2)
        pygame.mixer.music.play(-1)  # -1 = loop infinito
        pygame.display.set_mode((SCREEN_W, SCREEN_H), DOUBLEBUF|OPENGL|RESIZABLE)
        pygame.display.set_caption(TITLE)
        self.screen_w = SCREEN_W; self.screen_h = SCREEN_H

    def _init_gl(self):
        glEnable(GL_DEPTH_TEST); glDepthFunc(GL_LEQUAL)
        glClearColor(0.02, 0.02, 0.06, 1.0)

    def _init_shaders(self):
        def sh(v, f):
            return ShaderProgram(os.path.join(SHADER_DIR, v), os.path.join(SHADER_DIR, f))
        self.phong_shader = sh("phong.vert", "phong.frag")
        self.unlit_shader = sh("unlit.vert", "unlit.frag")

    def _init_game_state(self):
        self.input       = InputManager()
        self.player      = Player("Natsuki Subaru")
        self.combat      = None
        self.game_mode   = "menu"
        self.wireframe   = False
        self.clock       = pygame.time.Clock()
        self.hud         = HUD(self.screen_w, self.screen_h, self.unlit_shader)
        self.menus       = MenuManager()
        self.death_timer = 0.0
        self._combat_enemy_ref = None
        self.current_floor = self.FLOOR_ENTRY
        self.floor_state   = FloorState()
        self.scene  = Scene()
        self.camera = Camera()
        self.scene.set_aspect(self.screen_w / self.screen_h)
        self.player_node = None
        # Beatrice — aparece ao lado do Subaru ao usar certas magias
        self.beatrice_node  = None
        self.beatrice_timer = 0.0
        # Minigame de ritmo
        self.rhythm_active   = False
        self.rhythm_beats    = []
        self.rhythm_score    = 0
        self.rhythm_total    = 0
        self.rhythm_timer    = 0.0
        self.rhythm_window      = 0.20   # janela de acerto (centrada no beat)
        self.rhythm_warn_window = 0.55   # janela de aviso visual (começa antes do beat)
        self.rhythm_enemies    = []
        self.rhythm_targets    = []
        self.rhythm_active_idx = -1
        # Cutscene/story
        self.story_active    = False
        self.story_lines     = []
        self.story_idx       = 0
        self.story_timer     = 0.0
        self.story_callback  = None
        # Créditos
        self.credits_active  = False
        self.credits_timer   = 0.0
        self.credits_y       = 0.0
        # Fade de transição entre andares
        self._fade_alpha      = 0.0
        self._fade_duration   = 0.0
        self._fade_callback   = None
        self._fade_done       = True
        self._fading             = False
        self._fade_in            = False
        self._post_fade_mode     = "explore"
        self._fade_build_pending = False
        self._push_title_menu()

    # ── Cena base ─────────────────────────────────────────────────────────────

    def _clear_scene(self):
        if hasattr(self, 'scene') and self.scene is not None:
            self.scene.cleanup()
        self.scene = Scene()
        self.scene.set_aspect(self.screen_w / self.screen_h)
        self.floor_state = FloorState()
        self.beatrice_node  = None
        self.beatrice_timer = 0.0

    def _build_room(self, floor_color=(0.22,0.18,0.28), wall_color=(0.28,0.22,0.35),
                    ceil_color=(0.15,0.12,0.20)):
        pv, pi = make_plane(ROOM_W, ROOM_D, 4)
        floor_mesh = ProceduralMesh("floor", pv, pi, base_color=floor_color,
                                    ka=0.3, kd=0.7, ks=0.1, shininess=8)
        floor_tex = ProceduralTexture(128, color_a=(55,45,70), color_b=(40,33,55))
        self.scene.add(SceneNode("floor", mesh=floor_mesh, texture=floor_tex))
        ceiling_mesh = ProceduralMesh("ceiling", pv, pi, base_color=ceil_color,
                                       ka=0.2, kd=0.6, ks=0.05, shininess=4)
        self.scene.add(SceneNode("ceiling", mesh=ceiling_mesh,
                                  position=(0, ROOM_H, 0), rotation=(180,0,0)))
        pv2, pi2 = make_plane(ROOM_W, ROOM_H, 1)
        for name, pos, rot in [
            ("wall_n", (0, ROOM_H/2, -ROOM_D/2), (90,0,0)),
            ("wall_s", (0, ROOM_H/2,  ROOM_D/2), (-90,180,0)),
            ("wall_w", (-ROOM_W/2, ROOM_H/2, 0), (0,0,-90)),
            ("wall_e", ( ROOM_W/2, ROOM_H/2, 0), (0,0, 90)),
        ]:
            wm = ProceduralMesh(name, pv2, pi2, base_color=wall_color,
                                ka=0.25, kd=0.75, ks=0.1, shininess=8)
            self.scene.add(SceneNode(name, mesh=wm, position=pos, rotation=rot))

        self.scene.light.orbit    = False
        self.scene.light.pos      = [0.0, ROOM_H - 1.5, 0.0]
        self.scene.light.intensity = 1.2
        self.scene.light.color    = np.array([0.8,0.6,1.0], dtype=np.float32)
        lv, li = make_sphere(0.18, 8, 8)
        lm = ProceduralMesh("light_ball", lv, li, base_color=(1.0,0.9,0.5),
                             ka=1.0, kd=0.0, ks=0.0, shininess=1)
        self.light_node = SceneNode("light_vis", mesh=lm,
                                    position=[0.0, ROOM_H-1.5, 0.0])
        self.scene.add(self.light_node)

    def _place_player(self, pos=(0,0,10)):
        self.player.world_pos  = list(pos)
        self.player.velocity   = [0,0,0]
        self.player.on_ground  = True
        self.player_node = _load_obj_model(
            os.path.join(_HERE,"assets","models","Subaru","Subaru.obj"),
            position=pos, rotation=(0, 180, 0), scale=(1.0, 1.0, 1.0)
        )
        if self.player_node is None:
            sv, si = make_sphere(0.45,12,12)
            pm = ProceduralMesh("subaru",sv,si,base_color=(0.2,0.35,0.6),
                                ka=0.3,kd=0.8,ks=0.4,shininess=24)
            self.player_node = SceneNode("subaru",mesh=pm,position=list(pos))
        self.scene.add(self.player_node)

        # Pre-carrega Beatrice oculta (evita lag ao invocar)
        beat_path = os.path.join(_HERE, "assets", "models", "Beatrice", "Beatrice.obj")
        bx, by, bz = pos[0] + 1.2, pos[1], pos[2] - 0.5
        bnode = _load_obj_model(beat_path, position=(bx, by, bz),
                                rotation=(0, 180, 0), scale=(1.0, 1.0, 1.0))
        if bnode is None:
            bv, bi = make_sphere(0.4, 10, 10)
            bm = ProceduralMesh("beatrice_fb", bv, bi, base_color=(0.7, 0.4, 0.9),
                                ka=0.5, kd=0.7, ks=0.6, shininess=48)
            bnode = SceneNode("beatrice_fb", mesh=bm, position=[bx, by + 0.5, bz])
        bnode.visible = False
        self.scene.add(bnode)
        self.beatrice_node  = bnode
        self.beatrice_timer = 0.0

    # ── Build floors ──────────────────────────────────────────────────────────

    def _build_floor(self, floor_idx, show_story=False):
        self._clear_scene()
        self.current_floor = floor_idx
        builders = {
            self.FLOOR_ENTRY:    self._build_floor_entry,
            self.FLOOR_PUZZLE:   self._build_floor_puzzle,
            self.FLOOR_AERIAL:   self._build_floor_aerial,
            self.FLOOR_RHYTHM:   self._build_floor_rhythm,
            self.FLOOR_GAUNTLET: self._build_floor_gauntlet,
            self.FLOOR_REST:     self._build_floor_rest,
            self.FLOOR_BOSS:     self._build_floor_boss,
        }
        builders[floor_idx]()
        if show_story and floor_idx == self.FLOOR_ENTRY:
            self._start_story()
        if floor_idx == self.FLOOR_REST:
            self.game_mode = "story"
            self.input.capture_mouse(False)
            self._start_story_part2()

    def _build_floor_entry(self):
        """Andar 0: Corredor escuro. Porta no fundo -> barreira + heartless -> escada."""
        self._build_room(floor_color=(0.12,0.10,0.18), wall_color=(0.18,0.14,0.26))
        self._place_player(pos=(0,0,12))

        # Porta no fundo do corredor (Norte, Z=-13)
        dv, di = make_cube(1.0)
        dm = make_box_mesh("door",3.0,4.0,0.3, color=(0.35,0.22,0.10), ka=0.2,kd=0.7,ks=0.3,shin=24)
        door_node = SceneNode("door", mesh=dm, position=(0, 4.0,-15), scale=(1,1,1))
        self.scene.add(door_node)
        self.floor_state.door_node = door_node

        # Barreira mágica (inicialmente invisível até abrir a porta)
        bv, bi = make_cube(1.0)
        bm = make_box_mesh("barrier",ROOM_W-2,ROOM_H-1,0.2, color=(0.2,0.1,0.8))
        barrier_node = SceneNode("barrier", mesh=bm, position=(0,ROOM_H/2-0.5,-9.0))
        barrier_node.visible = False
        self.scene.add(barrier_node)
        self.floor_state.barrier_node  = barrier_node
        self.floor_state.barrier_active = False

        # Escada no fundo (atrás da barreira)
        _build_stairs(self.scene, self.floor_state)
        self.floor_state.stair_locked = True

        # Decoração: obeliscos encostados nas paredes laterais (x=±8.5, fora da área de passagem)
        for sx in (-8.5, 8.5):
            _add_tower_deco(self.scene, self.floor_state, "obelisk",
                            position=(sx, 0.0, 0.0), scale=(1.5, 1.5, 1.5),
                            collision_radius=1.2)

        # Plataforma decorativa encostada na parede sul (atrás do spawn do player)
        _add_tower_deco(self.scene, self.floor_state, "platform",
                        position=(0.0, 0.0, 13.0), scale=(1.2, 1.2, 1.2),
                        collision_radius=1.5)

        self.hud.add_popup("Avance pelo corredor...", 3.0, (200,200,255))
        self.hud.add_popup("[E/Enter] perto da porta para abrir", 5.0, (180,200,255))

    def _build_floor_puzzle(self):
        """Andar 1: Puzzle de imagem fragmentada + escada trancada."""
        self._build_room(floor_color=(0.18,0.16,0.28), wall_color=(0.26,0.20,0.38))
        self._place_player(pos=(0,0,12))

        # Quadro (moldura) na parede norte, onde os fragmentos serão encaixados
        frame_w, frame_h = 4.0, 2.25   # proporção 16:9, igual à imagem original
        frame_cx, frame_cy = 0.0, ROOM_H/2 + 0.4
        fv, fi = make_plane(frame_w + 0.3, frame_h + 0.3, 1)
        frame_mesh = ProceduralMesh("puzzle_frame", fv, fi, base_color=(0.45,0.35,0.10),
                                     ka=0.6, kd=0.5, ks=0.6, shininess=32)
        self.scene.add(SceneNode("puzzle_frame", mesh=frame_mesh,
                                  position=(frame_cx, frame_cy, -8.92), rotation=(90,0,0)))
        # Fundo escuro do quadro (onde os fragmentos faltantes mostram "vazio")
        bv, bi = make_plane(frame_w, frame_h, 1)
        backing_mesh = ProceduralMesh("puzzle_backing", bv, bi, base_color=(0.05,0.05,0.08),
                                       ka=0.5, kd=0.3, ks=0.0, shininess=1)
        self.scene.add(SceneNode("puzzle_backing", mesh=backing_mesh,
                                  position=(frame_cx, frame_cy, -8.9), rotation=(90,0,0)))

        # 4 fragmentos da imagem (couple.png), espalhados pela sala
        piece_w, piece_h = frame_w/2, frame_h/2
        pv, pi = make_plane(piece_w, piece_h, 1)
        scatter_positions = [(-4,1.4,-2),(4,1.4,-2),(-4,1.4,2),(4,1.4,2)]
        # offsets de cada fragmento dentro do quadro: invertido verticalmente (V-flip da textura)
        # piece_0 (sup-esq da imagem) -> slot inferior-esq do quadro, etc.
        # piece_0 (sup-esq da imagem) -> slot sup-esq do quadro, etc.
        mural_offsets = [(-piece_w/2, piece_h/2), (piece_w/2, piece_h/2),
                         (-piece_w/2,-piece_h/2), (piece_w/2,-piece_h/2)]
        img_dir = os.path.join(_HERE, "assets", "images", "puzzle")

        self.puzzle_pieces = []
        for idx, spos in enumerate(scatter_positions):
            tex = Texture(os.path.join(img_dir, f"piece_{idx}.png"))
            pm = ProceduralMesh(f"puzzle_piece_{idx}", pv, pi, base_color=(1,1,1),
                                 ka=0.9, kd=0.6, ks=0.1, shininess=8)
            pnode = SceneNode(f"puzzle_piece_{idx}", mesh=pm, texture=tex,
                              position=list(spos), rotation=(90,0,0))
            self.scene.add(pnode)
            mural_pos = (frame_cx + mural_offsets[idx][0],
                          frame_cy + mural_offsets[idx][1], -8.9)
            self.puzzle_pieces.append({
                "node": pnode, "collected": False,
                "scatter_pos": spos, "mural_pos": mural_pos,
            })
        self.floor_state.puzzle_solved = False

        # Escada trancada (topo/norte)
        _build_stairs(self.scene, self.floor_state)
        # Portão trancado
        gm = make_box_mesh("gate",3.2,2.0,0.3, color=(0.5,0.4,0.1))
        gate_node = SceneNode("gate", mesh=gm, position=(0,1.0,-10.5))
        self.scene.add(gate_node)
        self.floor_state.barrier_node = gate_node

        self.hud.add_popup("Junte os fragmentos espalhados pela sala!", 3.0, (200,220,255))
        self.hud.add_popup("[Z] perto de cada fragmento para encaixá-lo no quadro", 4.0, (180,180,220))

    def _build_floor_aerial(self):
        """Andar 2: Heartless comuns no chão + heartless voadores."""
        self._build_room(floor_color=(0.16,0.14,0.22), wall_color=(0.24,0.20,0.34))
        self._place_player(pos=(0,0,12))

        # Heartless no chão
        for px, pz in [(-4,0),(4,0),(0,4)]:
            e, n = _spawn_heartless(self.scene, (px,0.5,pz), level=3)
            e.respawns_left = 0
            self.floor_state.enemies.append((e,n))

        # Heartless voadores (altura y=3)
        for px, pz in [(-3,2),(3,2),(0,-2)]:
            e, n = _spawn_heartless(self.scene, (px,3.0,pz), scale=(0.0125,0.0125,0.0125), level=3, flying=True)
            e.is_flying = True
            e.respawns_left = 0
            e.aggro_range  = 8.0
            self.floor_state.enemies.append((e,n))

        self.floor_state.stair_locked = True

        # Escada (visível, mas trancada até derrotar os heartless)
        _build_stairs(self.scene, self.floor_state)
        gm = make_box_mesh("gate_a",3.2,2.0,0.3, color=(0.5,0.3,0.1))
        gate_node = SceneNode("gate_a", mesh=gm, position=(0,1.0,-10.5))
        self.scene.add(gate_node)
        self.floor_state.barrier_node = gate_node

        self.hud.add_popup("Cuidado com os Heartless voadores!", 3.0, (255,200,100))
        self.hud.add_popup("[Espaço] pra pular e alcançá-los!", 4.0, (200,200,255))

    def _build_floor_rhythm(self):
        """Andar 3: Combate rítmico — ataque os Heartless."""
        self._build_room(floor_color=(0.10,0.18,0.20), wall_color=(0.16,0.26,0.30))
        self._place_player(pos=(0,0,12))

        # Heartless estacionários que servem de "alvo" do ritmo
        self.rhythm_enemies = []
        for px, pz in [(-3,-3),(0,-4),(3,-3)]:
            e, n = _spawn_heartless(self.scene, (px,0.5,pz), level=2, stationary=True)
            e.respawns_left = 0
            meshes = _collect_meshes(n)
            self.rhythm_enemies.append({"enemy": e, "node": n, "meshes": meshes,
                                         "orig_colors": [tuple(m.base_color) for m in meshes]})

        # Escada bloqueada
        _build_stairs(self.scene, self.floor_state)
        gm = make_box_mesh("gate_r",3.2,2.0,0.3, color=(0.1,0.4,0.5))
        gate_node = SceneNode("gate_r", mesh=gm, position=(0,1.0,-10.5))
        self.scene.add(gate_node)
        self.floor_state.barrier_node = gate_node
        self.floor_state.rhythm_done  = False

        # Cristais decorativos nas laterais da sala de ritmo (encostados nas paredes x=±8)
        for cx, cz in [(-8.0, -2.0), (-8.0, 2.0), (8.0, -2.0), (8.0, 2.0)]:
            _add_tower_deco(self.scene, self.floor_state, "crystal",
                            position=(cx, 0.0, cz), scale=(1.0, 1.0, 1.0),
                            collision_radius=0.9)

        self.hud.add_popup("Combate Rítmico! ENTER pra começar", 4.0, (100,255,200))
        self.hud.add_popup("[Z] quando chegar na barra 'amarela'!", 4.0, (200,255,220))

    def _build_floor_gauntlet(self):
        """Andar 4: Corredor final – todos os tipos de heartless."""
        self._build_room(floor_color=(0.20,0.08,0.08), wall_color=(0.28,0.12,0.12))
        self._place_player(pos=(0,0,12))

        # Onda 1: heartless simples
        wave1 = []
        for px, pz in [(-5,2),(5,2),(0,0),(-3,-2),(3,-2)]:
            e, n = _spawn_heartless(self.scene, (px,0.5,pz), level=4)
            e.respawns_left = 0
            wave1.append((e,n))
        # Onda 2: mistura chão + voadores
        wave2 = []
        for px, pz in [(-4,1),(4,1)]:
            e, n = _spawn_heartless(self.scene, (px,0.5,pz), level=4)
            e.respawns_left = 0
            wave2.append((e,n))
        for px, pz in [(0,2),(-3,-1),(3,-1)]:
            e, n = _spawn_heartless(self.scene, (px,3.0,pz), scale=(0.0125,0.0125,0.0125), level=4, flying=True)
            e.is_flying = True
            wave2.append((e,n))
            n.visible = False  # wave2 começa invisível

        self.floor_state.gauntlet_waves = [wave1, wave2]
        self.floor_state.gauntlet_idx   = 0
        self.floor_state.enemies        = list(wave1)
        self.floor_state.stair_locked   = True

        # Porta no final
        pm = make_box_mesh("portal_gate",3.0,4.0,0.3, color=(0.5,0.1,0.1))
        pn = SceneNode("portal_gate", mesh=pm, position=(0,2.0,-13.5))
        self.scene.add(pn)
        self.hud.add_popup("Corredor Final! Sobreviva!", 3.0, (255,100,100))

    def _build_floor_rest(self):
        """Andar 5: Sala de descanso – recupera HP/MP e salva."""
        self._build_room(floor_color=(0.15,0.22,0.18), wall_color=(0.20,0.30,0.24),
                         ceil_color=(0.12,0.20,0.16))
        self._place_player(pos=(0,0,8))
        # Altar de descanso
        am = make_box_mesh("altar_rest",4.0,0.5,2.0, color=(0.4,0.6,0.5))
        self.scene.add(SceneNode("altar_rest", mesh=am, position=(0,0.25,0)))
        # Chama de luz suave
        self.scene.light.intensity = 0.8
        self.scene.light.color = np.array([0.7,1.0,0.8], dtype=np.float32)

        # Recuperar player e salvar
        self.player.stats.hp = self.player.stats.max_hp
        self.player.stats.mp = self.player.stats.max_mp
        save_game(self.current_floor, self.player)

        self.floor_state.stair_locked = False

        self.hud.add_popup("Sala de Descanso", 3.0, (100,255,180))
        self.hud.add_popup("HP e MP recuperados! Jogo salvo.", 3.5, (180,255,200))
        self.hud.add_popup("Avance para enfrentar o boss final...", 4.5, (255,220,200))

        # Porta para o boss
        bm = make_box_mesh("boss_door",3.0,4.0,0.3, color=(0.6,0.2,0.6))
        self.scene.add(SceneNode("boss_door", mesh=bm, position=(0,2.0,-13.0)))

    def _build_floor_boss(self):
        """Andar 6: Marluxia + Emilia inconsciente."""
        self._build_room(floor_color=(0.20,0.05,0.20), wall_color=(0.28,0.08,0.28),
                         ceil_color=(0.15,0.04,0.18))
        self._place_player(pos=(0,0,10))
        self.floor_state.stair_locked = False
        self.scene.light.color = np.array([1.0,0.5,1.0], dtype=np.float32)
        self.scene.light.intensity = 1.5

        # Emilia inconsciente ao fundo
        emilia_node = _load_obj_model(
            os.path.join(_HERE,"assets","models","Emilia","emilia.obj"),
            position=(0,0.0,-12), rotation=(0,0,0), scale=(1.0,1.0,1.0)
        )
        if emilia_node:
            self.scene.add(emilia_node)
        self.floor_state.emilia_node = emilia_node

        # Marluxia (boss) – representado por heartless maior e roxo
        boss_hp = 400; boss_level = 8
        bv, bi = make_sphere(0.9,16,16)
        bm = ProceduralMesh("marluxia",bv,bi, base_color=(0.7,0.1,0.8),
                            ka=0.4,kd=0.7,ks=0.8,shininess=96)
        boss_node = SceneNode("marluxia", mesh=bm, position=(0,1.5,-8), rotation=(0,0,0), scale=(1.0,1.0,1.0))
        # Tenta carregar modelo do Marluxia se existir
        m_path = os.path.join(_HERE,"assets","models","Marluxia","Marluxia.obj")
        if os.path.exists(m_path):
            loaded = _load_obj_model(m_path, position=(0,0,-8), rotation=(90,0,0), scale=(0.014,0.014,0.014))
            if loaded:
                boss_node = loaded

        self.scene.add(boss_node)
        boss_enemy = Enemy("Marluxia", level=boss_level, world_pos=[0.0,0.0,-8.0])
        boss_enemy.stats.max_hp = boss_hp
        boss_enemy.stats.hp     = boss_hp
        boss_enemy.stats.atk    = 22
        boss_enemy.stats.defense = 8
        boss_enemy.aggro_range  = 12.0
        boss_enemy.attack_range = 2.2
        boss_enemy.respawns_left = 0
        boss_enemy.spawn_pos = [0.0,0.0,-8.0]
        self.floor_state.boss      = boss_enemy
        self.floor_state.boss_node = boss_node
        self.floor_state.enemies   = [(boss_enemy, boss_node)]

        # Torre ao fundo da sala do boss (encostada na parede norte, atrás de Emilia)
        _add_tower_deco(self.scene, self.floor_state, "tower",
                        position=(0.0, 0.0, -13.5), scale=(1.0, 1.0, 1.0),
                        collision_radius=1.8)

        # Cristais nas quinas da sala (encostados nas paredes)
        for cx, cz in [(-8.5, -5.0), (8.5, -5.0), (-8.5, 5.0), (8.5, 5.0)]:
            _add_tower_deco(self.scene, self.floor_state, "crystal",
                            position=(cx, 0.0, cz), scale=(1.4, 1.4, 1.4),
                            collision_radius=1.0)

        # Plataformas encostadas nas paredes laterais, no meio da sala
        for px in (-8.5, 8.5):
            _add_tower_deco(self.scene, self.floor_state, "platform",
                            position=(px, 0.0, 0.0), scale=(1.0, 1.0, 1.0),
                            collision_radius=1.2)

        self.hud.add_popup("BOSS: MARLUXIA", 3.0, (255,80,255))
        self.hud.add_popup("Salve Emilia!", 3.5, (255,200,255))

    # ── Story / Cutscene ─────────────────────────────────────────────────────

    def _start_story(self):
        lines = [
            "Enquanto Emilia tentava recuperar suas memórias perdidas...",
            "...dentro da própria mente, Natsuki Subaru",
            "começou a avançar na torre em que ela foi capturada.",
            "",
            "Mas Subaru não vai desistir de Emilia.",
            "",
            "— Pressione ENTER para começar —",
        ]
        self._show_story(lines, callback=self._story_done)

    def _start_story_part2(self):
        lines = [
            "Subaru enfrentou diversos puzzles e inimigos da escuridão",
            "que tentaram impedir seu avanço...",
            "",
            "Agora, no fim da torre, há aquele por trás de tudo: Marluxia.",
            "Que fez tudo isso para atrair Subaru até aqui...",
            "...querendo obter o seu Retorno pela Morte.",
            "",
            "— Pressione ENTER para continuar —",
        ]
        self._show_story(lines, callback=self._story_done)

    def _show_story(self, lines, callback=None):
        self.story_active   = True
        self.story_lines    = lines
        self.story_idx      = 0
        self.story_timer    = 0.0
        self.story_callback = callback
        self.game_mode      = "story"
        self.input.capture_mouse(False)

    def _story_done(self):
        self.story_active = False
        self.game_mode    = "explore"
        self.input.capture_mouse(True)

    def _show_ending(self):
        lines = [
            "Marluxia cai.",
            "",
            "Emilia abre os olhos devagar...",
            "",
            '"Subaru...?"',
            "",
            "Suas memórias voltaram.",
            "Ela lembra de tudo.",
            "",
            '"Eu me lembro de você, Subaru."',
            "",
            "Os dois ficam juntos na sala silenciosa da torre.",
            "",
            "— FIM —",
            "",
            "— Pressione ENTER para os créditos —",
        ]
        self._show_story(lines, callback=self._start_credits)

    def _start_credits(self):
        self.credits_active = True
        self.credits_timer  = 0.0
        self.credits_y      = self.screen_h + 20
        self.story_active   = False
        self.game_mode      = "credits"

    # ── Menu system ──────────────────────────────────────────────────────────

    def _push_title_menu(self):
        def start():
            self.menus.clear()
            self.player = Player("Natsuki Subaru")
            self._build_floor(self.FLOOR_ENTRY, show_story=True)
            self.game_mode = "story"
            self.input.capture_mouse(False)

        def continue_game():
            self.menus.clear()
            floor = load_game(self.player)
            if floor is None:
                self.hud.add_popup("Nenhum save encontrado!", 2.0, (255,100,100))
                self._push_title_menu(); return
            self._build_floor(floor)
            self.game_mode = "explore"
            self.input.capture_mouse(True)

        def quit_game():
            pygame.quit(); sys.exit(0)

        title_menu = Menu("Torre de Plêiades", [
            MenuItem("Nova Partida",  start),
            MenuItem("Continuar",     continue_game),
            MenuItem("Sair",          quit_game),
        ])
        self.menus.push(title_menu)
        self.game_mode = "menu"

    def _push_pause_menu(self):
        def resume():
            self.menus.pop(); self.game_mode = "explore"
            self.input.capture_mouse(True)
        def save():
            save_game(self.current_floor, self.player)
            self.hud.add_popup("Jogo salvo!", 2.0, (100,255,100))
            self.menus.pop(); self.game_mode = "explore"
            self.input.capture_mouse(True)
        def title():
            self.menus.clear(); self._push_title_menu()
            self.input.capture_mouse(False)
        self.menus.push(Menu("Pausado", [
            MenuItem("Continuar",      resume),
            MenuItem("Salvar",         save),
            MenuItem("Menu Principal", title),
        ]))
        self.game_mode = "menu"; self.input.capture_mouse(False)

    def _push_combat_menu(self):
        def attack():
            if self.combat:
                self.combat.player_attack(); self._check_combat_end()
        def use_potion():
            if self.combat:
                self.combat.player_use_item("health_potion_s", self.player.inventory)
                self._check_combat_end()
        def flee():
            if self.combat:
                self.combat.player_flee(); self._check_combat_end()
        self.menus.push(Menu("Combate", [
            MenuItem("Atacar",  attack),
            MenuItem("Poção",   use_potion),
            MenuItem("Fugir",   flee),
        ]))

    # ── Combat ───────────────────────────────────────────────────────────────

    def _check_combat_end(self):
        if self.combat and self.combat.is_over():
            result = self.combat.result
            self.menus.pop(); self.combat = None
            if result == "win":
                self.hud.add_popup("Vitória!", 2.5, (255,220,80))
                if self._combat_enemy_ref:
                    self._combat_enemy_ref[0].dead = True
                    self._combat_enemy_ref[1].visible = False
                    self._combat_enemy_ref = None
            elif result == "lose":
                self._trigger_death(); return
            self.game_mode = "explore"; self.input.capture_mouse(True)
            self._check_floor_progress()

    def _start_combat_with(self, enemy_tuple):
        e, node = enemy_tuple
        self._combat_enemy_ref = enemy_tuple
        self.combat = self.player.start_combat(e.stats)
        self.game_mode = "combat"; self.input.capture_mouse(False)
        self._push_combat_menu()

    def _trigger_death(self):
        self.game_mode = "death"; self.death_timer = 3.5
        self.input.capture_mouse(False)

    def _respawn(self):
        self.player.stats.hp = self.player.stats.max_hp
        self.player.stats.mp = self.player.stats.max_mp
        # Volta para o save mais recente
        saved_floor = load_game(self.player)
        floor = saved_floor if saved_floor is not None else self.current_floor
        self._build_floor(floor)
        self.game_mode = "explore"; self.input.capture_mouse(True)
        self.hud.add_popup("Return by Death...", 3.0, (180,80,80))

    # ── Floor progression ─────────────────────────────────────────────────────

    def _advance_floor(self):
        """Salva e vai para o próximo andar (com fade de transição)."""
        next_floor = self.current_floor + 1
        if next_floor > self.FLOOR_BOSS:
            return
        def _do_transition():
            save_game(next_floor, self.player)
            self._build_floor(next_floor)
            # NÃO setar game_mode aqui — _update_fade controla o retorno
        self._start_fade(_do_transition, duration=0.35)
        self.hud.add_popup("Subindo para o próximo andar...", 2.0, (200,255,200))

    def _start_fade(self, callback, duration=0.35):
        """Inicia um fade-to-black; executa callback no pico e faz fade-in."""
        self._fade_alpha    = 0.0
        self._fade_duration = duration
        self._fade_callback = callback
        self._fade_done     = False
        self._fading        = True    # flag independente de game_mode
        self._fade_in       = False
        self.game_mode      = "fade"
        self.input.capture_mouse(False)

    def _check_floor_progress(self):
        """Chamado após cada ação importante para ver se o andar foi completado."""
        fs = self.floor_state
        alive = [e for e,n in fs.enemies if not e.dead]

        if self.current_floor == self.FLOOR_ENTRY:
            # Libera escada quando todos os heartless estão mortos e a barreira estava ativa
            if fs.barrier_active and not alive:
                fs.stair_locked  = False
                fs.barrier_node.visible = False
                fs.barrier_active = False
                self.hud.add_popup("A barreira caiu! Suba as escadas.", 3.0, (200,255,200))

        elif self.current_floor == self.FLOOR_AERIAL:
            if not alive:
                fs.stair_locked = False
                if fs.barrier_node: fs.barrier_node.visible = False
                self.hud.add_popup("Todos derrotados! Suba as escadas.", 3.0, (200,255,200))

        elif self.current_floor == self.FLOOR_GAUNTLET:
            if not alive:
                gidx = fs.gauntlet_idx
                if gidx + 1 < len(fs.gauntlet_waves):
                    # Próxima onda
                    fs.gauntlet_idx += 1
                    next_wave = fs.gauntlet_waves[fs.gauntlet_idx]
                    fs.enemies = next_wave
                    for e, n in next_wave:
                        n.visible = True
                        e.dead = False
                    self.hud.add_popup("Próxima onda!", 2.0, (255,180,100))
                else:
                    fs.stair_locked = False
                    self.hud.add_popup("Corredor limpo! Avance pela porta.", 3.0, (200,255,200))

        elif self.current_floor == self.FLOOR_BOSS:
            if fs.boss and fs.boss.dead:
                self._on_boss_defeated()

    def _on_boss_defeated(self):
        self.game_mode = "story"
        self.input.capture_mouse(False)
        self._show_ending()

    # ── Player attack (real-time) ─────────────────────────────────────────────

    def _player_melee_attack(self):
        p = self.player
        if p.attack_cd > 0: return
        p.is_attacking = True; p.attack_timer = 0.4
        p.attack_cd = 0.6
        p.combo_count = (p.combo_count + 1) % 3; p.combo_timer = 0.8
        hit = False
        for e, node in self.floor_state.enemies:
            if e.dead: continue
            dx = e.world_pos[0] - p.world_pos[0]
            dy = e.world_pos[1] - p.world_pos[1]
            dz = e.world_pos[2] - p.world_pos[2]
            # heartless voador: precisa estar na altura certa
            fly = getattr(e, 'is_flying', False)
            reach_y = abs(dy) < 2.5 if fly else abs(dy) < 1.5
            dist_xz = math.sqrt(dx*dx + dz*dz)
            if dist_xz < 2.0 and reach_y:
                damage = max(1, p.stats.atk + random.randint(-2,2) - e.stats.defense)
                actual = e.stats.take_damage(damage)
                self.hud.add_popup(f"-{actual} HP", 1.0, (255,200,140))
                if not e.stats.is_alive():
                    e.dead = True; node.visible = False
                    xp = e.stats.level * 20 + random.randint(5,15)
                    leveled = p.stats.gain_xp(xp)
                    self.hud.add_popup(f"+{xp} XP", 1.5, (230,200,80))
                    if leveled: self.hud.add_popup("LEVEL UP!", 3.0, (255,230,50))
                    self._check_floor_progress()
                hit = True; break
        # Puzzle orbs
        if self.current_floor == self.FLOOR_PUZZLE:
            self._try_activate_orb()
        if not hit:
            self.hud.add_popup("Swoosh!", 0.6, (200,200,200))

    def _try_activate_orb(self):
        p = self.player
        for piece in self.puzzle_pieces:
            if piece["collected"]: continue
            spos = piece["scatter_pos"]
            dx = spos[0] - p.world_pos[0]
            dz = spos[2] - p.world_pos[2]
            if math.sqrt(dx*dx+dz*dz) < 2.0:
                piece["collected"] = True
                node = piece["node"]
                node.position = list(piece["mural_pos"])
                self.hud.add_popup("Fragmento encaixado!", 1.5, (200,200,100))
                self._check_puzzle()
                return

    def _check_puzzle(self):
        if all(p["collected"] for p in self.puzzle_pieces):
            self.floor_state.puzzle_solved = True
            self.floor_state.stair_locked = False
            self.floor_state.barrier_node.visible = False
            self.hud.add_popup("Quadro completo! Suba as escadas.", 3.0, (100,255,100))

    # ── Rhythm game ───────────────────────────────────────────────────────────

    def _start_rhythm_game(self):
        self.rhythm_active = True
        self.rhythm_score  = 0
        self.rhythm_total  = 8
        # Sequência de beats (tempo em segundos a partir do início)
        self.rhythm_beats  = [1.0,1.5,2.0,2.7,3.2,4.0,4.5,5.0]
        self.rhythm_timer  = 0.0
        self.rhythm_hit    = [False]*len(self.rhythm_beats)
        # cada beat tem um Heartless-alvo que vai "piscar"
        n_en = len(self.rhythm_enemies)
        self.rhythm_targets = [i % n_en for i in range(len(self.rhythm_beats))]
        self.rhythm_active_idx = -1
        # restaura HP/visibilidade dos heartless do ritmo
        for re_ in self.rhythm_enemies:
            re_["enemy"].dead = False
            re_["enemy"].stats.hp = re_["enemy"].stats.max_hp
            re_["node"].visible = True
            _restore_colors(re_)
        self.game_mode     = "rhythm"
        self.input.capture_mouse(False)
        self.hud.add_popup("Pressione Z quando chegar na barra amarela!", 2.0, (100,255,200))

    def _update_rhythm(self, dt):
        if not self.rhythm_active: return
        self.rhythm_timer += dt
        t = self.rhythm_timer

        # Aviso visual: acende o heartless quando o beat está CHEGANDO (janela larga)
        # O acerto real usa rhythm_window (janela estreita centrada no beat)
        active_idx = -1
        for i, bt in enumerate(self.rhythm_beats):
            if not self.rhythm_hit[i] and (bt - self.rhythm_warn_window) <= t <= (bt + self.rhythm_window):
                active_idx = self.rhythm_targets[i]
                break
        if active_idx != self.rhythm_active_idx:
            for re_ in self.rhythm_enemies:
                _restore_colors(re_)
            if active_idx >= 0:
                re_ = self.rhythm_enemies[active_idx]
                _flash_color(re_, (1.0, 0.95, 0.2))  # pisca amarelo = "ataque agora!"
            self.rhythm_active_idx = active_idx

        # Verifica se algum beat passou sem ser acertado -> jogador toma dano
        for i, bt in enumerate(self.rhythm_beats):
            if not self.rhythm_hit[i] and t > bt + self.rhythm_window + 0.2:
                self.rhythm_hit[i] = True  # marcado como miss
                self._rhythm_player_damage()
        if not self.rhythm_active:
            return

        if t > self.rhythm_beats[-1] + 1.0:
            # Jogo acabou
            self.rhythm_active = False
            self.rhythm_active_idx = -1
            for re_ in self.rhythm_enemies:
                _restore_colors(re_)
            pct = self.rhythm_score / self.rhythm_total
            if pct >= 0.5:
                self.floor_state.rhythm_done = True
                self.floor_state.stair_locked = False
                self.floor_state.barrier_node.visible = False
                # Mata todos os heartless que ainda estiverem vivos
                for re_ in self.rhythm_enemies:
                    re_["enemy"].dead = True
                    re_["node"].visible = False
                self.hud.add_popup(f"Ritmo! {self.rhythm_score}/{self.rhythm_total} – Suba!", 3.0, (100,255,200))
            else:
                self.hud.add_popup(f"Muito fora do ritmo! ({self.rhythm_score}/{self.rhythm_total}) Tente de novo.", 3.0, (255,100,100))
            self.game_mode = "explore"
            self.input.capture_mouse(True)

    def _rhythm_player_damage(self, amount=8):
        p = self.player
        p.stats.hp = max(0, p.stats.hp - amount)
        self.hud.add_popup(f"-{amount} HP", 1.0, (255,100,100))
        if p.stats.hp <= 0:
            self.rhythm_active = False
            self.rhythm_active_idx = -1
            for re_ in self.rhythm_enemies:
                _restore_colors(re_)
            self._trigger_death()

    def _rhythm_press(self):
        if not self.rhythm_active: return
        t = self.rhythm_timer
        for i, bt in enumerate(self.rhythm_beats):
            if not self.rhythm_hit[i] and abs(t - bt) <= self.rhythm_window:
                self.rhythm_hit[i] = True
                self.rhythm_score  += 1
                # acerta o heartless que estava piscando
                target = self.rhythm_enemies[self.rhythm_targets[i]]
                e = target["enemy"]
                if not e.dead:
                    damage = max(1, self.player.stats.atk + random.randint(-2,2) - e.stats.defense)
                    e.stats.take_damage(damage)
                    self.hud.add_popup(f"-{damage} HP!", 1.0, (255,200,140))
                    if not e.stats.is_alive():
                        e.dead = True
                        target["node"].visible = False
                self.hud.add_popup("BEAT!", 0.5, (50,255,180))
                return
        self.hud.add_popup("Miss...", 0.5, (255,80,80))
        self._rhythm_player_damage(amount=4)

    # ── Input ─────────────────────────────────────────────────────────────────

    def _handle_global_input(self, dt):
        if self.input.key_pressed("f1"):
            self.wireframe = not self.wireframe

        if self.game_mode == "story":
            if self.input.key_pressed("return") or self.input.key_pressed("space"):
                self.story_idx += 1
                if self.story_idx >= len(self.story_lines):
                    if self.story_callback:
                        cb = self.story_callback
                        self.story_callback = None
                        cb()
            return

        if self.game_mode == "credits":
            if self.input.key_pressed("return") or self.input.key_pressed("escape"):
                self.credits_active = False
                self.game_mode = "menu"
                self._push_title_menu()
            return

        if self.game_mode == "rhythm":
            if self.input.key_pressed("z"):
                self._rhythm_press()
            if self.input.key_pressed("escape"):
                self.rhythm_active = False
                self.game_mode = "explore"
                self.input.capture_mouse(True)
            return

        if self.game_mode == "explore":
            dx, dy = self.input.mouse_delta
            if dx or dy: self.camera.process_mouse(dx, dy)
            if self.input.key_pressed("escape"):
                self._push_pause_menu()
            if self.input.key_pressed("z"):
                self._player_melee_attack()
            if self.input.key_pressed("x"):
                self.hud.spell_menu_open = not self.hud.spell_menu_open
                self.hud.item_menu_open = self.hud.skill_menu_open = False
            if self.input.key_pressed("c"):
                self.hud.item_menu_open = not self.hud.item_menu_open
                self.hud.spell_menu_open = self.hud.skill_menu_open = False
                self.hud.inventory_items = self.player.inventory.list_consumables()
            if self.input.key_pressed("v"):
                self.hud.skill_menu_open = not self.hud.skill_menu_open
                self.hud.spell_menu_open = self.hud.item_menu_open = False
            for n in range(1,5):
                if self.input.key_pressed(str(n)):
                    self._handle_submenu_number(n)
            # Interagir com porta (andar 0)
            if self.input.key_pressed("e") or self.input.key_pressed("return"):
                self._interact()
            # Ritmo: ENTER inicia
            if self.current_floor == self.FLOOR_RHYTHM and not self.floor_state.rhythm_done:
                if self.input.key_pressed("return"):
                    self._start_rhythm_game()

        elif self.game_mode in ("menu", "combat"):
            self.menus.handle_input(self.input)

        elif self.game_mode == "death":
            pass

    def _handle_submenu_number(self, n):
        idx = n - 1
        if self.hud.spell_menu_open and idx < len(SPELL_LIST):
            self._cast_spell(SPELL_LIST[idx])
        elif self.hud.item_menu_open:
            items = self.player.inventory.list_consumables()
            if idx < len(items):
                self._use_item_explore(items[idx][0].id)

    def _interact(self):
        """Interagir com objetos próximos (porta, escada, etc.)."""
        p = self.player
        pz = p.world_pos[2]; px = p.world_pos[0]

        if self.current_floor == self.FLOOR_ENTRY:
            # Subir escada se desbloqueada (prioridade máxima)
            if pz < -10.0 and not self.floor_state.stair_locked:
                self._advance_floor()
                return

            # Abrir porta / ativar barreira + heartless (só se barreira ainda não foi ativada)
            if pz < -10.0 and abs(px) < 3.0 and not self.floor_state.barrier_active \
                    and self.floor_state.stair_locked:
                self.floor_state.barrier_active = True
                self.floor_state.barrier_node.visible = True
                # Spawn heartless básicos
                for ep in [(-3,0.5,-5),(3,0.5,-5),(0,0.5,-3)]:
                    e, n = _spawn_heartless(self.scene, ep, level=2)
                    e.respawns_left = 0
                    self.floor_state.enemies.append((e,n))
                self.hud.add_popup("TUTORIAL DE COMBATE!", 2.5, (255,200,80))
                self.hud.add_popup("[Z] para atacar os Heartless!", 3.5, (200,200,255))
                return

        elif self.current_floor in (self.FLOOR_PUZZLE, self.FLOOR_AERIAL,
                                     self.FLOOR_RHYTHM, self.FLOOR_GAUNTLET):
            # Subir escada se desbloqueada
            if pz < -10.0 and not self.floor_state.stair_locked:
                self._advance_floor()

        elif self.current_floor == self.FLOOR_REST:
            # Porta para o boss
            if pz < -11.0 and abs(px) < 3.0:
                self._advance_floor()

    # ── Spells / Items ────────────────────────────────────────────────────────

    def _cast_spell(self, spell_id):
        sp = SPELL_DB.get(spell_id)
        if not sp: return
        if spell_id == "invisible_providence":
            if self.player.stats.hp <= 40:
                self.hud.add_popup("Vida insuficiente!", 1.5, (255,100,100)); return
            self.player.stats.hp = max(1, self.player.stats.hp - 40)
        else:
            if not self.player.stats.use_mp(sp.mp_cost):
                self.hud.add_popup("MP insuficiente!", 1.5, (100,100,255)); return
        if spell_id == "emt":
            self.player.stats.shield_time = 10.0
            self._show_beatrice()
            self.hud.add_popup("EMT ativado! Protegido por 10s", 2.0, (80,220,255)); return
        nearest = None; nearest_dist = 999.0
        for e, node in self.floor_state.enemies:
            if e.dead: continue
            dx=e.world_pos[0]-self.player.world_pos[0]; dz=e.world_pos[2]-self.player.world_pos[2]
            dist=math.sqrt(dx*dx+dz*dz)
            if dist < 8.0 and dist < nearest_dist:
                nearest=(e,node,dist); nearest_dist=dist
        if not nearest:
            self.hud.add_popup(f"{sp.name} – sem alvo próximo", 1.2, (140,140,255)); return
        e, node, _ = nearest
        if spell_id == "shamac":
            e.blind_time = 10.0; e.aggro = False
            self._show_beatrice()
            self.hud.add_popup(f"Shamac! {e.stats.name} perdeu sua pista.", 2.2, (180,120,255)); return
        dmg = e.stats.take_damage(sp.damage)
        if spell_id == "minya":
            self._show_beatrice()
        self.hud.add_popup(f"{sp.name}! -{dmg} HP", 2.0, (180,120,255))
        if not e.stats.is_alive():
            e.dead = True; node.visible = False
            xp=e.stats.level*20+random.randint(5,15)
            leveled=self.player.stats.gain_xp(xp)
            self.hud.add_popup(f"+{xp} XP", 2.0, (230,200,80))
            if leveled: self.hud.add_popup("LEVEL UP!", 3.0, (255,230,50))
            self._check_floor_progress()

    def _use_item_explore(self, item_id):
        item = ITEM_DB.get(item_id)
        if not item: return
        if not self.player.inventory.remove(item_id, 1):
            self.hud.add_popup("Item não encontrado!", 1.5, (255,100,100)); return
        if hasattr(item,"heal_hp") and item.heal_hp > 0:
            self.player.stats.hp = min(self.player.stats.max_hp, self.player.stats.hp+item.heal_hp)
        if hasattr(item,"heal_mp") and item.heal_mp > 0:
            self.player.stats.mp = min(self.player.stats.max_mp, self.player.stats.mp+item.heal_mp)
        self.hud.add_popup(f"Usou {item.name}", 1.5, (120,255,120))

    def _show_beatrice(self, duration=2.0):
        """Torna a Beatrice visível ao lado do Subaru por `duration` segundos."""
        if self.beatrice_node is None:
            return  # modelo não carregou nem como fallback
        p = self.player.world_pos
        self.beatrice_node.position = [p[0] + 1.2, p[1], p[2] - 0.5]
        self.beatrice_node.rotation[1] = self.player_node.rotation[1]
        self.beatrice_node.visible = True
        self.beatrice_timer = duration

    # ── Update ────────────────────────────────────────────────────────────────

    def _update_game(self, dt):
        if self.game_mode == "death":
            self.death_timer -= dt
            if self.death_timer <= 0.0:
                self._respawn(); return
        if self.game_mode == "credits":
            self.credits_y   -= 40 * dt
            self.credits_timer += dt
            return
        if getattr(self, '_fading', False):
            self._update_fade(dt)
            if self.game_mode == "fade":
                return   # ainda no fade — não atualiza o resto
        if self.game_mode == "rhythm":
            self._update_rhythm(dt)
        if self.game_mode not in ("explore","rhythm"): return
        self._update_player(dt)
        self._update_enemies(dt)
        self.hud.update(dt)
        # Beatrice — segue o Subaru e some quando o timer zera
        if self.beatrice_node is not None and self.beatrice_timer > 0.0:
            self.beatrice_timer -= dt
            p = self.player.world_pos
            self.beatrice_node.position = [p[0] + 1.2, p[1], p[2] - 0.5]
            self.beatrice_node.rotation[1] = self.player_node.rotation[1]
            if self.beatrice_timer <= 0.0:
                self.beatrice_node.visible = False
                # NÃO zera a referência — node fica na cena, só invisível

    def _update_fade(self, dt):
        half = self._fade_duration
        if not self._fade_in:
            # Fase 1: escurece até preto
            self._fade_alpha += dt / half
            if self._fade_alpha >= 1.0:
                self._fade_alpha = 1.0
                self._fade_in    = True
                # Agenda o build para o PRÓXIMO frame (tela já está preta)
                self._fade_build_pending = True
        elif getattr(self, '_fade_build_pending', False):
            # Frame seguinte ao pico: executa cleanup + build com tela preta
            self._fade_build_pending = False
            if self._fade_callback and not self._fade_done:
                self._fade_done = True
                self._post_fade_mode = "explore"   # default seguro antes do callback
                self._fade_callback()
                # Se o builder mudou game_mode explicitamente (ex: FLOOR_REST -> "story"),
                # captura isso; caso contrário mantém "explore"
                if self.game_mode not in ("fade",):
                    self._post_fade_mode = self.game_mode
                self.game_mode = "fade"
        else:
            # Fase 2: clareia de volta
            self._fade_alpha -= dt / half
            if self._fade_alpha <= 0.0:
                self._fade_alpha = 0.0
                self._fading     = False
                post = getattr(self, '_post_fade_mode', 'explore')
                self.game_mode = post
                if post == "explore":
                    self.input.capture_mouse(True)

    def _stair_ground_y(self, px: float, pz: float) -> float:
        """Altura do chão nos degraus; fora da faixa da escada retorna 0."""
        if not self.floor_state.has_stairs or abs(px) > STAIR_WIDTH / 2.0:
            return 0.0
        ground = 0.0
        for i in range(STAIR_COUNT):
            b = _stair_step_bounds(i)
            if b["z0"] <= pz <= b["z1"]:
                ground = max(ground, b["y1"])
        return ground

    def _resolve_stair_collisions(self, p):
        """Impede atravessar os degraus pelas laterais/frente (volume sólido)."""
        if not self.floor_state.has_stairs:
            return
        px, py, pz = p.world_pos
        pr = 0.5
        for i in range(STAIR_COUNT):
            b = _stair_step_bounds(i)
            if py >= b["y1"] - 0.08:
                continue
            cx = max(b["x0"], min(px, b["x1"]))
            cz = max(b["z0"], min(pz, b["z1"]))
            dx = px - cx
            dz = pz - cz
            dist2 = dx * dx + dz * dz
            if dist2 >= pr * pr or dist2 < 1e-8:
                continue
            dist = math.sqrt(dist2)
            push = (pr - dist) / dist
            px += dx * push
            pz += dz * push
        p.world_pos[0] = px
        p.world_pos[2] = pz

    def _update_player(self, dt):
        p = self.player
        keys = self.input.held_keys
        if p.attack_cd > 0:    p.attack_cd   -= dt
        if p.attack_timer > 0: p.attack_timer -= dt
        else:                  p.is_attacking  = False
        if p.combo_timer > 0:  p.combo_timer  -= dt
        else:                  p.combo_count   = 0
        if p.invincible > 0:   p.invincible   -= dt
        if p.stats.shield_time > 0: p.stats.shield_time -= dt

        move_x, move_z = 0.0, 0.0
        fwd = self.camera.flat_forward; rgt = self.camera.flat_right
        if not p.is_rolling:
            if "w" in keys: move_x+=fwd[0]; move_z+=fwd[2]
            if "s" in keys: move_x-=fwd[0]; move_z-=fwd[2]
            if "a" in keys: move_x-=rgt[0]; move_z-=rgt[2]
            if "d" in keys: move_x+=rgt[0]; move_z+=rgt[2]
            mag = math.sqrt(move_x*move_x+move_z*move_z)
            if mag > 0:
                move_x/=mag; move_z/=mag
                p.facing_deg = math.degrees(math.atan2(move_x,move_z))
            p.velocity[0] = move_x*p.WALK_SPEED
            p.velocity[2] = move_z*p.WALK_SPEED
            if "space" in keys and p.on_ground:
                p.velocity[1] = p.JUMP_FORCE; p.on_ground = False
            if self.input.key_pressed("lshift") and p.on_ground and mag > 0:
                p.is_rolling=True; p.roll_timer=p.ROLL_TIME
                p.roll_dir=[move_x,move_z]; p.invincible=p.ROLL_TIME
        else:
            p.roll_timer -= dt
            p.velocity[0] = p.roll_dir[0]*p.ROLL_SPEED
            p.velocity[2] = p.roll_dir[1]*p.ROLL_SPEED
            if p.roll_timer <= 0.0:
                p.is_rolling=False; p.velocity[0]=p.velocity[2]=0.0
        if not p.on_ground:
            p.velocity[1] += p.GRAVITY*dt

        p.world_pos[0] += p.velocity[0] * dt
        p.world_pos[2] += p.velocity[2] * dt

        self._resolve_stair_collisions(p)

        ground_y = self._stair_ground_y(p.world_pos[0], p.world_pos[2])
        if p.world_pos[1] > ground_y + 0.02:
            p.on_ground = False

        if not p.on_ground:
            p.velocity[1] += p.GRAVITY * dt

        p.world_pos[1] += p.velocity[1] * dt

        if p.world_pos[1] < ground_y:
            p.world_pos[1] = ground_y
            p.velocity[1] = 0.0
            p.on_ground = True
            
        hw=ROOM_W/2-0.6; hd=ROOM_D/2-0.6
        p.world_pos[0]=max(-hw,min(hw,p.world_pos[0]))
        # Impedir de passar pela parede norte se escada está trancada
        north_limit = -hd
        if self.floor_state.stair_locked and (
            self.current_floor != self.FLOOR_ENTRY or self.floor_state.barrier_active):
            north_limit = -9.5   # bate na barreira/portão
        p.world_pos[2]=max(north_limit,min(hd,p.world_pos[2]))

        # Colisão push-out com obstáculos decorativos
        for (ox, oz, radius) in self.floor_state.obstacles:
            dx = p.world_pos[0] - ox
            dz = p.world_pos[2] - oz
            dist2 = dx*dx + dz*dz
            min_dist = radius + 0.5   # 0.5 = raio do player
            if dist2 < min_dist * min_dist and dist2 > 0.0001:
                dist = math.sqrt(dist2)
                push = (min_dist - dist) / dist
                p.world_pos[0] += dx * push
                p.world_pos[2] += dz * push

        self.player_node.position=[p.world_pos[0],p.world_pos[1]+0.5,p.world_pos[2]]
        self.player_node.rotation[1]=p.facing_deg
        self.camera.update_third_person(p.world_pos)

        PLAYER_RADIUS = 0.5
        ENEMY_RADIUS = 0.6

        for e, node in self.floor_state.enemies:
            if e.dead:
                continue

            dx = self.player.world_pos[0] - e.world_pos[0]
            dz = self.player.world_pos[2] - e.world_pos[2]

            dist2 = dx*dx + dz*dz
            min_dist = PLAYER_RADIUS + ENEMY_RADIUS

            if dist2 < min_dist * min_dist and dist2 > 0.0001:
                dist = math.sqrt(dist2)

                push = (min_dist - dist) / dist

                self.player.world_pos[0] += dx * push
                self.player.world_pos[2] += dz * push

    def _update_enemies(self, dt):
        for e, node in self.floor_state.enemies:
            if e.dead: continue
            e.update(self.player.world_pos, dt)
            node.position = list(e.world_pos)
            if not getattr(e,'stationary',False):
                node.rotation[1] = e.facing_deg
            if e.aggro and self.player.invincible <= 0.0:
                dx=e.world_pos[0]-self.player.world_pos[0]
                dz=e.world_pos[2]-self.player.world_pos[2]
                if math.sqrt(dx*dx+dz*dz) < e.attack_range:
                    dmg = e.try_attack(self.player.stats)
                    if dmg > 0:
                        self.player.invincible = 0.5
                        self.hud.add_popup(f"-{dmg} HP", 1.2, (255,80,80))
                        if self.player.is_dead:
                            self._trigger_death()
        ENEMY_RADIUS = 0.6

        enemies = [e for e, node in self.floor_state.enemies if not e.dead]

        for i in range(len(enemies)):
            for j in range(i + 1, len(enemies)):

                e1 = enemies[i]
                e2 = enemies[j]

                dx = e1.world_pos[0] - e2.world_pos[0]
                dz = e1.world_pos[2] - e2.world_pos[2]

                dist2 = dx*dx + dz*dz
                min_dist = ENEMY_RADIUS * 2

                if dist2 < min_dist * min_dist and dist2 > 0.0001:

                    dist = math.sqrt(dist2)

                    push = (min_dist - dist) / dist * 0.5

                    e1.world_pos[0] += dx * push
                    e1.world_pos[2] += dz * push

                    e2.world_pos[0] -= dx * push
                    e2.world_pos[2] -= dz * push

    # ── Render ────────────────────────────────────────────────────────────────

    def _render(self):
        glPolygonMode(GL_FRONT_AND_BACK, GL_LINE if self.wireframe else GL_FILL)
        glClear(GL_COLOR_BUFFER_BIT|GL_DEPTH_BUFFER_BIT)
        self.scene.draw(self.phong_shader, self.camera)
        glDisable(GL_DEPTH_TEST)
        self._draw_hud()
        # Overlay de fade — desenhado por cima de tudo, em qualquer modo
        if getattr(self, '_fade_alpha', 0.0) > 0.0:
            self.hud.draw_rect(0, 0, self.screen_w, self.screen_h,
                               (0.0, 0.0, 0.0), min(1.0, self._fade_alpha))
        glEnable(GL_DEPTH_TEST)
        pygame.display.flip()

    def _draw_hud(self):
        h=self.hud; sw=self.screen_w; sh=self.screen_h

        if self.game_mode == "story":
            h.draw_rect(0, 0, sw, sh, (0.0,0.0,0.05))
            # Mostra apenas a linha atual (uma por vez)
            if self.story_idx < len(self.story_lines):
                line = self.story_lines[self.story_idx]
                color = (255,255,255) if line else (100,100,100)
                h.draw_text(line, sw//2, sh//2, 22, color, center=True)
            h.draw_text("[ENTER] próximo", sw//2, sh-40, 14, (150,150,150), center=True)
            return

        if self.game_mode == "credits":
            h.draw_rect(0,0,sw,sh,(0.0,0.0,0.0))
            credits = [
                "Torre de Plêiades",
                "Re:Zero – Uma nova jornada",
                "",
                "Design & Desenvolvimento",
                "Vesuvio",
                "Gabriel Luiz",
                "",
                "Baseado em Re:Zero kara Hajimeru Isekai Seikatsu",
                "por Tappei Nagatsuki",
                "",
                "Kingdom Hearts – Heartless",
                "© Square Enix / Disney",
                "",
                "Personagens: Subaru, Emilia, Marluxia",
                "",
                "Obrigado por jogar!",
                "",
                "[ENTER] Menu Principal",
            ]
            base = int(self.credits_y)
            for i, line in enumerate(credits):
                y = base + i*40
                if -40 < y < sh+40:
                    h.draw_text(line, sw//2, y, 22, (220,210,255), center=True)
            return

        if self.game_mode == "death":
            h.draw_death_screen(); return

        if self.game_mode != "menu":
            h.draw_main_hud(self.player, self.game_mode)
        else:
            self._draw_menu_background(h)

        if self.game_mode in ("menu","combat"):
            pw, ph = 340, 240
            px=sw//2-pw//2; py=sh//2-ph//2
            h.draw_bar(px-12,py-12,pw+24,ph+24,1.0,(0.04,0.04,0.10),(0.04,0.04,0.10))
            self.menus.draw(h, px, py)

        if self.combat:
            msgs = self.combat.log.recent(5)
            h.draw_combat_log(msgs)

        if self.game_mode == "rhythm":
            self._draw_rhythm_hud(h)

        if self.game_mode == "explore":
            floor_names = {
                self.FLOOR_ENTRY:   "Corredor de Entrada",
                self.FLOOR_PUZZLE:  "1º Andar – Puzzle",
                self.FLOOR_AERIAL:  "2º Andar – Combate Aéreo",
                self.FLOOR_RHYTHM:  "3º Andar – Ritmo",
                self.FLOOR_GAUNTLET:"Corredor Final",
                self.FLOOR_REST:    "Sala de Descanso",
                self.FLOOR_BOSS:    "Sala do Boss – Marluxia",
            }
            fname = floor_names.get(self.current_floor, "")
            h.draw_text(fname, sw//2, 12, 16, (200,180,255), center=True)

            hint = "[WASD] Mover  [Espaço] Pular  [Z] Atacar  [E/Enter] Interagir com porta  [ESC] Pausar"
            if self.current_floor == self.FLOOR_PUZZLE:
                hint = "[WASD] Mover  [Z] Ativar orbe (perto)  [X] Magia  [ESC] Pausar"
            if self.current_floor == self.FLOOR_RHYTHM:
                hint = "[Enter] Iniciar Ritmo  [Z] Bater no ritmo  [ESC] Pausar"
            submenu_open = self.hud.spell_menu_open or self.hud.item_menu_open or self.hud.skill_menu_open
            hint_y = sh - 92 - (204 if submenu_open else 0)
            h.draw_text(hint, 10, hint_y, 11, (120,120,120))

            # Indicador de status da escada/passagem
            if self.current_floor in (self.FLOOR_ENTRY, self.FLOOR_PUZZLE,
                                       self.FLOOR_AERIAL, self.FLOOR_RHYTHM,
                                       self.FLOOR_GAUNTLET):
                if self.floor_state.stair_locked:
                    status_txt, status_color = "Passagem: TRANCADA", (255,120,120)
                else:
                    status_txt, status_color = "Passagem: LIBERADA — [E/Enter] para subir", (120,255,140)
                h.draw_text(status_txt, sw//2, 36, 14, status_color, center=True)

    def _draw_rhythm_hud(self, h):
        sw, sh = self.screen_w, self.screen_h
        # Faixa de ritmo
        bar_x, bar_y, bar_w, bar_h = sw//2 - 300, sh - 140, 600, 30
        h.draw_rect(bar_x, bar_y, bar_w, bar_h, (0.05,0.12,0.12))
        # Marcador de tempo atual
        if self.rhythm_beats:
            t = self.rhythm_timer
            total_t = self.rhythm_beats[-1] + 1.0
            cx = bar_x + int((t / total_t) * bar_w)
            h.draw_rect(cx-3, bar_y, 6, bar_h, (0.2,1.0,0.6))
        # Beats
        total_t = (self.rhythm_beats[-1] + 1.0) if self.rhythm_beats else 1.0
        for i, bt in enumerate(self.rhythm_beats):
            bx = bar_x + int((bt / total_t) * bar_w)
            color = (0.0,0.6,0.0) if self.rhythm_hit[i] else (1.0,0.6,0.0)
            h.draw_rect(bx-4, bar_y, 8, bar_h, color)
        h.draw_text(f"Score: {self.rhythm_score}/{self.rhythm_total}", sw//2, sh-170, 18, (100,255,200), center=True)
        h.draw_text("[Z] no beat!", sw//2, sh-100, 16, (200,255,220), center=True)

    def _draw_menu_background(self, hud):
        sw, sh = self.screen_w, self.screen_h
        hud.draw_rect(0, 0, sw, sh, (0.03,0.03,0.08))
        hud.draw_rect(0, int(sh*0.15), sw, int(sh*0.1), (0.06,0.04,0.12))
        hud.draw_rect(0, int(sh*0.25), sw, int(sh*0.12), (0.08,0.06,0.18))
        hud.draw_text("Torre de Plêiades", sw//2, int(sh*0.10), 36, (235,220,255), bold=True, center=True)
        hud.draw_text("Re:Zero – uma nova jornada", sw//2, int(sh*0.175), 18, (200,180,220), center=True)
        rnd = 1
        for i in range(80):
            rnd=(rnd*1664525+1013904223)&0xFFFFFFFF; sx=(rnd>>8)%sw
            rnd=(rnd*1664525+1013904223)&0xFFFFFFFF; sy=(rnd>>8)%int(sh*0.55)
            hud.draw_text(".", sx, sy, 10, (220,220,255))

    def on_resize(self, w, h):
        self.screen_w=w; self.screen_h=h
        glViewport(0,0,w,h)
        self.scene.set_aspect(w/h)
        self.hud.resize(w,h)

    # ── Main loop ─────────────────────────────────────────────────────────────

    def run(self):
        while True:
            dt = min(self.clock.tick(60)/1000.0, 0.05)
            
            # 1. Atualiza os inputs recolhendo todos os eventos da fila
            self.input.update()
            if self.input.should_quit: 
                break
            
            # 2. Verifica se a janela foi redimensionada através do InputManager
            if self.input.resize_event:
                w, h = self.input.resize_event
                self.on_resize(w, h)
                
            # 3. Atualiza e renderiza o frame do jogo
            self._handle_global_input(dt)
            self._update_game(dt)
            self.scene.update(dt)
            self._render()
            
        pygame.quit()

if __name__ == "__main__":
    game = Game()
    game.input.__class__ = InputManager
    game.input.mouse_clicked = False
    game.input.mouse_pos = (0,0)
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
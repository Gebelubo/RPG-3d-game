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

import os, sys, math, random, json
import pygame
from pygame.locals import DOUBLEBUF, OPENGL, RESIZABLE
from OpenGL.GL import (
    glViewport, glEnable, glDisable, glClearColor, glClear,
    glDepthFunc, glPolygonMode,
    GL_DEPTH_TEST, GL_LEQUAL, GL_COLOR_BUFFER_BIT, GL_DEPTH_BUFFER_BIT,
    GL_FRONT_AND_BACK, GL_FILL, GL_LINE,
)
import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

from engine.math3d        import vec3
from engine.shader        import ShaderProgram
from engine.mesh          import Mesh, ProceduralMesh, make_cube, make_plane, make_sphere
from engine.texture       import Texture, ProceduralTexture
from engine.obj_loader    import OBJLoader
from engine.camera        import Camera
from engine.scene         import Scene, SceneNode, PointLight
from engine.gltf_loader   import GLTFLoader
from engine.skinned_mesh  import SkinnedMesh
from engine.animation     import AnimationController
from engine.input_manager import InputManager
from engine.math3d        import mat3_normal_matrix
from game.rpg_data        import Player, Stats, Enemy, SPELL_DB, SPELL_LIST, ITEM_DB
from hud                  import HUD
from menu                 import Menu, MenuItem, MenuManager

SCREEN_W, SCREEN_H = 1280, 720
TITLE      = "Torre de Plêiades – Re:Zero RPG"
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

BEATRICE_Y_OFFSET = 0.5  # quanto a Beatrice fica acima do chão (ajuste de altura do modelo)
SUBARU_Y_OFFSET    = 0.0  # quanto o modelo do Subaru fica acima do world_pos (chão lógico)

# ── Helpers ───────────────────────────────────────────────────────────────────

def make_box_mesh(name, w, h, d, color, ka=0.2, kd=0.8, ks=0.2, shin=16):
    verts, idxs = make_cube(1.0)
    verts = verts.copy()
    verts[:, 0] *= w / 2.0
    verts[:, 1] *= h / 2.0
    verts[:, 2] *= d / 2.0
    return ProceduralMesh(name, verts, idxs, base_color=color, ka=ka, kd=kd, ks=ks, shininess=shin)


def _stair_step_bounds(i):
    y_bot = i * STAIR_STEP_H
    y_top = (i + 1) * STAIR_STEP_H
    zc    = STAIR_Z_START - i * STAIR_Z_SPACING
    hw    = STAIR_WIDTH / 2.0
    hd    = STAIR_STEP_D / 2.0
    return {"x0": -hw, "x1": hw, "z0": zc - hd, "z1": zc + hd, "y0": y_bot, "y1": y_top}


def _build_stairs(scene, floor_state):
    """Escada sólida estilo castelo."""

    for i in range(STAIR_COUNT):

        # altura acumulada do degrau
        height = (i + 1) * STAIR_STEP_H

        z_center = STAIR_Z_START - i * STAIR_Z_SPACING

        sm = make_box_mesh(
            f"stair_{i}",
            STAIR_WIDTH,
            height,
            STAIR_STEP_D,
            color=(0.50, 0.45, 0.40),
        )

        tex = Texture(os.path.join(_HERE, "assets", "models", "tower", "darkwood.jpg"))

        scene.add(
            SceneNode(
                f"stair_{i}",
                mesh=sm,
                texture = tex,
                position=(0, height / 2.0, z_center)
            )
        )

    floor_state.has_stairs = True


def _collect_meshes(node):
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


_OBJ_CACHE: dict[str, list] = {}
MODEL_TOWER = os.path.join(_HERE, "assets", "models", "tower")


def _add_tower_deco(scene, floor_state, name, position, scale=(1,1,1), rotation=(0,0,0), collision_radius=1.0):
    x, y, z   = position
    sx, sy, sz = scale
    base_path  = os.path.join(_HERE, "assets", "models", "tower") + os.sep

    if name == "obelisk":
        verts, idxs = make_cube(1.0)
        mesh = ProceduralMesh("obelisk", verts, idxs,
                              base_color=(0.25, 0.20, 0.35),
                              ka=0.3, kd=0.7, ks=0.4, shininess=32)
        # Caminho corrigido: assets/models/tower/obsidian.png
        node_texture = Texture(f"{base_path}obsidian.png")
        
        node = SceneNode("obelisk", mesh=mesh, texture=node_texture,
                         position=[x, y + 2.0 * sy, z],
                         scale=[0.4 * sx, 4.0 * sy, 0.4 * sz])
        
        hb = CircleHitbox(x, y, z, collision_radius)
        floor_state.obstacles.append(hb)

    elif name == "crystal":
        verts, idxs = make_sphere(0.5, 8, 8)
        mesh = ProceduralMesh("crystal", verts, idxs,
                              base_color=(0.15, 0.60, 0.55),
                              ka=0.4, kd=0.6, ks=0.9, shininess=80)
        
        # Caminho corrigido: assets/models/tower/rune_crystal.png
        node_texture = Texture(f"{base_path}rune_crystal.png")
        
        node = SceneNode("crystal", mesh=mesh, texture=node_texture,
                         position=[x, y + 0.6 * sy, z],
                         scale=[0.5 * sx, 1.2 * sy, 0.5 * sz])
        floor_state.obstacles.append(CircleHitbox(x, y, z, collision_radius))

    elif name == "platform":
        verts, idxs = make_cube(1.0)

        mesh = ProceduralMesh(
            "platform",
            verts,
            idxs,
            base_color=(0.45, 0.40, 0.35),
            ka=0.3,
            kd=0.8,
            ks=0.2,
            shininess=12
        )

        node_texture = Texture(f"{base_path}tower_stone.png")

        platform_w = 2.5 * sx
        platform_d = 2.5 * sz

        node = SceneNode(
            "platform",
            mesh=mesh,
            texture=node_texture,
            position=[x, y + 0.2 * sy, z],
            scale=[platform_w, 0.4 * sy, platform_d]
        )

        scene.add(node)
        floor_state.obstacles.append(
            BoxHitbox(
                x=x,
                y=y,
                z=z,
                width=5 * sx,
                height=1.2 * sy,
                depth=5 * sz
            )
        )

    elif name == "tower":
        verts, idxs = make_cube(1.0)
        mesh = ProceduralMesh("tower", verts, idxs,
                              base_color=(0.30, 0.25, 0.40),
                              ka=0.3, kd=0.7, ks=0.3, shininess=16)
        
        # Caminho corrigido: assets/models/tower/tower_stone.png
        node_texture = Texture(f"{base_path}tower_stone.png")
        
        node = SceneNode("tower", mesh=mesh, texture=node_texture,
                         position=[x, y + 3.0 * sy, z],
                         scale=[1.5 * sx, 6.0 * sy, 1.5 * sz])
        floor_state.obstacles.append(CircleHitbox(x, y, z, collision_radius))
    else:
        return None

    scene.add(node)
    return node


def _load_obj_model(path, position=(0,0,0), rotation=(0,0,0), scale=(1,1,1)):
    model_dir = os.path.dirname(os.path.abspath(path))
    if path not in _OBJ_CACHE:
        try:
            _OBJ_CACHE[path] = OBJLoader().load(path) or []
        except Exception as exc:
            print(f"OBJ load failed for {path}: {exc}")
            _OBJ_CACHE[path] = []
    mesh_data_list = _OBJ_CACHE[path]
    if not mesh_data_list:
        return None

    parent = SceneNode(os.path.splitext(os.path.basename(path))[0],
                       position=list(position), rotation=list(rotation), scale=list(scale))
    for md in mesh_data_list:
        mesh    = Mesh(md)
        texture = None
        if mesh.texture_path:
            tex_name = os.path.basename(mesh.texture_path)
            tex_path = os.path.join(model_dir, tex_name)
            if not os.path.exists(tex_path):
                tex_path = mesh.texture_path
            try:
                texture = Texture(tex_path)
            except Exception as exc:
                print(f"Failed to load texture {tex_path}: {exc}")
        child = SceneNode(mesh.name, mesh=mesh, texture=texture)
        child.position[1] = -0.5
        parent.children.append(child)

    return parent


_SKINNED_CACHE: dict = {}

SUBARU_GLB_DIR = os.path.join(_HERE, "assets", "models", "Subaru")
SUBARU_GLB_FILES = {
    "Idle":                 os.path.join(SUBARU_GLB_DIR, "subaru_idle.glb"),
    "Walking":              os.path.join(SUBARU_GLB_DIR, "subaru_walking.glb"),
    "Jumping":              os.path.join(SUBARU_GLB_DIR, "subaru_jumping.glb"),
    "Punching":             os.path.join(SUBARU_GLB_DIR, "subaru_punching.glb"),
    "Reaction":             os.path.join(SUBARU_GLB_DIR, "subaru_hit.glb"),
    "Beatrice":             os.path.join(SUBARU_GLB_DIR, "subaru_beatrice.glb"),
    "InvisibleProvidence":  os.path.join(SUBARU_GLB_DIR, "subaru_invisibleprovidence.glb"),
    "Item":                 os.path.join(SUBARU_GLB_DIR, "subaru_item.glb"),
}

# Modelo completo e animado da própria Beatrice (mesh + skeleton + clipe de
# idle em loop), usado em _show_beatrice() no lugar do antigo Beatrice.obj
# estático. Tem um único clipe ("Swim_Idle_Loop") que toca em loop contínuo
# enquanto ela estiver visível em cena.
BEATRICE_GLB_PATH = os.path.join(_HERE, "assets", "models", "Beatrice", "beatrice_animation.glb")
BEATRICE_CLIP_NAMES = {"idle": "Swim_Idle_Loop"}


def _load_skinned_player(position=(0, 0, 0), rotation=(0, 180, 0)):
    cache_key = tuple(sorted(SUBARU_GLB_FILES.items()))
    if cache_key not in _SKINNED_CACHE:
        try:
            loader       = GLTFLoader()
            primary_path = SUBARU_GLB_FILES["Walking"]
            if not os.path.isfile(primary_path):
                _SKINNED_CACHE[cache_key] = None
            else:
                smd = loader.load_merged(primary_path)
                if smd is None:
                    raise ValueError("nenhuma primitive com skin encontrada")
                smd._primitives = loader.last_primitives  # todas as primitives com texturas individuais

                renamed_clips = {}
                for clip_key, glb_path in SUBARU_GLB_FILES.items():
                    if not os.path.isfile(glb_path):
                        continue
                    try:
                        part = loader.load_merged(glb_path) if clip_key != "Walking" else smd
                        if part and part.clips:
                            original_clip = next(iter(part.clips.values()))
                            renamed_clips[clip_key] = original_clip
                    except Exception as exc:
                        print(f"Falha ao carregar clipe {glb_path}: {exc}")
                smd.clips = renamed_clips

                if not smd.texture_path:
                    fallback = os.path.join(SUBARU_GLB_DIR, "tx_Subaru_00_Body_Base.png")
                    smd.texture_path = fallback if os.path.isfile(fallback) else None

                _SKINNED_CACHE[cache_key] = smd
        except Exception as exc:
            print(f"GLB load failed for Subaru: {exc}")
            _SKINNED_CACHE[cache_key] = None

    smd = _SKINNED_CACHE[cache_key]
    if smd is None:
        return None, None, None

    skinned_mesh    = SkinnedMesh(smd)
    skinned_mesh._primitives = getattr(smd, '_primitives', None)
    anim_controller = AnimationController(smd.bones, smd.clips)

    SUBARU_TARGET_HEIGHT = 1.8
    auto_scale = getattr(smd, "_auto_scale", None)
    if auto_scale is None:
        bone_matrices = anim_controller.get_bone_matrices()
        bm    = np.stack(bone_matrices, axis=0)
        pos_h = np.concatenate([smd.vertices[:, :3], np.ones((len(smd.vertices), 1), dtype=np.float32)], axis=1)

        skinned_y = np.zeros(len(smd.vertices), dtype=np.float32)
        for k in range(smd.joints.shape[1]):
            joint_idx  = smd.joints[:, k].astype(np.int64)
            w          = smd.weights[:, k]
            transformed = np.einsum('nij,nj->ni', bm[joint_idx], pos_h)
            skinned_y  += w * transformed[:, 1]

        raw_height = float(skinned_y.max() - skinned_y.min()) if len(skinned_y) else 0.0
        auto_scale = (SUBARU_TARGET_HEIGHT / raw_height) if raw_height > 1e-4 else 1.0
        smd._auto_scale = auto_scale

    node      = SceneNode("subaru_skinned", position=list(position), rotation=list(rotation),
                          scale=[auto_scale, auto_scale, auto_scale])
    node.mesh = skinned_mesh

    # textura de fallback (corpo) para o node — o render multi-textura usa smd._primitives
    texture = None
    if smd.texture_path:
        try:
            texture = Texture(smd.texture_path)
        except Exception as exc:
            print(f"Failed to load Subaru texture {smd.texture_path}: {exc}")
    node.texture = texture

    return node, skinned_mesh, anim_controller


_BEATRICE_SKINNED_CACHE: dict = {}

BEATRICE_TARGET_HEIGHT = 1.6  # Beatrice é um pouco mais baixa que o Subaru (1.8)


def _load_skinned_beatrice(position=(0, 0, 0), rotation=(0, 180, 0)):
    """Carrega beatrice_animation.glb (mesh + skeleton + clipe 'Swim_Idle_Loop')
    como um skinned mesh independente, espelhando _load_skinned_player.
    Retorna (node, skinned_mesh, anim_controller) ou (None, None, None) se o
    .glb não existir / falhar ao carregar."""
    cache_key = BEATRICE_GLB_PATH
    if cache_key not in _BEATRICE_SKINNED_CACHE:
        try:
            if not os.path.isfile(BEATRICE_GLB_PATH):
                _BEATRICE_SKINNED_CACHE[cache_key] = None
            else:
                loader = GLTFLoader()
                smd    = loader.load_merged(BEATRICE_GLB_PATH)
                if smd is None:
                    raise ValueError("nenhuma primitive com skin encontrada")
                smd._primitives = loader.last_primitives

                if not smd.clips:
                    raise ValueError("beatrice_animation.glb não contém animações")

                # Mantém o(s) clipe(s) com seus nomes originais do .glb
                # (ex.: "Swim_Idle_Loop") — BEATRICE_CLIP_NAMES mapeia
                # "idle" -> "Swim_Idle_Loop" na hora de criar o controller.

                if not smd.texture_path:
                    fallback = os.path.join(os.path.dirname(BEATRICE_GLB_PATH), "tx_Beatrice_Base.png")
                    smd.texture_path = fallback if os.path.isfile(fallback) else None

                _BEATRICE_SKINNED_CACHE[cache_key] = smd
        except Exception as exc:
            print(f"GLB load failed for Beatrice: {exc}")
            _BEATRICE_SKINNED_CACHE[cache_key] = None

    smd = _BEATRICE_SKINNED_CACHE[cache_key]
    if smd is None:
        return None, None, None

    skinned_mesh           = SkinnedMesh(smd)
    skinned_mesh._primitives = getattr(smd, '_primitives', None)
    anim_controller         = AnimationController(smd.bones, smd.clips, clip_names=BEATRICE_CLIP_NAMES)
    anim_controller.play("idle")

    auto_scale = getattr(smd, "_auto_scale", None)
    if auto_scale is None:
        bone_matrices = anim_controller.get_bone_matrices()
        bm    = np.stack(bone_matrices, axis=0)
        pos_h = np.concatenate([smd.vertices[:, :3], np.ones((len(smd.vertices), 1), dtype=np.float32)], axis=1)

        skinned_y = np.zeros(len(smd.vertices), dtype=np.float32)
        for k in range(smd.joints.shape[1]):
            joint_idx  = smd.joints[:, k].astype(np.int64)
            w          = smd.weights[:, k]
            transformed = np.einsum('nij,nj->ni', bm[joint_idx], pos_h)
            skinned_y  += w * transformed[:, 1]

        raw_height = float(skinned_y.max() - skinned_y.min()) if len(skinned_y) else 0.0
        auto_scale = (BEATRICE_TARGET_HEIGHT / raw_height) if raw_height > 1e-4 else 1.0
        smd._auto_scale = auto_scale

    node      = SceneNode("beatrice_skinned", position=list(position), rotation=list(rotation),
                          scale=[auto_scale, auto_scale, auto_scale])
    node.mesh = skinned_mesh

    texture = None
    if smd.texture_path:
        try:
            texture = Texture(smd.texture_path)
        except Exception as exc:
            print(f"Failed to load Beatrice texture {smd.texture_path}: {exc}")
    node.texture = texture

    return node, skinned_mesh, anim_controller


def _spawn_heartless(scene, pos, scale=(0.012,0.012,0.012), level=2, stationary=False, flying=False):
    if flying:
        model_path = os.path.join(_HERE, "assets", "models", "AerialKnocker", "AerialKnocker.obj")
        model_scale = (scale[0] * 0.8, scale[1] * 0.8, scale[2] * 0.8)  # ajuste fino se necessário
        rotation = (0, 180, 0)
    else:
        model_path  = os.path.join(_HERE, "assets", "models", "Heartless", "Heartless.obj")
        model_scale = scale
        pos = (pos[0], pos[1] - 0.5, pos[2])  # ajuste para alinhar com o chão
        rotation = (180, 0, 0)

    node = _load_obj_model(model_path, position=pos, rotation=rotation, scale=model_scale)

    if node is None:
        ev, ei = make_sphere(0.45, 10, 10)
        color  = (0.3, 0.3, 0.9) if flying else (0.7, 0.1, 0.1)
        em     = ProceduralMesh("heartless", ev, ei, base_color=color, ka=0.3, kd=0.8, ks=0.3, shininess=16)
        node   = SceneNode("heartless", mesh=em, position=list(pos))

    scene.add(node)
    e = Enemy("Heartless", level=level, world_pos=list(pos), stationary=stationary)
    e.spawn_pos = list(pos)
    return e, node


# ── Save / Load ───────────────────────────────────────────────────────────────

def save_game(floor, player):
    data = {
        "floor": floor, "hp": player.stats.hp, "mp": player.stats.mp,
        "max_hp": player.stats.max_hp, "max_mp": player.stats.max_mp,
        "level": player.stats.level, "xp": player.stats.xp, "xp_next": player.stats.xp_next,
        "atk": player.stats.atk, "defense": player.stats.defense,
        "inventory": player.inventory.items, "gold": player.inventory.gold,
    }
    with open(SAVE_PATH, "w") as f:
        json.dump(data, f)


def load_game(player):
    if not os.path.exists(SAVE_PATH):
        return None
    with open(SAVE_PATH) as f:
        data = json.load(f)
    player.stats.hp        = data.get("hp",      player.stats.max_hp)
    player.stats.mp        = data.get("mp",      player.stats.max_mp)
    player.stats.max_hp    = data.get("max_hp",  player.stats.max_hp)
    player.stats.max_mp    = data.get("max_mp",  player.stats.max_mp)
    player.stats.level     = data.get("level",   1)
    player.stats.xp        = data.get("xp",      0)
    player.stats.xp_next   = data.get("xp_next", 100)
    player.stats.atk       = data.get("atk",     player.stats.atk)
    player.stats.defense   = data.get("defense", player.stats.defense)
    player.inventory.items = {k: v for k, v in data.get("inventory", {}).items()}
    player.inventory.gold  = data.get("gold", 0)
    return data.get("floor", 0)


# ── Floor builders ────────────────────────────────────────────────────────────

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
        # Boss
        self.boss            = None
        self.boss_node       = None
        self.emilia_node     = None
        # Corredor final
        self.gauntlet_waves  = []
        self.gauntlet_idx    = 0


class Game:
    FLOOR_ENTRY    = 0
    FLOOR_PUZZLE   = 1
    FLOOR_AERIAL   = 2
    FLOOR_RHYTHM   = 3
    FLOOR_GAUNTLET = 4
    FLOOR_REST     = 5
    FLOOR_BOSS     = 6

    def __init__(self):
        self._init_window()
        self._init_gl()
        self._init_shaders()
        self._init_game_state()

    # ── Init ─────────────────────────────────────────────────────────────────

    def _init_window(self):
        pygame.init(); pygame.font.init()
        pygame.mixer.music.load(os.path.join(_HERE, "assets", "music", "trilha.mp3"))
        pygame.mixer.music.set_volume(0.2)
        pygame.mixer.music.play(-1)
        pygame.display.set_mode((SCREEN_W, SCREEN_H), DOUBLEBUF|OPENGL|RESIZABLE)
        pygame.display.set_caption(TITLE)
        self.screen_w = SCREEN_W; self.screen_h = SCREEN_H

    def _init_gl(self):
        glEnable(GL_DEPTH_TEST); glDepthFunc(GL_LEQUAL)
        glClearColor(0.02, 0.02, 0.06, 1.0)

    def _init_shaders(self):
        def sh(v, f):
            return ShaderProgram(os.path.join(SHADER_DIR, v), os.path.join(SHADER_DIR, f))
        self.phong_shader   = sh("phong.vert",   "phong.frag")
        self.unlit_shader   = sh("unlit.vert",   "unlit.frag")
        self.skinned_shader = sh("skinned.vert", "phong.frag")

    def _init_game_state(self):
        self.input              = InputManager()
        self.player             = Player("Natsuki Subaru")
        self.combat             = None
        self.game_mode          = "menu"
        self.wireframe          = False
        self.clock              = pygame.time.Clock()
        self.hud                = HUD(self.screen_w, self.screen_h, self.unlit_shader)
        self.menus              = MenuManager()
        self.death_timer        = 0.0
        self._combat_enemy_ref  = None
        self.current_floor      = self.FLOOR_ENTRY
        self.floor_state        = FloorState()
        self.scene              = Scene()
        self.camera              = Camera()
        self.scene.set_aspect(self.screen_w / self.screen_h)
        self.player_node         = None
        self.player_skinned_mesh = None
        self.player_anim         = None
        self.player_texture      = None
        self.beatrice_node       = None
        self.beatrice_timer      = 0.0
        self.beatrice_skinned_mesh = None
        self.beatrice_anim         = None
        self.rhythm_active       = False
        self.rhythm_beats        = []
        self.rhythm_score        = 0
        self.rhythm_total        = 0
        self.rhythm_timer        = 0.0
        self.rhythm_window       = 0.20
        self.rhythm_warn_window  = 0.55
        self.rhythm_enemies      = []
        self.rhythm_targets      = []
        self.rhythm_active_idx   = -1
        self.story_active        = False
        self.story_lines         = []
        self.story_idx           = 0
        self.story_timer         = 0.0
        self.story_callback      = None
        self.credits_active      = False
        self.credits_timer       = 0.0
        self.credits_y           = 0.0
        self._fade_alpha         = 0.0
        self._fade_duration      = 0.0
        self._fade_callback      = None
        self._fade_done          = True
        self._fading             = False
        self._fade_in            = False
        self._post_fade_mode     = "explore"
        self._fade_build_pending = False
        self._push_title_menu()

    # ── Cena base ─────────────────────────────────────────────────────────────

    def _clear_scene(self):
        if hasattr(self, 'scene') and self.scene is not None:
            self.scene.cleanup()
        if getattr(self, 'player_skinned_mesh', None) is not None:
            self.player_skinned_mesh.destroy()
            self.player_skinned_mesh = None
        if getattr(self, 'beatrice_skinned_mesh', None) is not None:
            self.beatrice_skinned_mesh.destroy()
            self.beatrice_skinned_mesh = None
        self.player_anim    = None
        self.player_node    = None
        self.beatrice_anim  = None
        self.scene          = Scene()
        self.scene.set_aspect(self.screen_w / self.screen_h)
        self.floor_state    = FloorState()
        self.beatrice_node  = None
        self.beatrice_timer = 0.0

    def _build_room(
        self,
        floor_color=(0.22, 0.18, 0.28),
        wall_color=(0.28, 0.22, 0.35),
        ceil_color=(0.15, 0.12, 0.20)
    ):
        # Piso
        pv, pi = make_plane(
            ROOM_W,
            ROOM_D,
            20,
            tile_u=ROOM_W / 2,
            tile_v=ROOM_D / 2
        )

        floor_mesh = ProceduralMesh(
            "floor",
            pv,
            pi,
            base_color=floor_color,
            ka=0.3,
            kd=0.7,
            ks=0.1,
            shininess=8
        )

        floor_ceiling = Texture(os.path.join(_HERE, "assets", "models", "tower", "floor.jpeg"))

        floor_tex = ProceduralTexture(
            128,
            color_a=(55, 45, 70),
            color_b=(40, 33, 55)
        )

        self.scene.add(
            SceneNode(
                "floor",
                mesh=floor_mesh,
                texture=floor_ceiling,
            )
        )

        # Teto
        ceiling_mesh = ProceduralMesh(
            "ceiling",
            pv,
            pi,
            base_color=ceil_color,
            ka=0.2,
            kd=0.6,
            ks=0.05,
            shininess=4
        )

        self.scene.add(
            SceneNode(
                "ceiling",
                mesh=ceiling_mesh,
                texture=floor_ceiling,
                position=(0, ROOM_H, 0),
                rotation=(180, 0, 0)
            )
        )

        # =========================
        # Paredes Norte e Sul
        # =========================

        pv_ns, pi_ns = make_plane(
            ROOM_W,
            ROOM_H,
            divs=10,
            tile_u=2,
            tile_v=2
        )

        wall_texture = Texture(os.path.join(_HERE, "assets", "models", "tower", "stone_bricks.jpg"))

        for name, pos, rot in [
            ("wall_n", (0, ROOM_H / 2, -ROOM_D / 2), (90, 0, 0)),
            ("wall_s", (0, ROOM_H / 2,  ROOM_D / 2), (-90, 180, 0)),
        ]:
            wm = ProceduralMesh(
                name,
                pv_ns,
                pi_ns,
                base_color=wall_color,
                ka=0.25,
                kd=0.75,
                ks=0.1,
                shininess=8
            )

            self.scene.add(
                SceneNode(
                    name,
                    mesh=wm,
                    texture=wall_texture,
                    position=pos,
                    rotation=rot
                )
            )

        # =========================
        # Paredes Leste e Oeste
        # =========================

        pv_ew, pi_ew = make_plane(ROOM_D, ROOM_H, divs=10, tile_u=2, tile_v=2)

        for name, pos, rot in [
            ("wall_w", (-ROOM_W / 2, ROOM_H / 2, 0), (90, 90, 0)),
            ("wall_e", ( ROOM_W / 2, ROOM_H / 2, 0), (90,-90, 0)),
        ]:
            wm = ProceduralMesh(
                name,
                pv_ew,
                pi_ew,
                base_color=wall_color,
                ka=0.25,
                kd=0.75,
                ks=0.1,
                shininess=8
            )

            self.scene.add(
                SceneNode(
                    name,
                    mesh=wm,
                    position=pos,
                    texture=wall_texture,
                    rotation=rot
                )
            )

        # Luz
        self.scene.light.orbit = False
        self.scene.light.pos = [0.0, ROOM_H - 1.5, 0.0]
        self.scene.light.intensity = 1.2
        self.scene.light.color = np.array(
            [0.8, 0.6, 1.0],
            dtype=np.float32
        )

        lv, li = make_sphere(0.18, 8, 8)

        lm = ProceduralMesh(
            "light_ball",
            lv,
            li,
            base_color=(1.0, 0.9, 0.5),
            ka=1.0,
            kd=0.0,
            ks=0.0,
            shininess=1
        )

        self.light_node = SceneNode(
            "light_vis",
            mesh=lm,
            position=[0.0, ROOM_H - 1.5, 0.0]
        )

        self.scene.add(self.light_node)

    def _place_player(self, pos=(0,0,10)):
        self.player.world_pos = list(pos)
        self.player.velocity  = [0,0,0]
        self.player.on_ground = True

        skinned_node, skinned_mesh, anim_controller = _load_skinned_player(position=pos, rotation=(0, 180, 0))
        if skinned_node is not None:
            self.player_node         = skinned_node
            self.player_skinned_mesh = skinned_mesh
            self.player_anim         = anim_controller
        else:
            self.player_skinned_mesh = None
            self.player_anim         = None
            self.player_node = _load_obj_model(
                os.path.join(_HERE, "assets", "models", "Subaru", "Subaru.obj"),
                position=pos, rotation=(0, 180, 0), scale=(1.0, 1.0, 1.0)
            )
            if self.player_node is None:
                sv, si = make_sphere(0.45, 12, 12)
                pm = ProceduralMesh("subaru", sv, si, base_color=(0.2,0.35,0.6), ka=0.3, kd=0.8, ks=0.4, shininess=24)
                self.player_node = SceneNode("subaru", mesh=pm, position=list(pos))
            self.scene.add(self.player_node)

        bx, by, bz = pos[0] + 1.2, pos[1] + BEATRICE_Y_OFFSET, pos[2] - 0.5
        beat_skinned_node, beat_skinned_mesh, beat_anim = _load_skinned_beatrice(
            position=(bx, by, bz), rotation=(0, 180, 0)
        )
        if beat_skinned_node is not None:
            # Skinned: NÃO entra em self.scene.add() — é desenhado à parte
            # por _render_skinned_beatrice() (shader com uBoneMatrices),
            # igual ao player_node skinned. Scene.draw() normal não sabe
            # desenhar skin/bones.
            bnode = beat_skinned_node
            self.beatrice_skinned_mesh = beat_skinned_mesh
            self.beatrice_anim         = beat_anim
        else:
            self.beatrice_skinned_mesh = None
            self.beatrice_anim         = None
            beat_path = os.path.join(_HERE, "assets", "models", "Beatrice", "Beatrice.obj")
            bnode = _load_obj_model(beat_path, position=(bx, by, bz), rotation=(0, 180, 0), scale=(1.0, 1.0, 1.0))
            if bnode is None:
                bv, bi = make_sphere(0.4, 10, 10)
                bm    = ProceduralMesh("beatrice_fb", bv, bi, base_color=(0.7, 0.4, 0.9), ka=0.5, kd=0.7, ks=0.6, shininess=48)
                bnode = SceneNode("beatrice_fb", mesh=bm, position=[bx, by + 0.5, bz])
            self.scene.add(bnode)
        bnode.visible = False
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
        self._build_room(floor_color=(0.12,0.10,0.18), wall_color=(0.18,0.14,0.26))
        self._place_player(pos=(0,2,12))

        # Porta no fundo do corredor (Norte, Z=-13)
        dv, di = make_cube(1.0)
        dm = make_box_mesh("door",3.0,4.0,0.3, color=(0.35,0.22,0.10), ka=0.2,kd=0.7,ks=0.3,shin=24)

        door_tex = Texture(os.path.join(_HERE, "assets", "models", "tower", "doorwood.jpeg"))

        door_node = SceneNode("door", mesh=dm, position=(0, 4.0,-15), scale=(1,1,1), texture=door_tex)
        self.scene.add(door_node)
        self.floor_state.door_node = door_node


        # Barreira mágica (inicialmente invisível até abrir a porta)
        bv, bi = make_cube(1.0)
        bm = make_box_mesh("barrier",ROOM_W-2,ROOM_H-1,0.2, color=(0.2,0.1,0.8))
        barrier_node = SceneNode("barrier", mesh=bm, position=(0,ROOM_H/2-0.5,-9.0))
        barrier_node.visible = False
        self.scene.add(barrier_node)
        self.floor_state.barrier_node   = barrier_node
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
        self._build_room(floor_color=(0.18,0.16,0.28), wall_color=(0.26,0.20,0.38))
        self._place_player(pos=(0,0,12))

        frame_w, frame_h = 4.0, 2.25
        frame_cx, frame_cy = 0.0, ROOM_H/2 + 0.4
        fv, fi = make_plane(frame_w + 0.3, frame_h + 0.3, 1)
        self.scene.add(SceneNode("puzzle_frame", mesh=ProceduralMesh("puzzle_frame", fv, fi, base_color=(0.45,0.35,0.10), ka=0.6, kd=0.5, ks=0.6, shininess=32),
                                  position=(frame_cx, frame_cy, -8.92), rotation=(90,0,0)))
        bv, bi = make_plane(frame_w, frame_h, 1)
        self.scene.add(SceneNode("puzzle_backing", mesh=ProceduralMesh("puzzle_backing", bv, bi, base_color=(0.05,0.05,0.08), ka=0.5, kd=0.3, ks=0.0, shininess=1),
                                  position=(frame_cx, frame_cy, -8.9), rotation=(90,0,0)))

        piece_w, piece_h   = frame_w/2, frame_h/2
        pv, pi             = make_plane(piece_w, piece_h, 1)
        scatter_positions  = [(-4,1.4,-2),(4,1.4,-2),(-4,1.4,2),(4,1.4,2)]
        mural_offsets      = [(-piece_w/2, piece_h/2),(piece_w/2, piece_h/2),(-piece_w/2,-piece_h/2),(piece_w/2,-piece_h/2)]
        img_dir            = os.path.join(_HERE, "assets", "images", "puzzle")

        self.puzzle_pieces = []
        for idx, spos in enumerate(scatter_positions):
            tex   = Texture(os.path.join(img_dir, f"piece_{idx}.png"))
            pm    = ProceduralMesh(f"puzzle_piece_{idx}", pv, pi, base_color=(1,1,1), ka=0.9, kd=0.6, ks=0.1, shininess=8)
            pnode = SceneNode(f"puzzle_piece_{idx}", mesh=pm, texture=tex, position=list(spos), rotation=(90,0,0))
            self.scene.add(pnode)
            mural_pos = (frame_cx + mural_offsets[idx][0], frame_cy + mural_offsets[idx][1], -8.9)
            self.puzzle_pieces.append({"node": pnode, "collected": False, "scatter_pos": spos, "mural_pos": mural_pos})
        self.floor_state.puzzle_solved = False

        _build_stairs(self.scene, self.floor_state)
        gm = make_box_mesh("gate", 3.2, 2.0, 0.3, color=(0.5,0.4,0.1))
        gate_node = SceneNode("gate", mesh=gm, position=(0,1.0,-10.5))
        self.scene.add(gate_node)
        self.floor_state.barrier_node = gate_node

        self.hud.add_popup("Junte os fragmentos espalhados pela sala!", 3.0, (200,220,255))
        self.hud.add_popup("[Z] perto de cada fragmento para encaixá-lo no quadro", 4.0, (180,180,220))

    def _build_floor_aerial(self):
        self._build_room(floor_color=(0.16,0.14,0.22), wall_color=(0.24,0.20,0.34))
        self._place_player(pos=(0,0,12))

        for px, pz in [(-4,0),(4,0),(0,4)]:
            e, n = _spawn_heartless(self.scene, (px,0.5,pz), level=3)
            e.respawns_left = 0
            self.floor_state.enemies.append((e,n))
        for px, pz in [(-3,2),(3,2),(0,-2)]:
            e, n = _spawn_heartless(self.scene, (px,3.0,pz), scale=(0.0125,0.0125,0.0125), level=3, flying=True)
            e.is_flying = True; e.respawns_left = 0; e.aggro_range = 8.0
            self.floor_state.enemies.append((e,n))
        self.floor_state.stair_locked = True

        _build_stairs(self.scene, self.floor_state)
        gm = make_box_mesh("gate_a", 3.2, 2.0, 0.3, color=(0.5,0.3,0.1))
        gate_node = SceneNode("gate_a", mesh=gm, position=(0,1.0,-10.5))
        self.scene.add(gate_node)
        self.floor_state.barrier_node = gate_node

        self.hud.add_popup("Cuidado com os Heartless voadores!", 3.0, (255,200,100))
        self.hud.add_popup("[Espaço] pra pular e alcançá-los!", 4.0, (200,200,255))

    def _build_floor_rhythm(self):
        self._build_room(floor_color=(0.10,0.18,0.20), wall_color=(0.16,0.26,0.30))
        self._place_player(pos=(0,0,12))

        self.rhythm_enemies = []
        for px, pz in [(-3,-3),(0,-4),(3,-3)]:
            e, n = _spawn_heartless(self.scene, (px,0.5,pz), level=2, stationary=True)
            e.respawns_left = 0
            meshes = _collect_meshes(n)
            self.rhythm_enemies.append({"enemy": e, "node": n, "meshes": meshes,
                                         "orig_colors": [tuple(m.base_color) for m in meshes]})

        _build_stairs(self.scene, self.floor_state)
        gm = make_box_mesh("gate_r", 3.2, 2.0, 0.3, color=(0.1,0.4,0.5))
        gate_node = SceneNode("gate_r", mesh=gm, position=(0,1.0,-10.5))
        self.scene.add(gate_node)
        self.floor_state.barrier_node = gate_node
        self.floor_state.rhythm_done  = False

        for cx, cz in [(-8.0,-2.0),(-8.0,2.0),(8.0,-2.0),(8.0,2.0)]:
            _add_tower_deco(self.scene, self.floor_state, "crystal", position=(cx, 0.0, cz), scale=(1.0,1.0,1.0), collision_radius=0.9)

        self.hud.add_popup("Combate Rítmico! ENTER pra começar", 4.0, (100,255,200))
        self.hud.add_popup("[Z] quando chegar na barra 'amarela'!", 4.0, (200,255,220))

    def _build_floor_gauntlet(self):
        self._build_room(floor_color=(0.20,0.08,0.08), wall_color=(0.28,0.12,0.12))
        self._place_player(pos=(0,0,12))

        wave1 = []
        for px, pz in [(-5,2),(5,2),(0,0),(-3,-2),(3,-2)]:
            e, n = _spawn_heartless(self.scene, (px,0.5,pz), level=4)
            e.respawns_left = 0; wave1.append((e,n))
        wave2 = []
        for px, pz in [(-4,1),(4,1)]:
            e, n = _spawn_heartless(self.scene, (px,0.5,pz), level=4)
            e.respawns_left = 0; wave2.append((e,n))
        for px, pz in [(0,2),(-3,-1),(3,-1)]:
            e, n = _spawn_heartless(self.scene, (px,3.0,pz), scale=(0.0125,0.0125,0.0125), level=4, flying=True)
            e.is_flying = True; wave2.append((e,n)); n.visible = False

        self.floor_state.gauntlet_waves = [wave1, wave2]
        self.floor_state.gauntlet_idx   = 0
        self.floor_state.enemies        = list(wave1)
        self.floor_state.stair_locked   = True

        pm = make_box_mesh("portal_gate", 3.0, 4.0, 0.3, color=(0.5,0.1,0.1))
        self.scene.add(SceneNode("portal_gate", mesh=pm, position=(0,2.0,-13.5)))
        self.hud.add_popup("Corredor Final! Sobreviva!", 3.0, (255,100,100))

    def _build_floor_rest(self):
        self._build_room(floor_color=(0.15,0.22,0.18), wall_color=(0.20,0.30,0.24), ceil_color=(0.12,0.20,0.16))
        self._place_player(pos=(0,0,8))
        self.scene.add(SceneNode("altar_rest", mesh=make_box_mesh("altar_rest",4.0,0.5,2.0, color=(0.4,0.6,0.5)), position=(0,0.25,0)))
        self.scene.light.intensity = 0.8
        self.scene.light.color     = np.array([0.7,1.0,0.8], dtype=np.float32)
        self.player.stats.hp = self.player.stats.max_hp
        self.player.stats.mp = self.player.stats.max_mp
        save_game(self.current_floor, self.player)
        self.floor_state.stair_locked = False
        self.hud.add_popup("Sala de Descanso", 3.0, (100,255,180))
        self.hud.add_popup("HP e MP recuperados! Jogo salvo.", 3.5, (180,255,200))
        self.hud.add_popup("Avance para enfrentar o boss final...", 4.5, (255,220,200))
        self.scene.add(SceneNode("boss_door", mesh=make_box_mesh("boss_door",3.0,4.0,0.3, color=(0.6,0.2,0.6)), position=(0,2.0,-13.0)))

    def _build_floor_boss(self):
        self._build_room(floor_color=(0.20,0.05,0.20), wall_color=(0.28,0.08,0.28), ceil_color=(0.15,0.04,0.18))
        self._place_player(pos=(0,0,10))
        self.floor_state.stair_locked  = False
        self.scene.light.color         = np.array([1.0,0.5,1.0], dtype=np.float32)
        self.scene.light.intensity     = 1.5

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
        boss_enemy = Enemy("Marluxia", level=8, world_pos=[0.0,0.0,-8.0])
        boss_enemy.stats.max_hp  = 400
        boss_enemy.stats.hp      = 400
        boss_enemy.stats.atk     = 22
        boss_enemy.stats.defense = 8
        boss_enemy.aggro_range   = 12.0
        boss_enemy.attack_range  = 2.2
        boss_enemy.respawns_left = 0
        boss_enemy.spawn_pos     = [0.0,0.0,-8.0]
        self.floor_state.boss      = boss_enemy
        self.floor_state.boss_node = boss_node
        self.floor_state.enemies   = [(boss_enemy, boss_node)]

        _add_tower_deco(self.scene, self.floor_state, "tower",    position=(0.0, 0.0, -13.5), scale=(1.0,1.0,1.0), collision_radius=1.8)
        for cx, cz in [(-8.5,-5.0),(8.5,-5.0),(-8.5,5.0),(8.5,5.0)]:
            _add_tower_deco(self.scene, self.floor_state, "crystal", position=(cx, 0.0, cz), scale=(1.4,1.4,1.4), collision_radius=1.0)
        for px in (-8.5, 8.5):
            _add_tower_deco(self.scene, self.floor_state, "platform", position=(px, 0.0, 0.0), scale=(1.0,1.0,1.0), collision_radius=1.2)

        self.hud.add_popup("BOSS: MARLUXIA", 3.0, (255,80,255))
        self.hud.add_popup("Salve Emilia!", 3.5, (255,200,255))

    # ── Story / Cutscene ─────────────────────────────────────────────────────

    def _start_story(self):
        self._show_story([
            "Enquanto Emilia tentava recuperar suas memórias perdidas...",
            "...dentro da própria mente, Natsuki Subaru",
            "começou a avançar na torre em que ela foi capturada.",
            "", "Mas Subaru não vai desistir de Emilia.", "",
            "— Pressione ENTER para começar —",
        ], callback=self._story_done)

    def _start_story_part2(self):
        self._show_story([
            "Subaru enfrentou diversos puzzles e inimigos da escuridão",
            "que tentaram impedir seu avanço...", "",
            "Agora, no fim da torre, há aquele por trás de tudo: Marluxia.",
            "Que fez tudo isso para atrair Subaru até aqui...",
            "...querendo obter o seu Retorno pela Morte.", "",
            "— Pressione ENTER para continuar —",
        ], callback=self._story_done)

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
        self._show_story([
            "Marluxia cai.", "", "Emilia abre os olhos devagar...", "", '"Subaru...?"', "",
            "Suas memórias voltaram.", "Ela lembra de tudo.", "",
            '"Eu me lembro de você, Subaru."', "",
            "Os dois ficam juntos na sala silenciosa da torre.", "", "— FIM —", "",
            "— Pressione ENTER para os créditos —",
        ], callback=self._start_credits)

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

        self.menus.push(Menu("Torre de Plêiades", [
            MenuItem("Nova Partida", start),
            MenuItem("Continuar",    continue_game),
            MenuItem("Sair",         quit_game),
        ]))
        self.game_mode = "menu"

    def _push_pause_menu(self):
        def resume():
            self.menus.pop(); self.game_mode = "explore"; self.input.capture_mouse(True)
        def save():
            save_game(self.current_floor, self.player)
            self.hud.add_popup("Jogo salvo!", 2.0, (100,255,100))
            self.menus.pop(); self.game_mode = "explore"; self.input.capture_mouse(True)
        def title():
            self.menus.clear(); self._push_title_menu(); self.input.capture_mouse(False)
        self.menus.push(Menu("Pausado", [
            MenuItem("Continuar",      resume),
            MenuItem("Salvar",         save),
            MenuItem("Menu Principal", title),
        ]))
        self.game_mode = "menu"; self.input.capture_mouse(False)

    def _push_combat_menu(self):
        def attack():
            if self.combat: self.combat.player_attack(); self._check_combat_end()
        def use_potion():
            if self.combat: self.combat.player_use_item("health_potion_s", self.player.inventory); self._check_combat_end()
        def flee():
            if self.combat: self.combat.player_flee(); self._check_combat_end()
        self.menus.push(Menu("Combate", [
            MenuItem("Atacar", attack), MenuItem("Poção", use_potion), MenuItem("Fugir", flee),
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
        self.game_mode = "death"; self.death_timer = 3.5; self.input.capture_mouse(False)

    def _respawn(self):
        self.player.stats.hp = self.player.stats.max_hp
        self.player.stats.mp = self.player.stats.max_mp
        saved_floor = load_game(self.player)
        floor = saved_floor if saved_floor is not None else self.current_floor
        self._build_floor(floor)
        self.game_mode = "explore"; self.input.capture_mouse(True)
        self.hud.add_popup("Return by Death...", 3.0, (180,80,80))

    # ── Floor progression ─────────────────────────────────────────────────────

    def _advance_floor(self):
        next_floor = self.current_floor + 1
        if next_floor > self.FLOOR_BOSS:
            return
        def _do_transition():
            save_game(next_floor, self.player)
            self._build_floor(next_floor)
        self._start_fade(_do_transition, duration=0.35)
        self.hud.add_popup("Subindo para o próximo andar...", 2.0, (200,255,200))

    def _start_fade(self, callback, duration=0.35):
        self._fade_alpha         = 0.0
        self._fade_duration      = duration
        self._fade_callback      = callback
        self._fade_done          = False
        self._fading             = True
        self._fade_in            = False
        self.game_mode           = "fade"
        self.input.capture_mouse(False)

    def _check_floor_progress(self):
        fs    = self.floor_state
        alive = [e for e,n in fs.enemies if not e.dead]

        if self.current_floor == self.FLOOR_ENTRY:
            if fs.barrier_active and not alive:
                fs.stair_locked = False
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
                    fs.gauntlet_idx += 1
                    next_wave = fs.gauntlet_waves[fs.gauntlet_idx]
                    fs.enemies = next_wave
                    for e, n in next_wave:
                        n.visible = True; e.dead = False
                    self.hud.add_popup("Próxima onda!", 2.0, (255,180,100))
                else:
                    fs.stair_locked = False
                    self.hud.add_popup("Corredor limpo! Avance pela porta.", 3.0, (200,255,200))

        elif self.current_floor == self.FLOOR_BOSS:
            if fs.boss and fs.boss.dead:
                self._on_boss_defeated()

    def _on_boss_defeated(self):
        self.game_mode = "story"; self.input.capture_mouse(False); self._show_ending()

    # ── Player attack (real-time) ─────────────────────────────────────────────

    def _player_melee_attack(self):
        p = self.player
        if p.attack_cd > 0: return
        p.is_attacking = True; p.attack_timer = 0.4; p.attack_cd = 0.6
        p.combo_count  = (p.combo_count + 1) % 3; p.combo_timer = 0.8
        if self.player_anim is not None:
            self.player_anim.play("punching", restart_if_same=True)
        hit = False
        for e, node in self.floor_state.enemies:
            if e.dead: continue
            dx = e.world_pos[0] - p.world_pos[0]
            dy = e.world_pos[1] - p.world_pos[1]
            dz = e.world_pos[2] - p.world_pos[2]
            fly     = getattr(e, 'is_flying', False)
            reach_y = abs(dy) < 2.5 if fly else abs(dy) < 1.5
            if math.sqrt(dx*dx + dz*dz) < 2.0 and reach_y:
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
        if self.current_floor == self.FLOOR_PUZZLE:
            self._try_activate_orb()
        if not hit:
            self.hud.add_popup("Swoosh!", 0.6, (200,200,200))

    def _try_activate_orb(self):
        p = self.player
        for piece in self.puzzle_pieces:
            if piece["collected"]: continue
            spos = piece["scatter_pos"]
            dx = spos[0] - p.world_pos[0]; dz = spos[2] - p.world_pos[2]
            if math.sqrt(dx*dx + dz*dz) < 2.0:
                piece["collected"] = True
                piece["node"].position = list(piece["mural_pos"])
                self.hud.add_popup("Fragmento encaixado!", 1.5, (200,200,100))
                self._check_puzzle(); return

    def _check_puzzle(self):
        if all(p["collected"] for p in self.puzzle_pieces):
            self.floor_state.puzzle_solved = True
            self.floor_state.stair_locked  = False
            self.floor_state.barrier_node.visible = False
            self.hud.add_popup("Quadro completo! Suba as escadas.", 3.0, (100,255,100))

    # ── Rhythm game ───────────────────────────────────────────────────────────

    def _start_rhythm_game(self):
        self.rhythm_active     = True
        self.rhythm_score      = 0
        self.rhythm_total      = 8
        self.rhythm_beats      = [1.0,1.5,2.0,2.7,3.2,4.0,4.5,5.0]
        self.rhythm_timer      = 0.0
        self.rhythm_hit        = [False] * len(self.rhythm_beats)
        n_en                   = len(self.rhythm_enemies)
        self.rhythm_targets    = [i % n_en for i in range(len(self.rhythm_beats))]
        self.rhythm_active_idx = -1
        for re_ in self.rhythm_enemies:
            re_["enemy"].dead = False
            re_["enemy"].stats.hp = re_["enemy"].stats.max_hp
            re_["node"].visible = True
            _restore_colors(re_)
        self.game_mode = "rhythm"; self.input.capture_mouse(False)
        self.hud.add_popup("Pressione Z quando chegar na barra amarela!", 2.0, (100,255,200))

    def _update_rhythm(self, dt):
        if not self.rhythm_active: return
        self.rhythm_timer += dt
        t = self.rhythm_timer

        active_idx = -1
        for i, bt in enumerate(self.rhythm_beats):
            if not self.rhythm_hit[i] and (bt - self.rhythm_warn_window) <= t <= (bt + self.rhythm_window):
                active_idx = self.rhythm_targets[i]; break
        if active_idx != self.rhythm_active_idx:
            for re_ in self.rhythm_enemies: _restore_colors(re_)
            if active_idx >= 0:
                _flash_color(self.rhythm_enemies[active_idx], (1.0, 0.95, 0.2))
            self.rhythm_active_idx = active_idx

        for i, bt in enumerate(self.rhythm_beats):
            if not self.rhythm_hit[i] and t > bt + self.rhythm_window + 0.2:
                self.rhythm_hit[i] = True; self._rhythm_player_damage()
        if not self.rhythm_active: return

        if t > self.rhythm_beats[-1] + 1.0:
            self.rhythm_active     = False
            self.rhythm_active_idx = -1
            for re_ in self.rhythm_enemies: _restore_colors(re_)
            pct = self.rhythm_score / self.rhythm_total
            if pct >= 0.5:
                self.floor_state.rhythm_done  = True
                self.floor_state.stair_locked = False
                self.floor_state.barrier_node.visible = False
                for re_ in self.rhythm_enemies:
                    re_["enemy"].dead = True; re_["node"].visible = False
                self.hud.add_popup(f"Ritmo! {self.rhythm_score}/{self.rhythm_total} – Suba!", 3.0, (100,255,200))
            else:
                self.hud.add_popup(f"Muito fora do ritmo! ({self.rhythm_score}/{self.rhythm_total}) Tente de novo.", 3.0, (255,100,100))
            self.game_mode = "explore"; self.input.capture_mouse(True)

    def _rhythm_player_damage(self, amount=8):
        p = self.player
        p.stats.hp = max(0, p.stats.hp - amount)
        p.is_taking_damage = True; p.reaction_timer = p.REACTION_TIME
        self.hud.add_popup(f"-{amount} HP", 1.0, (255,100,100))
        if p.stats.hp <= 0:
            self.rhythm_active = False; self.rhythm_active_idx = -1
            for re_ in self.rhythm_enemies: _restore_colors(re_)
            self._trigger_death()

    def _rhythm_press(self):
        if not self.rhythm_active: return
        t = self.rhythm_timer
        for i, bt in enumerate(self.rhythm_beats):
            if not self.rhythm_hit[i] and abs(t - bt) <= self.rhythm_window:
                self.rhythm_hit[i] = True; self.rhythm_score += 1
                target = self.rhythm_enemies[self.rhythm_targets[i]]
                e = target["enemy"]
                if not e.dead:
                    damage = max(1, self.player.stats.atk + random.randint(-2,2) - e.stats.defense)
                    e.stats.take_damage(damage)
                    self.hud.add_popup(f"-{damage} HP!", 1.0, (255,200,140))
                    if not e.stats.is_alive():
                        e.dead = True; target["node"].visible = False
                self.hud.add_popup("BEAT!", 0.5, (50,255,180)); return
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
                        cb = self.story_callback; self.story_callback = None; cb()
            return

        if self.game_mode == "credits":
            if self.input.key_pressed("return") or self.input.key_pressed("escape"):
                self.credits_active = False; self.game_mode = "menu"; self._push_title_menu()
            return

        if self.game_mode == "rhythm":
            if self.input.key_pressed("z"):     self._rhythm_press()
            if self.input.key_pressed("escape"):
                self.rhythm_active = False; self.game_mode = "explore"; self.input.capture_mouse(True)
            return

        if self.game_mode == "explore":
            dx, dy = self.input.mouse_delta
            if dx or dy: self.camera.process_mouse(dx, dy)
            if self.input.key_pressed("escape"): self._push_pause_menu()
            if self.input.key_pressed("z"):      self._player_melee_attack()
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
                if self.input.key_pressed(str(n)): self._handle_submenu_number(n)
            if self.input.key_pressed("e") or self.input.key_pressed("return"):
                self._interact()
            if self.current_floor == self.FLOOR_RHYTHM and not self.floor_state.rhythm_done:
                if self.input.key_pressed("return"): self._start_rhythm_game()

        elif self.game_mode in ("menu", "combat"):
            self.menus.handle_input(self.input)

    def _handle_submenu_number(self, n):
        idx = n - 1
        if self.hud.spell_menu_open and idx < len(SPELL_LIST):
            self._cast_spell(SPELL_LIST[idx])
        elif self.hud.item_menu_open:
            items = self.player.inventory.list_consumables()
            if idx < len(items): self._use_item_explore(items[idx][0].id)

    def _interact(self):
        p  = self.player
        pz = p.world_pos[2]; px = p.world_pos[0]

        if self.current_floor == self.FLOOR_ENTRY:
            if pz < -10.0 and not self.floor_state.stair_locked:
                self._advance_floor(); return
            if pz < -10.0 and abs(px) < 3.0 and not self.floor_state.barrier_active and self.floor_state.stair_locked:
                self.floor_state.barrier_active = True
                self.floor_state.barrier_node.visible = True
                for ep in [(-3,0.5,-5),(3,0.5,-5),(0,0.5,-3)]:
                    e, n = _spawn_heartless(self.scene, ep, level=2)
                    e.respawns_left = 0; self.floor_state.enemies.append((e,n))
                self.hud.add_popup("TUTORIAL DE COMBATE!", 2.5, (255,200,80))
                self.hud.add_popup("[Z] para atacar os Heartless!", 3.5, (200,200,255))

        elif self.current_floor in (self.FLOOR_PUZZLE, self.FLOOR_AERIAL, self.FLOOR_RHYTHM, self.FLOOR_GAUNTLET):
            if pz < -10.0 and not self.floor_state.stair_locked:
                self._advance_floor()

        elif self.current_floor == self.FLOOR_REST:
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
            if self.player_anim is not None:
                self.player_anim.play("invisibleprovidence", restart_if_same=True)
        else:
            if not self.player.stats.use_mp(sp.mp_cost):
                self.hud.add_popup("MP insuficiente!", 1.5, (100,100,255)); return
        if spell_id == "emt":
            self.player.stats.shield_time = 10.0; self._show_beatrice()
            if self.player_anim is not None:
                self.player_anim.play("beatrice", restart_if_same=True)
            self.hud.add_popup("EMT ativado! Protegido por 10s", 2.0, (80,220,255)); return
        nearest = None; nearest_dist = 999.0
        for e, node in self.floor_state.enemies:
            if e.dead: continue
            dx = e.world_pos[0]-self.player.world_pos[0]; dz = e.world_pos[2]-self.player.world_pos[2]
            dist = math.sqrt(dx*dx+dz*dz)
            if dist < 8.0 and dist < nearest_dist:
                nearest = (e,node,dist); nearest_dist = dist
        if not nearest:
            self.hud.add_popup(f"{sp.name} – sem alvo próximo", 1.2, (140,140,255)); return
        e, node, _ = nearest
        if spell_id == "shamac":
            e.blind_time = 10.0; e.aggro = False; self._show_beatrice()
            if self.player_anim is not None:
                self.player_anim.play("beatrice", restart_if_same=True)
            self.hud.add_popup(f"Shamac! {e.stats.name} perdeu sua pista.", 2.2, (180,120,255)); return
        dmg = e.stats.take_damage(sp.damage)
        if spell_id == "minya":
            self._show_beatrice()
            if self.player_anim is not None:
                self.player_anim.play("beatrice", restart_if_same=True)
        self.hud.add_popup(f"{sp.name}! -{dmg} HP", 2.0, (180,120,255))
        if not e.stats.is_alive():
            e.dead = True; node.visible = False
            xp = e.stats.level*20 + random.randint(5,15)
            leveled = self.player.stats.gain_xp(xp)
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
        if self.player_anim is not None:
            self.player_anim.play("item", restart_if_same=True)
        self.hud.add_popup(f"Usou {item.name}", 1.5, (120,255,120))

    def _show_beatrice(self, duration=3.3):
        if self.beatrice_node is None: return
        p = self.player.world_pos
        self.beatrice_node.position = [p[0] + 1.2, p[1] + BEATRICE_Y_OFFSET, p[2] - 0.5]
        self.beatrice_node.rotation[1] = self.player_node.rotation[1]
        self.beatrice_node.visible = True
        self.beatrice_timer = duration

    # ── Update ────────────────────────────────────────────────────────────────

    def _update_game(self, dt):
        if self.game_mode == "death":
            self.death_timer -= dt
            if self.death_timer <= 0.0: self._respawn(); return
        if self.game_mode == "credits":
            self.credits_y -= 40 * dt; self.credits_timer += dt; return
        if getattr(self, '_fading', False):
            self._update_fade(dt)
            if self.game_mode == "fade": return
        if self.game_mode == "rhythm":
            self._update_rhythm(dt)
        if self.game_mode not in ("explore","rhythm"): return
        self._update_player(dt)
        self._update_enemies(dt)
        self.hud.update(dt)
        if self.beatrice_node is not None and self.beatrice_timer > 0.0:
            self.beatrice_timer -= dt
            p = self.player.world_pos
            self.beatrice_node.position = [p[0] + 1.2, p[1] + BEATRICE_Y_OFFSET, p[2] - 0.5]
            self.beatrice_node.rotation[1] = self.player_node.rotation[1]
            if self.beatrice_timer <= 0.0:
                self.beatrice_node.visible = False
        # Avança o clipe de idle da Beatrice em loop contínuo sempre que ela
        # estiver visível em cena — independente do timer acima, então se o
        # timer/gatilho de visibilidade mudar no futuro a animação continua
        # tocando corretamente enquanto bnode.visible for True.
        if self.beatrice_anim is not None and self.beatrice_node is not None and self.beatrice_node.visible:
            self.beatrice_anim.update(dt)

    def _update_fade(self, dt):
        half = self._fade_duration
        if not self._fade_in:
            self._fade_alpha += dt / half
            if self._fade_alpha >= 1.0:
                self._fade_alpha = 1.0; self._fade_in = True; self._fade_build_pending = True
        elif getattr(self, '_fade_build_pending', False):
            self._fade_build_pending = False
            if self._fade_callback and not self._fade_done:
                self._fade_done = True
                self._post_fade_mode = "explore"
                self._fade_callback()
                if self.game_mode not in ("fade",):
                    self._post_fade_mode = self.game_mode
                self.game_mode = "fade"
        else:
            self._fade_alpha -= dt / half
            if self._fade_alpha <= 0.0:
                self._fade_alpha = 0.0; self._fading = False
                post = getattr(self, '_post_fade_mode', 'explore')
                self.game_mode = post
                if post == "explore": self.input.capture_mouse(True)

    def _stair_ground_y(self, px, pz):
        if not self.floor_state.has_stairs or abs(px) > STAIR_WIDTH / 2.0:
            return 0.0
        ground = 0.0
        for i in range(STAIR_COUNT):
            b = _stair_step_bounds(i)
            if b["z0"] <= pz <= b["z1"]:
                ground = max(ground, b["y1"])
        return ground

    def _resolve_stair_collisions(self, p):
        if not self.floor_state.has_stairs: return
        px, py, pz = p.world_pos
        pr = 0.5
        for i in range(STAIR_COUNT):
            b = _stair_step_bounds(i)
            if py >= b["y1"] - 0.08: continue
            cx = max(b["x0"], min(px, b["x1"]))
            cz = max(b["z0"], min(pz, b["z1"]))
            dx = px - cx; dz = pz - cz
            dist2 = dx*dx + dz*dz
            if dist2 >= pr*pr or dist2 < 1e-8: continue
            dist = math.sqrt(dist2); push = (pr - dist) / dist
            px += dx*push; pz += dz*push
        p.world_pos[0] = px; p.world_pos[2] = pz


    def _update_player_timers(self, dt):

        p = self.player

        if p.attack_cd > 0:
            p.attack_cd -= dt

        if p.attack_timer > 0:
            p.attack_timer -= dt
        else:
            p.is_attacking = False

        if p.combo_timer > 0:
            p.combo_timer -= dt
        else:
            p.combo_count = 0

        if p.invincible > 0:
            p.invincible -= dt

        if p.stats.shield_time > 0:
            p.stats.shield_time -= dt

    def _handle_player_jump(self):

        p = self.player

        if (
            "space" in self.input.held_keys
            and p.on_ground
        ):
            p.velocity[1] = p.JUMP_FORCE
            p.on_ground = False


    def _update_player_input(self, dt):

        p = self.player
        keys = self.input.held_keys

        move_x = 0.0
        move_z = 0.0

        fwd = self.camera.flat_forward
        rgt = self.camera.flat_right

        if "w" in keys:
            move_x += fwd[0]
            move_z += fwd[2]

        if "s" in keys:
            move_x -= fwd[0]
            move_z -= fwd[2]

        if "a" in keys:
            move_x -= rgt[0]
            move_z -= rgt[2]

        if "d" in keys:
            move_x += rgt[0]
            move_z += rgt[2]

        mag = math.sqrt(move_x * move_x + move_z * move_z)

        if mag > 0:
            move_x /= mag
            move_z /= mag

            p.facing_deg = math.degrees(
                math.atan2(move_x, move_z)
            )

        self.move_x = move_x
        self.move_z = move_z
        self.move_mag = mag

    def _move_player_horizontal(self, dt):

        p = self.player

        if not p.is_rolling:

            p.velocity[0] = self.move_x * p.WALK_SPEED
            p.velocity[2] = self.move_z * p.WALK_SPEED

            if (
                self.input.key_pressed("lshift")
                and p.on_ground
                and self.move_mag > 0
            ):
                p.is_rolling = True
                p.roll_timer = p.ROLL_TIME
                p.roll_dir = [self.move_x, self.move_z]
                p.invincible = p.ROLL_TIME

        else:

            p.roll_timer -= dt

            p.velocity[0] = p.roll_dir[0] * p.ROLL_SPEED
            p.velocity[2] = p.roll_dir[1] * p.ROLL_SPEED

            if p.roll_timer <= 0:
                p.is_rolling = False

        p.world_pos[0] += p.velocity[0] * dt
        p.world_pos[2] += p.velocity[2] * dt

    def _calculate_ground_height(self, player):

        ground_y = self._stair_ground_y(
            player.world_pos[0],
            player.world_pos[2]
        )

        for hitbox in self.floor_state.obstacles:

            if isinstance(hitbox, BoxHitbox):

                h = hitbox.get_surface_height(player)

                if h is not None:
                    ground_y = max(ground_y, h)
        return ground_y

    def _update_player_ground(self, dt):

        p = self.player

        ground_y = self._calculate_ground_height(p)

        if p.world_pos[1] > ground_y + 0.02:
            p.on_ground = False

        if not p.on_ground:
            p.velocity[1] += p.GRAVITY * dt

        p.world_pos[1] += p.velocity[1] * dt

        if p.world_pos[1] <= ground_y:

            p.world_pos[1] = ground_y
            p.velocity[1] = 0
            p.on_ground = True

    def _resolve_obstacle_collisions(self):

        p = self.player

        for hitbox in self.floor_state.obstacles:
            hitbox.resolve_player_collision(p)

    def _resolve_enemy_collisions(self):

        PLAYER_RADIUS = 0.5; ENEMY_RADIUS = 0.6
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

    def _update_player_visuals(self):

        p = self.player

        self.player_node.position = [
            p.world_pos[0],
            p.world_pos[1] + 0.5,
            p.world_pos[2]
        ]

        self.player_node.rotation[1] = p.facing_deg

        self.camera.update_third_person(
            p.world_pos
        )

    def _apply_room_bounds(self):

        p = self.player

        hw = ROOM_W / 2 - 0.6
        hd = ROOM_D / 2 - 0.6

        p.world_pos[0] = max(
            -hw,
            min(hw, p.world_pos[0])
        )

        north_limit = -hd

        if (
            self.floor_state.stair_locked
            and (
                self.current_floor != self.FLOOR_ENTRY
                or self.floor_state.barrier_active
            )
        ):
            north_limit = -9.5

        p.world_pos[2] = max(
            north_limit,
            min(hd, p.world_pos[2])
        )

    def _update_player(self, dt):

        self._update_player_timers(dt)

        self._update_player_input(dt)

        self._handle_player_jump()

        self._move_player_horizontal(dt)

        self._update_player_ground(dt)

        self._apply_room_bounds()

        self._resolve_obstacle_collisions()

        self._resolve_enemy_collisions()

        self._update_player_visuals()
                
    def _update_enemies(self, dt):
        for e, node in self.floor_state.enemies:
            if e.dead: continue
            e.update(self.player.world_pos, dt)
            node.position = list(e.world_pos)
            if not getattr(e, 'stationary', False):
                node.rotation[1] = e.facing_deg
            if e.aggro and self.player.invincible <= 0.0:
                dx = e.world_pos[0]-self.player.world_pos[0]
                dz = e.world_pos[2]-self.player.world_pos[2]
                if math.sqrt(dx*dx+dz*dz) < e.attack_range:
                    dmg = e.try_attack(self.player.stats)
                    if dmg > 0:
                        self.player.invincible = 0.5
                        self.player.is_taking_damage = True
                        self.player.reaction_timer = self.player.REACTION_TIME
                        self.hud.add_popup(f"-{dmg} HP", 1.2, (255,80,80))
                        if self.player.is_dead: self._trigger_death()

        ENEMY_RADIUS = 0.6
        enemies = [e for e, node in self.floor_state.enemies if not e.dead]
        for i in range(len(enemies)):
            for j in range(i + 1, len(enemies)):
                e1 = enemies[i]; e2 = enemies[j]
                dx = e1.world_pos[0]-e2.world_pos[0]; dz = e1.world_pos[2]-e2.world_pos[2]
                dist2 = dx*dx+dz*dz; min_dist = ENEMY_RADIUS * 2
                if dist2 < min_dist*min_dist and dist2 > 0.0001:
                    dist = math.sqrt(dist2); push = (min_dist - dist) / dist * 0.5
                    e1.world_pos[0] += dx*push; e1.world_pos[2] += dz*push
                    e2.world_pos[0] -= dx*push; e2.world_pos[2] -= dz*push

    # ── Render ────────────────────────────────────────────────────────────────

    def _render(self):
        glPolygonMode(GL_FRONT_AND_BACK, GL_LINE if self.wireframe else GL_FILL)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        self.scene.draw(self.phong_shader, self.camera)
        self._render_skinned_player()
        self._render_skinned_beatrice()
        glDisable(GL_DEPTH_TEST)
        self._draw_hud()
        if getattr(self, '_fade_alpha', 0.0) > 0.0:
            self.hud.draw_rect(0, 0, self.screen_w, self.screen_h, (0.0, 0.0, 0.0), min(1.0, self._fade_alpha))
        glEnable(GL_DEPTH_TEST)
        pygame.display.flip()

    def _render_skinned_player(self):
        if self.player_anim is None or self.player_skinned_mesh is None:
            return
        self._render_skinned(self.player_node, self.player_skinned_mesh, self.player_anim)

    def _render_skinned_beatrice(self):
        # Só desenha enquanto ela estiver visível (mesma flag usada por
        # _show_beatrice / _update_game) — evita custo de draw quando não
        # está em cena, igual ao comportamento do node antigo (.obj/esfera).
        if self.beatrice_anim is None or self.beatrice_skinned_mesh is None:
            return
        if self.beatrice_node is None or not self.beatrice_node.visible:
            return
        self._render_skinned(self.beatrice_node, self.beatrice_skinned_mesh, self.beatrice_anim)

    def _render_skinned(self, node, skinned_mesh, anim_controller):
        """Desenha um SkinnedMesh com skeleton animado (uBoneMatrices).
        Reaproveitado pelo player (Subaru) e pela Beatrice — ambos ficam
        fora do pipeline normal de Scene.draw(), que não sabe lidar com
        bone matrices / multi-primitive skinned."""
        shader = self.skinned_shader
        shader.use()
        shader.set_mat4("uView",        self.camera.view_matrix())
        shader.set_mat4("uProjection",  self.camera.projection_matrix(self.scene._aspect))
        shader.set_vec3("uViewPos",     self.camera.position)
        self.scene.light.apply(shader)

        model = node.model_matrix(None)
        shader.set_mat4("uModel",        model)
        shader.set_mat3("uNormalMatrix", mat3_normal_matrix(model))
        shader.set_mat4_array("uBoneMatrices", anim_controller.get_bone_matrices())

        shader.set_float("uAmbientStrength",  skinned_mesh.ka)
        shader.set_float("uDiffuseStrength",  skinned_mesh.kd)
        shader.set_float("uSpecularStrength", skinned_mesh.ks)
        shader.set_float("uShininess",        skinned_mesh.shininess)

        primitives = getattr(skinned_mesh, '_primitives', None)
        if primitives:
            for prim_smd in primitives:
                # Carrega a textura da primitive na primeira vez
                if not hasattr(prim_smd, '_texture_obj'):
                    if prim_smd.texture_path:
                        try:
                            prim_smd._texture_obj = Texture(prim_smd.texture_path)
                        except Exception:
                            prim_smd._texture_obj = None
                    else:
                        prim_smd._texture_obj = None

                # Cria o SkinnedMesh da primitive na primeira vez
                if not hasattr(prim_smd, '_skinned_mesh_obj'):
                    prim_smd._skinned_mesh_obj = SkinnedMesh(prim_smd)

                tex = prim_smd._texture_obj
                if tex:
                    tex.bind(0)
                    shader.set_bool("uUseTexture", True)
                    shader.set_int("uTexture", 0)
                else:
                    shader.set_bool("uUseTexture", False)
                    shader.set_vec3("uBaseColor", skinned_mesh.base_color)

                prim_smd._skinned_mesh_obj.draw()

                if tex:
                    tex.unbind()
        else:
            # Fallback: textura única do node
            if node.texture:
                node.texture.bind(0)
                shader.set_bool("uUseTexture", True)
                shader.set_int("uTexture", 0)
            else:
                shader.set_bool("uUseTexture", False)
                shader.set_vec3("uBaseColor", skinned_mesh.base_color)
            skinned_mesh.draw()
            if node.texture:
                node.texture.unbind()

    def _draw_hud(self):
        h = self.hud; sw = self.screen_w; sh = self.screen_h

        if self.game_mode == "story":
            h.draw_rect(0, 0, sw, sh, (0.0, 0.0, 0.05))
            if self.story_idx < len(self.story_lines):
                line  = self.story_lines[self.story_idx]
                color = (255,255,255) if line else (100,100,100)
                h.draw_text(line, sw//2, sh//2, 22, color, center=True)
            h.draw_text("[ENTER] próximo", sw//2, sh-40, 14, (150,150,150), center=True)
            return

        if self.game_mode == "credits":
            h.draw_rect(0, 0, sw, sh, (0.0, 0.0, 0.0))
            credits = [
                "Torre de Plêiades", "Re:Zero – Uma nova jornada", "",
                "Design & Desenvolvimento", "Vesuvio", "Gabriel Luiz", "",
                "Baseado em Re:Zero kara Hajimeru Isekai Seikatsu", "por Tappei Nagatsuki", "",
                "Kingdom Hearts – Heartless", "© Square Enix / Disney", "",
                "Personagens: Subaru, Emilia, Marluxia", "", "Obrigado por jogar!", "", "[ENTER] Menu Principal",
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

        if self.game_mode in ("menu", "combat"):
            pw, ph = 340, 240
            px = sw//2 - pw//2; py = sh//2 - ph//2
            h.draw_bar(px-12, py-12, pw+24, ph+24, 1.0, (0.04,0.04,0.10), (0.04,0.04,0.10))
            self.menus.draw(h, px, py)

        if self.combat:
            h.draw_combat_log(self.combat.log.recent(5))

        if self.game_mode == "rhythm":
            self._draw_rhythm_hud(h)

        if self.game_mode == "explore":
            floor_names = {
                self.FLOOR_ENTRY:    "Corredor de Entrada",
                self.FLOOR_PUZZLE:   "1º Andar – Puzzle",
                self.FLOOR_AERIAL:   "2º Andar – Combate Aéreo",
                self.FLOOR_RHYTHM:   "3º Andar – Ritmo",
                self.FLOOR_GAUNTLET: "Corredor Final",
                self.FLOOR_REST:     "Sala de Descanso",
                self.FLOOR_BOSS:     "Sala do Boss – Marluxia",
            }
            h.draw_text(floor_names.get(self.current_floor, ""), sw//2, 12, 16, (200,180,255), center=True)

            hint = "[WASD] Mover  [Espaço] Pular  [Z] Atacar  [E/Enter] Interagir  [ESC] Pausar"
            if self.current_floor == self.FLOOR_PUZZLE:
                hint = "[WASD] Mover  [Z] Ativar orbe (perto)  [X] Magia  [ESC] Pausar"
            if self.current_floor == self.FLOOR_RHYTHM:
                hint = "[Enter] Iniciar Ritmo  [Z] Bater no ritmo  [ESC] Pausar"
            submenu_open = self.hud.spell_menu_open or self.hud.item_menu_open or self.hud.skill_menu_open
            h.draw_text(hint, 10, sh - 92 - (204 if submenu_open else 0), 11, (120,120,120))

            if self.current_floor in (self.FLOOR_ENTRY, self.FLOOR_PUZZLE, self.FLOOR_AERIAL, self.FLOOR_RHYTHM, self.FLOOR_GAUNTLET):
                if self.floor_state.stair_locked:
                    h.draw_text("Passagem: TRANCADA", sw//2, 36, 14, (255,120,120), center=True)
                else:
                    h.draw_text("Passagem: LIBERADA — [E/Enter] para subir", sw//2, 36, 14, (120,255,140), center=True)

    def _draw_rhythm_hud(self, h):
        sw, sh = self.screen_w, self.screen_h
        bar_x, bar_y, bar_w, bar_h = sw//2 - 300, sh - 140, 600, 30
        h.draw_rect(bar_x, bar_y, bar_w, bar_h, (0.05,0.12,0.12))
        if self.rhythm_beats:
            total_t = self.rhythm_beats[-1] + 1.0
            cx = bar_x + int((self.rhythm_timer / total_t) * bar_w)
            h.draw_rect(cx-3, bar_y, 6, bar_h, (0.2,1.0,0.6))
        total_t = (self.rhythm_beats[-1] + 1.0) if self.rhythm_beats else 1.0
        for i, bt in enumerate(self.rhythm_beats):
            bx    = bar_x + int((bt / total_t) * bar_w)
            color = (0.0,0.6,0.0) if self.rhythm_hit[i] else (1.0,0.6,0.0)
            h.draw_rect(bx-4, bar_y, 8, bar_h, color)
        h.draw_text(f"Score: {self.rhythm_score}/{self.rhythm_total}", sw//2, sh-170, 18, (100,255,200), center=True)
        h.draw_text("[Z] no beat!", sw//2, sh-100, 16, (200,255,220), center=True)

    def _draw_menu_background(self, hud):
        sw, sh = self.screen_w, self.screen_h
        hud.draw_rect(0, 0, sw, sh, (0.03,0.03,0.08))
        hud.draw_rect(0, int(sh*0.15), sw, int(sh*0.1),  (0.06,0.04,0.12))
        hud.draw_rect(0, int(sh*0.25), sw, int(sh*0.12), (0.08,0.06,0.18))
        hud.draw_text("Torre de Plêiades",        sw//2, int(sh*0.10),  36, (235,220,255), bold=True, center=True)
        hud.draw_text("Re:Zero – uma nova jornada", sw//2, int(sh*0.175), 18, (200,180,220), center=True)
        rnd = 1
        for i in range(80):
            rnd=(rnd*1664525+1013904223)&0xFFFFFFFF; sx=(rnd>>8)%sw
            rnd=(rnd*1664525+1013904223)&0xFFFFFFFF; sy=(rnd>>8)%int(sh*0.55)
            hud.draw_text(".", sx, sy, 10, (220,220,255))

    def on_resize(self, w, h):
        self.screen_w = w; self.screen_h = h
        glViewport(0, 0, w, h)
        self.scene.set_aspect(w/h)
        self.hud.resize(w, h)

    # ── Main loop ─────────────────────────────────────────────────────────────

    def run(self):
        while True:
            dt = min(self.clock.tick(60)/1000.0, 0.05)
            self.input.update()
            if self.input.should_quit: break
            if self.input.resize_event:
                w, h = self.input.resize_event; self.on_resize(w, h)
            self._handle_global_input(dt)
            self._update_game(dt)
            self.scene.update(dt)
            self._render()
        pygame.quit()


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
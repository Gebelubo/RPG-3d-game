from src.here import _HERE

from src.config.paths import (SHADER_DIR)
from src.config.constants import (STAIR_WIDTH, 
                                  STAIR_COUNT, 
                                  BEATRICE_Y_OFFSET, 
                                  EMILIA_Y_OFFSET,
                                  SCREEN_H,
                                  SCREEN_W,
                                  TITLE,
                                  ROOM_D,
                                  ROOM_H,
                                  ROOM_W,
                                  MARLUXIA_Y_OFFSET, EMILIA_PHASE_OFFSETS)


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
sys.path.insert(0, _HERE)
from src.utils.image_utils import is_image_path

from src.engine.shader        import ShaderProgram
from src.engine.mesh          import ProceduralMesh, make_cube, make_plane, make_sphere
from src.engine.texture       import Texture, ProceduralTexture
from src.engine.camera        import Camera
from src.engine.scene         import Scene, SceneNode
from src.engine.skinned_mesh  import SkinnedMesh
from src.engine.input_manager import InputManager
from src.hud.hud               import HUD
from src.menu              import Menu, MenuItem, MenuManager
from src.engine.obstacle    import BoxHitbox
from src.engine.math3d        import mat3_normal_matrix
from src.hud.hud                  import HUD
from src.menu                 import Menu, MenuItem, MenuManager
from src.engine.sound_effects import Effects
from src.entities.enemy import Enemy, Boss
from src.entities.player import Player
from src.db.spell import SPELL_DB, SPELL_LIST
from src.db.item import ITEM_DB

from src.game.helper import Helper


from src.game.floor_state import FloorState





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
        self._helper = Helper()
        

    # ── Init ─────────────────────────────────────────────────────────────────

    def _init_window(self):
        pygame.init(); pygame.font.init()
        pygame.mixer.set_num_channels(32)
        pygame.mixer.music.load(os.path.join(_HERE, "assets", "music", "menu.mp3"))
        pygame.mixer.music.set_volume(0.2)
        pygame.mixer.music.play(-1, start=3.0)
        self.sounds = Effects()
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
        self._parkour_snapshot   = None
        self.void_fall_timer     = None
        self.player_texture      = None
        self.beatrice_node       = None
        self.beatrice_timer      = 0.0
        self.beatrice_skinned_mesh = None
        self.beatrice_anim         = None
        self.emilia_skinned_mesh   = None
        self.emilia_anim           = None
        self.marluxia_skinned_mesh = None
        self.marluxia_anim         = None
        self.rhythm_notes               = []
        self.rhythm_duration            = 90.0
        self.rhythm_timer               = 0.0
        self.rhythm_fall_time           = 1.6
        self.rhythm_window_perfect      = 0.05
        self.rhythm_window_good         = 0.12
        self.rhythm_window_ok           = 0.20
        self.rhythm_points_table        = {"perfect": 3, "good": 2, "ok": 1, "miss": 0}
        self.rhythm_max_points          = 0
        self.rhythm_score_points        = 0
        self.rhythm_last_feedback       = None
        self.rhythm_last_feedback_timer = 0.0
        self.rhythm_lane_flash          = [None, None, None, None]  # [cor, timer] por lane
        self.rhythm_hold_keys           = {}   # lane_idx -> {note_idx, held, required, quality}
        self.story_active        = False
        self.story_lines         = []
        self.story_idx           = 0
        self.story_timer         = 0.0
        self.story_callback      = None
        self.book_open = False  
        self.book_index = 1   
        self.book_max = 6
        self.book_dir = ""
        self._book_tex_cache: dict = {}
        self.credits_active      = False
        # ── Estado pós-boss: cutscene da Emilia ──────────────────────────────
        self.emilia_cutscene_phase = None   # None | "sleeping" | "waking" | "idle"
        self.emilia_stone_node     = None   # pedra/sarcófago no chão
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
        if getattr(self, 'emilia_skinned_mesh', None) is not None:
            self.emilia_skinned_mesh.destroy()
            self.emilia_skinned_mesh = None
        if getattr(self, 'marluxia_skinned_mesh', None) is not None:
            self.marluxia_skinned_mesh.destroy()
            self.marluxia_skinned_mesh = None
        # Destroi os skinned meshes de inimigos animados (Heartless / AerialKnocker)
        if hasattr(self, 'floor_state') and self.floor_state is not None:
            for e, _node in getattr(self.floor_state, 'enemies', []):
                sm = getattr(e, '_skinned_mesh', None)
                if sm is not None:
                    try:
                        sm.destroy()
                    except Exception:
                        pass
                    e._skinned_mesh = None
        self.player_anim    = None
        self.player_node    = None
        self.beatrice_anim  = None
        self.emilia_anim    = None
        self.emilia_cutscene_phase = None
        self.emilia_stone_node     = None
        self.marluxia_anim  = None
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

        skinned_node, skinned_mesh, anim_controller = self._helper.load_skinned_player(position=pos, rotation=(0, 180, 0))
        if skinned_node is not None:
            self.player_node         = skinned_node
            self.player_skinned_mesh = skinned_mesh
            self.player_anim         = anim_controller
        else:
            self.player_skinned_mesh = None
            self.player_anim         = None
            self.player_node = self._helper._load_obj_model(
                os.path.join(_HERE, "assets", "models", "Subaru", "Subaru.obj"),
                position=pos, rotation=(0, 180, 0), scale=(1.0, 1.0, 1.0)
            )
            if self.player_node is None:
                sv, si = make_sphere(0.45, 12, 12)
                pm = ProceduralMesh("subaru", sv, si, base_color=(0.2,0.35,0.6), ka=0.3, kd=0.8, ks=0.4, shininess=24)
                self.player_node = SceneNode("subaru", mesh=pm, position=list(pos))
            self.scene.add(self.player_node)

        bx, by, bz = pos[0] + 1.2, pos[1] + BEATRICE_Y_OFFSET, pos[2] - 0.5
        beat_skinned_node, beat_skinned_mesh, beat_anim = self._helper.load_skinned_beatrice(
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
            bnode = self._helper._load_obj_model(beat_path, position=(bx, by, bz), rotation=(0, 180, 0), scale=(1.0, 1.0, 1.0))
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

    def _build_floor_entry(self):
        pygame.mixer.music.stop()
        pygame.mixer.music.load(os.path.join(_HERE, "assets", "music", "tower.mp3"))
        pygame.mixer.music.play(-1)
        self._build_room(floor_color=(0.12,0.10,0.18), wall_color=(0.18,0.14,0.26))
        self._place_player(pos=(0,2,14))

        # Porta no fundo do corredor (Norte, Z=-13)
        dv, di = make_cube(1.0)
        dm = self._helper.make_box_mesh("door",3.0,4.0,0.3, color=(0.35,0.22,0.10), ka=0.2,kd=0.7,ks=0.3,shin=24)

        door_tex = Texture(os.path.join(_HERE, "assets", "models", "tower", "doorwood.jpeg"))

        door_node = SceneNode("door", mesh=dm, position=(0, 4.0,-15), scale=(1,1,1), texture=door_tex)
        self.scene.add(door_node)
        self.floor_state.door_node = door_node


        # Barreira mágica (inicialmente invisível até abrir a porta)
        bv, bi = make_cube(1.0)
        bm = self._helper.make_box_mesh("barrier",ROOM_W-2,ROOM_H-1,0.2, color=(0.2,0.1,0.8))
        barrier_node = SceneNode("barrier", mesh=bm, position=(0,ROOM_H/2-0.5,-9.0))
        barrier_node.visible = False
        self.scene.add(barrier_node)
        self.floor_state.barrier_node   = barrier_node
        self.floor_state.barrier_active = False


        # Escada no fundo (atrás da barreira)
        self._helper._build_stairs(self.scene, self.floor_state)
        self.floor_state.stair_locked = True


        # Decoração: obeliscos encostados nas paredes laterais (x=±8.5, fora da área de passagem)
        for sx in (-8.5, 8.5):
            self._helper._add_tower_deco(self.scene, self.floor_state, "obelisk",
                            position=(sx, 0.0, 0.0), scale=(1.5, 1.5, 1.5),
                            collision_radius=1.2)
        # Plataforma decorativa encostada na parede sul (atrás do spawn do player)
        self._helper._add_tower_deco(self.scene, self.floor_state, "platform",
                        position=(0.0, 0.0, 13.0), scale=(1.2, 1.2, 1.2),
                        collision_radius=1.5)

        #self.hud.add_popup("Avance pelo corredor...", 3.0, (200,200,255))
        #self.hud.add_popup("[E/Enter] perto da porta para abrir", 5.0, (180,200,255))


    def _build_floor_puzzle(self):
        # Só reinicia a música se não estiver tocando puzzle.mp3
        if not pygame.mixer.music.get_busy() or getattr(self, '_current_music', '') != 'puzzle':
            pygame.mixer.music.stop()
            pygame.mixer.music.load(os.path.join(_HERE, "assets", "music", "puzzle.mp3"))
            pygame.mixer.music.play(-1)
            self._current_music = 'puzzle'
        self._build_room(floor_color=(0.18,0.16,0.28), wall_color=(0.26,0.20,0.38))
        self._place_player(pos=(0,0,12))

        self.floor_state.obstacles = []
        self.floor_state.puzzle_guards = []
        self.floor_state.enemies = []
        self.floor_state.push_box = None

        frame_w, frame_h = 4.0, 2.25
        frame_cx, frame_cy = 0.0, ROOM_H/2 + 0.4
        fv, fi = make_plane(frame_w + 0.3, frame_h + 0.3, 1)
        self.scene.add(SceneNode("puzzle_frame",
            mesh=ProceduralMesh("puzzle_frame", fv, fi,
                base_color=(0.45,0.35,0.10), ka=0.6, kd=0.5, ks=0.6, shininess=32),
            position=(frame_cx, frame_cy, -8.92), rotation=(90,0,0)))
        bv, bi = make_plane(frame_w, frame_h, 1)
        self.scene.add(SceneNode("puzzle_backing",
            mesh=ProceduralMesh("puzzle_backing", bv, bi,
                base_color=(0.05,0.05,0.08), ka=0.5, kd=0.3, ks=0.0, shininess=1),
            position=(frame_cx, frame_cy, -8.91), rotation=(90,0,0)))

        self._helper._add_tower_deco(self.scene, self.floor_state, "platform",
                        position=(7.0, 1.0, 0.0), scale=(0.8, 0.8, 0.8),
                        collision_radius=1.5)
        self._helper._add_tower_deco(self.scene, self.floor_state, "platform",
                        position=(9.0, 4.0, -5.0), scale=(0.2, 0.2, 0.2),
                        collision_radius=1.5)
        self._helper._add_tower_deco(self.scene, self.floor_state, "platform",
                        position=(5.0, 3.0, -3.0), scale=(0.2, 0.2, 0.2),
                        collision_radius=1.5)
        self._helper._add_tower_deco(self.scene, self.floor_state, "platform",
                        position=(5.5, 5.0, -7.0), scale=(0.8, 0.2, 0.8),
                        collision_radius=1.5)

        piece_w, piece_h  = frame_w / 2, frame_h / 2
        pv, pi            = make_plane(piece_w, piece_h, 1)
        # Layout:
        #   idx 0 → sub-sala de parkour  (começa invisível, spawna lá)
        #   idx 1 → livre / parkour sala (5.5, 6, -7)
        #   idx 2 → em cima do botão     (-5.5, 2.5, 4)  precisa subir na caixa
        #   idx 3 → heartless            (-3, 1.4, 2)
        scatter_positions = [(0, 999, 0), (5.5, 6, -7), (-5.5, 2.5, 4), (-3, 1.4, 2)]
        mural_offsets     = [
            (-piece_w/2,  piece_h/2),
            ( piece_w/2,  piece_h/2),
            (-piece_w/2, -piece_h/2),
            ( piece_w/2, -piece_h/2),
        ]
        img_dir = os.path.join(_HERE, "assets", "images", "puzzle")

        self.puzzle_pieces = []
        for idx, spos in enumerate(scatter_positions):
            tex   = Texture(os.path.join(img_dir, f"piece_{idx}.png"))
            pm    = ProceduralMesh(f"puzzle_piece_{idx}", pv, pi,
                                   base_color=(1,1,1), ka=0.9, kd=0.6, ks=0.1, shininess=8)
            pnode = SceneNode(f"puzzle_piece_{idx}", mesh=pm, texture=tex,
                              position=list(spos), rotation=(90,0,0))
            if idx == 0:
                pnode.visible = False
            self.scene.add(pnode)
            mural_pos = (frame_cx + mural_offsets[idx][0],
                         frame_cy + mural_offsets[idx][1], -8.9)
            self.puzzle_pieces.append({
                "node":        pnode,
                "collected":   False,
                "scatter_pos": spos,
                "mural_pos":   mural_pos,
                "image_path":  os.path.join(img_dir, f"piece_{idx}.png"),
                "size":        (piece_w, piece_h),
            })
        self.floor_state.puzzle_solved = False

        # ── Heartless guardando a peça 3 (-3, 1.4, 2) ────────────────────
        guard_spawns = [(-2.0, 0.5, 1.2), (-0.6, 0.5, 3.2), (0.8, 0.5, 1.2)]
        self.floor_state.puzzle_guards = []
        for gpos in guard_spawns:
            ge, gn = self._helper._spawn_heartless(self.scene, gpos, level=3, stationary=True)
            ge.respawns_left = 0
            ge.aggro_range   = 4.0
            self.floor_state.puzzle_guards.append((ge, gn))
            self.floor_state.enemies.append((ge, gn))

        # ── Caixa spawna à esquerda do player, agora mais para frente (menos recuada)
        BOX_START  = [-7.0, 0.5, 12.0]
        BTN_POS    = (-5.5, 0.02, 4.0)
        BTN_RADIUS = 0.9

        bv2, bi2 = make_cube(1.0)
        box_mesh = ProceduralMesh("push_box", bv2, bi2,
                                  base_color=(0.55, 0.38, 0.18),
                                  ka=0.3, kd=0.8, ks=0.2, shininess=12)
        try:
            box_tex = Texture(os.path.join(_HERE, "assets", "models", "tower", "darkwood.jpg"))
        except Exception:
            box_tex = None
        box_node = SceneNode("push_box", mesh=box_mesh, texture=box_tex,
                             position=list(BOX_START), scale=[1.0, 1.0, 1.0])
        self.scene.add(box_node)

        btnv, btni = make_plane(BTN_RADIUS * 2, BTN_RADIUS * 2, 1)
        btn_mesh   = ProceduralMesh("push_btn", btnv, btni,
                                    base_color=(0.15, 0.70, 0.20),
                                    ka=0.5, kd=0.7, ks=0.1, shininess=4)
        btn_node   = SceneNode("push_btn", mesh=btn_mesh, position=list(BTN_POS))
        self.scene.add(btn_node)

        self.floor_state.push_box = {
            "node":       box_node,
            "pos":        [BOX_START[0], BOX_START[2]],
            "velocity":   [0.0, 0.0],
            "btn_pos":    (BTN_POS[0], BTN_POS[2]),
            "btn_radius": BTN_RADIUS,
            "btn_node":   btn_node,
            "activated":  False,
            "piece_idx":  2,
            "hit_count":  0,
            "hitbox":     BoxHitbox(x=BOX_START[0], y=BOX_START[1], z=BOX_START[2], width=1.0, height=1.0, depth=1.0),
        }

        # ── Portal para sub-sala (parede sul) ─────────────────────────────
        portal_mesh = self._helper.make_box_mesh("parkour_portal", 2.5, 3.0, 0.3,
                                    color=(0.2, 0.3, 0.6))
        portal_node = SceneNode("parkour_portal", mesh=portal_mesh,
                                position=(0, 1.5, 14.5))
        self.scene.add(portal_node)
        self.floor_state.parkour_portal_node = portal_node
        # Adiciona uma hitbox física para o portal de entrada da sub-sala
        try:
            self.floor_state.obstacles.append(
                BoxHitbox(x=0, y=1.5, z=14.5, width=2.5, height=3.0, depth=0.5))
        except Exception:
            pass

        self._helper._build_stairs(self.scene, self.floor_state)
        gm = self._helper.make_box_mesh("gate", 3.2, 2.0, 0.3, color=(0.5,0.4,0.1))
        gate_node = SceneNode("gate", mesh=gm, position=(0,1.0,-10.5))
        self.scene.add(gate_node)
        self.floor_state.barrier_node = gate_node

        #self.hud.add_popup("Junte os fragmentos espalhados pela sala!", 3.0, (200,220,255))
        #self.hud.add_popup("[Z] perto de cada fragmento para encaixá-lo no quadro", 4.0, (180,180,220))
        #self.hud.add_popup("Um fragmento está numa sala abaixo — volte pela entrada sul!", 5.0, (180,200,255))
        #self.hud.add_popup("Heartless guardam outro fragmento — derrote-os primeiro!", 5.5, (255,180,100))
        #self.hud.add_popup("Empurre a caixa [Z] até o botão verde e suba nela!", 6.0, (180,255,160))
        # Porta no fundo do corredor (Norte, Z=-15) — permite avançar ao subir as escadas
        dv, di = make_cube(1.0)
        dm = self._helper.make_box_mesh("door",3.0,4.0,0.3, color=(0.35,0.22,0.10), ka=0.2,kd=0.7,ks=0.3,shin=24)
        try:
            door_tex = Texture(os.path.join(_HERE, "assets", "models", "tower", "doorwood.jpeg"))
        except Exception:
            door_tex = None
        door_node = SceneNode("door", mesh=dm, position=(0, 4.0,-15), scale=(1,1,1), texture=door_tex)
        self.scene.add(door_node)
        self.floor_state.door_node = door_node
        # Se o puzzle já estiver resolvido, garante que a barreira não reapareça
        if getattr(self.floor_state, 'puzzle_solved', False):
            self._disable_barrier()

    def _build_parkour_room(self):
        """Constrói a sub-sala de parkour sobre o void."""
        # Salva o estado atual do puzzle antes de limpar a cena
        self._parkour_snapshot = {
            "puzzle_state": [(p["collected"], p["scatter_pos"]) for p in self.puzzle_pieces],
            "box_state": None,
            "enemy_state": [(e.world_pos.copy(), e.dead) for e, _ in getattr(self.floor_state, 'puzzle_guards', [])],
        }
        pb = getattr(self.floor_state, 'push_box', None)
        if pb is not None:
            self._parkour_snapshot["box_state"] = {
                "pos": pb["pos"].copy(),
                "velocity": pb["velocity"].copy(),
                "activated": pb["activated"],
                "hit_count": pb["hit_count"],
                "btn_color": getattr(pb["btn_node"].mesh, 'base_color', None),
            }

        self._clear_scene()
        self.floor_state.in_parkour_room = True
        pos = [0.0, 0.4, 12.0]  # Começa no topo da plataforma de entrada
        skinned_node, skinned_mesh, anim = self._helper.load_skinned_player(position=pos, rotation=(0, 180, 0))
        if skinned_node is not None:
            self.player_node = skinned_node
            self.player_skinned_mesh = skinned_mesh
            self.player_anim = anim
            # NÃO adicionar à cena — será renderizado por _render_skinned_player()
        else:
            self.player_node = None

        glClearColor(0.01, 0.01, 0.03, 1.0)

        wall_color  = (0.20, 0.16, 0.30)
        ceil_color  = (0.12, 0.10, 0.18)
        pv_ew, pi_ew = make_plane(ROOM_D, ROOM_H * 2, divs=6, tile_u=2, tile_v=2)
        wall_texture = Texture(os.path.join(_HERE, "assets", "models", "tower", "stone_bricks.jpg"))
        for name, pos, rot in [
            ("pk_wall_w", (-ROOM_W/2, ROOM_H, 0), (90,  90, 0)),
            ("pk_wall_e", ( ROOM_W/2, ROOM_H, 0), (90, -90, 0)),
        ]:
            wm = ProceduralMesh(name, pv_ew, pi_ew, base_color=wall_color,
                                ka=0.25, kd=0.75, ks=0.1, shininess=8)
            self.scene.add(SceneNode(name, mesh=wm, texture=wall_texture,
                                     position=pos, rotation=rot))

        pv_ns, pi_ns = make_plane(ROOM_W, ROOM_H * 2, divs=6, tile_u=2, tile_v=2)
        for name, pos, rot in [
            ("pk_wall_n", (0, ROOM_H, -ROOM_D/2), ( 90, 0, 0)),
            ("pk_wall_s", (0, ROOM_H,  ROOM_D/2), (-90, 180, 0)),
        ]:
            wm = ProceduralMesh(name, pv_ns, pi_ns, base_color=wall_color,
                                ka=0.25, kd=0.75, ks=0.1, shininess=8)
            self.scene.add(SceneNode(name, mesh=wm, texture=wall_texture,
                                     position=pos, rotation=rot))

        cv, ci = make_plane(ROOM_W, ROOM_D, 20, tile_u=ROOM_W/2, tile_v=ROOM_D/2)
        cm = ProceduralMesh("pk_ceil", cv, ci, base_color=ceil_color,
                            ka=0.2, kd=0.6, ks=0.05, shininess=4)
        ceil_tex = Texture(os.path.join(_HERE, "assets", "models", "tower", "floor.jpeg"))
        self.scene.add(SceneNode("pk_ceil", mesh=cm, texture=ceil_tex,
                                  position=(0, ROOM_H * 2, 0), rotation=(180, 0, 0)))

        entry_plat = self._helper.make_box_mesh("pk_entry", 4.0, 0.4, 3.0, color=(0.45,0.40,0.35))
        self.scene.add(SceneNode("pk_entry", mesh=entry_plat,
                                  position=(0, 0.2, 12.0),
                                  texture=Texture(os.path.join(_HERE, "assets", "models", "tower", "tower_stone.png"))))
        self.floor_state.obstacles.append(
            BoxHitbox(x=0, y=0.0, z=12.0, width=4.0, height=0.4, depth=3.0))

        # Plataformas do parkour: afastadas progressivamente da entrada e um pouco mais altas
        plat_defs = [
            ("pk_plat0", ( 1.5, 1.4,  6.6), 3.0, 0.4, 3.0),
            ("pk_plat1", (-2.4, 2.1,  3.2), 3.0, 0.4, 3.0),
            ("pk_plat2", ( 1.8, 3.0, -2.2), 3.0, 0.4, 3.0),
        ]
        plat_tex = Texture(os.path.join(_HERE, "assets", "models", "tower", "tower_stone.png"))
        for pname, (px, py, pz), pw, ph, pd in plat_defs:
            pm2 = self._helper.make_box_mesh(pname, pw, ph, pd, color=(0.40, 0.35, 0.50))
            self.scene.add(SceneNode(pname, mesh=pm2, texture=plat_tex,
                                      position=(px, py, pz)))
            self.floor_state.obstacles.append(
                BoxHitbox(x=px, y=py - ph/2, z=pz, width=pw, height=ph, depth=pd))

        final_tex = Texture(os.path.join(_HERE, "assets", "models", "tower", "tower_stone.png"))
        fm = self._helper.make_box_mesh("pk_final", 3.5, 0.4, 3.5, color=(0.35, 0.30, 0.50))
        # Plataforma final ajustada para manter espaçamento de 5.4 unidades
        self.scene.add(SceneNode("pk_final", mesh=fm, texture=final_tex,
                                  position=(0, 3.8, -7.2)))
        self.floor_state.obstacles.append(
            BoxHitbox(x=0, y=3.6, z=-7.2, width=3.5, height=0.4, depth=3.5))

        # ── Portal de volta (parede norte/entrada) ─────────────────────
        return_portal = self._helper.make_box_mesh("pk_return", 2.5, 3.0, 0.3, color=(0.6, 0.3, 0.2))
        # Recua o portal de retorno para não ficar no centro da plataforma inicial
        self.scene.add(SceneNode("pk_return", mesh=return_portal, position=(0, 1.5, 14.0)))
        self.floor_state.parkour_return_pos = (0, 0.4, 14.5)
        # Adiciona uma hitbox física para o portal (colisão)
        try:
            self.floor_state.obstacles.append(
                BoxHitbox(x=0, y=1.5, z=14.0, width=2.5, height=3.0, depth=0.5))
        except Exception:
            pass

        # Recriar a pe\u00e7a 0 na sub-sala se ainda n\u00e3o foi coletada
        if self.puzzle_pieces and not self.puzzle_pieces[0]["collected"]:
            piece0 = self.puzzle_pieces[0]
            piece_w, piece_h = piece0["size"]
            pv0, pi0 = make_plane(piece_w, piece_h, 1)
            tex0 = None
            if piece0.get("image_path"):
                tex0 = Texture(piece0["image_path"])
            mesh0 = ProceduralMesh("puzzle_piece_0", pv0, pi0,
                                   base_color=(1,1,1), ka=0.9, kd=0.6, ks=0.1, shininess=8)
            piece0_node = SceneNode("puzzle_piece_0", mesh=mesh0, texture=tex0,
                                    position=[0.0, 5.8, -7.2], rotation=(90,0,0))
            piece0_node.visible = True
            self.scene.add(piece0_node)
            piece0["node"] = piece0_node
            piece0["scatter_pos"] = (0.0, 5.8, -7.2)

        self.scene.light.orbit     = False
        self.scene.light.pos       = [0.0, ROOM_H * 1.5, 0.0]
        self.scene.light.intensity = 1.0
        self.scene.light.color     = np.array([0.6, 0.5, 0.9], dtype=np.float32)

        self.player.world_pos = [0.0, 0.4, 12.0]  # Começa no topo da plataforma de entrada
        self.player.velocity  = [0.0, 0.0, 0.0]
        self.player.on_ground = True
        self.player_node.position = list(self.player.world_pos)

        #self.hud.add_popup("Sub-sala de parkour!", 2.5, (180, 200, 255))
        #self.hud.add_popup("Cuidado com o void — cair é morte!", 3.0, (255, 100, 100))
        #self.hud.add_popup("Pule pelas plataformas e pegue o fragmento!", 3.5, (200, 220, 255))

    def _build_floor_aerial(self):
        pygame.mixer.music.stop()
        pygame.mixer.music.load(os.path.join(_HERE, "assets", "music", "combat.mp3"))
        pygame.mixer.music.play(-1)
        self._build_room(floor_color=(0.16,0.14,0.22), wall_color=(0.24,0.20,0.34))
        self._place_player(pos=(0,0,12))

        # Porta no fundo do corredor (Norte, Z=-15) — restaurada para navegação entre andares
        dv, di = make_cube(1.0)
        dm = self._helper.make_box_mesh("door",3.0,4.0,0.3, color=(0.35,0.22,0.10), ka=0.2,kd=0.7,ks=0.3,shin=24)
        try:
            door_tex = Texture(os.path.join(_HERE, "assets", "models", "tower", "doorwood.jpeg"))
        except Exception:
            door_tex = None
        door_node = SceneNode("door", mesh=dm, position=(0, 4.0,-15), scale=(1,1,1), texture=door_tex)
        self.scene.add(door_node)
        self.floor_state.door_node = door_node

        for px, pz in [(-4,0),(4,0),(0,4)]:
            e, n = self._helper._spawn_heartless(self.scene, (px,0.5,pz), level=3)
            e.respawns_left = 0
            self.floor_state.enemies.append((e,n))
        for px, pz in [(-3,2),(3,2),(0,-2)]:
            e, n = self._helper._spawn_heartless(self.scene, (px,3.0,pz), scale=(0.0125,0.0125,0.0125), level=3, flying=True)
            e.is_flying = True; e.respawns_left = 0; e.aggro_range = 8.0
            self.floor_state.enemies.append((e,n))
        self.floor_state.stair_locked = True

        self._helper._build_stairs(self.scene, self.floor_state)
        gm = self._helper.make_box_mesh("gate_a", 3.2, 2.0, 0.3, color=(0.5,0.3,0.1))
        gate_node = SceneNode("gate_a", mesh=gm, position=(0,1.0,-10.5))
        self.scene.add(gate_node)
        self.floor_state.barrier_node = gate_node

        #self.hud.add_popup("Cuidado com os Heartless voadores!", 3.0, (255,200,100))
        #self.hud.add_popup("[Espaço] pra pular e alcançá-los!", 4.0, (200,200,255))

    def _build_floor_rhythm(self):
        pygame.mixer.music.stop()
        pygame.mixer.music.load(os.path.join(_HERE, "assets", "music", "rythm.mp3"))
        pygame.mixer.music.stop()  # garante que não toque antes do obelisco ser ativado
        self._build_room(floor_color=(0.10,0.18,0.20), wall_color=(0.16,0.26,0.30))
        self._place_player(pos=(0,0,12))

        # ── Obelisco central — interagir com [E/Enter] inicia o minigame ──
        obv, obi = make_cube(1.0)
        ob_mesh = self._helper.make_box_mesh("rhythm_obelisk", 1.2, 3.2, 1.2, color=(0.25, 0.55, 0.60))
        ob_node = SceneNode("rhythm_obelisk", mesh=ob_mesh, position=(0.0, 1.6, -1.0))
        self.scene.add(ob_node)
        self.floor_state.rhythm_obelisk_node = ob_node
        self.floor_state.rhythm_obelisk_pos  = (0.0, -1.0)  # (x, z) p/ checagem de distância
        try:
            self.floor_state.obstacles.append(
                BoxHitbox(x=0.0, y=1.6, z=-1.0, width=1.2, height=3.2, depth=1.2))
        except Exception:
            pass

        self._helper._build_stairs(self.scene, self.floor_state)
        gm = self._helper.make_box_mesh("gate_r", 3.2, 2.0, 0.3, color=(0.1,0.4,0.5))
        gate_node = SceneNode("gate_r", mesh=gm, position=(0,1.0,-10.5))
        self.scene.add(gate_node)
        self.floor_state.barrier_node = gate_node
        self.floor_state.rhythm_done  = False

        # Porta no fundo do corredor (Norte, Z=-15) — permite avançar ao subir as escadas
        dv, di = make_cube(1.0)
        dm = self._helper.make_box_mesh("door",3.0,4.0,0.3, color=(0.35,0.22,0.10), ka=0.2,kd=0.7,ks=0.3,shin=24)
        try:
            door_tex = Texture(os.path.join(_HERE, "assets", "models", "tower", "doorwood.jpeg"))
        except Exception:
            door_tex = None
        door_node = SceneNode("door", mesh=dm, position=(0, 4.0,-15), scale=(1,1,1), texture=door_tex)
        self.scene.add(door_node)
        self.floor_state.door_node = door_node

        for cx, cz in [(-8.0,-2.0),(-8.0,2.0),(8.0,-2.0),(8.0,2.0)]:
            self._helper._add_tower_deco(self.scene, self.floor_state, "crystal", position=(cx, 0.0, cz), scale=(1.0,1.0,1.0), collision_radius=0.9)

        #self.hud.add_popup("Um obelisco antigo brilha no centro da sala...", 4.0, (100,255,200))
        #self.hud.add_popup("[E/Enter] perto dele para começar o ritual rítmico", 4.5, (200,255,220))

    def _build_floor_gauntlet(self):
        pygame.mixer.music.stop()
        pygame.mixer.music.load(os.path.join(_HERE, "assets", "music", "combat.mp3"))
        pygame.mixer.music.play(-1)
        self._build_room(floor_color=(0.20,0.08,0.08), wall_color=(0.28,0.12,0.12))
        self._place_player(pos=(0,0,12))

        wave1 = []
        for px, pz in [(-5,2),(5,2),(0,0),(-3,-2),(3,-2)]:
            e, n = self._helper._spawn_heartless(self.scene, (px,0.5,pz), level=4)
            e.respawns_left = 0; wave1.append((e,n))
        wave2 = []
        for px, pz in [(-4,1),(4,1)]:
            e, n = self._helper._spawn_heartless(self.scene, (px,0.5,pz), level=4)
            e.respawns_left = 0; wave2.append((e,n))
        for px, pz in [(0,2),(-3,-1),(3,-1)]:
            e, n = self._helper._spawn_heartless(self.scene, (px,3.0,pz), scale=(0.0125,0.0125,0.0125), level=4, flying=True)
            e.is_flying = True; wave2.append((e,n)); n.visible = False

        self.floor_state.gauntlet_waves = [wave1, wave2]
        self.floor_state.gauntlet_idx   = 0
        self.floor_state.enemies        = list(wave1)
        self.floor_state.stair_locked   = True

        # Constrói escadas para permitir subir quando corredor liberar
        self._helper._build_stairs(self.scene, self.floor_state)

        # Porta/portal visual + referência de barrier_node e hitbox (posicionada como nos outros andares)
        pm = self._helper.make_box_mesh("portal_gate", 3.2, 2.0, 0.3, color=(0.5,0.1,0.1))
        gate_node = SceneNode("portal_gate", mesh=pm, position=(0,1.0,-10.5))
        self.scene.add(gate_node)
        self.floor_state.barrier_node = gate_node
        # adiciona hitbox físico para bloquear até a barreira cair (mesma posição dos outros andares)
        try:
            self.floor_state.obstacles.append(
                BoxHitbox(x=0, y=1.0, z=-10.5, width=3.2, height=2.0, depth=0.5))
        except Exception:
            pass

        # Porta no fundo do corredor (Norte, Z=-15) — permite avançar após limpar
        dv, di = make_cube(1.0)
        dm = self._helper.make_box_mesh("door",3.0,4.0,0.3, color=(0.35,0.22,0.10), ka=0.2,kd=0.7,ks=0.3,shin=24)
        try:
            door_tex = Texture(os.path.join(_HERE, "assets", "models", "tower", "doorwood.jpeg"))
        except Exception:
            door_tex = None
        door_node = SceneNode("door", mesh=dm, position=(0, 4.0,-15), scale=(1,1,1), texture=door_tex)
        self.scene.add(door_node)
        self.floor_state.door_node = door_node

        #self.hud.add_popup("Corredor Final! Sobreviva!", 3.0, (255,100,100))

    def _build_floor_rest(self):
        pygame.mixer.music.stop()
        pygame.mixer.music.load(os.path.join(_HERE, "assets", "music", "tower.mp3"))
        pygame.mixer.music.play(-1)
        self._build_room(floor_color=(0.15,0.22,0.18), wall_color=(0.20,0.30,0.24), ceil_color=(0.12,0.20,0.16))
        self._place_player(pos=(0,0,8))
        rest_tex_path = os.path.join(_HERE, "assets", "models", "tower", "restfloor.avif")
        try:
            rest_tex = Texture(rest_tex_path)
        except Exception:
            rest_tex = None

        # Reaplica a textura no chão e nas paredes já criadas por _build_room.
        if rest_tex is not None:
            for node in getattr(self.scene, "nodes", []):
                if node.name in ("floor", "wall_n", "wall_s", "wall_e", "wall_w", "ceiling"):
                    node.texture = rest_tex
        
        # ── Mesa central com livro ──
        table_w, table_h, table_d = 2.0, 1.0, 1.2
        table_pos = (0, table_h/2, 0)
        table_mesh = self._helper.make_box_mesh("rest_table", table_w, table_h, table_d, color=(0.5,0.5,0.5))
        table_node = SceneNode("rest_table", mesh=table_mesh, position=table_pos, texture=rest_tex)
        self.scene.add(table_node)
        self.floor_state.obstacles.append(
            BoxHitbox(x=table_pos[0], y=table_pos[1], z=table_pos[2],
                      width=table_w, height=table_h, depth=table_d))
        
        # Livro em cima da mesa
        book_tex_path = os.path.join(_HERE, "assets", "models", "tower", "rune_crystal.png")
        try:
            book_tex = Texture(book_tex_path)
        except Exception:
            book_tex = None

        book_w, book_h, book_d = 0.5, 0.1, 0.4
        book_pos = (0, table_h + book_h/2, 0)
        book_mesh = self._helper.make_box_mesh("rest_book", book_w, book_h, book_d, color=(0.8,0.8,0.9))
        book_node = SceneNode("rest_book", mesh=book_mesh, position=book_pos, texture=book_tex)
        self.scene.add(book_node)

        # Guarda referência e estado do livro/relatórios no floor_state
        self.floor_state.rest_book_node   = book_node
        self.floor_state.rest_book_pos    = book_pos
        self.floor_state.rest_book_radius = 1.5  # raio de interação
        self.floor_state.report_open      = False
        self.floor_state.report_index     = 1     # marluxia_report1.png ... report6.png
        self.floor_state.report_max       = 6
        self.floor_state.report_dir       = os.path.join(_HERE, "assets", "images", "marluxia_reports")

        self.scene.light.intensity = 0.8
        self.scene.light.color     = np.array([0.7,1.0,0.8], dtype=np.float32)
        self.player.stats.hp = self.player.stats.max_hp
        self.player.stats.mp = self.player.stats.max_mp
        self._helper.save_game(self.current_floor, self.player)
        self.floor_state.stair_locked = False
        #self.hud.add_popup("Sala de Descanso", 3.0, (100,255,180))
        #self.hud.add_popup("HP e MP recuperados! Jogo salvo.", 3.5, (180,255,200))
        #self.hud.add_popup("Avance para enfrentar o boss final...", 4.5, (255,220,200))

        # Garante escadas e porta com textura/colisão para avançar ao boss
        self._helper._build_stairs(self.scene, self.floor_state)
        dv, di = make_cube(1.0)
        dm = self._helper.make_box_mesh("boss_door",3.0,4.0,0.3, color=(0.6,0.2,0.6))
        try:
            door_tex = Texture(os.path.join(_HERE, "assets", "models", "tower", "doorwood.jpeg"))
        except Exception:
            door_tex = None
        door_node = SceneNode("boss_door", mesh=dm, position=(0,4.0,-15), texture=door_tex)
        self.scene.add(door_node)
        self.floor_state.door_node = door_node
        try:
            self.floor_state.obstacles.append(BoxHitbox(x=0, y=2.0, z=-15.0, width=3.0, height=4.0, depth=0.5))
        except Exception:
            pass

    def _build_floor_boss(self):
        pygame.mixer.music.stop()
        pygame.mixer.music.load(os.path.join(_HERE, "assets", "music", "boss.mp3"))
        pygame.mixer.music.play(-1)
        self._build_room(floor_color=(0.20,0.05,0.20), wall_color=(0.28,0.08,0.28), ceil_color=(0.15,0.04,0.18))
        self._place_player(pos=(0,0,10))
        self.floor_state.stair_locked  = False
        self.scene.light.color         = np.array([1.0,0.5,1.0], dtype=np.float32)
        self.scene.light.intensity     = 1.5

        # ── Pedra/sarcófago onde a Emilia está deitada ───────────────────────
        # Uma laje plana no chão que serve de "cama" para a animação sleeping.
        # Tem física (BoxHitbox) para o player poder subir nela se quiser.
        stone_w, stone_h, stone_d = 1.8, 0.25, 3.2
        em_stone_pos = (3.5, stone_h / 2, -10.0)
        stone_mesh = self._helper.make_box_mesh(
            "emilia_stone", stone_w, stone_h, stone_d,
            color=(0.45, 0.40, 0.55), ka=0.25, kd=0.65, ks=0.15, shin=12
        )
        try:
            stone_tex = Texture(os.path.join(_HERE, "assets", "models", "tower", "stone_bricks.jpg"))
        except Exception:
            stone_tex = None
        stone_node = SceneNode(
            "emilia_stone", mesh=stone_mesh,
            position=list(em_stone_pos), texture=stone_tex
        )
        self.scene.add(stone_node)
        self.emilia_stone_node = stone_node
        self.floor_state.obstacles.append(
            BoxHitbox(
                x=em_stone_pos[0], y=em_stone_pos[1], z=em_stone_pos[2],
                width=stone_w, height=stone_h, depth=stone_d
            )
        )

        # ── Emilia deitada em cima da pedra (animação sleeping) ──────────────
        # Y = topo da pedra + offset do modelo
        self._emilia_base_pos = (3.5, stone_h + EMILIA_Y_OFFSET, -10.0)
        em_pos = self._emilia_base_pos
        em_node, em_skinned, em_anim = self._helper.load_skinned_emilia(
            position=em_pos, rotation=(0, 0, 0)
        )
        if em_node is not None:
            self.emilia_skinned_mesh = em_skinned
            self.emilia_anim         = em_anim
            if self.emilia_anim is not None:
                self.emilia_anim.play("sleeping", restart_if_same=True)
            self.emilia_cutscene_phase = "sleeping"
            self._apply_emilia_phase_offset("sleeping", em_node=em_node)
        else:
            self.emilia_skinned_mesh = None
            self.emilia_anim         = None
            self.emilia_cutscene_phase = None
            em_node = self._helper._load_obj_model(
                os.path.join(_HERE, "assets", "models", "Emilia", "emilia.obj"),
                position=em_pos, rotation=(0, 0, 0), scale=(1.0, 1.0, 1.0)
            )
            if em_node:
                self.scene.add(em_node)
        self.floor_state.emilia_node = em_node

        # Marluxia (boss) — tenta skinned mesh primeiro
        marl_pos = (0, MARLUXIA_Y_OFFSET, -8)
        mk_node, mk_skinned, mk_anim = self._helper.load_skinned_marluxia(
            position=marl_pos, rotation=(0, 180, 0)
        )
        if mk_node is not None:
            boss_node = mk_node
            self.marluxia_skinned_mesh = mk_skinned
            self.marluxia_anim         = mk_anim
        else:
            self.marluxia_skinned_mesh = None
            self.marluxia_anim         = None
            # Fallback: .obj ou esfera roxa
            bv, bi = make_sphere(0.9, 16, 16)
            bm = ProceduralMesh("marluxia", bv, bi, base_color=(0.7, 0.1, 0.8),
                                ka=0.4, kd=0.7, ks=0.8, shininess=96)
            boss_node = SceneNode("marluxia", mesh=bm, position=list(marl_pos))
            m_path = os.path.join(_HERE, "assets", "models", "Marluxia", "Marluxia.obj")
            if os.path.exists(m_path):
                try:
                    loaded = self._helper._load_obj_model(m_path, position=(0, 0, -8), rotation=(90, 0, 0), scale=(0.014, 0.014, 0.014))
                except Exception as exc:
                    print(f"Falha ao carregar Marluxia.obj, usando fallback: {exc}")
                    loaded = None
                if loaded:
                    boss_node = loaded
            self.scene.add(boss_node)

        boss_enemy = Boss("Marluxia", level=8, world_pos=[0.0, 0.0, -8.0])
        boss_enemy.stats.max_hp  = 400
        boss_enemy.stats.hp      = 400
        boss_enemy.stats.atk     = 22
        boss_enemy.stats.defense = 8
        boss_enemy.aggro_range   = 12.0
        boss_enemy.attack_range  = 2.2
        boss_enemy.respawns_left = 0
        boss_enemy.spawn_pos     = [0.0, 0.0, -8.0]
        boss_enemy._skinned_mesh = mk_skinned
        boss_enemy._anim         = mk_anim
        boss_enemy._anim_state   = None
        boss_enemy._y_offset     = MARLUXIA_Y_OFFSET
        self.floor_state.boss      = boss_enemy
        self.floor_state.boss_node = boss_node
        self.floor_state.enemies   = [(boss_enemy, boss_node)]

        self._helper._add_tower_deco(self.scene, self.floor_state, "tower",    position=(0.0, 0.0, -13.5), scale=(1.0, 1.0, 1.0), collision_radius=1.8)
        for cx, cz in [(-8.5, -5.0), (8.5, -5.0), (-8.5, 5.0), (8.5, 5.0)]:
            self._helper._add_tower_deco(self.scene, self.floor_state, "crystal", position=(cx, 0.0, cz), scale=(1.4, 1.4, 1.4), collision_radius=1.0)
        for px in (-8.5, 8.5):
            self._helper._add_tower_deco(self.scene, self.floor_state, "platform", position=(px, 0.0, 0.0), scale=(1.0, 1.0, 1.0), collision_radius=1.2)

        self.hud.add_popup("BOSS: MARLUXIA", 3.0, (255, 80, 255))
        self.hud.add_popup("Salve Emilia!", 3.5, (255, 200, 255))

    # ── Story / Cutscene ─────────────────────────────────────────────────────

    def _start_story(self):
        self._show_story([
            "src/assets/images/prologue_letter.png",
        ], callback=self._story_done)

    def _show_story(self, lines, callback=None):
        self.story_active   = True
        self.story_lines    = lines
        self.story_idx      = 0
        self.story_timer    = 0.0
        self.story_callback = callback
        self.game_mode      = "story"
        self.input.capture_mouse(False)

    def _open_book(self):
        self.book_open = True
        self.book_dir = self.floor_state.report_dir
        self.book_index = self.floor_state.report_index
        self.book_max = self.floor_state.report_max
        self.game_mode = "book"
        self.input.capture_mouse(False)

    def _close_book(self):
        self.book_open = False
        self.floor_state.report_index = self.book_index
        self.game_mode = "explore"
        self.input.capture_mouse(True)

    def _book_page_texture(self, index: int):
        path = os.path.join(
            self.book_dir,
            f"marluxia_report{index}.png"
        )

        if path not in self._book_tex_cache:

            try:
                self._book_tex_cache[path] = Texture(path, max_size=None)
            except Exception:
                self._book_tex_cache[path] = None
        return self._book_tex_cache[path]

    def _story_done(self):
        self.story_active = False
        self.game_mode    = "explore"
        self.input.capture_mouse(True)

    def _show_ending(self):
        # Mantido por compatibilidade; a cutscene real é orquestrada por
        # _on_boss_defeated usando callbacks encadeados.
        self._on_boss_defeated()

    def _apply_emilia_phase_offset(self, phase: str, em_node=None):
        """Aplica o offset de posição da fase atual da cutscene da Emilia,
        sempre a partir da posição base (nunca soma incrementalmente —
        evita acúmulo de erro se a fase for reaplicada)."""

        if em_node is None:
            em_node = getattr(self.floor_state, 'emilia_node', None)
        base = getattr(self, '_emilia_base_pos', None)
        if em_node is None or base is None:
            return
        off = EMILIA_PHASE_OFFSETS.get(phase, (0.0, 0.0, 0.0))
        em_node.position[0] = base[0] + off[0]
        em_node.position[1] = base[1] + off[1]
        em_node.position[2] = base[2] + off[2]

    def _show_ending_part2(self, callback):
        """Segunda caixa de diálogo: Emilia diz 'Subaru?' e lembra."""
        self._show_story([
            '"Subaru...?"',
            "",
            "A voz dela surge baixa e hesitante.",
            "",
            "Por um instante, Emilia apenas encara aquele momento, como se tentasse entender se aquilo era real.",
            "",
            "Mas então ela sente."
            "",
            "Mesmo durante todo aquele tempo, ela continuou carregando cada memória e cada sentimento em seu coração.",
            "",
            "As lembranças, os sentimentos e as promessas que compartilhou com Subaru ainda estavam lá.",
            "",
            "Ela estava de volta."
        ], callback=callback)

    def _show_ending_part3(self, callback):
        """Terceira caixa de diálogo"""
        self._show_story([
            '"Obrigada por me salvar, Subaru."',
            "",
            "Sob o cenário silencioso da torre, um momento de paz finalmente era compartilhado."
            "",
            "Tudo o que aconteceu até aquele ponto... cada batalha, cada sacrifício e cada escolha...",
            "existiram apenas para que esse momento pudesse acontecer.",
            "",
            "Pois esta é a história de um garoto inseguro.",
            "",
            "Um garoto que precisou se perder, cair e continuar seguindo em frente.",
            "",
            "Que suportou dores que ninguém deveria carregar, apenas para conseguir ficar ao lado da garota que amava.",
            "",
            "Esta é apenas a história de um garoto que se esforçava para isso",

            "— FIM —",
            "",
            "— Pressione ENTER para os créditos —",
        ], callback=callback)

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
            floor = self._helper.load_game(self.player)
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
            self._helper.save_game(self.current_floor, self.player)
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

    def _trigger_death(self):
        self.game_mode = "death"; self.death_timer = 3.5; self.input.capture_mouse(False)

    def _respawn(self):
        self.player.stats.hp = self.player.stats.max_hp
        self.player.stats.mp = self.player.stats.max_mp
        saved_floor = self._helper.load_game(self.player)
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
            self._helper.save_game(next_floor, self.player)
            self._build_floor(next_floor)
        self._start_fade(_do_transition, duration=0.35)
        #self.hud.add_popup("Subindo para o próximo andar...", 2.0, (200,255,200))

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
                # desativa completamente a barreira (visual + física)
                self._disable_barrier()
                pygame.mixer.music.stop()
                pygame.mixer.music.load(os.path.join(_HERE, "assets", "music", "tower.mp3"))
                pygame.mixer.music.play()
                #self.hud.add_popup("A barreira caiu! Suba as escadas.", 3.0, (200,255,200))

        elif self.current_floor == self.FLOOR_AERIAL:
            if not alive:
                fs.stair_locked = False
                # garante remoção completa da barreira (visual + colisão/flag)
                self._disable_barrier()
                pygame.mixer.music.stop()
                pygame.mixer.music.load(os.path.join(_HERE, "assets", "music", "tower.mp3"))
                pygame.mixer.music.play()
                #self.hud.add_popup("Todos derrotados! Suba as escadas.", 3.0, (200,255,200))

        elif self.current_floor == self.FLOOR_GAUNTLET:
            if not alive:
                gidx = fs.gauntlet_idx
                if gidx + 1 < len(fs.gauntlet_waves):
                    fs.gauntlet_idx += 1
                    next_wave = fs.gauntlet_waves[fs.gauntlet_idx]
                    fs.enemies = next_wave
                    for e, n in next_wave:
                        n.visible = True; e.dead = False
                    #self.hud.add_popup("Próxima onda!", 2.0, (255,180,100))
                else:
                    fs.stair_locked = False
                    # desativa completamente a barreira (visual + física)
                    self._disable_barrier()
                    pygame.mixer.music.stop()
                    pygame.mixer.music.load(os.path.join(_HERE, "assets", "music", "tower.mp3"))
                    pygame.mixer.music.play()
                    #self.hud.add_popup("Corredor limpo! Avance pela porta.", 3.0, (200,255,200))

        elif self.current_floor == self.FLOOR_BOSS:
            if fs.boss and fs.boss.dead:
                self._on_boss_defeated()

    def _on_boss_defeated(self):
        pygame.mixer.music.stop()
        pygame.mixer.music.load(os.path.join(_HERE, "assets", "music", "credits.mp3"))
        pygame.mixer.music.play()

        # ── Sequência da cutscene da Emilia ──────────────────────────────────
        #
        # Fase 1 (imediata): tela preta + texto "Marluxia cai..."
        #   → volta ao jogo: Emilia em waking
        # Fase 2: tela preta + texto "Subaru?" / memórias
        #   → volta ao jogo: Emilia em idle
        # Fase 3: tela preta + "eu me lembro de tudo" / créditos
        #
        # Cada fase é encadeada via callbacks da _show_story.

        def _after_story_1():
            # Troca a animação da Emilia para waking
            if self.emilia_anim is not None:
                self.emilia_anim.play("waking", restart_if_same=True)
            self.emilia_cutscene_phase = "waking"
            self._apply_emilia_phase_offset("waking") 
            # Volta ao explore brevemente para o jogador ver a animação
            self.game_mode = "explore"
            self.input.capture_mouse(True)
            # Depois de WAKING_DURATION segundos inicia a 2ª história
            self._emilia_waking_timer = 0.0
            self._emilia_waking_pending = True

        def _after_story_2():
            if self.emilia_anim is not None:
                self.emilia_anim.play("idle", restart_if_same=True)
            self.emilia_cutscene_phase = "idle"
            self._apply_emilia_phase_offset("idle") 
            self.game_mode = "explore"
            self.input.capture_mouse(True)
            # Depois de IDLE_SHOW_DURATION segundos inicia a 3ª história
            self._emilia_idle_timer = 0.0
            self._emilia_idle_pending = True

        def _after_story_3():
            self._start_credits()

        # Timers de espera (segundos que o jogador vê a animação antes da
        # próxima caixa de texto aparecer automaticamente).
        self._emilia_waking_duration = 3.5   # tempo assistindo a waking
        self._emilia_idle_duration   = 2.5   # tempo assistindo a idle
        self._emilia_waking_timer    = 0.0
        self._emilia_idle_timer      = 0.0
        self._emilia_waking_pending  = False
        self._emilia_idle_pending    = False

        # Guarda referências para uso nos timers do _update_game
        self._emilia_after_story_2 = _after_story_2
        self._emilia_after_story_3 = _after_story_3

        # ── Fase 1: história imediata (Marluxia cai, Emilia abre os olhos) ──
        self._show_story([
            "\"Então...isso é o coração de um herói\"",
            "",
            "\"No fim... era esse poder que eu procurava...\"",
            "",
            "Essas foram as últimas palavras de Marluxia.",
            "",
            "Seu corpo finalmente cede. O inimigo cai derrotado, e pela primeira vez em muito tempo, o silêncio toma conta da torre.",
            "",
            "Até que...",
            "",
            "Um pequeno movimento quebra o silêncio.",
            "",
            "Emilia começa lentamente a despertar de seu sono profundo."
        ], callback=_after_story_1)

    # ── Player attack (real-time) ─────────────────────────────────────────────

    def _player_melee_attack(self):
        self.sounds.attack_sfx.play()

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
            #self.hud.add_popup("Swoosh!", 0.6, (200,200,200))
            pass

    def _try_activate_orb(self):
        """Coleta fragmento ou empurra caixa."""
        p  = self.player
        fs = self.floor_state

        # ── Empurrar caixa ────────────────────────────────────────────────
        pb = getattr(fs, "push_box", None)
        if pb and not pb["activated"] and not getattr(fs, "in_parkour_room", False):
            bx, bz = pb["pos"][0], pb["pos"][1]
            dx = bx - p.world_pos[0]
            dz = bz - p.world_pos[2]
            if math.sqrt(dx*dx + dz*dz) < 1.8:
                IMPULSE = 3.5
                norm = math.sqrt(dx*dx + dz*dz)
                norm = norm if norm > 1e-4 else 1.0
                pb["velocity"][0] += (dx / norm) * IMPULSE
                pb["velocity"][1] += (dz / norm) * IMPULSE
                pb["hit_count"]   += 1
                #self.hud.add_popup(f"Caixa empurrada! (soco {pb['hit_count']})",
                 #                  0.7, (200, 200, 120))
                return

        # ── Coletar fragmento ─────────────────────────────────────────────
        for idx, piece in enumerate(self.puzzle_pieces):
            if piece["collected"]:
                continue

            spos = piece["scatter_pos"]
            dx   = spos[0] - p.world_pos[0]
            dy   = spos[1] - p.world_pos[1]
            dz   = spos[2] - p.world_pos[2]
            dist = math.sqrt(dx*dx + dy*dy + dz*dz)

            if dist >= 2.0:
                continue

            # Peça 0 → só coleta na sub-sala de parkour
            if idx == 0:
                if not getattr(fs, "in_parkour_room", False):
                    #self.hud.add_popup(
                     #   "Esse fragmento está numa sala abaixo — volte pela entrada sul!",
                      #  2.0, (180, 200, 255))
                    return
                piece["collected"] = True
                piece["scatter_pos"] = piece["mural_pos"]
                piece["node"].visible = False
                if getattr(self, '_parkour_snapshot', None) is not None:
                    self._parkour_snapshot["puzzle_state"][0] = (True, piece["scatter_pos"])
                self._check_puzzle()
                #self.hud.add_popup("Fragmento coletado! Volte para o quadro do puzzle.", 2.5, (200, 255, 200))
                return

            # Peça 2 → bloqueada pelo botão
            if idx == 2:
                if pb and not pb["activated"]:
                    #self.hud.add_popup("Empurre a caixa até o botão verde e suba nela!",
                    #                   1.5, (200, 255, 160))
                    return

            # Peça 3 → bloqueada pelos guardas
            if idx == 3:
                guards = getattr(fs, "puzzle_guards", [])
                if any(not ge.dead for ge, _gn in guards):
                    #self.hud.add_popup("Guardas vivos! Derrote os Heartless primeiro.",
                    #                   1.8, (255, 120, 80))
                    return
                
            piece["collected"] = True
            piece["node"].position = list(piece["mural_pos"])
            piece["node"].visible  = True
            #self.hud.add_popup("Fragmento encaixado!", 1.5, (200, 200, 100))
            self._check_puzzle()
            return

    def _check_puzzle(self):
        if all(p["collected"] for p in self.puzzle_pieces):
            self.floor_state.puzzle_solved = True
            self.floor_state.stair_locked  = False
            # desativa completamente a barreira (visual + física)
            self._disable_barrier()
            #self.hud.add_popup("Quadro completo! Suba as escadas.", 3.0, (100,255,100))

    def _disable_barrier(self):
        """Desativa a barreira visualmente e remove sua hitbox/flag do floor_state."""
        fs = getattr(self, 'floor_state', None)
        if fs is None: return
        try:
            if getattr(fs, 'barrier_node', None):
                fs.barrier_node.visible = False
        except Exception:
            pass
        # marca inativa e remove hitbox correspondente (se presente)
        try:
            fs.barrier_active = False
            # Remove hitboxes de barreira próximos às escadas (cobre z ≈ -9.0, -10.5, -13.5 etc.)
            new_obs = []
            for h in getattr(fs, 'obstacles', []):
                if not isinstance(h, BoxHitbox):
                    new_obs.append(h); continue
                hz = getattr(h, 'z', None)
                w = getattr(h, 'width', 0)
                # considera hitboxes largas/altas posicionadas no corredor como barreira
                if hz is not None and -14.0 <= hz <= -8.0 and w >= 2.0:
                    # pulando (removendo) este hitbox
                    continue
                new_obs.append(h)
            fs.obstacles = new_obs
        except Exception:
            pass
        # Além de limpar flags e hitboxes, garante que quaisquer nós de "gate"/"barrier"
        # próximos às escadas sejam escondidos (cobre duplicatas/iterações antigas).
        try:
            for node in list(getattr(self.scene, 'nodes', [])):
                name = getattr(node, 'name', '') or ''
                z = getattr(node, 'position', [0,0,0])[2] if getattr(node, 'position', None) else None
                if z is None:
                    continue
                if -13.0 <= z <= -8.0 and ( 'gate' in name or name == 'barrier' or name == 'portal_gate'):
                    try:
                        node.visible = False
                    except Exception:
                        pass
        except Exception:
            pass

    # ── Rhythm game ───────────────────────────────────────────────────────────

    # ── Beatmap fixo (60s), alinhado ao BPM real da música ──────────────────
    # rythm.mp3 está em 114 BPM -> 1 batida = 60/114 ≈ 0.5263s.
    # As notas são geradas em SUBDIVISÕES da batida (1, 1/2, 1/4) para que
    # caiam sempre em cima do tempo da música, mesmo quando a seção fica
    # mais difícil/densa. Cada item: (tempo_em_segundos, lane)
    # onde lane: 0=←  1=↓  2=↑  3=→
    RHYTHM_BPM = 114.0

    @classmethod
    def _generate_rhythm_beatmap(cls):
        beat = 60.0 / cls.RHYTHM_BPM   # duração de 1 batida em segundos (~0.526s)
        notes = []
        start_t = beat * 4    # pequeno respiro (4 batidas) antes da primeira seta

        def _run(t0, end_t, subdivision, lane_cycle, hold_period=0):
            """Gera notas a cada `subdivision` batidas a partir de t0.
            hold_period > 0 → a cada N notas normais, uma hold é inserida.
            Nunca duas holds seguidas; hold e a nota seguinte são sempre normais.
            """
            step = beat * subdivision
            hold_dur = round(beat * 1.8, 4)   # duração da hold (1.8 batidas)
            i = 0
            t = t0
            since_hold = 0        # quantas notas normais desde a última hold
            skip_next  = False    # garante 1 nota normal após cada hold
            while t < end_t:
                lane = lane_cycle[i % len(lane_cycle)]
                is_hold = (
                    hold_period > 0
                    and not skip_next
                    and since_hold >= hold_period
                )
                if is_hold:
                    dur = hold_dur
                    since_hold = 0
                    skip_next  = True   # próxima obrigatoriamente normal
                else:
                    dur = 0.0
                    since_hold += 1
                    skip_next   = False
                notes.append((round(t, 4), lane, dur))
                i += 1
                t = t0 + i * step
            return t

        # Seção 1 (aquecimento): hold a cada 6 notas normais (bem espaçado)
        t = _run(start_t, beat * 55, 1.0,
                 [0, 2, 1, 3, 0, 1, 3, 2], hold_period=6)

        # Seção 2 (intermediária): hold a cada 4 notas normais
        t = _run(t, beat * 116, 1.0,
                 [1, 3, 0, 2, 3, 1, 0, 2], hold_period=4)

        # Seção 3 (clímax): sem holds — rápido demais
        beat_count = 0
        lane_cycle3 = [2, 0, 3, 1, 2, 3, 0, 1]
        idx3 = 0
        end_t3 = beat * 165
        while t < end_t3:
            sub  = 1.0 if (beat_count % 2 == 0) else 0.5
            lane = lane_cycle3[idx3 % len(lane_cycle3)]
            notes.append((round(t, 4), lane, 0.0))
            beat_count += 1
            idx3 += 1
            t += beat * sub

        return notes

    def _start_rhythm_game(self):
        beatmap = self._generate_rhythm_beatmap()
        self.rhythm_notes = [
            {"time": bt, "lane": lane, "duration": dur,
             "hit_result": None, "hold_progress": 0.0}
            for bt, lane, dur in beatmap
        ]
        self.rhythm_duration   = 90.0
        self.rhythm_timer      = 0.0
        self.rhythm_fall_time  = 1.6   # segundos que uma nota leva para cair até a linha de acerto
        # Janelas de timing (segundos de tolerância em torno do tempo exato da nota)
        self.rhythm_window_perfect = 0.05
        self.rhythm_window_good    = 0.12
        self.rhythm_window_ok      = 0.20
        self.rhythm_points_table   = {"perfect": 3, "good": 2, "ok": 1, "miss": 0}
        self.rhythm_max_points     = len(self.rhythm_notes) * self.rhythm_points_table["perfect"]
        self.rhythm_score_points   = 0
        self.rhythm_last_feedback       = None
        self.rhythm_last_feedback_timer = 0.0
        self.rhythm_lane_flash          = [None, None, None, None]
        self.rhythm_hold_keys           = {}

        pygame.mixer.music.stop()
        pygame.mixer.music.load(os.path.join(_HERE, "assets", "music", "rythm.mp3"))
        pygame.mixer.music.play()

        self.game_mode = "rhythm"
        self.input.capture_mouse(False)

    def _rhythm_abort(self):
        """Cancela o minigame (ESC) sem completar — volta pro explore."""
        pygame.mixer.music.stop()
        pygame.mixer.music.load(os.path.join(_HERE, "assets", "music", "tower.mp3"))
        pygame.mixer.music.play()
        self.game_mode = "explore"
        self.input.capture_mouse(True)
        #self.hud.add_popup("Ritual interrompido. Volte ao obelisco para tentar de novo.", 3.0, (255,200,140))

    def _rhythm_set_feedback(self, label, color):
        self.rhythm_last_feedback       = (label, color)
        self.rhythm_last_feedback_timer = 0.8

    def _rhythm_classify(self, dt_abs):
        if dt_abs <= self.rhythm_window_perfect: return "perfect"
        if dt_abs <= self.rhythm_window_good:    return "good"
        if dt_abs <= self.rhythm_window_ok:      return "ok"
        return None

    def _trigger_lane_flash(self, lane_idx, color, duration):
        """Acende o brilho de fundo de uma lane por `duration` segundos."""
        self.rhythm_lane_flash[lane_idx] = [color, duration]

    def _rhythm_arrow_press(self, lane_name):
        lane_map = {"left": 0, "down": 1, "up": 2, "right": 3}
        lane = lane_map[lane_name]
        t    = self.rhythm_timer

        # Encontra a nota não resolvida mais próxima no tempo, na mesma lane,
        # dentro da janela mais permissiva (OK).
        best_idx, best_dt = None, None
        for idx, note in enumerate(self.rhythm_notes):
            if note["hit_result"] not in (None,) or note["lane"] != lane:
                continue
            dt_abs = abs(note["time"] - t)
            if dt_abs <= self.rhythm_window_ok and (best_dt is None or dt_abs < best_dt):
                best_idx, best_dt = idx, dt_abs

        if best_idx is None:
            self._rhythm_set_feedback("Miss", (255, 90, 90))
            self._trigger_lane_flash(lane, (255, 60, 60), 0.18)
            return

        note   = self.rhythm_notes[best_idx]
        result = self._rhythm_classify(best_dt)

        if note.get("duration", 0.0) > 0.0:
            # Hold note — registra início; resultado final vem ao soltar
            self.rhythm_hold_keys[lane] = {
                "note_idx": best_idx,
                "held":     0.0,
                "required": note["duration"],
                "quality":  result,
            }
            note["hit_result"] = "holding"
            # Brilho ciano persistente enquanto segura
            self._trigger_lane_flash(lane, (100, 255, 255), 9999.0)
        else:
            # Nota normal
            note["hit_result"] = result
            self.rhythm_score_points += self.rhythm_points_table[result]
            feedback_colors = {
                "perfect": ("Perfect!", (120, 255, 200)),
                "good":    ("Good",     (200, 255, 140)),
                "ok":      ("OK",       (255, 220, 120)),
            }
            label, color = feedback_colors[result]
            self._rhythm_set_feedback(label, color)
            self._trigger_lane_flash(lane, color, 0.25)

    def _rhythm_hold_release(self, lane_idx):
        """Chamado quando o jogador solta a tecla de uma hold note."""
        hold = self.rhythm_hold_keys.pop(lane_idx, None)
        if hold is None:
            return

        note  = self.rhythm_notes[hold["note_idx"]]
        ratio = hold["held"] / max(hold["required"], 0.001)

        if ratio >= 0.85:
            result = hold["quality"]
            self.rhythm_score_points += self.rhythm_points_table[result]
            feedback_colors = {
                "perfect": ("Perfect!", (120, 255, 200)),
                "good":    ("Good!",    (200, 255, 140)),
                "ok":      ("OK",       (255, 220, 120)),
            }
            label, color = feedback_colors[result]
            self._rhythm_set_feedback(label, color)
            self._trigger_lane_flash(lane_idx, color, 0.3)
            note["hit_result"] = result
        else:
            # Soltou cedo → miss
            note["hit_result"] = "miss"
            self._rhythm_set_feedback("Solto cedo!", (255, 90, 90))
            self._trigger_lane_flash(lane_idx, (255, 60, 60), 0.25)

        # Apaga o brilho persistente do hold
        self.rhythm_lane_flash[lane_idx] = None

    def _update_rhythm(self, dt):
        self.rhythm_timer += dt
        t = self.rhythm_timer

        # Feedback timer
        if self.rhythm_last_feedback_timer > 0.0:
            self.rhythm_last_feedback_timer -= dt
            if self.rhythm_last_feedback_timer <= 0.0:
                self.rhythm_last_feedback = None

        # Lane flash timers
        for i in range(4):
            fl = self.rhythm_lane_flash[i]
            if fl is not None:
                fl[1] -= dt
                if fl[1] <= 0.0:
                    self.rhythm_lane_flash[i] = None

        # Avança hold notes em progresso
        for lane_idx, hold in list(self.rhythm_hold_keys.items()):
            hold["held"] += dt
            note = self.rhythm_notes[hold["note_idx"]]
            note["hold_progress"] = min(1.0, hold["held"] / max(hold["required"], 0.001))
            # Se o tempo da nota acabou (+ margem) sem soltar → completa automaticamente
            note_end = note["time"] + note["duration"]
            if t > note_end + 0.3:
                self._rhythm_hold_release(lane_idx)

        # Miss automático para notas normais que passaram da janela
        for note in self.rhythm_notes:
            if note["hit_result"] is None and (t - note["time"]) > self.rhythm_window_ok:
                note["hit_result"] = "miss"

        if t >= self.rhythm_duration:
            # Finaliza holds abertas antes de encerrar
            for lane_idx in list(self.rhythm_hold_keys.keys()):
                self._rhythm_hold_release(lane_idx)
            self._finish_rhythm_game()

    def _finish_rhythm_game(self):
        max_pts = max(1, self.rhythm_max_points)
        pct = self.rhythm_score_points / max_pts

        pygame.mixer.music.stop()
        pygame.mixer.music.load(os.path.join(_HERE, "assets", "music", "tower.mp3"))
        pygame.mixer.music.play()

        if pct >= 0.70:
            self.floor_state.rhythm_done  = True
            self.floor_state.stair_locked = False
            self._disable_barrier()
            self.hud.add_popup(f"Ritual completo! {pct*100:.0f}% – Suba as escadas!", 3.5, (100,255,200))
        else:
            self.hud.add_popup(f"Apenas {pct*100:.0f}%... O obelisco exige 70%. Tente de novo!", 3.5, (255,140,140))

        self.game_mode = "explore"
        self.input.capture_mouse(True)

    # ── Input ─────────────────────────────────────────────────────────────────

    def _handle_global_input(self, dt):
        if self.input.key_pressed("f1"):
            self.wireframe = not self.wireframe

        if self.game_mode == "book":
            # ← / A : página anterior
            if self.input.key_pressed("left") or self.input.key_pressed("a"):
                 if self.book_index > 1:
                     self.book_index -= 1
            # → / D : próxima página
            if self.input.key_pressed("right") or self.input.key_pressed("d"):
                if self.book_index < self.book_max:
                    self.book_index += 1
            # ESC / E / Enter : fechar
            if (
                self.input.key_pressed("escape")
                or self.input.key_pressed("e")
                or self.input.key_pressed("return")
            ):
                self._close_book()
            
            return
            
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
            lane_map = {"left": 0, "down": 1, "up": 2, "right": 3}
            for lane_name, lane_idx in lane_map.items():
                if self.input.key_pressed(lane_name):
                    self._rhythm_arrow_press(lane_name)
                if hasattr(self.input, "key_released") and self.input.key_released(lane_name):
                    self._rhythm_hold_release(lane_idx)
            if self.input.key_pressed("escape"):
                self._rhythm_abort()
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
                pygame.mixer.music.stop()
                pygame.mixer.music.load(os.path.join(_HERE, "assets", "music", "combat.mp3"))
                pygame.mixer.music.play()
                self.floor_state.barrier_active = True
                self.floor_state.barrier_node.visible = True
                # Adiciona physics à barreira quando ela fica ativa
                self.floor_state.obstacles.append(
                    BoxHitbox(x=0, y=ROOM_H/2-0.5, z=-9.0, width=ROOM_W-2, height=ROOM_H-1, depth=0.2))
                # Reposiciona player no meio da sala para não ficar preso
                self.player.world_pos = [0.0, 0.5, -2.0]
                for ep in [(-3,0.5,-5),(3,0.5,-5),(0,0.5,-3)]:
                    e, n = self._helper._spawn_heartless(self.scene, ep, level=2)
                    e.respawns_left = 0; self.floor_state.enemies.append((e,n))
                #self.hud.add_popup("TUTORIAL DE COMBATE!", 2.5, (255,200,80))
                #self.hud.add_popup("[Z] para atacar os Heartless!", 3.5, (200,200,255))

        # Volta da sub-sala de parkour (entrada norte, apenas no puzzle)
        if (self.current_floor == self.FLOOR_PUZZLE
                and getattr(self.floor_state, 'in_parkour_room', False)
                and pz > 11.0 and abs(px) < 2.0):
            def _back_to_puzzle():
                self._rebuild_puzzle_keep_state()
            self._start_fade(_back_to_puzzle, duration=0.35)
            #self.hud.add_popup("Voltando...", 1.5, (180, 200, 255))
            return
        # Entrada na sub-sala de parkour (parede sul, apenas no puzzle)
        if (self.current_floor == self.FLOOR_PUZZLE
                and not getattr(self.floor_state, 'in_parkour_room', False)
                and pz > 13.5 and abs(px) < 2.0):
            def _enter_parkour():
                self._build_parkour_room()
            self._start_fade(_enter_parkour, duration=0.35)
            #self.hud.add_popup("Entrando na sub-sala...", 1.5, (180, 200, 255))
            return

        # Sair de FLOOR_PUZZLE (quando puzzle completo)
        if self.current_floor == self.FLOOR_PUZZLE:
            if pz < -10.0 and not self.floor_state.stair_locked:
                self._advance_floor()
                return

        if self.current_floor == self.FLOOR_AERIAL:
            # Avança para o próximo andar quando estiver perto das escadas e destrancado
            if pz < -10.0 and not self.floor_state.stair_locked:
                self._advance_floor()
                return
        if self.current_floor == self.FLOOR_RHYTHM:
            if pz < -10.0 and not self.floor_state.stair_locked:
                self._advance_floor()
                return
            ob_pos = getattr(self.floor_state, 'rhythm_obelisk_pos', None)
            if (ob_pos is not None and not self.floor_state.rhythm_done
                    and self.game_mode == "explore"):
                dist = ((px - ob_pos[0]) ** 2 + (pz - ob_pos[1]) ** 2) ** 0.5
                if dist < 2.2:
                    self._start_rhythm_game()
                    return
        if self.current_floor == self.FLOOR_GAUNTLET:
            if pz < -10.0 and not self.floor_state.stair_locked:
                self._advance_floor()
                return

        if self.current_floor == self.FLOOR_ENTRY:
            if pz < -10.0 and not self.floor_state.stair_locked:
                self._advance_floor()

        elif self.current_floor == self.FLOOR_REST:
        
            # Fechar livro
            if self.book_open:
                self._close_book()
                return
            
            # Avançar de andar
            pz = self.player.world_pos[2]
            px = self.player.world_pos[0]
            if pz < -11.0 and abs(px) < 3.0:
                self._advance_floor()
                return
            
            # Abrir livro
            book_pos = getattr(self.floor_state, 'rest_book_pos', None)
            radius = getattr(self.floor_state, 'rest_book_radius', 1.5)

            if book_pos is not None:
                dx = self.player.world_pos[0] - book_pos[0]
                dz = self.player.world_pos[2] - book_pos[2]
                dist = (dx * dx + dz * dz) ** 0.5
                if dist <= radius:
                    self._open_book()

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
            #self.hud.add_popup(f"{sp.name} – sem alvo próximo", 1.2, (140,140,255))
            return
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

    def _update_emilia_cutscene_timers(self, dt: float):
        """Avança os timers que controlam as pausas visuais entre as fases
        da cutscene da Emilia (waking → idle) e dispara as histórias seguintes
        automaticamente."""
        if getattr(self, '_emilia_waking_pending', False):
            self._emilia_waking_timer += dt
            if self._emilia_waking_timer >= getattr(self, '_emilia_waking_duration', 3.5):
                self._emilia_waking_pending = False
                cb2 = getattr(self, '_emilia_after_story_2', None)
                if cb2:
                    self._show_ending_part2(cb2)

        if getattr(self, '_emilia_idle_pending', False):
            self._emilia_idle_timer += dt
            if self._emilia_idle_timer >= getattr(self, '_emilia_idle_duration', 2.5):
                self._emilia_idle_pending = False
                cb3 = getattr(self, '_emilia_after_story_3', None)
                if cb3:
                    self._show_ending_part3(cb3)

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
        if self.game_mode == "story":
            self.story_timer += dt
            return
        if self.game_mode not in ("explore","rhythm"): return
        self._update_player(dt)
        if self.player_anim is not None:
            self.player_anim.update(dt)
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

        # Avança a animação idle da Emilia na sala do boss
        emilia_anim = getattr(self, 'emilia_anim', None)
        emilia_node = getattr(self.floor_state, 'emilia_node', None)
        if emilia_anim is not None and emilia_node is not None and getattr(emilia_node, 'visible', True):
                was_waking = (self.emilia_cutscene_phase == "waking")
                emilia_anim.update(dt)
                if was_waking and emilia_anim.state != "waking":
                    self._apply_emilia_phase_offset("idle", em_node=emilia_node)
                    self.emilia_cutscene_phase = "idle_pending"
        # Timers da cutscene da Emilia (waking/idle após morte do boss)
        self._update_emilia_cutscene_timers(dt)

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
            b = self._helper._stair_step_bounds(i)
            if b["z0"] <= pz <= b["z1"]:
                ground = max(ground, b["y1"])
        return ground

    def _resolve_stair_collisions(self, p):
        if not self.floor_state.has_stairs: return
        px, py, pz = p.world_pos
        pr = 0.5
        for i in range(STAIR_COUNT):
            b = self._helper._stair_step_bounds(i)
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
            if self.player_anim is not None:
                self.player_anim.play("jumping", restart_if_same=True)


    def _update_player_input(self, dt):

        p = self.player
        keys = self.input.held_keys

        move_x = 0.0
        move_z = 0.0

        fwd = self.camera.flat_forward
        rgt = self.camera.flat_right

        moving = False

        if "w" in keys:
            move_x += fwd[0]
            move_z += fwd[2]
            moving = True

        if "s" in keys:
            move_x -= fwd[0]
            move_z -= fwd[2]
            moving = True

        if "a" in keys:
            move_x -= rgt[0]
            move_z -= rgt[2]
            moving = True

        if "d" in keys:
            move_x += rgt[0]
            move_z += rgt[2]
            moving = True

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

        if self.player_anim is not None and not self.player_anim.is_one_shot_active():
            if not p.on_ground:
                self.player_anim.play("jumping")
            else:
                self.player_anim.play("walking" if mag > 0 else "idle")

        if moving and p.on_ground:

            if not self.sounds.walk_sfx.is_playing():
                self.sounds.walk_sfx.play(loops=-1)

        else:
            self.sounds.walk_sfx.stop()

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

        if getattr(self.floor_state, 'in_parkour_room', False):
            ground_y = -999.0
        else:
            ground_y = self._stair_ground_y(
                player.world_pos[0],
                player.world_pos[2]
            )

        for hitbox in self.floor_state.obstacles:

            if isinstance(hitbox, BoxHitbox):

                h = hitbox.get_surface_height(player)

                if h is not None:
                    ground_y = max(ground_y, h)
        
        # Verifica também o hitbox da caixa empurrável (dinâmico)
        pb = getattr(self.floor_state, "push_box", None)
        if pb and pb["hitbox"]:
            h = pb["hitbox"].get_surface_height(player)
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

        # Void da sub-sala de parkour: caída livre até a morte após alguns segundos
        if getattr(self.floor_state, 'in_parkour_room', False) and p.world_pos[1] < -2.0:
            self.void_fall_timer = (self.void_fall_timer or 0.0) + dt
            if self.void_fall_timer >= 1.5:
                self.void_fall_timer = None
                #self.hud.add_popup("Caiu no void!", 1.5, (255, 60, 60))
                self._trigger_death()
        else:
            self.void_fall_timer = None

    def _rebuild_puzzle_keep_state(self):
        """Volta do parkour pro puzzle mantendo progresso."""
        # Salva estado de TUDO que precisa persistir
        puzzle_solved = self.floor_state.puzzle_solved
        stair_locked = self.floor_state.stair_locked
        parkour_snapshot = getattr(self, "_parkour_snapshot", None)
        if parkour_snapshot is not None:
            puzzle_state = parkour_snapshot.get("puzzle_state", [(p["collected"], p["scatter_pos"]) for p in self.puzzle_pieces])
            box_state = parkour_snapshot.get("box_state")
            enemy_state = parkour_snapshot.get("enemy_state", [])
        else:
            puzzle_state = [(p["collected"], p["scatter_pos"]) for p in self.puzzle_pieces]
            box_state = None
            if self.floor_state.push_box:
                box_state = {
                    "pos": self.floor_state.push_box["pos"].copy(),
                    "velocity": self.floor_state.push_box["velocity"].copy(),
                    "activated": self.floor_state.push_box["activated"],
                    "hit_count": self.floor_state.push_box["hit_count"],
                }
            enemy_state = [(e.world_pos.copy(), e.dead) for e, _ in self.floor_state.puzzle_guards] if hasattr(self.floor_state, 'puzzle_guards') else []
        
        # Limpa e reconstrói
        self._clear_scene()
        self._build_floor_puzzle()
        # Restaura estado persistente do puzzle
        self.floor_state.puzzle_solved = puzzle_solved
        self.floor_state.stair_locked = stair_locked
        if puzzle_solved:
            # garante que a barreira fique removida ao reconstruir a sala
            self._disable_barrier()
        
        # Restaura estado das peças
        for idx, (was_collected, old_pos) in enumerate(puzzle_state):
            if idx == 0:  # Peça 0 fica na sub-sala
                self.puzzle_pieces[0]["collected"] = was_collected
                self.puzzle_pieces[0]["scatter_pos"] = old_pos
                if was_collected:
                    self.puzzle_pieces[0]["node"].visible = True
                    self.puzzle_pieces[0]["node"].position = list(self.puzzle_pieces[0]["mural_pos"])
                else:
                    self.puzzle_pieces[0]["node"].visible = False
                    self.puzzle_pieces[0]["node"].position = [0.0, 999.0, 0.0]
                continue
            
            if was_collected:
                self.puzzle_pieces[idx]["collected"] = True
                self.puzzle_pieces[idx]["node"].visible = True  # Visível no quadro
                self.puzzle_pieces[idx]["node"].position = list(self.puzzle_pieces[idx]["mural_pos"])  # Na mural
            else:
                self.puzzle_pieces[idx]["collected"] = False
                self.puzzle_pieces[idx]["node"].visible = True
                self.puzzle_pieces[idx]["scatter_pos"] = old_pos
                self.puzzle_pieces[idx]["node"].position = list(old_pos)
        
        # Restaura estado da caixa
        if box_state and self.floor_state.push_box:
            box = self.floor_state.push_box
            box["pos"] = box_state["pos"]
            box["velocity"] = box_state["velocity"]
            box["activated"] = box_state["activated"]
            box["hit_count"] = box_state["hit_count"]
            # Atualiza posição visual da caixa
            box["node"].position = [box["pos"][0], 0.5, box["pos"][1]]
            # Atualiza hitbox
            box["hitbox"].x = box["pos"][0]
            box["hitbox"].z = box["pos"][1]
            if box["activated"]:
                box["btn_node"].mesh.base_color = (0.85, 1.0, 0.15)
        
        # Restaura estado dos inimigos
        self.floor_state.enemies = []
        if hasattr(self.floor_state, 'puzzle_guards'):
            for ((e, n), (old_pos, was_dead)) in zip(self.floor_state.puzzle_guards, enemy_state):
                e.world_pos = list(old_pos)
                e.dead = was_dead
                n.visible = not was_dead
                n.position = list(old_pos)
                if was_dead:
                    n.visible = False
                self.floor_state.enemies.append((e, n))
        
        self.floor_state.in_parkour_room = False
        self.player.world_pos = [0.0, 0.8, 12.0]
        self.player.velocity = [0.0, 0.0, 0.0]
        self.player.on_ground = True
        #self.hud.add_popup("De volta ao puzzle!", 2.0, (200, 220, 255))

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
            dist2 = dx*dx + dz*dz; min_dist = PLAYER_RADIUS + ENEMY_RADIUS
            if dist2 < min_dist*min_dist and dist2 > 0.0001:
                dist = math.sqrt(dist2); push = (min_dist - dist) / dist
                self.player.world_pos[0] += dx*push; self.player.world_pos[2] += dz*push

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
            p.world_pos[1],
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

        south_limit = hd
        # Na sub-sala de parkour não há parede sul (o void fica abaixo)
        # mas mantemos os limites laterais normais.
        if getattr(self.floor_state, 'in_parkour_room', False):
            south_limit = hd  # sem restrição extra
        p.world_pos[2] = max(
            north_limit,
            min(south_limit, p.world_pos[2])
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

        self._update_push_box(dt)
        self._update_player_visuals()
                
    def _update_push_box(self, dt):
        """Física simples da caixa empurrável no andar de puzzle."""
        if self.current_floor != self.FLOOR_PUZZLE:
            return
        pb = getattr(self.floor_state, "push_box", None)
        if pb is None:
            return

        FRICTION = 5.0    # desaceleração (m/s²)
        BOX_Y    = 0.5    # altura fixa (metade da caixa)
        ROOM_HW  = ROOM_W / 2 - 0.8
        ROOM_HD  = ROOM_D / 2 - 0.8

        # Se não foi ativado ainda, aplica movimento e fricção
        if not pb["activated"]:
            vx, vz = pb["velocity"]

            # Fricção
            speed = math.sqrt(vx*vx + vz*vz)
            if speed > 0.0:
                decel = min(FRICTION * dt, speed)
                pb["velocity"][0] -= (vx / speed) * decel
                pb["velocity"][1] -= (vz / speed) * decel
                vx, vz = pb["velocity"]

            # Mover
            pb["pos"][0] += vx * dt
            pb["pos"][1] += vz * dt

            # Limites da sala
            pb["pos"][0] = max(-ROOM_HW, min(ROOM_HW, pb["pos"][0]))
            pb["pos"][1] = max(-ROOM_HD, min(ROOM_HD, pb["pos"][1]))

        # Atualiza SceneNode (sempre, ativada ou não)
        pb["node"].position = [pb["pos"][0], BOX_Y, pb["pos"][1]]
        
        # Atualiza hitbox da caixa
        pb["hitbox"].x = pb["pos"][0]
        pb["hitbox"].z = pb["pos"][1]
        pb["hitbox"].y = BOX_Y

        # Colisão player ↔ caixa (empurra player para fora – AABB vs círculo)
        BOX_HALF = 0.6
        PLAYER_R = 0.5
        px, _py, pz = self.player.world_pos
        bx, bz      = pb["pos"][0], pb["pos"][1]
        nx = max(bx - BOX_HALF, min(px, bx + BOX_HALF))
        nz = max(bz - BOX_HALF, min(pz, bz + BOX_HALF))
        ddx = px - nx; ddz = pz - nz
        dist2 = ddx*ddx + ddz*ddz
        if dist2 < PLAYER_R * PLAYER_R and dist2 > 1e-8:
            dist = math.sqrt(dist2)
            push = (PLAYER_R - dist) / dist
            self.player.world_pos[0] += ddx * push
            self.player.world_pos[2] += ddz * push

        # Checa se a caixa chegou no botão (apenas se ainda não foi ativada)
        if not pb["activated"]:
            btnx, btnz = pb["btn_pos"]
            ddx2 = pb["pos"][0] - btnx
            ddz2 = pb["pos"][1] - btnz
            if math.sqrt(ddx2*ddx2 + ddz2*ddz2) < pb["btn_radius"]:
                pb["velocity"]               = [0.0, 0.0]  # para de se mover
                pb["btn_node"].mesh.base_color = (0.85, 1.0, 0.15)  # botão fica amarelo
                pb["activated"]              = True  # marca como ativado para libertar o fragmento
                #self.hud.add_popup("Botão ativado! Fragmento liberado!", 2.5, (180, 255, 120))

    def _update_enemies(self, dt):
        for e, node in self.floor_state.enemies:
            if e.dead: continue
            e.update(self.player.world_pos, dt)
            if isinstance(e, Boss):
                self._update_boss(boss=e, node=node, dt=dt)
                return 
            y_off = getattr(e, '_y_offset', 0.0)
            node.position = [e.world_pos[0], e.world_pos[1] + y_off, e.world_pos[2]]
            if not getattr(e, 'stationary', False):
                node.rotation[1] = e.facing_deg

            # Animação: avança o controller e escolhe idle vs walking
            anim = getattr(e, '_anim', None)
            if anim is not None:
                is_moving = (not getattr(e, 'stationary', False)
                             and getattr(e, 'aggro', False))
                target_state = "walking" if is_moving else "idle"
                current_state = getattr(e, '_anim_state', None)

                if current_state != target_state:
                    e._anim_state = target_state
                    anim.play(target_state)
            if anim is not None:
                anim.update(dt)

            if e.aggro and self.player.invincible <= 0.0:
                dx = e.world_pos[0]-self.player.world_pos[0]
                dz = e.world_pos[2]-self.player.world_pos[2]
                if math.sqrt(dx*dx+dz*dz) < e.attack_range:
                    dmg = e.try_attack(self.player.stats)
                    if dmg > 0:
                        self.sounds.hit_sfx.play()
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

    def _update_boss(self, boss, node, dt):
        print("UPDATE BOSS")
        if boss.dead:
            return

        boss.update(self.player.world_pos, dt)

        y_off = getattr(boss, "_y_offset", 0.0)

        node.position = [
            boss.world_pos[0],
            boss.world_pos[1] + y_off,
            boss.world_pos[2]
        ]

        node.rotation[1] = boss.facing_deg

        anim = getattr(boss, "_anim", None)

        if anim is not None:

            target_state = boss.state

            current_state = getattr(
                boss,
                "_anim_state",
                None
            )

            if current_state != target_state:
                boss._anim_state = target_state
                anim.play(target_state)

            anim.update(dt)

        if boss.aggro and self.player.invincible <= 0.0:

            dx = boss.world_pos[0] - self.player.world_pos[0]
            dz = boss.world_pos[2] - self.player.world_pos[2]

            dist = math.sqrt(dx*dx + dz*dz)

            attack_range = boss.attack_range

            if boss.current_attack:
                attack_range = boss.current_attack["range"]

            if dist < attack_range:

                dmg = boss.try_attack(self.player.stats)
                print("TRY ATTACK")
                if dmg > 0:
                    print("DAMAGE")
                    self.sounds.hit_sfx.play()

                    self.player.invincible = 0.5

                    self.player.is_taking_damage = True

                    self.player.reaction_timer = (
                        self.player.REACTION_TIME
                    )

                    self.hud.add_popup(
                        f"-{dmg} HP",
                        1.2,
                        (255,80,80)
                    )

                    if self.player.is_dead:
                        self._trigger_death()
        
    def _render(self):
        glPolygonMode(GL_FRONT_AND_BACK, GL_LINE if self.wireframe else GL_FILL)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        self.scene.draw(self.phong_shader, self.camera)
        self._render_skinned_player()
        self._render_skinned_beatrice()
        self._render_skinned_emilia()
        self._render_enemy_skinned_meshes()
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

    def _render_skinned_emilia(self):
        """Desenha a Emilia inconsciente na sala do boss (skinned mesh)."""
        emilia_anim  = getattr(self, 'emilia_anim',  None)
        emilia_mesh  = getattr(self, 'emilia_skinned_mesh', None)
        emilia_node  = getattr(self.floor_state, 'emilia_node', None)
        if emilia_anim is None or emilia_mesh is None or emilia_node is None:
            return
        if not getattr(emilia_node, 'visible', True):
            return
        self._render_skinned(emilia_node, emilia_mesh, emilia_anim)

    def _render_enemy_skinned_meshes(self):
        """Desenha todos os inimigos que foram carregados como skinned mesh
        (Heartless terrestre e AerialKnocker). Inimigos com fallback .obj
        já estão na scene e são renderizados por scene.draw() normalmente."""
        for e, node in self.floor_state.enemies:
            if e.dead:
                continue
            skinned_mesh = getattr(e, '_skinned_mesh', None)
            anim         = getattr(e, '_anim', None)
            if skinned_mesh is None or anim is None:
                continue
            if not node.visible:
                continue
            self._render_skinned(node, skinned_mesh, anim)

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
                if is_image_path(line):
                    if not hasattr(self, "_story_tex_cache"):
                        self._story_tex_cache = {}
                    if line not in self._story_tex_cache:
                        self._story_tex_cache[line] = Texture(line, max_size=None)
                    tex = self._story_tex_cache[line]
                    FADE_DURATION = 4.0
                    alpha = min(1.0, self.story_timer / FADE_DURATION)
                    h.draw_image(texture=tex, x=0, y=0, w=sw, h=sh, alpha=alpha)
                else:
                    color = (255,255,255) if line else (100,100,100)
                    h.draw_text(line, sw//2, sh//2, 22, color, center=True)
            h.draw_text("[ENTER] próximo", sw//2, sh-40, 14, (150,150,150), center=True)
            return
    
        if self.game_mode == "book":
            # Fundo escuro
            h.draw_rect(
                0,
                0,
                sw,
                sh,
                (0.0, 0.0, 0.04)
            )

            tex = self._book_page_texture(self.book_index)

            if tex is not None:
                # Mantém proporção da imagem
                img_w = (
                    int(sh * (tex.width / tex.height))
                    if hasattr(tex, 'width')
                    else sw
                )

                img_h = sh

                if img_w > sw:

                    img_w = sw

                    img_h = (
                        int(sw * (tex.height / tex.width))
                        if hasattr(tex, 'width')
                        else sh
                    )


                img_x = (sw - img_w) // 2
                img_y = (sh - img_h) // 2


                h.draw_image(
                    texture=tex,
                    x=img_x,
                    y=img_y,
                    w=img_w,
                    h=img_h,
                    alpha=1.0
                )


            else:

                h.draw_text(
                    f"[Relatório {self.book_index} não encontrado]",
                    sw // 2,
                    sh // 2,
                    20,
                    (200,100,100),
                    center=True
                )

            # Navegação

            if self.book_index > 1:

                h.draw_text(
                    "← Anterior",
                    60,
                    sh - 40,
                    15,
                    (200,200,200)
                )

            if self.book_index < self.book_max:

                h.draw_text(
                    "Próximo →",
                    sw - 110,
                    sh - 40,
                    15,
                    (200,200,200)
                )

            h.draw_text(
                "[ESC / E] Fechar",
                sw // 2,
                sh - 6,
                12,
                (130,130,130),
                center=True
            )
            return
            
        if self.game_mode == "credits":
            h.draw_rect(0, 0, sw, sh, (0.0, 0.0, 0.0))
            credits = [
                "Torre de Plêiades",
                "Re:Zero – Uma nova jornada",
                "",
                "── Desenvolvimento ──",
                "",
                "Vesuvio  ·  Gabriel Luiz",
                "",
                "── História ──",
                "",
                "Inspirado em",
                "Re:Zero kara Hajimeru Isekai Seikatsu",
                "por Tappei Nagatsuki",
                "",
                "e em",
                "Kingdom Hearts: Re:Chain of Memories",
                "© Square Enix / Disney",
                "",
                "── Personagens ──",
                "",
                "Natsuki Subaru  ·  Emilia  ·  Beatrice",
                "Garfiel Tinsel  ·  Otto Suwen",
                "",
                "Marluxia  ·  Larxene  ·  Xemnas",
                "Sora  ·  Axel  ·  Naminé",
                "",
                "── Assets ──",
                "",
                "Modelos 3D de personagens",
                "Mixamo – Adobe Inc.",
                "",
                "Inimigos: Heartless",
                "Kingdom Hearts © Square Enix / Disney",
                "",
                "── Trilha Sonora ──",
                "",
                "Hikari (Simple and Clean) Orchestral Version",
                "Yoda",
                "",
                "Castle Oblivion",
                "Kingdom Hearts Re:Chain of Memories OST",
                "",
                "Styx Helix (Emotional Piano Cover)",
                "PianoPrince",
                "",
                "Sinister Shadows",
                "Yoko Shimomura",
                "",
                "Lord of the Castle",
                "Yoko Shimomura",
                "",
                "── Obrigado por jogar ──",
                "",
                "\"Mesmo que vocês esqueçam,",
                "eu não vou me esquecer de nenhum de vocês.\"",
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
        lane_names  = ["←", "↓", "↑", "→"]
        lane_colors = [(0.85,0.25,0.35), (0.25,0.85,0.45), (0.85,0.75,0.20), (0.25,0.55,0.95)]
        n_lanes  = 4
        lane_w   = 64
        gap      = 14
        total_w  = n_lanes * lane_w + (n_lanes - 1) * gap
        base_x   = sw // 2 - total_w // 2
        hit_y    = sh - 130
        track_h  = sh - 220
        track_top = hit_y - track_h

        # Monta mapa lane → progresso de hold ativo (para o indicador fixo)
        _hold_progress_by_lane = {}
        for _li, _hd in getattr(self, "rhythm_hold_keys", {}).items():
            _hold_progress_by_lane[_li] = min(1.0, _hd["held"] / max(_hd["required"], 0.001))

        for i in range(n_lanes):
            lx = base_x + i * (lane_w + gap)

            # Fundo base da trilha
            h.draw_rect(lx, track_top, lane_w, track_h, (0.05, 0.05, 0.08), alpha=0.55)

            # ── Lane flash (brilho de acerto / hold) ──────────────────────
            fl = getattr(self, "rhythm_lane_flash", [None]*4)[i]
            if fl is not None:
                raw_col, fl_timer = fl[0], fl[1]
                intensity = min(1.0, fl_timer * 5.0)
                if isinstance(raw_col[0], int):
                    fc = (raw_col[0]/255.0 * intensity,
                          raw_col[1]/255.0 * intensity,
                          raw_col[2]/255.0 * intensity)
                else:
                    fc = (raw_col[0] * intensity, raw_col[1] * intensity, raw_col[2] * intensity)
                h.draw_rect(lx, track_top, lane_w, track_h, fc, alpha=0.45 * intensity)

            # ── Indicador fixo de hold na linha de acerto ─────────────────
            if i in _hold_progress_by_lane:
                prog = _hold_progress_by_lane[i]

                # Fundo escuro da barra (largura total da lane)
                bar_h = 16
                bar_y = hit_y - bar_h // 2
                h.draw_rect(lx + 2, bar_y, lane_w - 4, bar_h,
                            (0.05, 0.05, 0.08), alpha=0.92)

                # Preenchimento da barra — vai de ciano para branco conforme enche
                fill_w = int((lane_w - 4) * prog)
                if fill_w > 0:
                    # Cor: ciano no início, branco puro no fim
                    r = 0.4 + 0.6 * prog
                    g = 1.0
                    b = 1.0 - 0.2 * prog
                    h.draw_rect(lx + 2, bar_y, fill_w, bar_h,
                                (r, g, b), alpha=0.97)

                # Borda da barra
                h.draw_rect(lx + 2, bar_y,     lane_w - 4, 2,  (1.0, 1.0, 1.0), alpha=0.6)
                h.draw_rect(lx + 2, bar_y + bar_h - 2, lane_w - 4, 2, (1.0, 1.0, 1.0), alpha=0.6)

                # Texto "SOLTE!" aparece quando barra está quase cheia (> 80%)
                if prog >= 0.80:
                    h.draw_text("SOLTE!", lx + lane_w // 2, bar_y - 18,
                                14, (255, 255, 100), bold=True, center=True)
                else:
                    h.draw_text("SEGURE", lx + lane_w // 2, bar_y - 18,
                                12, (160, 240, 240), bold=False, center=True)
            else:
                # Linha de acerto normal
                h.draw_rect(lx, hit_y - 4, lane_w, 8, lane_colors[i], alpha=0.9)

            h.draw_text(lane_names[i], lx + lane_w // 2, hit_y + 26,
                        22, (230, 230, 230), bold=True, center=True)

        t        = self.rhythm_timer
        note_h   = 18

        # ── HUD de progresso (topo central) ───────────────────────────────
        _duration  = self.rhythm_duration
        _max_pts   = max(1, self.rhythm_max_points)
        _pct       = self.rhythm_score_points / _max_pts
        _time_left = max(0.0, _duration - t)

        _panel_w = 320
        _panel_x = sw // 2 - _panel_w // 2
        _panel_y = 10

        # Fundo do painel
        h.draw_rect(_panel_x, _panel_y, _panel_w, 62, (0.03, 0.03, 0.08), alpha=0.82)

        # Tempo restante
        _mins = int(_time_left) // 60
        _secs = int(_time_left) % 60
        h.draw_text(f"{_mins}:{_secs:02d}",
                    sw // 2, _panel_y + 6,
                    15, (200, 220, 255), bold=False, center=True)

        # Barra de progresso da música
        _bar_x = _panel_x + 10
        _bar_y = _panel_y + 26
        _bar_w = _panel_w - 20
        _bar_h = 10
        _prog_frac = min(1.0, t / _duration)
        h.draw_rect(_bar_x, _bar_y, _bar_w, _bar_h, (0.12, 0.12, 0.22), alpha=0.92)
        if _prog_frac > 0:
            h.draw_rect(_bar_x, _bar_y, int(_bar_w * _prog_frac), _bar_h,
                        (0.35, 0.55, 1.0), alpha=0.95)

        # Score atual vs meta 70%
        _score_col = (120, 255, 160) if _pct >= 0.70 else (255, 200, 80)
        h.draw_text(f"Score: {_pct*100:.0f}%   |   Meta: 70%",
                    sw // 2, _panel_y + 46,
                    14, _score_col, bold=True, center=True)
        # ── fim HUD de progresso ──────────────────────────────────────────

        end_mk_h = 12   # altura do marcador de fim

        for note in self.rhythm_notes:
            if note["hit_result"] not in (None, "holding"):
                continue

            lane = note["lane"]
            lx   = base_x + lane * (lane_w + gap)
            col  = lane_colors[lane]
            dur  = note.get("duration", 0.0)

            # dt para a CABEÇA e para o FIM
            dt_head = note["time"] - t          # positivo = ainda vai chegar
            dt_end  = (note["time"] + dur) - t  # positivo = fim ainda vai chegar

            head_visible = -0.3 < dt_head <= self.rhythm_fall_time
            end_visible  = dur > 0.0 and -0.3 < dt_end <= self.rhythm_fall_time
            holding_now  = note["hit_result"] == "holding"

            if not head_visible and not end_visible and not holding_now:
                continue

            frac_head = 1.0 - (dt_head / self.rhythm_fall_time)
            ny_head   = int(track_top + frac_head * track_h)

            if dur == 0.0:
                # ── NOTA NORMAL ───────────────────────────────────────────
                if not head_visible:
                    continue
                h.draw_rect(lx + 4, ny_head - note_h // 2,
                            lane_w - 8, note_h, col)
                continue

            # ── HOLD NOTE ────────────────────────────────────────────────

            # Posição Y do marcador de fim (desce como nota independente)
            frac_end       = 1.0 - (dt_end / self.rhythm_fall_time)
            ny_end         = int(track_top + frac_end * track_h)
            ny_end_clamped = max(track_top, min(ny_end, track_top + track_h))

            # Topo do corpo
            if dt_end > self.rhythm_fall_time:
                body_top = track_top   # fim ainda não entrou na tela
            else:
                body_top = ny_end_clamped

            # Base do corpo
            if holding_now:
                body_bot = hit_y       # ancorado na linha de acerto
            else:
                body_bot = ny_head - note_h // 2

            body_h  = max(0, body_bot - body_top)
            body_cx = lx + lane_w // 2
            body_w  = 20

            # Corpo dourado
            if body_h > 0:
                h.draw_rect(body_cx - body_w // 2 - 2, body_top,
                            body_w + 4, body_h,
                            (0.0, 0.0, 0.0), alpha=0.65)
                h.draw_rect(body_cx - body_w // 2, body_top,
                            body_w, body_h,
                            (0.85, 0.65, 0.10), alpha=0.88)
                h.draw_rect(body_cx - 2, body_top,
                            4, body_h,
                            (1.0, 0.95, 0.55), alpha=0.75)

            # Marcador de FIM (branco-dourado, passa pelo NGC = hora de soltar)
            if end_visible or (holding_now and dt_end > -0.3):
                h.draw_rect(lx + 1, ny_end_clamped - end_mk_h // 2 - 1,
                            lane_w - 2, end_mk_h + 2,
                            (0.0, 0.0, 0.0), alpha=0.80)
                h.draw_rect(lx + 2, ny_end_clamped - end_mk_h // 2,
                            lane_w - 4, end_mk_h,
                            (1.0, 0.93, 0.42), alpha=0.98)
                h.draw_rect(lx + 5, ny_end_clamped - 2,
                            lane_w - 10, 4,
                            (0.28, 0.12, 0.0), alpha=0.88)

            # Cabeça dourada (só enquanto não foi pressionada)
            if head_visible and not holding_now:
                h.draw_rect(lx + 2, ny_head - note_h // 2 - 1,
                            lane_w - 4, note_h + 2,
                            (0.0, 0.0, 0.0), alpha=0.80)
                h.draw_rect(lx + 3, ny_head - note_h // 2,
                            lane_w - 6, note_h,
                            (1.0, 0.80, 0.10), alpha=1.0)
                h.draw_rect(lx + 7, ny_head - note_h // 2 + 3,
                            lane_w - 14, note_h - 6,
                            (1.0, 0.97, 0.70), alpha=0.70)
    def _draw_menu_background(self, hud):
        """
        Tela de título: céu noturno em gradiente contínuo, campo de estrelas com
        profundidade, lua/orbe arcano, silhueta de torre ao fundo e título em
        estandarte dourado — clima de fantasia medieval / Re:Zero.
        """
        sw, sh = self.screen_w, self.screen_h

        # ── Céu noturno (gradiente único, sem emendas visíveis) ────────────────
        hud.draw_gradient_rect(0, 0, sw, sh, (0.02, 0.02, 0.07), (0.12, 0.08, 0.10), steps=16)

        # ── Lua / orbe arcano no fundo ──────────────────────────────────────────
        moon_cx, moon_cy, moon_r = sw * 0.84, sh * 0.16, sh * 0.055
        hud.draw_medallion(moon_cx, moon_cy, moon_r, (0.85, 0.85, 0.95), ring_color=(0.30, 0.30, 0.50))
        hud.draw_gem(moon_cx, moon_cy, moon_r * 0.4, (0.95, 0.95, 1.0), sides=14, highlight=False)

        # ── Campo de estrelas (PRNG determinístico — mesmo céu a cada frame) ───
        rnd = 1
        def _next():
            nonlocal rnd
            rnd = (rnd * 1664525 + 1013904223) & 0xFFFFFFFF
            return rnd

        for _ in range(140):
            sx = (_next() >> 8) % sw
            sy = (_next() >> 8) % int(sh * 0.60)
            depth = ((_next() >> 16) % 100) / 100.0      # 0 = distante/fraca · 1 = próxima/brilhante
            size = 1 + round(depth * 2)
            b = 0.55 + depth * 0.45
            col = (min(1.0, b), min(1.0, b), min(1.0, b + (0.08 if depth > 0.7 else 0.0)))
            hud.draw_rect(sx, sy, size, size, col, alpha=0.5 + depth * 0.5)
            if depth > 0.88:
                # cintilação: pequena cruz de luz nas estrelas mais brilhantes
                hud.draw_rect(sx - 2, sy, 5, 1, col, alpha=0.45)
                hud.draw_rect(sx, sy - 2, 1, 5, col, alpha=0.45)

        # ── Silhueta da torre ao fundo, à esquerda ──────────────────────────────
        ground_y = sh * 0.66
        tx = sw * 0.16
        segments = [
            (sw * 0.075, sh * 0.11),
            (sw * 0.055, sh * 0.095),
            (sw * 0.040, sh * 0.085),
            (sw * 0.026, sh * 0.075),
        ]
        y_cur = ground_y
        for w, h in segments:
            y_cur -= h
            hud.draw_rect(tx - w / 2, y_cur, w, h, (0.035, 0.03, 0.07))
        hud.draw_gem(tx, y_cur - 6, 5, (0.55, 0.82, 1.0), sides=8)  # luz arcana no topo

        # ── Estandarte do título ────────────────────────────────────────────────
        title_w = min(560, sw * 0.62)
        title_h = 64
        title_y = int(sh * 0.06)
        hud.draw_banner(
            "TORRE DE PLÊIADES", sw / 2, title_y, w=title_w, h=title_h,
            base_color=(0.10, 0.06, 0.20), edge_color=(0.68, 0.55, 0.22),
            text_color=(235, 220, 255), text_size=34, notch=min(28, title_w * 0.05),
        )

        # ── Divisor decorativo com gemas nas pontas ─────────────────────────────
        deco_y = title_y + title_h + 14
        deco_w = title_w * 0.45
        hud.draw_rect(sw / 2 - deco_w / 2, deco_y, deco_w, 2, (0.78, 0.64, 0.28))
        hud.draw_gem(sw / 2 - deco_w / 2, deco_y + 1, 4, (0.78, 0.64, 0.28), sides=4)
        hud.draw_gem(sw / 2 + deco_w / 2, deco_y + 1, 4, (0.78, 0.64, 0.28), sides=4)

        # ── Subtítulo ────────────────────────────────────────────────────────────
        hud.draw_text("Re:Zero – uma nova jornada", sw // 2, deco_y + 22, 18,
                    (210, 195, 230), center=True, shadow=True)

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
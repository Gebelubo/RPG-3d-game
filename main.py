"""
main.py  –  Pleiades Tower RPG (Re:Zero)
Natsuki Subaru – action RPG em terceira pessoa.

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
"""
import os, sys, math, random
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

# ── Room dimensions ───────────────────────────────────────────────────────────
ROOM_W  = 20.0
ROOM_D  = 20.0
ROOM_H  = 8.0
WALL_T  = 0.5

# ── Helpers ───────────────────────────────────────────────────────────────────

def make_box_mesh(name, w, h, d, color, ka=0.2, kd=0.8, ks=0.2, shin=16):
    from engine.mesh import ProceduralMesh
    from engine.mesh import make_cube
    verts, idxs = make_cube(1.0)
    return ProceduralMesh(name, verts, idxs, base_color=color, ka=ka, kd=kd, ks=ks, shininess=shin)


def _load_obj_model(path, position=(0,0,0), rotation=(0,0,0), scale=(1,1,1)):
    mesh_data_list = OBJLoader().load(path)
    if not mesh_data_list:
        return None

    parent = SceneNode(
        os.path.splitext(os.path.basename(path))[0],
        position=position,
        rotation=rotation,
        scale=scale
    )

    for md in mesh_data_list:
        mesh = Mesh(md)

        texture = None
        if md.texture_path:
            try:
                texture = Texture(md.texture_path)
            except Exception as exc:
                print(f"Failed to load texture {md.texture_path}: {exc}")

        child = SceneNode(
            md.name,
            mesh=mesh,
            texture=texture
        )

        # Correção específica do Heartless
        if os.path.basename(path) == "Shadow.obj":
            child.position = [0.0, 0.5, -2.38]

        parent.children.append(child)

    return parent

class Game:
    def __init__(self):
        self._init_window()
        self._init_gl()
        self._init_shaders()
        self._init_scene()
        self._init_game_state()

    def _init_window(self):
        pygame.init(); pygame.font.init()
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

    def _init_scene(self):
        self.scene  = Scene()
        self.camera = Camera()
        self.scene.set_aspect(self.screen_w / self.screen_h)

        pv, pi = make_plane(ROOM_W, ROOM_D, 10)
        floor_mesh = ProceduralMesh("floor", pv, pi, base_color=(0.22,0.18,0.28),
                                    ka=0.3, kd=0.7, ks=0.1, shininess=8)
        floor_tex = ProceduralTexture(128, color_a=(55,45,70), color_b=(40,33,55))
        self.scene.add(SceneNode("floor", mesh=floor_mesh, texture=floor_tex))

        ceiling_mesh = ProceduralMesh("ceiling", pv, pi, base_color=(0.15, 0.12, 0.20),
                                       ka=0.2, kd=0.6, ks=0.05, shininess=4)
        self.scene.add(SceneNode("ceiling", mesh=ceiling_mesh,
                                  position=(0, ROOM_H, 0), rotation=(180,0,0)))

        wall_color = (0.28, 0.22, 0.35)
        pv, pi = make_plane(ROOM_W, ROOM_H, 1)
        # interior room walls as single planes with normals facing inward
        wall_n = SceneNode("wall_n", mesh=ProceduralMesh("wall_n", pv, pi, base_color=wall_color,
                                                            ka=0.25, kd=0.75, ks=0.1, shininess=8),
                           position=(0, ROOM_H/2, -ROOM_D/2), rotation=(90, 0, 0))
        wall_s = SceneNode("wall_s", mesh=ProceduralMesh("wall_s", pv, pi, base_color=wall_color,
                                                            ka=0.25, kd=0.75, ks=0.1, shininess=8),
                           position=(0, ROOM_H/2, ROOM_D/2), rotation=(-90, 180, 0))
        wall_w = SceneNode("wall_w", mesh=ProceduralMesh("wall_w", pv, pi, base_color=wall_color,
                                                            ka=0.25, kd=0.75, ks=0.1, shininess=8),
                           position=(-ROOM_W/2, ROOM_H/2, 0), rotation=(0, 0, -90))
        wall_e = SceneNode("wall_e", mesh=ProceduralMesh("wall_e", pv, pi, base_color=wall_color,
                                                            ka=0.25, kd=0.75, ks=0.1, shininess=8),
                           position=(ROOM_W/2, ROOM_H/2, 0), rotation=(0, 0, 90))
        self.scene.add(wall_n); self.scene.add(wall_s)
        self.scene.add(wall_w); self.scene.add(wall_e)

        pillar_color = (0.38, 0.30, 0.48)
        cv, ci = make_cube(1.0)
        for px, pz in [(-8,-8),(8,-8),(-8,8),(8,8)]:
            pm = ProceduralMesh("pillar", cv, ci, base_color=pillar_color,
                                ka=0.3, kd=0.7, ks=0.3, shininess=24)
            self.scene.add(SceneNode("pillar", mesh=pm, position=(px,ROOM_H/2,pz),
                                      scale=(0.8,ROOM_H,0.8)))

        altar_v, altar_i = make_cube(1.0)
        altar_m = ProceduralMesh("altar", altar_v, altar_i, base_color=(0.45,0.35,0.55),
                                  ka=0.3, kd=0.8, ks=0.5, shininess=32)
        self.scene.add(SceneNode("altar", mesh=altar_m, position=(0,0.25,0), scale=(4,0.5,4)))

        # Central floating crystal/orb (will be replaced by the Heartless model)
        ov, oi = make_sphere(0.4, 16, 16)
        orb_m = ProceduralMesh("orb", ov, oi, base_color=(0.8,0.5,1.0),
                                ka=0.9, kd=0.2, ks=0.8, shininess=64)
        self.orb_node = SceneNode("orb", mesh=orb_m, position=(0,1.8,0))
        def _orb_pulse(node, dt, _t=[0.0]):
            _t[0] += dt
            s = 0.35 + 0.08*math.sin(_t[0]*2.5)
            node.scale = [s, s, s]
            node.rotation[1] += 40*dt
        self.orb_node.set_animator(_orb_pulse)
        # keep orb invisible because the Heartless model will sit here
        self.orb_node.visible = False

        # --- Build platform / tower / obelisks / crystal using procedural geometry
        platform = make_box_mesh("platform_box", 12.0, 0.6, 12.0, color=(0.68,0.64,0.58), ka=0.2, kd=0.7, ks=0.15, shin=24)
        platform_node = SceneNode("platform", mesh=platform, position=(0, -0.3, 0))
        self.scene.add(platform_node)

        tower = make_box_mesh("tower_box", 3.0, 12.0, 3.0, color=(0.86,0.83,0.78), ka=0.25, kd=0.85, ks=0.25, shin=48)
        tower_node = SceneNode("tower", mesh=tower, position=(0, 6.0, 0))
        self.scene.add(tower_node)

        # simple frontal stair (3 steps)
        step_h = 0.4
        for i in range(3):
            step = make_box_mesh(f"step_{i}", 4.0, step_h, 1.6, color=(0.7,0.65,0.6), ka=0.2, kd=0.7, ks=0.12, shin=12)
            step_node = SceneNode(f"step_{i}", mesh=step, position=(0, (i * step_h) - 0.3, 3.0 - i * 1.2))
            self.scene.add(step_node)

        # four obelisks at corners
        obs_positions = [(-5.5, 0, -5.5), (5.5, 0, -5.5), (-5.5, 0, 5.5), (5.5, 0, 5.5)]
        for j, pos in enumerate(obs_positions):
            ob = make_box_mesh(f"obelisk_{j}", 0.8, 6.0, 0.8, color=(0.08,0.08,0.1), ka=0.05, kd=0.15, ks=0.6, shin=128)
            ob_node = SceneNode(f"obelisk_{j}", mesh=ob, position=(pos[0], 3.0, pos[2]))
            self.scene.add(ob_node)

        # magical crystal on top of tower
        cv, ci = make_sphere(0.5, 12, 12)
        crystal = ProceduralMesh("crystal", cv, ci, base_color=(0.2,0.9,1.0), ka=0.0, kd=0.6, ks=1.0, shininess=256)
        crystal_node = SceneNode("crystal", mesh=crystal, position=(0, 13.4, 0))
        def _crystal_spin(node, dt, _t=[0.0]):
            _t[0] += dt
            node.rotation[1] += 35*dt
            node.scale = [0.6 + 0.06*math.sin(_t[0]*2.2)]*3
        crystal_node.set_animator(_crystal_spin)
        self.scene.add(crystal_node)

        # Try to replace procedural pieces with OBJ/MTL models if present
        try:
            tower_dir = os.path.join(_HERE, "assets", "models", "tower")
            p_obj = os.path.join(tower_dir, "platform.obj")
            t_obj = os.path.join(tower_dir, "tower.obj")
            c_obj = os.path.join(tower_dir, "crystal.obj")
            o_obj = os.path.join(tower_dir, "obelisk.obj")

            loaded = False
            if os.path.exists(p_obj):
                pnode = _load_obj_model(p_obj, position=(0, -0.3, 0), rotation=(0,0,0), scale=(1,1,1))
                if pnode:
                    self.scene.add(pnode); self.scene.remove(platform_node); loaded = True
            if os.path.exists(t_obj):
                tnode = _load_obj_model(t_obj, position=(0, 6.0, 0), rotation=(0,0,0), scale=(1,1,1))
                if tnode:
                    self.scene.add(tnode); self.scene.remove(tower_node); loaded = True
            if os.path.exists(c_obj):
                cnode = _load_obj_model(c_obj, position=(0, 13.4, 0), rotation=(0,0,0), scale=(1,1,1))
                if cnode:
                    self.scene.add(cnode); self.scene.remove(crystal_node); loaded = True
            if os.path.exists(o_obj):
                obs_pos = [(-5.5, 0, -5.5), (5.5, 0, -5.5), (-5.5, 0, 5.5), (5.5, 0, 5.5)]
                for j, pos in enumerate(obs_pos):
                    onode = _load_obj_model(o_obj, position=(pos[0], 3.0, pos[2]), rotation=(0,0,0), scale=(1,1,1))
                    if onode:
                        self.scene.add(onode)
                        loaded = True
            if loaded:
                print("Loaded tower OBJ assets and replaced procedural geometry.")
        except Exception as exc:
            print("Failed to load tower OBJ assets:", exc)
        self.player_node = _load_obj_model(os.path.join(_HERE, "assets", "models", "Subaru", "subaru.obj"),
                           position=(0,0,3), rotation=(0,180,0), scale=(0.25,0.25,0.25))
        if self.player_node:
            self.scene.add(self.player_node)
        else:
            sv, si = make_sphere(0.45, 12, 12)
            player_mesh = ProceduralMesh("subaru", sv, si, base_color=(0.2,0.35,0.6),
                                          ka=0.3, kd=0.8, ks=0.4, shininess=24)
            self.player_node = SceneNode("subaru", mesh=player_mesh, position=(0,0.5,3))
            hv, hi = make_sphere(0.28, 10, 10)
            head_m = ProceduralMesh("head", hv, hi, base_color=(0.85,0.70,0.55),
                                     ka=0.3, kd=0.8, ks=0.1, shininess=8)
            head_node = SceneNode("head", mesh=head_m, position=(0,0.75,0))
            self.player_node.children.append(head_node)
            self.scene.add(self.player_node)

        # Emilia much larger to match desired proportions
        self.emilia_node = _load_obj_model(os.path.join(_HERE, "assets", "models", "Emilia", "emilia.obj"),
                           position=(-7,0,3), rotation=(0,180,0), scale=(2.0,2.0,2.0))
        if self.emilia_node:
            self.scene.add(self.emilia_node)

        self.enemies = []
        # Heartless large and placed atop the second stair (middle step)
        heartless_node = _load_obj_model(os.path.join(_HERE, "assets", "models", "Heartless", "Shadow.obj"),
                                         position=(0,0.9,0), rotation=(0,180,0), scale=(2.2,2.2,2.2))
        if heartless_node:
            step_idx = 1
            step_h = 0.4
            step_y = (step_idx * step_h) - 0.3
            step_z = 3.0 - step_idx * 1.2
            heartless_node.position = [0.0, step_y + 0.6, step_z - 2.4]
            heartless_node.rotation = [0.0, 180.0, 0.0]
            self.scene.add(heartless_node)
            e = Enemy("Heartless", level=2, world_pos=[0.0, step_y + 0.6, step_z], stationary=True)
            e.respawns_left = 3
            e.spawn_pos = [0.0, step_y + 0.6, step_z]
            e.aggro = False
            e.aggro_range = 1.6
            self.enemies.append((e, heartless_node))
        else:
            # fallback procedural heartless placed at center
            e = Enemy("Heartless", level=2, world_pos=[0.0, 1.8, 0.0], stationary=True)
            ev2, ei2 = make_sphere(0.4, 10, 10)
            em = ProceduralMesh("heartless", ev2, ei2, base_color=(0.7,0.1,0.1),
                                 ka=0.3, kd=0.8, ks=0.3, shininess=16)
            node = SceneNode("heartless", mesh=em, position=[0.0, 1.8, 0.0])
            node.rotation = [0.0, 180.0, 0.0]
            self.scene.add(node)
            e.aggro = False; e.aggro_range = 1.6
            self.enemies.append((e, node))

        self.scene.light.orbit    = True
        self.scene.light.orbit_r  = 6.0
        self.scene.light.pos[1]   = ROOM_H - 1.0
        self.scene.light.intensity = 1.3
        self.scene.light.color    = np.array([0.8, 0.6, 1.0], dtype=np.float32)

        lv2, li2 = make_sphere(0.18, 8, 8)
        lm = ProceduralMesh("light_ball", lv2, li2, base_color=(1.0,0.9,0.5),
                             ka=1.0, kd=0.0, ks=0.0, shininess=1)
        self.light_node = SceneNode("light_vis", mesh=lm)
        self.scene.add(self.light_node)

    def _init_game_state(self):
        self.input     = InputManager()
        self.player    = Player("Natsuki Subaru")
        self.combat    = None
        self.game_mode = "menu"
        self.wireframe = False
        self.clock     = pygame.time.Clock()
        self.hud       = HUD(self.screen_w, self.screen_h, self.unlit_shader)
        self.menus     = MenuManager()
        self.death_timer = 0.0
        self._combat_enemy_ref = None
        self._push_title_menu()

    def _push_title_menu(self):
        def start():
            self.menus.clear(); self.game_mode = "explore"
            self.input.capture_mouse(True)

        def quit_game():
            pygame.quit(); sys.exit(0)

        def push_settings():
            def back():
                self.menus.pop()
            def toggle_fullscreen():
                # simple toggle that announces state
                self.fullscreen = not getattr(self, 'fullscreen', False)
                self.hud.add_popup(f"Fullscreen: {self.fullscreen}", 1.8, (180,180,255))
            s_menu = Menu("Configurações", [
                MenuItem("Toggle Fullscreen", toggle_fullscreen),
                MenuItem("Voltar", back),
            ])
            self.menus.push(s_menu)

        def push_tutorial():
            def back():
                self.menus.pop()
            t_menu = Menu("Tutorial", [
                MenuItem("Como jogar: WASD mover, Z atacar", lambda: None),
                MenuItem("Voltar", back),
            ])
            self.menus.push(t_menu)

        title_menu = Menu("=== Torre de Plêiades ===", [
            MenuItem("Nova Partida", start),
            MenuItem("Configurações", push_settings),
            MenuItem("Tutorial", push_tutorial),
            MenuItem("Sair", quit_game),
        ])
        self.menus.push(title_menu)

    def _push_pause_menu(self):
        def resume():
            self.menus.pop(); self.game_mode = "explore"
            self.input.capture_mouse(True)
        def title():
            self.menus.clear(); self.game_mode = "menu"
            self._push_title_menu(); self.input.capture_mouse(False)
        self.menus.push(Menu("── PAUSADO ──", [
            MenuItem("Continuar",     resume),
            MenuItem("Menu Principal",title),
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
        self.menus.push(Menu("── COMBATE ──", [
            MenuItem("Atacar",   attack),
            MenuItem("Poção",    use_potion),
            MenuItem("Fugir",    flee),
        ]))

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
                self._trigger_death()
                return
            self.game_mode = "explore"; self.input.capture_mouse(True)

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
        self.player.world_pos = [0.0, 0.0, 3.0]
        self.player.velocity  = [0.0, 0.0, 0.0]
        for e, node in self.enemies:
            e.dead = False; e.aggro = False
            e.stats.hp = e.stats.max_hp
            node.visible = True
        self.game_mode = "explore"; self.input.capture_mouse(True)
        self.hud.add_popup("Return by Death...", 3.0, (180,80,80))

    def run(self):
        while True:
            dt = min(self.clock.tick(60) / 1000.0, 0.05)
            self.input.update()
            if self.input.should_quit: break
            self._handle_global_input(dt)
            self._update_game(dt)
            self.scene.update(dt)
            self._render()
        pygame.quit()

    def _handle_global_input(self, dt):
        if self.input.key_pressed("f1"):
            self.wireframe = not self.wireframe

        if self.game_mode == "explore":
            dx, dy = self.input.mouse_delta
            if dx or dy:
                self.camera.process_mouse(dx, dy)
            if self.input.key_pressed("escape"):
                self._push_pause_menu()
            if self.input.key_pressed("z"): self._player_melee_attack()
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
            if self.input.mouse_clicked:
                mx, my = self.input.mouse_pos
                action = self.hud.handle_click(mx, my, self.player)
                if action == "attack": self._player_melee_attack()
                sub = self.hud.handle_submenu_click(mx, my, self.player)
                if sub:
                    if sub.startswith("spell:"): self._cast_spell(sub[6:])
                    elif sub.startswith("item:"): self._use_item_explore(sub[5:])

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

    def _player_melee_attack(self):
        p = self.player
        if p.attack_cd > 0: return
        p.is_attacking = True; p.attack_timer = 0.4; p.attack_cd = 0.6
        p.combo_count = (p.combo_count + 1) % 3; p.combo_timer = 0.8
        hit = False
        for e, node in self.enemies:
            if e.dead: continue
            dx = e.world_pos[0] - p.world_pos[0]
            dz = e.world_pos[2] - p.world_pos[2]
            if math.sqrt(dx*dx+dz*dz) < 1.8:
                damage = max(1, p.stats.atk + random.randint(-2, 2) - e.stats.defense)
                actual = e.stats.take_damage(damage)
                self.hud.add_popup(f"Hit {e.stats.name} -{actual} HP", 1.2, (255,200,140))
                if not e.stats.is_alive():
                     
                    leveled = False

                    if hasattr(e, "respawns_left") and e.respawns_left > 0:
                        e.respawns_left -= 1

                        e.stats.hp = e.stats.max_hp
                        e.world_pos = list(e.spawn_pos)
                        node.position = list(e.spawn_pos)

                        self.hud.add_popup(
                            f"Heartless retornou! ({e.respawns_left} restantes)",
                            2.0,
                            (255, 120, 120)
                        )
                    else:
                        e.dead = True
                        node.visible = False
                        
                        xp = e.stats.level * 20 + random.randint(5, 15)
                        leveled = p.stats.gain_xp(xp)
                        
                        self.hud.add_popup(f"+{xp} XP", 2.0, (230,200,80))

                    if leveled:
                        self.hud.add_popup("LEVEL UP!", 3.0, (255,230,50))
                hit = True
                break
        if not hit:
            self.hud.add_popup("Swoosh!", 0.8, (200,200,200))

    def _cast_spell(self, spell_id):
        sp = SPELL_DB.get(spell_id)
        if not sp: return
        if spell_id == "invisible_providence":
            if self.player.stats.hp <= 40:
                self.hud.add_popup("Vida insuficiente!", 1.5, (255,100,100))
                return
            self.player.stats.hp = max(1, self.player.stats.hp - 40)
        else:
            if not self.player.stats.use_mp(sp.mp_cost):
                self.hud.add_popup("MP insuficiente!", 1.5, (100,100,255))
                return

        if spell_id == "emt":
            self.player.stats.shield_time = 10.0
            self.hud.add_popup("EMT ativado! Protegido por 10s", 2.0, (80,220,255))
            return

        nearest = None
        nearest_dist = 999.0
        for e, node in self.enemies:
            if e.dead: continue
            dx = e.world_pos[0] - self.player.world_pos[0]
            dz = e.world_pos[2] - self.player.world_pos[2]
            dist = math.sqrt(dx*dx + dz*dz)
            if dist < 6.0 and dist < nearest_dist:
                nearest = (e, node, dist)
                nearest_dist = dist

        if not nearest:
            self.hud.add_popup(f"{sp.name} – sem alvo próximo", 1.2, (140,140,255))
            return

        e, node, _ = nearest
        if spell_id == "shamac":
            e.blind_time = 10.0
            e.aggro = False
            self.hud.add_popup(f"Shamac! {e.stats.name} perdeu sua pista.", 2.2, (180,120,255))
            return

        dmg = e.stats.take_damage(sp.damage)
        self.hud.add_popup(f"{sp.name}! -{dmg} HP", 2.0, (180,120,255))

        if not e.stats.is_alive():

            leveled = False

            if hasattr(e, "respawns_left") and e.respawns_left > 0:
                e.respawns_left -= 1

                e.stats.hp = e.stats.max_hp
                e.world_pos = list(e.spawn_pos)

                node.position = list(e.spawn_pos)
                node.visible = True

                self.hud.add_popup(
                    f"Heartless retornou! ({e.respawns_left} restantes)",
                    2.0,
                    (255,120,120)
                )

            else:
                e.dead = True
                node.visible = False

                xp = e.stats.level * 20 + random.randint(5, 15)
                leveled = self.player.stats.gain_xp(xp)

                self.hud.add_popup(
                    f"+{xp} XP",
                    2.0,
                    (230,200,80)
                )

                if leveled:
                    self.hud.add_popup(
                        "LEVEL UP!",
                        3.0,
                        (255,230,50)
                    )

    def _use_item_explore(self, item_id):
        item = ITEM_DB.get(item_id)

        if not item:
            return

        if not self.player.inventory.remove(item_id, 1):
            self.hud.add_popup("Item não encontrado!", 1.5, (255,100,100))
            return

        if hasattr(item, "heal_hp") and item.heal_hp > 0:
            self.player.stats.hp = min(
                self.player.stats.max_hp,
                self.player.stats.hp + item.heal_hp
            )

        if hasattr(item, "heal_mp") and item.heal_mp > 0:
            self.player.stats.mp = min(
                self.player.stats.max_mp,
                self.player.stats.mp + item.heal_mp
            )

        self.hud.add_popup(
            f"Usou {item.name}",
            1.5,
            (120,255,120)
        )
    def _update_game(self, dt):
        if self.game_mode == "death":
            self.death_timer -= dt
            if self.death_timer <= 0.0:
                self._respawn(); return
        if self.game_mode != "explore": return

        self._update_player(dt)
        self._update_enemies(dt)
        self.hud.update(dt)
        lp = self.scene.light.pos
        self.light_node.position = [float(lp[0]), float(lp[1]), float(lp[2])]

    def _update_player(self, dt):
        p = self.player
        keys = self.input.held_keys

        if p.attack_cd > 0:   p.attack_cd   -= dt
        if p.attack_timer > 0:p.attack_timer -= dt
        else:                  p.is_attacking = False
        if p.combo_timer > 0:  p.combo_timer  -= dt
        else:                  p.combo_count   = 0
        if p.invincible > 0:   p.invincible   -= dt
        if p.stats.shield_time > 0: p.stats.shield_time -= dt

        move_x, move_z = 0.0, 0.0
        fwd = self.camera.flat_forward
        rgt = self.camera.flat_right

        if not p.is_rolling:
            if "w" in keys: move_x += fwd[0]; move_z += fwd[2]
            if "s" in keys: move_x -= fwd[0]; move_z -= fwd[2]
            if "a" in keys: move_x -= rgt[0]; move_z -= rgt[2]
            if "d" in keys: move_x += rgt[0]; move_z += rgt[2]

            mag = math.sqrt(move_x*move_x + move_z*move_z)
            if mag > 0:
                move_x /= mag; move_z /= mag
                p.facing_deg = math.degrees(math.atan2(move_x, move_z))

            spd = p.WALK_SPEED
            p.velocity[0] = move_x * spd
            p.velocity[2] = move_z * spd

            if "space" in keys and p.on_ground:
                p.velocity[1] = p.JUMP_FORCE
                p.on_ground = False

            if self.input.key_pressed("lshift") and p.on_ground and mag > 0:
                p.is_rolling  = True
                p.roll_timer  = p.ROLL_TIME
                p.roll_dir    = [move_x, move_z]
                p.invincible  = p.ROLL_TIME
        else:
            p.roll_timer -= dt
            p.velocity[0] = p.roll_dir[0] * p.ROLL_SPEED
            p.velocity[2] = p.roll_dir[1] * p.ROLL_SPEED
            if p.roll_timer <= 0.0:
                p.is_rolling = False
                p.velocity[0] = p.velocity[2] = 0.0

        if not p.on_ground:
            p.velocity[1] += p.GRAVITY * dt

        p.world_pos[0] += p.velocity[0] * dt
        p.world_pos[1] += p.velocity[1] * dt
        p.world_pos[2] += p.velocity[2] * dt

        def sample_ground_height(x, z):
            if abs(x) <= 2.0:
                if z > 2.4 and z <= 4.0:
                    return 0.2
                if z > 1.2 and z <= 2.4:
                    return 0.6
                if z > -0.4 and z <= 1.2:
                    return 1.0
            return 0.0

        ground_y = sample_ground_height(p.world_pos[0], p.world_pos[2])
        if p.world_pos[1] < ground_y:
            p.world_pos[1] = ground_y
            p.velocity[1]  = 0.0
            p.on_ground    = True

        half_w = ROOM_W/2 - 0.6; half_d = ROOM_D/2 - 0.6
        p.world_pos[0] = max(-half_w, min(half_w, p.world_pos[0]))
        p.world_pos[2] = max(-half_d, min(half_d, p.world_pos[2]))

        self.player_node.position = [p.world_pos[0], p.world_pos[1]+0.5, p.world_pos[2]]
        self.player_node.rotation[1] = p.facing_deg

        # Build simple blocker list from scene nodes to prevent camera clipping into floating objects
        blockers = []
        for node in self.scene.nodes:
            if node is self.player_node: continue
            if not getattr(node, 'visible', True): continue
            # only consider nodes that are floating above the player's chest
            node_pos = node.position
            if node_pos[1] <= p.world_pos[1] + 0.6:
                continue
            # only nearby floating nodes (avoid distant room geometry)
            dx = node_pos[0] - p.world_pos[0]; dz = node_pos[2] - p.world_pos[2]
            if math.sqrt(dx*dx + dz*dz) > 10.0: continue
            sx, sy, sz = node.scale if hasattr(node, 'scale') else (1.0,1.0,1.0)
            radius = max(abs(sx), abs(sz)) * 0.7
            blockers.append({"pos": node_pos, "radius": radius})

        self.camera.update_third_person(p.world_pos, blockers=blockers)

    def _update_enemies(self, dt):
        for e, node in self.enemies:
            if e.dead: continue
            e.update(self.player.world_pos, dt)
            node.position = list(e.world_pos)
            # Do not update visual rotation for stationary enemies
            if not getattr(e, 'stationary', False):
                node.rotation[1] = e.facing_deg
            if e.aggro and self.player.invincible <= 0.0:
                dx = e.world_pos[0]-self.player.world_pos[0]
                dz = e.world_pos[2]-self.player.world_pos[2]
                if math.sqrt(dx*dx+dz*dz) < e.attack_range:
                    dmg = e.try_attack(self.player.stats)
                    if dmg > 0:
                        self.player.invincible = 0.5
                        self.hud.add_popup(f"-{dmg} HP", 1.2, (255,80,80))
                        if self.player.is_dead:
                            self._trigger_death()

    def _render(self):
        glPolygonMode(GL_FRONT_AND_BACK, GL_LINE if self.wireframe else GL_FILL)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        self.scene.draw(self.phong_shader, self.camera)
        glDisable(GL_DEPTH_TEST)
        self._draw_hud()
        glEnable(GL_DEPTH_TEST)
        pygame.display.flip()

    def _draw_hud(self):
        h = self.hud; sw = self.screen_w; sh = self.screen_h

        if self.game_mode == "death":
            h.draw_death_screen(); return

        # Do not draw the in-game HUD while on the menu screen
        if self.game_mode != "menu":
            h.draw_main_hud(self.player, self.game_mode)
        else:
            # draw a dedicated menu background using HUD primitives
            self._draw_menu_background(h)

        if self.game_mode in ("menu","combat"):
            pw, ph = 340, 240
            px = sw//2 - pw//2; py = sh//2 - ph//2
            h.draw_bar(px-12, py-12, pw+24, ph+24, 1.0,
                       (0.04,0.04,0.10), (0.04,0.04,0.10))
            self.menus.draw(h, px, py)

        if self.combat:
            msgs = self.combat.log.recent(5)
            h.draw_combat_log(msgs)

        if self.game_mode == "explore":
            h.draw_text("[WASD] Mover  [Espaço] Pular  [Shift] Rolar  [Z] Atacar  [X/C/V] Menus  [ESC] Pausar",
                        10, sh-24, 12, (140,140,140))

    def on_resize(self, w, h):
        self.screen_w = w; self.screen_h = h
        glViewport(0, 0, w, h)
        self.scene.set_aspect(w/h)
        self.hud.resize(w, h)

    def _draw_menu_background(self, hud: HUD):
        # simple stylized background: gradient bands + title art + stars
        sw, sh = self.screen_w, self.screen_h
        # base gradient bands
        hud.draw_rect(0, 0, sw, sh, (0.03, 0.03, 0.08))
        hud.draw_rect(0, int(sh*0.15), sw, int(sh*0.1), (0.06, 0.04, 0.12))
        hud.draw_rect(0, int(sh*0.25), sw, int(sh*0.12), (0.08, 0.06, 0.18))

        # decorative title
        hud.draw_text("Torre de Plêiades", sw//2, int(sh*0.10), 36, (235,220,255), bold=True, center=True)
        hud.draw_text("Re:Zero – uma nova jornada", sw//2, int(sh*0.175), 18, (200,180,220), center=True)

        # subtle starfield (deterministic)
        rnd = 1
        for i in range(80):
            rnd = (rnd * 1664525 + 1013904223) & 0xFFFFFFFF
            sx = (rnd >> 8) % sw
            rnd = (rnd * 1664525 + 1013904223) & 0xFFFFFFFF
            sy = (rnd >> 8) % int(sh*0.55)
            hud.draw_text(".", sx, sy, 10, (220,220,255))


class InputManagerEx(InputManager):
    def __init__(self):
        super().__init__()
        self.mouse_clicked = False
        self.mouse_pos = (0, 0)

    def update(self):
        super().update()
        self.mouse_clicked = False
        for event in pygame.event.get(pygame.MOUSEBUTTONDOWN):
            if event.button == 1:
                self.mouse_clicked = True
                self.mouse_pos = event.pos


if __name__ == "__main__":
    game = Game()
    game.input.__class__ = InputManagerEx
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

    orig_run = game.run
    def patched_run():
        while True:
            dt = min(game.clock.tick(60)/1000.0, 0.05)
            game.input.update()
            if game.input.should_quit: break
            for event in pygame.event.get(pygame.VIDEORESIZE):
                game.on_resize(event.w, event.h)
            game._handle_global_input(dt)
            game._update_game(dt)
            game.scene.update(dt)
            game._render()
        pygame.quit()
    patched_run()

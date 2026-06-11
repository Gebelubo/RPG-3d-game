"""
main.py  –  RPG3D base game.

Controls:
  WASD          – move
  Mouse         – look (captured while playing)
  E             – interact / start combat
  ESC           – pause / release mouse
  F1            – toggle wireframe (debug)

Architecture:
  pygame        → window + context creation + events ONLY
  OpenGL 4.0    → all rendering
  NumPy         → all math
  Pillow        → image decoding
"""

import os
import sys
import math
import random
import pygame
from pygame.locals import DOUBLEBUF, OPENGL, RESIZABLE

from OpenGL.GL import (
    glViewport, glEnable, glDisable, glClearColor, glClear,
    glDepthFunc, glPolygonMode,
    GL_DEPTH_TEST, GL_LEQUAL, GL_COLOR_BUFFER_BIT, GL_DEPTH_BUFFER_BIT,
    GL_FRONT_AND_BACK, GL_FILL, GL_LINE,
)

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

from engine.math3d      import vec3
from engine.shader      import ShaderProgram
from engine.obj_loader  import OBJLoader
from engine.mesh        import Mesh, ProceduralMesh, make_cube, make_plane, make_sphere
from engine.texture     import Texture, ProceduralTexture
from engine.camera      import Camera
from engine.scene       import Scene, SceneNode, PointLight
from engine.input_manager import InputManager
from game.rpg_data      import Player, Stats, CombatSystem, ITEM_DB
from hud                import HUD
from menu               import Menu, MenuItem, MenuManager

import numpy as np

# ─────────────────────────────────────────────────────────────────────────────
SCREEN_W, SCREEN_H = 1280, 720
TITLE              = "RPG3D – Base Engine"
SHADER_DIR         = os.path.join(_HERE, "assets", "shaders")
MODELS_DIR         = os.path.join(_HERE, "assets", "models")
TEX_DIR            = os.path.join(_HERE, "assets", "textures")


class Game:

    def __init__(self):
        self._init_window()
        self._init_gl()
        self._init_shaders()
        self._init_scene()
        self._init_game_state()

    # ── Window ────────────────────────────────────────────────────────────────

    def _init_window(self):
        pygame.init()
        pygame.font.init()
        pygame.display.set_mode(
            (SCREEN_W, SCREEN_H),
            DOUBLEBUF | OPENGL | RESIZABLE,
        )
        pygame.display.set_caption(TITLE)
        self.screen_w = SCREEN_W
        self.screen_h = SCREEN_H

    def _init_gl(self):
        glEnable(GL_DEPTH_TEST)
        glDepthFunc(GL_LEQUAL)
        glClearColor(0.05, 0.07, 0.12, 1.0)

    def _init_shaders(self):
        def sh(v, f):
            return ShaderProgram(
                os.path.join(SHADER_DIR, v),
                os.path.join(SHADER_DIR, f),
            )
        self.phong_shader = sh("phong.vert", "phong.frag")
        self.unlit_shader = sh("unlit.vert", "unlit.frag")

    # ── Scene ─────────────────────────────────────────────────────────────────

    def _init_scene(self):
        self.scene  = Scene()
        self.camera = Camera(pos=(0, 2, 8))
        self.scene.set_aspect(self.screen_w / self.screen_h)

        # Ground (textured checkerboard)
        plane_v, plane_i = make_plane(40.0, 40.0, 8)
        plane_mesh = ProceduralMesh(
            "ground", plane_v, plane_i,
            base_color=(0.3, 0.55, 0.25), ka=0.3, kd=0.7, ks=0.1, shininess=8.0,
        )
        self.ground_tex = ProceduralTexture(128,
            color_a=(80,120,60), color_b=(60,100,45))
        self.scene.add(SceneNode("ground", mesh=plane_mesh, texture=self.ground_tex))

        # Animated spinning cube (solid colour – red)
        cube_v, cube_i = make_cube(0.8)
        cube_mesh = ProceduralMesh(
            "cube", cube_v, cube_i,
            base_color=(0.85, 0.2, 0.2), ka=0.2, kd=0.8, ks=0.9, shininess=64.0,
        )
        self.cube_node = SceneNode("spinning_cube", mesh=cube_mesh,
                                   position=(3.0, 1.5, -3.0))
        def _spin(node, dt):
            node.rotation[1] += 60.0 * dt
            node.rotation[0] += 30.0 * dt
        self.cube_node.set_animator(_spin)
        self.scene.add(self.cube_node)

        # Bobbing sphere (textured – enemy marker)
        sph_v, sph_i = make_sphere(0.7, 24, 24)
        sph_mesh = ProceduralMesh(
            "sphere", sph_v, sph_i,
            base_color=(0.6, 0.3, 0.8), ka=0.2, kd=0.7, ks=0.6, shininess=48.0,
        )
        self.enemy_tex = ProceduralTexture(64,
            color_a=(160,80,200), color_b=(80,40,120))
        self.enemy_node = SceneNode("enemy_sphere", mesh=sph_mesh,
                                    texture=self.enemy_tex,
                                    position=(-3.0, 0.7, -5.0))
        def _bob(node, dt, _t=[0.0]):
            _t[0] += dt
            node.position[1] = 0.7 + math.sin(_t[0] * 2.0) * 0.3
        self.enemy_node.set_animator(_bob)
        self.scene.add(self.enemy_node)

        # Columns (solid colour – grey)
        for cx, cz in [(-6, -6), (6, -6), (-6, -12), (6, -12)]:
            cv, ci = make_sphere(0.4, 8, 8)
            cm = ProceduralMesh("col", cv, ci,
                                base_color=(0.55, 0.5, 0.45),
                                ka=0.2, kd=0.8, ks=0.3, shininess=16.0)
            self.scene.add(SceneNode("col", mesh=cm, position=(cx, 0.4, cz)))

        # Load OBJ files from assets/models/
        self._load_obj_models()

        # Moving point light + visual marker
        self.scene.light.orbit   = True
        self.scene.light.orbit_r = 10.0
        self.scene.light.pos[1]  = 7.0
        self.scene.light.intensity = 1.1

        lv, li = make_sphere(0.25, 8, 8)
        lmesh = ProceduralMesh("light_ball", lv, li,
                               base_color=(1.0, 1.0, 0.6),
                               ka=1.0, kd=0.0, ks=0.0, shininess=1.0)
        self.light_node = SceneNode("light_vis", mesh=lmesh)
        self.scene.add(self.light_node)

    def _load_obj_models(self):
        if not os.path.isdir(MODELS_DIR):
            return
        loader = OBJLoader()
        for fname in sorted(os.listdir(MODELS_DIR)):
            if not fname.lower().endswith(".obj"):
                continue
            full = os.path.join(MODELS_DIR, fname)
            try:
                mesh_datas = loader.load(full)
            except Exception as e:
                print(f"[OBJ] Failed {fname}: {e}")
                continue
            for i, md in enumerate(mesh_datas):
                gpu_mesh = Mesh(md)
                tex = None
                if md.texture_path and os.path.isfile(md.texture_path):
                    try:
                        tex = Texture(md.texture_path)
                    except Exception:
                        pass
                node = SceneNode(
                    name=f"{fname}_{md.name}",
                    mesh=gpu_mesh,
                    texture=tex,
                    position=(i * 3.0, 0.0, -10.0),
                )
                self.scene.add(node)
                print(f"[OBJ] Loaded: {fname} / {md.name}")

    # ── Game state ────────────────────────────────────────────────────────────

    def _init_game_state(self):
        self.input   = InputManager()
        self.player  = Player("Hero")
        self.combat  = None
        self.game_mode = "menu"
        self.wireframe = False
        self.clock   = pygame.time.Clock()
        self.hud     = HUD(self.screen_w, self.screen_h, self.unlit_shader)
        self.menus   = MenuManager()
        self._push_title_menu()

    # ── Menus ─────────────────────────────────────────────────────────────────

    def _push_title_menu(self):
        def start():
            self.menus.clear()
            self.game_mode = "explore"
            self.input.capture_mouse(True)
        def quit_game():
            pygame.quit(); sys.exit(0)
        self.menus.push(Menu("=== RPG3D ===", [
            MenuItem("New Game", start),
            MenuItem("Quit",     quit_game),
        ]))

    def _push_pause_menu(self):
        def resume():
            self.menus.pop()
            self.game_mode = "explore"
            self.input.capture_mouse(True)
        def title():
            self.menus.clear()
            self.game_mode = "menu"
            self._push_title_menu()
            self.input.capture_mouse(False)
        self.menus.push(Menu("-- PAUSED --", [
            MenuItem("Resume",       resume),
            MenuItem("Title Screen", title),
        ]))
        self.game_mode = "menu"
        self.input.capture_mouse(False)

    def _push_combat_menu(self):
        def attack():
            if self.combat:
                self.combat.player_attack()
                self._check_combat_end()
        def use_potion():
            if self.combat:
                self.combat.player_use_item("health_potion_s", self.player.inventory)
                self._check_combat_end()
        def flee():
            if self.combat:
                self.combat.player_flee()
                self._check_combat_end()
        self.menus.push(Menu("-- COMBAT --", [
            MenuItem("Attack",     attack),
            MenuItem("Use Potion", use_potion),
            MenuItem("Flee",       flee),
        ]))

    def _check_combat_end(self):
        if self.combat and self.combat.is_over():
            self.menus.pop()
            self.combat    = None
            self.game_mode = "explore"
            self.input.capture_mouse(True)

    def _start_combat(self):
        lvl = self.player.stats.level
        enemy = Stats(
            name="Shadow Slime", level=lvl,
            max_hp=40 + lvl * 10, hp=40 + lvl * 10,
            atk=6 + lvl * 2, defense=2, spd=8,
        )
        self.combat    = self.player.start_combat(enemy)
        self.game_mode = "combat"
        self.input.capture_mouse(False)
        self._push_combat_menu()

    # ── Main loop ─────────────────────────────────────────────────────────────

    def run(self):
        while True:
            dt = self.clock.tick(60) / 1000.0
            self.input.update()
            if self.input.should_quit:
                break

            self._handle_global_input(dt)
            self.scene.update(dt)
            self._render()

        pygame.quit()

    def _handle_global_input(self, dt: float):
        if self.input.key_pressed("f1"):
            self.wireframe = not self.wireframe

        if self.game_mode == "explore":
            self.camera.process_keyboard(self.input.held_keys, dt)
            dx, dy = self.input.mouse_delta
            if dx or dy:
                self.camera.process_mouse(dx, dy)
            if self.input.key_pressed("e"):
                self._start_combat()
            if self.input.key_pressed("escape"):
                self._push_pause_menu()
            # Sync light visualiser
            lp = self.scene.light.pos
            self.light_node.position = [float(lp[0]), float(lp[1]), float(lp[2])]

        elif self.game_mode in ("menu", "combat"):
            self.menus.handle_input(self.input)

    # ── Render ────────────────────────────────────────────────────────────────

    def _render(self):
        glPolygonMode(GL_FRONT_AND_BACK, GL_LINE if self.wireframe else GL_FILL)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

        self.scene.draw(self.phong_shader, self.camera)

        glDisable(GL_DEPTH_TEST)
        self._draw_hud()
        glEnable(GL_DEPTH_TEST)

        pygame.display.flip()

    def _draw_hud(self):
        h  = self.hud
        p  = self.player.stats
        sw = self.screen_w
        sh = self.screen_h

        # HP bar + text
        h.draw_bar(10, 10, 200, 20, p.hp / p.max_hp,
                   bar_color=(0.8, 0.1, 0.1), bg_color=(0.25, 0.1, 0.1))
        h.draw_text(f"HP {p.hp}/{p.max_hp}", 218, 10, 16)

        # XP bar
        h.draw_bar(10, 36, 200, 12, p.xp / max(1, p.xp_next),
                   bar_color=(0.1, 0.4, 0.9), bg_color=(0.1, 0.1, 0.3))
        h.draw_text(f"LV {p.level}  XP {p.xp}/{p.xp_next}", 218, 33, 14)

        # Crosshair
        h.draw_text("+", sw // 2 - 6, sh // 2 - 9, 18)

        # Controls hint
        if self.game_mode == "explore":
            h.draw_text("[WASD] Move  [E] Attack  [ESC] Pause  [F1] Wireframe",
                        10, sh - 26, 14, (160, 160, 160))

        # Menu overlay
        if self.game_mode in ("menu", "combat"):
            pw, ph = 320, 220
            px = sw // 2 - pw // 2
            py = sh // 2 - ph // 2
            h.draw_bar(px - 12, py - 12, pw + 24, ph + 24, 1.0,
                       (0.04, 0.04, 0.10), (0.04, 0.04, 0.10))
            self.menus.draw(h, px, py)

        # Combat log
        if self.combat:
            msgs = self.combat.log.recent(5)
            base_y = sh - 30 - len(msgs) * 22
            for i, msg in enumerate(msgs):
                h.draw_text(msg, 10, base_y + i * 22, 14, (255, 215, 160))

    def on_resize(self, w: int, h: int):
        self.screen_w = w
        self.screen_h = h
        glViewport(0, 0, w, h)
        self.scene.set_aspect(w / h)
        self.hud.resize(w, h)


if __name__ == "__main__":
    game = Game()
    game.run()

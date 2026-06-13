"""
scene.py  –  SceneNode, Scene, PointLight.

SceneNode:
  position, rotation (euler YXZ), scale
  optional Mesh + Texture
  optional animate() callback

Scene:
  root node list
  single PointLight (moving)
  draw_all() uploads Phong uniforms and calls each node
"""

import math
import numpy as np
from .math3d import (
    identity, translate, rotate_x, rotate_y, rotate_z,
    scale as mat_scale, mat3_normal_matrix, vec3,
)
from .shader import ShaderProgram
from .mesh   import Mesh
from .texture import Texture


# ─────────────────────────────────────────────────────────────────────────────

class PointLight:
    def __init__(self,
                 pos=(5.0, 8.0, 5.0),
                 color=(1.0, 1.0, 1.0),
                 intensity=1.2):
        self.pos       = np.array(pos,   dtype=np.float32)
        self.color     = np.array(color, dtype=np.float32)
        self.intensity = intensity

        # Optional orbit animation
        self.orbit      = True
        self.orbit_cx   = 0.0
        self.orbit_cz   = 0.0
        self.orbit_r    = 8.0
        self.orbit_spd  = 0.5   # rad/sec
        self._orbit_t   = 0.0

    def update(self, dt: float):
        if self.orbit:
            self._orbit_t += dt * self.orbit_spd
            self.pos[0] = self.orbit_cx + math.cos(self._orbit_t) * self.orbit_r
            self.pos[2] = self.orbit_cz + math.sin(self._orbit_t) * self.orbit_r

    def apply(self, shader: ShaderProgram):
        shader.set_vec3("uLightPos",       self.pos)
        shader.set_vec3("uLightColor",     self.color)
        shader.set_float("uLightIntensity",self.intensity)


# ─────────────────────────────────────────────────────────────────────────────

class SceneNode:
    def __init__(self,
                 name:     str          = "node",
                 mesh:     Mesh | None  = None,
                 texture:  Texture | None = None,
                 position: tuple = (0, 0, 0),
                 rotation: tuple = (0, 0, 0),   # (rx, ry, rz) degrees
                 scale:    tuple = (1, 1, 1),
                 visible:  bool  = True):

        self.name     = name
        self.mesh     = mesh
        self.texture  = texture
        self.position = list(position)
        self.rotation = list(rotation)   # Euler YXZ
        self.scale    = list(scale)
        self.visible  = visible

        self.children: list["SceneNode"] = []
        self._animator = None            # callable(node, dt)

    # ── Transform ─────────────────────────────────────────────────────────────

    def model_matrix(self, parent: np.ndarray | None = None) -> np.ndarray:
        T = translate(*self.position)
        Ry = rotate_y(self.rotation[1])
        Rx = rotate_x(self.rotation[0])
        Rz = rotate_z(self.rotation[2])
        S  = mat_scale(*self.scale)
        local = T @ Ry @ Rx @ Rz @ S
        if parent is not None:
            return parent @ local
        return local

    # ── Animation ─────────────────────────────────────────────────────────────

    def set_animator(self, fn):
        """fn(node: SceneNode, dt: float)"""
        self._animator = fn

    def update(self, dt: float):
        if self._animator:
            self._animator(self, dt)
        for child in self.children:
            child.update(dt)

    # ── Draw ──────────────────────────────────────────────────────────────────

    def draw(self, shader: ShaderProgram, parent_model: np.ndarray | None = None):
        if not self.visible:
            return

        model = self.model_matrix(parent_model)

        if self.mesh:
            shader.set_mat4("uModel", model)
            shader.set_mat3("uNormalMatrix", mat3_normal_matrix(model))

            # Texture or solid colour
            if self.texture:
                self.texture.bind(0)
                shader.set_bool("uUseTexture", True)
                shader.set_int("uTexture", 0)
            else:
                shader.set_bool("uUseTexture", False)
                shader.set_vec3("uBaseColor", self.mesh.base_color)

            # Phong material
            shader.set_float("uAmbientStrength",  self.mesh.ka)
            shader.set_float("uDiffuseStrength",  self.mesh.kd)
            shader.set_float("uSpecularStrength", self.mesh.ks)
            shader.set_float("uShininess",        self.mesh.shininess)

            self.mesh.draw()

            if self.texture:
                self.texture.unbind()

        for child in self.children:
            child.draw(shader, model)

    # ── Cleanup ───────────────────────────────────────────────────────────────

    def cleanup(self):
        """Libera recursivamente todos os recursos de GPU deste nó e filhos."""
        for child in self.children:
            child.cleanup()
        if self.mesh is not None:
            self.mesh.destroy()
            self.mesh = None
        if self.texture is not None and hasattr(self.texture, 'destroy'):
            self.texture.destroy()
            self.texture = None


# ─────────────────────────────────────────────────────────────────────────────

class Scene:
    def __init__(self):
        self.nodes: list[SceneNode] = []
        self.light = PointLight()
        self.ambient_color = np.array([1.0, 1.0, 1.0], dtype=np.float32)

    def add(self, node: SceneNode) -> SceneNode:
        self.nodes.append(node)
        return node

    def remove(self, node: SceneNode):
        self.nodes = [n for n in self.nodes if n is not node]

    def update(self, dt: float):
        self.light.update(dt)
        for node in self.nodes:
            node.update(dt)

    def draw(self, shader: ShaderProgram, camera):
        """Call once per frame with the Phong shader already in use."""
        shader.use()
        view  = camera.view_matrix()
        proj  = camera.projection_matrix(self._aspect)
        shader.set_mat4("uView",       view)
        shader.set_mat4("uProjection", proj)
        shader.set_vec3("uViewPos",    camera.position)
        self.light.apply(shader)

        for node in self.nodes:
            node.draw(shader)

    def cleanup(self):
        """Destrói todos os recursos de GPU da cena. Chamar antes de descartar."""
        for node in self.nodes:
            node.cleanup()
        self.nodes.clear()

    @property
    def _aspect(self):
        return self.__dict__.get("aspect", 16/9)

    def set_aspect(self, aspect: float):
        self.aspect = aspect

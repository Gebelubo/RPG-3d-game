"""
camera.py  –  Free-look first-person camera.
Uses math3d for matrix construction.
"""

import math
import numpy as np
from .math3d import (
    look_at, perspective, vec3, normalize,
    rotate_y, rotate_x, translate, identity,
)


class Camera:
    def __init__(self,
                 pos=(0.0, 1.7, 5.0),
                 yaw=-90.0,
                 pitch=0.0,
                 fov=60.0,
                 near=0.1,
                 far=500.0):

        self.pos   = np.array(pos,  dtype=np.float32)
        self.yaw   = yaw      # degrees, -90 = looking down -Z
        self.pitch = pitch    # degrees, 0 = horizontal

        self.fov   = fov
        self.near  = near
        self.far   = far

        self.move_speed  = 5.0   # units/sec
        self.mouse_sens  = 0.15  # degrees per pixel

        self._update_vectors()

    # ── Direction vectors ─────────────────────────────────────────────────────

    def _update_vectors(self):
        yaw_r   = math.radians(self.yaw)
        pitch_r = math.radians(self.pitch)
        self.front = normalize(np.array([
            math.cos(pitch_r) * math.cos(yaw_r),
            math.sin(pitch_r),
            math.cos(pitch_r) * math.sin(yaw_r),
        ], dtype=np.float32))
        world_up = np.array([0, 1, 0], dtype=np.float32)
        self.right = normalize(np.cross(self.front, world_up))
        self.up    = normalize(np.cross(self.right, self.front))

    # ── Input ─────────────────────────────────────────────────────────────────

    def process_keyboard(self, keys, dt: float):
        """keys: set of currently held key names (strings)."""
        speed = self.move_speed * dt
        flat_front = normalize(np.array([self.front[0], 0, self.front[2]], dtype=np.float32))
        if "w" in keys:  self.pos += flat_front * speed
        if "s" in keys:  self.pos -= flat_front * speed
        if "a" in keys:  self.pos -= self.right * speed
        if "d" in keys:  self.pos += self.right * speed
        if "space"  in keys: self.pos[1] += speed
        if "lshift" in keys: self.pos[1] -= speed

    def process_mouse(self, dx: float, dy: float):
        self.yaw   += dx * self.mouse_sens
        self.pitch -= dy * self.mouse_sens
        self.pitch  = max(-89.0, min(89.0, self.pitch))
        self._update_vectors()

    # ── Matrices ──────────────────────────────────────────────────────────────

    def view_matrix(self) -> np.ndarray:
        return look_at(self.pos, self.pos + self.front, self.up)

    def projection_matrix(self, aspect: float) -> np.ndarray:
        return perspective(self.fov, aspect, self.near, self.far)

    @property
    def position(self) -> np.ndarray:
        return self.pos

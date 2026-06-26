"""
camera.py  –  Third-person camera (orbit around player) with smooth collision.
"""
import math
import numpy as np
from .math3d import look_at, perspective, normalize


class Camera:
    def __init__(self, fov=60.0, near=0.1, far=500.0):
        self.yaw   = 0.0    
        self.pitch = 20.0  
        self.fov   = fov
        self.near  = near
        self.far   = far
        self.arm_length = 3.2
        self.mouse_sens = 0.18
        self.pos         = np.array([0.0, 3.0, 5.5], dtype=np.float32)
        self.target_pos  = np.array([0.0, 1.0, 0.0], dtype=np.float32)
        self.front       = np.array([0.0, 0.0, -1.0], dtype=np.float32)
        self.right       = np.array([1.0, 0.0,  0.0], dtype=np.float32)
        self.up          = np.array([0.0, 1.0,  0.0], dtype=np.float32)
        self._update_vectors()

    def _update_vectors(self):
        yaw_r   = math.radians(self.yaw)
        pitch_r = math.radians(self.pitch)
        self.front = normalize(np.array([
            math.cos(pitch_r) * math.sin(yaw_r),
            math.sin(pitch_r),
            math.cos(pitch_r) * math.cos(yaw_r),
        ], dtype=np.float32))
        world_up = np.array([0.0, 1.0, 0.0], dtype=np.float32)
        right = np.cross(self.front, world_up)
        if np.linalg.norm(right) < 1e-6:
            right = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        self.right = normalize(right)
        self.up = normalize(np.cross(self.right, self.front))

    def update_third_person(self, player_pos, blockers: list = None, walls: list = None):
        target = np.array(player_pos, dtype=np.float32)
        target[1] += 1.4
        self.target_pos = target

        max_d = self.arm_length
        ground_y = target[1] - 1.0

        if self.front[1] > 1e-6:
            t_ground = (target[1] - ground_y) / self.front[1]
            if 0.1 < t_ground < max_d:
                max_d = max(0.1, t_ground - 0.05)

        if walls:
            PLAYER_RADIUS = 0.45
            for wall in walls:
                wp = np.array(wall["pos"], dtype=np.float32)
                normal = np.array(wall["normal"], dtype=np.float32)
                thickness = wall.get("thickness", 0.2)

                denom = np.dot(self.front, normal)
                if abs(denom) < 1e-6:
                    continue 
                
                d_plane = np.dot(target - wp, normal) / denom
                if d_plane > 0.1:
                    offset = (thickness + PLAYER_RADIUS) / abs(denom)
                    safe_d = d_plane - offset
                    if safe_d < max_d:
                        max_d = max(0.1, safe_d)


        raw_distance = max_d
        if blockers:
            for b in blockers:
                bp = np.array(b["pos"], dtype=np.float32)
                br = float(b.get("radius", 0.6))
                
                to_blocker = bp - target
                projection = np.dot(to_blocker, -self.front)
                
                if projection > 0:  
                    perpendicular_dist = np.linalg.norm(to_blocker - (-self.front * projection))
                    safety_margin = br + 0.45
                    
                    if perpendicular_dist < safety_margin:
                        collision_d = projection - math.sqrt(safety_margin**2 - perpendicular_dist**2)
                        if 0.1 < collision_d < raw_distance:
                            raw_distance = max(0.1, collision_d)

        if not hasattr(self, '_current_distance'):
            self._current_distance = raw_distance

        if raw_distance < self._current_distance:
            lerp_factor = 0.40  
        else:
            lerp_factor = 0.08  

        self._current_distance += (raw_distance - self._current_distance) * lerp_factor

        self.pos = target - self.front * self._current_distance

    def process_mouse(self, dx: float, dy: float):
        self.yaw   -= dx * self.mouse_sens
        self.pitch -= dy * self.mouse_sens
        self.pitch  = max(-89.0, min(89.0, self.pitch))
        self._update_vectors()

    def process_keyboard(self, keys, dt):
        pass  

    def view_matrix(self) -> np.ndarray:
        return look_at(self.pos, self.target_pos, self.up)

    def projection_matrix(self, aspect: float) -> np.ndarray:
        return perspective(self.fov, aspect, self.near, self.far)

    @property
    def position(self) -> np.ndarray:
        return self.pos

    @property
    def flat_forward(self) -> np.ndarray:
        f = np.array([self.front[0], 0.0, self.front[2]], dtype=np.float32)
        n = np.linalg.norm(f)
        return f / n if n > 0.001 else np.array([0, 0, -1], dtype=np.float32)

    @property
    def flat_right(self) -> np.ndarray:
        r = np.array([self.right[0], 0.0, self.right[2]], dtype=np.float32)
        n = np.linalg.norm(r)
        return r / n if n > 0.001 else np.array([1, 0, 0], dtype=np.float32)
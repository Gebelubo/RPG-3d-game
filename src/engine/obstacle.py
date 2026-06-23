from abc import ABC, abstractmethod
import math 
import time
class Hitbox(ABC):

    def __init__(self, x, y, z):
        self.x = x
        self.y = y
        self.z = z

    @abstractmethod
    def resolve_player_collision(self, player):
        pass

class CircleHitbox(Hitbox):
    def __init__(self, x, y, z, radius):
        super().__init__(x, y, z)
        self.radius = radius

    def resolve_player_collision(self, player):

        PLAYER_RADIUS = 0.5

        dx = player.world_pos[0] - self.x
        dz = player.world_pos[2] - self.z

        dist2 = dx * dx + dz * dz

        min_dist = self.radius + PLAYER_RADIUS

        if dist2 < min_dist * min_dist and dist2 > 0.0001:

            dist = math.sqrt(dist2)

            push = (min_dist - dist) / dist

            player.world_pos[0] += dx * push
            player.world_pos[2] += dz * push

class BoxHitbox(Hitbox):

    def __init__(
        self,
        x,
        y,
        z,
        width,
        height,
        depth
    ):
        super().__init__(x, y, z)

        self.width = width
        self.height = height
        self.depth = depth

    def get_surface_height(self, player):

        half_w = self.width * 0.5
        half_d = self.depth * 0.5

        left  = self.x - half_w
        right = self.x + half_w
        front = self.z - half_d
        back  = self.z + half_d

        px, py, pz = player.world_pos

        if not (left <= px <= right):
            return None

        if not (front <= pz <= back):
            return None

        top = self.y + self.height * 0.5

        if py >= top - 0.25:
            return top

        return None
    
    def resolve_player_collision(self, player):

        PLAYER_RADIUS = 0.5

        half_w = self.width * 0.5
        half_h = self.height * 0.5
        half_d = self.depth * 0.5

        left   = self.x - half_w
        right  = self.x + half_w
        bottom = self.y - half_h
        top    = self.y + half_h
        front  = self.z - half_d
        back   = self.z + half_d

        px, py, pz = player.world_pos

        player_feet = player.world_pos[1]

        if player_feet >= top - 0.1:
            return

        cx = max(left, min(px, right))
        cz = max(front, min(pz, back))

        dx = px - cx
        dz = pz - cz

        dist2 = dx * dx + dz * dz

        if dist2 >= PLAYER_RADIUS * PLAYER_RADIUS:
            return

        if dist2 < 1e-8:
            # centro já está dentro do retângulo: empurra pela borda mais próxima
            dist_left  = px - left
            dist_right = right - px
            dist_front = pz - front
            dist_back  = back - pz

            min_dist = min(dist_left, dist_right, dist_front, dist_back)

            if min_dist == dist_left:
                player.world_pos[0] = left - PLAYER_RADIUS
            elif min_dist == dist_right:
                player.world_pos[0] = right + PLAYER_RADIUS
            elif min_dist == dist_front:
                player.world_pos[2] = front - PLAYER_RADIUS
            else:
                player.world_pos[2] = back + PLAYER_RADIUS
            return

        dist = math.sqrt(dist2)

        push = (PLAYER_RADIUS - dist) / dist

        player.world_pos[0] += dx * push
        player.world_pos[2] += dz * push
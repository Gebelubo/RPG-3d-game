import os

from src.engine.mesh          import Mesh, ProceduralMesh, make_cube, make_plane, make_sphere
import json
from src.entities.enemy import Enemy
from src.config.cache import Caches

from src.config.paths import (_HERE, 
                              EMILIA_GLB_PATH, 
                              SUBARU_GLB_DIR, 
                              SUBARU_GLB_FILES, 
                              BEATRICE_GLB_PATH, 
                              MARLUXIA_GLB_PATH,
                              MODEL_TOWER,
                              HEARTLESS_GLB_PATH,
                              AERIALKNOCKER_GLB_PATH,
                              SAVE_PATH,
                              SHADER_DIR)
from src.config.constants import (STAIR_STEP_D, 
                                  STAIR_STEP_H, 
                                  STAIR_Z_START, 
                                  STAIR_Z_SPACING, 
                                  STAIR_WIDTH, 
                                  STAIR_COUNT, 
                                  BEATRICE_TARGET_HEIGHT, 
                                  BEATRICE_Y_OFFSET, 
                                  SUBARU_Y_OFFSET, 
                                  EMILIA_CLIP_NAMES, 
                                  EMILIA_MANUAL_SCALE, 
                                  EMILIA_TARGET_HEIGHT, 
                                  EMILIA_Y_OFFSET,
                                  MARLUXIA_CLIP_NAMES,
                                  MARLUXIA_TARGET_HEIGHT,
                                  HEARTLESS_CLIP_NAMES,
                                  HEARTLESS_TARGET_HEIGHT,
                                  HEARTLESS_Y_OFFSET,
                                  AERIALKNOCKER_CLIP_NAMES,
                                  AERIALKNOCKER_TARGET_HEIGHT,
                                  BEATRICE_CLIP_NAMES,
                                  AERIALKNOCKER_Y_OFFSET)
from src.config.cache import ( _EMILIA_SKINNED_CACHE, 
                              _BEATRICE_SKINNED_CACHE, 
                              _MARLUXIA_SKINNED_CACHE, 
                              _HEARTLESS_SKINNED_CACHE, 
                              _AERIALKNOCKER_SKINNED_CACHE)
from src.engine.texture       import Texture, ProceduralTexture
from src.engine.scene         import Scene, SceneNode, PointLight
from src.engine.obstacle    import Hitbox, CircleHitbox, BoxHitbox
from src.engine.obj_loader    import OBJLoader
from src.engine.gltf_loader   import GLTFLoader
from src.engine.skinned_mesh  import SkinnedMesh
from src.engine.animation     import AnimationController
import numpy as np

from src.db.character import CharacterDB
from src.entities.character import Character


class Helper:
    def __init__(self):
        self.cache = Caches()
        self.chardb = CharacterDB()

    def load_skinned_player(self, position, rotation):
        player = self.chardb.get_char("subaru")
        return player.load_skinned(position=position, rotation=rotation)
    
    def load_skinned_beatrice(self, position, rotation):
        char = self.chardb.get_char("beatrice")
        return char.load_skinned(position=position, rotation=rotation)
    
    def load_skinned_emilia(self, position, rotation):
        char = self.chardb.get_char("emilia")
        return char.load_skinned(position=position, rotation=rotation)
    
    def load_skinned_marluxia(self, position, rotation):
        char = self.chardb.get_char("marluxia")
        return char.load_skinned(position=position, rotation=rotation)
    
    def load_skinned_heartless(self, position, rotation):
        char = self.chardb.get_char("heartless")
        return char.load_skinned(position=position, rotation=rotation)
    def load_skinned_aerialknocker(self, position, rotation):
        char = self.chardb.get_char("aerialknocker")
        return char.load_skinned(position=position, rotation=rotation)

    def make_box_mesh(self, name, w, h, d, color, ka=0.2, kd=0.8, ks=0.2, shin=16):
        verts, idxs = make_cube(1.0)
        verts = verts.copy()
        verts[:, 0] *= w / 2.0
        verts[:, 1] *= h / 2.0
        verts[:, 2] *= d / 2.0
        return ProceduralMesh(name, verts, idxs, base_color=color, ka=ka, kd=kd, ks=ks, shininess=shin)


    def _stair_step_bounds(self, i):
        y_bot = i * STAIR_STEP_H
        y_top = (i + 1) * STAIR_STEP_H
        zc    = STAIR_Z_START - i * STAIR_Z_SPACING
        hw    = STAIR_WIDTH / 2.0
        hd    = STAIR_STEP_D / 2.0
        return {"x0": -hw, "x1": hw, "z0": zc - hd, "z1": zc + hd, "y0": y_bot, "y1": y_top}


    def _build_stairs(self, scene, floor_state):
        """Escada sólida estilo castelo."""

        for i in range(STAIR_COUNT):

            # altura acumulada do degrau
            height = (i + 1) * STAIR_STEP_H

            z_center = STAIR_Z_START - i * STAIR_Z_SPACING

            sm = self.make_box_mesh(
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


    def _collect_meshes(self, node):
        meshes = []
        if getattr(node, "mesh", None) is not None:
            meshes.append(node.mesh)
        for child in getattr(node, "children", []):
            meshes.extend(self._collect_meshes(child))
        return meshes


    def _restore_colors(self, re_):
        for m, c in zip(re_["meshes"], re_["orig_colors"]):
            m.base_color = c


    def _flash_color(self, re_, color):
        for m in re_["meshes"]:
            m.base_color = color


    def _add_tower_deco(self, scene, floor_state, name, position, scale=(1,1,1), rotation=(0,0,0), collision_radius=1.0):
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


    def _load_obj_model(self, path, position=(0,0,0), rotation=(0,0,0), scale=(1,1,1)):
        model_dir = os.path.dirname(os.path.abspath(path))
        if path not in self.cache.obj_cache:
            try:
                self.cache.obj_cache[path] = OBJLoader().load(path) or []
            except Exception as exc:
                print(f"OBJ load failed for {path}: {exc}")
                self.cache.obj_cache[path] = []
        mesh_data_list = self.cache.obj_cache[path]
        if not mesh_data_list:
            return None

        parent = SceneNode(os.path.splitext(os.path.basename(path))[0],
                        position=list(position), rotation=list(rotation), scale=list(scale))
        for md in mesh_data_list:
            try:
                mesh    = Mesh(md)
            except Exception as exc:
                print(f"Failed to build mesh from {path}: {exc}")
                continue
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

        if not parent.children:
            return None

        return parent

    def _spawn_heartless(self, scene, pos, scale=(0.012,0.012,0.012), level=2, stationary=False, flying=False):
        skinned_mesh = None
        anim_controller = None

        if flying:
            # Tenta carregar AerialKnocker como skinned mesh animado
            ak_pos = (pos[0], pos[1] + AERIALKNOCKER_Y_OFFSET, pos[2])
            sk_node, skinned_mesh, anim_controller = self.load_skinned_aerialknocker(
                position=ak_pos, rotation=(0, 180, 0)
            )
            if sk_node is not None:
                # Skinned: posicionado diretamente pelo loader; não entra em scene.add()
                # O render é feito por _render_enemy_skinned_meshes(), igual ao player.
                node = sk_node
            else:
                # Fallback: .obj estático
                model_path  = os.path.join(_HERE, "assets", "models", "AerialKnocker", "AerialKnocker.obj")
                model_scale = (scale[0] * 0.8, scale[1] * 0.8, scale[2] * 0.8)
                node = self._load_obj_model(model_path, position=ak_pos, rotation=(0, 180, 0), scale=model_scale)
                if node is None:
                    ev, ei = make_sphere(0.45, 10, 10)
                    em = ProceduralMesh("heartless", ev, ei, base_color=(0.3, 0.3, 0.9),
                                        ka=0.3, kd=0.8, ks=0.3, shininess=16)
                    node = SceneNode("heartless", mesh=em, position=list(ak_pos))
                scene.add(node)
        else:
            # Tenta carregar Heartless terrestre como skinned mesh animado
            adj_pos = (pos[0], pos[1] + HEARTLESS_Y_OFFSET, pos[2])
            sk_node, skinned_mesh, anim_controller = self.load_skinned_heartless(
                position=adj_pos, rotation=(0, 180, 0)
            )
            if sk_node is not None:
                node = sk_node
            else:
                # Fallback: .obj estático
                model_path  = os.path.join(_HERE, "assets", "models", "Heartless", "Heartless.obj")
                node = self._load_obj_model(model_path, position=adj_pos, rotation=(180, 0, 0), scale=scale)
                if node is None:
                    ev, ei = make_sphere(0.45, 10, 10)
                    em = ProceduralMesh("heartless", ev, ei, base_color=(0.7, 0.1, 0.1),
                                        ka=0.3, kd=0.8, ks=0.3, shininess=16)
                    node = SceneNode("heartless", mesh=em, position=list(adj_pos))
                scene.add(node)

        e = Enemy("Heartless", level=level, world_pos=list(pos), stationary=stationary)
        e.spawn_pos     = list(pos)
        e._skinned_mesh = skinned_mesh      # None se usou fallback .obj
        e._anim         = anim_controller   # None se usou fallback .obj
        e._anim_state   = None
        e._y_offset     = AERIALKNOCKER_Y_OFFSET if flying else HEARTLESS_Y_OFFSET
        return e, node


    # ── Save / Load ───────────────────────────────────────────────────────────────

    def save_game(self, floor, player):
        data = {
            "floor": floor, "hp": player.stats.hp, "mp": player.stats.mp,
            "max_hp": player.stats.max_hp, "max_mp": player.stats.max_mp,
            "level": player.stats.level, "xp": player.stats.xp, "xp_next": player.stats.xp_next,
            "atk": player.stats.atk, "defense": player.stats.defense,
            "inventory": player.inventory.items, "gold": player.inventory.gold,
        }
        with open(SAVE_PATH, "w") as f:
            json.dump(data, f)


    def load_game(self, player):
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

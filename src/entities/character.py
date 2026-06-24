import os
import numpy as np

from src.engine.animation     import AnimationController
from src.engine.texture       import Texture, ProceduralTexture
from src.engine.gltf_loader   import GLTFLoader
from src.engine.skinned_mesh  import SkinnedMesh
from src.engine.scene         import Scene, SceneNode, PointLight

class Character:

    def __init__(
        self,
        name: str,
        y_offset: float = 0.0,
        glb_path: str = None,
        clip_names: dict = None,
        target_height: float = None,
        manual_scale: float = None,
        fallback_texture: str = None,
        auto_play: str = "idle",
    ):

        self.name = name
        self.y_offset = y_offset
        self.glb_path = glb_path
        self.clip_names = clip_names or {}
        self.target_height = target_height
        self.manual_scale = manual_scale
        self.fallback_texture = fallback_texture
        self.auto_play = auto_play

        self.cache = {}
    # --------------------------------------------------

    def _load_smd(self):

        cache_key = self.glb_path

        if cache_key not in self.cache:

            try:
                if not os.path.isfile(self.glb_path):
                    self.cache[cache_key] = None

                else:
                    loader = GLTFLoader()

                    smd = loader.load_merged(self.glb_path)

                    if smd is None:
                        raise ValueError(
                            "nenhuma primitive com skin encontrada"
                        )

                    smd._primitives = loader.last_primitives

                    if self.clip_names and smd.clips:

                        first_clip = next(iter(smd.clips))

                        for alias, real_name in list(self.clip_names.items()):

                            if real_name not in smd.clips:
                                print(
                                    f"[{self.name}] "
                                    f"clip '{real_name}' não encontrado. "
                                    f"Usando '{first_clip}'."
                                )

                                self.clip_names[alias] = first_clip

                    if self.fallback_texture and not smd.texture_path:
                        if os.path.isfile(self.fallback_texture):
                            smd.texture_path = self.fallback_texture

                    self.cache[cache_key] = smd

            except Exception as exc:
                print(f"GLB load failed for {self.name}: {exc}")
                self.cache[cache_key] = None

        return self.cache[cache_key]

    # --------------------------------------------------

    def _create_animation_controller(self, smd):

        controller = AnimationController(
            smd.bones,
            smd.clips,
            clip_names=self.clip_names
        )

        if self.auto_play:
            try:
                controller.play(self.auto_play)
            except:
                pass

        return controller

    # --------------------------------------------------

    def _calculate_auto_scale(
        self,
        smd,
        anim_controller
    ):

        auto_scale = getattr(smd, "_auto_scale", None)

        if auto_scale is not None:
            return auto_scale

        bone_matrices = anim_controller.get_bone_matrices()

        bm = np.stack(bone_matrices, axis=0)

        pos_h = np.concatenate(
            [
                smd.vertices[:, :3],
                np.ones(
                    (len(smd.vertices), 1),
                    dtype=np.float32
                )
            ],
            axis=1
        )

        skinned_y = np.zeros(
            len(smd.vertices),
            dtype=np.float32
        )

        for k in range(smd.joints.shape[1]):

            joint_idx = smd.joints[:, k].astype(np.int64)

            w = smd.weights[:, k]

            transformed = np.einsum(
                "nij,nj->ni",
                bm[joint_idx],
                pos_h
            )

            skinned_y += w * transformed[:, 1]

        raw_height = (
            float(skinned_y.max() - skinned_y.min())
            if len(skinned_y)
            else 0.0
        )

        if raw_height > 1e-4:
            auto_scale = self.target_height / raw_height
        else:
            auto_scale = 1.0

        smd._auto_scale = auto_scale

        return auto_scale

    # --------------------------------------------------

    def _get_scale(
        self,
        smd,
        anim_controller
    ):

        if self.manual_scale is not None:
            return self.manual_scale

        if self.target_height is not None:
            return self._calculate_auto_scale(
                smd,
                anim_controller
            )

        return 1.0

    # --------------------------------------------------

    def _load_texture(self, smd):

        if not smd.texture_path:
            return None

        try:
            return Texture(smd.texture_path)

        except Exception as exc:
            print(
                f"Failed to load texture "
                f"{smd.texture_path}: {exc}"
            )
            return None

    # --------------------------------------------------

    def load_skinned(
        self,
        position=(0, 0, 0),
        rotation=(0, 180, 0)
    ):

        smd = self._load_smd()

        if smd is None:
            return None, None, None

        skinned_mesh = SkinnedMesh(smd)

        skinned_mesh._primitives = getattr(
            smd,
            "_primitives",
            None
        )

        anim_controller = self._create_animation_controller(
            smd
        )

        scale = self._get_scale(
            smd,
            anim_controller
        )

        final_position = list(position)
        final_position[1] += self.y_offset

        node = SceneNode(
            f"{self.name}_skinned",
            position=final_position,
            rotation=list(rotation),
            scale=[scale, scale, scale]
        )

        node.mesh = skinned_mesh

        node.texture = self._load_texture(smd)

        return node, skinned_mesh, anim_controller
    
class MultiClipCharacter(Character):

    def __init__(
        self,
        name,
        y_offset,
        files,
        target_height,
        primary_clip,
        fallback_texture=None
    ):

        super().__init__(
            name=name,
            y_offset=y_offset,
            glb_path=None,
            target_height=target_height,
            fallback_texture=fallback_texture
        )

        self.files = files
        self.primary_clip = primary_clip

    # --------------------------------------------------

    def _load_smd(self):

        cache_key = tuple(
            sorted(self.files.items())
        )

        if cache_key not in self.cache:

            try:

                loader = GLTFLoader()

                if self.primary_clip:
                    primary_path = self.files[self.primary_clip]
                else:
                    primary_path = next(iter(self.files.values()))

                if not os.path.isfile(primary_path):
                    self.cache[cache_key] = None

                else:

                    smd = loader.load_merged(
                        primary_path
                    )

                    if smd is None:
                        raise ValueError(
                            "nenhuma primitive com skin encontrada"
                        )

                    smd._primitives = loader.last_primitives

                    renamed_clips = {}

                    for clip_name, glb_path in self.files.items():

                        if not os.path.isfile(glb_path):
                            continue

                        try:

                            if glb_path == primary_path:
                                part = smd
                            else:
                                part = loader.load_merged(
                                    glb_path
                                )

                            if part and part.clips:

                                original_clip = next(
                                    iter(
                                        part.clips.values()
                                    )
                                )

                                renamed_clips[
                                    clip_name
                                ] = original_clip

                        except Exception as exc:
                            print(
                                f"Falha ao carregar "
                                f"{glb_path}: {exc}"
                            )

                    smd.clips = renamed_clips

                    if (
                        self.fallback_texture
                        and not smd.texture_path
                    ):
                        if os.path.isfile(
                            self.fallback_texture
                        ):
                            smd.texture_path = (
                                self.fallback_texture
                            )

                    self.cache[cache_key] = smd

            except Exception as exc:

                print(
                    f"GLB load failed "
                    f"for {self.name}: {exc}"
                )

                self.cache[cache_key] = None

        return self.cache[cache_key]
import os
import numpy as np
from dataclasses import dataclass, field
from typing import Optional

import pygltflib
from pygltflib import GLTF2


@dataclass
class Bone:
    name:               str
    parent_index:       int
    inverse_bind_matrix: np.ndarray
    local_bind_translation: np.ndarray
    local_bind_rotation:    np.ndarray
    local_bind_scale:       np.ndarray


@dataclass
class BoneKeyframes:
    times:        np.ndarray
    translations: np.ndarray
    rotations:    np.ndarray
    scales:       np.ndarray


@dataclass
class AnimationClip:
    name:      str
    duration:  float
    bone_tracks: list


@dataclass
class SkinnedMeshData:
    name:            str
    vertices:        np.ndarray
    indices:         np.ndarray
    joints:          np.ndarray
    weights:         np.ndarray
    bones:           list
    clips:           dict
    texture_path:    Optional[str] = None
    base_color:      tuple = (0.8, 0.8, 0.8)
    root_transform:  Optional[np.ndarray] = None


class GLTFLoader:
    def __init__(self):
        self.last_primitives: list = []

    def _compute_root_transform(self, gltf, joint_node_indices, bones=None) -> Optional[np.ndarray]:
        joint_set = set(joint_node_indices)
        parent_of = {}
        for idx, node in enumerate(gltf.nodes):
            if node.children:
                for child_idx in node.children:
                    parent_of[child_idx] = idx
        skeleton_root = None
        for node_idx in joint_node_indices:
            p = parent_of.get(node_idx)
            if p is None or p not in joint_set:
                skeleton_root = node_idx
                break
        if skeleton_root is None:
            return None
        chain = []
        cur = parent_of.get(skeleton_root)
        while cur is not None:
            chain.append(cur)
            cur = parent_of.get(cur)
        m = np.eye(4, dtype=np.float32)
        if chain:
            for node_idx in reversed(chain):
                node = gltf.nodes[node_idx]
                t, r, s = self._node_trs(node)
                node_m = np.eye(4, dtype=np.float32)
                rot3 = self._quat_to_mat3_local(r)
                node_m[:3, :3] = rot3 * s[np.newaxis, :]
                node_m[:3, 3] = t
                m = m @ node_m
        if not np.allclose(m, np.eye(4, dtype=np.float32)):
            return m
        if bones:
            try:
                root_bone_idx = joint_node_indices.index(skeleton_root)
            except ValueError:
                root_bone_idx = None
            if root_bone_idx is not None:
                root_bone = bones[root_bone_idx]
                local_m = np.eye(4, dtype=np.float32)
                rot3 = self._quat_to_mat3_local(root_bone.local_bind_rotation)
                local_m[:3, :3] = rot3 * root_bone.local_bind_scale[np.newaxis, :]
                local_m[:3, 3] = root_bone.local_bind_translation
                skin_m = local_m @ root_bone.inverse_bind_matrix
                if np.linalg.det(skin_m[:3, :3]) != 0 and not np.allclose(skin_m, np.eye(4, dtype=np.float32), atol=1e-3):
                    derived = np.linalg.inv(skin_m).astype(np.float32)
                    if not np.allclose(derived, np.eye(4, dtype=np.float32)):
                        # Esta normalização (manter só a rotação de 'derived' e
                        # zerar a escala) é exclusiva do asset da Beatrice — é o
                        # que cancela corretamente o inverso do /100 aplicado em
                        # _build_bones para ESSE asset especificamente. Para os
                        # demais assets (ex.: Subaru), 'derived' já vem correto
                        # do jeito que o código original (pré-correção Beatrice)
                        # calculava, então não tocamos nele.
                        if getattr(self, '_is_beatrice', False):
                            rot_only = derived[:3, :3].copy()
                            col_norms = np.linalg.norm(rot_only, axis=0)
                            col_norms = np.where(col_norms < 1e-8, 1.0, col_norms)
                            rot_only = rot_only / col_norms[np.newaxis, :]
                            derived = np.eye(4, dtype=np.float32)
                            derived[:3, :3] = rot_only
                        zup_to_yup = np.array([
                            [1, 0, 0, 0],
                            [0, 0, 1, 0],
                            [0, -1, 0, 0],
                            [0, 0, 0, 1],
                        ], dtype=np.float32)
                        return zup_to_yup @ derived
        return None

    @staticmethod
    def _quat_to_mat3_local(q: np.ndarray) -> np.ndarray:
        x, y, z, w = q
        xx, yy, zz = x * x, y * y, z * z
        xy, xz, yz = x * y, x * z, y * z
        wx, wy, wz = w * x, w * y, w * z
        return np.array([
            [1 - 2 * (yy + zz), 2 * (xy - wz),     2 * (xz + wy)],
            [2 * (xy + wz),     1 - 2 * (xx + zz), 2 * (yz - wx)],
            [2 * (xz - wy),     2 * (yz + wx),     1 - 2 * (xx + yy)],
        ], dtype=np.float32)

    def load_merged(self, path: str) -> Optional['SkinnedMeshData']:
        gltf = GLTF2().load(path)
        base_dir = os.path.dirname(os.path.abspath(path))
        if not gltf.skins:
            raise ValueError(f"{path}: nenhum skin encontrado (.glb sem esqueleto)")
        skin = gltf.skins[0]
        joint_node_indices = list(skin.joints)
        node_to_bone = {n: i for i, n in enumerate(joint_node_indices)}

        # Identifica se este asset é o da Beatrice (pelo nome do arquivo) para
        # decidir qual fluxo de correção de unidade usar:
        #  - Beatrice: detecção automática cm->m via heurística na escala da
        #    inverse bind matrix (necessária porque o export da Beatrice tem
        #    comportamento diferente do Subaru).
        #  - Qualquer outro asset (ex.: Subaru): mantém o comportamento
        #    histórico/original — sempre assume centímetros e aplica /100,
        #    sem essa heurística, porque é isso que funciona pra ele.
        self._is_beatrice = "beatrice" in os.path.basename(path).lower()

        if self._is_beatrice:
            # Detecta uma única vez se este asset foi exportado em centímetros
            # (Mixamo/FBX, comum) ou já em metros (ex.: export direto do
            # Blender). Usado tanto pelo bind pose (_build_bones) quanto pelas
            # curvas de animação (_merge_tracks) — as duas precisam concordar,
            # senão o bind pose fica em metros mas a animação "puxa" os bones
            # de volta para a escala cm a cada frame (ou vice-versa). Ver
            # _build_bones para detalhes da heurística.
            ibm_accessor = skin.inverseBindMatrices
            ibm_probe = self._read_accessor(gltf, ibm_accessor).reshape(-1, 4, 4)
            first_ibm_scale = float(np.linalg.norm(ibm_probe[0].T[:3, 0])) if len(ibm_probe) else 1.0
            self._needs_cm_to_m = first_ibm_scale > 10.0  # ~100 para cm; ~1 para m já correto
        else:
            self._needs_cm_to_m = True  # comportamento original: sempre cm->m

        bones = self._build_bones(gltf, skin, joint_node_indices, node_to_bone)
        clips = self._build_clips(gltf, node_to_bone, bones)
        root_transform = self._compute_root_transform(gltf, joint_node_indices, bones=bones)
        primitives = []
        for node in gltf.nodes:
            if node.mesh is None:
                continue
            mesh = gltf.meshes[node.mesh]
            for prim in mesh.primitives:
                smd = self._build_primitive(gltf, prim, base_dir, bones, clips, mesh.name or "skinned")
                if smd is None:
                    continue
                smd.root_transform = root_transform
                primitives.append(smd)
        if not primitives:
            self.last_primitives = []
            return None
        self.last_primitives = primitives
        return primitives[0]

    def _build_bones(self, gltf, skin, joint_node_indices, node_to_bone) -> list:
        ibm_accessor = skin.inverseBindMatrices
        ibm_data = self._read_accessor(gltf, ibm_accessor)
        ibm_data = ibm_data.reshape(-1, 4, 4)
        parent_of_node = {}
        for idx, n in enumerate(gltf.nodes):
            if n.children:
                for child_idx in n.children:
                    parent_of_node[child_idx] = idx
        joint_set = set(joint_node_indices)

        def find_joint_parent(node_idx: int) -> int:
            cur = parent_of_node.get(node_idx)
            while cur is not None:
                if cur in joint_set:
                    return node_to_bone[cur]
                cur = parent_of_node.get(cur)
            return -1

        def local_bind_matrix(node_idx: int) -> np.ndarray:
            chain = [node_idx]
            cur = parent_of_node.get(node_idx)
            while cur is not None and cur not in joint_set:
                chain.append(cur)
                cur = parent_of_node.get(cur)
            m = np.eye(4, dtype=np.float32)
            for idx in reversed(chain):
                m = m @ self._node_local_mat4(gltf.nodes[idx])
            return m

        bones = []
        # needs_cm_to_m já foi calculado uma vez em load_merged() (mesma
        # decisão usada pelas curvas de animação em _merge_tracks, para que
        # bind pose e animação fiquem na mesma unidade). Fallback para True
        # (comportamento histórico) se chamado fora do fluxo de load_merged.
        needs_cm_to_m = getattr(self, '_needs_cm_to_m', True)

        for bone_idx, node_idx in enumerate(joint_node_indices):
            node = gltf.nodes[node_idx]
            parent_index = find_joint_parent(node_idx)
            bind_m = local_bind_matrix(node_idx)
            t, r, s = self._mat4_to_trs(bind_m)
            ibm = ibm_data[bone_idx].T.astype(np.float32)

            # CORREÇÃO: alguns exportadores (Mixamo/FBX) gravam o bind pose
            # em centímetros, então tanto a translação do bind local quanto a
            # inverse bind matrix (rotação+escala+translação, linhas 0-2)
            # carregam um fator de escala 100 embutido. Se só um dos dois
            # for normalizado, esse fator não se cancela na cadeia
            # global_transform @ inverse_bind_matrix, e ossos no fim de
            # cadeias longas (ex.: Hips->Spine->Spine1->Spine2->Neck->Head)
            # ficam com escala/posição ~100x erradas mesmo com pesos de
            # skinning corretos. Aplicada apenas quando needs_cm_to_m
            # detecta essa unidade (ver load_merged) — assets já em metros
            # (ex.: exports diretos do Blender) NÃO devem passar por isso,
            # ou o modelo inteiro fica esmagado para ~1% do tamanho correto.
            if needs_cm_to_m:
                t = t / 100.0
                ibm[:3, :] = ibm[:3, :] / 100.0

            bones.append(Bone(
                name=node.name or f"bone_{bone_idx}",
                parent_index=parent_index,
                inverse_bind_matrix=ibm,
                local_bind_translation=t,
                local_bind_rotation=r,
                local_bind_scale=s,
            ))
        return bones

    def _node_trs(self, node):
        if node.matrix:
            m = np.array(node.matrix, dtype=np.float32).reshape(4, 4).T
            t = m[:3, 3].copy()
            sx = np.linalg.norm(m[:3, 0]); sy = np.linalg.norm(m[:3, 1]); sz = np.linalg.norm(m[:3, 2])
            s = np.array([sx, sy, sz], dtype=np.float32)
            rot_mat = m[:3, :3] / np.where(s == 0, 1, s)
            r = self._mat3_to_quat(rot_mat)
            return t, r, s
        t = np.array(node.translation if node.translation else [0, 0, 0], dtype=np.float32)
        r = np.array(node.rotation if node.rotation else [0, 0, 0, 1], dtype=np.float32)
        s = np.array(node.scale if node.scale else [1, 1, 1], dtype=np.float32)
        return t, r, s

    def _node_local_mat4(self, node) -> np.ndarray:
        t, r, s = self._node_trs(node)
        m = np.eye(4, dtype=np.float32)
        rot3 = self._quat_to_mat3_local(r)
        m[:3, :3] = rot3 * s[np.newaxis, :]
        m[:3, 3] = t
        return m

    def _mat4_to_trs(self, m: np.ndarray):
        t = m[:3, 3].copy()
        sx = np.linalg.norm(m[:3, 0]); sy = np.linalg.norm(m[:3, 1]); sz = np.linalg.norm(m[:3, 2])
        s = np.array([sx, sy, sz], dtype=np.float32)
        rot_mat = m[:3, :3] / np.where(s == 0, 1, s)
        r = self._mat3_to_quat(rot_mat)
        return t, r, s

    def _mat3_to_quat(self, m: np.ndarray) -> np.ndarray:
        tr = m[0, 0] + m[1, 1] + m[2, 2]
        if tr > 0:
            S = np.sqrt(tr + 1.0) * 2
            qw = 0.25 * S
            qx = (m[2, 1] - m[1, 2]) / S
            qy = (m[0, 2] - m[2, 0]) / S
            qz = (m[1, 0] - m[0, 1]) / S
        elif m[0, 0] > m[1, 1] and m[0, 0] > m[2, 2]:
            S = np.sqrt(1.0 + m[0, 0] - m[1, 1] - m[2, 2]) * 2
            qw = (m[2, 1] - m[1, 2]) / S
            qx = 0.25 * S
            qy = (m[0, 1] + m[1, 0]) / S
            qz = (m[0, 2] + m[2, 0]) / S
        elif m[1, 1] > m[2, 2]:
            S = np.sqrt(1.0 + m[1, 1] - m[0, 0] - m[2, 2]) * 2
            qw = (m[0, 2] - m[2, 0]) / S
            qx = (m[0, 1] + m[1, 0]) / S
            qy = 0.25 * S
            qz = (m[1, 2] + m[2, 1]) / S
        else:
            S = np.sqrt(1.0 + m[2, 2] - m[0, 0] - m[1, 1]) * 2
            qw = (m[1, 0] - m[0, 1]) / S
            qx = (m[0, 2] + m[2, 0]) / S
            qy = (m[1, 2] + m[2, 1]) / S
            qz = 0.25 * S
        return np.array([qx, qy, qz, qw], dtype=np.float32)

    def _build_clips(self, gltf, node_to_bone: dict, bones: list) -> dict:
        n_bones = len(bones)
        clips = {}
        for anim in (gltf.animations or []):
            bone_tracks = [None] * n_bones
            duration = 0.0
            per_bone = {}
            for ch in anim.channels:
                target_node = ch.target.node
                if target_node not in node_to_bone:
                    continue
                bone_idx = node_to_bone[target_node]
                sampler = anim.samplers[ch.sampler]
                times = self._read_accessor(gltf, sampler.input).reshape(-1)
                values = self._read_accessor(gltf, sampler.output)
                duration = max(duration, float(times[-1]) if len(times) else 0.0)
                per_bone.setdefault(bone_idx, {})[ch.target.path] = (times, values)
            for bone_idx, paths in per_bone.items():
                bone_tracks[bone_idx] = self._merge_tracks(paths, bones[bone_idx])
            clips[anim.name or f"clip_{len(clips)}"] = AnimationClip(
                name=anim.name or f"clip_{len(clips)}",
                duration=duration,
                bone_tracks=bone_tracks,
            )
        return clips

    def _merge_tracks(self, paths: dict, bone: 'Bone') -> BoneKeyframes:
        all_times = sorted(set(
            t for key in ("translation", "rotation", "scale") if key in paths
            for t in paths[key][0].tolist()
        ))
        all_times = np.array(all_times, dtype=np.float32) if all_times else np.array([0.0], dtype=np.float32)
        # IMPORTANTE: quando um canal (translation/rotation/scale) não existe
        # para este bone neste clipe — comum em exports que só gravam
        # rotation para bones de uma cadeia (ex.: spine_01..head) — o valor
        # default usado precisa ser o BIND LOCAL do bone, não um valor fixo
        # neutro (0 translação / escala 1). _sample_locals usa a translação
        # amostrada como transform local ABSOLUTO (substitui o bind, não soma
        # a ele), então um default [0,0,0] colapsaria esses bones na origem
        # do seu espaço de pai — colando spine_01..head todos na posição do
        # bone anterior na cadeia e "achatando" o personagem.
        # IMPORTANTE (Beatrice apenas): quando um canal (translation/rotation/
        # scale) não existe para este bone neste clipe — comum em exports que
        # só gravam rotation para bones de uma cadeia (ex.: spine_01..head) —
        # o valor default usado precisa ser o BIND LOCAL do bone, não um valor
        # fixo neutro (0 translação / escala 1). _sample_locals usa a
        # translação amostrada como transform local ABSOLUTO (substitui o
        # bind, não soma a ele), então um default [0,0,0] colapsaria esses
        # bones na origem do seu espaço de pai. Isso é necessário pro export
        # da Beatrice; o Subaru mantém os defaults neutros originais, que é o
        # que funciona pra ele.
        if getattr(self, '_is_beatrice', False):
            default_t = bone.local_bind_translation
            default_r = bone.local_bind_rotation
            default_s = bone.local_bind_scale
        else:
            default_t = np.array([0, 0, 0], dtype=np.float32)
            default_r = np.array([0, 0, 0, 1], dtype=np.float32)
            default_s = np.array([1, 1, 1], dtype=np.float32)
        translations = self._resample(paths.get("translation"), all_times, default=default_t)
        rotations    = self._resample(paths.get("rotation"),    all_times, default=default_r, is_quat=True)
        # CORREÇÃO TAMBÉM AQUI: quando o asset usa centímetros (ver
        # load_merged / _build_bones), as curvas de translation das
        # animações também vêm em centímetros e precisam do mesmo /100 —
        # senão a animação "puxaria" os bones de volta pra escala cm a cada
        # frame. Usa a mesma decisão needs_cm_to_m do bind pose (consistência
        # obrigatória entre os dois); assets já em metros não passam por isso.
        if "translation" in paths and getattr(self, '_needs_cm_to_m', True):
            translations = translations / 100.0
        scales       = self._resample(paths.get("scale"),       all_times, default=default_s)
        return BoneKeyframes(times=all_times, translations=translations,
                              rotations=rotations, scales=scales)

    def _resample(self, track, target_times, default, is_quat=False):
        n = len(target_times)
        if track is None:
            return np.tile(default, (n, 1)).astype(np.float32)
        times, values = track
        out = np.zeros((n, values.shape[1]), dtype=np.float32)
        for i, t in enumerate(target_times):
            idx = np.searchsorted(times, t)
            if idx <= 0:
                out[i] = values[0]
            elif idx >= len(times):
                out[i] = values[-1]
            else:
                t0, t1 = times[idx - 1], times[idx]
                a = values[idx - 1]; b = values[idx]
                alpha = 0.0 if t1 == t0 else (t - t0) / (t1 - t0)
                if is_quat:
                    out[i] = self._slerp(a, b, alpha)
                else:
                    out[i] = a + (b - a) * alpha
        return out

    def _slerp(self, q0, q1, t):
        dot = np.dot(q0, q1)
        if dot < 0.0:
            q1 = -q1; dot = -dot
        if dot > 0.9995:
            result = q0 + t * (q1 - q0)
            return result / np.linalg.norm(result)
        theta_0 = np.arccos(np.clip(dot, -1.0, 1.0))
        theta = theta_0 * t
        q2 = q1 - q0 * dot
        q2 = q2 / np.linalg.norm(q2)
        return q0 * np.cos(theta) + q2 * np.sin(theta)

    def _build_primitive(self, gltf, prim, base_dir, bones, clips, name) -> Optional[SkinnedMeshData]:
        attrs = prim.attributes
        if attrs.POSITION is None or attrs.JOINTS_0 is None or attrs.WEIGHTS_0 is None:
            return None
        positions = self._read_accessor(gltf, attrs.POSITION)
        normals   = self._read_accessor(gltf, attrs.NORMAL) if attrs.NORMAL is not None else np.zeros_like(positions)
        uvs       = self._read_accessor(gltf, attrs.TEXCOORD_0) if attrs.TEXCOORD_0 is not None else np.zeros((len(positions), 2), dtype=np.float32)
        uvs       = uvs.copy()
        uvs[:, 0] = np.mod(uvs[:, 0], 1.0)
        uvs[:, 1] = 1.0 - np.mod(uvs[:, 1], 1.0)
        joints    = self._read_accessor(gltf, attrs.JOINTS_0).astype(np.uint16)
        weights   = self._read_accessor(gltf, attrs.WEIGHTS_0).astype(np.float32)
        if prim.indices is None:
            # Primitive não-indexada (válido no glTF: ausência de "indices"
            # significa desenhar os vértices em sequência). Gera um índice
            # sequencial sintético para manter a mesma SkinnedMeshData.indices
            # que o resto do pipeline (skinning, draw) espera.
            mode = prim.mode if prim.mode is not None else 4  # default glTF = TRIANGLES
            n_verts = len(positions)
            if mode == 4:  # TRIANGLES
                indices = np.arange(n_verts, dtype=np.uint32)
            elif mode == 5:  # TRIANGLE_STRIP -> expande para lista de triângulos
                tris = []
                for i in range(n_verts - 2):
                    if i % 2 == 0:
                        tris.extend([i, i + 1, i + 2])
                    else:
                        tris.extend([i + 1, i, i + 2])
                indices = np.array(tris, dtype=np.uint32)
            elif mode == 6:  # TRIANGLE_FAN -> expande para lista de triângulos
                tris = []
                for i in range(1, n_verts - 1):
                    tris.extend([0, i, i + 1])
                indices = np.array(tris, dtype=np.uint32)
            else:
                print(f"_build_primitive: primitive sem 'indices' e mode={mode} não suportado para expansão; pulando.")
                return None
        else:
            indices = self._read_accessor(gltf, prim.indices).astype(np.uint32).reshape(-1)
        vertices = np.hstack([positions, normals, uvs]).astype(np.float32)
        wsum = weights.sum(axis=1, keepdims=True)
        wsum[wsum < 1e-8] = 1.0
        weights = weights / wsum
        texture_path = self._resolve_texture(gltf, prim, base_dir)
        return SkinnedMeshData(
            name=name, vertices=vertices, indices=indices,
            joints=joints, weights=weights,
            bones=bones, clips=clips,
            texture_path=texture_path,
        )

    def _resolve_texture(self, gltf, prim, base_dir) -> Optional[str]:
        try:
            material = gltf.materials[prim.material]
            tex_info = material.pbrMetallicRoughness.baseColorTexture
            if tex_info is None:
                return None
            tex = gltf.textures[tex_info.index]
            image = gltf.images[tex.source]
            if image.uri:
                path = os.path.join(base_dir, image.uri)
                return path if os.path.isfile(path) else None
            if image.bufferView is not None:
                return self._extract_embedded_image(gltf, image, base_dir)
        except Exception:
            return None
        return None

    def _extract_embedded_image(self, gltf, image, base_dir) -> Optional[str]:
        bv = gltf.bufferViews[image.bufferView]
        blob = gltf.binary_blob()
        data = blob[bv.byteOffset: bv.byteOffset + bv.byteLength]
        ext = ".png" if "png" in (image.mimeType or "") else ".jpg"
        out_path = os.path.join(base_dir, f"_embedded_{image.bufferView}{ext}")
        if not os.path.isfile(out_path):
            with open(out_path, "wb") as f:
                f.write(data)
        return out_path

    def _read_accessor(self, gltf, accessor_index: int) -> np.ndarray:
        return self._decode_accessor(gltf, accessor_index)

    def _decode_accessor(self, gltf, accessor_index: int) -> np.ndarray:
        accessor = gltf.accessors[accessor_index]
        buffer_view = gltf.bufferViews[accessor.bufferView]
        blob = gltf.binary_blob()
        comp_type_map = {
            5120: np.int8, 5121: np.uint8,
            5122: np.int16, 5123: np.uint16,
            5125: np.uint32, 5126: np.float32,
        }
        n_comp_map = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}
        dtype = comp_type_map[accessor.componentType]
        n_comp = n_comp_map[accessor.type]
        item_size = np.dtype(dtype).itemsize * n_comp
        base_offset = (buffer_view.byteOffset or 0) + (accessor.byteOffset or 0)
        count = accessor.count
        stride = buffer_view.byteStride or item_size
        if stride == item_size:
            arr = np.frombuffer(blob, dtype=dtype, count=count * n_comp, offset=base_offset)
            arr = arr.reshape(count, n_comp) if n_comp > 1 else arr.reshape(count)
        else:
            arr = np.empty((count, n_comp), dtype=dtype)
            for i in range(count):
                off = base_offset + i * stride
                arr[i] = np.frombuffer(blob, dtype=dtype, count=n_comp, offset=off)
            if n_comp == 1:
                arr = arr.reshape(count)
        if accessor.normalized and dtype == np.uint16:
            arr = arr.astype(np.float32) / 65535.0
        elif accessor.normalized and dtype == np.uint8:
            arr = arr.astype(np.float32) / 255.0
        return arr.astype(np.float32) if dtype in (np.float32,) else arr
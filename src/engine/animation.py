"""
animation.py  –  AnimationController.

Mantém o estado de animação atual (idle / walking / punching / reaction /
beatrice / invisibleprovidence / item), avança o tempo, faz um blend simples
(crossfade linear) entre o clipe anterior e o novo ao trocar de estado, e
expõe get_bone_matrices() — a lista de mat4 finais (uma por osso) pronta
para subir como uniform array no skinned.vert (uBoneMatrices[]).

Não depende de pygame/OpenGL — só numpy. Pode ser testado isoladamente.
"""

import numpy as np
from .gltf_loader import Bone, AnimationClip
from .math3d import identity


# Mapeia os nomes de "intenção" do jogo para os nomes de clipe esperados
# dentro do .glb (ajuste se os clipes saírem do Blender com outro nome).
DEFAULT_CLIP_NAMES = {
    "idle":                "Idle",
    "walking":             "Walking",
    "jumping":             "Jumping",
    "punching":            "Punching",
    "reaction":            "Reaction",
    "beatrice":            "Beatrice",            # minya / emt / shamac
    "invisibleprovidence": "InvisibleProvidence",  # invisible providence
    "item":                "Item",                 # uso de item (cura HP ou MP)
    # Emilia — cutscene pos-boss
    "sleeping":            "Sleeping",            # loop: deitada inconsciente
    "waking":              "Waking",              # one-shot: acordando
    # Marluxia — boss
    "normalattack":        "NormalAttack",
    "heavyattack":         "HeavyAttack",
    "roundattack":         "RoundAttack",
    "groundmagic":         "GroundMagic",
    "shoot":               "Shoot",
    "curse":               "Curse",
    "taunt":               "Taunt",
    "invincible":          "Invincible",
    "hit":                 "Hit",
    "death":               "Death",
}

# Estados que tocam uma vez e voltam para idle sozinhos ao terminar
ONE_SHOT_STATES = {
    "punching", "reaction", "jumping",
    "beatrice", "invisibleprovidence", "item",
    "waking",   # one-shot: toca uma vez e volta para idle
}

BLEND_TIME = 0.15  # segundos de crossfade ao trocar de estado


def _quat_to_mat3(q: np.ndarray) -> np.ndarray:
    x, y, z, w = q
    xx, yy, zz = x * x, y * y, z * z
    xy, xz, yz = x * y, x * z, y * z
    wx, wy, wz = w * x, w * y, w * z
    return np.array([
        [1 - 2 * (yy + zz), 2 * (xy - wz),     2 * (xz + wy)],
        [2 * (xy + wz),     1 - 2 * (xx + zz), 2 * (yz - wx)],
        [2 * (xz - wy),     2 * (yz + wx),     1 - 2 * (xx + yy)],
    ], dtype=np.float32)


def _trs_to_mat4(t: np.ndarray, r: np.ndarray, s: np.ndarray) -> np.ndarray:
    # Produz matrix column-major: translação na coluna 3 (m[:3, 3]),
    # mesma convenção das IBMs lidas do glTF e esperada pelo shader GLSL
    # (gl_Position = uProj * uView * uModel * skinMatrix * vec4(pos,1.0)).
    m = np.eye(4, dtype=np.float32)
    rot3 = _quat_to_mat3(r)
    m[:3, :3] = rot3 * s[np.newaxis, :]   # escala por coluna
    m[:3, 3] = t
    return m


def _slerp(q0, q1, t):
    dot = float(np.dot(q0, q1))
    if dot < 0.0:
        q1 = -q1; dot = -dot
    if dot > 0.9995:
        result = q0 + t * (q1 - q0)
        n = np.linalg.norm(result)
        return result / n if n > 1e-8 else result
    theta_0 = np.arccos(np.clip(dot, -1.0, 1.0))
    theta = theta_0 * t
    q2 = q1 - q0 * dot
    n = np.linalg.norm(q2)
    q2 = q2 / n if n > 1e-8 else q2
    return q0 * np.cos(theta) + q2 * np.sin(theta)


class AnimationController:
    """
    Uso típico (em main.py, dentro do update por frame):
        anim_controller.update(dt)
        bone_matrices = anim_controller.get_bone_matrices()
        shader.set_mat4_array("uBoneMatrices", bone_matrices)

    Trocar de estado (chamado nos eventos do jogo):
        anim_controller.play("walking")
        anim_controller.play("punching")            # one-shot, volta a idle/walking sozinho
        anim_controller.play("reaction")             # one-shot
        anim_controller.play("beatrice")             # one-shot (minya / emt / shamac)
        anim_controller.play("invisibleprovidence")  # one-shot
        anim_controller.play("item")                 # one-shot (cura HP ou MP)
    """

    def __init__(self, bones: list, clips: dict, clip_names: dict = None,
                 root_transform=None):
        self.bones = bones
        self.clips: dict = clips
        self.clip_names = clip_names or DEFAULT_CLIP_NAMES
        # Transform do node Armature (pai dos joints): embarca scale cm->m e
        # conversão de eixo. Pré-multiplicado nos globals dos bones raiz.
        self._root_transform = root_transform  # np.ndarray (4,4) ou None

        self.state = "idle"
        self.time = 0.0

        self._prev_state = None
        self._prev_time = 0.0
        self._blend_t = 0.0
        self._blend_duration = 0.0

        self._on_finish_state = "idle"  # para que estado voltar após um one-shot

    # ── Controle de estado ───────────────────────────────────────────────────

    def play(self, state_name: str, restart_if_same: bool = False):
        """Troca o estado de animação. Ignora se já está nesse estado
        (a menos que restart_if_same=True), para não resetar o tempo a
        cada frame em que a tecla continua pressionada."""
        if state_name not in self.clip_names:
            return
        if state_name == self.state and not restart_if_same:
            return

        self._prev_state = self.state
        self._prev_time = self.time
        self._blend_t = 0.0
        self._blend_duration = BLEND_TIME

        self.state = state_name
        self.time = 0.0

    def update(self, dt: float):
        self.time += dt
        if self._blend_t < self._blend_duration:
            self._blend_t += dt

        clip = self._clip_for(self.state)
        if clip and self.state in ONE_SHOT_STATES and self.time >= clip.duration:
            # one-shot terminou -> volta a idle (ou walking se ainda andando;
            # main.py decide isso chamando play("walking")/"idle" logo após
            # o one-shot acabar — ver _update_player_animation)
            self.play("idle")

    def is_playing(self, state_name: str) -> bool:
        return self.state == state_name

    def is_one_shot_active(self) -> bool:
        """True se o estado atual é um one-shot (punching/reaction/jumping/
        beatrice/invisibleprovidence/item) e ainda não terminou seu clipe.
        Usado por main.py pra saber se pode trocar livremente pra idle/walking
        ou se precisa esperar a animação atual acabar."""
        return self.state in ONE_SHOT_STATES and not self.finished_one_shot()

    def finished_one_shot(self) -> bool:
        """True no frame em que um estado one-shot acabou de completar
        seu clipe. Útil pra main.py decidir o próximo estado."""
        clip = self._clip_for(self.state)
        return (self.state in ONE_SHOT_STATES and clip is not None
                and self.time >= clip.duration)

    # ── Sampling ──────────────────────────────────────────────────────────────

    def _clip_for(self, state_name: str) -> AnimationClip:
        clip_name = self.clip_names.get(state_name)
        return self.clips.get(clip_name)

    def get_bone_matrices(self) -> list:
        """Retorna list[np.ndarray (4,4)], uma por osso, já prontas
        (globalTransform @ inverseBindMatrix) para o shader."""
        current_locals = self._sample_locals(self.state, self.time)

        if self._prev_state is not None and self._blend_t < self._blend_duration:
            prev_locals = self._sample_locals(self._prev_state, self._prev_time + self._blend_t)
            alpha = self._blend_t / self._blend_duration if self._blend_duration > 0 else 1.0
            locals_ = self._blend_locals(prev_locals, current_locals, alpha)
        else:
            locals_ = current_locals
            self._prev_state = None

        return self._compute_global_then_skin(locals_)

    def _sample_locals(self, state_name: str, t: float) -> list:
        """Retorna list[mat4] = transform local (no espaço do pai) de cada
        osso, amostrado no tempo t do clipe correspondente ao estado."""
        clip = self._clip_for(state_name)
        out = []
        for i, bone in enumerate(self.bones):
            track = clip.bone_tracks[i] if clip else None
            if track is None or len(track.times) == 0:
                # osso não animado neste clipe -> usa bind pose
                out.append(_trs_to_mat4(bone.local_bind_translation,
                                         bone.local_bind_rotation,
                                         bone.local_bind_scale))
                continue
            ct = t % clip.duration if clip and clip.duration > 0 else 0.0
            tr, rot, sc = self._sample_track(track, ct)
            out.append(_trs_to_mat4(tr, rot, sc))
        return out

    def _sample_track(self, track, t: float):
        times = track.times
        idx = np.searchsorted(times, t)
        if idx <= 0:
            return track.translations[0], track.rotations[0], track.scales[0]
        if idx >= len(times):
            return track.translations[-1], track.rotations[-1], track.scales[-1]
        t0, t1 = times[idx - 1], times[idx]
        alpha = 0.0 if t1 == t0 else (t - t0) / (t1 - t0)
        tr = track.translations[idx - 1] + (track.translations[idx] - track.translations[idx - 1]) * alpha
        sc = track.scales[idx - 1] + (track.scales[idx] - track.scales[idx - 1]) * alpha
        rot = _slerp(track.rotations[idx - 1], track.rotations[idx], alpha)
        return tr, rot, sc

    def _blend_locals(self, a_list, b_list, alpha: float) -> list:
        """Crossfade simples: lerp/slerp matriz-a-matriz entre dois poses já
        decompostas de volta em TRS seria mais correto, mas para um blend
        curto (BLEND_TIME) e ossos pequenos, lerp direto das matrizes 4x4
        já fica visualmente suave o bastante e é bem mais barato."""
        return [a * (1.0 - alpha) + b * alpha for a, b in zip(a_list, b_list)]

    def _compute_global_then_skin(self, locals_: list) -> list:
        globals_ = [None] * len(self.bones)

        def compute(i):
            if globals_[i] is not None:
                return globals_[i]
            bone = self.bones[i]
            if bone.parent_index == -1:
                # Bone raiz: pré-multiplica pelo root_transform do Armature
                # (embarca scale cm->m e conversão de eixo do exportador).
                if self._root_transform is not None:
                    globals_[i] = self._root_transform @ locals_[i]
                else:
                    globals_[i] = locals_[i]
            else:
                parent_global = compute(bone.parent_index)
                globals_[i] = parent_global @ locals_[i]
            return globals_[i]

        for i in range(len(self.bones)):
            compute(i)

        return [globals_[i] @ self.bones[i].inverse_bind_matrix
                for i in range(len(self.bones))]
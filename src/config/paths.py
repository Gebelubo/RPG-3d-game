from src.here import _HERE
import os

MODEL_TOWER = os.path.join(_HERE, "assets", "models", "tower")

SUBARU_GLB_DIR = os.path.join(_HERE, "assets", "models", "Subaru")
SUBARU_GLB_FILES = {
    "Idle":                 os.path.join(SUBARU_GLB_DIR, "subaru_idle.glb"),
    "Walking":              os.path.join(SUBARU_GLB_DIR, "subaru_walking.glb"),
    "Jumping":              os.path.join(SUBARU_GLB_DIR, "subaru_jumping.glb"),
    "Punching":             os.path.join(SUBARU_GLB_DIR, "subaru_punching.glb"),
    "Reaction":             os.path.join(SUBARU_GLB_DIR, "subaru_hit.glb"),
    "Beatrice":             os.path.join(SUBARU_GLB_DIR, "subaru_beatrice.glb"),
    "InvisibleProvidence":  os.path.join(SUBARU_GLB_DIR, "subaru_invisibleprovidence.glb"),
    "Item":                 os.path.join(SUBARU_GLB_DIR, "subaru_item.glb"),
}

# Modelo completo e animado da própria Beatrice (mesh + skeleton + clipe de
# idle em loop), usado em _show_beatrice() no lugar do antigo Beatrice.obj
# estático. Tem um único clipe ("Swim_Idle_Loop") que toca em loop contínuo
# enquanto ela estiver visível em cena.
BEATRICE_GLB_PATH = os.path.join(_HERE, "assets", "models", "Beatrice", "beatrice_animation.glb")
BEATRICE_CLIP_NAMES = {"idle": "Swim_Idle_Loop"}

HEARTLESS_GLB_PATH  = os.path.join(_HERE, "assets", "models", "Heartless",     "heartless_idle.glb")
AERIALKNOCKER_GLB_PATH  = os.path.join(_HERE, "assets", "models", "AerialKnocker", "aerialknocker_idle.glb")

EMILIA_GLB_PATH         = os.path.join(_HERE, "assets", "models", "Emilia", "emilia_idle.glb")

MARLUXIA_GLB_PATH       = os.path.join(_HERE, "assets", "models", "Marluxia", "marluxia_idle.glb")

SHADER_DIR = os.path.join(_HERE, "assets", "shaders")
SAVE_PATH  = os.path.join(_HERE, "savegame.json")
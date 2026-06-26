SCREEN_W, SCREEN_H = 1280, 720
TITLE      = "Re:Oblivion of Memories"


ROOM_W = 20.0
ROOM_D = 30.0
ROOM_H = 8.0

STAIR_COUNT     = 5
STAIR_WIDTH     = 3.0
STAIR_STEP_H    = 0.4
STAIR_STEP_D    = 1.2
STAIR_Z_START   = -10.5
STAIR_Z_SPACING = 1.0

BEATRICE_Y_OFFSET = 0.5  
SUBARU_Y_OFFSET    = 0.0  
HEARTLESS_Y_OFFSET = -0.5  
AERIALKNOCKER_Y_OFFSET = -0.8  


SUBARU_TARGET_HEIGHT = 1.8
HEARTLESS_TARGET_HEIGHT = 1.8  

AERIALKNOCKER_TARGET_HEIGHT = 1.4


HEARTLESS_CLIP_NAMES = {
    "idle":         "Idle",          # heartless_idle.glb
    "walking":      "Idle",
    "lightattack":  "NormalAttack",  # heartless_normalattack.glb
    "normalattack": "NormalAttack",
    "heavyattack":  "HeavyAttack",   # heartless_heavyattack.glb
    "death":        "Death",         # heartless_death.glb
}
AERIALKNOCKER_CLIP_NAMES = {
    "idle":        "Idle",           # aerialknocker_idle.glb
    "walking":     "Idle",
    "lightattack": "BaseAttack",     # aerialknocker_baseattack.glb
    "baseattack":  "BaseAttack",
    "heavyattack": "DownAttack",     # aerialknocker_downattack.glb
    "downattack":  "DownAttack",
    "death":       "Death",          # aerialknocker_death.glb
}

EMILIA_TARGET_HEIGHT    = 1.7
EMILIA_Y_OFFSET         = 0.0  

EMILIA_PHASE_OFFSETS = {
    "sleeping": (0.0, -1.0, 0.0),   # desce um pouco
    "waking":   (0.8, 0.0, 0.0),    # vai um pouco para a esquerda
    "idle":     (0.0, 0.0, 0.0),     # posição original, já está correta
}
EMILIA_CLIP_NAMES       = {"idle": "mixamo.com"}  # nome real do clipe no GLB
EMILIA_MANUAL_SCALE     = 0.75  # escala manual: GLB tem scale:100 nos nodes, auto_scale falha

MARLUXIA_TARGET_HEIGHT  = 0.5  # aumentado de 1.9 → 2.5 (ajuste à vontade)
MARLUXIA_Y_OFFSET       = 0.0
MARLUXIA_CLIP_NAMES = {
    "idle":          "Idle",
    "normalattack":  "NormalAttack",
    "heavyattack":   "HeavyAttack",
    "roundattack":   "RoundAttack",
    "groundmagic":   "GroundMagic",
    "shoot":         "Shoot",
    "curse":         "Curse",
    "taunt":         "Taunt",
    "invincible":    "Invincible",
    "hit":           "Hit",
    "death":         "Death",
}  

BEATRICE_CLIP_NAMES = {"idle": "Swim_Idle_Loop"}


BEATRICE_TARGET_HEIGHT = 1.6  




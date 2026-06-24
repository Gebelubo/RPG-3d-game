SCREEN_W, SCREEN_H = 1280, 720
TITLE      = "Torre de Plêiades – Re:Zero RPG"


ROOM_W = 20.0
ROOM_D = 30.0
ROOM_H = 8.0

STAIR_COUNT     = 5
STAIR_WIDTH     = 3.0
STAIR_STEP_H    = 0.4
STAIR_STEP_D    = 1.2
STAIR_Z_START   = -10.5
STAIR_Z_SPACING = 1.0

BEATRICE_Y_OFFSET = 0.5  # quanto a Beatrice fica acima do chão (ajuste de altura do modelo)
SUBARU_Y_OFFSET    = 0.0  # quanto o modelo do Subaru fica acima do world_pos (chão lógico)
HEARTLESS_Y_OFFSET = -0.5  # quanto o Heartless fica acima/abaixo do chão (negativo = mais baixo)
AERIALKNOCKER_Y_OFFSET = 0.0  # quanto o AerialKnocker fica acima/abaixo do world_pos


SUBARU_TARGET_HEIGHT = 1.8
# Heartless terrestre animado (heartless_idle.glb – mesma origem Mixamo do Subaru)
HEARTLESS_TARGET_HEIGHT = 1.8  # altura alvo em metros para auto-scale (aumente este valor para um Heartless maior)

# AerialKnocker animado (aerialknocker_idle.glb – mesma origem que Beatrice/Mixamo)
AERIALKNOCKER_TARGET_HEIGHT = 1.4

# Nenhum dos dois .glb tem clipes chamados "Idle"/"Walking" (não é o padrão
# Mixamo de fato) — cada um só exporta UM clipe de loop, com nome próprio:
#   heartless_idle.glb     -> "mixamo.com"
#   aerialknocker_idle.glb -> "Swim_Idle_Loop" (mesma origem da Beatrice)
# Como só existe esse clipe único, mapeamos tanto "idle" quanto "walking"
# para ele: assim o heartless/aerialknocker continuam tocando o mesmo loop
# ao andar em vez de cair no bind pose estático por falta de clipe "Walking".
HEARTLESS_CLIP_NAMES = {"idle": "mixamo.com", "walking": "mixamo.com"}
AERIALKNOCKER_CLIP_NAMES = {"idle": "Swim_Idle_Loop", "walking": "Swim_Idle_Loop"}

# Emilia animada – mesmo pipeline do Subaru (sem NGC, defaults neutros)
EMILIA_TARGET_HEIGHT    = 1.7
EMILIA_Y_OFFSET         = 0.0  # deitada no chão: Y sobe para ficar sobre a superfície
# Offsets de posição por fase da cutscene pós-boss (em metros, relativos à
# posição base em_pos). Ajuste estes valores visualmente conforme necessário.
EMILIA_PHASE_OFFSETS = {
    "sleeping": (0.0, -1.0, 0.0),   # desce um pouco
    "waking":   (0.8, 0.0, 0.0),    # vai um pouco para a esquerda
    "idle":     (0.0, 0.0, 0.0),     # posição original, já está correta
}
EMILIA_CLIP_NAMES       = {"idle": "mixamo.com"}  # nome real do clipe no GLB
EMILIA_MANUAL_SCALE     = 0.75  # escala manual: GLB tem scale:100 nos nodes, auto_scale falha

# Marluxia animado – mesmo pipeline da Beatrice/AerialKnocker (NGC Beatrice)
MARLUXIA_TARGET_HEIGHT  = 0.5  # aumentado de 1.9 → 2.5 (ajuste à vontade)
MARLUXIA_Y_OFFSET       = 0.0
MARLUXIA_CLIP_NAMES     = {"idle": "mixamo.com"}  # preenchido dinamicamente

BEATRICE_CLIP_NAMES = {"idle": "Swim_Idle_Loop"}


BEATRICE_TARGET_HEIGHT = 1.6  # Beatrice é um pouco mais baixa que o Subaru (1.8)




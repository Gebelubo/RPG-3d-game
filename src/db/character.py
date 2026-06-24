from src.entities.character import Character, MultiClipCharacter
import os

from src.config.constants import (SUBARU_Y_OFFSET,
                                  EMILIA_Y_OFFSET,
                                  BEATRICE_Y_OFFSET,
                                  MARLUXIA_Y_OFFSET,
                                  HEARTLESS_Y_OFFSET,
                                  AERIALKNOCKER_Y_OFFSET,
                                  EMILIA_CLIP_NAMES,
                                  BEATRICE_CLIP_NAMES,
                                  MARLUXIA_CLIP_NAMES,
                                  HEARTLESS_CLIP_NAMES,
                                  AERIALKNOCKER_CLIP_NAMES,
                                  EMILIA_MANUAL_SCALE,
                                  SUBARU_TARGET_HEIGHT,
                                  EMILIA_TARGET_HEIGHT,
                                  BEATRICE_TARGET_HEIGHT,
                                  MARLUXIA_TARGET_HEIGHT,
                                  HEARTLESS_TARGET_HEIGHT,
                                  AERIALKNOCKER_TARGET_HEIGHT)

from src.config.paths import (SUBARU_GLB_FILES,
                              EMILIA_GLB_PATH,
                              BEATRICE_GLB_PATH,
                              MARLUXIA_GLB_PATH,
                              HEARTLESS_GLB_PATH,
                              AERIALKNOCKER_GLB_PATH,
                              SUBARU_GLB_DIR)

CHARACTER_DB = {
    "subaru": MultiClipCharacter(name="subaru",
                            y_offset=SUBARU_Y_OFFSET,
                            target_height=SUBARU_TARGET_HEIGHT, 
                            files=SUBARU_GLB_FILES,
                            fallback_texture=os.path.join(os.path.dirname(SUBARU_GLB_DIR),"tx_Subaru_00_Body_Base.png"),
                            primary_clip="Walking"),
    "emilia": Character(name="emilia",
                        y_offset=EMILIA_Y_OFFSET, 
                        target_height=EMILIA_TARGET_HEIGHT, 
                        glb_path=EMILIA_GLB_PATH, 
                        clip_names=EMILIA_CLIP_NAMES, 
                        manual_scale=EMILIA_MANUAL_SCALE,
                        fallback_texture=os.path.join(os.path.dirname(EMILIA_GLB_PATH),"tx_Emilia_Base.png")),
    "beatrice": Character(name="beatrice",
                          y_offset=BEATRICE_Y_OFFSET, 
                          target_height=BEATRICE_TARGET_HEIGHT, 
                          glb_path=BEATRICE_GLB_PATH, 
                          clip_names=BEATRICE_CLIP_NAMES,
                          fallback_texture=os.path.join(os.path.dirname(BEATRICE_GLB_PATH),"tx_Beatrice_Base.png")),
    "marluxia": Character(name="marluxia",
                          y_offset=MARLUXIA_Y_OFFSET, 
                          target_height=MARLUXIA_TARGET_HEIGHT, 
                          glb_path=MARLUXIA_GLB_PATH, 
                          clip_names=MARLUXIA_CLIP_NAMES,
                          fallback_texture=os.path.join(os.path.dirname(MARLUXIA_GLB_PATH),"tx_Marluxia_Base.png")),
    "aerialknocker": Character(name="aerialknocker",
                               y_offset=AERIALKNOCKER_Y_OFFSET, 
                               target_height=AERIALKNOCKER_TARGET_HEIGHT, 
                               glb_path=AERIALKNOCKER_GLB_PATH, 
                               clip_names=AERIALKNOCKER_CLIP_NAMES,
                               fallback_texture=os.path.join(os.path.dirname(AERIALKNOCKER_GLB_PATH),"tx_AerialKnocker.png")),
    "heartless": Character(name="heartless",
                           y_offset=HEARTLESS_Y_OFFSET, 
                           target_height=HEARTLESS_TARGET_HEIGHT, 
                           glb_path=HEARTLESS_GLB_PATH, 
                           clip_names=HEARTLESS_CLIP_NAMES,
                           fallback_texture=os.path.join(os.path.dirname(HEARTLESS_GLB_PATH),"tx_Heartless.png"))
}

class CharacterDB:
    def __init__(self):
        pass

    def get_char(self, key: str) -> Character:
        return CHARACTER_DB[key]
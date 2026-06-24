from dataclasses import dataclass, field
from typing import Optional, List
import random
import math
@dataclass
class Item:
    id: str; name: str; description: str
    item_type: str = "consumable"; value: int = 0
    heal_hp: int = 0; heal_mp: int = 0
    atk_bonus: int = 0; def_bonus: int = 0

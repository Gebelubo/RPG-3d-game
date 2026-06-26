from dataclasses import dataclass, field
from typing import Optional, List
import random
import math
@dataclass
class Spell:
    id: str; name: str; description: str
    mp_cost: int = 10; damage: int = 0; heal_hp: int = 0
    element: str = "none"; icon_color: tuple = (0.5, 0.5, 1.0)


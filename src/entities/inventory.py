from dataclasses import dataclass, field
from typing import Optional, List
import random
import math

from src.db.item import ITEM_DB

@dataclass
class Inventory:
    items: dict = field(default_factory=dict)
    gold: int = 0

    def add(self, item_id, qty=1):
        self.items[item_id] = self.items.get(item_id, 0) + qty

    def remove(self, item_id, qty=1) -> bool:
        if self.items.get(item_id, 0) >= qty:
            self.items[item_id] -= qty
            if self.items[item_id] == 0: del self.items[item_id]
            return True
        return False

    def has(self, item_id, qty=1) -> bool:
        return self.items.get(item_id, 0) >= qty

    def list_consumables(self):
        return [(ITEM_DB[iid], qty) for iid, qty in self.items.items()
                if iid in ITEM_DB and ITEM_DB[iid].item_type == "consumable"]

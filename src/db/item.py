from src.entities.item import Item

ITEM_DB = {
    "health_potion_s": Item("health_potion_s", "Amor de Emilia",   "Recupera vida.",  heal_hp=30,  value=10),
    "health_potion_l": Item("health_potion_l", "Amor de Emilia",   "Recupera vida.",  heal_hp=80,  value=30),
    "mana_potion":     Item("mana_potion",     "Confiança de Beatrice",    "Recupera mana.",  heal_mp=40,  value=20),
    "iron_sword":      Item("iron_sword",      "Iron Sword",     "Espada de ferro.", item_type="weapon", atk_bonus=8, value=50),
    "tracksuit":       Item("tracksuit",       "Agasalho do Subaru", "Icônico agasalho.", item_type="armor", def_bonus=3, value=0),
}
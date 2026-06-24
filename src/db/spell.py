from src.entities.spell import Spell

SPELL_DB = {
    "shamac":    Spell("shamac",    "Shamac",              "Faz o inimigo perder sua pista por 10 segundos.",     mp_cost=15, damage=0,  element="dark", icon_color=(0.4,0.1,0.6)),
    "minya":     Spell("minya",     "Minya",              "Ataca o inimigo com a mão sombria.",                mp_cost=18, damage=40, element="dark", icon_color=(0.3,0.0,0.5)),
    "invisible_providence": Spell("invisible_providence", "Invisible Providence", "Ataca o inimigo de forma invisível.",       mp_cost=30, damage=60, element="light", icon_color=(0.8,0.8,0.4)),
    "emt":       Spell("emt",       "EMT",                "Protege contra ataques inimigos por 10 segundos.",  mp_cost=20, damage=0,  element="none", icon_color=(0.2,0.7,0.8)),
}
SPELL_LIST = ["shamac", "minya", "invisible_providence", "emt"]

# RPG3D – Base Engine

Motor 3D + base de jogo RPG em Python puro + OpenGL 4.0.

## Dependências

```
pip install pygame PyOpenGL PyOpenGL_accelerate numpy Pillow
```

## Executar

```
cd rpg3d/
python main.py
```

---

## Controles

| Tecla | Ação |
|---|---|
| W A S D | Mover câmera |
| Mouse | Olhar ao redor (capturado em modo jogo) |
| E | Iniciar combate |
| ESC | Menu de pausa / liberar mouse |
| F1 | Alternar wireframe (debug) |
| ↑ ↓ Enter | Navegar menus |

---

## Arquitetura

```
rpg3d/
├── main.py                 ← Entry point, Game loop
├── hud.py                  ← HUD 2D (OpenGL quads + texto)
├── menu.py                 ← Sistema de menus (stack-based)
├── requirements.txt
│
├── engine/
│   ├── math3d.py           ← Álgebra linear (NumPy puro)
│   ├── shader.py           ← Compilação/uso de shaders GLSL
│   ├── obj_loader.py       ← Leitor próprio de .obj / .mtl
│   ├── mesh.py             ← GPU mesh (VAO/VBO/IBO) + geo procedural
│   ├── texture.py          ← Carregamento de texturas (Pillow → GL)
│   ├── camera.py           ← Câmera livre FPS
│   ├── scene.py            ← SceneNode, Scene, PointLight
│   └── input_manager.py   ← Teclado + mouse via pygame (só eventos)
│
├── game/
│   └── rpg_data.py         ← Stats, Inventory, CombatSystem, Player
│
└── assets/
    ├── shaders/
    │   ├── phong.vert/frag  ← Shader Phong (iluminação)
    │   └── unlit.vert/frag  ← Shader sem iluminação (HUD, debug)
    ├── models/              ← Coloque arquivos .obj aqui
    └── textures/            ← Texturas extras (.png, .jpg)
```

---

## Conformidade com as constraints

| Requisito | Como foi implementado |
|---|---|
| OpenGL ≥ 4.0 puro | `#version 400 core` em todos os shaders; só `glDraw*`, `glBind*`, etc. |
| Projeção perspectiva | `engine/math3d.py → perspective()` + `Camera.projection_matrix()` |
| Câmera livre (FPS) | `engine/camera.py` – WASD + mouse look |
| Iluminação Phong | `assets/shaders/phong.vert/frag` – ambiente + difusa + especular |
| Fonte de luz animada | `PointLight.orbit = True` – orbita a cena em `Scene.update()` |
| Objeto animado | Cubo gira em X e Y via `SceneNode.set_animator()` |
| Objeto com textura | Esfera (enemy) + chão com `ProceduralTexture` |
| Objeto com cor sólida | Cubo usa `uBaseColor` sem textura |
| Leitor OBJ próprio | `engine/obj_loader.py` – parse completo v/vt/vn/f/mtllib/usemtl |
| Contexto gráfico via pygame | `pygame.display.set_mode(DOUBLEBUF \| OPENGL)` – só inicialização |
| Álgebra linear via NumPy | `engine/math3d.py` exclusivamente |
| Eventos por pygame | `engine/input_manager.py` usa só `pygame.event.get()` |

---

## Como adicionar conteúdo

### Adicionar modelo OBJ

Coloque o `.obj` (e `.mtl` + texturas) em `assets/models/`.
O jogo carrega automaticamente ao iniciar.

```python
# Ou carregue manualmente em _init_scene():
from engine.obj_loader import OBJLoader
from engine.mesh import Mesh
datas = OBJLoader().load("assets/models/meu_modelo.obj")
for md in datas:
    node = SceneNode("meu_obj", mesh=Mesh(md), position=(0, 0, -5))
    self.scene.add(node)
```

### Criar novo inimigo

```python
from game.rpg_data import Stats
goblin = Stats(name="Goblin", level=2, max_hp=60, hp=60,
               atk=8, defense=3, spd=12)
combat = player.start_combat(goblin)
```

### Animar qualquer nó

```python
def my_anim(node, dt):
    node.rotation[1] += 45 * dt   # gira 45°/s no eixo Y
    node.position[1] = math.sin(time.time())

node.set_animator(my_anim)
```

### Adicionar item ao banco

```python
from game.rpg_data import ITEM_DB, Item
ITEM_DB["mana_potion"] = Item(
    "mana_potion", "Mana Potion",
    "Restaura 50 MP.", heal_hp=0, value=20
)
```

---

## Próximos passos sugeridos

- [ ] Adicionar inimigos com pathfinding simples
- [ ] Sistema de diálogos (NPC com árvore de diálogo)
- [ ] Skybox (cubo invertido com textura de céu)
- [ ] Mapa com terreno gerado proceduralmente (heightmap)
- [ ] Sistema de save/load (JSON)
- [ ] Múltiplos inimigos por combate
- [ ] Efeitos de partículas (faíscas, fogo)
- [ ] Tela de inventário completa com ícones

# Re:Oblivion of Memories

RPG 3D em Python inspirado em *Re:Zero* e *Kingdom Hearts*. Você controla **Natsuki Subaru** enquanto sobe o **Caslte Oblivion**, enfrentando Heartless, resolvendo puzzles, passando por minigames e duelando contra **Marluxia** no confronto final.

O jogo roda em uma janela OpenGL (1280×720) com modelos animados GLB, combate em tempo real, sistema de magias, inventário e progressão por andares.

---

## Documentação

| Documento | Descrição |
|-----------|-----------|
| [Como rodar o jogo](docs/COMO-RODAR.md) | Requisitos, instalação, execução e solução de problemas |
| [Arquitetura do projeto](docs/ARQUITETURA.md) | Camadas do código, engine 3D, fluxo do game loop e dependências |
| [Conteúdo e gameplay](docs/JOGO.md) | Andares, mecânicas, personagens, magias, itens e história |
| [Controles](docs/CONTROLES.md) | Teclado, mouse, menus e atalhos |

---

## Início rápido

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
python main.py
```

Requisitos: **Python 3.10+**, placa com suporte a **OpenGL 3.x**.

---

## Visão geral

```
main.py  →  Game (game_main.py)  →  loop Pygame + render OpenGL
                ├── Engine (cena, câmera, shaders, GLTF)
                ├── Entidades (player, inimigos, stats)
                ├── HUD + menus
                └── 7 andares da torre (entry → boss)
```

| Andar | Tema principal |
|-------|----------------|
| 0 — Entrada | Tutorial de combate, porta e escadas |
| 1 — Puzzle | Fragmentos de mural, parkour, caixa empurrável |
| 2 — Aerial | Heartless terrestres e voadores |
| 3 — Ritmo | Minigame rítmico no obelisco |
| 4 — Corredor | Ondas de inimigos (gauntlet) |
| 5 — Descanso | Cura total, save automático, relatórios de Marluxia |
| 6 — Boss | Marluxia + cutscene da Emilia |

---

## Estrutura do repositório

```
RPG-3d-game/
├── main.py                 # Ponto de entrada
├── requirements.txt        # Dependências Python
├── docs/                   # Documentação detalhada
└── src/
    ├── config/             # Constantes, caminhos, cache
    ├── engine/             # Motor 3D (OpenGL, GLTF, cena)
    ├── entities/           # Player, inimigos, itens, stats
    ├── db/                 # Banco de dados estático (magias, itens, personagens)
    ├── game/               # Lógica principal (andares, combate, helper)
    ├── hud/                # Interface na tela
    ├── menu.py             # Sistema de menus
    ├── assets/             # Modelos, texturas, música, SFX
    └── tools/              # Utilitários (ex.: geração de texturas)
```

---

## Stack tecnológica

- **Pygame** — janela, input, áudio
- **PyOpenGL** — renderização 3D (Phong + skinning)
- **NumPy** — matemática e matrizes
- **Pillow** — carregamento de imagens
- **pygltflib** — leitura de modelos GLB/GLTF

---

## Licença

Projeto sob [MIT License](LICENSE) — Copyright (c) 2026 Gebelubo.

---

## Créditos e referências

Personagens e temas fazem referência a *Re:Zero* e *Kingdom Hearts*. Modelos 3D animados exportados via Mixamo; assets de áudio e imagem incluídos em `src/assets/`.

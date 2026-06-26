# Controles

Referência completa de teclado e mouse para **Re:Oblivion of Memories**.

[← Voltar ao README principal](../README.md)

---

## Exploração (`game_mode: explore`)

| Tecla | Ação |
|-------|------|
| `W` `A` `S` `D` | Mover (relativo à direção da câmera) |
| `Mouse` | Girar câmera (mouse capturado) |
| `Espaço` | Pular |
| `Shift` (esquerdo) | Rolamento (requer movimento + chão) |
| `Z` | Ataque corpo a corpo |
| `F` | Parry (durante wind-up de ataque pesado inimigo) |
| `X` | Abrir/fechar menu de **magias** |
| `C` | Abrir/fechar menu de **itens** |
| `V` | Abrir/fechar menu de **skills** |
| `1` `2` `3` `4` | Selecionar slot do submenu aberto (magia/item) |
| `E` ou `Enter` | Interagir (portas, obelisco, fragmentos, escadas) |
| `Esc` | Menu de pausa |
| `F1` | Alternar wireframe (debug visual) |

---

## Minigame rítmico (`game_mode: rhythm`)

| Tecla | Ação |
|-------|------|
| `←` `↓` `↑` `→` | Acertar notas nas 4 faixas |
| `Esc` | Abortar minigame |

Segure notas longas pressionando e soltando na faixa correta.

---

## Cutscenes e livro

| Tecla | Ação |
|-------|------|
| `Enter` ou `Espaço` | Avançar diálogo / imagem (`story`) |
| `←` / `A` | Página anterior (`book` — relatórios Marluxia) |
| `→` / `D` | Próxima página |
| `Esc`, `E` ou `Enter` | Fechar livro |

---

## Menus (`game_mode: menu`)

| Tecla | Ação |
|-------|------|
| `↑` / `W` | Subir opção |
| `↓` / `S` | Descer opção |
| `Enter` | Confirmar |
| `Esc` | Voltar (se houver menu anterior) |

Menus empilhados: título → pausa → submenus.

### Menu principal

- **Nova Partida** — reinicia save e inicia prologue
- **Continuar** — carrega `src/savegame.json`
- **Sair** — encerra o jogo

### Menu de pausa (`Esc` durante exploração)

- **Continuar**
- **Salvar**
- **Menu Principal**

---

## Tela de morte

Após morrer, aguarde ~3,5s — o jogo respawna automaticamente no andar salvo com HP cheio.

---

## Mouse

- Durante **exploração**: cursor oculto e capturado; movimento relativo gira a câmera
- Durante **menus / story / book**: cursor visível; clique esquerdo suportado via patch em `main.py`

---

## Efeitos especiais nos controles

| Efeito | Impacto |
|--------|---------|
| **Curse (Marluxia fase 3+)** | Inverte `WASD` de movimento |
| **EMT (magia)** | Bloqueia dano inimigo enquanto escudo ativo |
| **Rolamento** | I-frames breves |
| **Parry bem-sucedido** | Inimigo toma dano reflexo; sem dano no player |

---

## Resumo rápido (cartão de referência)

```
Mover .............. WASD
Câmera ............. Mouse
Pular .............. Espaço
Rolar .............. Shift
Atacar ............. Z
Parry .............. F
Magias ............. X + 1-4
Itens .............. C + 1-4
Interagir .......... E / Enter
Pausa .............. Esc
Ritmo .............. Setas
```

---

## Leitura complementar

- [Gameplay e andares](JOGO.md)
- [Como rodar o jogo](COMO-RODAR.md)

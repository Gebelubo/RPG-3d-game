# Como rodar o jogo

Guia para instalar dependências, executar **Re:Oblivion of Memories** e resolver problemas comuns.

[← Voltar ao README principal](../README.md)

---

## Requisitos

| Requisito | Detalhe |
|-----------|---------|
| Python | 3.10 ou superior recomendado |
| Sistema operacional | Windows, Linux ou macOS |
| GPU | Placa com suporte a **OpenGL 3.x** |
| Espaço em disco | ~200 MB (inclui assets 3D e áudio) |
| Áudio | Dispositivo de saída de som (opcional, mas recomendado) |

---

## Instalação

### 1. Clonar o repositório

```bash
git clone <url-do-repositorio>
cd RPG-3d-game
```

### 2. Criar ambiente virtual (recomendado)

**Windows (PowerShell):**

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

**Linux / macOS:**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Instalar dependências

```bash
pip install -r requirements.txt
```

Pacotes instalados:

| Pacote | Uso |
|--------|-----|
| `pygame>=2.5` | Janela, eventos, mixer de áudio |
| `PyOpenGL>=3.1` | Renderização OpenGL |
| `PyOpenGL_accelerate>=3.1` | Aceleração opcional do OpenGL |
| `numpy>=1.24` | Matrizes e vetores |
| `Pillow>=10.0` | Texturas e imagens da UI |
| `pygltflib>=1.16` | Carregamento de modelos GLB |

---

## Executar o jogo

Com o ambiente virtual ativo, na raiz do projeto:

```bash
python main.py
```

O fluxo de inicialização:

1. `main.py` instancia `Game` de `src/game/game_main.py`
2. Aplica um patch leve no `InputManager` para cliques de mouse em menus
3. Chama `game.run()` — loop principal a 60 FPS (via `pygame.time.Clock`)

Na primeira execução, o menu principal oferece **Nova Partida**, **Continuar** e **Sair**.

---

## Save game

O progresso é salvo em:

```
src/savegame.json
```

- **Continuar** no menu principal carrega esse arquivo (se existir)
- **Salvar** no menu de pausa grava andar, HP/MP, level, XP, inventário e ouro
- A **Sala de Descanso** (andar 5) salva automaticamente ao entrar
- **Nova Partida** sobrescreve o save com valores iniciais

O arquivo `savegame.json` está no `.gitignore` — cada máquina mantém seu próprio progresso.

---

## Configurações visuais

Constantes globais em `src/config/constants.py`:

| Constante | Padrão | Descrição |
|-----------|--------|-----------|
| `SCREEN_W` | 1280 | Largura da janela |
| `SCREEN_H` | 720 | Altura da janela |
| `TITLE` | Re:Oblivion of Memories | Título da janela |

A janela é **redimensionável** (`RESIZABLE`). O viewport OpenGL é atualizado quando a janela muda de tamanho.

---

## Solução de problemas

### `ModuleNotFoundError: No module named 'pygame'`

O ambiente virtual não está ativo ou as dependências não foram instaladas:

```bash
pip install -r requirements.txt
```

### Tela preta ou erro de OpenGL

- Atualize os drivers da placa de vídeo
- Em máquinas sem GPU dedicada, verifique se o OpenGL 3.x está disponível
- No Linux, instale pacotes como `mesa-utils` e teste com `glxinfo`

### Modelos não aparecem / erro ao carregar GLB

Confirme que a pasta `src/assets/models/` está intacta. Os personagens dependem de arquivos `.glb` em subpastas (`Subaru/`, `Heartless/`, `Marluxia/`, etc.).

### Sem som

- Verifique volume do sistema e do mixer do Pygame
- O jogo usa `pygame.mixer` com até 32 canais; falhas silenciosas podem ocorrer se o dispositivo de áudio estiver indisponível

### "Nenhum save encontrado!" ao continuar

Normal na primeira execução. Inicie uma **Nova Partida** ou salve manualmente no menu de pausa (`Esc` → Salvar).

### Performance baixa

- Feche outros programas que usem GPU
- A resolução padrão é 720p; reduzir o tamanho da janela pode ajudar
- `PyOpenGL_accelerate` deve estar instalado para melhor desempenho

---

## Desenvolvimento

### Estrutura mínima para rodar

```
main.py
requirements.txt
src/
├── here.py              # Define _HERE = pasta src/
├── game/game_main.py    # Classe Game
├── engine/              # Motor 3D
├── config/              # paths.py, constants.py
└── assets/              # Obrigatório em runtime
```

### Ferramentas auxiliares

- `src/tools/generate_textures.py` — utilitário para gerar texturas procedurais (não necessário para jogar)

### Debug

- **F1** — alterna modo wireframe (malha em linhas) durante exploração

---

## Próximos passos

- [Controles do jogo](CONTROLES.md)
- [Conteúdo e andares](JOGO.md)
- [Arquitetura do código](ARQUITETURA.md)

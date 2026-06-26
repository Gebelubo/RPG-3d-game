# Conteúdo e gameplay

Descrição do universo, mecânicas, andares, personagens, magias e progressão de **Re:Oblivion of Memories**.

[← Voltar ao README principal](../README.md)

---

## Premissa

**Natsuki Subaru** ascende a **Torre Pleiades** em busca de respostas sobre memórias perdidas. A torre é habitada por **Heartless**, enigmas antigos e culmina no confronto com **Marluxia**, guardião do último andar. **Emilia** aparece na narrativa final; **Beatrice** e elementos de *Re:Zero* permeiam magias, itens e diálogos.

O título do jogo é **Re:Oblivion of Memories** — um crossover fan game entre *Re:Zero* e *Kingdom Hearts*.

---

## Objetivo do jogador

1. Subir os **7 andares** da torre (índices 0–6)
2. Completar o desafio de cada andar (combate, puzzle, minigame ou ondas)
3. Usar as **escadas** ao fundo da sala após liberar a **barreira mágica**
4. Derrotar **Marluxia** e assistir à **cutscene final** com Emilia

---

## Andares da torre

### Andar 0 — Entrada (`FLOOR_ENTRY`)

| Aspecto | Detalhe |
|---------|---------|
| Música | `tower.mp3` |
| Objetivo | Atravessar o corredor, abrir a porta e vencer o tutorial de combate |
| Mecânicas | Porta interativa, barreira que spawna Heartless, escadas bloqueadas até limpar |

**Fluxo:** Ao interagir (`E` / `Enter`) perto da porta no fundo, uma barreira aparece e três Heartless surgem. Derrote todos para destravar a subida. A história introdutória exibe a carta prologue (`prologue_letter.png`).

---

### Andar 1 — Puzzle (`FLOOR_PUZZLE`)

| Aspecto | Detalhe |
|---------|---------|
| Música | `puzzle.mp3` |
| Objetivo | Reunir **4 fragmentos** e montar o mural na parede norte |

**Fragmentos:**

| Peça | Localização |
|------|-------------|
| 0 | Sub-sala de **parkour** (portal na parede sul) |
| 1 | Plataforma elevada na sala principal |
| 2 | Sobre botão verde — exige **empurrar a caixa** até o botão e subir nela |
| 3 | Guardada por **Heartless** estacionários |

**Mecânicas extras:**

- **Caixa empurrável** — interaja com `Z` para empurrar; ative o botão verde
- **Sub-sala parkour** — plataformas sobre o void; cair = morte
- Cada fragmento coletado é encaixado no quadro com `Z` quando próximo

Ao completar o mural, a barreira cai e as escadas liberam o próximo andar.

---

### Andar 2 — Aerial (`FLOOR_AERIAL`)

| Aspecto | Detalhe |
|---------|---------|
| Música | `combat.mp3` |
| Objetivo | Eliminar Heartless terrestres e **voadores** |

Heartless voadores ficam elevados — use **pulo** (`Espaço`) para alcançá-los. Derrotar todos libera a barreira.

---

### Andar 3 — Ritmo (`FLOOR_RHYTHM`)

| Aspecto | Detalhe |
|---------|---------|
| Música | `rythm.mp3` (inicia ao ativar o obelisco) |
| Objetivo | Completar o **minigame rítmico** no obelisco central |

Interaja com o obelisco para entrar no modo `rhythm`. Notas caem em **4 faixas**; acerte com as setas do teclado. Classificações: Perfect, Good, Ok, Miss — com pontuação mínima para passar. `Esc` aborta o minigame.

---

### Andar 4 — Corredor / Gauntlet (`FLOOR_GAUNTLET`)

| Aspecto | Detalhe |
|---------|---------|
| Música | `combat.mp3` |
| Objetivo | Sobreviver a **2 ondas** de inimigos |

- **Onda 1:** 5 Heartless terrestres
- **Onda 2:** 2 terrestres + 3 voadores (aparecem após limpar a primeira)

Estética avermelhada reforça a dificuldade. Barreira só cai após eliminar todas as ondas.

---

### Andar 5 — Descanso (`FLOOR_REST`)

| Aspecto | Detalhe |
|---------|---------|
| Música | `tower.mp3` |
| Objetivo | Recuperar-se antes do boss |

Ao entrar:

- **HP e MP restaurados** ao máximo
- **Save automático**
- **Livro na mesa** — relatórios de Marluxia (`marluxia_report1.png` … `report6.png`) com lore
- Escadas e porta levam ao andar do boss

---

### Andar 6 — Boss (`FLOOR_BOSS`)

| Aspecto | Detalhe |
|---------|---------|
| Música | `boss.mp3` |
| Boss | **Marluxia** (`MarluxiaBoss`) |
| Cenário | Emilia deitada em sarcófago (animação `sleeping`) |

#### Fases de Marluxia

| Fase | Gatilho | Comportamento |
|------|---------|---------------|
| 1 | Início | Ataques normais, heavy, round, shoot |
| 2 | HP ≤ 50% | +25% velocidade de movimento |
| 2b | HP ≤ 60% | Cooldowns de ataque reduzidos |
| 3 | HP ≤ 20% | **Curse** — controles invertidos; prioriza shoot/groundmagic |
| 4 | HP ≤ 10% | **Invencível** ~15s + buracos negros periódicos |
| Enrage | HP = 1 | Sequência especial antes da morte definitiva |

**Ataques do boss:** normal, heavy (parryável), round (AOE), shoot (distância), groundmagic (buracos negros), taunt (cura), curse (debuff no player).

Após a vitória: cutscene da Emilia (`sleeping` → `waking` → `idle`), diálogos e **créditos**.

---

## Personagem jogável

### Natsuki Subaru

| Stat inicial | Valor |
|--------------|-------|
| HP | 200 / 200 |
| MP | 400 / 400 |
| ATK | 12 |
| DEF | 4 |
| SPD | 10 |
| Level | 1 |

**Inventário inicial:**

- 4× Amor de Emilia (poção de HP)
- 3× Confiança de Beatrice (poção de MP)
- 1× Agasalho do Subaru (armadura)

**Habilidades de movimento:**

- Caminhar / correr relativo à câmera
- Pulo (`Espaço`)
- Rolamento (`Shift` durante movimento) — i-frames
- Combo de ataques corpo a corpo (`Z`)

---

## Inimigos

### Heartless

Inimigo padrão de *Kingdom Hearts*. Versões terrestres e voadoras.

- Perseguem o player dentro do `aggro_range`
- **Ataque leve** — rápido, dano moderado
- **Ataque pesado** — wind-up telegrafado; janela de **parry** (`F`)

### AerialKnocker

Variante aérea com animações `BaseAttack` e `DownAttack`.

### Marluxia

Boss final com IA por fases — ver seção do andar 6.

---

## Magias

Abrir menu: **X** — selecionar com **1–4**

| ID | Nome | MP | Efeito |
|----|------|-----|--------|
| `shamac` | Shamac | 50 | Cega o inimigo por ~10s (perde aggro) |
| `minya` | Minya | 40 | 40 de dano dark |
| `invisible_providence` | Invisible Providence | 40 | 60 de dano light |
| `emt` | EMT | 100 | Escudo por ~10s (bloqueia ataques) |

Cada magia dispara animação e SFX específicos do Subaru quando aplicável.

---

## Itens

Abrir menu: **C** — consumir com **1–4**

| ID | Nome | Efeito |
|----|------|--------|
| `health_potion_s` | Amor de Emilia | +30 HP |
| `health_potion_l` | Amor de Emilia (grande) | +80 HP |
| `mana_potion` | Confiança de Beatrice | +40 MP |
| `iron_sword` | Iron Sword | +8 ATK (equipamento) |
| `tracksuit` | Agasalho do Subaru | +3 DEF (equipamento) |

---

## Sistema de progressão

- **XP** ganho ao derrotar inimigos (fórmula baseada no level do inimigo)
- **Level up** até level 5 — aumenta HP/MP máximos, ATK, DEF e SPD
- **Ouro** via inventário (uso limitado no gameplay atual)
- **Save** persiste: andar, stats, XP, inventário, ouro

---

## Combate em tempo real

| Ação | Input |
|------|-------|
| Ataque melee | `Z` |
| Parry | `F` (durante wind-up de ataque pesado) |
| Magias | `X` + `1–4` |
| Itens | `C` + `1–4` |
| Interagir | `E` ou `Enter` |

Mecânicas:

- **Combo** — ataques encadeados com janela de tempo
- **I-frames** — durante rolamento e após parry bem-sucedido
- **Invencibilidade breve** após tomar dano (reaction animation)
- Inimigos **cegos** por Shamac não aggroam

---

## Narrativa e modos especiais

| Modo | Descrição |
|------|-----------|
| `story` | Texto/imagem sequencial — prologue e ending |
| `book` | Relatórios de Marluxia na sala de descanso |
| `credits` | Rolagem final pós-vitória |

Diálogos pós-boss incluem falas da Emilia e referências emocionais ao loop de Subaru.

---

## Barreiras e escadas

Padrão em quase todos os andares:

1. **Escadas** no fundo (coordenada Z negativa) levam ao andar seguinte
2. **Barreira mágica** bloqueia as escadas até completar o objetivo do andar
3. **Porta** visual no extremo norte da sala
4. Transição entre andares usa **fade** curto (~0,35s)

---

## Dicas gerais

1. **Entrada:** aprenda parry no tutorial — essencial no boss
2. **Puzzle:** explore a sub-sala de parkour cedo; a peça 0 só existe lá
3. **Aerial:** pule para atingir Heartless voadores
4. **Ritmo:** pratique timing Perfect para pontuação máxima
5. **Gauntlet:** gerencie MP — use EMT antes das ondas difíceis
6. **Descanso:** leia os relatórios antes do boss
7. **Marluxia:** guarde MP para EMT nas fases 3–4; parry nos heavies

---

## Referências cruzadas

- [Controles detalhados](CONTROLES.md)
- [Como instalar e executar](COMO-RODAR.md)
- [Arquitetura técnica](ARQUITETURA.md)

from src.hud.hud import BRONZE_F, GOLD_DARK_F, GOLD_F, PARCHMENT_DK_F

CONTROLS_SECTIONS = [
    ("Movimento e Câmera", [
        ("W A S D", "Mover (relativo à câmera)"),
        ("Mouse", "Girar a câmera"),
        ("Espaço", "Pular"),
        ("Shift", "Rolar / esquiva com i-frames"),
    ]),
    ("Combate", [
        ("Z", "Ataque corpo a corpo (combo)"),
        ("F", "Parry — bloqueia ataques pesados"),
        ("X + 1–4", "Lançar magia"),
        ("C + 1–4", "Usar item consumível"),
    ]),
    ("Magias", [
        ("Shamac", "Cega inimigos (50 MP)"),
        ("Minya", "Dano sombrio (40 MP)"),
        ("Invisible Providence", "Dano elevado (40 MP)"),
        ("EMT", "Escudo protetor (100 MP)"),
    ]),
    ("Interação", [
        ("E / Enter", "Interagir — portas, obelisco, fragmentos"),
        ("V", "Abrir menu de skills"),
        ("Esc", "Pausar o jogo"),
    ]),
    ("Minigame Rítmico", [
        ("← ↓ ↑ →", "Acertar notas nas 4 faixas"),
        ("Esc", "Cancelar ritual"),
    ]),
    ("Menus", [
        ("↑ / ↓", "Navegar opções"),
        ("Enter", "Confirmar seleção"),
        ("Esc", "Voltar"),
    ]),
]


def draw_controls_screen(hud, sw: int, sh: int):
    pad_x = max(24, int(sw * 0.05))
    panel_w = min(sw - pad_x * 2, 920)
    panel_h = min(int(sh * 0.58), 520)
    px = (sw - panel_w) // 2
    py = int(sh * 0.14)

    hud.draw_frame(
        px, py, panel_w, panel_h,
        bg_color=PARCHMENT_DK_F,
        border_color=GOLD_F,
        border_dark=GOLD_DARK_F,
        thickness=3,
        gem_color=BRONZE_F,
    )

    hud.draw_banner(
        "Controles e Funcionalidades", px + panel_w / 2, py + 10,
        w=min(panel_w - 48, 520), h=30,
        base_color=(0.12, 0.10, 0.22),
        edge_color=(0.40, 0.28, 0.55),
        text_color=(235, 220, 255),
        text_size=16,
        notch=12,
    )

    col_w = (panel_w - 48) // 2
    left_x = px + 20
    right_x = px + 24 + col_w
    y_start = py + 56
    line_h = 17
    section_gap = 10
    header_h = 20

    mid = (len(CONTROLS_SECTIONS) + 1) // 2
    columns = (CONTROLS_SECTIONS[:mid], CONTROLS_SECTIONS[mid:])

    for col_idx, sections in enumerate(columns):
        x_key = left_x if col_idx == 0 else right_x
        x_desc = x_key + 118
        y = y_start

        for title, entries in sections:
            hud.draw_text(title, x_key, y, 15, (220, 185, 90), bold=True)
            y += header_h

            for key_label, desc in entries:
                hud.draw_text(key_label, x_key + 4, y, 13, (160, 210, 255))
                hud.draw_text(desc, x_desc, y, 13, (195, 195, 210))
                y += line_h

            y += section_gap

    hud.draw_text(
        "[ESC] ou [Enter] para voltar ao menu",
        sw // 2, py + panel_h - 18, 12, (150, 150, 170), center=True,
    )

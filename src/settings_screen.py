"""Tela de configurações de áudio (menu principal)."""

from src.config.audio_settings import AudioSettings
from src.hud.hud import BRONZE_F, GOLD_DARK_F, GOLD_F, PARCHMENT_DK_F, SAPPHIRE_F

SETTINGS_ROWS = (
    ("music", "Música"),
    ("sfx",   "Efeitos Sonoros"),
)


def draw_settings_screen(hud, sw: int, sh: int, audio: AudioSettings,
                         selected_row: int, anim_t: float = 0.0):
    panel_w = min(sw - 80, 520)
    panel_h = 280
    px = (sw - panel_w) // 2
    py = int(sh * 0.28)

    hud.draw_frame(
        px, py, panel_w, panel_h,
        bg_color=PARCHMENT_DK_F,
        border_color=GOLD_F,
        border_dark=GOLD_DARK_F,
        thickness=3,
        gem_color=BRONZE_F,
    )

    hud.draw_banner(
        "Configurações", px + panel_w / 2, py + 10,
        w=min(panel_w - 48, 320), h=30,
        base_color=(0.10, 0.14, 0.24),
        edge_color=(0.28, 0.38, 0.62),
        text_color=(235, 220, 255),
        text_size=17,
        notch=12,
    )

    bar_x = px + 36
    bar_w = panel_w - 72
    bar_h = 18
    row_start = py + 62
    row_step = 72

    volumes = (audio.music_volume, audio.sfx_volume)
    percents = (audio.music_percent(), audio.sfx_percent())

    for i, (key, label) in enumerate(SETTINGS_ROWS):
        row_y = row_start + i * row_step
        is_sel = i == selected_row
        vol = volumes[i]
        pct = percents[i]

        if is_sel:
            pulse = 0.45 + 0.10 * abs((anim_t * 2.5) % 2.0 - 1.0)
            hud.draw_rect(px + 20, row_y - 8, panel_w - 40, 58,
                          (0.18, 0.14, 0.32), alpha=pulse)
            hud.draw_rect(px + 20, row_y - 8, 3, 58, GOLD_F, alpha=0.95)

        label_col = (255, 245, 230) if is_sel else (200, 195, 215)
        hud.draw_text(label, bar_x, row_y, 16, label_col, bold=is_sel)

        # Trilha da barra
        track_y = row_y + 26
        hud.draw_rect(bar_x, track_y, bar_w, bar_h, (0.08, 0.07, 0.12), alpha=0.9)
        hud.draw_rect(bar_x, track_y, bar_w, 2, GOLD_DARK_F, alpha=0.6)
        hud.draw_rect(bar_x, track_y + bar_h - 2, bar_w, 2, GOLD_DARK_F, alpha=0.6)

        fill_w = max(0, int(bar_w * vol))
        if fill_w > 0:
            fill_col = (0.35, 0.55, 0.95) if key == "music" else (0.45, 0.75, 0.55)
            hud.draw_rect(bar_x, track_y, fill_w, bar_h, fill_col, alpha=0.95)
            hud.draw_rect(bar_x, track_y, fill_w, max(3, bar_h // 3),
                          (fill_col[0] + 0.15, fill_col[1] + 0.15, fill_col[2] + 0.15),
                          alpha=0.5)

        # Indicador
        knob_x = bar_x + int(bar_w * vol)
        knob_col = SAPPHIRE_F if key == "music" else (0.35, 0.72, 0.48)
        hud.draw_medallion(knob_x, track_y + bar_h // 2, 9, knob_col)

        hud.draw_text(f"{pct}%", bar_x + bar_w + 8, track_y + 1, 14,
                      (180, 200, 255) if is_sel else (150, 155, 175))

        if is_sel:
            hud.draw_text("", bar_x - 22, track_y + 1, 14, (255, 220, 140))
            hud.draw_text("", bar_x + bar_w + 42, track_y + 1, 14, (255, 220, 140))

    hud.draw_text(
        "↑ ↓ selecionar  ·  ← → ajustar  ·  Esc voltar",
        sw // 2, py + panel_h - 20, 12, (150, 150, 170), center=True,
    )

"""Generates the Open Graph preview image (1200x630) for the home page."""

import os

from PIL import Image, ImageDraw, ImageFont

WIDTH, HEIGHT = 1200, 630
BLUE = (29, 78, 216)
RED = (220, 38, 38)
WHITE = (255, 255, 255)
TEXT = (26, 26, 26)
MUTED = (102, 102, 102)
CARD_BG = (245, 245, 245)
CARD_BORDER = (220, 220, 220)

STRIPE_HEIGHT = 50
CHECK_SIZE = 25

FONT_CANDIDATES = {
    "bold": [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ],
    "regular": [
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ],
}


def _font(size, weight="regular"):
    for path in FONT_CANDIDATES[weight]:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _draw_checkered_stripe(draw, y, color):
    for col in range(0, WIDTH, CHECK_SIZE):
        for row_idx, row_y in enumerate(range(y, y + STRIPE_HEIGHT, CHECK_SIZE)):
            col_idx = col // CHECK_SIZE
            fill = color if (col_idx + row_idx) % 2 == 0 else WHITE
            draw.rectangle(
                [col, row_y, col + CHECK_SIZE, row_y + CHECK_SIZE],
                fill=fill,
            )


def _format_date_pt(date_str):
    months = [
        "janeiro", "fevereiro", "março", "abril", "maio", "junho",
        "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
    ]
    try:
        year, month, day = date_str.split("-")
        return f"{int(day)} de {months[int(month) - 1]} de {year}"
    except (ValueError, IndexError):
        return date_str


def _tied_names(players, key, take=2):
    if not players:
        return None, None
    top = players[0][key]
    tied = [p for p in players if p[key] == top]
    names = [p["name"] for p in tied]
    if len(names) > take:
        joined = ", ".join(names[:take]) + f" +{len(names) - take}"
    else:
        joined = ", ".join(names)
    return joined, top


def _draw_card(draw, x, y, w, h, title, name, value):
    draw.rounded_rectangle(
        [x, y, x + w, y + h],
        radius=12,
        fill=CARD_BG,
        outline=CARD_BORDER,
        width=2,
    )
    draw.text((x + 24, y + 18), title.upper(), font=_font(20, "bold"), fill=BLUE)
    if name:
        draw.text((x + 24, y + 56), name, font=_font(34, "bold"), fill=TEXT)
        draw.text((x + 24, y + 110), value, font=_font(22, "regular"), fill=MUTED)
    else:
        draw.text((x + 24, y + 70), "—", font=_font(34, "bold"), fill=MUTED)


def _highlights(pelada, stats):
    top_scorer_name, top_scorer_value = _tied_names(stats["top_scorers"]["players"], "goals")
    top_winner_name, top_winner_value = _tied_names(stats["victory_ranking"]["players"], "wins")
    top_mesa_name, top_mesa_value = _tied_names(stats["ficou_na_mesa"]["players"], "total")

    gk = stats["best_goalkeeper"]
    if gk:
        top_conceded = gk[0]["goals_conceded"]
        tied_gk = [g for g in gk if g["goals_conceded"] == top_conceded]
        gk_names = ", ".join(g["name"] for g in tied_gk[:2])
        if len(tied_gk) > 2:
            gk_names += f" +{len(tied_gk) - 2}"
        gk_conceded = top_conceded
    else:
        gk_names = None
        gk_conceded = None

    return [
        ("Artilheiro", top_scorer_name,
         f"{top_scorer_value} gol{'s' if top_scorer_value != 1 else ''}" if top_scorer_name else ""),
        ("Maior Vencedor", top_winner_name,
         f"{top_winner_value} vitória{'s' if top_winner_value != 1 else ''}" if top_winner_name else ""),
        ("Pega Tudo", gk_names,
         f"{gk_conceded} gol{'s' if gk_conceded != 1 else ''} tomado{'s' if gk_conceded != 1 else ''}" if gk_names else ""),
        ("Rei da Mesa", top_mesa_name,
         f"{top_mesa_value}x ficou na mesa" if top_mesa_name else ""),
    ]


def generate_preview(pelada, stats, output_path):
    img = Image.new("RGB", (WIDTH, HEIGHT), WHITE)
    draw = ImageDraw.Draw(img)

    _draw_checkered_stripe(draw, 0, BLUE)
    _draw_checkered_stripe(draw, HEIGHT - STRIPE_HEIGHT, RED)

    draw.text((60, 80), "Pelada de Domingo", font=_font(56, "bold"), fill=TEXT)
    draw.text((60, 150), f"Última pelada · {_format_date_pt(pelada.date)}",
              font=_font(28, "regular"), fill=MUTED)

    card_w, card_h = 520, 170
    gap_x, gap_y = 40, 30
    start_x = 60
    start_y = 230

    cards = _highlights(pelada, stats)
    for idx, (title, name, value) in enumerate(cards):
        col = idx % 2
        row = idx // 2
        x = start_x + col * (card_w + gap_x)
        y = start_y + row * (card_h + gap_y)
        _draw_card(draw, x, y, card_w, card_h, title, name, value)

    img.save(output_path, "PNG", optimize=True)

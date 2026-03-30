from datetime import date

from models import Game, Goal, Pelada, Player
from stats import (
    compute_aggregate_stats,
    compute_best_goalkeeper,
    compute_ficou_na_mesa,
    compute_top_scorers,
    compute_victory_ranking,
    filter_peladas,
)


def _player(name, role="player"):
    return Player(name=name, role=role)


def _gk(name):
    return Player(name=name, role="goalkeeper")


def _goal(player, team, count=1, own_goal=False):
    return Goal(player=player, team=team, count=count, own_goal=own_goal)


def _make_game(
    number,
    blue_score,
    red_score,
    team_out,
    blue_names,
    red_names,
    goals=None,
    blue_gk=None,
    red_gk=None,
):
    blue_team = [_gk(blue_gk or f"GK_B_{number}")] + [_player(n) for n in blue_names]
    red_team = [_gk(red_gk or f"GK_R_{number}")] + [_player(n) for n in red_names]
    return Game(
        game_number=number,
        score={"blue": blue_score, "red": red_score},
        team_out=team_out,
        blue_team=blue_team,
        red_team=red_team,
        goals=goals or [],
    )


# --- Victory ranking ---


def test_victory_ranking_basic():
    pelada = Pelada(
        date="2026-01-01",
        referee="Juiz",
        games=[
            _make_game(
                1,
                2,
                1,
                "red",
                ["A", "B", "C", "D", "E"],
                ["F", "G", "H", "I", "J"],
                blue_gk="GK1",
                red_gk="GK2",
            ),
            _make_game(
                2,
                0,
                3,
                "blue",
                ["A", "B", "C", "D", "E"],
                ["K", "L", "M", "N", "O"],
                blue_gk="GK1",
                red_gk="GK3",
            ),
        ],
    )
    ranking = compute_victory_ranking(pelada)
    names_with_wins = {r["name"]: r["wins"] for r in ranking}

    # Jogo 1: blue vence → GK1, A, B, C, D, E com 1 vitória cada
    # Jogo 2: red vence → GK3, K, L, M, N, O com 1 vitória cada
    assert names_with_wins["A"] == 1
    assert names_with_wins["K"] == 1
    assert "F" not in names_with_wins  # F perdeu o jogo 1, não jogou jogo 2


def test_victory_ranking_draw_no_winner():
    pelada = Pelada(
        date="2026-01-01",
        referee="Juiz",
        games=[
            _make_game(
                1,
                1,
                1,
                "both",
                ["A", "B", "C", "D", "E"],
                ["F", "G", "H", "I", "J"],
                blue_gk="GK1",
                red_gk="GK2",
            ),
        ],
    )
    ranking = compute_victory_ranking(pelada)
    assert ranking == []  # Empate, ninguém venceu


# --- Ficou na mesa ---


def test_ficou_na_mesa_jogo1_vitoria():
    """Vencer o jogo 1 conta como ficou na mesa."""
    pelada = Pelada(
        date="2026-01-01",
        referee="Juiz",
        games=[
            _make_game(
                1,
                3,
                0,
                "red",
                ["A", "B", "C", "D", "E"],
                ["F", "G", "H", "I", "J"],
                blue_gk="GK1",
                red_gk="GK2",
            ),
        ],
    )
    ranking = compute_ficou_na_mesa(pelada)
    names = {r["name"]: r for r in ranking}
    assert names["A"]["vitorias"] == 1
    assert names["GK1"]["vitorias"] == 1
    assert "F" not in names  # perdedor não conta


def test_ficou_na_mesa_jogo1_empate():
    """Empate no jogo 1 não conta como ficou na mesa."""
    pelada = Pelada(
        date="2026-01-01",
        referee="Juiz",
        games=[
            _make_game(
                1,
                1,
                1,
                "both",
                ["A", "B", "C", "D", "E"],
                ["F", "G", "H", "I", "J"],
                blue_gk="GK1",
                red_gk="GK2",
            ),
        ],
    )
    ranking = compute_ficou_na_mesa(pelada)
    assert ranking == []


def test_ficou_na_mesa_vitoria():
    """Incumbent vence jogo 2 → crédito de vitória."""
    pelada = Pelada(
        date="2026-01-01",
        referee="Juiz",
        games=[
            # Jogo 1: blue vence, red sai
            _make_game(
                1,
                2,
                0,
                "red",
                ["A", "B", "C", "D", "E"],
                ["F", "G", "H", "I", "J"],
                blue_gk="GK1",
                red_gk="GK2",
            ),
            # Jogo 2: blue (incumbent) vence de novo
            _make_game(
                2,
                1,
                0,
                "red",
                ["A", "B", "C", "D", "E"],
                ["K", "L", "M", "N", "O"],
                blue_gk="GK1",
                red_gk="GK3",
            ),
        ],
    )
    ranking = compute_ficou_na_mesa(pelada)
    names = {r["name"]: r for r in ranking}
    assert "A" in names
    assert names["A"]["vitorias"] == 2  # jogo 1 + jogo 2
    assert names["A"]["empates"] == 0
    assert "K" not in names  # K é do entering, que perdeu


def test_ficou_na_mesa_empate_ao_entrar():
    """Empate → entering fica → crédito de empate ao entrar."""
    pelada = Pelada(
        date="2026-01-01",
        referee="Juiz",
        games=[
            # Jogo 1: blue vence, red sai
            _make_game(
                1,
                2,
                0,
                "red",
                ["A", "B", "C", "D", "E"],
                ["F", "G", "H", "I", "J"],
                blue_gk="GK1",
                red_gk="GK2",
            ),
            # Jogo 2: empate, blue é incumbent, red (entering) fica
            _make_game(
                2,
                1,
                1,
                "blue",
                ["A", "B", "C", "D", "E"],
                ["K", "L", "M", "N", "O"],
                blue_gk="GK1",
                red_gk="GK3",
            ),
        ],
    )
    ranking = compute_ficou_na_mesa(pelada)
    names = {r["name"]: r for r in ranking}
    assert "K" in names
    assert names["K"]["empates"] == 1
    assert names["K"]["vitorias"] == 0
    # A ganhou jogo 1 (ficou na mesa), mas empatou jogo 2 como incumbent (não ganha crédito extra)
    assert names["A"]["vitorias"] == 1
    assert names["A"]["empates"] == 0


def test_ficou_na_mesa_both_out():
    """team_out=both → próximo jogo ninguém ganha crédito."""
    pelada = Pelada(
        date="2026-01-01",
        referee="Juiz",
        games=[
            # Jogo 1: empate, ambos saem
            _make_game(
                1,
                1,
                1,
                "both",
                ["A", "B", "C", "D", "E"],
                ["F", "G", "H", "I", "J"],
                blue_gk="GK1",
                red_gk="GK2",
            ),
            # Jogo 2: dois times novos, blue vence
            _make_game(
                2,
                3,
                0,
                "red",
                ["K", "L", "M", "N", "O"],
                ["P", "Q", "R", "S", "T"],
                blue_gk="GK3",
                red_gk="GK4",
            ),
        ],
    )
    ranking = compute_ficou_na_mesa(pelada)
    # Jogo 1 empatou → ninguém ganha crédito no jogo 1
    for item in [
        {"name": "K", "vitorias": 1, "empates": 0, "total": 1},
        {"name": "L", "vitorias": 1, "empates": 0, "total": 1},
        {"name": "GK3", "vitorias": 1, "empates": 0, "total": 1},
        {"name": "N", "vitorias": 1, "empates": 0, "total": 1},
        {"name": "O", "vitorias": 1, "empates": 0, "total": 1},
        {"name": "M", "vitorias": 1, "empates": 0, "total": 1},
    ]:
        assert item in ranking


def test_ficou_na_mesa_multiple_games():
    """Testar acumulação ao longo de 3 jogos."""
    pelada = Pelada(
        date="2026-01-01",
        referee="Juiz",
        games=[
            # Jogo 1: blue vence
            _make_game(
                1,
                2,
                0,
                "red",
                ["A", "B", "C", "D", "E"],
                ["F", "G", "H", "I", "J"],
                blue_gk="GK1",
                red_gk="GK2",
            ),
            # Jogo 2: blue (incumbent) vence → +1 vitória para blue
            _make_game(
                2,
                1,
                0,
                "red",
                ["A", "B", "C", "D", "E"],
                ["K", "L", "M", "N", "O"],
                blue_gk="GK1",
                red_gk="GK3",
            ),
            # Jogo 3: empate, blue incumbent, red entering fica → +1 empate para red
            _make_game(
                3,
                1,
                1,
                "blue",
                ["A", "B", "C", "D", "E"],
                ["P", "Q", "R", "S", "T"],
                blue_gk="GK1",
                red_gk="GK4",
            ),
        ],
    )
    ranking = compute_ficou_na_mesa(pelada)
    names = {r["name"]: r for r in ranking}
    assert names["A"]["vitorias"] == 2  # jogo 1 + jogo 2
    assert names["A"]["empates"] == 0
    assert names["P"]["empates"] == 1  # ficou na mesa no jogo 3 (empate ao entrar)
    assert names["P"]["vitorias"] == 0


# --- Top scorers ---


def test_top_scorers_basic():
    pelada = Pelada(
        date="2026-01-01",
        referee="Juiz",
        games=[
            _make_game(
                1,
                3,
                1,
                "red",
                ["A", "B", "C", "D", "E"],
                ["F", "G", "H", "I", "J"],
                goals=[
                    _goal("A", "blue", 2),
                    _goal("B", "blue", 1),
                    _goal("F", "red", 1),
                ],
                blue_gk="GK1",
                red_gk="GK2",
            ),
        ],
    )
    ranking = compute_top_scorers(pelada)
    assert ranking[0]["name"] == "A"
    assert ranking[0]["goals"] == 2


def test_top_scorers_exclui_gol_contra():
    pelada = Pelada(
        date="2026-01-01",
        referee="Juiz",
        games=[
            _make_game(
                1,
                2,
                1,
                "red",
                ["A", "B", "C", "D", "E"],
                ["F", "G", "H", "I", "J"],
                goals=[
                    _goal("A", "blue", 1),
                    _goal("F", "red", 1, own_goal=True),  # gol contra
                    _goal("G", "red", 1),
                ],
                blue_gk="GK1",
                red_gk="GK2",
            ),
        ],
    )
    ranking = compute_top_scorers(pelada)
    names = {r["name"]: r["goals"] for r in ranking}
    assert "F" not in names  # gol contra não entra
    assert names["A"] == 1
    assert names["G"] == 1


# --- Best goalkeeper ---


def test_best_goalkeeper():
    pelada = Pelada(
        date="2026-01-01",
        referee="Juiz",
        games=[
            _make_game(
                1,
                3,
                1,
                "red",
                ["A", "B", "C", "D", "E"],
                ["F", "G", "H", "I", "J"],
                blue_gk="GK1",
                red_gk="GK2",
            ),
            _make_game(
                2,
                0,
                2,
                "blue",
                ["A", "B", "C", "D", "E"],
                ["K", "L", "M", "N", "O"],
                blue_gk="GK1",
                red_gk="GK3",
            ),
        ],
    )
    ranking = compute_best_goalkeeper(pelada)
    gk_data = {r["name"]: r for r in ranking}

    # GK1 jogou 2 jogos: tomou 1 (jogo 1) + 2 (jogo 2) = 3
    assert gk_data["GK1"]["goals_conceded"] == 3
    assert gk_data["GK1"]["games_played"] == 2
    # GK2 jogou 1 jogo: tomou 3
    assert gk_data["GK2"]["goals_conceded"] == 3
    assert gk_data["GK2"]["games_played"] == 1
    # GK3 jogou 1 jogo: tomou 0
    assert gk_data["GK3"]["goals_conceded"] == 0
    assert gk_data["GK3"]["games_played"] == 1
    # GK3 deve ser o primeiro (menos vazado)
    assert ranking[0]["name"] == "GK3"


# --- Filter peladas ---


def test_filter_peladas_mensal():
    peladas = [
        Pelada(date="2026-03-01", referee="A", games=[]),
        Pelada(date="2026-03-15", referee="B", games=[]),
        Pelada(date="2026-02-20", referee="C", games=[]),
    ]
    filtered = filter_peladas(peladas, "mensal", reference_date=date(2026, 3, 15))
    assert len(filtered) == 2
    assert all(p.date.startswith("2026-03") for p in filtered)


def test_filter_peladas_anual():
    peladas = [
        Pelada(date="2026-03-01", referee="A", games=[]),
        Pelada(date="2025-12-01", referee="B", games=[]),
    ]
    filtered = filter_peladas(peladas, "anual", reference_date=date(2026, 3, 15))
    assert len(filtered) == 1
    assert filtered[0].date == "2026-03-01"


def test_filter_peladas_total():
    peladas = [
        Pelada(date="2026-03-01", referee="A", games=[]),
        Pelada(date="2025-01-01", referee="B", games=[]),
    ]
    filtered = filter_peladas(peladas, "total")
    assert len(filtered) == 2


# --- Aggregate stats ---


def test_aggregate_stats():
    pelada1 = Pelada(
        date="2026-03-01",
        referee="Seu Jorge",
        games=[
            _make_game(
                1,
                2,
                0,
                "red",
                ["A", "B", "C", "D", "E"],
                ["F", "G", "H", "I", "J"],
                goals=[_goal("A", "blue", 2)],
                blue_gk="GK1",
                red_gk="GK2",
            ),
        ],
    )
    pelada2 = Pelada(
        date="2026-03-08",
        referee="Seu Jorge",
        games=[
            _make_game(
                1,
                1,
                3,
                "blue",
                ["A", "B", "C", "D", "E"],
                ["F", "G", "H", "I", "J"],
                goals=[_goal("A", "blue", 1), _goal("F", "red", 3)],
                blue_gk="GK1",
                red_gk="GK2",
            ),
        ],
    )
    agg = compute_aggregate_stats([pelada1, pelada2])

    # Maior vencedor (jogadores de linha): A tem 1 vitória (pelada1), F tem 1 (pelada2)
    wins = {r["name"]: r["wins"] for r in agg["maior_vencedor"]["players"]}
    assert wins["A"] == 1
    assert wins["F"] == 1

    # Maior vencedor (goleiros)
    gk_wins = {r["name"]: r["wins"] for r in agg["maior_vencedor"]["goalkeepers"]}
    assert gk_wins["GK1"] == 1
    assert gk_wins["GK2"] == 1

    # Goleador (jogadores de linha): A tem 3 gols total, F tem 3
    goals = {r["name"]: r["goals"] for r in agg["goleador"]["players"]}
    assert goals["A"] == 3
    assert goals["F"] == 3

    # Fominha (jogadores de linha): A jogou 2 jogos, F jogou 2 jogos
    participation = {r["name"]: r["games"] for r in agg["fominha"]["players"]}
    assert participation["A"] == 2
    assert participation["F"] == 2

    # Fominha (goleiros)
    gk_participation = {r["name"]: r["games"] for r in agg["fominha"]["goalkeepers"]}
    assert gk_participation["GK1"] == 2

    # Apitador: Seu Jorge apitou 2 peladas
    refs = {r["name"]: r["peladas"] for r in agg["apitador"]}
    assert refs["Seu Jorge"] == 2


def test_fominha_counts_all_games():
    pelada = Pelada(
        date="2026-01-01",
        referee="Juiz",
        games=[
            _make_game(
                1,
                1,
                0,
                "red",
                ["A", "B", "C", "D", "E"],
                ["F", "G", "H", "I", "J"],
                blue_gk="GK1",
                red_gk="GK2",
            ),
            _make_game(
                2,
                0,
                1,
                "blue",
                ["A", "B", "C", "D", "E"],
                ["K", "L", "M", "N", "O"],
                blue_gk="GK1",
                red_gk="GK3",
            ),
        ],
    )
    agg = compute_aggregate_stats([pelada])
    participation = {r["name"]: r["games"] for r in agg["fominha"]["players"]}
    assert participation["A"] == 2  # jogou nos 2 jogos
    assert participation["F"] == 1  # jogou só no jogo 1
    assert participation["K"] == 1  # jogou só no jogo 2
    gk_participation = {r["name"]: r["games"] for r in agg["fominha"]["goalkeepers"]}
    assert gk_participation["GK1"] == 2

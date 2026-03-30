from collections import defaultdict
from datetime import date

from models import Game, Pelada


def _build_role_map(pelada: Pelada) -> dict[str, str]:
    """Build a name -> role map from all games in a pelada."""
    roles = {}
    for game in pelada.games:
        for p in game.blue_team + game.red_team:
            roles[p.name] = p.role
    return roles


def _build_role_map_multi(peladas: list[Pelada]) -> dict[str, str]:
    """Build a name -> role map from multiple peladas (last seen role wins)."""
    roles = {}
    for pelada in peladas:
        roles.update(_build_role_map(pelada))
    return roles


def _split_by_role(ranking: list[dict], role_map: dict[str, str]) -> dict:
    """Split a ranking list into players and goalkeepers."""
    players = [r for r in ranking if role_map.get(r["name"]) == "player"]
    goalkeepers = [r for r in ranking if role_map.get(r["name"]) == "goalkeeper"]
    return {"players": players, "goalkeepers": goalkeepers}


def _opposite_side(side: str) -> str:
    return "red" if side == "blue" else "blue"


def _get_team_names(game: Game, side: str) -> set[str]:
    team = game.blue_team if side == "blue" else game.red_team
    return {p.name for p in team}


def _get_team_players(game: Game, side: str):
    return game.blue_team if side == "blue" else game.red_team


def _get_score(game: Game, side: str) -> int:
    return game.score[side]


def _winner_side(game: Game) -> str | None:
    if game.score["blue"] > game.score["red"]:
        return "blue"
    elif game.score["red"] > game.score["blue"]:
        return "red"
    return None


def compute_victory_ranking(pelada: Pelada) -> list[dict]:
    wins = defaultdict(int)
    for game in pelada.games:
        winner = _winner_side(game)
        if winner:
            for p in _get_team_players(game, winner):
                wins[p.name] += 1
    ranking = [{"name": name, "wins": count} for name, count in wins.items()]
    ranking.sort(key=lambda x: x["wins"], reverse=True)
    return ranking


def compute_ficou_na_mesa(pelada: Pelada) -> list[dict]:
    vitorias = defaultdict(int)
    empates = defaultdict(int)

    for game in pelada.games:
        if game.team_out == "both":
            continue
        team_stayed = "blue" if game.team_out == "red" else "red"
        players_stayed = game.blue_team if team_stayed == "blue" else game.red_team
        if _winner_side(game) is not None:
            for player in players_stayed:
                vitorias[player.name] += 1
        else:
            for player in players_stayed:
                empates[player.name] += 1

    all_names = set(vitorias.keys()) | set(empates.keys())
    ranking = [
        {
            "name": name,
            "vitorias": vitorias[name],
            "empates": empates[name],
            "total": vitorias[name] + empates[name],
        }
        for name in all_names
    ]
    ranking.sort(key=lambda x: x["total"], reverse=True)
    return ranking


def compute_top_scorers(pelada: Pelada) -> list[dict]:
    goals = defaultdict(int)
    for game in pelada.games:
        for goal in game.goals:
            if not goal.own_goal:
                goals[goal.player] += goal.count
    ranking = [{"name": name, "goals": count} for name, count in goals.items()]
    ranking.sort(key=lambda x: x["goals"], reverse=True)
    return ranking


def compute_best_goalkeeper(pelada: Pelada) -> list[dict]:
    conceded = defaultdict(int)
    games_played = defaultdict(int)

    for game in pelada.games:
        for side in ("blue", "red"):
            for p in _get_team_players(game, side):
                if p.role == "goalkeeper":
                    opposing_side = _opposite_side(side)
                    conceded[p.name] += _get_score(game, opposing_side)
                    games_played[p.name] += 1

    ranking = [
        {
            "name": name,
            "goals_conceded": conceded[name],
            "games_played": games_played[name],
        }
        for name in conceded
    ]
    ranking.sort(key=lambda x: x["goals_conceded"])
    return ranking


def compute_fominha(pelada: Pelada) -> list[dict]:
    participation = defaultdict(int)
    for game in pelada.games:
        for p in game.blue_team + game.red_team:
            participation[p.name] += 1
    ranking = [{"name": n, "games": g} for n, g in participation.items()]
    ranking.sort(key=lambda x: x["games"], reverse=True)
    return ranking


def compute_game_details(pelada: Pelada) -> list[dict]:
    details = []
    for game in pelada.games:
        details.append(
            {
                "game_number": game.game_number,
                "score": game.score,
                "team_out": game.team_out,
                "blue_team": [{"name": p.name, "role": p.role} for p in game.blue_team],
                "red_team": [{"name": p.name, "role": p.role} for p in game.red_team],
                "goals": [
                    {
                        "player": g.player,
                        "team": g.team,
                        "count": g.count,
                        "own_goal": g.own_goal,
                    }
                    for g in game.goals
                ],
            }
        )
    return details


def compute_pelada_stats(pelada: Pelada) -> dict:
    role_map = _build_role_map(pelada)
    victory = compute_victory_ranking(pelada)
    mesa = compute_ficou_na_mesa(pelada)
    scorers = compute_top_scorers(pelada)
    fominha = compute_fominha(pelada)
    return {
        "victory_ranking": _split_by_role(victory, role_map),
        "ficou_na_mesa": _split_by_role(mesa, role_map),
        "top_scorers": _split_by_role(scorers, role_map),
        "best_goalkeeper": compute_best_goalkeeper(pelada),
        "fominha": _split_by_role(fominha, role_map),
        "game_details": compute_game_details(pelada),
    }


# --- Aggregate stats ---


def filter_peladas(
    peladas: list[Pelada], period: str, reference_date: date | None = None
) -> list[Pelada]:
    if period == "total":
        return peladas

    ref = reference_date or date.today()

    if period == "mensal":
        return [p for p in peladas if p.date[:7] == f"{ref.year:04d}-{ref.month:02d}"]
    elif period == "anual":
        return [p for p in peladas if p.date[:4] == f"{ref.year:04d}"]

    return peladas


def compute_aggregate_stats(peladas: list[Pelada]) -> dict:
    total_wins = defaultdict(int)
    total_mesa_vitorias = defaultdict(int)
    total_mesa_empates = defaultdict(int)
    total_goals = defaultdict(int)
    total_conceded = defaultdict(int)
    total_gk_games = defaultdict(int)
    total_participation = defaultdict(int)
    total_referee = defaultdict(int)

    for pelada in peladas:
        # Vitórias
        for entry in compute_victory_ranking(pelada):
            total_wins[entry["name"]] += entry["wins"]

        # Ficou na mesa
        for entry in compute_ficou_na_mesa(pelada):
            total_mesa_vitorias[entry["name"]] += entry["vitorias"]
            total_mesa_empates[entry["name"]] += entry["empates"]

        # Artilharia
        for entry in compute_top_scorers(pelada):
            total_goals[entry["name"]] += entry["goals"]

        # Goleiro
        for entry in compute_best_goalkeeper(pelada):
            total_conceded[entry["name"]] += entry["goals_conceded"]
            total_gk_games[entry["name"]] += entry["games_played"]

        # Participação
        for game in pelada.games:
            for p in game.blue_team + game.red_team:
                total_participation[p.name] += 1

        # Juíz
        total_referee[pelada.referee] += 1

    maior_vencedor = sorted(
        [{"name": n, "wins": w} for n, w in total_wins.items()],
        key=lambda x: x["wins"],
        reverse=True,
    )

    all_mesa = set(total_mesa_vitorias.keys()) | set(total_mesa_empates.keys())
    rei_da_mesa = sorted(
        [
            {
                "name": n,
                "vitorias": total_mesa_vitorias[n],
                "empates": total_mesa_empates[n],
                "total": total_mesa_vitorias[n] + total_mesa_empates[n],
            }
            for n in all_mesa
        ],
        key=lambda x: x["total"],
        reverse=True,
    )

    goleador = sorted(
        [{"name": n, "goals": g} for n, g in total_goals.items()],
        key=lambda x: x["goals"],
        reverse=True,
    )

    pega_tudo = sorted(
        [
            {
                "name": n,
                "goals_conceded": total_conceded[n],
                "games_played": total_gk_games[n],
            }
            for n in total_conceded
        ],
        key=lambda x: x["goals_conceded"],
    )

    fominha = sorted(
        [{"name": n, "games": g} for n, g in total_participation.items()],
        key=lambda x: x["games"],
        reverse=True,
    )

    apitador = sorted(
        [{"name": n, "peladas": p} for n, p in total_referee.items()],
        key=lambda x: x["peladas"],
        reverse=True,
    )

    role_map = _build_role_map_multi(peladas)

    return {
        "maior_vencedor": _split_by_role(maior_vencedor, role_map),
        "rei_da_mesa": _split_by_role(rei_da_mesa, role_map),
        "goleador": _split_by_role(goleador, role_map),
        "pega_tudo": pega_tudo,
        "fominha": _split_by_role(fominha, role_map),
        "apitador": apitador,
    }

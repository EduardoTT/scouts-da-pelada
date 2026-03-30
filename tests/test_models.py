import json
import os
import tempfile

from models import load_pelada, load_all_peladas


def _write_json(data: dict, path: str):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f)


def _make_pelada_data(**overrides):
    base = {
        "date": "2026-01-01",
        "referee": "Juiz",
        "games": [
            {
                "game_number": 1,
                "score": {"blue": 1, "red": 0},
                "team_out": "red",
                "blue_team": [
                    {"name": "A", "role": "goalkeeper"},
                    {"name": "B", "role": "player"},
                    {"name": "C", "role": "player"},
                    {"name": "D", "role": "player"},
                    {"name": "E", "role": "player"},
                    {"name": "F", "role": "player"},
                ],
                "red_team": [
                    {"name": "G", "role": "goalkeeper"},
                    {"name": "H", "role": "player"},
                    {"name": "I", "role": "player"},
                    {"name": "J", "role": "player"},
                    {"name": "K", "role": "player"},
                    {"name": "L", "role": "player"},
                ],
                "goals": [{"player": "B", "team": "blue", "count": 1}],
            }
        ],
    }
    base.update(overrides)
    return base


def test_load_pelada_basic():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(_make_pelada_data(), f)
        path = f.name

    try:
        pelada = load_pelada(path)
        assert pelada.date == "2026-01-01"
        assert pelada.referee == "Juiz"
        assert len(pelada.games) == 1
        assert pelada.games[0].game_number == 1
        assert pelada.games[0].score == {"blue": 1, "red": 0}
        assert pelada.games[0].team_out == "red"
        assert len(pelada.games[0].blue_team) == 6
        assert len(pelada.games[0].red_team) == 6
        assert pelada.games[0].blue_team[0].role == "goalkeeper"
        assert len(pelada.games[0].goals) == 1
        assert pelada.games[0].goals[0].player == "B"
        assert pelada.games[0].goals[0].own_goal is False
    finally:
        os.unlink(path)


def test_load_pelada_own_goal():
    data = _make_pelada_data()
    data["games"][0]["goals"].append(
        {"player": "H", "team": "red", "count": 1, "own_goal": True}
    )

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(data, f)
        path = f.name

    try:
        pelada = load_pelada(path)
        own_goals = [g for g in pelada.games[0].goals if g.own_goal]
        assert len(own_goals) == 1
        assert own_goals[0].player == "H"
    finally:
        os.unlink(path)


def test_load_pelada_team_out_both():
    data = _make_pelada_data()
    data["games"][0]["score"] = {"blue": 1, "red": 1}
    data["games"][0]["team_out"] = "both"

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(data, f)
        path = f.name

    try:
        pelada = load_pelada(path)
        assert pelada.games[0].team_out == "both"
    finally:
        os.unlink(path)


def test_load_all_peladas():
    with tempfile.TemporaryDirectory() as tmpdir:
        _write_json(_make_pelada_data(date="2026-01-01"), os.path.join(tmpdir, "2026-01-01.json"))
        _write_json(_make_pelada_data(date="2026-01-08"), os.path.join(tmpdir, "2026-01-08.json"))

        peladas = load_all_peladas(tmpdir)
        assert len(peladas) == 2
        assert peladas[0].date == "2026-01-01"
        assert peladas[1].date == "2026-01-08"

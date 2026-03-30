from dataclasses import dataclass, field
import json
import glob
import os


@dataclass
class Goal:
    player: str
    team: str  # "blue" | "red"
    count: int
    own_goal: bool = False


@dataclass
class Player:
    name: str
    role: str  # "goalkeeper" | "player"


@dataclass
class Game:
    game_number: int
    score: dict  # {"blue": int, "red": int}
    team_out: str  # "blue" | "red" | "both"
    blue_team: list[Player]
    red_team: list[Player]
    goals: list[Goal]


@dataclass
class Pelada:
    date: str
    referee: str
    games: list[Game]


def load_pelada(filepath: str) -> Pelada:
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    games = []
    for g in data["games"]:
        blue_team = [Player(name=p["name"], role=p["role"]) for p in g["blue_team"]]
        red_team = [Player(name=p["name"], role=p["role"]) for p in g["red_team"]]
        goals = [
            Goal(
                player=gl["player"],
                team=gl["team"],
                count=gl["count"],
                own_goal=gl.get("own_goal", False),
            )
            for gl in g.get("goals", [])
        ]
        games.append(
            Game(
                game_number=g["game_number"],
                score=g["score"],
                team_out=g["team_out"],
                blue_team=blue_team,
                red_team=red_team,
                goals=goals,
            )
        )

    return Pelada(date=data["date"], referee=data["referee"], games=games)


def load_all_peladas(directory: str) -> list[Pelada]:
    peladas = []
    for filepath in sorted(glob.glob(os.path.join(directory, "*.json"))):
        peladas.append(load_pelada(filepath))
    return peladas

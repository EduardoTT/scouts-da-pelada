"""Cadastro de jogadores.

Os dados ficam em players.json: a chave é o nome principal do jogador (o que
vai nos JSONs de data/) e o valor é a lista de apelidos que aparecem nas
anotações. Este módulo só lê e grava o arquivo, para que nenhum cadastro de
jogador precise editar código Python.
"""

import json
import os

PLAYERS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "players.json")


def load_players(path: str = PLAYERS_FILE) -> dict[str, list[str]]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_players(data: dict[str, list[str]], path: str = PLAYERS_FILE) -> None:
    """Grava um jogador por linha, para o diff de cada cadastro ficar legível."""
    lines = [
        f"  {json.dumps(name, ensure_ascii=False)}: {json.dumps(aliases, ensure_ascii=False)}"
        for name, aliases in data.items()
    ]
    with open(path, "w", encoding="utf-8") as f:
        f.write("{\n" + ",\n".join(lines) + "\n}\n")


players = load_players()

"""Validação dos arquivos reais em data/ contra o cadastro do players.py.

Erros de digitação em nome de jogador não quebram o build: eles viram um
jogador novo e silenciosamente dividem as estatísticas em duas linhas.
Estes testes pegam isso na hora do cadastro da pelada.
"""

import glob
import json
import os

from players import players

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")

CANONICAL = set(players)
ALIAS_TO_KEY = {alias: key for key, aliases in players.items() for alias in aliases}


def _data_files():
    return sorted(glob.glob(os.path.join(DATA_DIR, "*.json")))


def _names_in_game(game: dict):
    """Todo nome de jogador citado num jogo: escalações e gols."""
    for p in game["blue_team"] + game["red_team"]:
        yield p["name"]
    for goal in game.get("goals", []):
        yield goal["player"]


def test_data_dir_nao_esta_vazio():
    """Se o glob quebrar, os testes abaixo passariam sem checar nada."""
    assert _data_files(), f"nenhum JSON encontrado em {DATA_DIR}"


def test_nomes_usam_as_chaves_canonicas_do_players():
    """Nomes no data/ têm que ser a chave do dicionário, nunca um apelido.

    Gravar "Júnior" (apelido) em vez de "Junior" (chave) faz o jogador
    aparecer duas vezes nos rankings agregados.
    """
    offenders = {}
    for filepath in _data_files():
        with open(filepath, encoding="utf-8") as f:
            pelada = json.load(f)
        for game in pelada["games"]:
            for name in _names_in_game(game):
                if name in CANONICAL:
                    continue
                sugestao = ALIAS_TO_KEY.get(name)
                motivo = (
                    f"apelido de {sugestao!r}"
                    if sugestao
                    else "não existe no players.py"
                )
                offenders.setdefault(
                    (name, motivo), set()
                ).add(os.path.basename(filepath))

    assert not offenders, "nomes fora do cadastro do players.py:\n" + "\n".join(
        f"  {name!r} ({motivo}) em {sorted(arquivos)}"
        for (name, motivo), arquivos in sorted(offenders.items())
    )


def test_artilheiros_estao_escalados_no_time_que_marcou():
    """Um gol atribuído a quem não está no time indica nome trocado."""
    offenders = []
    for filepath in _data_files():
        with open(filepath, encoding="utf-8") as f:
            pelada = json.load(f)
        for game in pelada["games"]:
            times = {
                "blue": {p["name"] for p in game["blue_team"]},
                "red": {p["name"] for p in game["red_team"]},
            }
            for goal in game.get("goals", []):
                if goal["player"] not in times[goal["team"]]:
                    offenders.append(
                        f"  {os.path.basename(filepath)} jogo {game['game_number']}: "
                        f"{goal['player']!r} marcou pelo {goal['team']} mas não está escalado"
                    )

    assert not offenders, "gols de jogadores fora do time:\n" + "\n".join(offenders)


def test_placar_bate_com_a_soma_dos_gols():
    offenders = []
    for filepath in _data_files():
        with open(filepath, encoding="utf-8") as f:
            pelada = json.load(f)
        for game in pelada["games"]:
            for side in ("blue", "red"):
                marcados = sum(
                    g["count"] for g in game.get("goals", []) if g["team"] == side
                )
                if marcados != game["score"][side]:
                    offenders.append(
                        f"  {os.path.basename(filepath)} jogo {game['game_number']} "
                        f"({side}): placar {game['score'][side]}, gols somam {marcados}"
                    )

    assert not offenders, "placar diverge dos gols:\n" + "\n".join(offenders)


def test_cada_time_tem_exatamente_um_goleiro():
    offenders = []
    for filepath in _data_files():
        with open(filepath, encoding="utf-8") as f:
            pelada = json.load(f)
        for game in pelada["games"]:
            for side in ("blue_team", "red_team"):
                goleiros = [p for p in game[side] if p["role"] == "goalkeeper"]
                if len(goleiros) != 1:
                    offenders.append(
                        f"  {os.path.basename(filepath)} jogo {game['game_number']} "
                        f"({side}): {len(goleiros)} goleiros"
                    )

    assert not offenders, "times sem exatamente 1 goleiro:\n" + "\n".join(offenders)

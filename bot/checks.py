"""Verificações do rascunho que vão além de tests/test_data.py.

Erros bloqueiam a publicação. Avisos viram perguntas ao organizador, que pode
confirmar que está certo.
"""

from dataclasses import dataclass, field
from datetime import date

TIMES = ("blue", "red")
TEAM_OUT = ("blue", "red", "both")
NOME_TIME = {"blue": "azul", "red": "vermelho", "both": "os dois"}


@dataclass
class Resultado:
    erros: list[str] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.erros


def _estrutura(dados) -> list[str]:
    """Erros de formato. Se houver algum, as outras verificações não rodam."""
    if not isinstance(dados, dict):
        return ["O arquivo não é um objeto JSON."]
    erros = [f'Falta o campo "{k}".' for k in ("date", "referee", "games") if k not in dados]
    if not isinstance(dados.get("games", []), list) or not dados.get("games"):
        erros.append("A pelada precisa ter pelo menos um jogo em \"games\".")
        return erros
    for i, jogo in enumerate(dados["games"], 1):
        if not isinstance(jogo, dict):
            erros.append(f"O jogo na posição {i} não é um objeto.")
            continue
        for k in ("game_number", "score", "team_out", "blue_team", "red_team", "goals"):
            if k not in jogo:
                erros.append(f'Jogo na posição {i}: falta o campo "{k}".')
        placar = jogo.get("score", {})
        if not (isinstance(placar, dict) and all(isinstance(placar.get(t), int) for t in TIMES)):
            erros.append(f"Jogo na posição {i}: o placar precisa ter \"blue\" e \"red\" inteiros.")
        for t in TIMES:
            for p in jogo.get(f"{t}_team", []):
                if not (isinstance(p, dict) and p.get("name") and p.get("role") in ("goalkeeper", "player")):
                    erros.append(f"Jogo na posição {i}: jogador mal formado no time {NOME_TIME[t]}: {p!r}.")
        for g in jogo.get("goals", []):
            if not (isinstance(g, dict) and g.get("player") and g.get("team") in TIMES
                    and isinstance(g.get("count"), int) and g["count"] > 0):
                erros.append(f"Jogo na posição {i}: gol mal formado: {g!r}.")
    return erros


def _nomes(time: list[dict]) -> set[str]:
    return {p["name"] for p in time}


def verificar(dados, nome_arquivo: str, datas_publicadas: set[str], nova: bool) -> Resultado:
    """nome_arquivo é a data do arquivo (AAAA-MM-DD); nova indica cadastro (e não correção)."""
    r = Resultado(erros=_estrutura(dados))
    if r.erros:
        return r

    try:
        date.fromisoformat(dados["date"])
    except (TypeError, ValueError):
        r.erros.append(f'A data "{dados["date"]}" não está no formato AAAA-MM-DD.')
    if dados["date"] != nome_arquivo:
        r.erros.append(f'O campo "date" ({dados["date"]}) não bate com o nome do arquivo ({nome_arquivo}.json).')
    if nova and nome_arquivo in datas_publicadas:
        r.erros.append(f"Já existe uma pelada publicada em {nome_arquivo}. Isso deveria ser uma correção.")

    jogos = dados["games"]
    numeros = [j["game_number"] for j in jogos]
    if numeros != list(range(1, len(jogos) + 1)):
        r.erros.append(f"Os jogos precisam estar numerados em sequência a partir de 1. Hoje estão: {numeros}.")

    for jogo in jogos:
        n = jogo["game_number"]
        azul, vermelho = jogo["score"]["blue"], jogo["score"]["red"]
        saiu = jogo["team_out"]
        if saiu not in TEAM_OUT:
            r.erros.append(f'Jogo {n}: "team_out" precisa ser "blue", "red" ou "both", não {saiu!r}.')
            continue
        if azul != vermelho:
            perdedor = "red" if azul > vermelho else "blue"
            if saiu != perdedor:
                r.erros.append(
                    f"Jogo {n}: o {NOME_TIME[perdedor]} perdeu ({azul} x {vermelho}), "
                    f"mas o registro diz que saiu {NOME_TIME[saiu]}."
                )
        elif n == 1 and saiu == "both":
            r.erros.append("Jogo 1: empate no primeiro jogo vai para os pênaltis, então só um time sai.")

        for t in TIMES:
            # Já houve times com 5 e com 7 nas peladas publicadas, então não é erro.
            tamanho = len(jogo[f"{t}_team"])
            if tamanho != 6:
                r.avisos.append(f"Jogo {n}: o time {NOME_TIME[t]} tem {tamanho} jogadores (o normal é 6).")
        repetidos = _nomes(jogo["blue_team"]) & _nomes(jogo["red_team"])
        if repetidos:
            r.erros.append(f"Jogo {n}: {', '.join(sorted(repetidos))} aparece nos dois times.")

    for anterior, seguinte in zip(jogos, jogos[1:]):
        saiu = anterior["team_out"]
        if saiu not in ("blue", "red"):
            continue
        time_que_saiu = _nomes(anterior[f"{saiu}_team"])
        for t in TIMES:
            if _nomes(seguinte[f"{t}_team"]) == time_que_saiu:
                r.avisos.append(
                    f"Jogo {seguinte['game_number']}: o time {NOME_TIME[t]} é exatamente o time que saiu "
                    f"no jogo {anterior['game_number']}. Confirme se eles voltaram mesmo ou se o "
                    f"\"team_out\" do jogo {anterior['game_number']} está errado."
                )
    return r

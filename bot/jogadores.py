"""Leitura, busca e gravação do players.json de um worktree.

O formato de gravação é o mesmo do players.save_players da raiz do repo (um
jogador por linha). O teste test_jogadores garante que os dois continuam
iguais.
"""

import difflib
import json
import unicodedata
from pathlib import Path


def normaliza(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return " ".join(sem_acento.lower().split())


def carrega(path: Path) -> dict[str, list[str]]:
    return json.loads(path.read_text(encoding="utf-8"))


def grava(path: Path, dados: dict[str, list[str]]) -> None:
    linhas = [
        f"  {json.dumps(nome, ensure_ascii=False)}: {json.dumps(apelidos, ensure_ascii=False)}"
        for nome, apelidos in dados.items()
    ]
    path.write_text("{\n" + ",\n".join(linhas) + "\n}\n", encoding="utf-8")


def dono_do_nome(dados: dict[str, list[str]], texto: str) -> list[str]:
    """Jogadores cujo nome principal ou algum apelido é igual ao texto (sem acento e caixa)."""
    alvo = normaliza(texto)
    return [nome for nome, apelidos in dados.items() if alvo in {normaliza(a) for a in [nome, *apelidos]}]


def busca(dados: dict[str, list[str]], texto: str, limite: int = 8) -> list[tuple[str, str, float]]:
    """(nome principal, grafia que bateu, semelhança de 0 a 1), da mais parecida para a menos."""
    alvo = normaliza(texto)
    achados: dict[str, tuple[str, float]] = {}
    for nome, apelidos in dados.items():
        for grafia in [nome, *apelidos]:
            g = normaliza(grafia)
            nota = difflib.SequenceMatcher(None, alvo, g).ratio()
            if alvo and (alvo in g.split() or g in alvo.split()):
                nota = max(nota, 0.8)
            if alvo == g:
                nota = 1.0
            if nota >= 0.6 and nota > achados.get(nome, ("", 0.0))[1]:
                achados[nome] = (grafia, nota)
    ordenado = sorted(achados.items(), key=lambda kv: -kv[1][1])[:limite]
    return [(nome, grafia, round(nota, 2)) for nome, (grafia, nota) in ordenado]

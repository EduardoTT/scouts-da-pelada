"""Resumo legível da pelada, gerado a partir do JSON.

O organizador confirma este texto, e não um texto escrito pelo modelo, para
que o que ele aprova seja exatamente o que vai ser publicado.
"""

from datetime import date

DIAS = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]
NOME_TIME = {"blue": "Azul", "red": "Vermelho", "both": "os dois"}
LIMITE_TELEGRAM = 4000


def _data(iso: str) -> str:
    d = date.fromisoformat(iso)
    return f"{d.day:02d}/{d.month:02d}/{d.year} ({DIAS[d.weekday()]})"


def _time(jogadores: list[dict]) -> str:
    return ", ".join(p["name"] + (" (gol)" if p["role"] == "goalkeeper" else "") for p in jogadores)


def _gols(jogo: dict) -> str:
    partes = []
    for g in jogo["goals"]:
        qtd = f" {g['count']}" if g["count"] > 1 else ""
        if g.get("own_goal"):
            partes.append(f"{g['player']}{qtd} (contra, a favor do {NOME_TIME[g['team']].lower()})")
        else:
            partes.append(f"{g['player']}{qtd} ({NOME_TIME[g['team']].lower()})")
    return ", ".join(partes) if partes else "nenhum"


def _jogo(jogo: dict) -> str:
    s = jogo["score"]
    return "\n".join([
        f"Jogo {jogo['game_number']}: Azul {s['blue']} x {s['red']} Vermelho. Saiu: {NOME_TIME[jogo['team_out']].lower()}.",
        f"Azul: {_time(jogo['blue_team'])}",
        f"Vermelho: {_time(jogo['red_team'])}",
        f"Gols: {_gols(jogo)}",
    ])


def resumo(
    dados: dict,
    anterior: dict | None = None,
    jogadores_novos: list[str] | None = None,
    apelidos_novos: dict[str, list[str]] | None = None,
) -> str:
    """anterior é a versão publicada, quando o rascunho é uma correção."""
    titulo = "Correção da pelada" if anterior else "Pelada"
    partes = [
        f"{titulo} de {_data(dados['date'])}",
        f"Juiz: {dados['referee'] or 'não informado'}",
        f"{len(dados['games'])} jogos",
    ]
    if anterior:
        partes.append("O que muda: " + _mudancas(anterior, dados))
    if jogadores_novos:
        partes.append("Jogadores novos no cadastro: " + ", ".join(jogadores_novos))
    if apelidos_novos:
        partes.append("Apelidos novos: " + "; ".join(f"{k}: {', '.join(v)}" for k, v in apelidos_novos.items()))
    blocos = ["\n".join(partes)] + [_jogo(j) for j in dados["games"]]
    return "\n\n".join(blocos)


def _mudancas(antes: dict, depois: dict) -> str:
    itens = []
    if antes.get("referee") != depois.get("referee"):
        itens.append(f"juiz ({antes.get('referee') or 'vazio'} para {depois.get('referee') or 'vazio'})")
    jogos_antes = {j["game_number"]: j for j in antes.get("games", [])}
    jogos_depois = {j["game_number"]: j for j in depois.get("games", [])}
    for n in sorted(set(jogos_antes) | set(jogos_depois)):
        if n not in jogos_antes:
            itens.append(f"jogo {n} incluído")
        elif n not in jogos_depois:
            itens.append(f"jogo {n} removido")
        elif jogos_antes[n] != jogos_depois[n]:
            itens.append(f"jogo {n}")
    return ", ".join(itens) if itens else "nada"


def dividir(texto: str, limite: int = LIMITE_TELEGRAM) -> list[str]:
    """Divide em mensagens de até `limite` caracteres, quebrando entre parágrafos."""
    mensagens, atual = [], ""
    for bloco in texto.split("\n\n"):
        while len(bloco) > limite:
            if atual:
                mensagens.append(atual)
                atual = ""
            mensagens.append(bloco[:limite])
            bloco = bloco[limite:]
        candidato = f"{atual}\n\n{bloco}" if atual else bloco
        if len(candidato) > limite:
            mensagens.append(atual)
            atual = bloco
        else:
            atual = candidato
    if atual:
        mensagens.append(atual)
    return mensagens

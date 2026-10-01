"""Ferramentas próprias do agente e o hook que limita o que ele acessa.

As ferramentas rodam dentro do processo do bot. O agente não tem Bash: tudo o
que precisa executar código (testes, cadastro de jogador) passa por aqui.
"""

import hashlib
import json
import re
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from claude_agent_sdk import create_sdk_mcp_server, tool

import checks
import jogadores
from access import Pessoa
from publish import DATA_FILE, Repo

SERVIDOR = "pelada"
FERRAMENTAS_NATIVAS = ["Read", "Glob", "Grep", "Write", "Edit"]
DATA = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@dataclass
class Sessao:
    chat_id: int
    organizador: Pessoa
    wt: Path
    data: str | None = None
    # Preenchidos por apresentar_resumo: a data pronta e a impressão digital
    # dos arquivos, para o bot recusar publicar se algo mudou depois.
    pronto: str | None = None
    impressao: str | None = None
    resumo_pendente: bool = False
    custo_usd: float = 0.0
    hoje: datetime | None = None  # só a avaliação muda; o normal é a hora atual
    mensagens: list[str] = field(default_factory=list)


def impressao_digital(wt: Path, data: str) -> str:
    h = hashlib.sha256()
    for rel in (f"data/{data}.json", "players.json"):
        p = wt / rel
        h.update(rel.encode())
        h.update(p.read_bytes() if p.exists() else b"")
    return h.hexdigest()


def _texto(t: str, erro: bool = False) -> dict[str, Any]:
    r: dict[str, Any] = {"content": [{"type": "text", "text": t}]}
    if erro:
        r["is_error"] = True
    return r


def _roda_testes_de_dados(wt: Path) -> tuple[bool, str]:
    r = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "tests/test_data.py"],
        cwd=wt, capture_output=True, text=True,
    )
    saida = (r.stdout + r.stderr).strip().splitlines()
    return r.returncode == 0, "\n".join(saida[-40:])


def verifica_rascunho(sessao: Sessao, repo: Repo, data: str) -> tuple[bool, str]:
    if not DATA.match(data):
        return False, f'"{data}" não é uma data no formato AAAA-MM-DD.'
    path = sessao.wt / "data" / f"{data}.json"
    if not path.exists():
        return False, f"O arquivo data/{data}.json não existe no rascunho."
    try:
        dados = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return False, f"O arquivo data/{data}.json não é um JSON válido: {e}"

    publicadas = repo.published_dates()
    resultado = checks.verificar(dados, data, publicadas, nova=data not in publicadas)
    linhas = []
    if resultado.erros:
        linhas += ["Erros (bloqueiam a publicação):", *[f"- {e}" for e in resultado.erros]]
    else:
        ok, saida = _roda_testes_de_dados(sessao.wt)
        if not ok:
            resultado.erros.append("testes")
            linhas += ["Erros dos testes de dados (bloqueiam a publicação):", saida]
    if resultado.avisos:
        linhas += ["Avisos (confirme com o organizador se está certo):", *[f"- {a}" for a in resultado.avisos]]
    if not linhas:
        linhas = ["Nenhum erro e nenhum aviso."]
    return resultado.ok, "\n".join(linhas)


def criar_ferramentas(sessao: Sessao, repo: Repo, outras_sessoes: Callable[[], list[Sessao]]) -> list:
    """As ferramentas da sessão, com o estado dela capturado."""
    players_path = sessao.wt / "players.json"

    @tool(
        "buscar_jogador",
        "Procura no cadastro (players.json) jogadores cujo nome principal ou apelido se parece com o texto. "
        "Use para cada nome das anotações que não bate exatamente com um apelido cadastrado, antes de "
        "perguntar ao organizador ou de cadastrar alguém.",
        {"nome": str},
    )
    async def buscar_jogador(args):
        dados = jogadores.carrega(players_path)
        exatos = jogadores.dono_do_nome(dados, args["nome"])
        achados = jogadores.busca(dados, args["nome"])
        if not achados:
            return _texto(f'Nenhum jogador parecido com "{args["nome"]}".')
        linhas = [f'Parecidos com "{args["nome"]}" (nome principal, grafia que bateu, semelhança):']
        linhas += [f"- {n} | {g} | {s}" for n, g, s in achados]
        if len(exatos) == 1:
            linhas.append(f"Bate exatamente com o apelido de {exatos[0]}.")
        elif len(exatos) > 1:
            linhas.append(f"Atenção: bate exatamente com apelidos de mais de um jogador: {', '.join(exatos)}. Pergunte qual.")
        return _texto("\n".join(linhas))

    @tool(
        "adicionar_jogador",
        "Cadastra um jogador novo no players.json. Só use depois de o organizador confirmar que não é "
        "nenhum jogador existente. Parâmetros: nome (como o jogador é conhecido, sem o sufixo Conv), "
        "convidado (true para convidado, que ganha o sufixo \" Conv\"; false para jogador fixo). "
        "Opcional: apelidos, lista de outras grafias que aparecem nas anotações.",
        {
            "type": "object",
            "properties": {
                "nome": {"type": "string"},
                "convidado": {"type": "boolean"},
                "apelidos": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["nome", "convidado"],
        },
    )
    async def adicionar_jogador(args):
        dados = jogadores.carrega(players_path)
        base = " ".join(args["nome"].split())
        if base.lower().endswith(" conv"):
            base = base[:-5].strip()
        if not base:
            return _texto("O nome não pode ser vazio.", erro=True)
        if args["convidado"]:
            principal = f"{base} Conv"
            apelidos = [principal, f"{base} conv", f"{base} convidado"]
        else:
            principal = base
            apelidos = [base]
        for extra in args.get("apelidos") or []:
            extra = " ".join(extra.split())
            if extra and extra not in apelidos:
                apelidos.append(extra)
        conflitos = {a: jogadores.dono_do_nome(dados, a) for a in [principal, *apelidos]}
        conflitos = {a: donos for a, donos in conflitos.items() if donos}
        if conflitos:
            detalhes = "; ".join(f'"{a}" já é de {", ".join(d)}' for a, d in conflitos.items())
            return _texto(f"Não cadastrei: {detalhes}. Confirme com o organizador.", erro=True)
        dados[principal] = apelidos
        jogadores.grava(players_path, dados)
        return _texto(f'Cadastrado "{principal}" com os apelidos {apelidos}. Use "{principal}" no JSON da pelada.')

    @tool(
        "desfazer_jogador_novo",
        "Remove do cadastro um jogador que foi criado neste mesmo rascunho e ainda não foi publicado. Use "
        "quando o organizador quiser outro nome para ele ou disser que não era jogador novo; depois "
        "cadastre de novo com o nome certo e atualize o rascunho. Não serve para jogadores já publicados.",
        {"nome": str},
    )
    async def desfazer_jogador_novo(args):
        dados = jogadores.carrega(players_path)
        nome = args["nome"]
        if nome not in dados:
            return _texto(f'"{nome}" não está no cadastro.', erro=True)
        publicado = subprocess.run(["git", "show", "HEAD:players.json"], cwd=sessao.wt, capture_output=True, text=True)
        if nome in json.loads(publicado.stdout):
            return _texto(f'"{nome}" já estava publicado antes deste cadastro. Renomear é com o administrador.', erro=True)
        del dados[nome]
        jogadores.grava(players_path, dados)
        return _texto(f'Removi "{nome}" do cadastro. Lembre de tirar esse nome do rascunho da pelada.')

    @tool(
        "adicionar_apelido",
        "Adiciona uma grafia nova à lista de apelidos de um jogador já cadastrado, por exemplo quando as "
        "anotações escrevem o nome de um jeito diferente. Parâmetros: jogador (nome principal) e apelido.",
        {"jogador": str, "apelido": str},
    )
    async def adicionar_apelido(args):
        dados = jogadores.carrega(players_path)
        jogador, apelido = args["jogador"], " ".join(args["apelido"].split())
        if jogador not in dados:
            return _texto(f'"{jogador}" não é um nome principal do cadastro.', erro=True)
        donos = [d for d in jogadores.dono_do_nome(dados, apelido) if d != jogador]
        if donos:
            return _texto(f'Não adicionei: "{apelido}" já é apelido de {", ".join(donos)}.', erro=True)
        if apelido in dados[jogador]:
            return _texto(f'"{apelido}" já é apelido de {jogador}.')
        dados[jogador].append(apelido)
        jogadores.grava(players_path, dados)
        return _texto(f'Adicionado "{apelido}" aos apelidos de {jogador}.')

    @tool(
        "consultar_data",
        "Diz se já existe pelada publicada na data e se outro organizador está cadastrando a mesma data "
        "agora. Chame assim que souber a data da pelada (formato AAAA-MM-DD), antes de fazer as outras perguntas.",
        {"data": str},
    )
    async def consultar_data(args):
        data = args["data"]
        if not DATA.match(data):
            return _texto(f'"{data}" não está no formato AAAA-MM-DD.', erro=True)
        sessao.data = data
        repo.ensure_clone()
        linhas = []
        if data in repo.published_dates():
            pub = repo.ultima_publicacao_da_data(data)
            quem = f" por {pub.autor_nome} em {pub.publicado_em}" if pub else " (fora do bot)"
            linhas.append(
                f"Já existe pelada publicada em {data}{quem}. Avise o organizador e pergunte se ele quer "
                "corrigir algo nela. Se sim, edite o arquivo existente. Se não, encerre o cadastro."
            )
        outros = [s for s in outras_sessoes() if s.chat_id != sessao.chat_id and s.data == data]
        for s in outros:
            linhas.append(
                f"{s.organizador.nome} está cadastrando a pelada de {data} agora. Avise o organizador: ele "
                "pode esperar e corrigir depois que a outra pessoa publicar, ou descartar o rascunho."
            )
        return _texto("\n".join(linhas) or f"Não há pelada publicada nem outro cadastro em andamento em {data}.")

    @tool(
        "verificar_rascunho",
        "Roda as verificações e os testes de dados no rascunho data/AAAA-MM-DD.json e devolve erros e avisos.",
        {"data": str},
    )
    async def verificar_rascunho(args):
        ok, texto = verifica_rascunho(sessao, repo, args["data"])
        return _texto(texto, erro=not ok)

    @tool(
        "apresentar_resumo",
        "Verifica o rascunho e, se não houver erros, faz o bot mostrar ao organizador o resumo da pelada "
        "com o botão Publicar. Só chame quando todas as dúvidas e avisos estiverem resolvidos. Depois, "
        "não repita o resumo: escreva só uma frase pedindo que ele confira e toque em Publicar.",
        {"data": str},
    )
    async def apresentar_resumo(args):
        data = args["data"]
        ok, texto = verifica_rascunho(sessao, repo, data)
        if not ok:
            return _texto("O resumo não foi apresentado porque há erros.\n" + texto, erro=True)
        sessao.data = data
        sessao.pronto = data
        sessao.impressao = impressao_digital(sessao.wt, data)
        sessao.resumo_pendente = True
        return _texto("O resumo será mostrado ao organizador com o botão Publicar.")

    return [
        buscar_jogador, adicionar_jogador, desfazer_jogador_novo, adicionar_apelido,
        consultar_data, verificar_rascunho, apresentar_resumo,
    ]


def criar_servidor(sessao: Sessao, repo: Repo, outras_sessoes: Callable[[], list[Sessao]]):
    return create_sdk_mcp_server(name=SERVIDOR, version="1.0.0", tools=criar_ferramentas(sessao, repo, outras_sessoes))


def nomes_das_ferramentas() -> list[str]:
    return [f"mcp__{SERVIDOR}__{n}" for n in (
        "buscar_jogador", "adicionar_jogador", "desfazer_jogador_novo", "adicionar_apelido",
        "consultar_data", "verificar_rascunho", "apresentar_resumo",
    )]


def _dentro(wt: Path, caminho: str) -> Path | None:
    """Resolve o caminho (relativo ao worktree) e devolve None se sair dele."""
    if not caminho:
        return wt
    p = Path(caminho).expanduser()
    if not p.is_absolute():
        p = wt / p
    try:
        real = p.resolve()
        real.relative_to(wt.resolve())
    except (ValueError, OSError):
        return None
    return real


def criar_hook(wt: Path):
    """PreToolUse: roda antes de qualquer regra de permissão e nega o que sair do combinado."""
    permitidas = set(FERRAMENTAS_NATIVAS) | set(nomes_das_ferramentas())
    raiz = wt.resolve()

    def nega(input_data, motivo):
        return {
            "hookSpecificOutput": {
                "hookEventName": input_data["hook_event_name"],
                "permissionDecision": "deny",
                "permissionDecisionReason": motivo,
            }
        }

    async def hook(input_data, tool_use_id, context):
        nome = input_data.get("tool_name", "")
        entrada = input_data.get("tool_input") or {}
        if nome not in permitidas:
            return nega(input_data, f"A ferramenta {nome} não está disponível neste bot.")
        if nome in ("Write", "Edit"):
            real = _dentro(wt, entrada.get("file_path", ""))
            rel = real.relative_to(raiz).as_posix() if real else None
            if rel is None or not DATA_FILE.match(rel):
                return nega(input_data, "Só é permitido escrever arquivos data/AAAA-MM-DD.json. "
                                        "Jogadores e apelidos mudam pelas ferramentas próprias.")
        elif nome == "Read":
            if _dentro(wt, entrada.get("file_path", "")) is None:
                return nega(input_data, "Só é permitido ler arquivos do repositório da pelada.")
        elif nome in ("Glob", "Grep"):
            if _dentro(wt, entrada.get("path", "")) is None:
                return nega(input_data, "Só é permitido buscar dentro do repositório da pelada.")
            padrao = entrada.get("pattern" if nome == "Glob" else "glob", "") or ""
            if padrao.startswith(("/", "~")) or ".." in padrao:
                return nega(input_data, "Use padrões relativos ao repositório da pelada.")
        return {}

    return hook

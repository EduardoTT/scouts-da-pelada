"""Uma sessão por chat: worktree próprio, agente próprio e o ciclo de vida da conversa.

Este módulo não sabe nada de Telegram. O main.py e o cli.py usam o Gerente
do mesmo jeito.
"""

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

from access import Pessoa
from agent import Agente, Resposta
from config import Config, agora
from publish import Publicacao, PublishError, Repo, VerificacaoError
from storage import read_json, write_json
from summary import resumo
from tools import Sessao, impressao_digital

log = logging.getLogger(__name__)
INATIVIDADE = timedelta(hours=6)


@dataclass
class Ativa:
    sessao: Sessao
    agente: Agente
    lock: asyncio.Lock
    coletando: bool = True
    ultima_atividade: datetime | None = None


class RascunhoMudouError(PublishError):
    pass


class Gerente:
    def __init__(self, cfg: Config, repo: Repo, relogio=agora):
        self.cfg = cfg
        self.repo = repo
        self.relogio = relogio
        self.ativas: dict[int, Ativa] = {}
        self.registro_path = cfg.volume_dir / "sessoes_ativas.json"

    # ---------- ciclo de vida ----------

    def sessoes(self) -> list[Sessao]:
        return [a.sessao for a in self.ativas.values()]

    def ativa(self, chat_id: int) -> Ativa | None:
        return self.ativas.get(chat_id)

    async def abrir(self, chat_id: int, organizador: Pessoa) -> Ativa:
        if chat_id in self.ativas:
            return self.ativas[chat_id]
        wt = await asyncio.to_thread(self.repo.create_worktree, f"chat-{chat_id}")
        sessao = Sessao(chat_id=chat_id, organizador=organizador, wt=wt, hoje=self.relogio())
        ativa = Ativa(sessao, Agente(self.cfg, sessao, self.repo, self.sessoes), asyncio.Lock())
        ativa.ultima_atividade = agora()
        self.ativas[chat_id] = ativa
        self._salva_registro()
        return ativa

    async def encerrar(self, chat_id: int) -> None:
        ativa = self.ativas.pop(chat_id, None)
        if ativa is None:
            return
        try:
            await ativa.agente.fechar()
        except Exception:
            log.exception("erro ao fechar o agente do chat %s", chat_id)
        await asyncio.to_thread(self.repo.remove_worktree, ativa.sessao.wt)
        self._salva_registro()

    async def encerrar_inativas(self) -> list[int]:
        limite = agora() - INATIVIDADE
        velhas = [cid for cid, a in self.ativas.items() if a.ultima_atividade < limite and not a.lock.locked()]
        for cid in velhas:
            await self.encerrar(cid)
        return velhas

    def _salva_registro(self) -> None:
        write_json(self.registro_path, sorted(self.ativas))

    def chats_interrompidos(self) -> list[int]:
        """Chats que tinham sessão aberta quando o bot parou. Limpa o registro."""
        chats = read_json(self.registro_path, [])
        write_json(self.registro_path, [])
        return chats

    # ---------- conversa ----------

    def juntar(self, ativa: Ativa, texto: str) -> int:
        ativa.sessao.mensagens.append(texto)
        ativa.ultima_atividade = agora()
        return len(ativa.sessao.mensagens)

    async def terminei(self, ativa: Ativa) -> Resposta:
        texto = "\n\n".join(ativa.sessao.mensagens)
        ativa.sessao.mensagens.clear()
        ativa.coletando = False
        return await self.enviar(
            ativa,
            "O organizador mandou as anotações abaixo e avisou que terminou.\n\n"
            f"--- início das anotações ---\n{texto}\n--- fim das anotações ---",
        )

    async def enviar(self, ativa: Ativa, texto: str) -> Resposta:
        async with ativa.lock:
            ativa.ultima_atividade = agora()
            ativa.sessao.resumo_pendente = False
            resposta = await ativa.agente.enviar(texto)
            ativa.ultima_atividade = agora()
            return resposta

    def resumo_pronto(self, ativa: Ativa) -> str | None:
        """Texto do resumo, se o agente acabou de chamar apresentar_resumo."""
        s = ativa.sessao
        if not (s.resumo_pendente and s.pronto):
            return None
        s.resumo_pendente = False
        dados = json.loads((s.wt / "data" / f"{s.pronto}.json").read_text(encoding="utf-8"))
        anterior = None
        if s.pronto in self.repo.published_dates():
            anterior = json.loads(self.repo._git("show", f"origin/main:data/{s.pronto}.json", cwd=s.wt).stdout)
        antes = json.loads(self.repo._git("show", "HEAD:players.json", cwd=s.wt).stdout)
        depois = json.loads((s.wt / "players.json").read_text(encoding="utf-8"))
        novos = [n for n in depois if n not in antes]
        apelidos = {n: [a for a in depois[n] if a not in antes[n]] for n in depois if n in antes and depois[n] != antes[n]}
        return resumo(dados, anterior, novos, apelidos)

    # ---------- publicação ----------

    async def publicar(self, ativa: Ativa) -> tuple[Publicacao, list[int]]:
        """Publica o rascunho apresentado. Devolve a publicação e os chats a avisar."""
        s = ativa.sessao
        async with ativa.lock:
            if not s.pronto:
                raise PublishError("Ainda não há um resumo pronto para publicar.")
            if impressao_digital(s.wt, s.pronto) != s.impressao:
                raise RascunhoMudouError("O rascunho mudou depois do resumo. Peça o resumo de novo antes de publicar.")
            tipo = "correcao" if s.pronto in self.repo.published_dates() else "cadastro"
            pub = await asyncio.to_thread(self.repo.publish, s.wt, s.pronto, tipo, s.organizador)
        avisar = [o.chat_id for o in self.sessoes() if o.chat_id != s.chat_id and o.data == s.pronto]
        await self.encerrar(s.chat_id)
        return pub, avisar

    async def falha_de_publicacao(self, ativa: Ativa, erro: VerificacaoError) -> Resposta:
        """Devolve ao agente o erro dos testes, para ele corrigir o rascunho."""
        ativa.sessao.pronto = None
        return await self.enviar(
            ativa,
            "[Mensagem do bot, não do organizador] A publicação foi recusada porque os testes ou o build "
            f"do site falharam. Saída:\n{erro.saida}\n\nCorrija o rascunho, explique ao organizador em "
            "uma frase o que mudou e chame apresentar_resumo de novo.",
        )

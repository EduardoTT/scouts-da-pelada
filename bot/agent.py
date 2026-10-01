"""Configuração do Agent SDK e a conversa com o agente de uma sessão."""

from collections.abc import Callable
from dataclasses import dataclass

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    HookMatcher,
    ResultMessage,
    TextBlock,
)

from config import BOT_DIR, Config, agora
from publish import Repo
from summary import DIAS
from tools import FERRAMENTAS_NATIVAS, Sessao, criar_hook, criar_servidor, nomes_das_ferramentas

PROMPT = (BOT_DIR / "prompt.md").read_text(encoding="utf-8")


@dataclass
class Resposta:
    texto: str
    custo_total_usd: float
    encerrada: bool = False  # True quando a sessão estourou turnos ou orçamento


def opcoes(cfg: Config, sessao: Sessao, repo: Repo, outras_sessoes: Callable[[], list[Sessao]]) -> ClaudeAgentOptions:
    hoje = sessao.hoje or agora()
    contexto = (
        f"\n\n# Contexto desta conversa\n\nHoje é {hoje:%Y-%m-%d} ({DIAS[hoje.weekday()]}), "
        f"{hoje:%H:%M} no horário de Brasília. O organizador se chama {sessao.organizador.nome}."
    )
    return ClaudeAgentOptions(
        model=cfg.model,
        cwd=str(sessao.wt),
        system_prompt=PROMPT + contexto,
        setting_sources=[],
        tools=FERRAMENTAS_NATIVAS,
        allowed_tools=FERRAMENTAS_NATIVAS + nomes_das_ferramentas(),
        disallowed_tools=["Bash", "WebFetch", "WebSearch", "Agent", "NotebookEdit"],
        permission_mode="dontAsk",
        mcp_servers={"pelada": criar_servidor(sessao, repo, outras_sessoes)},
        hooks={"PreToolUse": [HookMatcher(hooks=[criar_hook(sessao.wt)])]},
        max_turns=cfg.max_turns,
        max_budget_usd=cfg.max_budget_usd,
        env={
            "CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1",
            "CLAUDE_CONFIG_DIR": str(cfg.volume_dir / "claude"),
            # Com só seis ferramentas próprias, carregar todas de uma vez é mais simples.
            "ENABLE_TOOL_SEARCH": "false",
        },
    )


class Agente:
    def __init__(self, cfg: Config, sessao: Sessao, repo: Repo, outras_sessoes: Callable[[], list[Sessao]]):
        self.sessao = sessao
        self.client = ClaudeSDKClient(options=opcoes(cfg, sessao, repo, outras_sessoes))
        self.conectado = False

    async def enviar(self, texto: str) -> Resposta:
        if not self.conectado:
            await self.client.connect()
            self.conectado = True
        await self.client.query(texto)
        partes: list[str] = []
        resultado: ResultMessage | None = None
        async for msg in self.client.receive_response():
            if isinstance(msg, AssistantMessage):
                partes.append("".join(b.text for b in msg.content if isinstance(b, TextBlock)))
            elif isinstance(msg, ResultMessage):
                resultado = msg

        custo = (resultado.total_cost_usd if resultado else None) or self.sessao.custo_usd
        self.sessao.custo_usd = custo
        if resultado and resultado.subtype in ("error_max_turns", "error_max_budget_usd"):
            return Resposta(
                "Essa conversa ficou longa demais e foi encerrada. Mande /nova e comece de novo, "
                "de preferência colando as anotações todas de uma vez.",
                custo, encerrada=True,
            )
        if resultado and resultado.is_error:
            return Resposta("Tive um problema para processar sua mensagem. Tente de novo em instantes.", custo)
        # O texto final da vez é a última mensagem com texto do agente.
        final = (resultado.result if resultado and resultado.result else None) or next(
            (p for p in reversed(partes) if p.strip()), ""
        )
        return Resposta(final.strip(), custo)

    async def fechar(self) -> None:
        if self.conectado:
            await self.client.disconnect()
            self.conectado = False

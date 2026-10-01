"""Conversa com o agente pelo terminal, sem Telegram. Para testes locais.

Uso:
    uv run python cli.py              # interativo
    uv run python cli.py roteiro.txt  # lê as mensagens de um arquivo, separadas por linhas "---"

Comandos: /terminei, /publicar, /nova, /sair. Publica no repo de REPO_SSH_URL,
então use o repo de teste.
"""

import asyncio
import sys

from access import Pessoa
from config import Config
from publish import PublishError, Repo, VerificacaoError
from session import Gerente

CHAT = 1


async def responde(gerente: Gerente, ativa, resposta) -> None:
    if resposta.texto:
        print(f"\n[bot] {resposta.texto}")
    texto = gerente.resumo_pronto(ativa)
    if texto:
        print(f"\n[resumo]\n{texto}\n\n[botões: Publicar]")
    print(f"\n(custo acumulado: US$ {resposta.custo_total_usd:.3f})")


async def trata(gerente: Gerente, organizador: Pessoa, entrada: str) -> bool:
    entrada = entrada.strip()
    if not entrada:
        return True
    if entrada == "/sair":
        return False
    if entrada == "/nova":
        await gerente.encerrar(CHAT)
        print("[bot] Rascunho descartado.")
        return True
    ativa = await gerente.abrir(CHAT, organizador)
    if entrada == "/terminei":
        await responde(gerente, ativa, await gerente.terminei(ativa))
    elif entrada == "/publicar":
        try:
            pub, avisar = await gerente.publicar(ativa)
            print(f"[bot] Publicado: {pub.tipo} de {pub.data_pelada}, commits {pub.commits}. Avisar: {avisar}")
        except VerificacaoError as e:
            await responde(gerente, ativa, await gerente.falha_de_publicacao(ativa, e))
        except PublishError as e:
            print(f"[bot] Não publiquei: {e}")
    elif ativa.coletando:
        n = gerente.juntar(ativa, entrada)
        print(f"[bot] Recebi ({n} mensagens). Mande /terminei quando acabar.")
    else:
        await responde(gerente, ativa, await gerente.enviar(ativa, entrada))
    return True


async def main() -> None:
    cfg = Config.from_env()
    repo = Repo(cfg.repo_url, cfg.volume_dir, cfg.git_author_name, cfg.git_author_email, ssh_key=cfg.deploy_key_file)
    await asyncio.to_thread(repo.ensure_clone)
    gerente = Gerente(cfg, repo)
    organizador = Pessoa(cfg.admin_id, "Eduardo", None)
    try:
        if len(sys.argv) > 1:
            blocos = open(sys.argv[1], encoding="utf-8").read().split("\n---\n")
            for bloco in blocos:
                print(f"\n[organizador] {bloco.strip()}")
                if not await trata(gerente, organizador, bloco):
                    break
        else:
            while True:
                try:
                    entrada = input("\n[você] ")
                except EOFError:
                    break
                if not await trata(gerente, organizador, entrada):
                    break
    finally:
        await gerente.encerrar(CHAT)


if __name__ == "__main__":
    asyncio.run(main())

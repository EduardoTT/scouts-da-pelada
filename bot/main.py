"""Bot de Telegram: acesso, conversa com o agente, publicação e /desfazer."""

import asyncio
import contextlib
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, User
from telegram.constants import ChatAction, ChatType
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from access import AccessStore, Pessoa
from config import Config
from deploy import espera_deploy
from publish import ConflitoError, PublishError, Repo, VerificacaoError
from session import Ativa, Gerente
from summary import dividir

logging.basicConfig(format="%(asctime)s %(levelname)s %(name)s: %(message)s", level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger("bot")

PRIVADO = filters.ChatType.PRIVATE

BOAS_VINDAS = (
    "Oi! Eu cadastro as peladas no site.\n\n"
    "Cole as anotações da pelada, do jeito que vocês escrevem, em uma ou várias mensagens. "
    "Quando terminar, toque em Terminei. Eu monto o cadastro, pergunto o que faltar e mostro "
    "um resumo para você conferir antes de publicar.\n\n"
    "Para corrigir uma pelada antiga, escreva o que está errado e em qual data.\n\n"
    "Comandos:\n"
    "/nova descarta o cadastro em andamento\n"
    "/desfazer desfaz uma publicação sua"
)


def botoes(*linhas: list[tuple[str, str]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton(t, callback_data=d) for t, d in linha] for linha in linhas])


def pessoa(user: User) -> Pessoa:
    return Pessoa(user.id, user.full_name, user.username)


class Bot:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        key = cfg.deploy_key_file
        if cfg.deploy_key:
            key = cfg.volume_dir / "deploy_key"
            cfg.volume_dir.mkdir(parents=True, exist_ok=True)
            key.write_text(cfg.deploy_key.strip() + "\n", encoding="utf-8")
            key.chmod(0o600)
        self.repo = Repo(cfg.repo_url, cfg.volume_dir, cfg.git_author_name, cfg.git_author_email, ssh_key=key)
        self.acesso = AccessStore(cfg.volume_dir / "organizadores.json", cfg.admin_id)
        self.gerente = Gerente(cfg, self.repo)
        self.status_msg: dict[int, int] = {}  # chat -> id da mensagem "Recebi N"

    # ---------- utilidades ----------

    async def digitando(self, ctx: ContextTypes.DEFAULT_TYPE, chat_id: int, trabalho):
        """Mostra "digitando..." enquanto o trabalho roda."""
        async def loop():
            while True:
                with contextlib.suppress(Exception):
                    await ctx.bot.send_chat_action(chat_id, ChatAction.TYPING)
                await asyncio.sleep(4)

        tarefa = asyncio.create_task(loop())
        try:
            return await trabalho
        finally:
            tarefa.cancel()

    async def envia(self, ctx, chat_id: int, texto: str, markup=None) -> None:
        partes = dividir(texto) or [""]
        for i, parte in enumerate(partes):
            await ctx.bot.send_message(chat_id, parte, reply_markup=markup if i == len(partes) - 1 else None)

    async def responde_agente(self, ctx, ativa: Ativa, resposta) -> None:
        chat_id = ativa.sessao.chat_id
        resumo = self.gerente.resumo_pronto(ativa)
        if resumo:
            await self.envia(ctx, chat_id, resumo)
        if resposta.texto:
            markup = botoes([("Publicar", "publicar")]) if resumo else None
            await self.envia(ctx, chat_id, resposta.texto, markup)
        elif resumo:
            await ctx.bot.send_message(chat_id, "Confira o resumo.", reply_markup=botoes([("Publicar", "publicar")]))
        if resposta.encerrada:
            await self.gerente.encerrar(chat_id)

    async def limpa_status(self, ctx, chat_id: int) -> None:
        msg_id = self.status_msg.pop(chat_id, None)
        if msg_id:
            with contextlib.suppress(Exception):
                await ctx.bot.delete_message(chat_id, msg_id)

    # ---------- acesso ----------

    async def start(self, update: Update, ctx) -> None:
        user = update.effective_user
        if self.acesso.is_allowed(user.id):
            await update.message.reply_text(BOAS_VINDAS)
        elif self.acesso.is_pending(user.id):
            await update.message.reply_text("Seu pedido de acesso está com o administrador. Aguarde a resposta.")
        else:
            await update.message.reply_text(
                "Este bot cadastra as peladas no site e só funciona para organizadores aprovados.",
                reply_markup=botoes([("Pedir acesso", "pedir")]),
            )

    async def pedir(self, update: Update, ctx) -> None:
        q = update.callback_query
        await q.answer()
        p = pessoa(q.from_user)
        if self.acesso.is_allowed(p.id):
            await q.edit_message_text(BOAS_VINDAS)
            return
        if self.acesso.request(p):
            await ctx.bot.send_message(
                self.cfg.admin_id,
                f"{p.descricao} pediu acesso ao bot de cadastro de peladas.",
                reply_markup=botoes([("Aprovar", f"aprovar:{p.id}"), ("Recusar", f"recusar:{p.id}")]),
            )
        await q.edit_message_text("Pedido enviado ao administrador. Eu aviso quando ele responder.")

    async def decidir(self, update: Update, ctx) -> None:
        q = update.callback_query
        await q.answer()
        if not self.acesso.is_admin(q.from_user.id):
            return
        acao, user_id = q.data.split(":")
        if acao == "aprovar":
            p = self.acesso.approve(int(user_id))
            if p:
                await ctx.bot.send_message(p.id, "Seu acesso foi aprovado!\n\n" + BOAS_VINDAS)
                await q.edit_message_text(f"Acesso aprovado para {p.descricao}.")
        elif acao == "recusar":
            p = self.acesso.reject(int(user_id))
            if p:
                await ctx.bot.send_message(p.id, "Seu pedido de acesso não foi aprovado.")
                await q.edit_message_text(f"Pedido de {p.descricao} recusado.")
        elif acao == "remover":
            p = self.acesso.remove(int(user_id))
            if p:
                await self.gerente.encerrar(p.id)
                await q.edit_message_text(f"{p.descricao} não é mais organizador.")
        if not p:
            await q.edit_message_text("Esse pedido já tinha sido resolvido.")

    async def organizadores(self, update: Update, ctx) -> None:
        if not self.acesso.is_admin(update.effective_user.id):
            return
        orgs = self.acesso.organizers()
        if not orgs:
            await update.message.reply_text("Nenhum organizador aprovado ainda.")
            return
        await update.message.reply_text(
            "Organizadores aprovados. Toque em um nome para remover o acesso.",
            reply_markup=botoes(*[[(f"Remover {o.descricao}", f"remover:{o.id}")] for o in orgs]),
        )

    # ---------- conversa ----------

    async def mensagem(self, update: Update, ctx) -> None:
        user = update.effective_user
        if not self.acesso.is_allowed(user.id):
            await self.start(update, ctx)
            return
        chat_id = update.effective_chat.id
        ativa = await self.gerente.abrir(chat_id, pessoa(user))
        texto = update.message.text
        if ativa.coletando:
            n = self.gerente.juntar(ativa, texto)
            await self.limpa_status(ctx, chat_id)
            plural = "mensagem" if n == 1 else "mensagens"
            msg = await update.message.reply_text(
                f"Recebi {n} {plural}. Pode mandar mais. Quando acabar, toque em Terminei.",
                reply_markup=botoes([("Terminei", "terminei")]),
            )
            self.status_msg[chat_id] = msg.message_id
            return
        resposta = await self.digitando(ctx, chat_id, self.gerente.enviar(ativa, texto))
        await self.responde_agente(ctx, ativa, resposta)

    async def terminei(self, update: Update, ctx) -> None:
        q = update.callback_query
        await q.answer()
        chat_id = q.message.chat.id
        ativa = self.gerente.ativa(chat_id)
        if not ativa or not ativa.coletando or not ativa.sessao.mensagens:
            return
        self.status_msg.pop(chat_id, None)
        await q.edit_message_text("Recebi tudo. Vou montar o cadastro, isso pode levar um minuto.")
        resposta = await self.digitando(ctx, chat_id, self.gerente.terminei(ativa))
        await self.responde_agente(ctx, ativa, resposta)

    async def nova(self, update: Update, ctx) -> None:
        if not self.acesso.is_allowed(update.effective_user.id):
            return
        chat_id = update.effective_chat.id
        await self.limpa_status(ctx, chat_id)
        await self.gerente.encerrar(chat_id)
        await update.message.reply_text("Pronto, descartei o cadastro em andamento. Pode mandar as anotações.")

    # ---------- publicação ----------

    async def publicar(self, update: Update, ctx) -> None:
        q = update.callback_query
        await q.answer()
        chat_id = q.message.chat.id
        ativa = self.gerente.ativa(chat_id)
        if not ativa:
            await ctx.bot.send_message(chat_id, "Esse cadastro não está mais aberto. Mande as anotações de novo.")
            return
        with contextlib.suppress(Exception):
            await q.edit_message_reply_markup(None)
        await ctx.bot.send_message(chat_id, "Publicando...")
        try:
            pub, avisar = await self.digitando(ctx, chat_id, self.gerente.publicar(ativa))
        except VerificacaoError as e:
            log.warning("publicação recusada nos testes: %s", e.saida)
            resposta = await self.digitando(ctx, chat_id, self.gerente.falha_de_publicacao(ativa, e))
            await self.responde_agente(ctx, ativa, resposta)
            return
        except ConflitoError as e:
            await self.gerente.encerrar(chat_id)
            await ctx.bot.send_message(chat_id, f"{e}\n\nDescartei este cadastro.")
            return
        except PublishError as e:
            await ctx.bot.send_message(chat_id, f"Não consegui publicar: {e}")
            return

        link = f"{self.cfg.site_url}?v={pub.data_pelada}"
        for outro in avisar:
            with contextlib.suppress(Exception):
                await ctx.bot.send_message(
                    outro,
                    f"{ativa.sessao.organizador.nome} acabou de publicar a pelada de {pub.data_pelada}. "
                    "Se ainda quiser mudar algo, mande /nova e diga o que corrigir.",
                )
        await ctx.bot.send_message(chat_id, "Publicado! Estou esperando o site atualizar...")
        ok = await espera_deploy(self.cfg.repo_url, pub.commits[-1])
        if ok is False:
            await ctx.bot.send_message(chat_id, "O site não conseguiu atualizar. Avise o administrador.")
            await ctx.bot.send_message(
                self.cfg.admin_id, f"O deploy da publicação de {pub.data_pelada} ({pub.commits[-1][:7]}) falhou."
            )
            return
        prefixo = "O site já está atualizado." if ok else "O site deve atualizar em alguns minutos."
        await ctx.bot.send_message(chat_id, f"{prefixo} Link para o WhatsApp:\n{link}")

    # ---------- desfazer ----------

    async def desfazer(self, update: Update, ctx) -> None:
        user = update.effective_user
        if not self.acesso.is_allowed(user.id):
            return
        pubs = self.repo.desfaziveis(user.id, self.acesso.is_admin(user.id))
        if not pubs:
            await update.message.reply_text("Não há publicação que você possa desfazer.")
            return
        nomes = {"cadastro": "Cadastro", "correcao": "Correção"}
        await update.message.reply_text(
            "Qual publicação você quer desfazer?",
            reply_markup=botoes(*[
                [(f"{nomes[p.tipo]} de {p.data_pelada} ({p.autor_nome}, {p.publicado_em[:16].replace('T', ' ')})",
                  f"desf:{p.id}")]
                for p in pubs
            ]),
        )

    async def desfazer_escolha(self, update: Update, ctx) -> None:
        q = update.callback_query
        await q.answer()
        _, pub_id = q.data.split(":")
        await q.edit_message_text(
            "Tem certeza? A publicação vai sair do site.",
            reply_markup=botoes([("Sim, desfazer", f"desfok:{pub_id}"), ("Cancelar", "desfnao")]),
        )

    async def desfazer_confirma(self, update: Update, ctx) -> None:
        q = update.callback_query
        await q.answer()
        if q.data == "desfnao":
            await q.edit_message_text("Nada foi desfeito.")
            return
        user = q.from_user
        if not self.acesso.is_allowed(user.id):
            return
        _, pub_id = q.data.split(":")
        await q.edit_message_text("Desfazendo...")
        try:
            nova = await self.digitando(
                ctx, q.message.chat.id,
                asyncio.to_thread(self.repo.desfazer, pub_id, pessoa(user), self.acesso.is_admin(user.id)),
            )
        except PublishError as e:
            await ctx.bot.send_message(q.message.chat.id, f"Não consegui desfazer: {e}")
            return
        await ctx.bot.send_message(
            q.message.chat.id, f"Desfeito. A pelada de {nova.data_pelada} volta ao que era antes no site em alguns minutos."
        )

    # ---------- erros e manutenção ----------

    async def erro(self, update: object, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        log.exception("erro tratando update", exc_info=ctx.error)
        if isinstance(update, Update) and update.effective_chat:
            with contextlib.suppress(Exception):
                await ctx.bot.send_message(update.effective_chat.id, "Tive um problema. Tente de novo em instantes.")

    async def ao_iniciar(self, app: Application) -> None:
        await asyncio.to_thread(self.repo.ensure_clone)
        for chat_id in self.gerente.chats_interrompidos():
            with contextlib.suppress(Exception):
                await app.bot.send_message(
                    chat_id, "O bot reiniciou e o cadastro que estava em andamento se perdeu. "
                             "Por favor, mande as anotações de novo."
                )
        self._faxina = asyncio.create_task(self.faxina())
        log.info("bot pronto")

    async def faxina(self) -> None:
        while True:
            await asyncio.sleep(1800)
            with contextlib.suppress(Exception):
                fechadas = await self.gerente.encerrar_inativas()
                if fechadas:
                    log.info("sessões inativas encerradas: %s", fechadas)

    def app(self) -> Application:
        app = (
            Application.builder()
            .token(self.cfg.telegram_token)
            .concurrent_updates(True)
            .post_init(self.ao_iniciar)
            .build()
        )
        app.add_handler(CommandHandler("start", self.start, filters=PRIVADO))
        app.add_handler(CommandHandler("nova", self.nova, filters=PRIVADO))
        app.add_handler(CommandHandler("desfazer", self.desfazer, filters=PRIVADO))
        app.add_handler(CommandHandler("organizadores", self.organizadores, filters=PRIVADO))
        app.add_handler(MessageHandler(PRIVADO & filters.TEXT & ~filters.COMMAND, self.mensagem))
        app.add_handler(CallbackQueryHandler(self.pedir, pattern="^pedir$"))
        app.add_handler(CallbackQueryHandler(self.decidir, pattern="^(aprovar|recusar|remover):"))
        app.add_handler(CallbackQueryHandler(self.terminei, pattern="^terminei$"))
        app.add_handler(CallbackQueryHandler(self.publicar, pattern="^publicar$"))
        app.add_handler(CallbackQueryHandler(self.desfazer_escolha, pattern="^desf:"))
        app.add_handler(CallbackQueryHandler(self.desfazer_confirma, pattern="^(desfok:|desfnao$)"))
        app.add_error_handler(self.erro)
        return app


def main() -> None:
    cfg = Config.from_env()
    Bot(cfg).app().run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=False)


if __name__ == "__main__":
    main()

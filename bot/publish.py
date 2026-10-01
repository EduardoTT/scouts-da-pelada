"""Tudo o que mexe no git: clone, worktrees, testes, commit, push e desfazer.

Este módulo é código fixo. O agente nunca chama nada daqui: quem chama é o
bot, quando o organizador toca em "Publicar" ou usa /desfazer.
"""

import json
import os
import re
import subprocess
import sys
import threading
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path

from access import Pessoa
from config import agora
from storage import read_json, write_json

DATA_FILE = re.compile(r"^data/\d{4}-\d{2}-\d{2}\.json$")
PLAYERS_FILE = "players.json"
MAX_TENTATIVAS_PUSH = 3


class PublishError(Exception):
    """Erro com mensagem pronta para mostrar ao organizador."""


class ConflitoError(PublishError):
    pass


class VerificacaoError(PublishError):
    def __init__(self, mensagem: str, saida: str):
        super().__init__(mensagem)
        self.saida = saida


class SemPermissaoError(PublishError):
    pass


@dataclass
class Publicacao:
    id: str
    tipo: str  # "cadastro", "correcao" ou "desfazer"
    data_pelada: str
    commits: list[str]
    autor_id: int
    autor_nome: str
    publicado_em: str
    desfaz: str | None = None
    desfeita_por: str | None = None


def _nomes(nomes: list[str]) -> str:
    return nomes[0] if len(nomes) == 1 else ", ".join(nomes[:-1]) + " e " + nomes[-1]


def mensagem_players(antes: dict, depois: dict) -> str:
    """Mensagem de commit no padrão do histórico ("Cadastra o Landir no players.json")."""
    novos = [n for n in depois if n not in antes]
    apelidos = [n for n in depois if n in antes and depois[n] != antes[n]]
    if len(novos) == 1 and not apelidos:
        return f"Cadastra o {novos[0]} no {PLAYERS_FILE}"
    if novos and not apelidos:
        return f"Cadastra {_nomes(novos)} no {PLAYERS_FILE}"
    if apelidos and not novos:
        return f"Adiciona apelidos de {_nomes(apelidos)} no {PLAYERS_FILE}"
    return f"Atualiza o {PLAYERS_FILE}: cadastra {_nomes(novos)} e adiciona apelidos de {_nomes(apelidos)}"


class Repo:
    def __init__(
        self,
        url: str,
        volume_dir: Path,
        author_name: str,
        author_email: str,
        ssh_key: Path | None = None,
        python: str = sys.executable,
    ):
        self.url = url
        self.root = volume_dir / "repo"
        self.worktrees = volume_dir / "worktrees"
        self.log_path = volume_dir / "publicacoes.json"
        self.author = (author_name, author_email)
        self.ssh_key = ssh_key
        self.python = python
        self.known_hosts = volume_dir / "known_hosts"
        # Um lock só para o repo compartilhado: fetch, worktrees e publicações
        # acontecem um de cada vez.
        self._lock = threading.RLock()

    # ---------- git ----------

    def _env(self) -> dict:
        env = dict(os.environ, GIT_TERMINAL_PROMPT="0")
        if self.ssh_key:
            env["GIT_SSH_COMMAND"] = (
                f"ssh -i {self.ssh_key} -o IdentitiesOnly=yes "
                f"-o StrictHostKeyChecking=accept-new -o UserKnownHostsFile={self.known_hosts}"
            )
        return env

    def _git(self, *args: str, cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess:
        name, email = self.author
        cmd = ["git", "-c", f"user.name={name}", "-c", f"user.email={email}", *args]
        result = subprocess.run(cmd, cwd=cwd or self.root, env=self._env(), capture_output=True, text=True)
        if check and result.returncode != 0:
            raise subprocess.CalledProcessError(result.returncode, cmd, result.stdout, result.stderr)
        return result

    def ensure_clone(self) -> None:
        with self._lock:
            if (self.root / ".git").exists():
                self._git("fetch", "--prune", "origin")
                return
            self.root.parent.mkdir(parents=True, exist_ok=True)
            self._git("clone", self.url, str(self.root), cwd=self.root.parent)

    def create_worktree(self, name: str) -> Path:
        """Worktree novo a partir do origin/main atualizado. Substitui um anterior de mesmo nome."""
        with self._lock:
            self._git("fetch", "--prune", "origin")
            path = self.worktrees / name
            if path.exists():
                self.remove_worktree(path)
            self.worktrees.mkdir(parents=True, exist_ok=True)
            self._git("worktree", "add", "--detach", str(path), "origin/main")
            return path

    def remove_worktree(self, path: Path) -> None:
        with self._lock:
            self._git("worktree", "remove", "--force", str(path), check=False)
            self._git("worktree", "prune")

    def changed_files(self, wt: Path) -> list[str]:
        out = self._git("status", "--porcelain", "--untracked-files=all", cwd=wt).stdout
        return [line[3:] for line in out.splitlines() if line.strip()]

    def published_dates(self) -> set[str]:
        """Datas das peladas que existem no origin/main."""
        out = self._git("ls-tree", "--name-only", "origin/main", "data/").stdout
        return {Path(p).stem for p in out.splitlines() if DATA_FILE.match(p)}

    # ---------- verificação ----------

    def verify(self, wt: Path) -> tuple[bool, str]:
        """Roda os testes e o build do site dentro do worktree."""
        for cmd in ([self.python, "-m", "pytest", "-q", "tests"], [self.python, "build.py"]):
            result = subprocess.run(cmd, cwd=wt, capture_output=True, text=True)
            if result.returncode != 0:
                saida = (result.stdout + result.stderr).strip()
                return False, "\n".join(saida.splitlines()[-60:])
        return True, ""

    # ---------- publicação ----------

    def publish(self, wt: Path, data_pelada: str, tipo: str, autor: Pessoa) -> Publicacao:
        """Commita as mudanças do worktree e publica no main.

        Em caso de erro, o worktree volta a ter as mudanças sem commit, para o
        agente poder corrigir e o organizador tentar de novo.
        """
        assert tipo in ("cadastro", "correcao")
        with self._lock:
            mudancas = self.changed_files(wt)
            if not mudancas:
                raise PublishError("Não há nenhuma mudança para publicar.")
            proibidas = [m for m in mudancas if m != PLAYERS_FILE and not DATA_FILE.match(m)]
            if proibidas:
                raise PublishError(f"O rascunho mexeu em arquivos que o bot não publica: {', '.join(proibidas)}")

            base = self._git("rev-parse", "HEAD", cwd=wt).stdout.strip()
            corpo = f"Publicado pelo bot de Telegram por {autor.nome}."
            try:
                if PLAYERS_FILE in mudancas:
                    antes = json.loads(self._git("show", f"HEAD:{PLAYERS_FILE}", cwd=wt).stdout)
                    depois = json.loads((wt / PLAYERS_FILE).read_text(encoding="utf-8"))
                    self._git("add", PLAYERS_FILE, cwd=wt)
                    self._git("commit", "-m", mensagem_players(antes, depois), "-m", corpo, cwd=wt)
                if any(DATA_FILE.match(m) for m in mudancas):
                    verbo = "Cadastra" if tipo == "cadastro" else "Corrige"
                    self._git("add", "data", cwd=wt)
                    self._git("commit", "-m", f"{verbo} a pelada de {data_pelada}", "-m", corpo, cwd=wt)
                commits = self._push_com_rebase(wt)
            except Exception:
                self._desfaz_commits_locais(wt, base)
                raise

            pub = Publicacao(
                id=uuid.uuid4().hex[:8],
                tipo=tipo,
                data_pelada=data_pelada,
                commits=commits,
                autor_id=autor.id,
                autor_nome=autor.nome,
                publicado_em=agora().isoformat(timespec="seconds"),
            )
            self._registra(pub)
            return pub

    def _desfaz_commits_locais(self, wt: Path, base: str) -> None:
        """Volta o worktree para antes dos commits, mantendo as mudanças nos arquivos."""
        if self._git("rev-parse", "-q", "--verify", "REBASE_HEAD", cwd=wt, check=False).returncode == 0:
            self._git("rebase", "--abort", cwd=wt, check=False)
        head = self._git("rev-parse", "HEAD", cwd=wt).stdout.strip()
        if head == base:
            return
        # Se o rebase já aconteceu, a base certa é o origin/main novo.
        alvo = base
        if self._git("merge-base", "--is-ancestor", "origin/main", "HEAD", cwd=wt, check=False).returncode == 0:
            alvo = "origin/main"
        self._git("reset", "--mixed", alvo, cwd=wt)

    def _push_com_rebase(self, wt: Path) -> list[str]:
        """Rebase sobre o origin/main, testes, build e push. Repete se o main andou."""
        for _ in range(MAX_TENTATIVAS_PUSH):
            self._git("fetch", "origin", cwd=wt)
            rebase = self._git("rebase", "origin/main", cwd=wt, check=False)
            if rebase.returncode != 0:
                self._git("rebase", "--abort", cwd=wt, check=False)
                raise ConflitoError(
                    "Alguém publicou uma mudança no mesmo arquivo enquanto você editava. "
                    "Descarte este rascunho e comece de novo a partir da versão publicada."
                )
            ok, saida = self.verify(wt)
            if not ok:
                raise VerificacaoError("Os testes ou o build do site falharam.", saida)
            commits = self._git("rev-list", "--reverse", "origin/main..HEAD", cwd=wt).stdout.split()
            push = self._git("push", "origin", "HEAD:main", cwd=wt, check=False)
            if push.returncode == 0:
                self._git("fetch", "origin", cwd=wt)
                return commits
            if "rejected" not in push.stderr and "fetch first" not in push.stderr:
                raise PublishError(f"O push falhou: {push.stderr.strip()}")
        raise PublishError("O site mudou várias vezes seguidas durante a publicação. Tente de novo em instantes.")

    # ---------- registro e desfazer ----------

    def _publicacoes(self) -> list[dict]:
        return read_json(self.log_path, [])

    def _registra(self, pub: Publicacao) -> None:
        pubs = self._publicacoes()
        pubs.append(asdict(pub))
        write_json(self.log_path, pubs)

    def publicacoes(self) -> list[Publicacao]:
        return [Publicacao(**p) for p in self._publicacoes()]

    def ultima_publicacao_da_data(self, data_pelada: str) -> Publicacao | None:
        pubs = [p for p in self.publicacoes() if p.data_pelada == data_pelada and p.tipo != "desfazer"]
        return pubs[-1] if pubs else None

    def desfaziveis(self, user_id: int, is_admin: bool, limite: int = 10) -> list[Publicacao]:
        pubs = [
            p for p in self.publicacoes()
            if p.tipo != "desfazer" and p.desfeita_por is None and (is_admin or p.autor_id == user_id)
        ]
        return list(reversed(pubs))[:limite]

    def desfazer(self, pub_id: str, autor: Pessoa, is_admin: bool) -> Publicacao:
        with self._lock:
            pub = next((p for p in self.publicacoes() if p.id == pub_id), None)
            if pub is None or pub.tipo == "desfazer":
                raise PublishError("Publicação não encontrada.")
            if not is_admin and pub.autor_id != autor.id:
                raise SemPermissaoError("Você só pode desfazer as suas próprias publicações.")
            if pub.desfeita_por:
                raise PublishError("Essa publicação já foi desfeita.")

            wt = self.create_worktree(f"desfazer-{pub_id}")
            try:
                for commit in reversed(pub.commits):
                    r = self._git("revert", "--no-commit", commit, cwd=wt, check=False)
                    if r.returncode != 0:
                        raise ConflitoError(
                            "Uma publicação posterior mudou os mesmos arquivos, então essa não pode ser "
                            "desfeita automaticamente. Peça ao admin para resolver."
                        )
                verbo = "o cadastro" if pub.tipo == "cadastro" else "a correção"
                self._git(
                    "commit", "-m", f"Desfaz {verbo} da pelada de {pub.data_pelada}",
                    "-m", f"Desfeito pelo bot de Telegram por {autor.nome}. Reverte {', '.join(pub.commits)}.",
                    cwd=wt,
                )
                try:
                    commits = self._push_com_rebase(wt)
                except VerificacaoError as e:
                    raise VerificacaoError(
                        "Desfazer essa publicação quebraria o site, provavelmente porque uma publicação "
                        "posterior depende dela (por exemplo, usa um jogador cadastrado nela).",
                        e.saida,
                    ) from e
            finally:
                self.remove_worktree(wt)

            nova = Publicacao(
                id=uuid.uuid4().hex[:8],
                tipo="desfazer",
                data_pelada=pub.data_pelada,
                commits=commits,
                autor_id=autor.id,
                autor_nome=autor.nome,
                publicado_em=agora().isoformat(timespec="seconds"),
                desfaz=pub.id,
            )
            pubs = self._publicacoes()
            for p in pubs:
                if p["id"] == pub.id:
                    p["desfeita_por"] = nova.id
            pubs.append(asdict(nova))
            write_json(self.log_path, pubs)
            return nova

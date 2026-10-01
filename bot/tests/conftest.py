import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

BOT_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = BOT_DIR.parent
sys.path.insert(0, str(BOT_DIR))

from access import Pessoa  # noqa: E402
from publish import Repo  # noqa: E402

ORGANIZADOR = Pessoa(111, "Fulano", "fulano")
OUTRO = Pessoa(222, "Beltrano", None)
ADMIN = Pessoa(999, "Admin", "admin")


def git(*args, cwd):
    return subprocess.run(
        ["git", "-c", "user.name=Teste", "-c", "user.email=teste@example.com", *args],
        cwd=cwd, check=True, capture_output=True, text=True,
    ).stdout


@pytest.fixture(scope="session")
def seed_origin(tmp_path_factory) -> Path:
    """Repositório bare com uma cópia dos arquivos atuais do projeto (sem o bot)."""
    base = tmp_path_factory.mktemp("seed")
    work = base / "work"
    arquivos = subprocess.run(
        ["git", "ls-files", "-co", "--exclude-standard"],
        cwd=PROJECT_DIR, check=True, capture_output=True, text=True,
    ).stdout.splitlines()
    for rel in arquivos:
        if rel.startswith(("bot/", "original/", "docs/")):
            continue
        src = PROJECT_DIR / rel
        if not src.is_file():
            continue
        dst = work / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    git("init", "-q", "-b", "main", cwd=work)
    git("add", "-A", cwd=work)
    git("commit", "-q", "-m", "Estado inicial", cwd=work)
    bare = base / "origin.git"
    git("clone", "-q", "--bare", str(work), str(bare), cwd=base)
    return bare


@pytest.fixture
def origin(seed_origin, tmp_path) -> Path:
    copia = tmp_path / "origin.git"
    shutil.copytree(seed_origin, copia)
    return copia


@pytest.fixture
def repo(origin, tmp_path) -> Repo:
    r = Repo(
        url=str(origin),
        volume_dir=tmp_path / "volume",
        author_name="Pelada Bot",
        author_email="bot@example.com",
    )
    r.ensure_clone()
    return r


@pytest.fixture
def outro_clone(origin, tmp_path):
    """Simula alguém publicando por fora do bot (por exemplo, o admin no Claude Code)."""
    path = tmp_path / "outro"
    git("clone", "-q", str(origin), str(path), cwd=tmp_path)

    def publica(rel: str, conteudo: str, msg: str = "Mudança externa"):
        git("pull", "-q", "--rebase", cwd=path)
        alvo = path / rel
        alvo.parent.mkdir(parents=True, exist_ok=True)
        alvo.write_text(conteudo, encoding="utf-8")
        git("add", rel, cwd=path)
        git("commit", "-q", "-m", msg, cwd=path)
        git("push", "-q", "origin", "HEAD:main", cwd=path)

    return publica


def pelada(data: str, trocar: dict[str, str] | None = None) -> str:
    """Uma pelada válida, copiada da de 2026-09-27, com outra data e nomes opcionalmente trocados."""
    texto = (PROJECT_DIR / "data" / "2026-09-27.json").read_text(encoding="utf-8")
    for antigo, novo in (trocar or {}).items():
        texto = texto.replace(f'"{antigo}"', f'"{novo}"')
    dados = json.loads(texto)
    dados["date"] = data
    return json.dumps(dados, ensure_ascii=False, indent=2) + "\n"


def arquivos_no_main(origin: Path) -> set[str]:
    return set(git("ls-tree", "-r", "--name-only", "main", cwd=origin).splitlines())


def mensagens_no_main(origin: Path) -> list[str]:
    return git("log", "--format=%s", "main", cwd=origin).splitlines()

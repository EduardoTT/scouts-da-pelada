"""Configuração do bot, lida de variáveis de ambiente e, localmente, de bot/.env."""

import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

BOT_DIR = Path(__file__).resolve().parent
FUSO = ZoneInfo("America/Sao_Paulo")


def agora() -> datetime:
    """Hora atual em Brasília, independente do fuso do container."""
    return datetime.now(FUSO)


def load_dotenv(path: Path = BOT_DIR / ".env") -> None:
    """Carrega KEY=VALUE do arquivo sem sobrescrever o que já está no ambiente."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))


@dataclass(frozen=True)
class Config:
    telegram_token: str
    admin_id: int
    repo_url: str
    volume_dir: Path
    deploy_key: str | None
    deploy_key_file: Path | None
    model: str
    max_budget_usd: float
    max_turns: int
    git_author_name: str
    git_author_email: str
    site_url: str

    @classmethod
    def from_env(cls) -> "Config":
        load_dotenv()
        env = os.environ
        key_file = env.get("GITHUB_DEPLOY_KEY_FILE")
        return cls(
            # Localmente o bot/.env tem o token do bot de testes, que tem prioridade.
            # No Railway essa variável não existe, e vale o token de produção.
            telegram_token=env.get("TELEGRAM_DEV_BOT_TOKEN") or env["TELEGRAM_BOT_TOKEN"],
            admin_id=int(env["ADMIN_TELEGRAM_ID"]),
            repo_url=env["REPO_SSH_URL"],
            volume_dir=Path(env.get("VOLUME_DIR", BOT_DIR / ".volume")).expanduser(),
            deploy_key=env.get("GITHUB_DEPLOY_KEY") or None,
            deploy_key_file=Path(key_file).expanduser() if key_file else None,
            model=env.get("CLAUDE_MODEL", "claude-opus-5-5"),
            max_budget_usd=float(env.get("MAX_BUDGET_USD", "2.0")),
            max_turns=int(env.get("MAX_TURNS", "60")),
            git_author_name=env.get("GIT_AUTHOR_NAME", "Pelada Bot"),
            git_author_email=env.get("GIT_AUTHOR_EMAIL", "pelada-bot@users.noreply.github.com"),
            site_url=env.get("SITE_URL", "https://eduardott.github.io/scouts-da-pelada/"),
        )

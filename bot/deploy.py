"""Espera o GitHub Pages publicar o commit, consultando a API pública do GitHub Actions."""

import asyncio
import json
import logging
import re
import urllib.error
import urllib.request

log = logging.getLogger(__name__)
REPO = re.compile(r"github\.com[:/]([^/]+)/([^/.]+?)(?:\.git)?$")


def _runs(dono: str, nome: str, sha: str) -> list[dict] | None:
    url = f"https://api.github.com/repos/{dono}/{nome}/actions/runs?head_sha={sha}"
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.load(r).get("workflow_runs", [])
    except urllib.error.HTTPError as e:
        if e.code == 404:  # repo privado, como o de teste
            return None
        raise


async def espera_deploy(repo_url: str, sha: str, limite_s: int = 600, intervalo_s: int = 15) -> bool | None:
    """True se o deploy terminou com sucesso, False se falhou, None se não deu para saber."""
    m = REPO.search(repo_url)
    if not m:
        return None
    dono, nome = m.groups()
    for _ in range(max(1, limite_s // intervalo_s)):
        try:
            runs = await asyncio.to_thread(_runs, dono, nome, sha)
        except Exception:
            log.exception("erro ao consultar o deploy")
            return None
        if runs is None:
            return None
        if runs and all(r["status"] == "completed" for r in runs):
            return all(r["conclusion"] == "success" for r in runs)
        await asyncio.sleep(intervalo_s)
    return None

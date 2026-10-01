import asyncio
import json
import os

import pytest

import jogadores
from conftest import ORGANIZADOR, OUTRO, PROJECT_DIR, pelada
from tools import Sessao, criar_ferramentas, criar_hook, impressao_digital, verifica_rascunho


def roda(coro):
    return asyncio.run(coro)


@pytest.fixture
def wt(repo):
    return repo.create_worktree("chat-1")


@pytest.fixture
def sessao(wt):
    return Sessao(chat_id=1, organizador=ORGANIZADOR, wt=wt)


@pytest.fixture
def chama(sessao, repo):
    outras = []
    ferramentas = {t.name: t for t in criar_ferramentas(sessao, repo, lambda: outras)}

    def _chama(ferramenta, **args):
        r = roda(ferramentas[ferramenta].handler(args))
        return r["content"][0]["text"], bool(r.get("is_error"))

    _chama.outras = outras
    return _chama


# ---------- hook ----------

def decide(hook, ferramenta, **entrada):
    r = roda(hook({"hook_event_name": "PreToolUse", "tool_name": ferramenta, "tool_input": entrada}, None, None))
    return r.get("hookSpecificOutput", {}).get("permissionDecision", "allow")


def test_hook_deixa_escrever_so_json_de_pelada(wt):
    hook = criar_hook(wt)
    assert decide(hook, "Write", file_path=str(wt / "data/2026-10-04.json")) == "allow"
    assert decide(hook, "Write", file_path="data/2026-10-04.json") == "allow"
    assert decide(hook, "Edit", file_path=str(wt / "data/2026-09-27.json")) == "allow"
    for proibido in ["players.json", "build.py", "data/x.json", "data/2026-10-04.json.bak",
                     "tests/test_data.py", ".git/config", "/etc/passwd", "../repo/players.json",
                     "data/../build.py"]:
        alvo = proibido if proibido.startswith("/") else str(wt / proibido)
        assert decide(hook, "Write", file_path=alvo) == "deny", proibido
        assert decide(hook, "Edit", file_path=alvo) == "deny", proibido


def test_hook_nega_link_simbolico_para_fora(wt, tmp_path):
    fora = tmp_path / "segredo.json"
    fora.write_text("{}")
    os.symlink(fora, wt / "data" / "2026-10-04.json")
    hook = criar_hook(wt)
    assert decide(hook, "Write", file_path=str(wt / "data/2026-10-04.json")) == "deny"
    assert decide(hook, "Read", file_path=str(wt / "data/2026-10-04.json")) == "deny"


def test_hook_limita_leitura_ao_worktree(wt):
    hook = criar_hook(wt)
    assert decide(hook, "Read", file_path=str(wt / "players.json")) == "allow"
    assert decide(hook, "Read", file_path="data/2026-09-27.json") == "allow"
    assert decide(hook, "Read", file_path=str(wt.parent.parent / "publicacoes.json")) == "deny"
    assert decide(hook, "Read", file_path="~/.ssh/id_ed25519") == "deny"
    assert decide(hook, "Read", file_path="/etc/passwd") == "deny"
    assert decide(hook, "Glob", pattern="data/*.json") == "allow"
    assert decide(hook, "Glob", pattern="/etc/*") == "deny"
    assert decide(hook, "Glob", pattern="../*") == "deny"
    assert decide(hook, "Grep", pattern="Wesley", path="data") == "allow"
    assert decide(hook, "Grep", pattern="x", path="/") == "deny"


def test_hook_nega_ferramentas_fora_da_lista(wt):
    hook = criar_hook(wt)
    for nome in ["Bash", "WebFetch", "WebSearch", "Agent", "NotebookEdit", "mcp__outro__x"]:
        assert decide(hook, nome) == "deny", nome
    assert decide(hook, "mcp__pelada__buscar_jogador", nome="Giga") == "allow"


# ---------- ferramentas de jogadores ----------

def test_buscar_jogador_acha_apelido_e_parecidos(chama):
    texto, erro = chama("buscar_jogador", nome="Júnior")
    assert not erro and "Junior" in texto and "Bate exatamente com o apelido de Junior" in texto
    texto, _ = chama("buscar_jogador", nome="Fabjnho")
    assert "Fabinho" in texto


def test_buscar_jogador_avisa_nome_ambiguo(chama):
    texto, _ = chama("buscar_jogador", nome="Pedro")
    assert "mais de um jogador" in texto and "Pedro Cabeludo" in texto


def test_adicionar_jogador_fixo_e_convidado(chama, wt):
    texto, erro = chama("adicionar_jogador", nome="Zé Novo", convidado=False)
    assert not erro
    texto, erro = chama("adicionar_jogador", nome="Beto Conv", convidado=True, apelidos=["Beto"])
    assert not erro
    dados = jogadores.carrega(wt / "players.json")
    assert dados["Zé Novo"] == ["Zé Novo"]
    assert dados["Beto Conv"] == ["Beto Conv", "Beto conv", "Beto convidado", "Beto"]


def test_adicionar_jogador_recusa_nome_ou_apelido_existente(chama, wt):
    antes = (wt / "players.json").read_text()
    _, erro = chama("adicionar_jogador", nome="Giga", convidado=False)
    assert erro
    _, erro = chama("adicionar_jogador", nome="Novo", convidado=False, apelidos=["Gigante"])
    assert erro
    _, erro = chama("adicionar_jogador", nome="leo", convidado=False)  # "Leo" já é do Léo Negão
    assert erro
    assert (wt / "players.json").read_text() == antes


def test_adicionar_apelido(chama, wt):
    _, erro = chama("adicionar_apelido", jogador="Giga", apelido="Gigão")
    assert not erro
    assert "Gigão" in jogadores.carrega(wt / "players.json")["Giga"]
    _, erro = chama("adicionar_apelido", jogador="Giga", apelido="Wesley")
    assert erro
    _, erro = chama("adicionar_apelido", jogador="Ninguém", apelido="X")
    assert erro


def test_gravacao_do_bot_igual_a_do_players_py(tmp_path):
    import importlib.util

    spec = importlib.util.spec_from_file_location("players_raiz", PROJECT_DIR / "players.py")
    players_raiz = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(players_raiz)
    dados = jogadores.carrega(PROJECT_DIR / "players.json")
    jogadores.grava(tmp_path / "a.json", dados)
    players_raiz.save_players(dados, tmp_path / "b.json")
    assert (tmp_path / "a.json").read_text() == (tmp_path / "b.json").read_text()


# ---------- consultar_data ----------

def test_consultar_data_livre(chama, sessao):
    texto, _ = chama("consultar_data", data="2026-10-04")
    assert "Não há pelada publicada" in texto
    assert sessao.data == "2026-10-04"


def test_consultar_data_publicada_e_em_cadastro(chama):
    chama.outras.append(Sessao(chat_id=2, organizador=OUTRO, wt=PROJECT_DIR, data="2026-09-27"))
    texto, _ = chama("consultar_data", data="2026-09-27")
    assert "Já existe pelada publicada em 2026-09-27" in texto
    assert "Beltrano está cadastrando" in texto


def test_consultar_data_nao_acusa_a_propria_sessao(chama, sessao):
    chama.outras.append(sessao)
    sessao.data = "2026-10-04"
    texto, _ = chama("consultar_data", data="2026-10-04")
    assert "está cadastrando" not in texto


def test_consultar_data_mostra_quem_publicou(chama, repo):
    wt2 = repo.create_worktree("chat-9")
    (wt2 / "data/2026-10-04.json").write_text(pelada("2026-10-04"), encoding="utf-8")
    repo.publish(wt2, "2026-10-04", "cadastro", OUTRO)
    texto, _ = chama("consultar_data", data="2026-10-04")
    assert "por Beltrano" in texto


# ---------- verificação e resumo ----------

def test_verificar_rascunho_valido(chama, wt):
    (wt / "data/2026-10-04.json").write_text(pelada("2026-10-04"), encoding="utf-8")
    texto, erro = chama("verificar_rascunho", data="2026-10-04")
    assert not erro, texto


def test_verificar_rascunho_com_jogador_fora_do_cadastro(chama, wt):
    (wt / "data/2026-10-04.json").write_text(pelada("2026-10-04", {"Landir": "Zé Ninguém"}), encoding="utf-8")
    texto, erro = chama("verificar_rascunho", data="2026-10-04")
    assert erro and "Zé Ninguém" in texto


def test_verificar_rascunho_com_json_quebrado(chama, wt):
    (wt / "data/2026-10-04.json").write_text("{", encoding="utf-8")
    texto, erro = chama("verificar_rascunho", data="2026-10-04")
    assert erro and "não é um JSON válido" in texto


def test_apresentar_resumo_marca_pronto(chama, wt, sessao):
    (wt / "data/2026-10-04.json").write_text(pelada("2026-10-04"), encoding="utf-8")
    _, erro = chama("apresentar_resumo", data="2026-10-04")
    assert not erro
    assert sessao.pronto == "2026-10-04" and sessao.resumo_pendente
    assert sessao.impressao == impressao_digital(wt, "2026-10-04")


def test_apresentar_resumo_recusa_com_erro(chama, wt, sessao):
    dados = json.loads(pelada("2026-10-04"))
    dados["games"][0]["team_out"] = "blue"  # azul venceu o jogo 1, não pode ter saído
    (wt / "data/2026-10-04.json").write_text(json.dumps(dados), encoding="utf-8")
    texto, erro = chama("apresentar_resumo", data="2026-10-04")
    assert erro and "o vermelho perdeu" in texto
    assert sessao.pronto is None


def test_verifica_rascunho_recusa_data_mal_formada(sessao, repo):
    ok, texto = verifica_rascunho(sessao, repo, "../build")
    assert not ok and "AAAA-MM-DD" in texto


def test_desfazer_jogador_novo_so_vale_para_o_rascunho(chama, wt):
    chama("adicionar_jogador", nome="Gustavo", convidado=True)
    _, erro = chama("desfazer_jogador_novo", nome="Gustavo Conv")
    assert not erro
    assert "Gustavo Conv" not in jogadores.carrega(wt / "players.json")
    _, erro = chama("desfazer_jogador_novo", nome="Giga")
    assert erro and "Giga" in jogadores.carrega(wt / "players.json")

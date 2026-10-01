import json

import pytest

from conftest import ADMIN, ORGANIZADOR, OUTRO, arquivos_no_main, mensagens_no_main, pelada
from publish import ConflitoError, PublishError, SemPermissaoError, VerificacaoError, mensagem_players


def escreve(wt, rel, conteudo):
    (wt / rel).write_text(conteudo, encoding="utf-8")


def adiciona_jogador(wt, nome):
    path = wt / "players.json"
    dados = json.loads(path.read_text(encoding="utf-8"))
    dados[nome] = [nome]
    # Mesmo formato do players.save_players: um jogador por linha.
    linhas = [f"  {json.dumps(k, ensure_ascii=False)}: {json.dumps(v, ensure_ascii=False)}" for k, v in dados.items()]
    path.write_text("{\n" + ",\n".join(linhas) + "\n}\n", encoding="utf-8")


def test_publica_pelada_nova(repo, origin):
    wt = repo.create_worktree("chat-1")
    escreve(wt, "data/2026-10-04.json", pelada("2026-10-04"))

    pub = repo.publish(wt, "2026-10-04", "cadastro", ORGANIZADOR)

    assert "data/2026-10-04.json" in arquivos_no_main(origin)
    assert mensagens_no_main(origin)[0] == "Cadastra a pelada de 2026-10-04"
    assert len(pub.commits) == 1
    assert repo.publicacoes()[-1].autor_id == ORGANIZADOR.id
    assert repo.published_dates() >= {"2026-10-04", "2026-09-27"}


def test_jogador_novo_vai_num_commit_anterior_ao_da_pelada(repo, origin):
    wt = repo.create_worktree("chat-1")
    adiciona_jogador(wt, "Zé Novo")
    escreve(wt, "data/2026-10-04.json", pelada("2026-10-04", {"Landir": "Zé Novo"}))

    pub = repo.publish(wt, "2026-10-04", "cadastro", ORGANIZADOR)

    assert mensagens_no_main(origin)[:2] == [
        "Cadastra a pelada de 2026-10-04",
        "Cadastra o Zé Novo no players.json",
    ]
    assert len(pub.commits) == 2


def test_correcao_usa_outra_mensagem(repo, origin):
    wt = repo.create_worktree("chat-1")
    escreve(wt, "data/2026-09-27.json", pelada("2026-09-27").replace('"referee": ""', '"referee": "Robson"'))

    repo.publish(wt, "2026-09-27", "correcao", ORGANIZADOR)

    assert mensagens_no_main(origin)[0] == "Corrige a pelada de 2026-09-27"


def test_recusa_arquivo_fora_de_data_e_players(repo, origin):
    wt = repo.create_worktree("chat-1")
    escreve(wt, "data/2026-10-04.json", pelada("2026-10-04"))
    escreve(wt, "build.py", "print('invadido')\n")
    antes = mensagens_no_main(origin)

    with pytest.raises(PublishError, match="build.py"):
        repo.publish(wt, "2026-10-04", "cadastro", ORGANIZADOR)

    assert mensagens_no_main(origin) == antes


def test_recusa_quando_nao_ha_mudanca(repo):
    wt = repo.create_worktree("chat-1")
    with pytest.raises(PublishError, match="Não há nenhuma mudança"):
        repo.publish(wt, "2026-10-04", "cadastro", ORGANIZADOR)


def test_teste_falhando_nao_publica_e_devolve_o_rascunho(repo, origin):
    wt = repo.create_worktree("chat-1")
    escreve(wt, "data/2026-10-04.json", pelada("2026-10-04", {"Landir": "Desconhecido"}))
    antes = mensagens_no_main(origin)

    with pytest.raises(VerificacaoError) as erro:
        repo.publish(wt, "2026-10-04", "cadastro", ORGANIZADOR)

    assert "Desconhecido" in erro.value.saida
    assert mensagens_no_main(origin) == antes
    assert repo.changed_files(wt) == ["data/2026-10-04.json"]
    assert repo.publicacoes() == []


def test_main_mudou_durante_o_cadastro_faz_rebase(repo, origin, outro_clone):
    wt = repo.create_worktree("chat-1")
    escreve(wt, "data/2026-10-04.json", pelada("2026-10-04"))
    outro_clone("data/2026-10-11.json", pelada("2026-10-11"), "Cadastra a pelada de 2026-10-11")

    repo.publish(wt, "2026-10-04", "cadastro", ORGANIZADOR)

    assert {"data/2026-10-04.json", "data/2026-10-11.json"} <= arquivos_no_main(origin)


def test_conflito_no_mesmo_arquivo_devolve_o_rascunho(repo, origin):
    wt1 = repo.create_worktree("chat-1")
    wt2 = repo.create_worktree("chat-2")
    escreve(wt1, "data/2026-09-27.json", pelada("2026-09-27").replace('"referee": ""', '"referee": "Robson"'))
    escreve(wt2, "data/2026-09-27.json", pelada("2026-09-27").replace('"referee": ""', '"referee": "Outro"'))
    repo.publish(wt1, "2026-09-27", "correcao", ORGANIZADOR)

    with pytest.raises(ConflitoError):
        repo.publish(wt2, "2026-09-27", "correcao", OUTRO)

    assert repo.changed_files(wt2) == ["data/2026-09-27.json"]
    assert mensagens_no_main(origin)[0] == "Corrige a pelada de 2026-09-27"


def test_desfazer_reverte_e_marca_a_publicacao(repo, origin):
    wt = repo.create_worktree("chat-1")
    escreve(wt, "data/2026-10-04.json", pelada("2026-10-04"))
    pub = repo.publish(wt, "2026-10-04", "cadastro", ORGANIZADOR)

    desfeita = repo.desfazer(pub.id, ORGANIZADOR, is_admin=False)

    assert "data/2026-10-04.json" not in arquivos_no_main(origin)
    assert mensagens_no_main(origin)[0] == "Desfaz o cadastro da pelada de 2026-10-04"
    assert desfeita.desfaz == pub.id
    assert repo.publicacoes()[0].desfeita_por == desfeita.id
    assert repo.desfaziveis(ORGANIZADOR.id, is_admin=False) == []
    with pytest.raises(PublishError, match="já foi desfeita"):
        repo.desfazer(pub.id, ORGANIZADOR, is_admin=False)


def test_so_o_autor_ou_o_admin_desfazem(repo, origin):
    wt = repo.create_worktree("chat-1")
    escreve(wt, "data/2026-10-04.json", pelada("2026-10-04"))
    pub = repo.publish(wt, "2026-10-04", "cadastro", ORGANIZADOR)

    assert repo.desfaziveis(OUTRO.id, is_admin=False) == []
    assert [p.id for p in repo.desfaziveis(ADMIN.id, is_admin=True)] == [pub.id]
    with pytest.raises(SemPermissaoError):
        repo.desfazer(pub.id, OUTRO, is_admin=False)

    repo.desfazer(pub.id, ADMIN, is_admin=True)
    assert "data/2026-10-04.json" not in arquivos_no_main(origin)


def test_desfazer_recusa_quando_publicacao_posterior_depende(repo, origin):
    wt = repo.create_worktree("chat-1")
    adiciona_jogador(wt, "Zé Novo")
    escreve(wt, "data/2026-10-04.json", pelada("2026-10-04", {"Landir": "Zé Novo"}))
    primeira = repo.publish(wt, "2026-10-04", "cadastro", ORGANIZADOR)
    wt = repo.create_worktree("chat-1")
    escreve(wt, "data/2026-10-11.json", pelada("2026-10-11", {"Landir": "Zé Novo"}))
    repo.publish(wt, "2026-10-11", "cadastro", OUTRO)
    antes = mensagens_no_main(origin)

    with pytest.raises(VerificacaoError, match="publicação posterior depende"):
        repo.desfazer(primeira.id, ORGANIZADOR, is_admin=False)

    assert mensagens_no_main(origin) == antes
    assert repo.publicacoes()[0].desfeita_por is None


@pytest.mark.parametrize(
    "antes, depois, esperado",
    [
        ({"A": ["A"]}, {"A": ["A"], "B": ["B"]}, "Cadastra o B no players.json"),
        ({}, {"B": ["B"], "C": ["C"]}, "Cadastra B e C no players.json"),
        ({"A": ["A"]}, {"A": ["A", "a"]}, "Adiciona apelidos de A no players.json"),
        ({"A": ["A"]}, {"A": ["A", "a"], "B": ["B"]}, "Atualiza o players.json: cadastra B e adiciona apelidos de A"),
    ],
)
def test_mensagem_players(antes, depois, esperado):
    assert mensagem_players(antes, depois) == esperado

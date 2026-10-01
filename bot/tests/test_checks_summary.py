import json

import pytest

from checks import verificar
from conftest import pelada
from summary import dividir, resumo


@pytest.fixture
def dados():
    return json.loads(pelada("2026-10-04"))


def erros(d, publicadas=frozenset(), nova=True, nome="2026-10-04"):
    return verificar(d, nome, set(publicadas), nova).erros


def avisos(d):
    return verificar(d, "2026-10-04", set(), True).avisos


def test_pelada_valida_nao_tem_erro(dados):
    assert erros(dados) == []


def test_data_ja_publicada_so_e_erro_em_cadastro_novo(dados):
    assert any("Já existe" in e for e in erros(dados, {"2026-10-04"}))
    assert erros(dados, {"2026-10-04"}, nova=False) == []


def test_data_do_campo_diferente_do_arquivo(dados):
    assert any("não bate com o nome do arquivo" in e for e in erros(dados, nome="2026-10-11"))


def test_numeracao_fora_de_sequencia(dados):
    dados["games"][2]["game_number"] = 2
    assert any("sequência" in e for e in erros(dados))


def test_team_out_invalido(dados):
    dados["games"][0]["team_out"] = "green"
    assert any('"team_out" precisa ser' in e for e in erros(dados))


def test_team_out_apontando_o_vencedor(dados):
    dados["games"][0]["team_out"] = "blue"  # azul venceu por 2 x 0
    assert any("o vermelho perdeu" in e for e in erros(dados))


def test_both_em_jogo_com_vencedor(dados):
    dados["games"][0]["team_out"] = "both"
    assert any("o vermelho perdeu" in e for e in erros(dados))


def test_empate_no_jogo_1_nao_pode_sair_os_dois(dados):
    dados["games"][0]["score"] = {"blue": 0, "red": 0}
    dados["games"][0]["goals"] = []
    dados["games"][0]["team_out"] = "both"
    assert any("pênaltis" in e for e in erros(dados))


def test_jogador_nos_dois_times(dados):
    dados["games"][0]["red_team"].append({"name": "Denis", "role": "player"})
    assert any("aparece nos dois times" in e for e in erros(dados))


def test_estrutura_quebrada(dados):
    del dados["games"][0]["score"]
    assert erros(dados)
    assert erros({"date": "2026-10-04"})
    assert erros([])


def test_time_com_5_ou_7_e_aviso_nao_erro(dados):
    dados["games"][0]["blue_team"].pop()
    dados["games"][1]["red_team"].append({"name": "Fulano", "role": "player"})
    assert not [e for e in erros(dados) if "jogadores" in e]
    assert sum("jogadores (o normal é 6)" in a for a in avisos(dados)) == 2


def test_time_que_saiu_voltando_inteiro_e_aviso(dados):
    dados["games"][1]["red_team"] = list(dados["games"][0]["red_team"])  # vermelho saiu no jogo 1
    assert any("exatamente o time que saiu" in a for a in avisos(dados))


def test_resumo_tem_jogos_gols_e_novidades(dados):
    texto = resumo(dados, jogadores_novos=["Landir"], apelidos_novos={"Claudio": ["Cláudio"]})
    assert texto.startswith("Pelada de 04/10/2026 (domingo)")
    assert "Juiz: não informado" in texto
    assert "Jogo 6: Azul 3 x 1 Vermelho. Saiu: vermelho." in texto
    assert "Wesley (gol)" in texto
    assert "Denis 3 (azul)" in texto
    assert "Jogadores novos no cadastro: Landir" in texto
    assert "Claudio: Cláudio" in texto


def test_resumo_de_correcao_lista_o_que_muda(dados):
    novo = json.loads(json.dumps(dados))
    novo["referee"] = "Robson"
    novo["games"][2]["goals"][0]["count"] = 2
    texto = resumo(novo, anterior=dados)
    assert texto.startswith("Correção da pelada")
    assert "O que muda: juiz (vazio para Robson), jogo 3" in texto


def test_resumo_mostra_gol_contra(dados):
    dados["games"][0]["goals"].append({"player": "Giga", "team": "blue", "count": 1, "own_goal": True})
    assert "Giga (contra, a favor do azul)" in resumo(dados)


def test_dividir_respeita_limite_e_paragrafos():
    texto = "\n\n".join(f"bloco {i} " + "x" * 50 for i in range(40))
    partes = dividir(texto, limite=300)
    assert all(len(p) <= 300 for p in partes)
    assert "\n\n".join(partes) == texto
    assert dividir("curto") == ["curto"]
    assert all(len(p) <= 100 for p in dividir("y" * 250, limite=100))

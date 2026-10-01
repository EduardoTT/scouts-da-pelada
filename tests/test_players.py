"""O players.json é lido e gravado pelo players.py, inclusive pelo bot."""

import json

from players import PLAYERS_FILE, load_players, save_players


def test_gravar_sem_mudancas_mantem_o_arquivo_identico(tmp_path):
    """Gravar o cadastro sem mudanças não pode gerar diff no git."""
    copia = tmp_path / "players.json"
    save_players(load_players(), copia)
    with open(PLAYERS_FILE, encoding="utf-8") as original:
        assert copia.read_text(encoding="utf-8") == original.read()


def test_gravar_preserva_ordem_e_acentos(tmp_path):
    copia = tmp_path / "players.json"
    dados = {"Júnior": ["Júnior", "JR"], "Ánderson": ["Ánderson"]}
    save_players(dados, copia)
    assert list(load_players(copia)) == ["Júnior", "Ánderson"]
    assert "Júnior" in copia.read_text(encoding="utf-8")
    assert json.loads(copia.read_text(encoding="utf-8")) == dados


def test_cadastro_e_um_dicionario_de_listas_de_texto():
    for nome, apelidos in load_players().items():
        assert isinstance(nome, str) and nome
        assert isinstance(apelidos, list) and apelidos
        assert all(isinstance(a, str) and a for a in apelidos)

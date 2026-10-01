import time
from datetime import datetime, timedelta, timezone

import pytest

from access import AccessStore, Pessoa
from config import FUSO, agora

ADMIN_ID = 999
FULANO = Pessoa(111, "Fulano", "fulano")


@pytest.fixture
def store(tmp_path):
    return AccessStore(tmp_path / "organizadores.json", ADMIN_ID)


def test_admin_tem_acesso_sem_estar_na_lista(store):
    assert store.is_admin(ADMIN_ID)
    assert store.is_allowed(ADMIN_ID)
    assert store.organizers() == []


def test_desconhecido_nao_tem_acesso(store):
    assert not store.is_allowed(FULANO.id)


def test_pedido_aprovado_libera_acesso(store):
    assert store.request(FULANO)
    assert store.is_pending(FULANO.id)
    assert not store.is_allowed(FULANO.id)

    assert store.approve(FULANO.id) == FULANO
    assert store.is_allowed(FULANO.id)
    assert not store.is_pending(FULANO.id)
    assert store.organizers() == [FULANO]


def test_pedido_repetido_nao_duplica(store):
    assert store.request(FULANO)
    assert not store.request(FULANO)
    store.approve(FULANO.id)
    assert not store.request(FULANO)


def test_pedido_recusado_nao_libera(store):
    store.request(FULANO)
    assert store.reject(FULANO.id) == FULANO
    assert not store.is_allowed(FULANO.id)
    assert not store.is_pending(FULANO.id)


def test_aprovar_sem_pedido_nao_faz_nada(store):
    assert store.approve(FULANO.id) is None
    assert not store.is_allowed(FULANO.id)


def test_remover_organizador(store):
    store.request(FULANO)
    store.approve(FULANO.id)
    assert store.remove(FULANO.id) == FULANO
    assert not store.is_allowed(FULANO.id)


def test_acesso_sobrevive_a_nova_instancia(tmp_path):
    AccessStore(tmp_path / "o.json", ADMIN_ID).request(FULANO)
    AccessStore(tmp_path / "o.json", ADMIN_ID).approve(FULANO.id)
    assert AccessStore(tmp_path / "o.json", ADMIN_ID).is_allowed(FULANO.id)


def test_agora_usa_brasilia_mesmo_com_relogio_em_utc(monkeypatch):
    monkeypatch.setenv("TZ", "UTC")
    time.tzset()
    try:
        hora = agora()
        assert hora.utcoffset() == timedelta(hours=-3)
        esperado = datetime.now(timezone.utc).astimezone(FUSO)
        assert abs((hora - esperado).total_seconds()) < 5
    finally:
        monkeypatch.undo()
        time.tzset()

"""Quem pode falar com o bot: o admin fixo e os organizadores que ele aprovou."""

import threading
from dataclasses import dataclass
from pathlib import Path

from config import agora
from storage import read_json, write_json


@dataclass(frozen=True)
class Pessoa:
    id: int
    nome: str
    username: str | None

    @property
    def descricao(self) -> str:
        return f"{self.nome} (@{self.username})" if self.username else self.nome


class AccessStore:
    """Organizadores aprovados e pedidos pendentes, em organizadores.json no volume."""

    def __init__(self, path: Path, admin_id: int):
        self.path = path
        self.admin_id = admin_id
        self._lock = threading.Lock()

    def _load(self) -> dict:
        return read_json(self.path, {"organizadores": {}, "pendentes": {}})

    def is_admin(self, user_id: int) -> bool:
        return user_id == self.admin_id

    def is_allowed(self, user_id: int) -> bool:
        return self.is_admin(user_id) or str(user_id) in self._load()["organizadores"]

    def is_pending(self, user_id: int) -> bool:
        return str(user_id) in self._load()["pendentes"]

    def request(self, pessoa: Pessoa) -> bool:
        """Registra o pedido. Devolve False se já havia pedido ou acesso."""
        with self._lock:
            data = self._load()
            key = str(pessoa.id)
            if key in data["organizadores"] or key in data["pendentes"]:
                return False
            data["pendentes"][key] = {
                "nome": pessoa.nome,
                "username": pessoa.username,
                "pedido_em": agora().isoformat(timespec="seconds"),
            }
            write_json(self.path, data)
            return True

    def approve(self, user_id: int) -> Pessoa | None:
        with self._lock:
            data = self._load()
            pedido = data["pendentes"].pop(str(user_id), None)
            if pedido is None:
                return None
            data["organizadores"][str(user_id)] = {
                "nome": pedido["nome"],
                "username": pedido["username"],
                "aprovado_em": agora().isoformat(timespec="seconds"),
            }
            write_json(self.path, data)
            return Pessoa(user_id, pedido["nome"], pedido["username"])

    def reject(self, user_id: int) -> Pessoa | None:
        with self._lock:
            data = self._load()
            pedido = data["pendentes"].pop(str(user_id), None)
            if pedido is None:
                return None
            write_json(self.path, data)
            return Pessoa(user_id, pedido["nome"], pedido["username"])

    def remove(self, user_id: int) -> Pessoa | None:
        with self._lock:
            data = self._load()
            org = data["organizadores"].pop(str(user_id), None)
            if org is None:
                return None
            write_json(self.path, data)
            return Pessoa(user_id, org["nome"], org["username"])

    def organizers(self) -> list[Pessoa]:
        data = self._load()["organizadores"]
        return [Pessoa(int(k), v["nome"], v["username"]) for k, v in data.items()]

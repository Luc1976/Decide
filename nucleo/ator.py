"""Quem está agindo. Os serviços recebem um Ator em vez de um 'usuario_id' solto."""
from dataclasses import dataclass
from typing import Optional

from nucleo.tabelas import Usuario


@dataclass(frozen=True)
class Ator:
    id: Optional[int]
    nome: str                 # gravado nos campos 'autor' (texto) dos registros
    username: str = ""
    admin: bool = False
    pode_criar_projetos: bool = False

    @classmethod
    def de_usuario(cls, usuario: Usuario, nome: Optional[str] = None) -> "Ator":
        return cls(
            id=usuario.id,
            nome=nome if nome is not None else usuario.nome_completo,
            username=usuario.username,
            admin=bool(usuario.admin),
            pode_criar_projetos=bool(usuario.admin or usuario.pode_criar_projetos),
        )


ANONIMO = Ator(id=None, nome="")

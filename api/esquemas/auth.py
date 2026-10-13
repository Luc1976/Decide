import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

from api.esquemas.comum import Saida


class LoginEntrada(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    senha: str = Field(min_length=1, max_length=200)


class UsuarioSaida(Saida):
    id: int
    username: str
    nome_completo: str
    admin: bool
    pode_criar_projetos: bool
    organizacao_id: Optional[int] = None
    superadmin: bool = False
    tema: Optional[str] = None


class TokenSaida(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expira_em: datetime.datetime
    usuario: UsuarioSaida


class TrocaSenhaEntrada(BaseModel):
    senha_atual: str
    nova_senha: str = Field(min_length=6, max_length=200)


class NovoUsuarioEntrada(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    senha: str = Field(min_length=6, max_length=200)
    nome_completo: str = Field(min_length=1, max_length=200)
    admin: bool = False
    pode_criar_projetos: bool = True


class TemaEntrada(BaseModel):
    tema: Literal["claro", "escuro"]

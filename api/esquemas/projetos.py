import datetime
from typing import Optional

from pydantic import BaseModel, Field

from api.esquemas.comum import Papel, Saida


class ProjetoEntrada(BaseModel):
    nome: str = Field(min_length=1, max_length=200)
    cliente: str = Field(min_length=1, max_length=200)
    descricao: Optional[str] = Field(default=None, max_length=5000)


class ProjetoSaida(Saida):
    id: int
    nome: str
    cliente: str
    descricao: Optional[str] = None
    data_criacao: datetime.datetime
    meu_papel: Optional[str] = None  # "Administrador", "Responsável", "Editor" ou "Leitor"


class ResumoProjetoSaida(BaseModel):
    decisoes: int
    atas: int
    anexos: int
    membros: int
    pendencias: int


class MembroEntrada(BaseModel):
    username: str = Field(min_length=1)
    papel: Papel


class MembroSaida(BaseModel):
    usuario_id: int
    username: str
    nome_completo: str
    papel: str


class AuditoriaSaida(Saida):
    id: int
    momento: datetime.datetime
    usuario_nome: str
    acao: str
    alvo_tipo: Optional[str] = None
    alvo_id: Optional[int] = None
    detalhes: Optional[str] = None

import datetime

from pydantic import BaseModel, Field

from api.esquemas.comum import Saida


class OrganizacaoSaida(Saida):
    id: int
    nome: str
    slug: str
    ativa: bool
    data_criacao: datetime.datetime


class OrganizacaoResumoSaida(OrganizacaoSaida):
    """Para o superadmin: só contagens, nunca o conteúdo dos projetos."""
    usuarios: int
    projetos: int


class RenomearOrganizacaoEntrada(BaseModel):
    nome: str = Field(min_length=1, max_length=200)


class PrimeiroAdminEntrada(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    nome_completo: str = Field(min_length=1, max_length=200)
    senha: str = Field(min_length=6, max_length=200)


class NovaOrganizacaoEntrada(BaseModel):
    nome: str = Field(min_length=1, max_length=200)
    admin: PrimeiroAdminEntrada


class SituacaoOrganizacaoEntrada(BaseModel):
    ativa: bool

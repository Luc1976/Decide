import datetime
from typing import Optional

from pydantic import BaseModel, Field

from api.esquemas.comum import Categoria, Impacto, Saida


class PendenciaEntrada(BaseModel):
    titulo: str = Field(min_length=1, max_length=300)
    descricao: str = Field(default="", max_length=20000)
    categoria: Categoria = "Geral"
    responsavel: str = Field(default="", max_length=200)
    prazo: Optional[datetime.date] = None


class PendenciaSaida(Saida):
    id: int
    numero: int
    titulo: str
    descricao: str
    categoria: str
    responsavel: str
    prazo: Optional[datetime.date] = None
    status: str
    autor: str
    data_criacao: datetime.datetime
    reuniao_id: Optional[int] = None
    decisao_id: Optional[int] = None
    resolucao: str
    resolvida_por: str
    data_resolucao: Optional[datetime.datetime] = None


class NovaDecisaoDaPendencia(BaseModel):
    titulo: str = Field(min_length=1, max_length=300)
    descricao: Optional[str] = None
    categoria: Optional[Categoria] = None
    impacto: Optional[Impacto] = None
    justificativa: Optional[str] = None


class ResolverEntrada(BaseModel):
    """Informe decisao_id (decisão já registrada) OU nova_decisao (criada na hora)."""
    decisao_id: Optional[int] = None
    nova_decisao: Optional[NovaDecisaoDaPendencia] = None
    observacao: str = ""


class CancelarEntrada(BaseModel):
    motivo: str = Field(min_length=1, max_length=2000)

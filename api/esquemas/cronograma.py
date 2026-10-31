import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field

from api.esquemas.pendencias import NovaDecisaoDaPendencia


class ItemCronograma(BaseModel):
    nome: str = Field(min_length=1, max_length=200)
    tipo: Literal["etapa", "marco"] = "etapa"
    inicio: datetime.date
    entrega: Optional[datetime.date] = None  # marco: igual ao início
    depende_da_anterior: bool = True
    padrao: bool = False


class CronogramaEntrada(BaseModel):
    itens: List[ItemCronograma] = Field(min_length=1, max_length=200)
    observacao: str = Field(default="", max_length=2000)


class RevisaoEntrada(CronogramaEntrada):
    """Informe decisao_id (decisão já registrada) OU nova_decisao (criada na mesma gravação)."""
    decisao_id: Optional[int] = None
    nova_decisao: Optional[NovaDecisaoDaPendencia] = None


class ItemCronogramaSaida(ItemCronograma):
    entrega: datetime.date
    desvio_entrega_dias: Optional[int] = None  # em relação à versão 1; None = versão 1 ou item novo
    novo: bool = False


class VersaoSaida(BaseModel):
    numero: int
    criado_em: datetime.datetime
    autor: str
    decisao_id: Optional[int] = None
    observacao: str = ""


class CronogramaSaida(BaseModel):
    versao: Optional[VersaoSaida] = None
    itens: List[ItemCronogramaSaida] = []
    versoes: List[VersaoSaida] = []
    removidos_desde_v1: List[str] = []

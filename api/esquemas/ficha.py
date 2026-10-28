import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from api.esquemas.comum import Saida, Tipologia


class CampoFichaSaida(BaseModel):
    grupo: str
    nome: str
    unidade: Optional[str] = None
    valor: str
    personalizado: bool
    atualizado_por: Optional[str] = None
    data_atualizacao: Optional[datetime.datetime] = None


class IndicadorSaida(BaseModel):
    rotulo: str
    texto: str
    alerta: bool


class PadraoConstrutivoSaida(Saida):
    tipologia: str
    ind_estrutura: Optional[str] = None
    ind_vedacao: Optional[str] = None
    ind_carga_piso: Optional[float] = Field(default=None, ge=0)
    ind_pavimento_externo: Optional[str] = None
    multi_sistema_principal: Optional[str] = None
    multi_tipo_laje: Optional[str] = None
    corp_fachada: Optional[str] = None
    dc_tier_redundancia: Optional[str] = None
    shop_estrutura: Optional[str] = None
    shop_cobertura: Optional[str] = None


class PadraoConstrutivoEntrada(PadraoConstrutivoSaida):
    """Só os campos da tipologia escolhida são guardados; os demais são limpos."""
    tipologia: Tipologia


class FichaSaida(BaseModel):
    campos: List[CampoFichaSaida]
    indicadores: List[IndicadorSaida]
    padrao: Optional[PadraoConstrutivoSaida] = None


class ItemFichaEntrada(BaseModel):
    grupo: str = Field(min_length=1, max_length=200)
    nome: str = Field(min_length=1, max_length=200)
    unidade: Optional[str] = Field(default="", max_length=30)
    valor: str = Field(default="", max_length=5000, description="Vazio apaga campo personalizado")


class FichaEntrada(BaseModel):
    itens: List[ItemFichaEntrada] = Field(max_length=500)


class FichaGravadaSaida(BaseModel):
    campos_alterados: int


class HistoricoFichaSaida(Saida):
    id: int
    grupo: str
    nome: str
    valor_anterior: Optional[str] = None
    valor_novo: Optional[str] = None
    autor: str
    data_registro: datetime.datetime
    decisao_id: Optional[int] = None
    reuniao_id: Optional[int] = None
    origem: Optional[str] = None  # "Decisão D-005 · Ata 04"

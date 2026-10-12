import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from api.esquemas.comum import Saida
from api.esquemas.decisoes import DecisaoSaida
from api.esquemas.ficha import HistoricoFichaSaida
from api.esquemas.pendencias import PendenciaSaida


class AtaEntrada(BaseModel):
    titulo: str = Field(min_length=1, max_length=300)
    data_reuniao: datetime.date
    participantes: Optional[str] = Field(default=None, max_length=2000)
    texto: str = Field(default="", max_length=600_000)


class AtaSaida(Saida):
    id: int
    numero: int
    titulo: str
    data_reuniao: datetime.date
    participantes: Optional[str] = None
    texto: str
    status: str
    autor: str
    data_fechamento: Optional[datetime.datetime] = None


class AtaResumoSaida(Saida):
    """Para listas: sem o texto (que pode ser longo)."""
    id: int
    numero: int
    titulo: str
    data_reuniao: datetime.date
    status: str
    autor: str


class AdendoEntrada(BaseModel):
    texto: str = Field(min_length=1, max_length=20000)


class AdendoSaida(Saida):
    id: int
    texto: str
    autor: str
    data_registro: datetime.datetime


class AtaDetalhesSaida(BaseModel):
    ata: AtaSaida
    decisoes: List[DecisaoSaida]
    pendencias: List[PendenciaSaida]
    alteracoes_ficha: List[HistoricoFichaSaida]
    adendos: List[AdendoSaida]


class TextoAtaEntrada(BaseModel):
    texto: str = Field(max_length=600_000)


class AlteracaoPrevista(BaseModel):
    decisao_indice: Optional[int]
    grupo: str
    nome: str
    unidade: Optional[str] = None
    valor: str


class PreVisualizacaoSaida(BaseModel):
    decisoes: List[str]
    pendencias: List[str]
    alteracoes_ficha: List[AlteracaoPrevista]
    erros: List[str]


class TranscricaoEntrada(BaseModel):
    transcricao: str = Field(min_length=1, max_length=600_000)


class RascunhoIASaida(BaseModel):
    texto: str
    participantes: List[str]
    avisos: List[str]
    aviso_privacidade: str

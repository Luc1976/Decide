import datetime
import os
from typing import List, Optional

from pydantic import BaseModel, Field

from api.esquemas.comum import Categoria, Impacto, Saida
from nucleo.numeracao import codigo_decisao
from nucleo.servicos.decisoes import anexos_da_decisao, checklist_da_decisao


class ItemChecklist(BaseModel):
    texto: str = Field(min_length=1, max_length=500)
    feito: bool = False


class AlteracaoFichaEntrada(BaseModel):
    grupo: str
    nome: str
    unidade: Optional[str] = ""
    valor: str = Field(min_length=1)


class DecisaoEntrada(BaseModel):
    titulo: str = Field(min_length=1, max_length=300)
    categoria: Categoria
    descricao: str = Field(default="", max_length=20000)
    justificativa: str = Field(default="", max_length=20000)
    impacto: Impacto
    alternativa_descartada: Optional[str] = Field(default=None, max_length=20000)
    data_decisao: Optional[datetime.date] = None
    anexos: List[str] = Field(default_factory=list, max_length=30,
                              description="Chaves devolvidas por POST /projetos/{id}/anexos")
    checklist: Optional[List[ItemChecklist]] = None
    alteracao_ficha: Optional[AlteracaoFichaEntrada] = None


class AnexoSaida(BaseModel):
    indice: int
    nome: str


class DecisaoSaida(BaseModel):
    id: int
    numero: Optional[int]
    codigo: str
    titulo: str
    categoria: str
    descricao: str
    justificativa: str
    alternativa_descartada: Optional[str] = None
    impacto: str
    autor: str
    data_decisao: datetime.date
    reuniao_id: Optional[int] = None
    anexos: List[AnexoSaida]
    checklist: list

    @classmethod
    def de(cls, d) -> "DecisaoSaida":
        return cls(
            id=d.id, numero=d.numero, codigo=codigo_decisao(d.numero), titulo=d.titulo,
            categoria=d.categoria, descricao=d.descricao, justificativa=d.justificativa,
            alternativa_descartada=d.alternativa_descartada, impacto=d.impacto, autor=d.autor,
            data_decisao=d.data_decisao, reuniao_id=d.reuniao_id,
            anexos=[AnexoSaida(indice=i, nome=os.path.basename(c)) for i, c in enumerate(anexos_da_decisao(d))],
            checklist=checklist_da_decisao(d),
        )


class AnexoEnviadoSaida(BaseModel):
    chave: str
    nome: str


class LinkSaida(BaseModel):
    url: str
    expira_em_segundos: int

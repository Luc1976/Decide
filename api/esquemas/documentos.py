import datetime
import os
from typing import List, Literal, Optional

from pydantic import BaseModel, Field

from api.esquemas.decisoes import AnexoSaida
from nucleo.servicos.documentos import anexos_do_documento

Situacao = Literal["Recebido", "Pendente", "N/A"]


class DocumentoSaida(BaseModel):
    id: int
    nome: str
    situacao: str
    padrao: bool
    ordem: int
    observacao: str
    anexos: List[AnexoSaida]
    data_recebimento: Optional[datetime.date] = None
    recebido_por: str
    atualizado_por: str
    data_atualizacao: datetime.datetime

    @classmethod
    def de(cls, d) -> "DocumentoSaida":
        return cls(
            id=d.id, nome=d.nome, situacao=d.situacao, padrao=d.padrao, ordem=d.ordem,
            observacao=d.observacao, data_recebimento=d.data_recebimento, recebido_por=d.recebido_por,
            atualizado_por=d.atualizado_por, data_atualizacao=d.data_atualizacao,
            anexos=[AnexoSaida(indice=i, nome=os.path.basename(c)) for i, c in enumerate(anexos_do_documento(d))],
        )


class ResumoDocumentosSaida(BaseModel):
    recebidos: int
    pendentes: int
    nao_aplicaveis: int
    total: int
    aplicaveis: int


class NovoDocumentoEntrada(BaseModel):
    nome: str = Field(min_length=1, max_length=200)
    observacao: str = Field(default="", max_length=5000)


class AtualizarDocumentoEntrada(BaseModel):
    """Envie só o que muda. 'nome' só vale para itens acrescentados."""
    situacao: Optional[Situacao] = None
    observacao: Optional[str] = Field(default=None, max_length=5000)
    nome: Optional[str] = Field(default=None, min_length=1, max_length=200)


class AnexarEntrada(BaseModel):
    chave: str = Field(description="Chave devolvida por POST /projetos/{id}/anexos")

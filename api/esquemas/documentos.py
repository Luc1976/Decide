import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field

from api.esquemas.comum import Saida

Situacao = Literal["Recebido", "Pendente", "N/A"]


class ArquivoDocumentoSaida(Saida):
    id: int
    nome: str
    data_recebimento: datetime.date
    enviado_por: str
    data_envio: datetime.datetime


class DocumentoSaida(BaseModel):
    id: int
    nome: str
    situacao: str
    padrao: bool
    ordem: int
    observacao: str
    data_recebimento: Optional[datetime.date] = None
    recebido_por: str
    atualizado_por: str
    data_atualizacao: datetime.datetime
    arquivos: List[ArquivoDocumentoSaida]

    @classmethod
    def de(cls, d, arquivos) -> "DocumentoSaida":
        return cls(
            id=d.id, nome=d.nome, situacao=d.situacao, padrao=d.padrao, ordem=d.ordem,
            observacao=d.observacao, data_recebimento=d.data_recebimento, recebido_por=d.recebido_por,
            atualizado_por=d.atualizado_por, data_atualizacao=d.data_atualizacao,
            arquivos=[ArquivoDocumentoSaida.model_validate(a) for a in arquivos],
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
    """Envie só o que muda. 'nome' só vale para itens acrescentados; 'data_recebimento' só
    para itens recebidos (ou junto com situacao='Recebido')."""
    situacao: Optional[Situacao] = None
    observacao: Optional[str] = Field(default=None, max_length=5000)
    nome: Optional[str] = Field(default=None, min_length=1, max_length=200)
    data_recebimento: Optional[datetime.date] = None


class AnexarEntrada(BaseModel):
    chave: str = Field(description="Chave devolvida por POST /projetos/{id}/anexos")
    data_recebimento: Optional[datetime.date] = Field(default=None, description="Quando foi recebido (padrão: hoje)")
    nome: Optional[str] = Field(default=None, max_length=200)


class DataArquivoEntrada(BaseModel):
    data_recebimento: datetime.date

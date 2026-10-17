from typing import Literal

from pydantic import BaseModel, ConfigDict

from models import CATEGORIAS, IMPACTOS, PAPEIS
from nucleo.tabelas import SITUACOES_PENDENCIA, TipologiaProjeto

Categoria = Literal[CATEGORIAS]
Impacto = Literal[IMPACTOS]
Papel = Literal[PAPEIS]
SituacaoPendencia = Literal[SITUACOES_PENDENCIA]
Tipologia = Literal[tuple(t.value for t in TipologiaProjeto)]


class Saida(BaseModel):
    """Base das respostas: aceita objetos do banco (from_attributes)."""
    model_config = ConfigDict(from_attributes=True)


class Mensagem(BaseModel):
    detail: str

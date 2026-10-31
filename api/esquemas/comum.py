from typing import Literal

from pydantic import BaseModel, ConfigDict

from models import CATEGORIAS, IMPACTOS, PAPEIS
from catalogo_tipologias import TIPOLOGIAS
from nucleo.tabelas import SITUACOES_PENDENCIA

Categoria = Literal[CATEGORIAS]
Impacto = Literal[IMPACTOS]
Papel = Literal[PAPEIS]
SituacaoPendencia = Literal[SITUACOES_PENDENCIA]
Tipologia = Literal[TIPOLOGIAS]


class Saida(BaseModel):
    """Base das respostas: aceita objetos do banco (from_attributes)."""
    model_config = ConfigDict(from_attributes=True)


class Mensagem(BaseModel):
    detail: str

"""Marcações das atas: [D] decisão, [P] pendência. ([F] ficha fica em ficha_calculos.py.)"""
import re
import unicodedata
from typing import List

_PADRAO_DECISAO = re.compile(r"^\s*\[D\]\s*(.+?)\s*$", re.IGNORECASE)
_PADRAO_PENDENCIA = re.compile(r"^\s*\[P\]\s*(.+?)\s*$", re.IGNORECASE)


def extrair_decisoes(texto: str) -> List[str]:
    """Linhas da ata que começam com [D] (sem diferenciar maiúsculas/minúsculas)."""
    return [m.group(1) for m in map(_PADRAO_DECISAO.match, (texto or "").splitlines()) if m]


def extrair_pendencias(texto: str) -> List[str]:
    """Linhas da ata que começam com [P]: assuntos que ficaram sem decisão."""
    return [m.group(1) for m in map(_PADRAO_PENDENCIA.match, (texto or "").splitlines()) if m]


def titulo_da_linha(linha: str, limite: int = 70) -> str:
    if len(linha) <= limite:
        return linha
    return linha[: limite - 1].rstrip() + "…"


def normalizar(texto: str) -> str:
    """Minúsculas e sem acentos: 'Orçamento' casa com 'orcamento'."""
    sem_acento = unicodedata.normalize("NFKD", texto or "")
    return "".join(c for c in sem_acento if not unicodedata.combining(c)).casefold().strip()

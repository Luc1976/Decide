"""Marcações das atas: [D] decisão, [P] pendência. ([F] ficha fica em ficha_calculos.py.)"""
import re
import unicodedata
from typing import List

from models import CATEGORIAS, IMPACTOS

_PADRAO_DECISAO = re.compile(r"^\s*\[D\]\s*(.+?)\s*$", re.IGNORECASE)
_PADRAO_PENDENCIA = re.compile(r"^\s*\[P\]\s*(.+?)\s*$", re.IGNORECASE)


def extrair_decisoes(texto: str) -> List[str]:
    """Linhas da ata que começam com [D] (sem diferenciar maiúsculas/minúsculas)."""
    return [m.group(1) for m in map(_PADRAO_DECISAO.match, (texto or "").splitlines()) if m]


# Formato da linha de decisão: [D] (Disciplina) (Impacto) Título: descrição
# As duas marcações entre parênteses vêm logo depois do [D], em qualquer ordem, e só aceitam
# os valores padrão do app (models.CATEGORIAS e models.IMPACTOS).
FORMATO_DECISAO = "[D] (Disciplina) (Impacto) Título: descrição"
EXEMPLO_DECISAO = "[D] (Estrutura) (Alto) Adotar estrutura metálica: vãos de 12 m."
_PADRAO_TAG = re.compile(r"^\(([^()]*)\)\s*")


def _achar_opcao(valor: str, opcoes) -> str | None:
    alvo = normalizar(valor)
    for opcao in opcoes:
        if normalizar(opcao) == alvo:
            return opcao
    return None


def interpretar_decisao(linha: str) -> dict:
    """Lê uma linha [D] (texto depois do marcador). Devolve categoria, impacto, texto e erros.

    Erros: marcação que não é disciplina nem impacto padrão, marcação repetida, ou falta de
    disciplina/impacto. Quem chama decide o que fazer com os erros (o fechamento da ata recusa)."""
    categoria = impacto = None
    erros = []
    resto = (linha or "").strip()
    while True:
        achado = _PADRAO_TAG.match(resto)
        if not achado:
            break
        valor = achado.group(1).strip()
        cat, imp = _achar_opcao(valor, CATEGORIAS), _achar_opcao(valor, IMPACTOS)
        if cat and categoria is None:
            categoria = cat
        elif imp and impacto is None:
            impacto = imp
        elif cat or imp:
            erros.append(f"'({valor})' está repetido")
        else:
            erros.append(f"'({valor})' não é uma disciplina nem um impacto válido")
        resto = resto[achado.end():]
    if categoria is None:
        erros.append("falta a disciplina entre parênteses")
    if impacto is None:
        erros.append("falta o impacto entre parênteses")
    return {"categoria": categoria, "impacto": impacto, "texto": resto.strip(), "erros": erros}


def erros_das_decisoes(texto: str) -> List[str]:
    """Mensagens prontas para mostrar à pessoa, uma por linha [D] com problema."""
    mensagens = []
    for linha in extrair_decisoes(texto):
        info = interpretar_decisao(linha)
        if info["erros"]:
            mensagens.append(f"\"{titulo_da_linha(linha, 40)}\": " + "; ".join(info["erros"]))
    return mensagens


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

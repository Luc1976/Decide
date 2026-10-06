"""Ajudas para o app funcionar bem no celular e no computador.

Telas estreitas (< 768 px, o ponto "md" do Flet) são tratadas como "compactas":
rótulos de botões mais curtos, diálogos com margens menores e campos empilhados.
"""
import inspect

import flet as ft

LIMITE_COMPACTO = 768  # px; mesmo ponto "md" do ResponsiveRow


def largura_pagina(page):
    """Largura atual da página em px, ou None se ainda não se sabe."""
    try:
        w = page.width
    except Exception:
        return None
    return w if isinstance(w, (int, float)) and w > 0 else None


def compacto(page) -> bool:
    w = largura_pagina(page)
    return w is not None and w < LIMITE_COMPACTO


def rotulo(page, longo: str, curto: str) -> str:
    """Texto completo no computador, versão curta no celular."""
    return curto if compacto(page) else longo


def col(xs=12, sm=None, md=None, lg=None) -> dict:
    """Colunas (de 12) por tamanho de tela, para o argumento col= de qualquer controle
    dentro de um ft.ResponsiveRow. Ex.: col(12, md=6) = linha inteira no celular, metade no PC."""
    try:
        bp = ft.ResponsiveRowBreakpoint
        chaves = {"xs": bp.XS, "sm": bp.SM, "md": bp.MD, "lg": bp.LG}
    except AttributeError:  # versões do Flet sem o enum aceitam texto
        chaves = {"xs": "xs", "sm": "sm", "md": "md", "lg": "lg"}
    valores = {"xs": xs, "sm": sm, "md": md, "lg": lg}
    return {chaves[nome]: v for nome, v in valores.items() if v is not None}


def _aceita(controle, nome: str) -> bool:
    try:
        return nome in inspect.signature(controle).parameters
    except (TypeError, ValueError):
        return False


def opcoes_dialogo(page) -> dict:
    """Argumentos extras do AlertDialog: no celular reduz as margens para ele ocupar a tela."""
    if not compacto(page):
        return {}
    extras = {}
    for nome, valor in (("inset_padding", 8), ("content_padding", 14)):
        if _aceita(ft.AlertDialog, nome):
            extras[nome] = valor
    return extras


def largura_dialogo(page, maximo: int) -> int:
    """Largura do conteúdo de um diálogo: 'maximo' no computador; no celular, cabe na tela."""
    w = largura_pagina(page)
    if w is None:
        return maximo
    margem = 2 * 8 + 2 * 14 if opcoes_dialogo(page) else 2 * 40 + 2 * 24  # margens do diálogo
    return int(max(240, min(maximo, w - margem)))


def largura_campo(page, maximo: int) -> int:
    """Largura de um campo solto na tela (login etc.): limitada à largura do celular."""
    w = largura_pagina(page)
    return maximo if w is None else int(max(220, min(maximo, w - 40)))

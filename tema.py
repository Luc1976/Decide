"""Aparência do app: modo claro e escuro, cores e selos.

Regra para as telas: NÃO usar cores fixas (ft.Colors.GREY_400, BLUE_200...) em textos e
fundos. Use as cores "por papel" do tema, que se ajustam sozinhas ao modo claro/escuro:

    ft.Colors.ON_SURFACE_VARIANT   texto secundário (datas, autores, dicas)
    ft.Colors.PRIMARY              destaque (projeto ativo, links)
    ft.Colors.TERTIARY             ficha do empreendimento
    ft.Colors.ERROR                erros, atrasos, ações perigosas
    ft.Colors.SURFACE_CONTAINER    fundo de cabeçalhos e painéis

e, para o que o tema não tem, as funções daqui: sucesso(page), aviso(page), fundo_marcacao(...).
Selos (disciplina, impacto, situação): selo(texto, cor) — fundo em tom médio e texto escuro,
com contraste conferido em tests/test_tema.py nos dois modos.
"""
from typing import Optional

import flet as ft

CLARO, ESCURO = "claro", "escuro"
MODOS = (CLARO, ESCURO)
MODO_PADRAO = CLARO  # padrão: claro; quem preferir o escuro troca no menu e fica salvo

COR_BASE = "#2F5DA8"  # azul do Decidiu: o Flet gera toda a paleta a partir dela

# Botão "Atas de Reunião" (e o que for da ata): verde-azulado, diferente do azul principal.
_TERCIARIA = {CLARO: ("#0F766E", "#FFFFFF"), ESCURO: ("#5FD4C4", "#00201C")}


def _tema(modo: str) -> ft.Theme:
    terciaria, sobre_terciaria = _TERCIARIA[modo]
    return ft.Theme(
        color_scheme_seed=COR_BASE,
        color_scheme=ft.ColorScheme(tertiary=terciaria, on_tertiary=sobre_terciaria),
        use_material3=True,
        visual_density=ft.VisualDensity.COMFORTABLE,
    )


def configurar(page) -> None:
    """Chamar uma vez, ao abrir o app."""
    page.theme = _tema(CLARO)
    page.dark_theme = _tema(ESCURO)
    aplicar_modo(page, MODO_PADRAO)


def modo_valido(modo: Optional[str]) -> str:
    return modo if modo in MODOS else MODO_PADRAO


def aplicar_modo(page, modo: Optional[str]) -> None:
    page.theme_mode = ft.ThemeMode.LIGHT if modo_valido(modo) == CLARO else ft.ThemeMode.DARK


def modo_atual(page) -> str:
    return CLARO if getattr(page, "theme_mode", None) == ft.ThemeMode.LIGHT else ESCURO


def eh_claro(page) -> bool:
    return modo_atual(page) == CLARO


def oposto(modo: str) -> str:
    return ESCURO if modo_valido(modo) == CLARO else CLARO


# ---------------------------------------------------------------- cores que o tema não tem

def sucesso(page) -> str:
    """Mensagens de 'salvo', 'pronto'."""
    return "#15803D" if eh_claro(page) else "#66BB6A"


def aviso(page) -> str:
    """Mensagens de 'processando', rascunho, pendência."""
    return "#B45309" if eh_claro(page) else "#FFB300"


def fundo_marcacao(page, tipo: str) -> str:
    """Fundo das linhas [D], [P] e [F] no texto da ata (o texto usa a cor normal)."""
    claro = {"D": "#DBEAFE", "P": "#FFEDD5", "F": "#CCFBF1"}
    escuro = {"D": "#0D47A1", "P": "#7A3B00", "F": "#004D40"}
    return (claro if eh_claro(page) else escuro)[tipo]


# ---------------------------------------------------------------- selos (chips)

TEXTO_SELO = "#1C1B1F"  # texto escuro sobre os fundos em tom médio: contraste alto nos 2 modos

# (fundo do selo, cor forte para ícones/pontos)
CORES_CATEGORIA = {
    "Arquitetura": ("#64B5F6", "#1565C0"),
    "Estrutura": ("#4DB6AC", "#00796B"),
    "instalações": ("#FFB74D", "#E65100"),
    "Orçamento": ("#CE93D8", "#7B1FA2"),
    "Geral": ("#BDBDBD", "#616161"),
    "Elétrica": ("#FFE082", "#F9A825"),
    "Hidrossanitário": ("#81D4FA", "#0277BD"),
    "HVAC": ("#C5E1A5", "#558B2F"),
    "PPCI": ("#FFAB91", "#D84315"),
    "Arquitetura de Interiores": ("#F8BBD0", "#AD1457"),
    "Urbanismo": ("#D1C4E9", "#4527A0"),
    "Fundações": ("#D7CCC8", "#5D4037"),
}
CORES_IMPACTO = {"Alto": "#EF9A9A", "Médio": "#FFD54F", "Baixo": "#81C784"}
CORES_SITUACAO = {
    "Rascunho": "#FFD54F",
    "Fechada": "#81C784",
    "Aberta": "#FFB74D",
    "Resolvida": "#81C784",
    "Cancelada": "#BDBDBD",
    "Ativa": "#81C784",
    "Suspensa": "#EF9A9A",
}
CORES_DOCUMENTO = {"Recebido": "#81C784", "Pendente": "#FFD54F", "N/A": "#BDBDBD"}
_NEUTRO = ("#BDBDBD", "#616161")


def cor_documento_forte(page, situacao: str) -> str:
    """Ícone da situação do documento: verde (recebido), âmbar (pendente), neutro (N/A)."""
    if situacao == "Recebido":
        return sucesso(page)
    if situacao == "Pendente":
        return aviso(page)
    return ft.Colors.ON_SURFACE_VARIANT


def cor_categoria(categoria: str) -> str:
    return CORES_CATEGORIA.get(categoria, _NEUTRO)[0]


def cor_categoria_forte(categoria: str) -> str:
    return CORES_CATEGORIA.get(categoria, _NEUTRO)[1]


def selo(texto: str, fundo: str, icone=None) -> ft.Container:
    """Etiqueta arredondada com texto escuro sobre fundo colorido (legível nos dois modos)."""
    rotulo = ft.Text(texto, size=12, weight=ft.FontWeight.W_600, color=TEXTO_SELO)
    conteudo = rotulo if icone is None else ft.Row(
        tight=True, spacing=4, controls=[ft.Icon(icone, size=14, color=TEXTO_SELO), rotulo]
    )
    return ft.Container(
        content=conteudo,
        bgcolor=fundo,
        border_radius=20,
        padding=ft.Padding.symmetric(horizontal=10, vertical=3),
    )


# ---------------------------------------------------------------- botões

def botao_destaque(texto: str, icone, on_click=None, terciario: bool = False, **extras) -> ft.FilledButton:
    """Ação principal da tela: fundo colorido (azul do tema ou verde-azulado)."""
    estilo = ft.ButtonStyle(
        icon_size=20,
        text_style=ft.TextStyle(weight=ft.FontWeight.W_600),
        padding=ft.Padding.symmetric(horizontal=18, vertical=12),
        **({"bgcolor": ft.Colors.TERTIARY, "color": ft.Colors.ON_TERTIARY, "icon_color": ft.Colors.ON_TERTIARY}
           if terciario else {}),
    )
    return ft.FilledButton(content=texto, icon=icone, on_click=on_click, style=estilo, **extras)


def botao_secundario(texto: str, icone, on_click=None, **extras) -> ft.FilledTonalButton:
    """Ações frequentes, mas não principais: fundo suave e ícone na cor do tema."""
    return ft.FilledTonalButton(
        content=texto, icon=icone, on_click=on_click,
        style=ft.ButtonStyle(icon_size=20, icon_color=ft.Colors.PRIMARY), **extras,
    )


# ---------------------------------------------------------------- contraste (usado nos testes)

def _luminancia(hex_cor: str) -> float:
    hex_cor = hex_cor.lstrip("#")
    canais = [int(hex_cor[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in canais]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def contraste(cor_a: str, cor_b: str) -> float:
    """Razão de contraste WCAG (1 a 21). Texto normal pede 4,5; ideal 7."""
    a, b = sorted((_luminancia(cor_a), _luminancia(cor_b)), reverse=True)
    return (a + 0.05) / (b + 0.05)

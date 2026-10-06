"""Relatório de decisões em PDF. Recebe dados prontos (sem acessar o banco nem o Flet),
o que o torna fácil de testar. Usa as fontes padrão do PDF (Helvetica): letras acentuadas
funcionam; símbolos fora do alfabeto latino (emojis, setas) são trocados por equivalentes
simples ou por '?' para não aparecerem como quadrados pretos."""
import json
import re
import unicodedata
from collections import Counter
from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    CondPageBreak,
    HRFlowable,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from ficha_calculos import calcular_indicadores
from models import FICHA_GRUPOS, GRUPO_OUTRAS

AZUL = colors.HexColor("#1F3A5F")
CINZA = colors.HexColor("#5F6B7A")
CINZA_CLARO = colors.HexColor("#EEF1F5")
COR_IMPACTO = {
    "Alto": colors.HexColor("#B3261E"),
    "Médio": colors.HexColor("#9A6700"),
    "Baixo": colors.HexColor("#1B7F3B"),
}

_SUBSTITUICOES = {
    "→": "->", "←": "<-", "≥": ">=", "≤": "<=", "≠": "!=", "✓": "[x]", "✔": "[x]",
    "☐": "[ ]", "☑": "[x]", "•": "-", "…": "...", "\u00a0": " ", "\u200b": "",
    "‑": "-",
}  # ² ³ ¹ existem na fonte padrão (m² funciona); só trocamos o que não existe
_RE_PREFIXO_UPLOAD = re.compile(r"^[0-9a-f]{32}_")


def _limpo(texto) -> str:
    """Texto seguro para as fontes padrão: troca símbolos comuns e o que não existe em cp1252."""
    texto = str(texto if texto is not None else "")
    for antigo, novo in _SUBSTITUICOES.items():
        texto = texto.replace(antigo, novo)
    return texto.encode("cp1252", errors="replace").decode("cp1252")


def _p(texto) -> str:
    """Texto para dentro de um Paragraph: seguro para a fonte, escapado e com quebras de linha.
    Expoentes (m², m³) viram marcação <super>, que funciona em qualquer leitor de PDF."""
    saida = escape(_limpo(texto)).replace("\r", "").replace("\n", "<br/>")
    for simbolo, digito in (("²", "2"), ("³", "3"), ("¹", "1")):
        saida = saida.replace(simbolo, f"<super>{digito}</super>")
    return saida


def nome_do_anexo(caminho: str) -> str:
    """'uploads/<id>/planta.pdf' ou 'anexos_projetos/<id>_planta.pdf' -> 'planta.pdf'."""
    nome = re.split(r"[\\/]", caminho or "")[-1]
    return _RE_PREFIXO_UPLOAD.sub("", nome)


def nome_do_arquivo(projeto_nome: str, quando: datetime) -> str:
    base = unicodedata.normalize("NFKD", projeto_nome or "projeto")
    base = "".join(c for c in base if not unicodedata.combining(c))
    base = re.sub(r"[^A-Za-z0-9]+", "-", base).strip("-")[:40] or "projeto"
    return f"Relatorio-decisoes-{base}-{quando:%Y%m%d}.pdf"


def _estilos():
    base = getSampleStyleSheet()
    return {
        "titulo": ParagraphStyle("titulo", parent=base["Title"], fontName="Helvetica-Bold",
                                 fontSize=22, leading=26, textColor=AZUL, alignment=TA_LEFT, spaceAfter=2),
        "subtitulo": ParagraphStyle("subtitulo", parent=base["Normal"], fontSize=13, leading=17,
                                    textColor=CINZA, spaceAfter=10),
        "h2": ParagraphStyle("h2", parent=base["Heading2"], fontName="Helvetica-Bold", fontSize=14,
                             leading=18, textColor=AZUL, spaceBefore=14, spaceAfter=6, keepWithNext=1),
        "h3": ParagraphStyle("h3", parent=base["Heading3"], fontName="Helvetica-Bold", fontSize=10.5,
                             leading=14, textColor=CINZA, spaceBefore=8, spaceAfter=3, keepWithNext=1),
        "corpo": ParagraphStyle("corpo", parent=base["Normal"], fontSize=10, leading=14),
        "pequeno": ParagraphStyle("pequeno", parent=base["Normal"], fontSize=8.5, leading=12, textColor=CINZA),
        "dec_titulo": ParagraphStyle("dec_titulo", parent=base["Normal"], fontName="Helvetica-Bold",
                                     fontSize=11.5, leading=15, spaceBefore=5, spaceAfter=3),
        "rotulo": ParagraphStyle("rotulo", parent=base["Normal"], fontSize=9.5, leading=13,
                                 leftIndent=0, spaceAfter=2),
    }


def _titulo_secao(texto, estilos, altura_minima=4.5 * cm):
    """Título de seção + quebra de página condicional (só quebra se faltar espaço)."""
    return [CondPageBreak(altura_minima), Paragraph(texto, estilos["h2"])]


def _tabela_chave_valor(linhas, estilos, larguras=(5.2 * cm, 11.8 * cm)):
    dados = [[Paragraph(f"<b>{_p(k)}</b>", estilos["corpo"]), Paragraph(_p(v), estilos["corpo"])] for k, v in linhas]
    tabela = Table(dados, colWidths=larguras)
    tabela.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, colors.HexColor("#D5DAE1")),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 2),
    ]))
    return tabela


def _canvas_com_rodape(texto_esquerda: str):
    """Canvas que escreve 'Página X de Y' (precisa saber o total, então grava as páginas antes)."""

    class _Numerado(canvas.Canvas):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._estados = []

        def showPage(self):
            self._estados.append(dict(self.__dict__))
            self._startPage()

        def save(self):
            total = len(self._estados)
            for estado in self._estados:
                self.__dict__.update(estado)
                self.setFont("Helvetica", 8)
                self.setFillColor(CINZA)
                self.drawString(2 * cm, 1.2 * cm, _limpo(texto_esquerda)[:95])
                self.drawRightString(A4[0] - 2 * cm, 1.2 * cm, f"Página {self._pageNumber} de {total}")
                self.setStrokeColor(colors.HexColor("#D5DAE1"))
                self.line(2 * cm, 1.7 * cm, A4[0] - 2 * cm, 1.7 * cm)
                super().showPage()
            super().save()

    return _Numerado


def _lista_checklist(texto_json):
    try:
        itens = json.loads(texto_json) if texto_json else []
    except ValueError:
        return []
    return [(str(i.get("tarefa", "")), bool(i.get("feito"))) for i in itens if isinstance(i, dict)]


def _bloco_decisao(decisao, estilos, atas_por_id, alteracoes, incluir_detalhes):
    numero = f"D-{decisao.numero:03d}" if getattr(decisao, "numero", None) else "D-?"
    impacto = decisao.impacto or ""
    cor = COR_IMPACTO.get(impacto, CINZA)
    cabecalho = Table(
        [[
            Paragraph(f"<b>{_p(numero)}</b>", estilos["corpo"]),
            Paragraph(f"{decisao.data_decisao:%d/%m/%Y} &nbsp;|&nbsp; {_p(decisao.categoria)}", estilos["corpo"]),
            Paragraph(f'<font color="{cor.hexval().replace("0x", "#")}"><b>Impacto: {_p(impacto)}</b></font>', estilos["corpo"]),
        ]],
        colWidths=[2.2 * cm, 9.3 * cm, 5.5 * cm],
    )
    cabecalho.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), CINZA_CLARO),
        ("ALIGN", (2, 0), (2, 0), "RIGHT"),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))

    primeiro = [cabecalho, Paragraph(_p(decisao.titulo), estilos["dec_titulo"])]
    if decisao.descricao and decisao.descricao.strip() != (decisao.titulo or "").strip():
        primeiro.append(Paragraph(_p(decisao.descricao), estilos["corpo"]))
    resto = []

    def campo(rotulo, valor):
        resto.append(Paragraph(f"<b>{_p(rotulo)}:</b> {_p(valor)}", estilos["rotulo"]))

    if incluir_detalhes:
        if decisao.justificativa:
            campo("Justificativa", decisao.justificativa)
        if decisao.alternativa_descartada:
            campo("Alternativa descartada", decisao.alternativa_descartada)
        itens = _lista_checklist(decisao.checklist)
        if itens:
            resto.append(Paragraph("<b>Checklist:</b>", estilos["rotulo"]))
            for tarefa, feito in itens:
                resto.append(Paragraph(f"{'[x]' if feito else '[ ]'} {_p(tarefa)}", estilos["rotulo"]))
    for alteracao in alteracoes.get(decisao.id, []):
        campo("Ficha", f"{alteracao.nome}: {alteracao.valor_anterior or '(vazio)'} -> {alteracao.valor_novo or '(vazio)'}")
    anexos = [nome_do_anexo(c) for c in (decisao.anexos or "").split(",") if c]
    if anexos:
        campo("Anexos", "; ".join(anexos))
    origem = atas_por_id.get(decisao.reuniao_id)
    if origem:
        campo("Origem", f"Ata {origem[0]:02d} - {origem[1]}")
    campo("Registrada por", decisao.autor or "-")

    return [CondPageBreak(4.5 * cm), KeepTogether(primeiro)] + resto + [Spacer(1, 6), HRFlowable(width="100%", thickness=0.3, color=colors.HexColor("#D5DAE1")), Spacer(1, 4)]


def _secao_ficha(caracteristicas, estilos):
    por_chave = {(c.grupo, c.nome): c for c in caracteristicas if (c.valor or "").strip()}
    if not por_chave:
        return []
    elementos = _titulo_secao("Ficha do empreendimento", estilos)
    ordem = list(FICHA_GRUPOS) + [GRUPO_OUTRAS]
    for grupo in ordem:
        nomes_modelo = [n for n, _ in FICHA_GRUPOS.get(grupo, [])]
        extras = sorted(n for (g, n) in por_chave if g == grupo and n not in nomes_modelo)
        linhas = []
        for nome in nomes_modelo + extras:
            c = por_chave.get((grupo, nome))
            if c:
                unidade = f" {c.unidade}" if c.unidade else ""
                linhas.append((nome, f"{c.valor}{unidade}"))
        if linhas:
            elementos.append(Paragraph(grupo, estilos["h3"]))
            elementos.append(_tabela_chave_valor(linhas, estilos))
    indicadores = calcular_indicadores({c.nome: c.valor for c in caracteristicas})
    if indicadores:
        elementos.append(Paragraph("Indicadores calculados", estilos["h3"]))
        elementos.append(_tabela_chave_valor([(r, t) for r, t, _ in indicadores], estilos))
    return elementos


def gerar_relatorio_pdf(
    destino: Path,
    projeto,
    decisoes,
    atas_por_id: dict,
    alteracoes_por_decisao: dict,
    caracteristicas,
    gerado_por: str,
    filtros_texto: str = "Todas as decisões",
    incluir_ficha: bool = True,
    incluir_detalhes: bool = True,
    nome_app: str = "Memória de Projetos",
    agora: datetime = None,
) -> int:
    """Grava o PDF em 'destino' e devolve quantas decisões entraram."""
    agora = agora or datetime.now()
    estilos = _estilos()
    decisoes = sorted(decisoes, key=lambda d: (d.data_decisao, d.numero or 0, d.id or 0))

    story = [
        Paragraph("Relatório de Decisões", estilos["titulo"]),
        Paragraph(_p(projeto.nome), estilos["subtitulo"]),
        _tabela_chave_valor(
            [("Cliente", projeto.cliente)]
            + ([("Descrição", projeto.descricao)] if projeto.descricao else [])
            + [
                ("Gerado em", f"{agora:%d/%m/%Y às %H:%M}"),
                ("Gerado por", gerado_por),
                ("Filtros", filtros_texto),
                ("Decisões no relatório", str(len(decisoes))),
            ],
            estilos,
        ),
    ]

    if decisoes:
        por_categoria = Counter(d.categoria for d in decisoes)
        por_impacto = Counter(d.impacto for d in decisoes)
        story += _titulo_secao("Resumo", estilos, 3.5 * cm)
        story.append(Paragraph(
            "<b>Por categoria:</b> " + _p(" | ".join(f"{k}: {v}" for k, v in sorted(por_categoria.items()))),
            estilos["corpo"]))
        story.append(Paragraph(
            "<b>Por impacto:</b> " + _p(" | ".join(f"{k}: {por_impacto[k]}" for k in ("Alto", "Médio", "Baixo") if por_impacto.get(k))),
            estilos["corpo"]))

    if incluir_ficha:
        story += _secao_ficha(caracteristicas, estilos)

    story += _titulo_secao("Decisões (ordem cronológica)", estilos, 7 * cm)
    if not decisoes:
        story.append(Paragraph("Nenhuma decisão encontrada para os filtros escolhidos.", estilos["corpo"]))
    for decisao in decisoes:
        story += _bloco_decisao(decisao, estilos, atas_por_id, alteracoes_por_decisao, incluir_detalhes)

    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    documento = SimpleDocTemplate(
        str(destino), pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=2 * cm, bottomMargin=2.3 * cm,
        title=_limpo(f"Relatório de Decisões - {projeto.nome}"), author=_limpo(gerado_por), subject=_limpo(nome_app),
    )
    documento.build(story, canvasmaker=_canvas_com_rodape(f"{nome_app}  |  {projeto.nome}"))
    return len(decisoes)

"""PDF de uma ata de reunião finalizada. Recebe dados prontos (sem banco nem Flet),
por isso é fácil de testar. Reaproveita estilos e rodapé do relatório de decisões."""
import re
import unicodedata
from datetime import datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from relatorio_pdf import (
    AZUL,
    CINZA,
    CINZA_CLARO,
    _canvas_com_rodape,
    _estilos,
    _p,
    _tabela_chave_valor,
    _titulo_secao,
    _limpo,
)


def nome_do_arquivo_ata(numero, titulo: str, quando) -> str:
    sem_acento = unicodedata.normalize("NFKD", titulo or "")
    sem_acento = "".join(c for c in sem_acento if not unicodedata.combining(c))
    base = re.sub(r"[^A-Za-z0-9]+", "-", sem_acento).strip("-")[:40] or "reuniao"
    return f"Ata-{int(numero or 0):02d}-{base}-{quando:%Y%m%d}.pdf"


def _codigo(decisao) -> str:
    numero = getattr(decisao, "numero", None)
    return f"D-{numero:03d}" if numero else "D-?"


def _linha_texto(linha: str, estilos):
    """Uma linha do texto da ata: [D] e [F] destacadas, o resto normal."""
    limpa = linha.strip()
    if not limpa:
        return Spacer(1, 4)
    if limpa.upper().startswith("[D]"):
        return Table(
            [[Paragraph(f"<b>{_p(limpa)}</b>", estilos["corpo"])]],
            colWidths=[16.9 * cm],
            style=TableStyle([("BACKGROUND", (0, 0), (-1, -1), CINZA_CLARO),
                              ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                              ("LEFTPADDING", (0, 0), (-1, -1), 6)]),
        )
    if limpa.upper().startswith("[F]"):
        return Paragraph(f"<font color='#1B7F3B'><b>{_p(limpa)}</b></font>", estilos["corpo"])
    return Paragraph(_p(limpa), estilos["corpo"])


def gerar_ata_pdf(destino, projeto_nome: str, ata, decisoes, alteracoes, adendos,
                  autor_pdf: str, nome_app: str) -> None:
    """Grava o PDF da ata em 'destino'.
    ata: objeto com numero, titulo, data_reuniao, participantes, texto, autor (e status).
    decisoes: decisões da ata. alteracoes: alterações da ficha feitas por esta ata
    (nome, valor_anterior, valor_novo). adendos: correções posteriores (texto, autor, data_registro)."""
    estilos = _estilos()
    historia = []

    historia.append(Paragraph(f"Ata {int(ata.numero):02d}", estilos["titulo"]))
    historia.append(Paragraph(_p(ata.titulo or "Reunião"), estilos["subtitulo"]))
    historia.append(_tabela_chave_valor([
        ("Projeto", projeto_nome or ""),
        ("Data da reunião", ata.data_reuniao.strftime("%d/%m/%Y")),
        ("Participantes", ata.participantes or "não informados"),
        ("Registrada por", ata.autor or ""),
        ("Situação", ata.status or "Fechada"),
    ], estilos))
    historia.append(Spacer(1, 6))
    historia.append(HRFlowable(width="100%", thickness=0.6, color=AZUL, spaceBefore=4, spaceAfter=6))

    historia += _titulo_secao("Texto da ata", estilos, altura_minima=3 * cm)
    for linha in (ata.texto or "").splitlines():
        historia.append(_linha_texto(linha, estilos))

    if decisoes:
        historia += _titulo_secao("Decisões desta ata", estilos, altura_minima=3 * cm)
        for d in decisoes:
            titulo = _limpo(getattr(d, "titulo", "") or "")
            corpo = [Paragraph(f"{_codigo(d)} · {_p(titulo)}", estilos["dec_titulo"])]
            if getattr(d, "descricao", None):
                corpo.append(Paragraph(_p(d.descricao), estilos["corpo"]))
            meta = " | ".join(
                x for x in (
                    f"Categoria: {d.categoria}" if getattr(d, "categoria", None) else "",
                    f"Impacto: {d.impacto}" if getattr(d, "impacto", None) else "",
                ) if x
            )
            if meta:
                corpo.append(Paragraph(_p(meta), estilos["pequeno"]))
            corpo.append(Spacer(1, 4))
            historia.append(KeepTogether(corpo))

    if alteracoes:
        historia += _titulo_secao("Alterações da ficha do empreendimento", estilos, altura_minima=3 * cm)
        historia.append(_tabela_chave_valor(
            [(a.nome, f"{a.valor_anterior or '(vazio)'}  →  {a.valor_novo or '(vazio)'}") for a in alteracoes],
            estilos,
        ))

    if adendos:
        historia += _titulo_secao("Adendos", estilos, altura_minima=3 * cm)
        for a in adendos:
            quando = getattr(a, "data_registro", None)
            cabecalho = f"{quando:%d/%m/%Y %H:%M}" if isinstance(quando, datetime) else ""
            historia.append(KeepTogether([
                Paragraph(_p(f"{cabecalho} · {a.autor or ''}"), estilos["pequeno"]),
                Paragraph(_p(a.texto), estilos["corpo"]),
                Spacer(1, 6),
            ]))

    Path(destino).parent.mkdir(parents=True, exist_ok=True)
    documento = SimpleDocTemplate(
        str(destino), pagesize=(21 * cm, 29.7 * cm),
        leftMargin=2 * cm, rightMargin=2 * cm, topMargin=2 * cm, bottomMargin=2.2 * cm,
        title=_limpo(f"Ata {int(ata.numero):02d} - {ata.titulo or ''}"),
        author=_limpo(nome_app),
    )
    rodape = f"{nome_app} · {projeto_nome} · Ata {int(ata.numero):02d} · gerado por {autor_pdf}"
    documento.build(historia, canvasmaker=_canvas_com_rodape(rodape))

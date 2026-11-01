"""Gantt desenhado no relatório PDF (seção Cronograma)."""
from datetime import date as d

from reportlab.graphics.shapes import Polygon, Rect, String

from cronograma_calculos import Item
from relatorio_pdf import desenho_gantt


def _itens(n_meses_extra=0):
    return [
        Item("Kick-off", "marco", d(2025, 8, 19), d(2025, 8, 19), depende_da_anterior=False),
        Item("Anteprojeto", "etapa", d(2025, 9, 1), d(2025, 12, 15)),
        Item("Projeto executivo", "etapa", d(2026, 1, 5), d(2026, 6 + n_meses_extra % 6, 30)),
        Item("Liberado para obra", "marco", d(2026, 7, 15), d(2026, 7, 15)),
    ]


def _formas(desenho, tipo):
    saida = []

    def andar(no):
        for filho in getattr(no, "contents", []):
            if isinstance(filho, tipo):
                saida.append(filho)
            andar(filho)
    andar(desenho)
    return saida


def test_desenha_barras_losangos_nomes_e_referencia():
    atual = _itens()
    referencia = [Item("Kick-off", "marco", d(2025, 8, 19), d(2025, 8, 19)),
                  Item("Anteprojeto", "etapa", d(2025, 9, 1), d(2025, 11, 30)),
                  Item("Projeto executivo", "etapa", d(2025, 12, 15), d(2026, 5, 30)),
                  Item("Liberado para obra", "marco", d(2026, 6, 15), d(2026, 6, 15))]
    desenho = desenho_gantt(atual, referencia, hoje=d(2026, 3, 1))
    textos = [s.text for s in _formas(desenho, String)]
    for nome in ("Kick-off", "Anteprojeto", "Projeto executivo", "Liberado para obra", "08/25", "Hoje"):
        assert any(nome in t for t in textos), nome
    barras = [r for r in _formas(desenho, Rect) if getattr(r, "_papel", "") == "etapa"]
    referencias = [r for r in _formas(desenho, Rect) if getattr(r, "_papel", "") == "referencia"]
    assert len(barras) == 2 and len(referencias) == 2
    atrasadas = [r for r in barras if getattr(r, "_atrasada", False)]
    assert len(atrasadas) == 2  # as duas etapas entregam depois da referência
    losangos = [p for p in _formas(desenho, Polygon) if getattr(p, "_papel", "") == "marco"]
    assert len(losangos) == 2
    assert desenho.width > 400 and desenho.height > 60


def test_versao_1_sem_referencia_e_casos_minimos():
    desenho = desenho_gantt(_itens(), [])
    assert not [r for r in _formas(desenho, Rect) if getattr(r, "_papel", "") == "referencia"]
    assert not [r for r in _formas(desenho, Rect) if getattr(r, "_atrasada", False)]
    um = desenho_gantt([Item("Kick-off", "marco", d(2025, 8, 19), d(2025, 8, 19))], [])
    assert um.height > 0
    so_marcos = desenho_gantt([Item("A", "marco", d(2025, 1, 1), d(2025, 1, 1)),
                               Item("B", "marco", d(2025, 1, 1), d(2025, 1, 1))], [])
    assert so_marcos.height > 0


def test_cronograma_longo_espaca_os_rotulos_de_mes():
    longo = [Item("Kick-off", "marco", d(2024, 1, 10), d(2024, 1, 10)),
             Item("Projeto executivo", "etapa", d(2024, 2, 1), d(2026, 12, 20))]
    desenho = desenho_gantt(longo, [])
    rotulos = [s.text for s in _formas(desenho, String) if len(s.text) == 5 and s.text[2] == "/"]
    assert 8 <= len(rotulos) <= 20  # 36 meses: um rótulo a cada 2 ou 3 meses, sem amontoar
    nomes_longos = desenho_gantt([Item("Aprovação do projeto legal na prefeitura municipal e no corpo de bombeiros",
                                       "etapa", d(2025, 1, 1), d(2025, 6, 1))], [])
    nome = [s.text for s in _formas(nomes_longos, String) if s.text.startswith("Aprovação")][0]
    assert len(nome) <= 34 and nome.endswith("…")


def test_relatorio_com_cronograma_gera_pdf(tmp_path):
    from types import SimpleNamespace

    from relatorio_pdf import gerar_relatorio_pdf

    projeto = SimpleNamespace(nome="Aurora", cliente="X", descricao=None, id=1)
    dados = {"atual": _itens(), "v1": _itens(), "numero": 1,
             "versoes": [(1, __import__("datetime").datetime(2025, 8, 19), "Ana", "Linha de base")]}
    destino = tmp_path / "r.pdf"
    gerar_relatorio_pdf(destino, projeto, [], {}, {}, [], "Ana", cronograma=dados)
    assert destino.read_bytes().startswith(b"%PDF")

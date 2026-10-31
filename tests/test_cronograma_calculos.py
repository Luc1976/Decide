"""Cálculo do cronograma: cadeia de dependência, desvios, validação e escala."""
from datetime import date as d

import cronograma_calculos as cc
from cronograma_calculos import Item


def _base():
    return [
        Item("Kick-off", "marco", d(2025, 8, 19), d(2025, 8, 19), padrao=True),
        Item("Estudo preliminar", "etapa", d(2025, 8, 20), d(2025, 10, 30), padrao=True),
        Item("Anteprojeto", "etapa", d(2025, 11, 3), d(2026, 1, 30), padrao=True),
        Item("Projeto básico", "etapa", d(2026, 2, 2), d(2026, 4, 30), padrao=True),
        Item("Aprovação na prefeitura", "etapa", d(2026, 2, 10), d(2026, 5, 15), depende_da_anterior=False),
        # começa antes do fim do básico: sobreposição planejada que deve ser preservada
        Item("Projeto executivo", "etapa", d(2026, 4, 20), d(2026, 9, 30), padrao=True),
        Item("Liberado para obra", "marco", d(2026, 10, 15), d(2026, 10, 15), padrao=True),
    ]


def _por_nome(resultado):
    return {i.nome: (i, recalc) for i, recalc in resultado}


def test_itens_padrao():
    padrao = cc.itens_padrao()
    assert [i.nome for i, _ in padrao] == ["Kick-off", "Projeto conceitual", "Estudo preliminar", "Anteprojeto",
                                         "Projeto básico", "Projeto executivo", "Liberado para obra"]
    marcados = {i.nome: m for i, m in padrao}
    assert marcados["Projeto conceitual"] is False and marcados["Anteprojeto"] is True
    tipos = {i.nome: i.tipo for i, _ in padrao}
    assert tipos["Kick-off"] == tipos["Liberado para obra"] == "marco"
    assert not padrao[0][0].depende_da_anterior and all(i.depende_da_anterior for i, _ in padrao[1:])


def test_atraso_empurra_a_cadeia_e_preserva_duracoes_e_sobreposicao():
    r = _por_nome(cc.recalcular(_base(), {"Projeto básico": (d(2026, 2, 2), d(2026, 5, 30))}))  # +30 dias
    basico, recalc = r["Projeto básico"]
    assert basico.entrega == d(2026, 5, 30) and recalc is False
    executivo, recalc = r["Projeto executivo"]
    assert (executivo.inicio, executivo.entrega, recalc) == (d(2026, 5, 20), d(2026, 10, 30), True)
    obra, recalc = r["Liberado para obra"]
    assert obra.inicio == obra.entrega == d(2026, 11, 14) and recalc
    assert r["Aprovação na prefeitura"][0].entrega == d(2026, 5, 15) and not r["Aprovação na prefeitura"][1]
    assert r["Anteprojeto"][0].entrega == d(2026, 1, 30) and not r["Anteprojeto"][1]  # antes não muda


def test_antecipacao_puxa_a_cadeia():
    r = _por_nome(cc.recalcular(_base(), {"Projeto executivo": (d(2026, 4, 20), d(2026, 9, 20))}))  # -10
    assert r["Liberado para obra"][0].entrega == d(2026, 10, 5)


def test_edicao_manual_no_meio_vira_o_novo_deslocamento():
    editados = {"Anteprojeto": (d(2025, 11, 3), d(2026, 2, 9)),          # +10
                "Projeto executivo": (d(2026, 5, 4), d(2026, 10, 2))}     # o usuário fixa (+2 na entrega)
    r = _por_nome(cc.recalcular(_base(), editados))
    assert r["Projeto básico"][0].entrega == d(2026, 5, 10)               # +10
    assert r["Liberado para obra"][0].entrega == d(2026, 10, 17)          # +2, do executivo


def test_mudar_so_o_inicio_nao_move_as_seguintes():
    r = _por_nome(cc.recalcular(_base(), {"Projeto básico": (d(2026, 2, 16), d(2026, 4, 30))}))
    assert r["Projeto executivo"][0].inicio == d(2026, 4, 20) and not r["Projeto executivo"][1]


def test_item_paralelo_editado_nao_move_ninguem():
    r = _por_nome(cc.recalcular(_base(), {"Aprovação na prefeitura": (d(2026, 2, 10), d(2026, 6, 16))}))
    assert r["Aprovação na prefeitura"][0].entrega == d(2026, 6, 16)
    assert r["Liberado para obra"][0].entrega == d(2026, 10, 15)


def test_item_novo_entra_com_as_datas_digitadas():
    base = _base()
    novo = Item("Lançamento comercial", "marco", d(2026, 3, 1), d(2026, 3, 1), depende_da_anterior=False)
    r = _por_nome(cc.recalcular(base[:4] + [novo] + base[4:], {"Lançamento comercial": (d(2026, 3, 1), d(2026, 3, 1))}))
    assert r["Lançamento comercial"][0].entrega == d(2026, 3, 1) and not r["Lançamento comercial"][1]
    assert r["Liberado para obra"][0].entrega == d(2026, 10, 15)


def test_desvios_por_nome_com_novo_e_removido():
    referencia = _base()
    atual = [i for i, _ in cc.recalcular(referencia, {"Projeto básico": (d(2026, 2, 2), d(2026, 5, 30))})]
    atual = [i for i in atual if i.nome != "Aprovação na prefeitura"]
    atual.append(Item("Lançamento comercial", "marco", d(2026, 3, 1), d(2026, 3, 1), depende_da_anterior=False))
    desv, removidos = cc.desvios(atual, referencia)
    assert desv[cc.chave("projeto basico")].entrega_dias == 30
    assert desv[cc.chave("Liberado para obra")].entrega_dias == 30
    assert desv[cc.chave("Anteprojeto")].entrega_dias == 0
    assert desv[cc.chave("Lançamento comercial")].novo
    assert removidos == ["Aprovação na prefeitura"]
    assert cc.texto_desvio(30) == "+30 dias" and cc.texto_desvio(-1) == "−1 dia" and cc.texto_desvio(0) == "no prazo"


def test_validacao():
    assert cc.validar(_base()) == []
    erros = cc.validar([
        Item("A", "etapa", d(2026, 3, 1), d(2026, 2, 1)),
        Item("a", "etapa", d(2026, 3, 1), d(2026, 4, 1)),
        Item("Sem datas", "etapa", None, d(2026, 4, 1)),
        Item("", "marco", d(2026, 4, 1), d(2026, 4, 1)),
    ])
    texto = " | ".join(erros)
    assert "entrega antes do início" in texto and "repetido" in texto and "Sem datas" in texto and "nome" in texto
    assert cc.validar([]) == ["Inclua ao menos uma etapa ou marco."]


def test_marco_tem_uma_data_so():
    m = Item("Kick-off", "marco", d(2025, 8, 19), d(2025, 9, 1))
    assert cc.normalizar_item(m).entrega == d(2025, 8, 19)


def test_escala_mensal_com_margem():
    inicio, fim, meses = cc.escala(_base())
    assert inicio <= d(2025, 8, 19) and fim >= d(2026, 10, 15)
    assert meses[0] == d(2025, 8, 1) and meses[-1] == d(2026, 10, 1) and len(meses) == 15
    assert 0 < cc.posicao(d(2026, 1, 1), inicio, fim) < 1

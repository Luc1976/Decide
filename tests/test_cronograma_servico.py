"""Serviço do cronograma: versões, revisão ligada a decisão, permissões e exclusão."""
from datetime import date as d

import pytest

from cronograma_calculos import Item
from nucleo.ator import Ator
from nucleo.db import nova_sessao
from nucleo.erros import Conflito, NaoEncontrado, SemPermissao
from nucleo.servicos import cronograma, decisoes, organizacoes, projetos, usuarios
from nucleo.servicos.decisoes import DadosDecisao
from nucleo.tabelas import CronogramaItem, CronogramaVersao, RegistroAuditoria


@pytest.fixture
def s():
    with nova_sessao() as sessao:
        yield sessao


def _ator(s, username, pode_criar=True):
    return Ator.de_usuario(usuarios.criar(s, username, "senha123", username.title(), False, pode_criar))


@pytest.fixture
def cenario(s):
    ana, bia, cli = _ator(s, "ana"), _ator(s, "bia"), _ator(s, "cli", pode_criar=False)
    p = projetos.criar(s, ana, "Edifício Aurora", "Construtora X")
    projetos.definir_membro(s, ana, p.id, "bia", "Editor")
    projetos.definir_membro(s, ana, p.id, "cli", "Leitor")
    return {"p": p.id, "ana": ana, "bia": bia, "cli": cli}


def _itens():
    return [
        Item("Kick-off", "marco", d(2025, 8, 19), d(2025, 8, 19), depende_da_anterior=False, padrao=True),
        Item("Anteprojeto", "etapa", d(2025, 9, 1), d(2025, 12, 15), padrao=True),
        Item("Projeto executivo", "etapa", d(2026, 1, 5), d(2026, 6, 30), padrao=True),
        Item("Liberado para obra", "marco", d(2026, 7, 15), d(2026, 7, 15), padrao=True),
    ]


def _atrasar_executivo(itens, dias=30):
    from datetime import timedelta
    novos = list(itens)
    ex = novos[2]
    novos[2] = Item(ex.nome, ex.tipo, ex.inicio, ex.entrega + timedelta(days=dias), padrao=True)
    novos[3] = Item("Liberado para obra", "marco", d(2026, 7, 15) + timedelta(days=dias),
                    d(2026, 7, 15) + timedelta(days=dias), padrao=True)
    return novos


def test_cria_versao_1_e_le_como_cliente(s, cenario):
    p = cenario["p"]
    v = cronograma.criar(s, cenario["bia"], p, _itens())
    assert v.numero == 1 and v.decisao_id is None
    dados = cronograma.obter(s, cenario["cli"], p)
    assert dados["versao"].numero == 1 and [i.nome for i in dados["itens"]][-1] == "Liberado para obra"
    assert [x.numero for x in dados["versoes"]] == [1]
    with pytest.raises(Conflito):
        cronograma.criar(s, cenario["bia"], p, _itens())


def test_validacao_recusa_e_nada_e_gravado(s, cenario):
    errado = [Item("Anteprojeto", "etapa", d(2026, 3, 1), d(2026, 2, 1))]
    with pytest.raises(ValueError, match="entrega antes do início"):
        cronograma.criar(s, cenario["bia"], cenario["p"], errado)
    assert cronograma.obter(s, cenario["bia"], cenario["p"])["versao"] is None


def test_revisao_com_decisao_existente(s, cenario):
    p, bia = cenario["p"], cenario["bia"]
    cronograma.criar(s, bia, p, _itens())
    dec = decisoes.criar(s, bia, p, DadosDecisao("Prazo estendido", "Geral", "d", "j", "Médio"))
    v2 = cronograma.revisar(s, bia, p, _atrasar_executivo(_itens()), decisao_id=dec.id)
    assert (v2.numero, v2.decisao_id) == (2, dec.id)
    assert cronograma.versoes_por_decisao(s, p) == {dec.id: 2}
    atual = cronograma.obter(s, cenario["cli"], p)
    assert atual["versao"].numero == 2
    assert atual["itens"][-1].entrega == d(2026, 8, 14)
    assert cronograma.obter(s, cenario["cli"], p, numero=1)["itens"][-1].entrega == d(2026, 7, 15)
    acoes = [a.acao for a in s.query(RegistroAuditoria).all()]
    assert "cronograma.criar" in acoes and "cronograma.revisar" in acoes


def test_revisao_com_decisao_nova_numerada_na_mesma_gravacao(s, cenario):
    p, bia = cenario["p"], cenario["bia"]
    cronograma.criar(s, bia, p, _itens())
    decisoes.criar(s, bia, p, DadosDecisao("Outra", "Geral", "d", "j", "Baixo"))  # D-001
    v2 = cronograma.revisar(s, bia, p, _atrasar_executivo(_itens()), nova_decisao={
        "titulo": "Executivo atrasa 30 dias", "categoria": "Geral", "impacto": "Alto",
        "descricao": "Atraso nas sondagens", "justificativa": "Reapresentação na prefeitura"})
    dec = s.get(decisoes.Decisao, v2.decisao_id)
    assert dec.numero == 2 and dec.titulo == "Executivo atrasa 30 dias"


def test_revisao_exige_decisao_e_mudanca(s, cenario):
    p, bia = cenario["p"], cenario["bia"]
    cronograma.criar(s, bia, p, _itens())
    with pytest.raises(ValueError, match="decisão"):
        cronograma.revisar(s, bia, p, _atrasar_executivo(_itens()))
    dec = decisoes.criar(s, bia, p, DadosDecisao("X", "Geral", "d", "j", "Baixo"))
    with pytest.raises(ValueError, match="Nada mudou"):
        cronograma.revisar(s, bia, p, _itens(), decisao_id=dec.id)
    with pytest.raises(ValueError, match="título"):  # decisão nova inválida: nada é gravado
        cronograma.revisar(s, bia, p, _atrasar_executivo(_itens()), nova_decisao={"titulo": ""})
    assert [v.numero for v in cronograma.obter(s, bia, p)["versoes"]] == [1]
    assert len(decisoes.listar(s, bia, p)) == 1


def test_revisao_sem_versao_1_e_recusada(s, cenario):
    dec = decisoes.criar(s, cenario["bia"], cenario["p"], DadosDecisao("X", "Geral", "d", "j", "Baixo"))
    with pytest.raises(Conflito):
        cronograma.revisar(s, cenario["bia"], cenario["p"], _itens(), decisao_id=dec.id)


def test_permissoes(s, cenario):
    p = cenario["p"]
    with pytest.raises(SemPermissao):
        cronograma.criar(s, cenario["cli"], p, _itens())
    cronograma.criar(s, cenario["bia"], p, _itens())
    dec = decisoes.criar(s, cenario["bia"], p, DadosDecisao("X", "Geral", "d", "j", "Baixo"))
    with pytest.raises(SemPermissao):
        cronograma.revisar(s, cenario["cli"], p, _atrasar_executivo(_itens()), decisao_id=dec.id)
    # usuário de outra organização não vê nem o projeto
    org = organizacoes.nova_organizacao(s, "Outro escritório")
    s.commit()
    estranho = Ator.de_usuario(usuarios.criar(s, "ze", "senha123", "Zé", True, True, organizacao_id=org.id))
    with pytest.raises(NaoEncontrado):
        cronograma.obter(s, estranho, p)


def test_decisao_de_outro_projeto_e_recusada(s, cenario):
    p, ana, bia = cenario["p"], cenario["ana"], cenario["bia"]
    outro = projetos.criar(s, ana, "Galpão", "Y")
    dec = decisoes.criar(s, ana, outro.id, DadosDecisao("X", "Geral", "d", "j", "Baixo"))
    cronograma.criar(s, bia, p, _itens())
    with pytest.raises(ValueError, match="decisão deste projeto"):
        cronograma.revisar(s, bia, p, _atrasar_executivo(_itens()), decisao_id=dec.id)


def test_excluir_projeto_apaga_o_cronograma(s, cenario):
    p, ana, bia = cenario["p"], cenario["ana"], cenario["bia"]
    cronograma.criar(s, bia, p, _itens())
    dec = decisoes.criar(s, bia, p, DadosDecisao("X", "Geral", "d", "j", "Baixo"))
    cronograma.revisar(s, bia, p, _atrasar_executivo(_itens()), decisao_id=dec.id)
    projetos.excluir(s, ana, p)
    assert s.query(CronogramaVersao).count() == 0 and s.query(CronogramaItem).count() == 0

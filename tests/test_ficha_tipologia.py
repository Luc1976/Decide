"""Ficha por tipologia nos serviços: campos do catálogo, limpeza com histórico, atas e decisões."""
import datetime

import pytest

import database as db

P, T = "Programa", "Uso / tipologia"
SIS, ALT = "Sistemas construtivos", "Alturas e dimensões"


def _ficha(pid):
    return {(c.grupo, c.nome): c.valor for c in db.listar_caracteristicas(pid)}


def _residencial_com_laje(pid, admin):
    db.salvar_caracteristicas(pid, [
        (P, T, "", "Residencial"),
        (SIS, "Sistema estrutural", "", "Concreto armado convencional"),
        (SIS, "Tipo de laje", "", "Nervurada"),
        (ALT, "Pé-direito – cozinhas", "m", "2,60"),
    ], "Lucas", usuario_id=admin.id)


def test_campos_da_tipologia_entram_na_lista_de_campos(admin, projeto_padrao):
    pid = projeto_padrao.id
    nomes = {n for _, n, _ in db.campos_da_ficha(pid)}
    assert "Tipo de laje" not in nomes and "Sistema estrutural" not in nomes  # sem tipologia
    _residencial_com_laje(pid, admin)
    campos = db.campos_da_ficha(pid)
    assert (SIS, "Tipo de laje", "") in campos and (ALT, "Pé-direito – cozinhas", "m") in campos
    assert (SIS, "Climatização", "") not in campos  # é de Comercial


def test_trocar_tipologia_limpa_com_historico(admin, projeto_padrao):
    pid = projeto_padrao.id
    _residencial_com_laje(pid, admin)
    qtd = db.salvar_caracteristicas(pid, [(P, T, "", "Industrial")], "Lucas", usuario_id=admin.id)
    ficha = _ficha(pid)
    assert ficha[(P, T)] == "Industrial"
    assert ficha[(SIS, "Sistema estrutural")] == "Concreto armado convencional"  # comum: fica
    assert not ficha.get((SIS, "Tipo de laje")) and not ficha.get((ALT, "Pé-direito – cozinhas"))
    assert qtd == 3
    ultimos = [(h.nome, h.valor_anterior, h.valor_novo) for h in db.listar_historico_ficha(pid)[:3]]
    assert ("Tipo de laje", "Nervurada", None) in ultimos


def test_decisao_que_troca_tipologia_limpa_ligada_a_decisao(admin, projeto_padrao):
    pid = projeto_padrao.id
    _residencial_com_laje(pid, admin)
    db.adicionar_decisao(pid, "Vira galpão", "Arquitetura", "d", "j", None, "Alto", "Lucas", None, None,
                         alteracao_ficha=(P, T, "", "Industrial"), usuario_id=admin.id)
    dec = db.listar_decisoes_projeto(pid)[0]
    ligadas = db.alteracoes_ficha_por_decisao(pid)[dec.id]
    assert {h.nome for h in ligadas} == {T, "Tipo de laje", "Pé-direito – cozinhas"}


def test_mudar_o_pai_limpa_o_dependente(admin, projeto_padrao):
    pid = projeto_padrao.id
    _residencial_com_laje(pid, admin)
    db.salvar_caracteristicas(pid, [(SIS, "Sistema estrutural", "", "Alvenaria estrutural")], "Lucas",
                              usuario_id=admin.id)
    assert not _ficha(pid).get((SIS, "Tipo de laje"))


def test_ata_troca_tipologia_e_define_sistema_da_nova_na_mesma_ata(admin, projeto_padrao):
    pid = projeto_padrao.id
    _residencial_com_laje(pid, admin)
    texto = ("[D] (Arquitetura) (Alto) Projeto vira galpão logístico\n"
             "[F] Uso / tipologia = Industrial\n"
             "[F] Altura da doca de carga e descarga = 1,20\n"
             "[F] Cobertura = Telha zipada")
    ata = db.criar_reuniao(pid, "Mudança de programa", datetime.date.today(), "", texto, "Lucas", admin.id)
    db.fechar_reuniao(ata.id, "Lucas", admin.id)
    ficha = _ficha(pid)
    assert ficha[(P, T)] == "Industrial"
    assert ficha[(ALT, "Altura da doca de carga e descarga")] == "1,20"
    assert ficha[(SIS, "Cobertura")] == "Telha zipada"
    assert not ficha.get((SIS, "Tipo de laje"))


def test_ata_recusa_campo_de_outra_tipologia(admin, projeto_padrao):
    pid = projeto_padrao.id
    _residencial_com_laje(pid, admin)
    ata = db.criar_reuniao(pid, "X", datetime.date.today(), "", "[F] Altura dos portões = 6,00", "Lucas", admin.id)
    with pytest.raises(ValueError, match="Altura dos portões"):
        db.fechar_reuniao(ata.id, "Lucas", admin.id)


def test_valor_fora_da_lista_e_aceito(admin, projeto_padrao):
    pid = projeto_padrao.id
    db.salvar_caracteristicas(pid, [(P, T, "", "Residencial"), (SIS, "Fachada", "", "Tijolo à vista")],
                              "Lucas", usuario_id=admin.id)
    assert _ficha(pid)[(SIS, "Fachada")] == "Tijolo à vista"


def test_obter_ficha_nao_devolve_mais_padrao(admin, projeto_padrao):
    from nucleo.ator import Ator
    from nucleo.db import nova_sessao
    from nucleo.servicos import ficha

    with nova_sessao() as s:
        dados = ficha.obter(s, Ator.de_usuario(admin), projeto_padrao.id)
    assert "padrao" not in dados and not hasattr(ficha, "salvar_padrao")

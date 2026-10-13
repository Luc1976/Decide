"""Documentos de referência (checklist de arquivos e informações recebidas)."""
import datetime

import pytest

import database as db
from nucleo.ator import Ator
from nucleo.db import nova_sessao
from nucleo.erros import Conflito, NaoEncontrado, SemPermissao
from nucleo.servicos import documentos, projetos, usuarios
from nucleo.servicos.documentos import ITENS_PADRAO


@pytest.fixture
def s():
    with nova_sessao() as sessao:
        yield sessao


@pytest.fixture
def cenario(s):
    def ator(login, pode=True):
        return Ator.de_usuario(usuarios.criar(s, login, "senha123", login.title(), False, pode))

    ana, bia, cli, ze = ator("ana"), ator("bia"), ator("cli", False), ator("ze")
    p = projetos.criar(s, ana, "Galpão Sinop", "Cliente X")
    projetos.definir_membro(s, ana, p.id, "bia", "Editor")
    projetos.definir_membro(s, ana, p.id, "cli", "Leitor")
    return {"p": p.id, "ana": ana, "bia": bia, "cli": cli, "ze": ze}


def _doc(s, ator, pid, nome):
    return next(d for d in documentos.listar(s, ator, pid) if d.nome == nome)


def test_projeto_novo_nasce_com_a_lista_padrao(s, cenario):
    docs = documentos.listar(s, cenario["cli"], cenario["p"])
    assert [d.nome for d in docs] == list(ITENS_PADRAO)
    assert all(d.situacao == "Pendente" and d.padrao for d in docs)
    assert documentos.resumo_do_projeto(s, cenario["cli"], cenario["p"]) == {
        "Recebido": 0, "Pendente": 7, "N/A": 0, "total": 7, "aplicaveis": 7}


def test_projeto_exemplo_do_banco_novo_tambem_tem_lista():
    lucas = db.autenticar_usuario("lucas", "senha-admin")
    projeto = db.listar_projetos_do_usuario(lucas.id)[0]
    assert len(db.listar_documentos(projeto.id, lucas.id)) == 7


def test_marcar_recebido_guarda_data_e_quem(s, cenario):
    p, bia = cenario["p"], cenario["bia"]
    topo = _doc(s, bia, p, "Levantamento topográfico")
    topo = documentos.atualizar(s, bia, topo.id, situacao="Recebido", observacao="  Enviado pelo cliente R01 ")
    assert (topo.data_recebimento, topo.recebido_por, topo.observacao) == (
        datetime.date.today(), "Bia", "Enviado pelo cliente R01")
    topo = documentos.atualizar(s, bia, topo.id, situacao="N/A")
    assert topo.data_recebimento is None and topo.recebido_por == ""
    assert documentos.resumo_do_projeto(s, bia, p)["aplicaveis"] == 6
    with pytest.raises(ValueError):
        documentos.atualizar(s, bia, topo.id, situacao="Talvez")


def test_itens_acrescentados(s, cenario):
    p, bia = cenario["p"], cenario["bia"]
    novo = documentos.criar(s, bia, p, "Licença ambiental", "pedir à prefeitura")
    assert (novo.ordem, novo.padrao, novo.situacao) == (8, False, "Pendente")
    with pytest.raises(ValueError, match="já está"):
        documentos.criar(s, bia, p, "  licença AMBIENTAL ")
    documentos.atualizar(s, bia, novo.id, nome="Licença ambiental prévia (LP)")
    with pytest.raises(Conflito):  # padrão não se renomeia...
        documentos.atualizar(s, bia, _doc(s, bia, p, "Layout").id, nome="Planta")
    with pytest.raises(Conflito):  # ...nem se exclui
        documentos.excluir(s, bia, _doc(s, bia, p, "Layout").id)
    assert documentos.excluir(s, bia, novo.id) == []
    assert len(documentos.listar(s, bia, p)) == 7


def test_anexos(s, cenario, tmp_path):
    from nucleo.armazenamento import ArmazenamentoLocal
    from nucleo.servicos import anexos

    p, bia, ana = cenario["p"], cenario["bia"], cenario["ana"]
    chave = anexos.enviar(s, bia, p, "sondagem SPT.pdf", b"%PDF", ArmazenamentoLocal(tmp_path))
    spt = _doc(s, bia, p, "Relatórios de Sondagens SPT")
    spt = documentos.anexar(s, bia, spt.id, chave)
    assert spt.situacao == "Recebido" and documentos.anexos_do_documento(spt) == [chave]
    assert documentos.anexo(s, cenario["cli"], p, spt.id, 0) == chave
    assert documentos.documento_tem_anexo(s, p, chave)
    outro = projetos.criar(s, ana, "Outro", "Y")
    with pytest.raises(ValueError, match="inválido"):
        documentos.anexar(s, ana, _doc(s, ana, outro.id, "Layout").id, chave)
    _, removida = documentos.remover_anexo(s, bia, spt.id, 0)
    assert removida == chave and documentos.anexos_do_documento(_doc(s, bia, p, spt.nome)) == []


def test_permissoes(s, cenario):
    p, cli, ze = cenario["p"], cenario["cli"], cenario["ze"]
    layout = _doc(s, cli, p, "Layout")
    with pytest.raises(SemPermissao):
        documentos.atualizar(s, cli, layout.id, situacao="Recebido")
    with pytest.raises(SemPermissao):
        documentos.criar(s, cli, p, "Qualquer")
    with pytest.raises(NaoEncontrado):
        documentos.listar(s, ze, p)
    outro = projetos.criar(s, cenario["ana"], "Outro", "Y")
    with pytest.raises(NaoEncontrado):  # documento de outro projeto pela rota errada
        documentos.anexo(s, cenario["ana"], outro.id, layout.id, 0)


def test_excluir_projeto_leva_os_documentos(s, cenario):
    p, ana = cenario["p"], cenario["ana"]
    assert projetos.excluir(s, ana, p) == []
    from nucleo.tabelas import DocumentoReferencia
    from sqlmodel import select

    assert s.exec(select(DocumentoReferencia).where(DocumentoReferencia.projeto_id == p)).all() == []

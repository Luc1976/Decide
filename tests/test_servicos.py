"""Regras novas da camada de serviços (o que o app Flet não garantia sozinho)."""
import datetime

import pytest

from nucleo.ator import Ator
from nucleo.db import nova_sessao
from nucleo.erros import Conflito, NaoEncontrado, SemPermissao
from nucleo.servicos import anexos, atas, decisoes, ficha, pendencias, projetos, usuarios
from nucleo.servicos.decisoes import DadosDecisao
from nucleo.tabelas import RegistroAuditoria


@pytest.fixture
def s():
    with nova_sessao() as sessao:
        yield sessao


def _ator(s, username, pode_criar=True):
    u = usuarios.criar(s, username, "senha123", username.title(), False, pode_criar)
    return Ator.de_usuario(u)


@pytest.fixture
def cenario(s):
    """Ana é Responsável, Bia é Editora, Cli é Leitor (cliente), Zé não tem acesso."""
    ana, bia = _ator(s, "ana"), _ator(s, "bia")
    cli, ze = _ator(s, "cli", pode_criar=False), _ator(s, "ze")
    p = projetos.criar(s, ana, "Edifício Aurora", "Construtora X")
    projetos.definir_membro(s, ana, p.id, "bia", "Editor")
    projetos.definir_membro(s, ana, p.id, "cli", "Leitor")
    return {"p": p.id, "ana": ana, "bia": bia, "cli": cli, "ze": ze}


def _dec(titulo="Estrutura metálica", **extra):
    return DadosDecisao(titulo=titulo, categoria="Estrutura", descricao="d", justificativa="j", impacto="Alto", **extra)


def test_leitura_exige_acesso(s, cenario):
    p, ze, cli = cenario["p"], cenario["ze"], cenario["cli"]
    decisoes.criar(s, cenario["bia"], p, _dec())
    assert len(decisoes.listar(s, cli, p)) == 1
    with pytest.raises(NaoEncontrado):  # sem acesso: nem confirma que o projeto existe
        decisoes.listar(s, ze, p)
    with pytest.raises(NaoEncontrado):
        ficha.obter(s, ze, p)
    with pytest.raises(NaoEncontrado):
        pendencias.listar(s, ze, p)


def test_leitor_nao_grava_e_recebe_403(s, cenario):
    with pytest.raises(SemPermissao):
        decisoes.criar(s, cenario["cli"], cenario["p"], _dec())
    with pytest.raises(SemPermissao):
        projetos.listar_membros(s, cenario["bia"], cenario["p"])


def test_leitor_nao_ve_rascunho_de_ata(s, cenario):
    p, bia, cli = cenario["p"], cenario["bia"], cenario["cli"]
    rascunho = atas.criar(s, bia, p, "Rascunho", datetime.date.today(), "", "texto")
    fechada = atas.criar(s, bia, p, "Fechada", datetime.date.today(), "", "[D] Algo")
    atas.fechar(s, bia, fechada.id)
    assert {a.id for a in atas.listar(s, bia, p)} == {rascunho.id, fechada.id}
    assert [a.id for a in atas.listar(s, cli, p)] == [fechada.id]
    with pytest.raises(NaoEncontrado):
        atas.obter(s, cli, rascunho.id)
    assert atas.detalhes(s, cli, fechada.id)["decisoes"][0].titulo == "Algo"


def test_objeto_de_outro_projeto_e_404(s, cenario):
    ana = cenario["ana"]
    outro = projetos.criar(s, ana, "Outro", "C")
    d = decisoes.criar(s, ana, outro.id, _dec())
    with pytest.raises(NaoEncontrado):
        decisoes.obter(s, ana, cenario["p"], d.id)  # id certo, projeto errado na rota


def test_validacao_da_decisao(s, cenario):
    with pytest.raises(ValueError, match="título"):
        decisoes.criar(s, cenario["bia"], cenario["p"], _dec(titulo="  "))
    with pytest.raises(ValueError, match="categoria"):
        decisoes.criar(s, cenario["bia"], cenario["p"],
                       DadosDecisao("T", "Inventada", "d", "j", "Alto"))


def test_anexo_so_do_proprio_projeto(s, cenario, tmp_path):
    from nucleo.armazenamento import ArmazenamentoLocal

    p, bia, ana = cenario["p"], cenario["bia"], cenario["ana"]
    arm = ArmazenamentoLocal(tmp_path)
    chave = anexos.enviar(s, bia, p, "planta, térreo.pdf", b"%PDF-1", arm)
    assert chave.startswith(f"uploads/p{p}/") and "," not in chave
    assert arm.ler(chave) == b"%PDF-1"
    d = decisoes.criar(s, bia, p, _dec(anexos=[chave]))
    assert decisoes.anexo(s, cenario["cli"], p, d.id, 0) == chave
    outro = projetos.criar(s, ana, "Outro", "C")
    with pytest.raises(ValueError, match="Anexo inválido"):
        decisoes.criar(s, ana, outro.id, _dec(anexos=[chave]))
    with pytest.raises(SemPermissao):
        anexos.enviar(s, cenario["cli"], p, "x.pdf", b"1", arm)
    with pytest.raises(ValueError):
        arm.salvar("../fora.txt", b"x")


def test_link_assinado_do_anexo(s, cenario):
    link = anexos.gerar_link("uploads/p1/abc/x.pdf")
    assert anexos.chave_do_link(link.rsplit("/", 1)[1]) == "uploads/p1/abc/x.pdf"
    assert anexos.chave_do_link("adulterado.abc") is None


def test_conflitos_de_estado(s, cenario):
    p, bia = cenario["p"], cenario["bia"]
    ata = atas.criar(s, bia, p, "A", datetime.date.today(), "", "")
    atas.fechar(s, bia, ata.id)
    with pytest.raises(Conflito):
        atas.fechar(s, bia, ata.id)
    pend = pendencias.criar(s, bia, p, "Cor")
    pendencias.cancelar(s, bia, pend.id, "desnecessária")
    with pytest.raises(Conflito):
        pendencias.cancelar(s, bia, pend.id, "de novo")


def test_pre_visualizar_ata(s, cenario):
    prev = atas.pre_visualizar(s, cenario["bia"], cenario["p"], "[D] A\n[F] CA = 2,5\n[F] xyz = 1\n[P] B")
    assert prev["decisoes"] == ["A"] and prev["pendencias"] == ["B"]
    assert prev["alteracoes_ficha"][0]["nome"] == "Coeficiente de aproveitamento (CA)"
    assert prev["erros"] == ["campo 'xyz' não existe na ficha"]


def test_ficha_com_indicadores(s, cenario):
    p, bia = cenario["p"], cenario["bia"]
    ficha.salvar(s, bia, p, [
        ("Terreno e localização", "Área do terreno", "m²", "1.000"),
        ("Parâmetros urbanísticos", "Coeficiente de aproveitamento (CA)", "", "2"),
    ])
    f = ficha.obter(s, cenario["cli"], p)
    assert {"rotulo": "Potencial construtivo", "texto": "2.000,00 m²", "alerta": False} in f["indicadores"]
    hist = ficha.historico(s, cenario["cli"], p)
    assert len(hist) == 2 and hist[0][1] is None


def test_auditoria_registra_gravacoes(s, cenario):
    p, bia = cenario["p"], cenario["bia"]
    d = decisoes.criar(s, bia, p, _dec())
    acoes = [(r.acao, r.usuario_nome) for r in s.exec(
        __import__("sqlmodel").select(RegistroAuditoria).where(RegistroAuditoria.projeto_id == p)
    ).all()]
    assert ("projeto.criar", "ana") in acoes
    assert ("membro.definir", "ana") in acoes
    assert ("decisao.criar", "bia") in acoes
    assert d.autor == "Bia"


def test_rascunho_ia_usa_contexto_do_projeto(s, cenario):
    from nucleo.servicos import ia

    p, bia = cenario["p"], cenario["bia"]
    decisoes.criar(s, bia, p, _dec("Laje protendida"))
    vistos = {}

    def falso(sistema, pedido):
        vistos["pedido"] = pedido
        return '{"decisoes": [{"titulo": "Usar laje nervurada", "categoria": "Estrutura", "impacto": "Alto"}]}'

    texto = "Fulano: vamos decidir a laje. " * 20
    r = ia.rascunho_de_ata(s, bia, p, texto, chamar=falso)
    assert "D-001 Laje protendida" in vistos["pedido"]
    assert "Usar laje nervurada" in r["texto"]
    with pytest.raises(SemPermissao):
        ia.rascunho_de_ata(s, cenario["cli"], p, texto, chamar=falso)

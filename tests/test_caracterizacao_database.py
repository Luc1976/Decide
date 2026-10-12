"""Comportamento atual de database.py (o que o app Flet usa).

Estes testes foram escritos ANTES de database.py passar a delegar para nucleo/servicos e
garantem que a troca não mudou nada para as telas Flet."""
import datetime

import pytest

import database as db


def _usuario(username, admin=False, pode_criar=True):
    return db.criar_usuario(username, "senha123", username.title(), admin, pode_criar)


# ---------------------------------------------------------------- usuários e login

def test_admin_inicial_e_login(admin):
    assert admin.username == "lucas"
    assert db.autenticar_usuario("LUCAS ", "senha-admin").id == admin.id
    assert db.autenticar_usuario("lucas", "errada") is None


def test_criar_usuario_valida():
    with pytest.raises(ValueError):
        db.criar_usuario("com espaco", "senha123", "X")
    with pytest.raises(ValueError):
        db.criar_usuario("curta", "123", "X")
    _usuario("ana")
    with pytest.raises(ValueError):
        _usuario("ana")


def test_alterar_propria_senha():
    u = _usuario("ana")
    with pytest.raises(ValueError):
        db.alterar_propria_senha(u.id, "errada", "nova-senha")
    db.alterar_propria_senha(u.id, "senha123", "nova-senha")
    assert db.autenticar_usuario("ana", "nova-senha") is not None


# ---------------------------------------------------------------- projetos e membros

def test_criar_projeto_vira_responsavel():
    ana = _usuario("ana")
    p = db.criar_projeto("Edifício X", "Cliente Y", None, ana.id)
    assert db.nivel_no_projeto(ana.id, p.id) == 3
    assert [x.id for x in db.listar_projetos_do_usuario(ana.id)] == [p.id]


def test_cliente_nao_cria_projeto():
    cli = _usuario("cli", pode_criar=False)
    with pytest.raises(PermissionError):
        db.criar_projeto("P", "C", None, cli.id)


def test_membros_e_ultimo_responsavel(admin):
    ana, bia = _usuario("ana"), _usuario("bia")
    p = db.criar_projeto("P", "C", None, ana.id)
    db.definir_membro(p.id, "bia", "Leitor", ana.id)
    assert db.nivel_no_projeto(bia.id, p.id) == 1
    with pytest.raises(PermissionError):
        db.definir_membro(p.id, "ana", "Leitor", bia.id)
    with pytest.raises(ValueError):  # não pode ficar sem Responsável
        db.definir_membro(p.id, "ana", "Editor", ana.id)
    with pytest.raises(ValueError):
        db.definir_membro(p.id, "lucas", "Leitor", ana.id)  # admin
    membros = db.listar_membros(p.id, ana.id)
    assert [(u.username, papel) for u, papel in membros] == [("ana", "Responsável"), ("bia", "Leitor")]
    db.remover_membro(p.id, bia.id, ana.id)
    assert db.nivel_no_projeto(bia.id, p.id) == 0


def test_atualizar_e_excluir_projeto(admin):
    ana = _usuario("ana")
    p = db.criar_projeto("P", "C", None, ana.id)
    p2 = db.atualizar_projeto(p.id, "P2", "C2", "desc", ana.id)
    assert (p2.nome, p2.cliente, p2.descricao) == ("P2", "C2", "desc")
    db.adicionar_decisao(p.id, "T", "Geral", "D", "J", None, "Alto", "Ana", "uploads/a/x.pdf", None, usuario_id=ana.id)
    assert db.resumo_projeto(p.id, ana.id)["decisoes"] == 1
    caminhos = db.excluir_projeto(p.id, ana.id)
    assert caminhos == ["uploads/a/x.pdf"]
    assert all(x.id != p.id for x in db.listar_projetos())


# ---------------------------------------------------------------- decisões e ficha

def test_decisao_numerada_e_altera_ficha(admin, projeto_padrao):
    pid = projeto_padrao.id
    db.adicionar_decisao(pid, "A", "Geral", "d", "j", None, "Alto", "Lucas", None, None, usuario_id=admin.id)
    db.adicionar_decisao(
        pid, "B", "Arquitetura", "d", "j", None, "Médio", "Lucas", None, None,
        alteracao_ficha=("Terreno e localização", "Área do terreno", "m²", "1.000,00"),
        usuario_id=admin.id,
    )
    decs = sorted(db.listar_decisoes_projeto(pid), key=lambda d: d.numero)
    assert [d.numero for d in decs] == [1, 2]
    fic = {c.nome: c.valor for c in db.listar_caracteristicas(pid)}
    assert fic["Área do terreno"] == "1.000,00"
    hist = db.alteracoes_ficha_por_decisao(pid)
    assert list(hist) == [decs[1].id]
    assert db.mapa_origens_ficha(pid) == {hist[decs[1].id][0].id: "Decisão D-002"}


def test_leitor_nao_grava(projeto_padrao):
    leitor = _usuario("cli", pode_criar=False)
    with pytest.raises(PermissionError):
        db.adicionar_decisao(projeto_padrao.id, "A", "Geral", "d", "j", None, "Alto", "x", None, None, usuario_id=leitor.id)


def test_busca_sem_acento(admin, projeto_padrao):
    db.adicionar_decisao(projeto_padrao.id, "Orçamento revisto", "Orçamento", "d", "j", None, "Alto", "Lucas", None, None, usuario_id=admin.id)
    assert len(db.buscar_decisoes_projeto(projeto_padrao.id, "orcamento")) == 1
    assert db.buscar_decisoes_projeto(projeto_padrao.id, "inexistente") == []


def test_salvar_ficha_e_campo_personalizado(admin, projeto_padrao):
    pid = projeto_padrao.id
    n = db.salvar_caracteristicas(pid, [
        ("Terreno e localização", "Testada", "m", "20"),
        (db.GRUPO_OUTRAS, "Heliponto", "", "sim"),
    ], "Lucas", usuario_id=admin.id)
    assert n == 2
    assert ("Outras características", "Heliponto", "") in db.campos_da_ficha(pid)
    assert db.salvar_caracteristicas(pid, [("Terreno e localização", "Testada", "m", "20")], "Lucas", usuario_id=admin.id) == 0
    db.salvar_caracteristicas(pid, [(db.GRUPO_OUTRAS, "Heliponto", "", "")], "Lucas", usuario_id=admin.id)
    assert "Heliponto" not in {c.nome for c in db.listar_caracteristicas(pid)}
    assert len(db.listar_historico_ficha(pid)) == 3


def test_padrao_construtivo(admin, projeto_padrao):
    p = db.salvar_padrao_construtivo(projeto_padrao.id, {"tipologia": "Industrial", "ind_carga_piso": 5.0}, admin.id)
    assert p.ind_carga_piso == 5.0
    p = db.salvar_padrao_construtivo(projeto_padrao.id, {"tipologia": "Multifamiliar", "multi_tipo_laje": "Maciça"}, admin.id)
    assert p.ind_carga_piso is None and p.multi_tipo_laje == "Maciça"
    assert db.obter_padrao_construtivo(projeto_padrao.id).tipologia == "Multifamiliar"


# ---------------------------------------------------------------- atas

TEXTO_ATA = """Reunião de alinhamento
[D] Adotar estrutura metálica
[F] TO = 60
[F] Área do terreno = 2.000
Discussão livre
[D] Fachada em ACM
[P] Definir cor da fachada
"""


def test_fechar_ata_cria_decisoes_pendencias_e_ficha(admin, projeto_padrao):
    pid = projeto_padrao.id
    ata = db.criar_reuniao(pid, "Alinhamento", datetime.date(2026, 5, 1), "Ana, Bia", TEXTO_ATA, "Lucas", admin.id)
    assert ata.numero == 1 and ata.status == "Rascunho"
    criadas = db.fechar_reuniao(ata.id, "Lucas", admin.id)
    assert [d.titulo for d in criadas] == ["Adotar estrutura metálica", "Fachada em ACM"]
    assert [d.numero for d in criadas] == [1, 2]
    assert criadas[0].justificativa == "Registrada na Ata 01 - Alinhamento"
    assert criadas[0].data_decisao == datetime.date(2026, 5, 1)
    assert db.buscar_reuniao(ata.id).status == "Fechada"
    pend = db.listar_pendencias_reuniao(ata.id)
    assert [p.titulo for p in pend] == ["Definir cor da fachada"]
    alt = db.listar_alteracoes_ficha_ata(ata.id)
    assert [(a.nome, a.valor_novo, a.decisao_id) for a in alt] == [
        ("Taxa de ocupação (TO)", "60", criadas[0].id),
        ("Área do terreno", "2.000", criadas[0].id),
    ]
    with pytest.raises(ValueError):
        db.fechar_reuniao(ata.id, "Lucas", admin.id)
    with pytest.raises(ValueError):
        db.atualizar_reuniao_rascunho(ata.id, "x", datetime.date.today(), "", "", admin.id)
    db.adicionar_adendo(ata.id, "Correção", "Lucas", admin.id)
    assert len(db.listar_adendos(ata.id)) == 1


def test_fechar_ata_com_f_invalida_nao_grava_nada(admin, projeto_padrao):
    ata = db.criar_reuniao(projeto_padrao.id, "A", datetime.date.today(), "", "[D] X\n[F] campo inexistente = 3", "L", admin.id)
    with pytest.raises(ValueError, match=r"\[F\]"):
        db.fechar_reuniao(ata.id, "L", admin.id)
    assert db.listar_decisoes_projeto(projeto_padrao.id) == []
    assert db.buscar_reuniao(ata.id).status == "Rascunho"


def test_adendo_so_em_ata_fechada(admin, projeto_padrao):
    ata = db.criar_reuniao(projeto_padrao.id, "A", datetime.date.today(), "", "", "L", admin.id)
    with pytest.raises(ValueError):
        db.adicionar_adendo(ata.id, "x", "L", admin.id)
    with pytest.raises(ValueError):
        db.criar_reuniao(projeto_padrao.id, "  ", datetime.date.today(), "", "", "L", admin.id)


def test_busca_atas(admin, projeto_padrao):
    db.criar_reuniao(projeto_padrao.id, "Reunião de Orçamento", datetime.date.today(), "", "", "L", admin.id)
    assert len(db.buscar_reunioes_projeto(projeto_padrao.id, "orcamento")) == 1


# ---------------------------------------------------------------- pendências

def test_ciclo_de_pendencia(admin, projeto_padrao):
    pid = projeto_padrao.id
    p1 = db.criar_pendencia(pid, "Cor da fachada", prazo=datetime.date(2026, 1, 10), autor="L", usuario_id=admin.id)
    p2 = db.criar_pendencia(pid, "Tipo de piso", autor="L", usuario_id=admin.id)
    assert (p1.numero, p2.numero) == (1, 2)
    assert db.contar_pendencias_abertas(pid) == 2
    r = db.resolver_pendencia(p1.id, "L", admin.id, nova_decisao={"titulo": "Fachada branca"})
    assert r.status == "Resolvida" and r.decisao_id is not None
    dec = [d for d in db.listar_decisoes_projeto(pid) if d.id == r.decisao_id][0]
    assert dec.justificativa == "Resolve a pendência P-001 - Cor da fachada"
    with pytest.raises(ValueError):
        db.atualizar_pendencia(p1.id, "x", "", "Geral", "", None, admin.id)
    db.cancelar_pendencia(p2.id, "não se aplica", "L", admin.id)
    assert db.contar_pendencias_abertas(pid) == 0
    db.reabrir_pendencia(p1.id, admin.id)
    lista = db.listar_pendencias(pid)
    assert [p.id for p in lista] == [p1.id, p2.id]  # abertas primeiro
    with pytest.raises(ValueError):
        db.cancelar_pendencia(p1.id, "", "L", admin.id)


def test_resolver_com_decisao_de_outro_projeto(admin, projeto_padrao):
    outro = db.criar_projeto("Outro", "C", None, admin.id)
    db.adicionar_decisao(outro.id, "X", "Geral", "d", "j", None, "Alto", "L", None, None, usuario_id=admin.id)
    dec_outro = db.listar_decisoes_projeto(outro.id)[0]
    p = db.criar_pendencia(projeto_padrao.id, "P", autor="L", usuario_id=admin.id)
    with pytest.raises(ValueError):
        db.resolver_pendencia(p.id, "L", admin.id, decisao_id=dec_outro.id)


def test_anexo_pertence_ao_projeto(admin, projeto_padrao):
    db.adicionar_decisao(projeto_padrao.id, "A", "Geral", "d", "j", None, "Alto", "L", "uploads/a/1.pdf,uploads/b/2.pdf", None, usuario_id=admin.id)
    assert db.anexo_pertence_ao_projeto(projeto_padrao.id, "uploads/b/2.pdf")
    assert not db.anexo_pertence_ao_projeto(projeto_padrao.id, "uploads/c/3.pdf")

"""API REST: fluxo completo e barreiras de segurança, pela HTTP (como o frontend usará)."""
import datetime

import pytest
from fastapi.testclient import TestClient

import database as db
from api.autenticacao import LIMITADOR_LOGIN
from api.main import app

V = "/api/v1"


@pytest.fixture
def cliente():
    LIMITADOR_LOGIN._falhas.clear()
    LIMITADOR_LOGIN._bloqueado_ate.clear()
    with TestClient(app) as c:
        yield c


def _login(c, username, senha="senha123"):
    r = c.post(f"{V}/auth/login", json={"username": username, "senha": senha})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
def equipe(cliente):
    """lucas (admin), ana (Responsável), bia (Editora), cli (Leitor), ze (sem acesso)."""
    for u, pode in (("ana", True), ("bia", True), ("cli", False), ("ze", True)):
        db.criar_usuario(u, "senha123", u.title(), False, pode)
    h = {u: _login(cliente, u) for u in ("ana", "bia", "cli", "ze")}
    h["lucas"] = _login(cliente, "lucas", "senha-admin")
    r = cliente.post(f"{V}/projetos", json={"nome": "Edifício Aurora", "cliente": "Construtora X"}, headers=h["ana"])
    assert r.status_code == 201 and r.json()["meu_papel"] == "Responsável"
    pid = r.json()["id"]
    for u, papel in (("bia", "Editor"), ("cli", "Leitor")):
        assert cliente.put(f"{V}/projetos/{pid}/membros", json={"username": u, "papel": papel},
                           headers=h["ana"]).status_code == 204
    h["pid"] = pid
    return h


# ---------------------------------------------------------------- autenticação

def test_sem_token_401(cliente):
    assert cliente.get(f"{V}/projetos").status_code == 401
    r = cliente.get(f"{V}/projetos", headers={"Authorization": "Bearer lixo"})
    assert r.status_code == 401 and "expirada" in r.json()["detail"]


def test_login_errado_e_bloqueio(cliente):
    for _ in range(5):
        assert cliente.post(f"{V}/auth/login", json={"username": "lucas", "senha": "x"}).status_code == 401
    r = cliente.post(f"{V}/auth/login", json={"username": "lucas", "senha": "senha-admin"})
    assert r.status_code == 429


def test_eu_e_troca_de_senha(cliente, equipe):
    assert cliente.get(f"{V}/auth/eu", headers=equipe["bia"]).json()["username"] == "bia"
    r = cliente.post(f"{V}/auth/senha", json={"senha_atual": "errada", "nova_senha": "nova-senha"}, headers=equipe["bia"])
    assert r.status_code == 422
    r = cliente.post(f"{V}/auth/senha", json={"senha_atual": "senha123", "nova_senha": "nova-senha"}, headers=equipe["bia"])
    assert r.status_code == 204
    _login(cliente, "bia", "nova-senha")


def test_usuario_removido_perde_acesso_na_hora(cliente, equipe):
    from nucleo.db import nova_sessao
    from nucleo.tabelas import MembroProjeto, Usuario
    from sqlmodel import select

    with nova_sessao() as s:
        u = s.exec(select(Usuario).where(Usuario.username == "ze")).one()
        for m in s.exec(select(MembroProjeto).where(MembroProjeto.usuario_id == u.id)).all():
            s.delete(m)
        s.delete(u)
        s.commit()
    assert cliente.get(f"{V}/projetos", headers=equipe["ze"]).status_code == 401


# ---------------------------------------------------------------- permissões

def test_isolamento_entre_projetos(cliente, equipe):
    pid = equipe["pid"]
    assert cliente.get(f"{V}/projetos", headers=equipe["ze"]).json() == []
    assert cliente.get(f"{V}/projetos/{pid}", headers=equipe["ze"]).status_code == 404
    assert cliente.get(f"{V}/projetos/{pid}/decisoes", headers=equipe["ze"]).status_code == 404
    assert cliente.get(f"{V}/projetos/{pid}/ficha", headers=equipe["ze"]).status_code == 404
    nomes = {p["nome"] for p in cliente.get(f"{V}/projetos", headers=equipe["lucas"]).json()}
    assert "Edifício Aurora" in nomes  # admin vê todos


def test_leitor_le_mas_nao_grava(cliente, equipe):
    pid = equipe["pid"]
    nova = {"titulo": "X", "categoria": "Geral", "impacto": "Alto"}
    assert cliente.post(f"{V}/projetos/{pid}/decisoes", json=nova, headers=equipe["cli"]).status_code == 403
    assert cliente.get(f"{V}/projetos/{pid}/decisoes", headers=equipe["cli"]).status_code == 200
    assert cliente.get(f"{V}/projetos/{pid}/membros", headers=equipe["bia"]).status_code == 403
    assert cliente.get(f"{V}/projetos/{pid}/auditoria", headers=equipe["bia"]).status_code == 403
    assert cliente.get(f"{V}/admin/usuarios", headers=equipe["ana"]).status_code == 403
    assert cliente.get(f"{V}/projetos/{pid}", headers=equipe["cli"]).json()["meu_papel"] == "Leitor"


def test_validacao_de_entrada_422(cliente, equipe):
    pid = equipe["pid"]
    r = cliente.post(f"{V}/projetos/{pid}/decisoes",
                     json={"titulo": "", "categoria": "Inventada", "impacto": "Alto"}, headers=equipe["bia"])
    assert r.status_code == 422


# ---------------------------------------------------------------- fluxo principal

def test_fluxo_ata_decisoes_ficha_pendencias(cliente, equipe):
    pid, bia, cli = equipe["pid"], equipe["bia"], equipe["cli"]
    texto = "[D] Estrutura metálica\n[F] Área do terreno = 1.000\n[F] CA = 2\n[P] Cor da fachada"

    prev = cliente.post(f"{V}/projetos/{pid}/atas/pre-visualizar", json={"texto": texto}, headers=bia).json()
    assert prev["erros"] == [] and len(prev["alteracoes_ficha"]) == 2

    ata = cliente.post(f"{V}/projetos/{pid}/atas", json={
        "titulo": "Alinhamento", "data_reuniao": "2026-10-01", "participantes": "Ana, Bia", "texto": texto,
    }, headers=bia).json()
    assert ata["numero"] == 1 and ata["status"] == "Rascunho"
    assert cliente.get(f"{V}/projetos/{pid}/atas", headers=cli).json() == []  # rascunho escondido

    r = cliente.post(f"{V}/projetos/{pid}/atas/{ata['id']}/fechar", headers=bia)
    assert r.status_code == 200
    assert [d["codigo"] for d in r.json()] == ["D-001"]
    assert cliente.post(f"{V}/projetos/{pid}/atas/{ata['id']}/fechar", headers=bia).status_code == 409

    det = cliente.get(f"{V}/projetos/{pid}/atas/{ata['id']}", headers=cli).json()
    assert det["ata"]["status"] == "Fechada"
    assert [p["titulo"] for p in det["pendencias"]] == ["Cor da fachada"]
    assert {a["origem"] for a in det["alteracoes_ficha"]} == {"Decisão D-001 · Ata 01"}

    f = cliente.get(f"{V}/projetos/{pid}/ficha", headers=cli).json()
    assert {"rotulo": "Potencial construtivo", "texto": "2.000,00 m²", "alerta": False} in f["indicadores"]

    pend = det["pendencias"][0]
    r = cliente.post(f"{V}/projetos/{pid}/pendencias/{pend['id']}/resolver",
                     json={"nova_decisao": {"titulo": "Fachada branca", "categoria": "Arquitetura"}}, headers=bia)
    assert r.status_code == 200 and r.json()["status"] == "Resolvida"
    linha = cliente.get(f"{V}/projetos/{pid}/decisoes", params={"q": "fachada"}, headers=cli).json()
    assert [d["codigo"] for d in linha] == ["D-002"]


def test_decisao_com_anexo_e_download(cliente, equipe):
    pid, bia, cli = equipe["pid"], equipe["bia"], equipe["cli"]
    r = cliente.post(f"{V}/projetos/{pid}/anexos", files={"arquivo": ("planta.pdf", b"%PDF-teste", "application/pdf")},
                     headers=bia)
    assert r.status_code == 201
    chave = r.json()["chave"]
    r = cliente.post(f"{V}/projetos/{pid}/decisoes", json={
        "titulo": "Planta aprovada", "categoria": "Arquitetura", "impacto": "Médio",
        "anexos": [chave], "checklist": [{"texto": "Conferir cotas", "feito": True}],
        "alteracao_ficha": {"grupo": "Programa", "nome": "Nº de pavimentos", "valor": "12"},
    }, headers=bia)
    assert r.status_code == 201, r.text
    d = r.json()
    assert d["anexos"] == [{"indice": 0, "nome": "planta.pdf"}] and d["checklist"][0]["feito"] is True

    link = cliente.get(f"{V}/projetos/{pid}/decisoes/{d['id']}/anexos/0/link", headers=cli).json()["url"]
    arquivo = cliente.get(link)
    assert arquivo.status_code == 200 and arquivo.content == b"%PDF-teste"
    assert cliente.get(link[:-3] + "xyz").status_code == 403
    assert cliente.get(f"{V}/projetos/{pid}/decisoes/{d['id']}/anexos/0/link", headers=equipe["ze"]).status_code == 404


def test_pdfs(cliente, equipe):
    pytest.importorskip("reportlab")
    pid, bia, cli = equipe["pid"], equipe["bia"], equipe["cli"]
    cliente.post(f"{V}/projetos/{pid}/decisoes", json={"titulo": "Laje", "categoria": "Estrutura", "impacto": "Alto"},
                 headers=bia)
    r = cliente.get(f"{V}/projetos/{pid}/relatorios/decisoes.pdf", headers=cli)
    assert r.status_code == 200 and r.content.startswith(b"%PDF")
    r = cliente.get(f"{V}/projetos/{pid}/relatorios/decisoes.pdf", params={"categoria": "Orçamento"}, headers=cli)
    assert r.status_code == 422
    ata = cliente.post(f"{V}/projetos/{pid}/atas", json={"titulo": "A", "data_reuniao": str(datetime.date.today())},
                       headers=bia).json()
    assert cliente.get(f"{V}/projetos/{pid}/atas/{ata['id']}/pdf", headers=bia).content.startswith(b"%PDF")


def test_padrao_construtivo_e_auditoria(cliente, equipe):
    pid = equipe["pid"]
    r = cliente.put(f"{V}/projetos/{pid}/padrao-construtivo",
                    json={"tipologia": "Industrial", "ind_carga_piso": 5}, headers=equipe["bia"])
    assert r.status_code == 200 and r.json()["ind_carga_piso"] == 5
    assert cliente.get(f"{V}/projetos/{pid}/ficha", headers=equipe["cli"]).json()["padrao"]["tipologia"] == "Industrial"
    acoes = [a["acao"] for a in cliente.get(f"{V}/projetos/{pid}/auditoria", headers=equipe["ana"]).json()]
    assert acoes[0] == "padrao.salvar" and "projeto.criar" in acoes


def test_excluir_projeto(cliente, equipe):
    pid = equipe["pid"]
    assert cliente.get(f"{V}/projetos/{pid}/resumo", headers=equipe["ana"]).json()["membros"] == 3
    assert cliente.delete(f"{V}/projetos/{pid}", headers=equipe["bia"]).status_code == 403
    assert cliente.delete(f"{V}/projetos/{pid}", headers=equipe["ana"]).status_code == 204
    assert cliente.get(f"{V}/projetos/{pid}", headers=equipe["ana"]).status_code == 404


def test_saude_opcoes_e_openapi(cliente):
    assert cliente.get("/api/saude").json()["status"] == "ok"
    assert "Orçamento" in cliente.get(f"{V}/opcoes").json()["categorias"]
    caminhos = cliente.get("/api/openapi.json").json()["paths"]
    assert f"{V}/projetos/{{projeto_id}}/atas/{{ata_id}}/fechar" in caminhos

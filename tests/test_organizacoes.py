"""Isolamento entre organizações (escritórios assinantes): nada atravessa a fronteira."""
import io

import pytest
from fastapi.testclient import TestClient

import database as db
from api.autenticacao import LIMITADOR_LOGIN
from api.main import app

V = "/api/v1"


@pytest.fixture
def c():
    LIMITADOR_LOGIN._falhas.clear()
    LIMITADOR_LOGIN._bloqueado_ate.clear()
    with TestClient(app) as cliente:
        yield cliente


def _login(c, username, senha="senha123"):
    r = c.post(f"{V}/auth/login", json={"username": username, "senha": senha})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
def duas_orgs(c):
    """Org A (a inicial): lucas (admin + superadmin) e ana. Org B: beto (admin)."""
    db.criar_usuario("ana", "senha123", "Ana")  # sem criador: entra na única organização
    h = {"lucas": _login(c, "lucas", "senha-admin"), "ana": _login(c, "ana")}
    r = c.post(f"{V}/plataforma/organizacoes", json={
        "nome": "Escritório Beta", "admin": {"username": "beto", "nome_completo": "Beto", "senha": "senha123"},
    }, headers=h["lucas"])
    assert r.status_code == 201, r.text
    h["org_b"] = r.json()["id"]
    h["beto"] = _login(c, "beto")
    h["proj_a"] = c.post(f"{V}/projetos", json={"nome": "Projeto A", "cliente": "X"}, headers=h["ana"]).json()["id"]
    h["proj_b"] = c.post(f"{V}/projetos", json={"nome": "Projeto B", "cliente": "Y"}, headers=h["beto"]).json()["id"]
    return h


def test_projetos_nao_atravessam_organizacoes(c, duas_orgs):
    h = duas_orgs
    assert [p["nome"] for p in c.get(f"{V}/projetos", headers=h["beto"]).json()] == ["Projeto B"]
    nomes_lucas = {p["nome"] for p in c.get(f"{V}/projetos", headers=h["lucas"]).json()}
    assert "Projeto A" in nomes_lucas and "Projeto B" not in nomes_lucas  # admin só da sua
    for quem, alheio in (("beto", h["proj_a"]), ("lucas", h["proj_b"])):
        assert c.get(f"{V}/projetos/{alheio}", headers=h[quem]).status_code == 404
        assert c.get(f"{V}/projetos/{alheio}/decisoes", headers=h[quem]).status_code == 404
        assert c.get(f"{V}/projetos/{alheio}/relatorios/decisoes.pdf", headers=h[quem]).status_code == 404
        r = c.post(f"{V}/projetos/{alheio}/decisoes",
                   json={"titulo": "Invasão", "categoria": "Geral", "impacto": "Alto"}, headers=h[quem])
        assert r.status_code == 403


def test_nao_adiciona_membro_de_outra_organizacao(c, duas_orgs):
    h = duas_orgs
    r = c.put(f"{V}/projetos/{h['proj_b']}/membros", json={"username": "ana", "papel": "Editor"}, headers=h["beto"])
    assert r.status_code == 404 and "não encontrado" in r.json()["detail"]


def test_usuarios_por_organizacao(c, duas_orgs):
    h = duas_orgs
    r = c.post(f"{V}/admin/usuarios", json={"username": "carla", "nome_completo": "Carla", "senha": "senha123"},
               headers=h["beto"])
    assert r.status_code == 201 and r.json()["organizacao_id"] == h["org_b"]
    assert {u["username"] for u in c.get(f"{V}/admin/usuarios", headers=h["beto"]).json()} == {"beto", "carla"}
    assert "carla" not in {u["username"] for u in c.get(f"{V}/admin/usuarios", headers=h["lucas"]).json()}
    # login é único na plataforma
    r = c.post(f"{V}/admin/usuarios", json={"username": "ana", "nome_completo": "Outra", "senha": "senha123"},
               headers=h["beto"])
    assert r.status_code == 422


def test_plataforma_so_para_superadmin(c, duas_orgs):
    h = duas_orgs
    resumo = {o["nome"]: o for o in c.get(f"{V}/plataforma/organizacoes", headers=h["lucas"]).json()}
    assert resumo["Escritório Beta"]["usuarios"] == 1 and resumo["Escritório Beta"]["projetos"] == 1
    assert resumo["Escritório Beta"]["slug"] == "escritorio-beta"
    assert c.get(f"{V}/plataforma/organizacoes", headers=h["beto"]).status_code == 403
    assert c.post(f"{V}/plataforma/organizacoes", json={
        "nome": "Pirata", "admin": {"username": "p", "nome_completo": "P", "senha": "senha123"}},
        headers=h["beto"]).status_code == 403


def test_suspender_organizacao_bloqueia_login_e_tokens(c, duas_orgs):
    h = duas_orgs
    r = c.put(f"{V}/plataforma/organizacoes/{h['org_b']}/situacao", json={"ativa": False}, headers=h["lucas"])
    assert r.status_code == 200 and r.json()["ativa"] is False
    assert c.get(f"{V}/projetos", headers=h["beto"]).status_code == 403  # token já emitido
    r = c.post(f"{V}/auth/login", json={"username": "beto", "senha": "senha123"})
    assert r.status_code == 403 and "suspenso" in r.json()["detail"]
    assert db.autenticar_usuario("beto", "senha123") is None  # tela de login do Flet
    c.put(f"{V}/plataforma/organizacoes/{h['org_b']}/situacao", json={"ativa": True}, headers=h["lucas"])
    _login(c, "beto")
    minha = c.get(f"{V}/organizacao", headers=h["lucas"]).json()["id"]
    r = c.put(f"{V}/plataforma/organizacoes/{minha}/situacao", json={"ativa": False}, headers=h["lucas"])
    assert r.status_code == 422


def test_organizacao_e_auditoria(c, duas_orgs):
    h = duas_orgs
    assert c.get(f"{V}/organizacao", headers=h["beto"]).json()["nome"] == "Escritório Beta"
    assert c.put(f"{V}/organizacao", json={"nome": "Beta Arquitetura"}, headers=h["beto"]).json()["nome"] == "Beta Arquitetura"
    eu = c.get(f"{V}/auth/eu", headers=h["beto"]).json()
    assert eu["organizacao_id"] == h["org_b"] and eu["superadmin"] is False
    acoes_b = [a["acao"] for a in c.get(f"{V}/admin/auditoria", headers=h["beto"]).json()]
    assert "organizacao.renomear" in acoes_b and "projeto.criar" in acoes_b
    projetos_vistos = {a["projeto_id"] for a in c.get(f"{V}/admin/auditoria", headers=h["beto"]).json()}
    assert h["proj_a"] not in projetos_vistos
    assert c.get(f"{V}/admin/auditoria", headers=h["ana"]).status_code == 403


def test_logo_da_empresa_por_organizacao(c, duas_orgs):
    from PIL import Image

    import logos

    png = io.BytesIO()
    Image.new("RGB", (40, 20), "red").save(png, format="PNG")
    r = c.put(f"{V}/admin/logo-empresa", files={"arquivo": ("logo.png", png.getvalue(), "image/png")},
              headers=duas_orgs["beto"])
    assert r.status_code == 204
    org_a = c.get(f"{V}/organizacao", headers=duas_orgs["lucas"]).json()["id"]
    assert logos.logo_empresa(duas_orgs["org_b"]) is not None
    assert logos.logo_empresa(org_a) is None and logos.logo_empresa(None) is None
    logos.caminho_logo_empresa(duas_orgs["org_b"]).unlink()


def test_telas_flet_criam_usuario_na_organizacao_do_admin(c, duas_orgs):
    from nucleo.db import nova_sessao
    from nucleo.servicos.usuarios import buscar_por_username

    with nova_sessao() as s:
        beto = buscar_por_username(s, "beto")
    novo = db.criar_usuario("dani", "senha123", "Dani", criador_id=beto.id)
    assert novo.organizacao_id == duas_orgs["org_b"]
    assert {u.username for u in db.listar_usuarios(beto.id)} == {"beto", "dani"}
    with pytest.raises(PermissionError):  # Dani não é admin
        db.criar_usuario("eva", "senha123", "Eva", criador_id=novo.id)
    with pytest.raises(ValueError, match="organização"):  # duas organizações: CLI precisa dizer qual
        db.criar_usuario("fabio", "senha123", "Fábio")


def test_linha_de_comando_com_organizacao(c, duas_orgs):
    novo = db.criar_usuario("gil", "senha123", "Gil", organizacao_slug="escritorio-beta")
    assert novo.organizacao_id == duas_orgs["org_b"]
    with pytest.raises(ValueError, match="não encontrada"):
        db.criar_usuario("hugo", "senha123", "Hugo", organizacao_slug="nao-existe")
    assert {o.slug for o in db.listar_organizacoes()} == {"organizacao-principal", "escritorio-beta"}

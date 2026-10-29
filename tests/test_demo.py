"""Projeto de demonstração (scripts/seed_demo.py): carga, telas e checklist."""
import pytest

ft = pytest.importorskip("flet")

import database as db  # noqa: E402
from nucleo.db import nova_sessao  # noqa: E402
from nucleo.servicos.usuarios import buscar_por_username  # noqa: E402
from test_tela_plataforma import PaginaFalsa, _todos  # noqa: E402


@pytest.fixture
def demo(monkeypatch):
    from scripts.seed_demo import carregar_pelo_ambiente

    monkeypatch.setenv("DECIDIU_CARREGAR_DEMO", "1")
    monkeypatch.setenv("DECIDIU_DEMO_SENHA", "senha-demo")
    carregar_pelo_ambiente()
    with nova_sessao() as s:
        helena = buscar_por_username(s, "demo.helena")
        marcos = buscar_por_username(s, "demo.marcos")
    assert helena is not None, "a demonstração não foi carregada"
    projeto = db.listar_projetos_do_usuario(helena.id)
    projeto = next(p for p in projeto if p.nome == "Residencial Alto das Quaresmeiras")
    return helena, marcos, projeto


@pytest.mark.parametrize("login", ["helena", "marcos"])
def test_linha_do_tempo_da_demo_monta_com_checklists(demo, login):
    """Reproduz o KeyError 'tarefa' ao entrar como demo.helena na homologação."""
    import tema
    from views.timeline import build_timeline_view

    helena, marcos, projeto = demo
    usuario = helena if login == "helena" else marcos
    pagina = PaginaFalsa()
    pagina.theme_mode = None
    tema.configurar(pagina)
    tela = build_timeline_view(pagina, projeto, usuario, None, None, None, None, None, None, None,
                               on_open_plataforma=lambda _: None)
    marcados = {x.label: x.value for x in _todos(tela) if isinstance(x, ft.Checkbox)}
    assert marcados.get("Quadro de áreas preliminar conferido") is True  # checklist da D-003
    assert marcados.get("Amostras de revestimento recebidas") is False   # checklist da D-035


def test_checklist_aceita_os_dois_formatos():
    """Telas gravam {"tarefa"}, a API grava {"texto"}: as duas leituras precisam funcionar."""
    import json

    from nucleo.servicos.decisoes import texto_do_item
    from relatorio_pdf import _lista_checklist

    itens = [{"tarefa": "Pela tela", "feito": True}, {"texto": "Pela API", "feito": False}]
    assert [texto_do_item(i) for i in itens] == ["Pela tela", "Pela API"]
    assert _lista_checklist(json.dumps(itens)) == [("Pela tela", True), ("Pela API", False)]

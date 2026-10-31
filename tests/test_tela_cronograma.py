"""Tela do cronograma: criar a versão 1, Gantt, revisão com recálculo e decisão, cliente."""
import pytest

ft = pytest.importorskip("flet")

import database as db  # noqa: E402
from test_tela_plataforma import PaginaFalsa, _filhos  # noqa: E402


def _visiveis(c):
    if getattr(c, "visible", True) is False:
        return
    yield c
    for f in _filhos(c):
        yield from _visiveis(f)


def _tudo(pagina, tela):
    yield from _visiveis(tela)
    if pagina.dialogo is not None:
        yield from _visiveis(pagina.dialogo)


def _botao(pagina, tela, texto):
    achados = [x for x in _tudo(pagina, tela) if isinstance(x, (ft.Button, ft.TextButton)) and x.content == texto]
    assert achados, f"botão '{texto}' não aparece"
    return achados[0]


def _campo(pagina, tela, rotulo):
    achados = [x for x in _tudo(pagina, tela) if isinstance(x, (ft.TextField, ft.Dropdown)) and x.label == rotulo]
    assert achados, f"campo '{rotulo}' não aparece"
    return achados[0]


def _textos(pagina, tela):
    return " ".join(x.value for x in _tudo(pagina, tela) if isinstance(x, ft.Text) and x.value)


def _digitar(pagina, tela, rotulo, valor):
    campo = _campo(pagina, tela, rotulo)
    campo.value = valor
    if campo.on_change:
        campo.on_change(None)


def _tela(projeto, usuario):
    from views.cronograma import build_cronograma_view

    pagina = PaginaFalsa()
    return pagina, build_cronograma_view(pagina, projeto, usuario, None, None)


DATAS = {
    "Kick-off – data": "19/08/2025",
    "Estudo preliminar – início": "20/08/2025", "Estudo preliminar – entrega": "30/10/2025",
    "Anteprojeto – início": "03/11/2025", "Anteprojeto – entrega": "30/01/2026",
    "Projeto básico – início": "02/02/2026", "Projeto básico – entrega": "30/04/2026",
    "Projeto executivo – início": "04/05/2026", "Projeto executivo – entrega": "30/09/2026",
    "Liberado para obra – data": "15/10/2026",
}


def _criar_v1(admin, projeto):
    pagina, tela = _tela(projeto, admin)
    _botao(pagina, tela, "Criar cronograma").on_click(None)
    for rotulo, valor in DATAS.items():
        _digitar(pagina, tela, rotulo, valor)
    _botao(pagina, tela, "Salvar cronograma").on_click(None)
    return pagina, tela


def test_sem_cronograma_mostra_aviso_e_cria_a_versao_1(admin, projeto_padrao):
    pagina, tela = _tela(projeto_padrao, admin)
    assert "ainda não tem cronograma" in _textos(pagina, tela)
    pagina, tela = _criar_v1(admin, projeto_padrao)
    assert "Versão 1" in _textos(pagina, tela) and "Liberado para obra: 15/10/2026" in _textos(pagina, tela)
    from nucleo.db import nova_sessao
    from nucleo.servicos import cronograma
    from nucleo.ator import Ator
    with nova_sessao() as s:
        dados = cronograma.obter(s, Ator.de_usuario(admin), projeto_padrao.id)
    assert [i.nome for i in dados["itens"]] == ["Kick-off", "Estudo preliminar", "Anteprojeto", "Projeto básico",
                                               "Projeto executivo", "Liberado para obra"]  # conceitual desmarcado


def test_gantt_tem_uma_linha_por_item_e_losango_nos_marcos(admin, projeto_padrao):
    pagina, tela = _criar_v1(admin, projeto_padrao)
    linhas = [x for x in _visiveis(tela) if getattr(x, "data", None) and str(x.data).startswith("linha:")]
    assert [x.data for x in linhas] == [f"linha:{n}" for n in ("Kick-off", "Estudo preliminar", "Anteprojeto",
                                                                "Projeto básico", "Projeto executivo",
                                                                "Liberado para obra")]
    losangos = [x for x in _visiveis(tela) if isinstance(x, ft.Icon) and x.icon == ft.Icons.DIAMOND]
    assert len(losangos) >= 2


def test_revisao_recalcula_as_seguintes_e_exige_decisao(admin, projeto_padrao):
    pagina, tela = _criar_v1(admin, projeto_padrao)
    _botao(pagina, tela, "Revisar cronograma").on_click(None)
    _digitar(pagina, tela, "Projeto básico – entrega", "30/05/2026")  # +30 dias
    assert _campo(pagina, tela, "Projeto executivo – entrega").value == "30/10/2026"
    assert _campo(pagina, tela, "Liberado para obra – data").value == "14/11/2026"
    assert "recalculada" in _textos(pagina, tela)
    _botao(pagina, tela, "Salvar revisão").on_click(None)
    assert "Indique a decisão" in _textos(pagina, tela)  # sem decisão não grava
    decisao = _campo(pagina, tela, "Decisão que motivou")
    decisao.value = "nova"
    decisao.on_select(None)
    _digitar(pagina, tela, "Título da nova decisão", "Prazo estendido pela prefeitura")
    _botao(pagina, tela, "Salvar revisão").on_click(None)
    texto = _textos(pagina, tela)
    assert "Versão 2" in texto and "D-001" in texto and "+30 dias" in texto
    assert [d.titulo for d in db.listar_decisoes_projeto(projeto_padrao.id)] == ["Prazo estendido pela prefeitura"]


def test_adicionar_marco_proprio(admin, projeto_padrao):
    pagina, tela = _tela(projeto_padrao, admin)
    _botao(pagina, tela, "Criar cronograma").on_click(None)
    for rotulo, valor in DATAS.items():
        _digitar(pagina, tela, rotulo, valor)
    _botao(pagina, tela, "+ Adicionar marco").on_click(None)
    _digitar(pagina, tela, "Nome do novo item", "Lançamento comercial")
    _digitar(pagina, tela, "Lançamento comercial – data", "01/03/2026")
    _botao(pagina, tela, "Salvar cronograma").on_click(None)
    assert "Lançamento comercial" in _textos(pagina, tela)


def test_cliente_ve_sem_poder_criar_ou_revisar(admin, projeto_padrao):
    from nucleo.db import nova_sessao
    from nucleo.servicos.usuarios import buscar_por_username

    db.criar_usuario("cli.c", "senha123", "Cliente", pode_criar_projetos=False)
    db.definir_membro(projeto_padrao.id, "cli.c", "Leitor", admin.id)
    with nova_sessao() as s:
        cliente = buscar_por_username(s, "cli.c")
    pagina, tela = _tela(projeto_padrao, cliente)
    assert not [x for x in _visiveis(tela) if isinstance(x, ft.Button) and x.content == "Criar cronograma"]
    _criar_v1(admin, projeto_padrao)
    pagina, tela = _tela(projeto_padrao, cliente)
    assert "Versão 1" in _textos(pagina, tela)
    assert not [x for x in _visiveis(tela) if isinstance(x, ft.Button) and x.content == "Revisar cronograma"]


def test_linha_do_tempo_tem_menu_e_selo_da_decisao(admin, projeto_padrao):
    import tema
    from test_tela_plataforma import _todos
    from views.timeline import build_timeline_view

    pagina, tela = _criar_v1(admin, projeto_padrao)
    _botao(pagina, tela, "Revisar cronograma").on_click(None)
    _digitar(pagina, tela, "Projeto executivo – entrega", "15/10/2026")
    decisao = _campo(pagina, tela, "Decisão que motivou")
    decisao.value = "nova"
    decisao.on_select(None)
    _digitar(pagina, tela, "Título da nova decisão", "Executivo estendido")
    _botao(pagina, tela, "Salvar revisão").on_click(None)

    pagina = PaginaFalsa()
    pagina.theme_mode = None
    tema.configurar(pagina)
    timeline = build_timeline_view(pagina, projeto_padrao, admin, None, None, None, None, None, None, None,
                                   on_open_plataforma=lambda _: None, on_open_cronograma=lambda: None)
    textos = " ".join(x.value for x in _todos(timeline) if isinstance(x, ft.Text) and x.value)
    assert "Impacta cronograma · Versão 2" in textos
    menu = {x.title.value for x in _todos(timeline.drawer) if isinstance(x, ft.ListTile)}
    assert "Cronograma" in menu

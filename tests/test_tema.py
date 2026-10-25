"""Aparência: modo claro/escuro, contraste dos selos e cabeçalho com ações em destaque."""
import datetime
import pathlib
import re

import pytest

ft = pytest.importorskip("flet")

import database as db  # noqa: E402
import tema  # noqa: E402
from nucleo.db import nova_sessao  # noqa: E402
from nucleo.servicos.usuarios import buscar_por_username  # noqa: E402
from test_tela_plataforma import PaginaFalsa, _textos, _todos  # noqa: E402

VIEWS = pathlib.Path(__file__).parent.parent / "views"


def _usuario(login):
    with nova_sessao() as s:
        return buscar_por_username(s, login)


def _pagina(modo):
    pagina = PaginaFalsa()
    pagina.theme_mode = None
    tema.configurar(pagina)
    tema.aplicar_modo(pagina, modo)
    return pagina


# ---------------------------------------------------------------- cores

def test_selos_com_texto_escuro_tem_contraste_alto():
    fundos = [f for f, _ in tema.CORES_CATEGORIA.values()]
    fundos += list(tema.CORES_IMPACTO.values()) + list(tema.CORES_SITUACAO.values())
    for fundo in fundos:
        assert tema.contraste(fundo, tema.TEXTO_SELO) >= 7, fundo  # AAA (antes: 2,6 a 4,8)


def test_cores_adaptativas_legiveis_nos_dois_modos():
    claro, escuro = _pagina(tema.CLARO), _pagina(tema.ESCURO)
    for pagina, fundo in ((claro, "#FFFFFF"), (escuro, "#1C1B1F")):
        assert tema.contraste(tema.sucesso(pagina), fundo) >= 4.5
        assert tema.contraste(tema.aviso(pagina), fundo) >= 4.5
        for tipo in "DPF":  # texto normal do modo sobre o fundo das linhas [D] [P] [F]
            texto = "#1C1B1F" if pagina is claro else "#E6E1E5"
            assert tema.contraste(tema.fundo_marcacao(pagina, tipo), texto) >= 4.5


def test_telas_sem_cores_fixas_de_paleta():
    """Cores fixas (GREY_400, BLUE_200...) somem no modo claro. Só cores por papel."""
    permitidas = {"WHITE"}  # fundo branco do logo, como no PDF
    for arquivo in VIEWS.glob("*.py"):
        for cor in re.findall(r"ft\.Colors\.([A-Z_0-9]+)", arquivo.read_text()):
            fixa = re.search(r"_\d+$", cor) or cor in {"WHITE_70", "BLACK"}
            assert not fixa or cor in permitidas, f"{arquivo.name}: ft.Colors.{cor}"


def test_preferencia_vazia_e_claro():
    pagina = _pagina(None)
    assert tema.modo_atual(pagina) == tema.CLARO
    tema.aplicar_modo(pagina, "claro")
    assert pagina.theme_mode == ft.ThemeMode.LIGHT and tema.oposto("claro") == "escuro"


# ---------------------------------------------------------------- telas nos dois modos

@pytest.fixture
def cenario():
    lucas = _usuario("lucas")
    projeto = db.listar_projetos_do_usuario(lucas.id)[0]
    db.adicionar_decisao(projeto.id, "Laje", "Estrutura", "d", "j", None, "Alto", "Lucas", None, None,
                         usuario_id=lucas.id)
    ata = db.criar_reuniao(projeto.id, "Kickoff", datetime.date.today(), "", "[D] X\n[P] Y", "Lucas", lucas.id)
    db.fechar_reuniao(ata.id, "Lucas", lucas.id)
    db.criar_pendencia(projeto.id, "Cor", autor="Lucas", usuario_id=lucas.id)
    return lucas, projeto


def _timeline(pagina, usuario, projeto, trocar=None):
    from views.timeline import build_timeline_view

    return build_timeline_view(pagina, projeto, usuario, None, None, None, None, None, None, None,
                               on_open_plataforma=lambda _: None, on_trocar_tema=trocar)


@pytest.mark.parametrize("modo", [tema.CLARO, tema.ESCURO])
def test_todas_as_telas_montam_nos_dois_modos(cenario, modo):
    from views.atas import build_atas_view
    from views.ficha import build_ficha_view
    from views.login import build_login_view
    from views.pendencias import build_pendencias_view
    from views.plataforma import build_plataforma_view
    from views.sem_projeto import build_sem_projeto_view

    lucas, projeto = cenario
    pagina = _pagina(modo)
    telas = [
        _timeline(pagina, lucas, projeto),
        build_atas_view(pagina, projeto, lucas, None, None, None)[0],
        build_pendencias_view(pagina, projeto, lucas, None, None),
        build_ficha_view(pagina, projeto, lucas, None, None),
        build_plataforma_view(pagina, lucas, None, None),
        build_login_view(lambda *a: None, pagina),
        build_sem_projeto_view(pagina, lucas, None, None),
    ]
    assert all(isinstance(t, ft.View) for t in telas)
    assert "Estrutura" in _textos(telas[0]) and "Fechada" in _textos(telas[1])


def _menu_visivel(view) -> set:
    return {b.title.value for b in _todos(view.drawer) if isinstance(b, ft.ListTile) and b.visible is not False}


def test_tela_principal_tem_so_busca_e_acoes_principais(cenario):
    lucas, projeto = cenario
    view = _timeline(_pagina(tema.ESCURO), lucas, projeto)
    acoes, separador, lista = view.controls
    destaque = {b.content: b for b in _todos(acoes) if isinstance(b, ft.FilledButton)}
    assert set(destaque) == {"+ Nova Decisão", "Atas de Reunião"}
    assert destaque["Atas de Reunião"].style.bgcolor == ft.Colors.TERTIARY  # cor diferente
    assert destaque["+ Nova Decisão"].style.bgcolor is None  # azul principal do tema
    assert any(isinstance(x, ft.TextField) and x.label == "Buscar decisões" for x in _todos(acoes))
    assert isinstance(separador, ft.Divider) and isinstance(lista, ft.ListView) and lista.expand
    # nada além disso na área principal: o resto foi para o menu
    assert not [b for b in _todos(acoes) if isinstance(b, (ft.FilledTonalButton, ft.TextButton, ft.ListTile))]
    assert view.appbar.title.controls[0].value == projeto.nome


def test_menu_lateral_tem_as_demais_opcoes(cenario):
    lucas, projeto = cenario
    view = _timeline(_pagina(tema.ESCURO), lucas, projeto, trocar=lambda: None)
    assert isinstance(view.drawer, ft.NavigationDrawer)
    assert any(isinstance(x, ft.Dropdown) and x.label == "Projeto" for x in _todos(view.drawer))
    assert {
        "Pendências de decisão (2)", "Ficha do Empreendimento", "Relatório PDF",
        "Novo projeto", "Editar projeto", "Membros e acessos", "Excluir projeto",
        "Usuários da organização", "Logo da empresa (PDFs)", "Plataforma: organizações",
        "Modo claro", "Minha conta (senha)", "Sair",
    } <= _menu_visivel(view)


def test_item_do_menu_fecha_o_menu_e_executa(cenario):
    import asyncio

    lucas, projeto = cenario
    chamadas = []
    view = _timeline(_pagina(tema.ESCURO), lucas, projeto, trocar=lambda: chamadas.append("tema"))
    item = next(b for b in _todos(view.drawer) if isinstance(b, ft.ListTile) and b.title.value == "Modo claro")
    asyncio.run(item.on_click(None))  # fora de uma página real, fechar o menu é ignorado
    assert chamadas == ["tema"]
    claro = _timeline(_pagina(tema.CLARO), lucas, projeto, trocar=lambda: None)
    assert "Modo escuro" in _menu_visivel(claro)


def test_permissoes_nao_mudaram(cenario):
    """Leitor: sem 'Nova Decisão' e sem gestão do projeto; vê Atas, Ficha, Relatório e Pendências."""
    lucas, projeto = cenario
    db.criar_usuario("cli", "senha123", "Cliente", pode_criar_projetos=False)
    db.definir_membro(projeto.id, "cli", "Leitor", lucas.id)
    view = _timeline(_pagina(tema.CLARO), _usuario("cli"), projeto)
    botoes = {b.content: b.visible for b in _todos(view.controls[0]) if isinstance(b, ft.FilledButton)}
    assert botoes == {"+ Nova Decisão": False, "Atas de Reunião": True}
    menu = _menu_visivel(view)
    assert {"Ficha do Empreendimento", "Relatório PDF", "Sair"} <= menu
    assert any(m.startswith("Pendências") for m in menu)
    assert not {"Novo projeto", "Editar projeto", "Membros e acessos", "Excluir projeto",
                "Usuários da organização", "Plataforma: organizações"} & menu
    secoes = [x for x in _todos(view.drawer) if isinstance(x, ft.Container)
              and isinstance(x.content, ft.Text) and x.content.value == "GESTÃO DO PROJETO"]
    assert secoes and secoes[0].visible is False


def test_celular_margens_menores_e_rotulos_curtos(cenario):
    lucas, projeto = cenario
    pagina = _pagina(tema.ESCURO)
    pagina.width = 390
    view = _timeline(pagina, lucas, projeto)
    assert view.padding.left == 8
    assert {b.content for b in _todos(view.controls[0]) if isinstance(b, ft.FilledButton)} == {"+ Decisão", "Atas"}

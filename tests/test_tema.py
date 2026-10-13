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


def test_preferencia_vazia_e_escuro():
    pagina = _pagina(None)
    assert tema.modo_atual(pagina) == tema.ESCURO
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


def test_cabecalho_destaca_nova_decisao_e_atas(cenario):
    lucas, projeto = cenario
    view = _timeline(_pagina(tema.ESCURO), lucas, projeto)
    destaque = {b.content: b for b in _todos(view) if isinstance(b, ft.FilledButton)}
    assert set(destaque) == {"+ Nova Decisão", "Atas de Reunião"}
    assert destaque["Atas de Reunião"].style.bgcolor == ft.Colors.TERTIARY  # cor diferente
    assert destaque["+ Nova Decisão"].style.bgcolor is None  # azul principal do tema
    secundarios = {b.content for b in _todos(view) if isinstance(b, ft.FilledTonalButton)}
    assert {"Ficha do Empreendimento", "Relatório PDF"} <= secundarios
    assert any(c.startswith("Pendências") for c in secundarios)


def test_separador_entre_acoes_e_busca(cenario):
    lucas, projeto = cenario
    controles = _timeline(_pagina(tema.ESCURO), lucas, projeto).controls
    assert isinstance(controles[1], ft.Divider)
    assert isinstance(controles[2], ft.ResponsiveRow)
    assert any(isinstance(x, ft.TextField) and x.label == "Buscar decisões" for x in _todos(controles[2]))


def test_botao_de_tema_alterna_e_mostra_o_modo_oposto(cenario):
    lucas, projeto = cenario
    chamadas = []
    escuro = _timeline(_pagina(tema.ESCURO), lucas, projeto, trocar=lambda: chamadas.append(1))
    botao = next(b for b in _todos(escuro) if isinstance(b, ft.IconButton) and b.tooltip == "Mudar para o modo claro")
    botao.on_click(None)
    assert chamadas == [1]
    claro = _timeline(_pagina(tema.CLARO), lucas, projeto, trocar=lambda: None)
    assert any(isinstance(b, ft.IconButton) and b.tooltip == "Mudar para o modo escuro" for b in _todos(claro))


def test_permissoes_do_cabecalho_nao_mudaram(cenario):
    """Leitor continua sem 'Nova Decisão' e sem gestão do projeto; vê Atas, Ficha e Relatório."""
    lucas, projeto = cenario
    db.criar_usuario("cli", "senha123", "Cliente", pode_criar_projetos=False)
    db.definir_membro(projeto.id, "cli", "Leitor", lucas.id)
    view = _timeline(_pagina(tema.CLARO), _usuario("cli"), projeto)
    visiveis = {b.content for b in _todos(view)
                if isinstance(b, (ft.Button, ft.TextButton)) and b.visible is not False}
    assert "+ Nova Decisão" not in visiveis
    assert not {"Novo Projeto", "Editar Projeto", "Membros", "Excluir Projeto"} & visiveis
    assert {"Atas de Reunião", "Ficha do Empreendimento", "Relatório PDF"} <= visiveis
    dicas = {b.tooltip for b in _todos(view) if isinstance(b, ft.IconButton)}
    assert "Usuários da organização" not in dicas and not any("Plataforma" in (d or "") for d in dicas)

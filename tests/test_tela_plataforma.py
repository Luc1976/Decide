"""Tela da plataforma (Flet), dirigida como o usuário faria: clicando e preenchendo campos."""
import pytest

ft = pytest.importorskip("flet")

import database as db  # noqa: E402
from nucleo.db import nova_sessao  # noqa: E402
from nucleo.servicos.usuarios import buscar_por_username  # noqa: E402
from nucleo.tabelas import Organizacao  # noqa: E402


class PaginaFalsa:
    """O mínimo de ft.Page que as telas usam."""

    def __init__(self, largura=1200):
        self.width = largura
        self.web = True
        self.dialogos = []

    def show_dialog(self, dialogo):
        self.dialogos.append(dialogo)

    def pop_dialog(self):
        self.dialogos.pop()

    def update(self, *_):
        pass

    def launch_url(self, url, *_, **__):
        self.links = getattr(self, "links", []) + [url]

    @property
    def dialogo(self):
        return self.dialogos[-1] if self.dialogos else None


def _filhos(c):
    for nome in ("controls", "content", "actions", "title", "label", "appbar", "drawer", "leading", "subtitle"):
        v = getattr(c, nome, None)
        if isinstance(v, list):
            yield from v
        elif v is not None and not isinstance(v, (str, int, float, bool)):
            yield v


def _todos(c):
    yield c
    for f in _filhos(c):
        yield from _todos(f)


def _textos(c) -> str:
    return " ".join(x.value for x in _todos(c) if isinstance(x, ft.Text) and x.value)


def _botao(raiz, texto):
    achados = [x for x in _todos(raiz) if isinstance(x, (ft.Button, ft.TextButton)) and x.content == texto]
    assert achados, f"botão '{texto}' não encontrado"
    return achados[0]


def _campo(raiz, rotulo):
    return next(x for x in _todos(raiz) if isinstance(x, ft.TextField) and x.label == rotulo)


def _clicar(raiz, texto):
    _botao(raiz, texto).on_click(None)


def _usuario(username):
    with nova_sessao() as s:
        return buscar_por_username(s, username)


@pytest.fixture
def tela():
    from views.plataforma import build_plataforma_view

    pagina = PaginaFalsa()
    view = build_plataforma_view(pagina, _usuario("lucas"), on_logout=None, on_voltar=None)
    return pagina, view


def _criar_pela_tela(pagina, view, nome="Studio Beta", login="joana", senha="senha123", senha2=None):
    _clicar(view, "+ Nova Organização")
    dialogo = pagina.dialogo
    _campo(dialogo, "Nome do escritório").value = nome
    _campo(dialogo, "Nome do administrador").value = "Joana"
    _campo(dialogo, "Usuário (login)").value = login
    _campo(dialogo, "Senha inicial").value = senha
    _campo(dialogo, "Repita a senha").value = senha if senha2 is None else senha2
    _clicar(dialogo, "Criar organização")
    return dialogo


def test_lista_inicial_com_a_propria_organizacao(tela):
    _, view = tela
    texto = _textos(view)
    assert "1 organização · 1 ativa(s) · 1 usuário · 1 projeto" in texto
    assert "(a sua)" in texto and "A sua organização não pode ser suspensa." in texto
    assert not [x for x in _todos(view) if isinstance(x, ft.TextButton) and x.content == "Suspender"]


def test_criar_organizacao_pela_tela(tela):
    pagina, view = tela
    _criar_pela_tela(pagina, view)
    assert pagina.dialogo.title.value == "Organização criada"
    assert "joana" in _textos(pagina.dialogo) and "senha123" not in _textos(pagina.dialogo)
    with nova_sessao() as s:
        joana = buscar_por_username(s, "joana")
        org = s.get(Organizacao, joana.organizacao_id)
        assert (org.nome, joana.admin, joana.superadmin) == ("Studio Beta", True, False)
    assert "2 organizações" in _textos(view) and "Studio Beta" in _textos(view)
    assert db.autenticar_usuario("joana", "senha123") is not None


def test_erros_aparecem_no_formulario(tela):
    pagina, view = tela
    dialogo = _criar_pela_tela(pagina, view, senha2="outra-senha")
    assert pagina.dialogo is dialogo and "não conferem" in _textos(dialogo)
    pagina.pop_dialog()
    dialogo = _criar_pela_tela(pagina, view, login="lucas")  # login já existe
    assert pagina.dialogo is dialogo and "já existe" in _textos(dialogo)


def test_suspender_e_reativar(tela):
    pagina, view = tela
    _criar_pela_tela(pagina, view)
    pagina.pop_dialog()
    _clicar(view, "Suspender")
    assert "Suspender “Studio Beta”?" in _textos(pagina.dialogo)
    _clicar(pagina.dialogo, "Suspender")
    assert pagina.dialogo is None
    assert "Suspensa" in _textos(view) and db.autenticar_usuario("joana", "senha123") is None
    _clicar(view, "Reativar")
    assert db.autenticar_usuario("joana", "senha123") is not None


def test_busca_e_filtro(tela):
    pagina, view = tela
    _criar_pela_tela(pagina, view)
    pagina.pop_dialog()
    busca = _campo(view, "Buscar organização")
    busca.value = "beta"
    busca.on_change(None)
    assert "Studio Beta" in _textos(view) and "Organização principal" not in _textos(view)
    busca.value = ""
    filtro = next(x for x in _todos(view) if isinstance(x, ft.Dropdown))
    filtro.value = "Suspensas"
    filtro.on_select(None)
    assert "Nenhuma organização encontrada." in _textos(view)


def test_quem_nao_e_superadmin_ve_acesso_restrito():
    from views.plataforma import build_plataforma_view

    db.criar_usuario("ana", "senha123", "Ana", admin=True)
    view = build_plataforma_view(PaginaFalsa(), _usuario("ana"), None, None)
    assert "Acesso restrito" in _textos(view)


def test_celular_usa_rotulo_curto():
    from views.plataforma import build_plataforma_view

    view = build_plataforma_view(PaginaFalsa(largura=390), _usuario("lucas"), None, None)
    _botao(view, "+ Organização")

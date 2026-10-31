"""Tela Documentos de referência, dirigida como o usuário (clicando e preenchendo)."""
import asyncio
from types import SimpleNamespace

import pytest

ft = pytest.importorskip("flet")

import database as db  # noqa: E402
from nucleo.armazenamento import armazenamento_padrao  # noqa: E402
from nucleo.db import nova_sessao  # noqa: E402
from nucleo.servicos.usuarios import buscar_por_username  # noqa: E402
from test_tela_plataforma import PaginaFalsa, _campo, _clicar, _textos, _todos  # noqa: E402


def _usuario(login):
    with nova_sessao() as s:
        return buscar_por_username(s, login)


@pytest.fixture
def cenario():
    lucas = _usuario("lucas")
    projeto = db.listar_projetos_do_usuario(lucas.id)[0]
    return lucas, projeto


def _tela(usuario, projeto, pagina=None):
    from views.documentos import build_documentos_view

    pagina = pagina or PaginaFalsa()
    return pagina, build_documentos_view(pagina, projeto, usuario, None, None)


def _cartao(view, nome):
    """O cartão (Container) cujo título é 'nome'."""
    lista = view.controls[-1]
    return next(c for c in lista.controls if nome in _textos(c).split(" (acrescentado)")[0] and
                any(isinstance(t, ft.Text) and t.value == nome for t in _todos(c)))


def _doc(projeto, usuario, nome):
    return next(d for d in db.listar_documentos(projeto.id, usuario.id) if d.nome == nome)


def test_lista_padrao_e_resumo(cenario):
    lucas, projeto = cenario
    _, view = _tela(lucas, projeto)
    texto = _textos(view)
    for nome in ("Levantamento topográfico", "Projetos preliminares", "Layout", "Relatórios de Sondagens SPT",
                 "Relatório de sondagem a trado (CBR)", "BEP / EIR", "Outros"):
        assert nome in texto
    assert "0 de 7 recebidos · 7 pendente(s)" in texto


def test_marcar_situacao_pelo_seletor(cenario):
    lucas, projeto = cenario
    _, view = _tela(lucas, projeto)
    seletor = next(x for x in _todos(_cartao(view, "Layout")) if isinstance(x, ft.SegmentedButton))
    assert [s.value for s in seletor.segments] == ["Recebido", "Pendente", "N/A"]
    seletor.on_change(SimpleNamespace(control=SimpleNamespace(selected=["Recebido"])))
    assert _doc(projeto, lucas, "Layout").situacao == "Recebido"
    assert "1 de 7 recebidos" in _textos(view) and "Recebido em" in _textos(_cartao(view, "Layout"))
    seletor = next(x for x in _todos(_cartao(view, "BEP / EIR")) if isinstance(x, ft.SegmentedButton))
    seletor.on_change(SimpleNamespace(control=SimpleNamespace(selected=["N/A"])))
    assert "1 de 6 recebidos · 5 pendente(s) · 1 não se aplica(m)" in _textos(view)


def test_novo_item_editar_e_excluir(cenario):
    lucas, projeto = cenario
    pagina, view = _tela(lucas, projeto)
    _clicar(view, "+ Novo Item")
    _campo(pagina.dialogo, "Documento ou informação").value = "Licença ambiental"
    _campo(pagina.dialogo, "Observação (opcional)").value = "pedir à prefeitura"
    _clicar(pagina.dialogo, "Salvar")
    assert pagina.dialogo is None and "Licença ambiental" in _textos(view)

    _clicar(_cartao(view, "Licença ambiental"), "Editar")
    assert _campo(pagina.dialogo, "Documento ou informação").disabled is False
    _campo(pagina.dialogo, "Observação (opcional)").value = "protocolo 123"
    _clicar(pagina.dialogo, "Salvar")
    assert _doc(projeto, lucas, "Licença ambiental").observacao == "protocolo 123"

    _clicar(_cartao(view, "Licença ambiental"), "Excluir")
    _clicar(pagina.dialogo, "Confirmar")
    assert "Licença ambiental" not in _textos(view)


def test_item_padrao_nao_exclui_nem_renomeia(cenario):
    lucas, projeto = cenario
    pagina, view = _tela(lucas, projeto)
    cartao = _cartao(view, "Layout")
    assert not [b for b in _todos(cartao) if isinstance(b, ft.TextButton) and b.content == "Excluir"]
    _clicar(cartao, "Editar")
    assert _campo(pagina.dialogo, "Documento ou informação").disabled is True


def _arquivos(projeto, usuario, nome):
    return next(a for d, a in db.listar_documentos_com_arquivos(projeto.id, usuario.id) if d.nome == nome)


def test_anexar_com_data_de_recebimento(cenario):
    import datetime

    lucas, projeto = cenario
    pagina = PaginaFalsa()
    pagina.web = False  # modo app: o arquivo chega em bytes
    _, view = _tela(lucas, projeto, pagina)

    async def escolher(**_):
        return [SimpleNamespace(id=1, name="topografia R01.pdf", size=4, bytes=b"%PDF", path=None)]

    view.services[0].pick_files = escolher
    _clicar(_cartao(view, "Levantamento topográfico"), "Anexar arquivo")
    dialogo = pagina.dialogo
    data = _campo(dialogo, "Data de recebimento")
    assert data.value == f"{datetime.date.today():%d/%m/%Y}"  # hoje, já preenchido
    data.value = "31/12/2099"
    asyncio.run(next(b for b in _todos(dialogo) if isinstance(b, ft.Button) and b.content == "Escolher arquivos")
                .on_click(None))
    assert "futura" in _textos(dialogo) and pagina.dialogo is dialogo
    data.value = "02/09/2026"
    asyncio.run(next(b for b in _todos(dialogo) if isinstance(b, ft.Button) and b.content == "Escolher arquivos")
                .on_click(None))

    [arq] = _arquivos(projeto, lucas, "Levantamento topográfico")
    assert (arq.nome, arq.data_recebimento) == ("topografia R01.pdf", datetime.date(2026, 9, 2))
    doc = _doc(projeto, lucas, "Levantamento topográfico")
    assert (doc.situacao, doc.data_recebimento) == ("Recebido", datetime.date(2026, 9, 2))
    assert armazenamento_padrao().ler(arq.chave) == b"%PDF"
    cartao = _cartao(view, "Levantamento topográfico")
    assert any(isinstance(b, ft.TextButton) and b.content == "topografia R01.pdf" for b in _todos(cartao))
    assert "recebido em 02/09/2026" in _textos(cartao)

    # corrigir a data do arquivo
    next(b for b in _todos(cartao) if isinstance(b, ft.IconButton) and b.tooltip == "Corrigir a data de recebimento"
         ).on_click(None)
    _campo(pagina.dialogo, "Recebido em").value = "01/09/2026"
    _clicar(pagina.dialogo, "Salvar")
    assert _arquivos(projeto, lucas, "Levantamento topográfico")[0].data_recebimento == datetime.date(2026, 9, 1)

    # corrigir a data do item
    _clicar(_cartao(view, "Levantamento topográfico"), "Editar")
    campo = _campo(pagina.dialogo, "Recebido em")
    assert campo.visible and campo.value == "02/09/2026"
    campo.value = "30/08/2026"
    _clicar(pagina.dialogo, "Salvar")
    assert _doc(projeto, lucas, "Levantamento topográfico").data_recebimento == datetime.date(2026, 8, 30)
    armazenamento_padrao().apagar([arq.chave])


def test_pendente_nao_mostra_data_no_editar(cenario):
    lucas, projeto = cenario
    pagina, view = _tela(lucas, projeto)
    _clicar(_cartao(view, "Layout"), "Editar")
    assert _campo(pagina.dialogo, "Recebido em").visible is False


def test_botao_pdf_gera_e_abre(cenario):
    lucas, projeto = cenario
    pytest.importorskip("reportlab")
    pagina, view = _tela(lucas, projeto)
    botao = next(b for b in _todos(view) if isinstance(b, ft.FilledTonalButton) and b.content == "PDF")
    asyncio.run(botao.on_click(None))
    # o Flet atual não tem page.launch_url: o link do PDF vem numa janela (views/abrir_link.py)
    links = [s.url for x in _todos(pagina.dialogo) if isinstance(x, ft.Text)
             for s in (x.spans or []) if getattr(s, "url", None)]
    assert links and links[0].startswith("/anexo/")
    assert "PDF gerado." in _textos(view)


def test_cliente_so_acompanha(cenario):
    lucas, projeto = cenario
    db.criar_usuario("cli", "senha123", "Cliente", pode_criar_projetos=False)
    db.definir_membro(projeto.id, "cli", "Leitor", lucas.id)
    _, view = _tela(_usuario("cli"), projeto)
    assert not [x for x in _todos(view) if isinstance(x, ft.SegmentedButton)]
    assert not [b for b in _todos(view) if isinstance(b, (ft.Button, ft.TextButton))
                and b.content in ("+ Novo Item", "Anexar arquivo", "Editar", "Excluir") and b.visible is not False]
    assert "Pendente" in _textos(view)  # situação aparece como selo


def test_filtro(cenario):
    lucas, projeto = cenario
    db.atualizar_documento(_doc(projeto, lucas, "Layout").id, lucas.id, situacao="Recebido")
    _, view = _tela(lucas, projeto)
    filtro = next(x for x in _todos(view) if isinstance(x, ft.Dropdown))
    filtro.value = "Recebidos"
    filtro.on_select(None)
    nomes = [t.value for c in view.controls[-1].controls for t in _todos(c)
             if isinstance(t, ft.Text) and t.weight == ft.FontWeight.BOLD]
    assert nomes == ["Layout"]


def test_acesso_pela_ficha_com_contagem(cenario):
    from views.ficha import build_ficha_view

    lucas, projeto = cenario
    db.atualizar_documento(_doc(projeto, lucas, "Layout").id, lucas.id, situacao="Recebido")
    chamadas = []
    view = build_ficha_view(PaginaFalsa(), projeto, lucas, None, None, on_open_documentos=lambda _: chamadas.append(1))
    botao = next(b for b in _todos(view) if isinstance(b, ft.FilledButton)
                 and str(b.content).startswith("Documentos de referência"))
    assert botao.content == "Documentos de referência (1/7)"
    botao.on_click(None)
    assert chamadas == [1]

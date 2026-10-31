"""Tela única da ficha: tipologia em lista, cards do catálogo, cascata e "Outro"."""
import pytest

ft = pytest.importorskip("flet")

import database as db  # noqa: E402
from test_tela_plataforma import PaginaFalsa, _filhos  # noqa: E402

P, T = "Programa", "Uso / tipologia"
SIS = "Sistemas construtivos"


def _visiveis(c):
    """Controles que aparecem na tela (o controle e todos os pais visíveis)."""
    if getattr(c, "visible", True) is False:
        return
    yield c
    for f in _filhos(c):
        yield from _visiveis(f)


def _rotulos(tela):
    return {x.label for x in _visiveis(tela) if isinstance(x, (ft.Dropdown, ft.TextField)) and x.label}


def _textos(tela):
    return " ".join(x.value for x in _visiveis(tela) if isinstance(x, ft.Text) and x.value)


def _controle(tela, rotulo, tipo=(ft.Dropdown, ft.TextField)):
    achados = [x for x in _visiveis(tela) if isinstance(x, tipo) and x.label == rotulo]
    assert achados, f"'{rotulo}' não aparece"
    return achados[0]


def _escolher(tela, rotulo, valor):
    lista = _controle(tela, rotulo, ft.Dropdown)
    assert valor in [o.key for o in lista.options], (rotulo, valor)
    lista.value = valor
    lista.on_select(None)


def _botao_salvar(tela):
    return next(x for x in _visiveis(tela) if isinstance(x, ft.Button) and x.content == "Salvar ficha")


def _tela(projeto, usuario):
    from views.ficha import build_ficha_view

    return build_ficha_view(PaginaFalsa(), projeto, usuario, None, None)


def test_tela_unica_sem_abas_e_tipologia_em_lista(admin, projeto_padrao):
    tela = _tela(projeto_padrao, admin)
    assert not [x for x in _visiveis(tela) if isinstance(x, (ft.Tabs, ft.TabBar))]
    tipologia = _controle(tela, T, ft.Dropdown)
    assert [o.key for o in tipologia.options] == ["Residencial", "Comercial", "Industrial", "Condomínio de lotes",
                                                  "Corporativo", "Shopping Center", "Data Center", "Outro"]
    assert "Escolha a tipologia no card Programa" in _textos(tela)
    assert "Alturas e dimensões" not in _textos(tela)


def test_escolher_tipologia_abre_os_campos_e_a_cascata(admin, projeto_padrao):
    tela = _tela(projeto_padrao, admin)
    _escolher(tela, T, "Residencial")
    rotulos = _rotulos(tela)
    assert "Sistema estrutural" in rotulos and "Pé-direito – cozinhas (m)" in rotulos
    assert "Tipo de laje" not in rotulos and "Alturas e dimensões" in _textos(tela)
    _escolher(tela, "Sistema estrutural", "Concreto armado convencional")
    assert "Tipo de laje" in _rotulos(tela)
    _escolher(tela, "Sistema estrutural", "Alvenaria estrutural")
    assert "Tipo de laje" not in _rotulos(tela)
    _escolher(tela, T, "Shopping Center")
    assert "ABL – área bruta locável (m²)" in _rotulos(tela) and "Pé-direito – cozinhas (m)" not in _rotulos(tela)


def test_outro_abre_texto_e_salvar_grava_o_texto_e_limpa_o_invisivel(admin, projeto_padrao):
    pid = projeto_padrao.id
    tela = _tela(projeto_padrao, admin)
    _escolher(tela, T, "Residencial")
    _escolher(tela, "Sistema estrutural", "Concreto armado convencional")
    _escolher(tela, "Tipo de laje", "Nervurada")
    _escolher(tela, "Fachada", "Outro")
    _controle(tela, "Fachada – especifique", ft.TextField).value = "Tijolo à vista"
    _controle(tela, "Pé-direito – cozinhas (m)", ft.TextField).value = "2,60"
    _botao_salvar(tela).on_click(None)
    ficha = {(c.grupo, c.nome): c.valor for c in db.listar_caracteristicas(pid)}
    assert ficha[(P, T)] == "Residencial" and ficha[(SIS, "Tipo de laje")] == "Nervurada"
    assert ficha[(SIS, "Fachada")] == "Tijolo à vista"
    assert ficha[("Alturas e dimensões", "Pé-direito – cozinhas")] == "2,60"

    # reabrir mostra "Outro" + texto; trocar a estrutura esconde e limpa a laje
    tela = _tela(projeto_padrao, admin)
    assert _controle(tela, "Fachada", ft.Dropdown).value == "Outro"
    assert _controle(tela, "Fachada – especifique", ft.TextField).value == "Tijolo à vista"
    _escolher(tela, "Sistema estrutural", "Alvenaria estrutural")
    _botao_salvar(tela).on_click(None)
    ficha = {(c.grupo, c.nome): c.valor for c in db.listar_caracteristicas(pid)}
    assert (SIS, "Tipo de laje") not in ficha


def test_tipologia_antiga_em_texto_livre_aparece_como_outro(admin, projeto_padrao):
    db.salvar_caracteristicas(projeto_padrao.id, [(P, T, "", "Residencial multifamiliar vertical")], "Lucas",
                              usuario_id=admin.id)
    tela = _tela(projeto_padrao, admin)
    assert _controle(tela, T, ft.Dropdown).value == "Outro"
    assert _controle(tela, f"{T} – especifique", ft.TextField).value == "Residencial multifamiliar vertical"
    assert "não tem sistemas construtivos no catálogo" in _textos(tela)


def test_leitor_ve_os_sistemas_sem_poder_alterar(admin, projeto_padrao):
    from nucleo.db import nova_sessao
    from nucleo.servicos.usuarios import buscar_por_username

    db.salvar_caracteristicas(projeto_padrao.id, [(P, T, "", "Industrial"), (SIS, "Cobertura", "", "Telha zipada")],
                              "Lucas", usuario_id=admin.id)
    db.criar_usuario("cliente.x", "senha-cliente", "Cliente X", admin=False, pode_criar_projetos=False)
    db.definir_membro(projeto_padrao.id, "cliente.x", "Leitor", admin.id)
    with nova_sessao() as s:
        cliente = buscar_por_username(s, "cliente.x")
    tela = _tela(projeto_padrao, cliente)
    cobertura = _controle(tela, "Cobertura", ft.Dropdown)
    assert cobertura.value == "Telha zipada" and cobertura.disabled
    assert _controle(tela, T, ft.Dropdown).disabled
    assert not [x for x in _visiveis(tela) if isinstance(x, ft.Button) and x.content == "Salvar ficha"]

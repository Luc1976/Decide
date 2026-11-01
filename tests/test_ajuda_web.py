"""Página de ajuda em /ajuda: entrega, imagens, segurança e links internos."""
import re
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from ajuda_web import PASTA, registrar_rota_ajuda

HTML = (PASTA / "index.html").read_text(encoding="utf-8")


def _cliente():
    app = FastAPI()

    @app.get("/{qualquer:path}")  # como o site do Flet: responde a qualquer caminho
    def site(qualquer: str):
        return {"site": qualquer}

    registrar_rota_ajuda(app)
    return TestClient(app)


def test_pagina_e_imagens():
    c = _cliente()
    r = c.get("/ajuda")
    assert r.status_code == 200 and "text/html" in r.headers["content-type"] and "Ajuda" in r.text
    assert c.get("/ajuda/", follow_redirects=False).status_code == 308
    assert c.get("/ajuda/img/10-cronograma.png").headers["content-type"] == "image/png"
    assert c.get("/timeline").json() == {"site": "timeline"}  # o resto do site não muda


def test_nao_entrega_nada_fora_da_pasta():
    c = _cliente()
    for caminho in ("/ajuda/img/nao-existe.png", "/ajuda/img/index.html", "/ajuda/img/config.py"):
        assert c.get(caminho).status_code == 404, caminho
    # caminhos com ".." não chegam à ajuda: caem na rota do site, sem entregar arquivo do servidor
    for caminho in ("/ajuda/img/..%2F..%2Fconfig.py", "/ajuda/img/../../config.py"):
        r = c.get(caminho)
        assert "site" in r.json() and "DATA_DIR" not in r.text, caminho


def test_todas_as_imagens_da_pagina_existem_e_tem_texto_alternativo():
    imagens = re.findall(r'<img [^>]*>', HTML)
    assert len(imagens) >= 12
    for tag in imagens:
        src = re.search(r'src="([^"]+)"', tag).group(1)
        alt = re.search(r'alt="([^"]*)"', tag)
        assert src.startswith("/ajuda/img/") or src == "/icon.png", src
        if src.startswith("/ajuda/img/"):
            assert (PASTA / "img" / Path(src).name).is_file(), src
        assert alt and alt.group(1).strip(), f"imagem sem texto alternativo: {src}"


def test_indice_aponta_para_secoes_que_existem():
    ids = set(re.findall(r'id="([^"]+)"', HTML))
    ancoras = re.findall(r'href="#([^"]+)"', HTML)
    assert len(ancoras) >= 10
    assert not [a for a in ancoras if a not in ids]


def test_links_de_ajuda_no_menu_e_no_login(admin, projeto_padrao):
    import flet as ft

    import tema
    from test_tela_plataforma import PaginaFalsa, _todos
    from views.login import build_login_view
    from views.timeline import build_timeline_view

    pagina = PaginaFalsa()
    pagina.theme_mode = None
    tema.configurar(pagina)
    timeline = build_timeline_view(pagina, projeto_padrao, admin, None, None, None, None, None, None, None,
                                   on_open_plataforma=lambda _: None)
    ajuda = [x for x in _todos(timeline.drawer) if isinstance(x, ft.ListTile) and x.title.value == "Ajuda"]
    assert ajuda and ajuda[0].url.url == "/ajuda"
    login = build_login_view(lambda *a: None, PaginaFalsa())
    botoes = [x for x in _todos(login) if isinstance(x, ft.TextButton) and x.content == "Ajuda"]
    assert botoes and botoes[0].url.url == "/ajuda"

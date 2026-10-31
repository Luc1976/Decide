"""Página de ajuda do Decidiu em /ajuda (pasta ajuda/ do repositório: index.html + img/).

Servida pelo próprio app, na frente da rota do site (como os ícones), então acompanha cada
deploy. Só entrega arquivos da pasta ajuda/ com nomes simples: nada de caminhos."""
import re
from pathlib import Path

from fastapi import Response
from fastapi.responses import FileResponse, RedirectResponse

PASTA = Path(__file__).resolve().parent / "ajuda"
_NOME_IMAGEM = re.compile(r"^[A-Za-z0-9_-]+\.(png|webp|jpg|svg)$")
_TIPOS = {"png": "image/png", "webp": "image/webp", "jpg": "image/jpeg", "svg": "image/svg+xml"}


def registrar_rota_ajuda(app) -> None:
    async def pagina():
        arquivo = PASTA / "index.html"
        if not arquivo.is_file():
            return Response("Ajuda indisponível.", status_code=404, media_type="text/plain")
        return FileResponse(arquivo, media_type="text/html; charset=utf-8",
                            headers={"Cache-Control": "no-cache"})

    async def com_barra():
        return RedirectResponse("/ajuda", status_code=308)

    async def imagem(nome: str):
        if not _NOME_IMAGEM.match(nome) or not (PASTA / "img" / nome).is_file():
            return Response("Não encontrado.", status_code=404, media_type="text/plain")
        tipo = _TIPOS[nome.rsplit(".", 1)[1]]
        return FileResponse(PASTA / "img" / nome, media_type=tipo, headers={"Cache-Control": "public, max-age=3600"})

    rotas = (("/ajuda", pagina), ("/ajuda/", com_barra), ("/ajuda/img/{nome}", imagem))
    for caminho, funcao in rotas:
        app.add_api_route(caminho, funcao, methods=["GET"], include_in_schema=False)
    # na frente da rota que atende o site (o Flet responde a qualquer caminho)
    for _ in rotas:
        app.router.routes.insert(0, app.router.routes.pop())

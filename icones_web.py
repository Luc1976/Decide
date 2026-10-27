"""Ícone da aba do navegador e do atalho no celular: o logotipo do Decidiu, no lugar do ícone
padrão do Flet. Atende /favicon.ico, /favicon.png, /icon.png e /apple-touch-icon.png."""
import base64

from fastapi import Response

from config import ASSETS_DIR
from marca import LOGO_CABECALHO_B64

CAMINHOS = ("/favicon.ico", "/favicon.png", "/icon.png", "/apple-touch-icon.png")


def registrar_rota_icones(app) -> None:
    """Acrescenta os caminhos de ícone ao app ASGI, na frente da rota que atende o site."""
    try:
        imagem = (ASSETS_DIR / "icon.png").read_bytes()
    except OSError:  # sem o arquivo novo, usa a logo embutida
        imagem = base64.b64decode(LOGO_CABECALHO_B64)

    async def icone():
        return Response(content=imagem, media_type="image/png",
                        headers={"Cache-Control": "public, max-age=86400"})

    for caminho in CAMINHOS:
        app.add_api_route(caminho, icone, methods=["GET"], include_in_schema=False)
    app.router.routes.insert(0, app.router.routes.pop())

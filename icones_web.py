"""Ícone da aba do navegador e do atalho no celular: o ícone do Decidiu (assets/icon.png),
no lugar do ícone padrão do Flet. Atende /favicon.ico, /favicon.png, /icon.png e
/apple-touch-icon.png."""
import base64
import logging

from fastapi import Response

from config import ASSETS_DIR
from marca import LOGO_CABECALHO_B64

log = logging.getLogger("decidiu.icones")

CAMINHOS = ("/favicon.ico", "/favicon.png", "/icon.png", "/apple-touch-icon.png")
ARQUIVO_ICONE = ASSETS_DIR / "icon.png"
_RESERVA = base64.b64decode(LOGO_CABECALHO_B64)


def _imagem() -> bytes:
    """Lê o arquivo a cada pedido (é pequeno e o sistema guarda em memória); se faltar, avisa no log."""
    try:
        return ARQUIVO_ICONE.read_bytes()
    except OSError:
        log.warning("Ícone do app não encontrado em %s; usando a logo de reserva.", ARQUIVO_ICONE)
        return _RESERVA


def registrar_rota_icones(app) -> None:
    """Acrescenta os caminhos de ícone ao app ASGI, na frente da rota que atende o site."""

    async def icone():
        # no-cache: o navegador confere se o ícone mudou em vez de mostrar o antigo por dias
        return Response(content=_imagem(), media_type="image/png",
                        headers={"Cache-Control": "no-cache"})

    for caminho in CAMINHOS:
        app.add_api_route(caminho, icone, methods=["GET"], include_in_schema=False)
    app.router.routes.insert(0, app.router.routes.pop())

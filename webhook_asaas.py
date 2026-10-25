"""Recebe os avisos do Asaas em POST /api/v1/asaas/webhook.

Segurança: o Asaas envia o token configurado no cabeçalho 'asaas-access-token'. Sem a variável
ASAAS_WEBHOOK_TOKEN no servidor, o endpoint recusa tudo (503).
"""
import asyncio
import hmac
import logging
import os

from fastapi import HTTPException, Request

from nucleo.db import nova_sessao
from nucleo.servicos import assinaturas

CAMINHO = "/api/v1/asaas/webhook"
log = logging.getLogger(__name__)


def registrar_rota_webhook(app) -> None:
    """Acrescenta o endpoint ao app ASGI, na frente da rota que atende o site."""

    async def receber(request: Request):
        esperado = (os.getenv("ASAAS_WEBHOOK_TOKEN") or "").strip()
        if not esperado:
            raise HTTPException(status_code=503, detail="Webhook não configurado.")
        recebido = request.headers.get("asaas-access-token", "")
        if not hmac.compare_digest(recebido.encode("utf-8"), esperado.encode("utf-8")):
            raise HTTPException(status_code=401, detail="Token inválido.")
        evento = await request.json()

        def processar():
            with nova_sessao() as s:
                return assinaturas.processar_evento(s, evento)

        processado = await asyncio.to_thread(processar)
        log.info("Asaas: evento %s processado=%s", evento.get("event"), processado)
        return {"recebido": True, "processado": processado}

    app.add_api_route(CAMINHO, receber, methods=["POST"], include_in_schema=False)
    app.router.routes.insert(0, app.router.routes.pop())

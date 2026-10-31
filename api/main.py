"""Aplicação FastAPI do Decidiu.

    uvicorn api.main:app --host 0.0.0.0 --port 8000

Roda separada do app Flet (main.py) e usa o mesmo banco e as mesmas regras (nucleo/).
Por não guardar estado em memória entre requisições, pode rodar em várias instâncias.
"""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from api import erros
from api.configuracao import PREFIXO, VERSAO, configuracao
from api.deps import Sessao
from api.rotas import (admin, arquivos, atas, auth, cronograma, decisoes, documentos, ficha, organizacoes,
                       pendencias, projetos)
from config import garantir_pastas
from models import CAMPOS_LONGOS, CATEGORIAS, FICHA_GRUPOS, IMPACTOS, PAPEIS
from nucleo.db import aguardar_banco
from nucleo.migracoes import atualizar_banco
import catalogo_tipologias as catalogo
from nucleo.tabelas import SITUACOES_PENDENCIA


@asynccontextmanager
async def _ciclo_de_vida(_: FastAPI):
    garantir_pastas()
    aguardar_banco()  # se o banco não responder, a mensagem no log explica a causa provável
    if os.getenv("DECIDIU_MIGRAR_NA_PARTIDA", "1") == "1":
        # "alembic upgrade head": só aplica o que falta. No PostgreSQL há uma trava, então o
        # app Flet e a API podem iniciar juntos sem conflito.
        atualizar_banco()
    yield


def criar_app() -> FastAPI:
    app = FastAPI(
        title="Decidiu API",
        version=VERSAO,
        description="Memória de decisões de projeto: linha do tempo, atas, pendências e ficha do empreendimento.",
        docs_url="/api/docs",
        redoc_url=None,
        openapi_url="/api/openapi.json",
        lifespan=_ciclo_de_vida,
    )
    cfg = configuracao()
    if cfg.cors_origens:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=cfg.cors_origens,
            allow_methods=["GET", "POST", "PUT", "DELETE"],
            allow_headers=["Authorization", "Content-Type"],
        )

    @app.middleware("http")
    async def _cabecalhos_de_seguranca(request, call_next):
        resposta = await call_next(request)
        resposta.headers.setdefault("X-Content-Type-Options", "nosniff")
        resposta.headers.setdefault("Referrer-Policy", "no-referrer")
        resposta.headers.setdefault("X-Frame-Options", "DENY")
        return resposta

    erros.registrar(app)
    for modulo in (auth, organizacoes, projetos, decisoes, atas, pendencias, ficha, cronograma, documentos, admin,
                   arquivos):
        app.include_router(modulo.rotas, prefix=PREFIXO)
    app.include_router(organizacoes.plataforma, prefix=PREFIXO)

    @app.get("/api/saude", tags=["Sistema"], summary="Verificação de funcionamento (para o Railway)")
    def saude(s: Sessao):
        s.exec(text("SELECT 1"))
        return {"status": "ok", "versao": VERSAO}

    @app.get(f"{PREFIXO}/opcoes", tags=["Sistema"], summary="Listas fixas para os formulários do frontend")
    def opcoes():
        return {
            "categorias": CATEGORIAS,
            "impactos": IMPACTOS,
            "papeis": PAPEIS,
            "situacoes_pendencia": SITUACOES_PENDENCIA,
            "tipologias": list(catalogo.TIPOLOGIAS),
            "opcao_outro": catalogo.OUTRO,
            "ficha_grupos": {g: [{"nome": n, "unidade": u or None, "longo": n in CAMPOS_LONGOS} for n, u in campos]
                             for g, campos in FICHA_GRUPOS.items()},
            "ordem_dos_grupos": catalogo.ordem_dos_grupos(),
            # Campos de cada tipologia. 'opcoes' vazio = campo de texto (número); toda lista
            # aceita "Outro" com texto livre. 'depende_de' + 'valores_que_mostram' = cascata.
            "campos_por_tipologia": {
                t: [{"grupo": c.grupo, "nome": c.nome, "unidade": c.unidade or None,
                     "opcoes": list(c.opcoes), "depende_de": c.depende_de,
                     "valores_que_mostram": list(c.valores_que_mostram)}
                    for c in catalogo.campos_da_tipologia(t)]
                for t in catalogo.TIPOLOGIAS
            },
        }

    return app


app = criar_app()

"""Aplicação FastAPI do Decidiu.

    uvicorn api.main:app --host 0.0.0.0 --port 8000

Roda separada do app Flet (main.py) e usa o mesmo banco e as mesmas regras (nucleo/).
Por não guardar estado em memória entre requisições, pode rodar em várias instâncias.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlmodel import SQLModel

from api import erros
from api.configuracao import PREFIXO, VERSAO, configuracao
from api.deps import Sessao
from api.rotas import admin, arquivos, atas, auth, decisoes, ficha, pendencias, projetos
from config import garantir_pastas
from models import CAMPOS_LONGOS, CATEGORIAS, FICHA_GRUPOS, IMPACTOS, PAPEIS
from nucleo.db import engine
from nucleo.tabelas import SITUACOES_PENDENCIA, TipologiaProjeto


@asynccontextmanager
async def _ciclo_de_vida(_: FastAPI):
    garantir_pastas()
    # Cria só as tabelas que faltam (ex.: auditoria). Mudanças em tabelas existentes
    # devem ir para migrações Alembic, não para cá.
    SQLModel.metadata.create_all(engine)
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
    for modulo in (auth, projetos, decisoes, atas, pendencias, ficha, admin, arquivos):
        app.include_router(modulo.rotas, prefix=PREFIXO)

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
            "tipologias": [t.value for t in TipologiaProjeto],
            "ficha_grupos": {g: [{"nome": n, "unidade": u or None, "longo": n in CAMPOS_LONGOS} for n, u in campos]
                             for g, campos in FICHA_GRUPOS.items()},
        }

    return app


app = criar_app()

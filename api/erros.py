"""Tradução dos erros de domínio (nucleo/erros.py) para respostas HTTP.

As rotas não fazem try/except: o serviço levanta o erro e este módulo responde com o
código certo e a mensagem em português no campo 'detail'."""
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from nucleo.erros import Conflito, NaoEncontrado
from nucleo.servicos.ia import ErroIA


def _resposta(codigo: int, erro: Exception) -> JSONResponse:
    return JSONResponse(status_code=codigo, content={"detail": str(erro)})


def registrar(app: FastAPI) -> None:
    @app.exception_handler(NaoEncontrado)
    async def _404(_: Request, erro: NaoEncontrado):
        return _resposta(404, erro)

    @app.exception_handler(Conflito)
    async def _409(_: Request, erro: Conflito):
        return _resposta(409, erro)

    @app.exception_handler(PermissionError)  # inclui SemPermissao
    async def _403(_: Request, erro: PermissionError):
        return _resposta(403, erro)

    @app.exception_handler(ErroIA)
    async def _ia(_: Request, erro: ErroIA):
        return _resposta(422, erro)

    @app.exception_handler(ValueError)  # regra de negócio (ErroDominio e ValueError dos serviços)
    async def _422(_: Request, erro: ValueError):
        return _resposta(422, erro)

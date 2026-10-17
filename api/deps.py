"""Dependências injetadas nas rotas: sessão do banco e usuário autenticado."""
from typing import Annotated, Iterator

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlmodel import Session

from api.autenticacao import ler_token
from nucleo.ator import Ator
from nucleo.db import nova_sessao
from nucleo.permissoes import organizacao_ativa
from nucleo.servicos.usuarios import MENSAGEM_ORG_DESATIVADA
from nucleo.tabelas import Usuario

_bearer = HTTPBearer(auto_error=False, description="Token obtido em POST /api/v1/auth/login")


def obter_sessao() -> Iterator[Session]:
    """Uma sessão por requisição. Os serviços fazem o commit; aqui só se fecha."""
    with nova_sessao() as s:
        yield s


Sessao = Annotated[Session, Depends(obter_sessao)]


def _nao_autenticado(mensagem: str = "Faça login para continuar.") -> HTTPException:
    return HTTPException(status.HTTP_401_UNAUTHORIZED, mensagem, headers={"WWW-Authenticate": "Bearer"})


def ator_atual(s: Sessao, credenciais: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)]) -> Ator:
    if credenciais is None:
        raise _nao_autenticado()
    usuario_id = ler_token(credenciais.credentials)
    if usuario_id is None:
        raise _nao_autenticado("Sessão expirada ou inválida. Entre novamente.")
    usuario = s.get(Usuario, usuario_id)
    if usuario is None:
        raise _nao_autenticado("Usuário não encontrado.")
    if not organizacao_ativa(s, usuario.organizacao_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, MENSAGEM_ORG_DESATIVADA)
    return Ator.de_usuario(usuario)


AtorAtual = Annotated[Ator, Depends(ator_atual)]

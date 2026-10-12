"""Tokens de acesso (JWT HS256).

Fluxo: POST /api/v1/auth/login com usuário e senha -> token. O frontend manda o token em
'Authorization: Bearer <token>' em todas as chamadas. A cada requisição o usuário é relido
do banco: se foi removido ou perdeu acesso, vale na hora.

Próximo passo (ver docs): trocar por um provedor gerenciado (Clerk, Auth0, Keycloak) para
ter MFA, recuperação de senha por e-mail e login social. Só este arquivo e deps.py mudam.
"""
import datetime
from typing import Optional

import jwt

from api.configuracao import configuracao
from seguranca import LimitadorTentativas

ALGORITMO = "HS256"
EMISSOR = "decidiu"

# 5 senhas erradas bloqueiam o usuário por 15 min. Em memória: vale por processo.
# Com várias instâncias, mover para o Redis (mesma interface).
LIMITADOR_LOGIN = LimitadorTentativas(maximo=5, janela_s=900, bloqueio_s=900)


def emitir_token(usuario_id: int, agora: Optional[datetime.datetime] = None) -> tuple[str, datetime.datetime]:
    cfg = configuracao()
    agora = agora or datetime.datetime.now(datetime.timezone.utc)
    expira = agora + datetime.timedelta(minutes=cfg.token_minutos)
    token = jwt.encode(
        {"sub": str(usuario_id), "iat": agora, "exp": expira, "iss": EMISSOR, "typ": "acesso"},
        cfg.jwt_segredo,
        algorithm=ALGORITMO,
    )
    return token, expira


def ler_token(token: str) -> Optional[int]:
    """Id do usuário, ou None se o token for inválido/expirado."""
    try:
        dados = jwt.decode(token, configuracao().jwt_segredo, algorithms=[ALGORITMO], issuer=EMISSOR,
                           options={"require": ["exp", "sub", "iss"]})
    except jwt.PyJWTError:
        return None
    if dados.get("typ") != "acesso":
        return None
    try:
        return int(dados["sub"])
    except (TypeError, ValueError):
        return None

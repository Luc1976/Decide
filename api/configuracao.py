"""Configuração da API por variáveis de ambiente.

DECIDIU_JWT_SEGREDO     segredo dos tokens de acesso (>= 32 caracteres). Sem ela, deriva
                        do segredo do servidor (MEMORIA_SEGREDO / segredo.key).
DECIDIU_TOKEN_MINUTOS   validade do token de acesso (padrão 60).
DECIDIU_CORS_ORIGENS    origens do frontend, separadas por vírgula
                        (ex.: https://app.decidiu.com.br,http://localhost:5173).
DECIDIU_DATABASE_URL    PostgreSQL (ver nucleo/db.py). Sem ela, SQLite em MEMORIA_DATA_DIR.
"""
import hashlib
import hmac
import os
from dataclasses import dataclass
from functools import lru_cache
from typing import List

VERSAO = "1.0.0"
PREFIXO = "/api/v1"


@dataclass(frozen=True)
class Configuracao:
    jwt_segredo: str
    token_minutos: int
    cors_origens: List[str]


def _segredo_jwt() -> str:
    do_ambiente = (os.getenv("DECIDIU_JWT_SEGREDO") or "").strip()
    if len(do_ambiente) >= 32:
        return do_ambiente
    from seguranca import segredo_do_servidor

    # Derivado (e diferente) do segredo dos links de anexos.
    return hmac.new(segredo_do_servidor(), b"api-jwt", hashlib.sha256).hexdigest()


@lru_cache(maxsize=1)
def configuracao() -> Configuracao:
    origens = [o.strip() for o in (os.getenv("DECIDIU_CORS_ORIGENS") or "").split(",") if o.strip()]
    return Configuracao(
        jwt_segredo=_segredo_jwt(),
        token_minutos=int(os.getenv("DECIDIU_TOKEN_MINUTOS") or "60"),
        cors_origens=origens,
    )

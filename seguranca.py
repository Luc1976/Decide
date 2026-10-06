"""Peças de segurança do modo site, sem dependências pesadas (fáceis de testar)."""
import base64
import functools
import hashlib
import hmac
import json
import os
import secrets
import time
from pathlib import Path
from typing import Callable, Optional

from config import DATA_DIR


# ---------- Links assinados e temporários (anexos) ----------

def carregar_segredo(pasta: Path) -> bytes:
    """MEMORIA_SEGREDO, ou um segredo aleatório guardado (uma vez) em pasta/segredo.key."""
    do_ambiente = os.getenv("MEMORIA_SEGREDO") or ""
    if len(do_ambiente) >= 16:
        return do_ambiente.encode()
    arquivo = Path(pasta) / "segredo.key"
    if arquivo.is_file():
        return arquivo.read_bytes().strip()
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    segredo = secrets.token_hex(32).encode()
    try:
        fd = os.open(arquivo, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as f:
            f.write(segredo)
    except FileExistsError:  # outro processo criou ao mesmo tempo
        return arquivo.read_bytes().strip()
    return segredo


@functools.lru_cache(maxsize=1)
def segredo_do_servidor() -> bytes:
    return carregar_segredo(DATA_DIR)


def assinar_token(segredo: bytes, dados: dict, validade_s: int = 300, agora: Optional[float] = None) -> str:
    corpo = dict(dados, exp=int((agora if agora is not None else time.time()) + validade_s))
    bruto = base64.urlsafe_b64encode(
        json.dumps(corpo, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).decode().rstrip("=")
    assinatura = hmac.new(segredo, bruto.encode(), hashlib.sha256).hexdigest()
    return f"{bruto}.{assinatura}"


def verificar_token(segredo: bytes, token: str, agora: Optional[float] = None) -> Optional[dict]:
    """Devolve os dados se a assinatura confere e não expirou; senão None."""
    try:
        bruto, assinatura = (token or "").rsplit(".", 1)
        esperado = hmac.new(segredo, bruto.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(assinatura, esperado):
            return None
        dados = json.loads(base64.urlsafe_b64decode(bruto + "=" * (-len(bruto) % 4)))
        if dados.get("exp", 0) < (agora if agora is not None else time.time()):
            return None
        return dados
    except (ValueError, TypeError, KeyError):
        return None


# ---------- Limite de tentativas de login ----------

class LimitadorTentativas:
    """Bloqueia um usuário por 'bloqueio_s' depois de 'maximo' falhas em 'janela_s'.
    Fica em memória (vale para um único processo, como o app roda)."""

    def __init__(self, maximo: int = 5, janela_s: int = 900, bloqueio_s: int = 900,
                 relogio: Callable[[], float] = time.time):
        self.maximo, self.janela_s, self.bloqueio_s, self.relogio = maximo, janela_s, bloqueio_s, relogio
        self._falhas: dict = {}
        self._bloqueado_ate: dict = {}

    def bloqueado(self, chave: str) -> int:
        """Segundos restantes de bloqueio (0 se livre)."""
        ate = self._bloqueado_ate.get(chave, 0)
        restante = int(ate - self.relogio())
        if restante > 0:
            return restante
        self._bloqueado_ate.pop(chave, None)
        return 0

    def falhou(self, chave: str) -> None:
        agora = self.relogio()
        recentes = [t for t in self._falhas.get(chave, []) if agora - t < self.janela_s]
        recentes.append(agora)
        self._falhas[chave] = recentes
        if len(recentes) >= self.maximo:
            self._bloqueado_ate[chave] = agora + self.bloqueio_s
            self._falhas.pop(chave, None)

    def sucesso(self, chave: str) -> None:
        self._falhas.pop(chave, None)
        self._bloqueado_ate.pop(chave, None)

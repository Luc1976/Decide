"""Arquivos (anexos, logos, PDFs) atrás de uma interface única.

Hoje: disco local (o volume /dados do Railway). Problema para escalar: com 2+ instâncias
da API, cada uma tem seu próprio disco. A solução é um armazenamento de objetos
(Cloudflare R2, AWS S3) com a MESMA interface: basta escrever ArmazenamentoS3 e trocar
em armazenamento_padrao(). Os serviços não mudam.

As "chaves" são caminhos relativos a DATA_DIR, compatíveis com os anexos já gravados pelo
app Flet ("uploads/<pasta>/<arquivo>").
"""
import re
import unicodedata
import uuid
from pathlib import Path
from typing import Iterable, Optional, Protocol

import config

PREFIXO_UPLOADS = "uploads"
TAMANHO_MAXIMO_ANEXO = 25 * 1024 * 1024  # 25 MB


def nome_seguro(nome: str, limite: int = 120) -> str:
    """Nome de arquivo sem caminho, sem vírgula (o campo 'anexos' usa vírgula) e sem
    caracteres que confundam o sistema de arquivos."""
    nome = Path((nome or "").replace("\\", "/")).name
    nome = unicodedata.normalize("NFC", nome).replace(",", "_")
    nome = re.sub(r"[^\w.\- ()À-ÿ]", "_", nome).strip(" .") or "arquivo"
    if len(nome) > limite:
        base, ponto, ext = nome.rpartition(".")
        nome = (base[: limite - len(ext) - 1] + "." + ext) if ponto else nome[:limite]
    return nome


def chave_anexo(projeto_id: int, nome: str) -> str:
    """Chave nova de anexo, sempre dentro da pasta do projeto."""
    return f"{PREFIXO_UPLOADS}/p{int(projeto_id)}/{uuid.uuid4().hex}/{nome_seguro(nome)}"


def chave_do_projeto(projeto_id: int, chave: str) -> bool:
    """A chave foi gerada para este projeto? (impede anexar arquivo de outro projeto)"""
    return (chave or "").startswith(f"{PREFIXO_UPLOADS}/p{int(projeto_id)}/") and ".." not in chave


class Armazenamento(Protocol):
    def salvar(self, chave: str, dados: bytes) -> str: ...
    def ler(self, chave: str) -> bytes: ...
    def existe(self, chave: str) -> bool: ...
    def caminho_local(self, chave: str) -> Optional[Path]: ...
    def apagar(self, chaves: Iterable[str]) -> int: ...


class ArmazenamentoLocal:
    """Arquivos em DATA_DIR. Só aceita chaves dentro das pastas permitidas."""

    PASTAS = ("uploads", "relatorios", "logos")

    def __init__(self, base: Optional[Path] = None):
        self.base = Path(base or config.DATA_DIR).resolve()

    def _resolver(self, chave: str) -> Path:
        alvo = (self.base / (chave or "")).resolve()
        raizes = [(self.base / p).resolve() for p in self.PASTAS]
        if not any(r in alvo.parents for r in raizes):
            raise ValueError("Caminho de arquivo inválido.")
        return alvo

    def salvar(self, chave: str, dados: bytes) -> str:
        alvo = self._resolver(chave)
        alvo.parent.mkdir(parents=True, exist_ok=True)
        alvo.write_bytes(dados)
        return chave

    def ler(self, chave: str) -> bytes:
        return self._resolver(chave).read_bytes()

    def existe(self, chave: str) -> bool:
        try:
            return self._resolver(chave).is_file()
        except ValueError:
            return False

    def caminho_local(self, chave: str) -> Optional[Path]:
        try:
            alvo = self._resolver(chave)
        except ValueError:
            return None
        return alvo if alvo.is_file() else None

    def apagar(self, chaves: Iterable[str]) -> int:
        # Reaproveita a rotina do app (aceita também os caminhos antigos do desktop).
        return config.apagar_anexos(list(chaves or []))


def armazenamento_padrao() -> Armazenamento:
    return ArmazenamentoLocal()

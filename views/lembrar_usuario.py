"""Guarda só o nome de usuário neste aparelho, para a próxima entrada. A senha nunca é guardada.

Usa o armazenamento do navegador que o Flet expõe (shared_preferences; client_storage em versões
antigas). Se nenhum existir, a função simplesmente não faz nada: o login continua funcionando."""
import inspect

CHAVE = "decidiu.usuario_lembrado"


def _armazenamento(page):
    for nome in ("shared_preferences", "client_storage"):
        armazenamento = getattr(page, nome, None)
        if armazenamento is not None:
            return armazenamento
    return None


async def ler(page) -> str:
    try:
        armazenamento = _armazenamento(page)
        if armazenamento is None:
            return ""
        valor = armazenamento.get(CHAVE)
        if inspect.isawaitable(valor):
            valor = await valor
        return valor or ""
    except Exception:  # armazenamento indisponível: entrada normal, sem preencher
        return ""


async def gravar(page, usuario: str) -> None:
    """usuario vazio apaga o nome guardado."""
    try:
        armazenamento = _armazenamento(page)
        if armazenamento is None:
            return
        escrita = armazenamento.set(CHAVE, usuario or "")
        if inspect.isawaitable(escrita):
            await escrita
    except Exception:
        pass

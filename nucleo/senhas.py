"""Senhas com PBKDF2-SHA256 e sal; nunca guardamos a senha em texto puro.

No Pyodide (Python no navegador) o hashlib NÃO tem pbkdf2_hmac (falta o OpenSSL), então há
uma implementação em Python puro. O resultado é idêntico, por isso hashes gerados num
ambiente são verificáveis no outro."""
import hashlib
import hmac
import secrets

_ITERACOES_NATIVO = 200_000
_ITERACOES_PURO = 50_000  # Python puro em WebAssembly é lento; menos iterações
TAMANHO_MINIMO = 6


def _pbkdf2_puro(senha: bytes, sal: bytes, iteracoes: int) -> bytes:
    """PBKDF2-HMAC-SHA256, 1 bloco (32 bytes), só com hashlib.sha256."""
    if len(senha) > 64:
        senha = hashlib.sha256(senha).digest()
    senha = senha.ljust(64, b"\0")
    interno = hashlib.sha256(bytes(b ^ 0x36 for b in senha))
    externo = hashlib.sha256(bytes(b ^ 0x5C for b in senha))

    def prf(dados: bytes) -> bytes:
        i = interno.copy()
        i.update(dados)
        o = externo.copy()
        o.update(i.digest())
        return o.digest()

    u = prf(sal + b"\x00\x00\x00\x01")
    t = int.from_bytes(u, "big")
    for _ in range(iteracoes - 1):
        u = prf(u)
        t ^= int.from_bytes(u, "big")
    return t.to_bytes(32, "big")


def _pbkdf2(senha: str, sal: bytes, iteracoes: int) -> bytes:
    nativo = getattr(hashlib, "pbkdf2_hmac", None)
    if nativo is not None:
        return nativo("sha256", senha.encode(), sal, iteracoes)
    return _pbkdf2_puro(senha.encode(), sal, iteracoes)


def hash_senha(senha: str) -> str:
    iteracoes = _ITERACOES_NATIVO if hasattr(hashlib, "pbkdf2_hmac") else _ITERACOES_PURO
    sal = secrets.token_hex(16)
    h = _pbkdf2(senha, bytes.fromhex(sal), iteracoes)
    return f"pbkdf2${iteracoes}${sal}${h.hex()}"


def senha_confere(senha: str, armazenada: str) -> bool:
    if not armazenada.startswith("pbkdf2$"):  # legado: texto puro
        return hmac.compare_digest(senha, armazenada)
    _, iteracoes, sal, esperado = armazenada.split("$")
    h = _pbkdf2(senha, bytes.fromhex(sal), int(iteracoes))
    return hmac.compare_digest(h.hex(), esperado)


def eh_hash(armazenada: str) -> bool:
    return armazenada.startswith("pbkdf2$")


def validar_nova_senha(senha: str, mensagem: str = "A senha deve ter pelo menos 6 caracteres.") -> None:
    if len(senha or "") < TAMANHO_MINIMO:
        raise ValueError(mensagem)

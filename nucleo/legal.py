"""Links legais do app. O Termos de Serviço fica publicado fora do código: a URL vem de
MEMORIA_URL_TERMOS (no Railway). Sem ela, o app mostra 'em breve' em vez de um link quebrado."""
import os


def url_termos() -> str:
    return (os.getenv("MEMORIA_URL_TERMOS") or "").strip()

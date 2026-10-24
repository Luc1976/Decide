"""E-mails transacionais pelo Resend (confirmação de cadastro e recuperação de senha).

Usa a variável RESEND_API_KEY (no Railway). Sem a chave, nada é enviado e o erro vai para o log.
O remetente é o domínio verificado no Resend (noreply.decidiu.com), ou MEMORIA_EMAIL_REMETENTE.
"""
import json
import logging
import os
import urllib.error
import urllib.request

REMETENTE_PADRAO = "Decidiu <noreply@noreply.decidiu.com>"
URL_API = "https://api.resend.com/emails"

log = logging.getLogger(__name__)


def enviar(destino: str, assunto: str, html: str) -> bool:
    """Envia um e-mail. True se o Resend aceitou; False se faltou a chave ou falhou o envio."""
    chave = (os.getenv("RESEND_API_KEY") or "").strip()
    if not chave:
        log.error("RESEND_API_KEY não configurada: e-mail para %s não enviado.", destino)
        return False
    corpo = json.dumps({
        "from": os.getenv("MEMORIA_EMAIL_REMETENTE") or REMETENTE_PADRAO,
        "to": [destino],
        "subject": assunto,
        "html": html,
    }).encode("utf-8")
    pedido = urllib.request.Request(URL_API, data=corpo, method="POST", headers={
        "Authorization": f"Bearer {chave}",
        "Content-Type": "application/json",
        "User-Agent": "decidiu-app/1.0",  # o Resend recusa o User-Agent padrão do urllib
    })
    try:
        with urllib.request.urlopen(pedido, timeout=15) as resposta:
            log.info("E-mail '%s' aceito pelo Resend para %s", assunto, destino)
            return 200 <= resposta.status < 300
    except urllib.error.HTTPError as erro:  # o Resend explica o motivo no corpo da resposta
        detalhe = erro.read().decode("utf-8", "replace")[:500]
        log.error("Resend recusou o e-mail para %s (HTTP %s): %s", destino, erro.code, detalhe)
        return False
    except (urllib.error.URLError, OSError) as erro:
        log.error("Falha de conexão ao enviar e-mail para %s: %s", destino, erro)
        return False

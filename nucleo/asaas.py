"""Cliente da API do Asaas: cliente, assinatura e link de pagamento.

Variáveis (no Railway):
- ASAAS_API_KEY: chave de API do ambiente escolhido.
- ASAAS_SANDBOX: "1" (padrão) usa o ambiente de testes; "0" usa o de produção.
Os dados do cartão nunca passam por aqui: o cliente paga na página do próprio Asaas.
"""
import datetime
import json
import logging
import os
import urllib.error
import urllib.request
from typing import Optional

log = logging.getLogger(__name__)


class ErroAsaas(ValueError):
    """Falha ao falar com o Asaas. Vira mensagem na tela (ValueError é tratado pelas telas)."""


def _base() -> str:
    sandbox = (os.getenv("ASAAS_SANDBOX") or "1").strip() != "0"
    return "https://api-sandbox.asaas.com/v3" if sandbox else "https://api.asaas.com/v3"


def _motivo_asaas(detalhe: str) -> str:
    """Mensagem de validação que o Asaas devolve no corpo do erro (ex.: CPF inválido)."""
    try:
        erros = json.loads(detalhe).get("errors") or []
        return "; ".join(e.get("description", "") for e in erros if e.get("description"))
    except (ValueError, AttributeError):
        return ""


def _chamar(metodo: str, caminho: str, corpo: Optional[dict] = None) -> dict:
    chave = (os.getenv("ASAAS_API_KEY") or "").strip()
    if not chave:
        raise ErroAsaas("Pagamentos ainda não estão configurados. Fale com o suporte.")
    dados = json.dumps(corpo).encode("utf-8") if corpo is not None else None
    pedido = urllib.request.Request(_base() + caminho, data=dados, method=metodo, headers={
        "access_token": chave,
        "Content-Type": "application/json",
        "User-Agent": "decidiu-app/1.0",
    })
    try:
        with urllib.request.urlopen(pedido, timeout=20) as resposta:
            return json.loads(resposta.read() or b"{}")
    except urllib.error.HTTPError as erro:
        detalhe = erro.read().decode("utf-8", "replace")[:500]
        log.error("Asaas recusou %s %s (HTTP %s): %s", metodo, caminho, erro.code, detalhe)
        motivo = _motivo_asaas(detalhe)
        mensagem = "O Asaas recusou o pedido" + (f": {motivo}" if motivo else ". Confira os dados e tente de novo.")
        raise ErroAsaas(mensagem) from erro
    except (urllib.error.URLError, OSError) as erro:
        log.error("Falha de conexão com o Asaas em %s: %s", caminho, erro)
        raise ErroAsaas("Não foi possível falar com o Asaas agora. Tente em alguns minutos.") from erro


def criar_cliente(nome: str, cpf_cnpj: str, email: str, referencia: str) -> str:
    resposta = _chamar("POST", "/customers", {
        "name": nome,
        "cpfCnpj": cpf_cnpj,
        "email": email,
        "externalReference": referencia,
    })
    return resposta["id"]


def criar_assinatura(cliente_id: str, valor: float, ciclo: str, proximo_vencimento: datetime.date,
                     descricao: str, referencia: str) -> str:
    """ciclo: 'MONTHLY' ou 'YEARLY'. Cobrança por cartão de crédito."""
    resposta = _chamar("POST", "/subscriptions", {
        "customer": cliente_id,
        "billingType": "CREDIT_CARD",
        "value": valor,
        "nextDueDate": proximo_vencimento.isoformat(),
        "cycle": ciclo,
        "description": descricao,
        "externalReference": referencia,
    })
    return resposta["id"]


def criar_link_anual(nome: str, descricao: str, valor: float, parcelas_maximas: int,
                      referencia: str) -> tuple:
    """Link de pagamento parcelável (até parcelas_maximas, escolhidas pelo pagador), cobrado no ato.
    Devolve (id do link, url). Os pagamentos feitos por ele trazem 'paymentLink' com esse id."""
    resposta = _chamar("POST", "/paymentLinks", {
        "name": nome,
        "description": descricao,
        "value": valor,
        "billingType": "CREDIT_CARD",
        "chargeType": "INSTALLMENT",
        "maxInstallmentCount": parcelas_maximas,
        "externalReference": referencia,
        "notificationEnabled": True,
    })
    if not resposta.get("id") or not resposta.get("url"):
        raise ErroAsaas("O Asaas não devolveu o link de pagamento. Tente de novo em alguns minutos.")
    return resposta["id"], resposta["url"]


def link_primeira_cobranca(assinatura_id: str) -> Optional[str]:
    """Link da página de pagamento da cobrança mais recente da assinatura."""
    cobrancas = _chamar("GET", f"/subscriptions/{assinatura_id}/payments").get("data") or []
    for cobranca in cobrancas:
        if cobranca.get("invoiceUrl"):
            return cobranca["invoiceUrl"]
    return None

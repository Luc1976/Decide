"""Assinaturas: gera o pagamento do plano escolhido no Asaas e aplica os avisos de pagamento.

Regras:
- Quem assina é o administrador da organização, com a própria senha (mesmo se a conta estiver
  bloqueada pelo vencimento do teste).
- Enquanto o pagamento não é confirmado, a organização continua no status atual (o teste
  segue valendo até o fim, ou fica bloqueada se já venceu).
- O aviso de pagamento confirmado (webhook) libera a organização; atraso e cancelamento a bloqueiam.
"""
import calendar
import datetime
import re
from typing import Optional

from sqlmodel import Session, select

from nucleo import asaas, planos
from nucleo.senhas import senha_confere
from nucleo.servicos.usuarios import buscar_por_username
from nucleo.tabelas import Organizacao, Usuario

CICLOS_ASAAS = {planos.CICLO_MENSAL: "MONTHLY", planos.CICLO_ANUAL: "YEARLY"}
EVENTOS_PAGOS = ("PAYMENT_CONFIRMED", "PAYMENT_RECEIVED")
EVENTOS_ATRASO = ("PAYMENT_OVERDUE",)
EVENTOS_CANCELAMENTO = ("SUBSCRIPTION_INACTIVATED", "SUBSCRIPTION_DELETED")


def _cpf_cnpj(valor: str) -> str:
    digitos = re.sub(r"\D", "", valor or "")
    if len(digitos) not in (11, 14):
        raise ValueError("Informe um CPF ou CNPJ válido.")
    return digitos


def _somar_meses(data: datetime.date, meses: int) -> datetime.date:
    mes = data.month - 1 + meses
    ano, mes = data.year + mes // 12, mes % 12 + 1
    return data.replace(year=ano, month=mes, day=min(data.day, calendar.monthrange(ano, mes)[1]))


def assinar(s: Session, usuario: Usuario, plano: str, ciclo: str, cpf_cnpj: str) -> str:
    """Cria (ou reaproveita) a assinatura e devolve o link de pagamento."""
    if not usuario.admin:
        raise ValueError("Só o administrador da organização pode assinar.")
    org = s.get(Organizacao, usuario.organizacao_id) if usuario.organizacao_id else None
    if org is None:
        raise ValueError("Organização não encontrada.")
    if org.plano == planos.PLANO_INTERNO:
        raise ValueError("Esta organização não precisa de assinatura.")
    if org.assinatura_status == planos.STATUS_ATIVA and org.asaas_assinatura_id:
        raise ValueError("A assinatura da sua organização já está ativa.")
    valor = planos.valor_cobranca(plano, ciclo)  # valida plano e ciclo
    if plano == planos.PLANO_FUNDADOR and org.plano != planos.PLANO_FUNDADOR \
            and planos.vagas_fundador_restantes(s) <= 0:
        raise ValueError("As vagas do plano Fundador já foram preenchidas. Escolha o plano Equipe.")

    if org.asaas_assinatura_id:  # já existe cobrança aguardando pagamento
        if org.plano != plano or org.ciclo != ciclo:
            raise ValueError("Já existe uma cobrança aguardando pagamento para outro plano. "
                             "Pague o link já gerado ou fale com o suporte.")
        link = asaas.link_primeira_cobranca(org.asaas_assinatura_id)
        if link:
            return link

    cpf = _cpf_cnpj(cpf_cnpj)
    hoje = planos.agora_utc().date()
    if org.asaas_cliente_id is None:
        org.asaas_cliente_id = asaas.criar_cliente(org.nome, cpf, usuario.email or usuario.username,
                                                   f"org:{org.id}")
    # Quem assina durante o teste começa a pagar só quando o teste termina.
    inicio = hoje
    fim_teste = planos._com_fuso(org.teste_fim)
    if org.assinatura_status == planos.STATUS_TESTE and fim_teste is not None:
        inicio = max(hoje, fim_teste.date())
    assinatura_id = asaas.criar_assinatura(
        cliente_id=org.asaas_cliente_id,
        valor=valor,
        ciclo=CICLOS_ASAAS[ciclo],
        proximo_vencimento=inicio,
        descricao=f"Decidiu - plano {planos.PRECOS[plano]['nome']} ({ciclo})",
        referencia=f"org:{org.id}",
    )
    org.plano = plano
    org.ciclo = ciclo
    org.asaas_assinatura_id = assinatura_id
    if plano == planos.PLANO_FUNDADOR:
        fim = _somar_meses(hoje, planos.MESES_FIDELIDADE_FUNDADOR)
        org.fidelidade_fim = datetime.datetime(fim.year, fim.month, fim.day, tzinfo=datetime.timezone.utc)
    s.add(org)
    s.commit()

    link = asaas.link_primeira_cobranca(assinatura_id)
    if not link:
        raise ValueError("A assinatura foi criada, mas o link de pagamento ainda não está disponível. "
                         "Tente de novo em alguns minutos.")
    return link


def assinar_com_senha(s: Session, username: str, senha: str, plano: str, ciclo: str, cpf_cnpj: str) -> str:
    """Confere usuário e senha antes de gerar o pagamento (a tela de entrada usa isto)."""
    usuario = buscar_por_username(s, username)
    if usuario is None or not senha_confere(senha or "", usuario.senha):
        raise ValueError("Usuário ou senha incorretos.")
    return assinar(s, usuario, plano, ciclo, cpf_cnpj)


def _organizacao_da_assinatura(s: Session, assinatura_id: Optional[str]) -> Optional[Organizacao]:
    if not assinatura_id:
        return None
    return s.exec(select(Organizacao).where(Organizacao.asaas_assinatura_id == assinatura_id)).first()


def processar_evento(s: Session, evento: dict) -> bool:
    """Aplica um aviso do Asaas. Devolve True se alguma organização foi atualizada."""
    tipo = evento.get("event")
    if tipo in EVENTOS_PAGOS + EVENTOS_ATRASO:
        assinatura_id = (evento.get("payment") or {}).get("subscription")
    elif tipo in EVENTOS_CANCELAMENTO:
        assinatura_id = (evento.get("subscription") or {}).get("id")
    else:
        return False
    org = _organizacao_da_assinatura(s, assinatura_id)
    if org is None:
        return False
    if tipo in EVENTOS_PAGOS:
        org.assinatura_status = planos.STATUS_ATIVA
    elif tipo in EVENTOS_ATRASO:
        org.assinatura_status = planos.STATUS_ATRASADA
    else:
        org.assinatura_status = planos.STATUS_CANCELADA
    s.add(org)
    s.commit()
    return True

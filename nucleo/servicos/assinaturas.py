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


def _link_anual(s: Session, org: Organizacao, plano: str) -> str:
    """Plano anual: link de pagamento parcelável (até 10x), cobrado no ato. A fidelidade começa
    quando o pagamento é confirmado (ver processar_evento)."""
    if org.asaas_link_url and org.asaas_link_id and org.plano == plano and org.ciclo == planos.CICLO_ANUAL:
        return org.asaas_link_url  # mesmo plano e ciclo: reaproveita o link já criado
    nome = planos.PRECOS[plano]["nome"]
    valor = planos.valor_cobranca(plano, planos.CICLO_ANUAL)
    link_id, url = asaas.criar_link_anual(
        nome=f"Decidiu - plano {nome} anual",
        descricao=(f"Assinatura anual do plano {nome} do Decidiu. Fidelidade de 12 meses em contrato. "
                   "Pagamento no ato, em até 10x no cartão."),
        valor=valor,
        parcelas_maximas=planos.PARCELAS_MAXIMAS_ANUAL,
        referencia=f"org:{org.id}",
    )
    org.plano = plano
    org.ciclo = planos.CICLO_ANUAL
    org.asaas_link_id = link_id
    org.asaas_link_url = url
    s.add(org)
    s.commit()
    return url


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

    if ciclo == planos.CICLO_ANUAL:
        return _link_anual(s, org, plano)

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
    # Mensal: quem assina durante o teste começa a pagar quando o teste termina.
    # Anual: cobrança no ato da assinatura.
    inicio = hoje
    fim_teste = planos._com_fuso(org.teste_fim)
    if ciclo == planos.CICLO_MENSAL and org.assinatura_status == planos.STATUS_TESTE and fim_teste is not None:
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
    # Fidelidade: plano Fundador e planos anuais (em contrato).
    if plano == planos.PLANO_FUNDADOR or ciclo == planos.CICLO_ANUAL:
        meses = planos.MESES_FIDELIDADE_FUNDADOR if plano == planos.PLANO_FUNDADOR else planos.MESES_FIDELIDADE_ANUAL
        fim = _somar_meses(hoje, meses)
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


def _organizacao_do_link(s: Session, link_id: Optional[str]) -> Optional[Organizacao]:
    if not link_id:
        return None
    return s.exec(select(Organizacao).where(Organizacao.asaas_link_id == link_id)).first()


def _renovar_fidelidade_anual(org: Organizacao) -> None:
    """Pagamento confirmado: abre 12 meses de fidelidade, a não ser que ainda esteja dentro
    de um período já pago (parcelas seguintes não estendem o prazo)."""
    agora = planos.agora_utc()
    fim = planos._com_fuso(org.fidelidade_fim)
    if fim is not None and fim > agora:
        return
    fim_novo = _somar_meses(agora.date(), planos.MESES_FIDELIDADE_ANUAL)
    org.fidelidade_fim = datetime.datetime(fim_novo.year, fim_novo.month, fim_novo.day,
                                           tzinfo=datetime.timezone.utc)


def _organizacao_da_assinatura(s: Session, assinatura_id: Optional[str]) -> Optional[Organizacao]:
    if not assinatura_id:
        return None
    return s.exec(select(Organizacao).where(Organizacao.asaas_assinatura_id == assinatura_id)).first()


def processar_evento(s: Session, evento: dict) -> Optional[dict]:
    """Aplica um aviso do Asaas. Devolve None se nada mudou, ou um dicionário com a transição
    ('ativada' só na primeira vez que a organização passa a ativa, 'cancelada', 'atrasada')."""
    tipo = evento.get("event")
    if tipo in EVENTOS_PAGOS + EVENTOS_ATRASO:
        pagamento = evento.get("payment") or {}
        org = _organizacao_da_assinatura(s, pagamento.get("subscription"))
        if org is None:  # plano anual: o pagamento veio do link da organização
            org = _organizacao_do_link(s, pagamento.get("paymentLink"))
    elif tipo in EVENTOS_CANCELAMENTO:
        org = _organizacao_da_assinatura(s, (evento.get("subscription") or {}).get("id"))
    else:
        return None
    if org is None:
        return None
    anterior = org.assinatura_status
    if tipo in EVENTOS_PAGOS:
        org.assinatura_status = planos.STATUS_ATIVA
        if org.ciclo == planos.CICLO_ANUAL:
            _renovar_fidelidade_anual(org)
    elif tipo in EVENTOS_ATRASO:
        org.assinatura_status = planos.STATUS_ATRASADA
    else:
        org.assinatura_status = planos.STATUS_CANCELADA
    s.add(org)
    s.commit()
    if org.assinatura_status == planos.STATUS_ATIVA and anterior != planos.STATUS_ATIVA:
        return {"transicao": "ativada", "organizacao_id": org.id}
    if org.assinatura_status == planos.STATUS_CANCELADA and anterior != planos.STATUS_CANCELADA:
        return {"transicao": "cancelada", "organizacao_id": org.id}
    return {"transicao": "mantida", "organizacao_id": org.id}

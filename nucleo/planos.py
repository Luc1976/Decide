"""Planos e regras de acesso do SaaS.

Valores e prazos combinados com o dono do produto:
- Solo: R$ 29,90 por mês, ou R$ 299 por ano. 1 usuário com acesso total, 5 projetos ativos,
  10 atas por mês geradas com IA.
- Equipe: R$ 79,90 por mês, ou R$ 799 por ano. 10 integrantes com acesso total (1 administrador
  + 9 colaboradores), 30 projetos ativos, 50 atas por mês geradas com IA.
- Clientes que só acompanham projetos não contam como integrantes (em todos os planos).
- Fundador: plano separado, com as mesmas funções e limites do Equipe, a R$ 49,90 por mês para sempre,
  com fidelidade de 12 meses em contrato. Vagas limitadas (15 primeiros escritórios).
- Planos anuais: fidelidade de 12 meses em contrato; cobrança no ato da assinatura.
- Teste grátis de 30 dias antes de qualquer cobrança. Cobrança só por cartão de crédito.

A fidelidade do Fundador é contratual: o Asaas não a impõe, então o sistema não a bloqueia.
"""
import datetime
from typing import Optional

from sqlmodel import Session, select

from nucleo.tabelas import Organizacao

DIAS_TESTE = 30
LIMITE_FUNDADORES = 15
MESES_FIDELIDADE_FUNDADOR = 12
MESES_FIDELIDADE_ANUAL = 12  # planos anuais: fidelidade de 12 meses em contrato

PLANO_TESTE = "teste"
PLANO_SOLO = "solo"
PLANO_EQUIPE = "equipe"
PLANO_FUNDADOR = "fundador"
PLANO_INTERNO = "interno"       # operação própria do dono: sem cobrança

STATUS_TESTE = "teste"
STATUS_ATIVA = "ativa"
STATUS_PENDENTE = "pendente"
STATUS_ATRASADA = "atrasada"
STATUS_CANCELADA = "cancelada"

CICLO_MENSAL = "mensal"
CICLO_ANUAL = "anual"

# Preço por ciclo, em reais. O Fundador só existe no mensal.
PRECOS = {
    PLANO_SOLO: {"nome": "Solo", CICLO_MENSAL: 29.90, CICLO_ANUAL: 299.00},
    PLANO_EQUIPE: {"nome": "Equipe", CICLO_MENSAL: 79.90, CICLO_ANUAL: 799.00},
    PLANO_FUNDADOR: {"nome": "Fundador", CICLO_MENSAL: 49.90},
}

# Limites de uso por plano. O teste grátis usa os limites do Solo.
LIMITES = {
    PLANO_SOLO: {"administradores": 1, "colaboradores": 0, "projetos": 5},
    PLANO_EQUIPE: {"administradores": 1, "colaboradores": 9, "projetos": 30},
    PLANO_FUNDADOR: {"administradores": 1, "colaboradores": 9, "projetos": 30},
}
PLANO_BASE_TESTE = PLANO_SOLO

# Transcrições de IA (rascunho de ata) por organização, por mês. Conta só o que foi gerado com sucesso.
# Operação interna (PLANO_INTERNO) não tem limite.
LIMITES_IA_MENSAL = {
    PLANO_TESTE: 5,
    PLANO_SOLO: 10,
    PLANO_EQUIPE: 50,
    PLANO_FUNDADOR: 50,
}

MENSAGEM_TESTE_ENCERRADO = (
    "Seu período de teste terminou. Escolha um plano para continuar usando o Decidiu."
)
MENSAGEM_ASSINATURA_PENDENTE = (
    "A cobrança da sua assinatura ainda não foi confirmada. Confira o pagamento ou fale com o suporte."
)
MENSAGEM_ASSINATURA_ATRASADA = (
    "A assinatura da sua organização está com pagamento em atraso. Regularize para voltar a acessar."
)
MENSAGEM_ASSINATURA_CANCELADA = (
    "A assinatura da sua organização foi cancelada. Escolha um plano para continuar."
)


def agora_utc() -> datetime.datetime:
    """Horário atual em UTC, com fuso (o PostgreSQL exige fuso nas colunas de data/hora)."""
    return datetime.datetime.now(datetime.timezone.utc)


def _com_fuso(valor: Optional[datetime.datetime]) -> Optional[datetime.datetime]:
    """Valor em UTC com fuso. Sem fuso (SQLite ou dado antigo) é tratado como UTC."""
    if valor is None:
        return None
    if valor.tzinfo is None:
        return valor.replace(tzinfo=datetime.timezone.utc)
    return valor.astimezone(datetime.timezone.utc)


def valor_cobranca(plano: str, ciclo: str) -> float:
    """Valor em reais de um plano pago no ciclo escolhido."""
    tabela = PRECOS.get(plano)
    if tabela is None or ciclo not in tabela:
        raise ValueError(f"Plano '{plano}' não tem cobrança no ciclo '{ciclo}'.")
    return tabela[ciclo]


def acesso_liberado(org: Organizacao, agora: Optional[datetime.datetime] = None) -> bool:
    """Pode a organização usar o app agora? Só regra de assinatura, sem olhar a flag 'ativa'."""
    if org.plano == PLANO_INTERNO or org.assinatura_status == STATUS_ATIVA:
        return True
    agora = _com_fuso(agora or agora_utc())
    fim_teste = _com_fuso(org.teste_fim)
    return org.assinatura_status == STATUS_TESTE and fim_teste is not None and fim_teste > agora


def motivo_bloqueio(org: Organizacao) -> str:
    """Mensagem para a organização bloqueada pela assinatura."""
    if org.assinatura_status == STATUS_TESTE:
        return MENSAGEM_TESTE_ENCERRADO
    if org.assinatura_status == STATUS_PENDENTE:
        return MENSAGEM_ASSINATURA_PENDENTE
    if org.assinatura_status == STATUS_ATRASADA:
        return MENSAGEM_ASSINATURA_ATRASADA
    if org.assinatura_status == STATUS_CANCELADA:
        return MENSAGEM_ASSINATURA_CANCELADA
    return MENSAGEM_TESTE_ENCERRADO


def limites_da_org(org: Organizacao) -> Optional[dict]:
    """Limites da organização, ou None quando não há limite (operação interna)."""
    if org.plano == PLANO_INTERNO:
        return None
    return LIMITES[PLANO_BASE_TESTE if org.plano == PLANO_TESTE else org.plano]


def _nome_do_plano(org: Organizacao) -> str:
    if org.plano == PLANO_TESTE:
        return "Teste"
    return PRECOS.get(org.plano, {}).get("nome", org.plano)


def nome_do_plano(org: Organizacao) -> str:
    return _nome_do_plano(org)


def limite_ia_mensal(org: Organizacao) -> Optional[int]:
    """Transcrições de IA permitidas por mês para a organização, ou None quando não há limite."""
    if org.plano == PLANO_INTERNO:
        return None
    return LIMITES_IA_MENSAL.get(org.plano, 0)


def erro_limite_usuario(org: Organizacao, administradores: int, colaboradores: int,
                        novo_admin: bool, novo_cliente: bool = False) -> Optional[str]:
    """Mensagem de erro se cadastrar mais um usuário estoura o plano; None se cabe.
    Clientes (só acompanham projetos) não contam como colaboradores."""
    limites = limites_da_org(org)
    if limites is None or novo_cliente:
        return None
    if novo_admin and administradores + 1 > limites["administradores"]:
        return (f"O plano {_nome_do_plano(org)} permite {limites['administradores']} "
                f"administrador. Troque de plano para adicionar outro.")
    if not novo_admin and colaboradores + 1 > limites["colaboradores"]:
        return (f"O plano {_nome_do_plano(org)} permite {limites['colaboradores']} colaboradores. "
                f"Troque de plano para adicionar mais.")
    return None


def erro_limite_projeto(org: Organizacao, projetos: int) -> Optional[str]:
    """Mensagem de erro se criar mais um projeto estoura o plano; None se cabe."""
    limites = limites_da_org(org)
    if limites is None or projetos + 1 <= limites["projetos"]:
        return None
    return (f"O plano {_nome_do_plano(org)} permite até {limites['projetos']} projetos. "
            f"Troque de plano para criar mais.")


def contar_usuarios(s: Session, organizacao_id: int) -> tuple:
    """(administradores, colaboradores) da organização. Clientes não entram na contagem."""
    from nucleo.tabelas import Usuario
    linhas = s.exec(
        select(Usuario.admin, Usuario.pode_criar_projetos).where(Usuario.organizacao_id == organizacao_id)
    ).all()
    administradores = sum(1 for admin, _ in linhas if admin)
    colaboradores = sum(1 for admin, pode in linhas if not admin and pode)
    return administradores, colaboradores


def contar_projetos(s: Session, organizacao_id: int) -> int:
    """Projetos ativos (não arquivados) da organização."""
    from nucleo.tabelas import Projeto
    return len(s.exec(select(Projeto.id).where(
        Projeto.organizacao_id == organizacao_id, Projeto.arquivado == False  # noqa: E712
    )).all())


def vagas_fundador_restantes(s: Session) -> int:
    """Quantas vagas do plano Fundador ainda existem (quem cancelou libera a vaga)."""
    ocupadas = s.exec(
        select(Organizacao.id).where(
            Organizacao.plano == PLANO_FUNDADOR,
            Organizacao.assinatura_status != STATUS_CANCELADA,
        )
    ).all()
    return max(0, LIMITE_FUNDADORES - len(ocupadas))

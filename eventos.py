"""
Decidiu — registro de eventos de uso e métricas para o painel do administrador.

Uso rápido:
    from eventos import registrar_evento, TipoEvento
    registrar_evento(TipoEvento.LOGIN, usuario_id=u.id, usuario_email=u.email)

A tabela "eventos" é criada automaticamente pelo SQLModel.metadata.create_all(engine),
desde que este módulo seja importado ANTES dessa chamada (ver INTEGRACAO.md).
"""

from __future__ import annotations

import logging
import os
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from sqlalchemy import JSON, Column, DateTime, func
from sqlmodel import Field, Session, SQLModel, select

log = logging.getLogger("decidiu.eventos")
FUSO = ZoneInfo("America/Sao_Paulo")


# --------------------------------------------------------------------------- #
# Tipos de evento
# --------------------------------------------------------------------------- #
class TipoEvento:
    CADASTRO = "cadastro"                    # novo usuário criou conta
    LOGIN = "login"                          # login bem-sucedido
    LOGIN_FALHOU = "login_falhou"            # senha errada / usuário inexistente
    ACESSO = "acesso"                        # sessão aberta já logado (sem novo login)
    TRIAL_INICIADO = "trial_iniciado"
    ASSINATURA_ATIVADA = "assinatura_ativada"
    ASSINATURA_CANCELADA = "assinatura_cancelada"
    PROJETO_CRIADO = "projeto_criado"
    DECISAO_CRIADA = "decisao_criada"
    ATA_CRIADA = "ata_criada"
    RELATORIO_PDF = "relatorio_pdf"
    ACESSO_ADMIN_NEGADO = "acesso_admin_negado"  # alguém tentou abrir o painel


TIPOS_DE_ATIVIDADE = (TipoEvento.LOGIN, TipoEvento.ACESSO)


# --------------------------------------------------------------------------- #
# Modelo
# --------------------------------------------------------------------------- #
def _agora_utc() -> datetime:
    return datetime.now(timezone.utc)


class Evento(SQLModel, table=True):
    __tablename__ = "eventos"

    id: Optional[int] = Field(default=None, primary_key=True)
    tipo: str = Field(index=True, max_length=50)
    usuario_id: Optional[int] = Field(default=None, index=True)
    usuario_email: Optional[str] = Field(default=None, max_length=255)
    projeto_id: Optional[int] = Field(default=None)
    detalhes: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    criado_em: datetime = Field(
        default_factory=_agora_utc,
        sa_column=Column(DateTime(timezone=True), index=True, nullable=False),
    )


# --------------------------------------------------------------------------- #
# Engine (usa o do database.py do projeto)
# --------------------------------------------------------------------------- #
def _engine_padrao():
    from database import engine  # engine do PostgreSQL "Decidiudata"

    return engine


# --------------------------------------------------------------------------- #
# Registro
# --------------------------------------------------------------------------- #
def registrar_evento(
    tipo: str,
    usuario_id: Optional[int] = None,
    usuario_email: Optional[str] = None,
    projeto_id: Optional[int] = None,
    detalhes: Optional[dict] = None,
    engine=None,
) -> None:
    """Grava um evento. Nunca levanta exceção: uma falha aqui não pode
    derrubar o login ou o cadastro do usuário."""
    try:
        engine = engine or _engine_padrao()
        with Session(engine) as s:
            s.add(
                Evento(
                    tipo=tipo,
                    usuario_id=usuario_id,
                    usuario_email=(usuario_email or "").strip().lower() or None,
                    projeto_id=projeto_id,
                    detalhes=detalhes,
                )
            )
            s.commit()
    except Exception:  # noqa: BLE001
        log.exception("Falha ao registrar evento %s", tipo)


# --------------------------------------------------------------------------- #
# Controle de acesso ao painel
# --------------------------------------------------------------------------- #
def emails_admin() -> set[str]:
    """Lê a variável de ambiente ADMIN_EMAILS (separados por vírgula)."""
    bruto = os.getenv("ADMIN_EMAILS", "")
    return {e.strip().lower() for e in bruto.split(",") if e.strip()}


def eh_admin(email: Optional[str]) -> bool:
    if not email:
        return False
    admins = emails_admin()
    return bool(admins) and email.strip().lower() in admins


# --------------------------------------------------------------------------- #
# Métricas para o painel
# --------------------------------------------------------------------------- #
def _contar(s: Session, tipo: str, desde: Optional[datetime] = None) -> int:
    q = select(func.count()).select_from(Evento).where(Evento.tipo == tipo)
    if desde is not None:
        q = q.where(Evento.criado_em >= desde)
    return s.exec(q).one()


def _usuarios_ativos(s: Session, desde: datetime) -> int:
    q = (
        select(func.count(func.distinct(Evento.usuario_id)))
        .where(Evento.tipo.in_(TIPOS_DE_ATIVIDADE))
        .where(Evento.usuario_id.is_not(None))
        .where(Evento.criado_em >= desde)
    )
    return s.exec(q).one()


def _como_utc(dt: datetime) -> datetime:
    # SQLite devolve datetimes sem fuso; PostgreSQL devolve com fuso.
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def metricas(engine=None, dias_grafico: int = 30) -> dict:
    """Tudo que o painel mostra, em uma única chamada."""
    engine = engine or _engine_padrao()
    agora = _agora_utc()
    hoje_local = agora.astimezone(FUSO).replace(hour=0, minute=0, second=0, microsecond=0)
    inicio_hoje = hoje_local.astimezone(timezone.utc)
    d7 = agora - timedelta(days=7)
    d30 = agora - timedelta(days=30)

    with Session(engine) as s:
        trials = _contar(s, TipoEvento.TRIAL_INICIADO)
        assinaturas = _contar(s, TipoEvento.ASSINATURA_ATIVADA)

        r = {
            "cadastros_total": _contar(s, TipoEvento.CADASTRO),
            "cadastros_7d": _contar(s, TipoEvento.CADASTRO, d7),
            "cadastros_30d": _contar(s, TipoEvento.CADASTRO, d30),
            "ativos_hoje": _usuarios_ativos(s, inicio_hoje),
            "ativos_7d": _usuarios_ativos(s, d7),
            "ativos_30d": _usuarios_ativos(s, d30),
            "trials_total": trials,
            "assinaturas_total": assinaturas,
            "cancelamentos_total": _contar(s, TipoEvento.ASSINATURA_CANCELADA),
            "conversao_trial": (assinaturas / trials * 100) if trials else 0.0,
            "logins_falhos_7d": _contar(s, TipoEvento.LOGIN_FALHOU, d7),
            "projetos_30d": _contar(s, TipoEvento.PROJETO_CRIADO, d30),
            "decisoes_30d": _contar(s, TipoEvento.DECISAO_CRIADA, d30),
        }

        # Cadastros por dia (agrupados no fuso de São Paulo, em Python,
        # para funcionar igual no PostgreSQL e no SQLite local).
        inicio_grafico = hoje_local - timedelta(days=dias_grafico - 1)
        datas = s.exec(
            select(Evento.criado_em)
            .where(Evento.tipo == TipoEvento.CADASTRO)
            .where(Evento.criado_em >= inicio_grafico.astimezone(timezone.utc))
        ).all()
        por_dia = Counter(_como_utc(d).astimezone(FUSO).date() for d in datas)
        r["cadastros_por_dia"] = [
            (dia, por_dia.get(dia, 0))
            for dia in (
                (inicio_grafico + timedelta(days=i)).date() for i in range(dias_grafico)
            )
        ]

        ultimos = s.exec(
            select(Evento).order_by(Evento.criado_em.desc()).limit(50)
        ).all()
        r["ultimos_eventos"] = [
            {
                "quando": _como_utc(e.criado_em).astimezone(FUSO).strftime("%d/%m %H:%M"),
                "tipo": e.tipo,
                "email": e.usuario_email or "—",
            }
            for e in ultimos
        ]

    return r

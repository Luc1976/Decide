"""Trilha de auditoria. Cada serviço que grava chama registrar() na MESMA transação:
se a gravação for desfeita, o registro de auditoria também é."""
import json
from typing import Optional

from sqlmodel import Session, select

from nucleo.ator import Ator
from nucleo.tabelas import RegistroAuditoria


def registrar(
    s: Session,
    ator: Ator,
    acao: str,
    projeto_id: Optional[int] = None,
    alvo_tipo: Optional[str] = None,
    alvo_id: Optional[int] = None,
    detalhes=None,
) -> None:
    if detalhes is not None and not isinstance(detalhes, str):
        detalhes = json.dumps(detalhes, ensure_ascii=False, default=str)
    s.add(RegistroAuditoria(
        usuario_id=ator.id,
        usuario_nome=ator.username or ator.nome,
        acao=acao,
        projeto_id=projeto_id,
        alvo_tipo=alvo_tipo,
        alvo_id=alvo_id,
        detalhes=detalhes,
    ))


def listar(s: Session, projeto_id: Optional[int] = None, limite: int = 200):
    consulta = select(RegistroAuditoria)
    if projeto_id is not None:
        consulta = consulta.where(RegistroAuditoria.projeto_id == projeto_id)
    return s.exec(
        consulta.order_by(RegistroAuditoria.momento.desc(), RegistroAuditoria.id.desc()).limit(limite)
    ).all()

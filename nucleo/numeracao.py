"""Sequenciais por projeto: D-001 (decisões), P-001 (pendências), Ata 01.

O número é 'maior + 1'. Com vários usuários gravando ao mesmo tempo, duas transações
poderiam ler o mesmo 'maior' e gerar números repetidos. Para evitar isso, a linha do
projeto é travada (SELECT ... FOR UPDATE) antes de calcular: no PostgreSQL, quem chegar
depois espera a primeira transação terminar. No SQLite a trava é ignorada (lá a gravação
já é serializada pelo próprio arquivo)."""
from sqlmodel import Session, select

from nucleo.tabelas import Decisao, Pendencia, Projeto, Reuniao


def travar_projeto(s: Session, projeto_id: int) -> None:
    s.exec(select(Projeto.id).where(Projeto.id == projeto_id).with_for_update()).first()


def _proximo(s: Session, coluna, projeto_coluna, projeto_id: int) -> int:
    ultimo = s.exec(
        select(coluna).where(projeto_coluna == projeto_id, coluna != None)  # noqa: E711
        .order_by(coluna.desc())
    ).first()
    return (ultimo or 0) + 1


def proxima_decisao(s: Session, projeto_id: int) -> int:
    return _proximo(s, Decisao.numero, Decisao.projeto_id, projeto_id)


def proxima_pendencia(s: Session, projeto_id: int) -> int:
    return _proximo(s, Pendencia.numero, Pendencia.projeto_id, projeto_id)


def proxima_ata(s: Session, projeto_id: int) -> int:
    return _proximo(s, Reuniao.numero, Reuniao.projeto_id, projeto_id)


def codigo_decisao(numero) -> str:
    return f"D-{numero:03d}" if numero else "D-???"


def codigo_pendencia(numero) -> str:
    return f"P-{numero:03d}"

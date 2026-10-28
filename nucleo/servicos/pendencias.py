"""Pendências: assuntos que aguardam decisão (P-001, P-002...)."""
import datetime
from typing import List, Optional

from sqlmodel import Session, select

from nucleo import auditoria, numeracao
from nucleo.ator import Ator
from nucleo.erros import Conflito, NaoEncontrado
from nucleo.marcacoes import normalizar
from nucleo.permissoes import EDITOR, LEITOR, exigir
from nucleo.tabelas import (
    PENDENCIA_ABERTA,
    PENDENCIA_CANCELADA,
    PENDENCIA_RESOLVIDA,
    Decisao,
    Pendencia,
)


def _agora():
    return datetime.datetime.now(datetime.timezone.utc)


# ---------------------------------------------------------------- consultas sem checagem

def consultar(s: Session, projeto_id: int, status: Optional[str] = None, termo: str = "") -> List[Pendencia]:
    """Em aberto primeiro (prazo mais próximo antes), depois as demais (mais recentes antes).
    'termo' filtra por assunto, detalhes, responsável ou categoria (sem acentos)."""
    consulta = select(Pendencia).where(Pendencia.projeto_id == projeto_id)
    if status:
        consulta = consulta.where(Pendencia.status == status)
    pendencias = list(s.exec(consulta).all())
    termo_busca = normalizar(termo)
    if termo_busca:
        pendencias = [p for p in pendencias
                      if termo_busca in normalizar(" ".join([p.titulo, p.descricao, p.responsavel, p.categoria]))]
    abertas = sorted((p for p in pendencias if p.status == PENDENCIA_ABERTA),
                     key=lambda p: (p.prazo is None, p.prazo or datetime.date.max, p.numero))
    encerradas = sorted((p for p in pendencias if p.status != PENDENCIA_ABERTA),
                        key=lambda p: (p.data_resolucao or datetime.datetime.min, p.numero), reverse=True)
    return abertas + encerradas


def contar_abertas(s: Session, projeto_id: int) -> int:
    return len(s.exec(select(Pendencia.id).where(
        Pendencia.projeto_id == projeto_id, Pendencia.status == PENDENCIA_ABERTA)).all())


def _para_alterar(s: Session, ator: Ator, pendencia_id: int, projeto_id: Optional[int]) -> Pendencia:
    pendencia = s.get(Pendencia, pendencia_id)
    if pendencia is None or (projeto_id is not None and pendencia.projeto_id != projeto_id):
        raise NaoEncontrado("Pendência não encontrada.")
    exigir(s, ator, pendencia.projeto_id, EDITOR)
    return pendencia


def _exigir_aberta(p: Pendencia, mensagem: str = "Esta pendência não está em aberto.") -> None:
    if p.status != PENDENCIA_ABERTA:
        raise Conflito(mensagem)


# ---------------------------------------------------------------- serviços

def listar(s: Session, ator: Ator, projeto_id: int, status: Optional[str] = None, termo: str = "") -> List[Pendencia]:
    exigir(s, ator, projeto_id, LEITOR)
    return consultar(s, projeto_id, status, termo)


def obter(s: Session, ator: Ator, projeto_id: int, pendencia_id: int) -> Pendencia:
    exigir(s, ator, projeto_id, LEITOR)
    p = s.get(Pendencia, pendencia_id)
    if p is None or p.projeto_id != projeto_id:
        raise NaoEncontrado("Pendência não encontrada.")
    return p


def criar(s: Session, ator: Ator, projeto_id: int, titulo: str, descricao: str = "",
          categoria: str = "Geral", responsavel: str = "",
          prazo: Optional[datetime.date] = None) -> Pendencia:
    titulo = (titulo or "").strip()
    if not titulo:
        raise ValueError("Informe o assunto pendente.")
    exigir(s, ator, projeto_id, EDITOR)
    numeracao.travar_projeto(s, projeto_id)
    pendencia = Pendencia(
        projeto_id=projeto_id,
        numero=numeracao.proxima_pendencia(s, projeto_id),
        titulo=titulo,
        descricao=(descricao or "").strip(),
        categoria=categoria or "Geral",
        responsavel=(responsavel or "").strip(),
        prazo=prazo,
        autor=ator.nome,
    )
    s.add(pendencia)
    s.flush()
    auditoria.registrar(s, ator, "pendencia.criar", projeto_id, "pendencia", pendencia.id,
                        {"numero": pendencia.numero})
    s.commit()
    s.refresh(pendencia)
    return pendencia


def atualizar(s: Session, ator: Ator, pendencia_id: int, titulo: str, descricao: str, categoria: str,
              responsavel: str, prazo: Optional[datetime.date], projeto_id: Optional[int] = None) -> Pendencia:
    titulo = (titulo or "").strip()
    if not titulo:
        raise ValueError("Informe o assunto pendente.")
    p = _para_alterar(s, ator, pendencia_id, projeto_id)
    _exigir_aberta(p, "Só pendências em aberto podem ser editadas. Reabra-a primeiro.")
    p.titulo = titulo
    p.descricao = (descricao or "").strip()
    p.categoria = categoria or "Geral"
    p.responsavel = (responsavel or "").strip()
    p.prazo = prazo
    s.add(p)
    auditoria.registrar(s, ator, "pendencia.atualizar", p.projeto_id, "pendencia", p.id)
    s.commit()
    s.refresh(p)
    return p


def resolver(s: Session, ator: Ator, pendencia_id: int, decisao_id: Optional[int] = None,
             nova_decisao: Optional[dict] = None, observacao: str = "",
             projeto_id: Optional[int] = None) -> Pendencia:
    """Marca a pendência como resolvida, ligada a uma decisão:
    - decisao_id: decisão já registrada no mesmo projeto; ou
    - nova_decisao: {"titulo", "descricao", "categoria", "impacto", "justificativa"} cria a
      decisão (D-xxx) na mesma transação."""
    p = _para_alterar(s, ator, pendencia_id, projeto_id)
    _exigir_aberta(p)
    if nova_decisao is not None:
        titulo = (nova_decisao.get("titulo") or "").strip()
        if not titulo:
            raise ValueError("Informe o título da decisão.")
        numeracao.travar_projeto(s, p.projeto_id)
        decisao = Decisao(
            projeto_id=p.projeto_id,
            titulo=titulo,
            categoria=nova_decisao.get("categoria") or p.categoria or "Geral",
            descricao=(nova_decisao.get("descricao") or "").strip() or titulo,
            justificativa=(nova_decisao.get("justificativa") or "").strip()
            or f"Resolve a pendência {numeracao.codigo_pendencia(p.numero)} - {p.titulo}",
            impacto=nova_decisao.get("impacto") or "Médio",
            autor=ator.nome,
            numero=numeracao.proxima_decisao(s, p.projeto_id),
        )
        s.add(decisao)
        s.flush()
        decisao_id = decisao.id
        auditoria.registrar(s, ator, "decisao.criar", p.projeto_id, "decisao", decisao.id,
                            {"numero": decisao.numero, "origem": "pendencia"})
    elif decisao_id is not None:
        decisao = s.get(Decisao, decisao_id)
        if decisao is None or decisao.projeto_id != p.projeto_id:
            raise ValueError("Escolha uma decisão deste projeto.")
    else:
        raise ValueError("Escolha a decisão que resolve a pendência.")
    p.status = PENDENCIA_RESOLVIDA
    p.decisao_id = decisao_id
    p.resolucao = (observacao or "").strip()
    p.resolvida_por = ator.nome
    p.data_resolucao = _agora()
    s.add(p)
    auditoria.registrar(s, ator, "pendencia.resolver", p.projeto_id, "pendencia", p.id,
                        {"decisao_id": decisao_id})
    s.commit()
    s.refresh(p)
    return p


def cancelar(s: Session, ator: Ator, pendencia_id: int, motivo: str,
             projeto_id: Optional[int] = None) -> Pendencia:
    """Assunto que deixou de precisar de decisão. Fica no histórico (não é apagado)."""
    motivo = (motivo or "").strip()
    if not motivo:
        raise ValueError("Informe o motivo do cancelamento.")
    p = _para_alterar(s, ator, pendencia_id, projeto_id)
    _exigir_aberta(p)
    p.status = PENDENCIA_CANCELADA
    p.resolucao = motivo
    p.resolvida_por = ator.nome
    p.data_resolucao = _agora()
    s.add(p)
    auditoria.registrar(s, ator, "pendencia.cancelar", p.projeto_id, "pendencia", p.id)
    s.commit()
    s.refresh(p)
    return p


def reabrir(s: Session, ator: Ator, pendencia_id: int, projeto_id: Optional[int] = None) -> Pendencia:
    """Volta a pendência para 'Aberta'. A decisão ligada (se houver) continua registrada."""
    p = _para_alterar(s, ator, pendencia_id, projeto_id)
    p.status = PENDENCIA_ABERTA
    p.decisao_id = None
    p.resolucao = ""
    p.resolvida_por = ""
    p.data_resolucao = None
    s.add(p)
    auditoria.registrar(s, ator, "pendencia.reabrir", p.projeto_id, "pendencia", p.id)
    s.commit()
    s.refresh(p)
    return p

"""Permissões por projeto.

Níveis: 0 sem acesso, 1 Leitor, 2 Editor, 3 Responsável, 4 administrador.

Regra de ouro da nova arquitetura: TODA leitura e TODA gravação passa por aqui, dentro
do serviço. A tela (Flet ou frontend web) só esconde botões; quem barra é o serviço.

Isolamento entre organizações: usuário e projeto precisam ser da MESMA organização, e ela
precisa estar ativa. Isso vale também para o administrador (que só administra a sua) e para
o superadmin (que gerencia organizações, mas não lê os projetos delas).
"""
from typing import Optional

from sqlmodel import Session, select

from models import NIVEL_ADMIN, NIVEL_PAPEL
from nucleo.ator import Ator
from nucleo.erros import NaoEncontrado, SemPermissao
from nucleo.tabelas import MembroProjeto, Organizacao, Projeto, Usuario

LEITOR, EDITOR, RESPONSAVEL = "Leitor", "Editor", "Responsável"


def nivel(s: Session, usuario_id: Optional[int], projeto_id: int) -> int:
    """Nível do usuário no projeto. Lê o usuário do banco a cada chamada: se o acesso
    foi retirado com a sessão aberta, vale na hora."""
    if usuario_id is None:
        return 0
    usuario = s.get(Usuario, usuario_id)
    projeto = s.get(Projeto, projeto_id)
    if usuario is None or projeto is None:
        return 0
    if not mesma_organizacao_ativa(s, usuario, projeto.organizacao_id):
        return 0
    if usuario.admin:
        return NIVEL_ADMIN
    membro = s.exec(
        select(MembroProjeto).where(
            MembroProjeto.projeto_id == projeto_id, MembroProjeto.usuario_id == usuario_id
        )
    ).first()
    return NIVEL_PAPEL.get(membro.papel, 0) if membro else 0


def exigir(s: Session, ator: Ator, projeto_id: int, minimo: str = LEITOR) -> int:
    """Barra a ação se o ator não tem o papel mínimo. Devolve o nível.

    Sem nenhum acesso ao projeto -> NaoEncontrado (não revela que o projeto existe).
    Com acesso, mas papel insuficiente -> SemPermissao."""
    n = nivel(s, ator.id, projeto_id)
    if n == 0:
        if minimo == LEITOR:
            raise NaoEncontrado("Projeto não encontrado.")
        # Compatibilidade com o app Flet, que espera PermissionError nas gravações.
        raise SemPermissao()
    if n < NIVEL_PAPEL[minimo]:
        raise SemPermissao()
    return n


def organizacao_ativa(s: Session, organizacao_id: Optional[int]) -> bool:
    org = s.get(Organizacao, organizacao_id) if organizacao_id is not None else None
    if org is None or not org.ativa:
        return False
    from nucleo.planos import acesso_liberado  # import tardio: planos depende só de tabelas
    return acesso_liberado(org)


def mesma_organizacao_ativa(s: Session, usuario: Usuario, organizacao_id: Optional[int]) -> bool:
    return (
        organizacao_id is not None
        and usuario.organizacao_id == organizacao_id
        and organizacao_ativa(s, organizacao_id)
    )


def exigir_admin(s: Session, ator: Ator) -> Usuario:
    """Administrador da organização (ativa). Devolve o usuário, já lido do banco."""
    usuario = s.get(Usuario, ator.id) if ator.id is not None else None
    if usuario is None or not usuario.admin or not organizacao_ativa(s, usuario.organizacao_id):
        raise SemPermissao("Só administradores podem fazer isso.")
    return usuario


def exigir_superadmin(s: Session, ator: Ator) -> Usuario:
    """Dono da plataforma (gerencia organizações)."""
    usuario = s.get(Usuario, ator.id) if ator.id is not None else None
    if usuario is None or not usuario.superadmin or not organizacao_ativa(s, usuario.organizacao_id):
        raise SemPermissao("Só o administrador da plataforma pode fazer isso.")
    return usuario


def pode_editar(nivel_atual: int) -> bool:
    return nivel_atual >= NIVEL_PAPEL[EDITOR]

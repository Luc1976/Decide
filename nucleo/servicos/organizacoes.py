"""Organizações (escritórios assinantes do SaaS).

- Administrador da organização: vê e renomeia a SUA organização.
- Superadmin (dono da plataforma): cria organizações com o primeiro administrador, lista
  todas (só contagens, nunca o conteúdo) e ativa/desativa. Não lê projetos de ninguém.
"""
import re
import unicodedata
from dataclasses import dataclass
from typing import List, Optional

from sqlalchemy import func
from sqlmodel import Session, select

from nucleo import auditoria
from nucleo.ator import Ator
from nucleo.erros import NaoEncontrado
from nucleo.permissoes import exigir_admin, exigir_superadmin
from nucleo.servicos.usuarios import novo_usuario
from nucleo.tabelas import Organizacao, Projeto, Usuario


@dataclass
class ResumoOrganizacao:
    organizacao: Organizacao
    usuarios: int
    projetos: int


def gerar_slug(nome: str) -> str:
    texto = unicodedata.normalize("NFKD", nome or "")
    texto = "".join(c for c in texto if not unicodedata.combining(c)).lower()
    return re.sub(r"[^a-z0-9]+", "-", texto).strip("-")[:60] or "organizacao"


def _slug_livre(s: Session, nome: str) -> str:
    base = gerar_slug(nome)
    slug, n = base, 2
    while s.exec(select(Organizacao.id).where(Organizacao.slug == slug)).first() is not None:
        slug, n = f"{base}-{n}", n + 1
    return slug


def _validar_nome(nome: str) -> str:
    nome = (nome or "").strip()
    if not nome:
        raise ValueError("Informe o nome da organização.")
    return nome


def nova_organizacao(s: Session, nome: str) -> Organizacao:
    """Adiciona na sessão, sem commit (usada também na criação do banco)."""
    org = Organizacao(nome=_validar_nome(nome), slug=_slug_livre(s, nome))
    s.add(org)
    s.flush()
    return org


# ---------------------------------------------------------------- administrador da organização

def minha(s: Session, ator: Ator) -> Organizacao:
    usuario = s.get(Usuario, ator.id) if ator.id is not None else None
    org = s.get(Organizacao, usuario.organizacao_id) if usuario and usuario.organizacao_id else None
    if org is None:
        raise NaoEncontrado("Organização não encontrada.")
    return org


def renomear(s: Session, ator: Ator, nome: str) -> Organizacao:
    org = s.get(Organizacao, exigir_admin(s, ator).organizacao_id)
    org.nome = _validar_nome(nome)
    s.add(org)
    auditoria.registrar(s, ator, "organizacao.renomear", alvo_tipo="organizacao", alvo_id=org.id,
                        detalhes={"nome": org.nome})
    s.commit()
    s.refresh(org)
    return org


# ---------------------------------------------------------------- plataforma (superadmin)

def listar(s: Session, ator: Ator) -> List[ResumoOrganizacao]:
    exigir_superadmin(s, ator)
    usuarios = dict(s.exec(select(Usuario.organizacao_id, func.count(Usuario.id)).group_by(Usuario.organizacao_id)).all())
    projetos = dict(s.exec(select(Projeto.organizacao_id, func.count(Projeto.id)).group_by(Projeto.organizacao_id)).all())
    return [ResumoOrganizacao(o, usuarios.get(o.id, 0), projetos.get(o.id, 0))
            for o in s.exec(select(Organizacao).order_by(Organizacao.nome)).all()]


def criar(s: Session, ator: Ator, nome: str, admin_username: str, admin_nome: str,
          admin_senha: str) -> Organizacao:
    """Nova organização com o primeiro administrador, numa transação só."""
    exigir_superadmin(s, ator)
    org = nova_organizacao(s, nome)
    admin = novo_usuario(s, admin_username, admin_senha, admin_nome, org.id, admin=True)
    auditoria.registrar(s, ator, "organizacao.criar", alvo_tipo="organizacao", alvo_id=org.id,
                        detalhes={"nome": org.nome, "admin": admin.username})
    s.commit()
    s.refresh(org)
    return org


def definir_ativa(s: Session, ator: Ator, organizacao_id: int, ativa: bool) -> Organizacao:
    """Desativar bloqueia o login de todos da organização (os dados ficam guardados)."""
    superadmin = exigir_superadmin(s, ator)
    org = s.get(Organizacao, organizacao_id)
    if org is None:
        raise NaoEncontrado("Organização não encontrada.")
    if not ativa and org.id == superadmin.organizacao_id:
        raise ValueError("Você não pode desativar a sua própria organização.")
    org.ativa = ativa
    s.add(org)
    auditoria.registrar(s, ator, "organizacao.ativar" if ativa else "organizacao.desativar",
                        alvo_tipo="organizacao", alvo_id=org.id)
    s.commit()
    s.refresh(org)
    return org


def obter(s: Session, organizacao_id: Optional[int]) -> Optional[Organizacao]:
    return s.get(Organizacao, organizacao_id) if organizacao_id is not None else None

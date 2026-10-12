"""Usuários: login, cadastro (admin) e troca de senha."""
from typing import List, Optional

from sqlmodel import Session, select

from nucleo import auditoria
from nucleo.ator import Ator
from nucleo.erros import NaoEncontrado
from nucleo.permissoes import exigir_admin
from nucleo.senhas import eh_hash, hash_senha, senha_confere, validar_nova_senha
from nucleo.tabelas import Usuario


def _limpar_username(username: str) -> str:
    return (username or "").strip().lower()


def buscar_por_username(s: Session, username: str) -> Optional[Usuario]:
    return s.exec(select(Usuario).where(Usuario.username == _limpar_username(username))).first()


def ator_por_id(s: Session, usuario_id: Optional[int], nome: Optional[str] = None) -> Ator:
    """Ator a partir do id. Usuário inexistente vira um ator sem acesso a nada."""
    usuario = s.get(Usuario, usuario_id) if usuario_id is not None else None
    if usuario is None:
        return Ator(id=usuario_id, nome=nome or "")
    return Ator.de_usuario(usuario, nome)


def autenticar(s: Session, username: str, senha: str) -> Optional[Usuario]:
    """Confere usuário e senha. Senha legada em texto puro é migrada para hash."""
    usuario = buscar_por_username(s, username)
    if not usuario or not senha_confere(senha or "", usuario.senha):
        return None
    if not eh_hash(usuario.senha):
        usuario.senha = hash_senha(senha)
        s.add(usuario)
        s.commit()
        s.refresh(usuario)
    return usuario


def criar(
    s: Session,
    username: str,
    senha: str,
    nome_completo: str,
    admin: bool = False,
    pode_criar_projetos: bool = True,
    ator: Optional[Ator] = None,
) -> Usuario:
    """Cadastra um usuário. Com 'ator', exige que ele seja administrador (API);
    sem 'ator' é uso interno (linha de comando, admin inicial)."""
    if ator is not None:
        exigir_admin(s, ator)
    username = _limpar_username(username)
    nome_completo = (nome_completo or "").strip()
    if not username or not nome_completo:
        raise ValueError("Preencha o nome completo e o usuário.")
    if " " in username:
        raise ValueError("O usuário não pode conter espaços.")
    validar_nova_senha(senha)
    if buscar_por_username(s, username):
        raise ValueError(f"O usuário '{username}' já existe.")
    usuario = Usuario(
        username=username,
        senha=hash_senha(senha),
        nome_completo=nome_completo,
        admin=admin,
        pode_criar_projetos=pode_criar_projetos or admin,
    )
    s.add(usuario)
    s.flush()
    if ator is not None:
        auditoria.registrar(s, ator, "usuario.criar", alvo_tipo="usuario", alvo_id=usuario.id,
                            detalhes={"username": username, "admin": admin})
    s.commit()
    s.refresh(usuario)
    return usuario


def listar(s: Session, ator: Optional[Ator] = None) -> List[Usuario]:
    if ator is not None:
        exigir_admin(s, ator)
    return list(s.exec(select(Usuario).order_by(Usuario.nome_completo)).all())


def alterar_propria_senha(s: Session, ator: Ator, senha_atual: str, nova_senha: str) -> None:
    validar_nova_senha(nova_senha, "A nova senha deve ter pelo menos 6 caracteres.")
    usuario = s.get(Usuario, ator.id) if ator.id is not None else None
    if usuario is None or not senha_confere(senha_atual or "", usuario.senha):
        raise ValueError("A senha atual está incorreta.")
    usuario.senha = hash_senha(nova_senha)
    s.add(usuario)
    auditoria.registrar(s, ator, "usuario.trocar_senha", alvo_tipo="usuario", alvo_id=usuario.id)
    s.commit()


def redefinir_senha(s: Session, username: str, nova_senha: str) -> None:
    """Uso administrativo (linha de comando / variável de ambiente)."""
    validar_nova_senha(nova_senha)
    usuario = buscar_por_username(s, username)
    if usuario is None:
        raise NaoEncontrado(f"Usuário '{username}' não encontrado.")
    usuario.senha = hash_senha(nova_senha)
    s.add(usuario)
    s.commit()

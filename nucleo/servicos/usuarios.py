"""Usuários: login, cadastro (admin da organização) e troca de senha."""
from typing import List, Optional

from sqlmodel import Session, select

from nucleo import auditoria
from nucleo.ator import Ator
from nucleo.erros import NaoEncontrado, SemPermissao
from nucleo.permissoes import exigir_admin, organizacao_ativa
from nucleo.senhas import eh_hash, hash_senha, senha_confere, validar_nova_senha
from nucleo.tabelas import Organizacao, Usuario

MENSAGEM_ORG_DESATIVADA = "O acesso da sua organização está suspenso. Fale com o suporte do Decidiu."


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
    """Confere usuário e senha (None se não conferem). Senha legada em texto puro é migrada
    para hash. Senha certa, mas organização desativada -> SemPermissao."""
    usuario = buscar_por_username(s, username)
    if not usuario or not senha_confere(senha or "", usuario.senha):
        return None
    if not organizacao_ativa(s, usuario.organizacao_id):
        raise SemPermissao(MENSAGEM_ORG_DESATIVADA)
    if not eh_hash(usuario.senha):
        usuario.senha = hash_senha(senha)
        s.add(usuario)
        s.commit()
        s.refresh(usuario)
    return usuario


def organizacao_padrao(s: Session) -> Optional[int]:
    """Id da organização quando só existe UMA (instalação de um escritório só)."""
    ids = s.exec(select(Organizacao.id).limit(2)).all()
    return ids[0] if len(ids) == 1 else None


def novo_usuario(s: Session, username: str, senha: str, nome_completo: str, organizacao_id: int,
                 admin: bool = False, pode_criar_projetos: bool = True, superadmin: bool = False) -> Usuario:
    """Valida e adiciona o usuário na sessão, SEM commit (para compor com outra gravação)."""
    username = _limpar_username(username)
    nome_completo = (nome_completo or "").strip()
    if not username or not nome_completo:
        raise ValueError("Preencha o nome completo e o usuário.")
    if " " in username:
        raise ValueError("O usuário não pode conter espaços.")
    validar_nova_senha(senha)
    if s.get(Organizacao, organizacao_id) is None:
        raise ValueError("Organização não encontrada.")
    # O login é único na plataforma toda (a pessoa entra só com o usuário).
    if buscar_por_username(s, username):
        raise ValueError(f"O usuário '{username}' já existe.")
    usuario = Usuario(
        username=username,
        senha=hash_senha(senha),
        nome_completo=nome_completo,
        admin=admin,
        pode_criar_projetos=pode_criar_projetos or admin,
        organizacao_id=organizacao_id,
        superadmin=superadmin,
    )
    s.add(usuario)
    s.flush()
    return usuario


def criar(
    s: Session,
    username: str,
    senha: str,
    nome_completo: str,
    admin: bool = False,
    pode_criar_projetos: bool = True,
    ator: Optional[Ator] = None,
    organizacao_id: Optional[int] = None,
) -> Usuario:
    """Cadastra um usuário.

    Com 'ator' (API e telas): ele precisa ser administrador, e o usuário novo entra na
    organização DELE. Sem 'ator' (linha de comando): na 'organizacao_id' informada ou, se
    houver uma só organização, nela."""
    if ator is not None:
        organizacao_id = exigir_admin(s, ator).organizacao_id
    elif organizacao_id is None:
        organizacao_id = organizacao_padrao(s)
        if organizacao_id is None:
            raise ValueError("Informe a organização do usuário.")
    usuario = novo_usuario(s, username, senha, nome_completo, organizacao_id, admin, pode_criar_projetos)
    if ator is not None:
        auditoria.registrar(s, ator, "usuario.criar", alvo_tipo="usuario", alvo_id=usuario.id,
                            detalhes={"username": usuario.username, "admin": admin})
    s.commit()
    s.refresh(usuario)
    return usuario


def listar(s: Session, ator: Optional[Ator] = None) -> List[Usuario]:
    """Com 'ator' (admin): só os usuários da organização dele. Sem 'ator': todos (uso interno)."""
    consulta = select(Usuario).order_by(Usuario.nome_completo)
    if ator is not None:
        consulta = consulta.where(Usuario.organizacao_id == exigir_admin(s, ator).organizacao_id)
    return list(s.exec(consulta).all())


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

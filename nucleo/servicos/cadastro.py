"""Cadastro de novos escritórios pelo site e recuperação de senha por e-mail.

- Cadastro: cria a organização em teste (30 dias) e o administrador, com o aceite dos Termos.
- Confirmação de e-mail: link válido por 48 horas.
- Recuperação de senha: link válido por 30 minutos e de uso único. O token guarda um pedaço
  do hash da senha atual; ao trocar a senha, o hash muda e o link antigo deixa de valer.
- Pedido de recuperação responde sempre igual, para não revelar quais e-mails têm conta.
"""
import datetime
import logging
import os
import re

from sqlmodel import Session, select

from nucleo import email as correio
from nucleo.planos import DIAS_TESTE, PLANO_TESTE, STATUS_TESTE, agora_utc
from nucleo.senhas import hash_senha, validar_nova_senha
from nucleo.servicos import organizacoes
from nucleo.servicos.usuarios import buscar_por_username, novo_usuario
from nucleo.tabelas import Usuario
from seguranca import assinar_token, segredo_do_servidor, verificar_token

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
VALIDADE_CONFIRMACAO_S = 48 * 3600
VALIDADE_REDEFINICAO_S = 30 * 60
MENSAGEM_LINK_INVALIDO = "Este link expirou ou já foi usado. Peça um novo na tela de entrada."

log = logging.getLogger(__name__)


def _url_publica() -> str:
    return (os.getenv("MEMORIA_URL_PUBLICA") or "https://www.decidiu.app").rstrip("/")


def _email_valido(email: str) -> str:
    email = (email or "").strip().lower()
    if not EMAIL_RE.match(email):
        raise ValueError("Informe um e-mail válido.")
    return email


def _email_em_uso(s: Session, email: str) -> bool:
    return buscar_por_username(s, email) is not None or s.exec(
        select(Usuario.id).where(Usuario.email == email)
    ).first() is not None


def enviar_confirmacao(usuario: Usuario) -> bool:
    token = assinar_token(segredo_do_servidor(), {"a": "confirmar", "u": usuario.id},
                          validade_s=VALIDADE_CONFIRMACAO_S)
    link = f"{_url_publica()}/login?confirmar={token}"
    html = (f"<p>Olá, {usuario.nome_completo}!</p>"
            f"<p>Confirme seu e-mail para ativar sua conta no Decidiu:</p>"
            f"<p><a href=\"{link}\">Confirmar meu e-mail</a></p>"
            f"<p>O link vale por 48 horas.</p>")
    return correio.enviar(usuario.email, "Confirme seu e-mail - Decidiu", html)


def cadastrar(s: Session, nome_escritorio: str, nome_completo: str, email: str, senha: str,
              aceitou_termos: bool) -> Usuario:
    """Cria o escritório em teste e o administrador. Lança ValueError com a mensagem para a tela."""
    if not aceitou_termos:
        raise ValueError("Para criar a conta, aceite os Termos de Serviço.")
    nome_escritorio = (nome_escritorio or "").strip()
    if not nome_escritorio:
        raise ValueError("Informe o nome do escritório.")
    email = _email_valido(email)
    if _email_em_uso(s, email):
        raise ValueError("Já existe uma conta com este e-mail. Use Entrar ou recupere a senha.")
    validar_nova_senha(senha)

    agora = agora_utc()
    org = organizacoes.nova_organizacao(s, nome_escritorio)
    org.plano = PLANO_TESTE
    org.assinatura_status = STATUS_TESTE
    org.teste_fim = agora + datetime.timedelta(days=DIAS_TESTE)
    s.add(org)
    # O e-mail é o login: a pessoa entra com o mesmo endereço em que recebe as mensagens.
    usuario = novo_usuario(s, email, senha, nome_completo, org.id, admin=True, pode_criar_projetos=True)
    usuario.email = email
    usuario.termos_aceitos_em = agora
    s.add(usuario)
    s.commit()
    s.refresh(usuario)
    try:
        enviar_confirmacao(usuario)
    except Exception:  # o cadastro vale mesmo se o e-mail falhar; o erro já foi para o log
        log.exception("Falha ao enviar confirmação de e-mail")
    return usuario


def confirmar_email(s: Session, token: str) -> Usuario:
    dados = verificar_token(segredo_do_servidor(), token or "")
    if not dados or dados.get("a") != "confirmar":
        raise ValueError("Este link de confirmação expirou. Entre e peça um novo.")
    usuario = s.get(Usuario, dados.get("u"))
    if usuario is None:
        raise ValueError("Este link de confirmação expirou. Entre e peça um novo.")
    usuario.email_verificado = True
    s.add(usuario)
    s.commit()
    s.refresh(usuario)
    return usuario


def esqueci_senha(s: Session, email: str) -> None:
    """Envia o link de recuperação se o e-mail existir. Não diz nada ao chamador."""
    email = (email or "").strip().lower()
    usuario = s.exec(select(Usuario).where(Usuario.email == email)).first() if email else None
    if usuario is None:
        return
    token = assinar_token(segredo_do_servidor(),
                          {"a": "redefinir", "u": usuario.id, "h": usuario.senha[-16:]},
                          validade_s=VALIDADE_REDEFINICAO_S)
    link = f"{_url_publica()}/login?token={token}"
    html = (f"<p>Olá, {usuario.nome_completo}!</p>"
            f"<p>Recebemos um pedido para redefinir a senha da sua conta no Decidiu.</p>"
            f"<p><a href=\"{link}\">Criar nova senha</a></p>"
            f"<p>O link vale por 30 minutos e só pode ser usado uma vez. "
            f"Se não foi você, ignore este e-mail.</p>")
    correio.enviar(usuario.email, "Redefinição de senha - Decidiu", html)


def redefinir_com_token(s: Session, token: str, nova_senha: str) -> Usuario:
    dados = verificar_token(segredo_do_servidor(), token or "")
    if not dados or dados.get("a") != "redefinir":
        raise ValueError(MENSAGEM_LINK_INVALIDO)
    usuario = s.get(Usuario, dados.get("u"))
    if usuario is None or usuario.senha[-16:] != dados.get("h"):  # já usado ou senha trocada
        raise ValueError(MENSAGEM_LINK_INVALIDO)
    validar_nova_senha(nova_senha)
    usuario.senha = hash_senha(nova_senha)
    usuario.email_verificado = True  # quem recebeu o link provou que controla o e-mail
    s.add(usuario)
    s.commit()
    s.refresh(usuario)
    return usuario

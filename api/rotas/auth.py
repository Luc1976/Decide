import math

from fastapi import APIRouter, HTTPException, status

from api.autenticacao import LIMITADOR_LOGIN, emitir_token
from api.deps import AtorAtual, Sessao
from api.esquemas.auth import LoginEntrada, TemaEntrada, TokenSaida, TrocaSenhaEntrada, UsuarioSaida
from nucleo.servicos import usuarios
from nucleo.tabelas import Usuario

rotas = APIRouter(prefix="/auth", tags=["Autenticação"])


@rotas.post("/login", response_model=TokenSaida, summary="Entrar (devolve o token de acesso)")
def login(dados: LoginEntrada, s: Sessao):
    chave = dados.username.strip().lower()
    espera = LIMITADOR_LOGIN.bloqueado(chave)
    if espera:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS,
                            f"Muitas tentativas. Tente novamente em {math.ceil(espera / 60)} min.")
    usuario = usuarios.autenticar(s, dados.username, dados.senha)
    if usuario is None:
        LIMITADOR_LOGIN.falhou(chave)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Usuário ou senha incorretos.")
    LIMITADOR_LOGIN.sucesso(chave)
    token, expira = emitir_token(usuario.id)
    return TokenSaida(access_token=token, expira_em=expira, usuario=UsuarioSaida.model_validate(usuario))


@rotas.get("/eu", response_model=UsuarioSaida, summary="Usuário logado")
def eu(ator: AtorAtual, s: Sessao):
    return s.get(Usuario, ator.id)


@rotas.post("/senha", status_code=204, summary="Trocar a própria senha")
def trocar_senha(dados: TrocaSenhaEntrada, ator: AtorAtual, s: Sessao):
    usuarios.alterar_propria_senha(s, ator, dados.senha_atual, dados.nova_senha)


@rotas.put("/tema", response_model=UsuarioSaida, summary="Modo claro ou escuro (preferência do usuário)")
def definir_tema(dados: TemaEntrada, ator: AtorAtual, s: Sessao):
    return usuarios.definir_tema(s, ator, dados.tema)

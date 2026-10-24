import asyncio
import logging
import math
from urllib.parse import parse_qsl

import flet as ft

import tema

from database import autenticar_usuario, definir_tema, init_db, listar_projetos_do_usuario, pode_no_projeto
from nucleo.db import nova_sessao
from nucleo.servicos import cadastro
from views.atas import build_atas_view
from views.documentos import build_documentos_view
from views.ficha import build_ficha_view
from views.login import build_login_view
from views.pendencias import build_pendencias_view
from views.plataforma import build_plataforma_view
from views.sem_projeto import build_sem_projeto_view
from views.timeline import build_timeline_view
from seguranca import LimitadorTentativas

# Compartilhado entre todas as sessões: 5 senhas erradas bloqueiam o usuário por 15 min.
LIMITADOR_LOGIN = LimitadorTentativas(maximo=5, janela_s=900, bloqueio_s=900)
log = logging.getLogger(__name__)


def _confirmar_email_link(token):
    try:
        with nova_sessao() as s:
            cadastro.confirmar_email(s, token)
        return "E-mail confirmado. Agora é só entrar."
    except ValueError as erro:
        return str(erro)


async def cadastrar_conta(nome_escritorio, nome_completo, email, senha, aceitou):
    def fazer():
        with nova_sessao() as s:
            cadastro.cadastrar(s, nome_escritorio, nome_completo, email, senha, aceitou)
    try:
        await asyncio.to_thread(fazer)  # envia e-mail: não trava a tela
        return None
    except ValueError as erro:
        return str(erro)
    except Exception:  # erro inesperado: vai para o log completo (Deploy Logs)
        log.exception("Falha ao criar conta")
        return ("Não foi possível criar a conta agora. Tente de novo em instantes; "
                "se continuar, fale com o suporte.")


async def pedir_redefinicao(email):
    def fazer():
        with nova_sessao() as s:
            cadastro.esqueci_senha(s, email)
    try:
        await asyncio.to_thread(fazer)
    except Exception:  # a resposta na tela é a mesma, mesmo com falha
        log.exception("Falha ao pedir redefinição de senha")
    return None


async def redefinir_senha_link(token, senha):
    def fazer():
        with nova_sessao() as s:
            cadastro.redefinir_com_token(s, token, senha)
    try:
        await asyncio.to_thread(fazer)
        return None
    except ValueError as erro:
        return str(erro)


def main(page: ft.Page):
    page.title = "Ru.A Estudio - Memória de Projetos"
    tema.configurar(page)  # temas claro e escuro; começa no escuro até o login
    page.padding = 20

    init_db()
    usuario_logado = None
    projeto_ativo = None  # definido no login, entre os projetos que o usuário pode ver
    ata_para_abrir = None  # id da ata que a tela de atas deve abrir ao montar

    def mostrar_view(view: ft.View):
        """Troca a view atual. A view já chega pronta (construída ANTES do clear),
        então page.views nunca fica vazia durante a construção."""
        page.views.clear()
        page.views.append(view)
        page.update()

    def montar_timeline():
        mostrar_view(
            build_timeline_view(
                page,
                projeto_ativo,
                usuario_logado,
                sair,
                projeto_criado,
                projeto_selecionado,
                abrir_atas,
                abrir_ficha,
                projeto_excluido,
                abrir_pendencias,
                abrir_plataforma,
                trocar_tema,
            )
        )

    def trocar_tema():
        """Alterna claro/escuro, guarda a escolha do usuário e redesenha a tela atual."""
        novo = tema.oposto(tema.modo_atual(page))
        tema.aplicar_modo(page, novo)
        if usuario_logado is not None:
            usuario_logado.tema = novo
            try:
                definir_tema(usuario_logado.id, novo)
            except Exception as erro:  # a preferência é conveniência: nunca derruba a tela
                print(f"[memoria] Não foi possível guardar o tema: {erro}", flush=True)
        route_change(None)

    def montar_plataforma():
        mostrar_view(build_plataforma_view(page, usuario_logado, sair, voltar_timeline))

    def montar_pendencias():
        mostrar_view(
            build_pendencias_view(
                page,
                projeto_ativo,
                usuario_logado,
                sair,
                voltar_timeline,
                abrir_atas,
            )
        )

    def montar_ficha():
        mostrar_view(
            build_ficha_view(
                page,
                projeto_ativo,
                usuario_logado,
                sair,
                voltar_timeline,
                abrir_documentos,
            )
        )

    def montar_documentos():
        mostrar_view(build_documentos_view(page, projeto_ativo, usuario_logado, sair, abrir_ficha))

    def montar_atas():
        nonlocal ata_para_abrir
        view, ao_montar = build_atas_view(
            page,
            projeto_ativo,
            usuario_logado,
            sair,
            voltar_timeline,
            ata_para_abrir,
        )
        ata_para_abrir = None
        mostrar_view(view)
        ao_montar()  # só agora a view está na página e pode abrir diálogos

    async def fazer_login(username, senha, mensagem_erro):
        nonlocal usuario_logado, projeto_ativo
        chave = (username or "").strip().lower()
        espera = LIMITADOR_LOGIN.bloqueado(chave)
        if espera:
            mensagem_erro.value = (
                f"Muitas tentativas. Tente novamente em {math.ceil(espera / 60)} min."
            )
            page.update()
            return
        try:
            usuario = autenticar_usuario(username, senha)
        except PermissionError as erro:  # senha certa, mas assinatura/organização bloqueada
            mensagem_erro.value = str(erro)
            page.update()
            return
        if usuario:
            LIMITADOR_LOGIN.sucesso(chave)
            usuario_logado = usuario
            tema.aplicar_modo(page, usuario.tema)  # modo escolhido por ele (padrão: escuro)
            projetos = listar_projetos_do_usuario(usuario.id)
            projeto_ativo = projetos[0] if projetos else None
            await page.push_route("/timeline")
        else:
            LIMITADOR_LOGIN.falhou(chave)
            mensagem_erro.value = "Usuário ou senha incorretos."
            page.update()

    async def sair(_):
        nonlocal usuario_logado, projeto_ativo
        usuario_logado = None
        projeto_ativo = None
        await page.push_route("/login")

    def garantir_projeto_valido() -> bool:
        """O projeto ativo precisa ser um que o usuário ainda pode ver (o acesso pode
        ter sido retirado com a sessão aberta). Sem nenhum projeto, mostra a tela vazia."""
        nonlocal projeto_ativo
        if projeto_ativo is not None and not pode_no_projeto(
            usuario_logado.id, projeto_ativo.id, "Leitor"
        ):
            projeto_ativo = None
        if projeto_ativo is None:
            projetos = listar_projetos_do_usuario(usuario_logado.id)
            projeto_ativo = projetos[0] if projetos else None
        return projeto_ativo is not None

    async def abrir_atas(ata_id=None):
        nonlocal ata_para_abrir
        ata_para_abrir = ata_id
        await page.push_route("/atas")

    async def abrir_ficha(_=None):
        await page.push_route("/ficha")

    async def abrir_pendencias(_=None):
        await page.push_route("/pendencias")

    async def abrir_documentos(_=None):
        await page.push_route("/documentos")

    async def abrir_plataforma(_=None):
        await page.push_route("/plataforma")

    async def voltar_timeline(_=None):
        await page.push_route("/timeline")

    def projeto_criado(novo_projeto):
        nonlocal projeto_ativo
        projeto_ativo = novo_projeto
        montar_timeline()

    def projeto_excluido():
        """Depois de apagar o projeto ativo: vai para outro projeto do usuário ou para a
        tela de 'nenhum projeto'."""
        nonlocal projeto_ativo
        projeto_ativo = None
        if garantir_projeto_valido():
            montar_timeline()
        else:
            mostrar_view(
                build_sem_projeto_view(page, usuario_logado, sair, projeto_criado)
            )

    def projeto_selecionado(projeto):
        # Só memoriza; a própria view já atualiza a tela sem reconstruir.
        nonlocal projeto_ativo
        projeto_ativo = projeto

    def route_change(_):
        caminho, _, consulta = (page.route or "/login").partition("?")
        params = dict(parse_qsl(consulta))
        if usuario_logado is None:
            if caminho != "/login":
                asyncio.create_task(page.push_route("/login"))
                return
            aviso = _confirmar_email_link(params["confirmar"]) if params.get("confirmar") else None
            mostrar_view(build_login_view(
                fazer_login, page,
                on_cadastro=cadastrar_conta,
                on_esqueci=pedir_redefinicao,
                on_redefinir=redefinir_senha_link,
                token_redefinir=params.get("token"),
                aviso=aviso,
            ))
        elif page.route == "/plataforma":
            montar_plataforma()  # não depende de projeto; a própria tela confere o superadmin
        elif not garantir_projeto_valido():
            mostrar_view(
                build_sem_projeto_view(page, usuario_logado, sair, projeto_criado)
            )
        elif page.route == "/timeline":
            montar_timeline()
        elif page.route == "/atas":
            montar_atas()
        elif page.route == "/ficha":
            montar_ficha()
        elif page.route == "/pendencias":
            montar_pendencias()
        elif page.route == "/documentos":
            montar_documentos()
        else:
            asyncio.create_task(page.push_route("/timeline"))

    page.on_route_change = route_change
    route_change(None)

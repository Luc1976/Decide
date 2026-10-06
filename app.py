import asyncio
import math

import flet as ft

from database import autenticar_usuario, init_db, listar_projetos_do_usuario, pode_no_projeto
from views.atas import build_atas_view
from views.ficha import build_ficha_view
from views.login import build_login_view
from views.sem_projeto import build_sem_projeto_view
from views.timeline import build_timeline_view
from seguranca import LimitadorTentativas

# Compartilhado entre todas as sessões: 5 senhas erradas bloqueiam o usuário por 15 min.
LIMITADOR_LOGIN = LimitadorTentativas(maximo=5, janela_s=900, bloqueio_s=900)


def main(page: ft.Page):
    page.title = "Ru.A Estudio - Memória de Projetos"
    page.theme_mode = ft.ThemeMode.DARK
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
            )
        )

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
        usuario = autenticar_usuario(username, senha)
        if usuario:
            LIMITADOR_LOGIN.sucesso(chave)
            usuario_logado = usuario
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
        if usuario_logado is None:
            if page.route != "/login":
                asyncio.create_task(page.push_route("/login"))
                return
            mostrar_view(build_login_view(fazer_login, page))
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
        else:
            asyncio.create_task(page.push_route("/timeline"))

    page.on_route_change = route_change
    route_change(None)

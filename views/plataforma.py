"""Tela da plataforma: organizações (escritórios assinantes). Só para o superadmin.

- Nova organização, já com o primeiro administrador (que depois cadastra a equipe dele).
- Lista com situação, quantidade de usuários e projetos (só contagens: o conteúdo dos
  projetos de cada escritório continua invisível para a plataforma).
- Suspender (ninguém da organização entra; os dados ficam guardados) e reativar.

As regras ficam em nucleo/servicos/organizacoes.py (as mesmas da API); a tela só chama.
"""
import datetime

import flet as ft

from database import criar_organizacao, definir_organizacao_ativa, listar_organizacoes_plataforma
from layout import col, largura_dialogo, opcoes_dialogo, rotulo
from nucleo.marcacoes import normalizar

TODAS, ATIVAS, SUSPENSAS = "Todas", "Ativas", "Suspensas"


def _data_local(momento: datetime.datetime) -> str:
    if momento.tzinfo is None:  # o SQLite devolve datas sem fuso (gravadas em UTC)
        momento = momento.replace(tzinfo=datetime.timezone.utc)
    return momento.astimezone().strftime("%d/%m/%Y")


def _plural(n: int, singular: str, plural: str) -> str:
    return f"{n} {singular if n == 1 else plural}"


def build_plataforma_view(page, usuario, on_logout, on_voltar):
    if not getattr(usuario, "superadmin", False):
        return ft.View(
            route="/plataforma",
            controls=[
                ft.Container(
                    padding=20,
                    content=ft.Column([
                        ft.Text("Acesso restrito", size=22, weight=ft.FontWeight.BOLD),
                        ft.Text("Esta tela é só para o administrador da plataforma.", color=ft.Colors.GREY_400),
                        ft.Button(content="Voltar", icon=ft.Icons.ARROW_BACK, on_click=on_voltar),
                    ]),
                )
            ],
        )

    resumo = ft.Text("", size=13, color=ft.Colors.GREY_400)
    mensagem_lista = ft.Text("", size=12, color=ft.Colors.RED_400)
    campo_busca = ft.TextField(
        label="Buscar organização",
        hint_text="Nome ou identificador",
        prefix_icon=ft.Icons.SEARCH,
        col=col(12, md=8),
        on_change=lambda _: carregar(),
    )
    filtro = ft.Dropdown(
        label="Situação",
        col=col(12, md=4),
        value=TODAS,
        options=[ft.DropdownOption(key=o, text=o) for o in (TODAS, ATIVAS, SUSPENSAS)],
        on_select=lambda _: carregar(),
    )
    lista = ft.ListView(expand=True, spacing=12, padding=10)

    # ---------------------------------------------------------------- nova organização
    input_nome = ft.TextField(label="Nome do escritório", hint_text="Ex.: Studio Beta Arquitetura")
    input_admin_nome = ft.TextField(label="Nome do administrador")
    input_admin_usuario = ft.TextField(label="Usuário (login)", hint_text="Sem espaços. Ex.: joana.beta")
    input_senha = ft.TextField(label="Senha inicial", password=True, can_reveal_password=True)
    input_senha2 = ft.TextField(label="Repita a senha", password=True, can_reveal_password=True)
    mensagem_form = ft.Text("", size=12, color=ft.Colors.RED_400)

    def abrir_nova(_=None):
        for campo in (input_nome, input_admin_nome, input_admin_usuario, input_senha, input_senha2):
            campo.value = ""
        mensagem_form.value = ""
        page.show_dialog(modal_nova)

    def salvar_nova(_):
        if (input_senha.value or "") != (input_senha2.value or ""):
            mensagem_form.value = "As senhas não conferem."
            page.update()
            return
        try:
            org = criar_organizacao(
                usuario.id,
                input_nome.value,
                input_admin_usuario.value,
                input_admin_nome.value,
                input_senha.value,
            )
        except (ValueError, PermissionError) as erro:
            mensagem_form.value = str(erro)
            page.update()
            return
        login = (input_admin_usuario.value or "").strip().lower()
        page.pop_dialog()
        texto_criada.value = (
            f"A organização “{org.nome}” foi criada.\n\n"
            f"Envie ao administrador:\n"
            f"• o endereço do Decidiu;\n"
            f"• o usuário: {login};\n"
            f"• a senha que você definiu (por um canal separado, como telefone).\n\n"
            f"No primeiro acesso, peça que ele troque a senha em “Minha conta” e cadastre a "
            f"equipe em “Usuários”."
        )
        page.show_dialog(modal_criada)
        carregar()

    modal_nova = ft.AlertDialog(
        **opcoes_dialogo(page),
        title=ft.Text("Nova organização"),
        content=ft.Container(
            width=largura_dialogo(page, 520),
            content=ft.Column(
                tight=True,
                scroll=ft.ScrollMode.AUTO,
                controls=[
                    input_nome,
                    ft.Text("Primeiro administrador", weight=ft.FontWeight.BOLD),
                    ft.Text(
                        "Ele cadastra a própria equipe e os clientes do escritório.",
                        size=12, color=ft.Colors.GREY_400,
                    ),
                    input_admin_nome,
                    input_admin_usuario,
                    ft.ResponsiveRow([
                        ft.Container(input_senha, col=col(12, md=6)),
                        ft.Container(input_senha2, col=col(12, md=6)),
                    ]),
                    mensagem_form,
                ],
            ),
        ),
        actions=[
            ft.TextButton(content="Cancelar", on_click=lambda _: page.pop_dialog()),
            ft.Button(content="Criar organização", icon=ft.Icons.ADD_BUSINESS, on_click=salvar_nova),
        ],
    )

    texto_criada = ft.Text("")
    modal_criada = ft.AlertDialog(
        **opcoes_dialogo(page),
        title=ft.Text("Organização criada"),
        content=ft.Container(width=largura_dialogo(page, 480), content=texto_criada),
        actions=[ft.Button(content="Entendi", on_click=lambda _: page.pop_dialog())],
    )

    # ---------------------------------------------------------------- suspender / reativar
    alvo = {"org": None}
    texto_suspender = ft.Text("")
    mensagem_suspender = ft.Text("", size=12, color=ft.Colors.RED_400)

    def mudar_situacao(org, ativa: bool) -> bool:
        try:
            definir_organizacao_ativa(usuario.id, org.id, ativa)
        except (ValueError, PermissionError) as erro:
            mensagem_lista.value = str(erro)
            return False
        mensagem_lista.value = ""
        return True

    def pedir_suspensao(org):
        alvo["org"] = org
        texto_suspender.value = (
            f"Suspender “{org.nome}”?\n\n"
            "Ninguém dessa organização conseguirá entrar, e quem estiver com o app aberto perde o "
            "acesso na hora. Os projetos e os dados ficam guardados, e você pode reativar quando quiser."
        )
        mensagem_suspender.value = ""
        page.show_dialog(modal_suspender)

    def confirmar_suspensao(_):
        org = alvo["org"]
        if org is None:
            return
        if not mudar_situacao(org, False):
            mensagem_suspender.value = mensagem_lista.value
            mensagem_lista.value = ""
            page.update()
            return
        page.pop_dialog()
        carregar()

    def reativar(org):
        mudar_situacao(org, True)
        carregar()

    modal_suspender = ft.AlertDialog(
        **opcoes_dialogo(page),
        title=ft.Text("Suspender organização"),
        content=ft.Container(
            width=largura_dialogo(page, 480),
            content=ft.Column(tight=True, controls=[texto_suspender, mensagem_suspender]),
        ),
        actions=[
            ft.TextButton(content="Cancelar", on_click=lambda _: page.pop_dialog()),
            ft.Button(
                content="Suspender",
                icon=ft.Icons.BLOCK,
                bgcolor=ft.Colors.RED_700,
                color=ft.Colors.WHITE,
                on_click=confirmar_suspensao,
            ),
        ],
    )

    # ---------------------------------------------------------------- lista
    def card(resumo_org, minha: bool):
        org = resumo_org.organizacao
        situacao = ft.Chip(
            label=ft.Text("Ativa" if org.ativa else "Suspensa"),
            color=ft.Colors.GREEN_700 if org.ativa else ft.Colors.RED_700,
        )
        titulo = [situacao, ft.Text(org.nome, size=16, weight=ft.FontWeight.BOLD)]
        if minha:
            titulo.append(ft.Text("(a sua)", size=13, color=ft.Colors.BLUE_200))

        if minha:
            acao = ft.Text("A sua organização não pode ser suspensa.", size=11, color=ft.Colors.GREY_500)
        elif org.ativa:
            acao = ft.TextButton(
                content="Suspender",
                icon=ft.Icons.BLOCK,
                style=ft.ButtonStyle(color=ft.Colors.RED_400),
                on_click=lambda _, o=org: pedir_suspensao(o),
            )
        else:
            acao = ft.Button(content="Reativar", icon=ft.Icons.CHECK_CIRCLE, on_click=lambda _, o=org: reativar(o))

        return ft.Container(
            padding=15,
            border_radius=10,
            bgcolor=ft.Colors.SURFACE,
            border=ft.Border.all(1, ft.Colors.GREEN_900 if org.ativa else ft.Colors.RED_900),
            content=ft.Column(
                spacing=6,
                controls=[
                    ft.Row(wrap=True, controls=titulo),
                    ft.Row(
                        wrap=True,
                        spacing=18,
                        controls=[
                            ft.Text(_plural(resumo_org.usuarios, "usuário", "usuários"), size=13),
                            ft.Text(_plural(resumo_org.projetos, "projeto", "projetos"), size=13),
                            ft.Text(f"Desde {_data_local(org.data_criacao)}", size=13, color=ft.Colors.GREY_400),
                            ft.Text(f"Identificador: {org.slug}", size=12, color=ft.Colors.GREY_500),
                        ],
                    ),
                    ft.Row(alignment=ft.MainAxisAlignment.END, controls=[acao]),
                ],
            ),
        )

    def carregar():
        try:
            todas = listar_organizacoes_plataforma(usuario.id)
        except PermissionError as erro:
            lista.controls = [ft.Text(str(erro), color=ft.Colors.RED_400)]
            page.update()
            return
        ativas = [r for r in todas if r.organizacao.ativa]
        resumo.value = (
            f"{_plural(len(todas), 'organização', 'organizações')} · {len(ativas)} ativa(s) · "
            f"{_plural(sum(r.usuarios for r in todas), 'usuário', 'usuários')} · "
            f"{_plural(sum(r.projetos for r in todas), 'projeto', 'projetos')}"
        )
        termo = normalizar(campo_busca.value or "")
        visiveis = [
            r for r in todas
            if (not termo or termo in normalizar(f"{r.organizacao.nome} {r.organizacao.slug}"))
            and (filtro.value != ATIVAS or r.organizacao.ativa)
            and (filtro.value != SUSPENSAS or not r.organizacao.ativa)
        ]
        lista.controls = [card(r, r.organizacao.id == usuario.organizacao_id) for r in visiveis]
        if not visiveis:
            lista.controls = [ft.Text("Nenhuma organização encontrada.", color=ft.Colors.GREY_400)]
        page.update()

    header = ft.Container(
        padding=15,
        bgcolor=ft.Colors.SURFACE,
        border_radius=10,
        content=ft.ResponsiveRow(
            controls=[
                ft.Column(
                    col=col(12, md=5),
                    controls=[
                        ft.Text("Plataforma", size=22, weight=ft.FontWeight.BOLD),
                        ft.Text("Organizações (escritórios assinantes)", size=14, color=ft.Colors.BLUE_200),
                        resumo,
                    ],
                ),
                ft.Row(
                    col=col(12, md=7),
                    wrap=True,
                    alignment=ft.MainAxisAlignment.END,
                    controls=[
                        ft.Button(content="Linha do tempo", icon=ft.Icons.TIMELINE, on_click=on_voltar),
                        ft.Button(
                            content=rotulo(page, "+ Nova Organização", "+ Organização"),
                            icon=ft.Icons.ADD_BUSINESS,
                            on_click=abrir_nova,
                        ),
                        ft.IconButton(icon=ft.Icons.LOGOUT, tooltip="Sair", on_click=on_logout),
                    ],
                ),
            ],
        ),
    )

    carregar()
    return ft.View(
        route="/plataforma",
        controls=[
            header,
            ft.ResponsiveRow([campo_busca, filtro]),
            mensagem_lista,
            ft.Divider(),
            lista,
        ],
    )

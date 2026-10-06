import flet as ft
from database import criar_projeto
from layout import largura_campo


def build_sem_projeto_view(page, usuario, on_logout, on_project_created):
    """Tela para quem ainda não tem acesso a nenhum projeto."""
    pode_criar = bool(usuario.admin or getattr(usuario, "pode_criar_projetos", False))
    mensagem = ft.Text("", color=ft.Colors.RED_400, size=12)
    input_nome = ft.TextField(label="Nome do projeto", width=largura_campo(page, 400))
    input_cliente = ft.TextField(label="Cliente", width=largura_campo(page, 400))
    input_descricao = ft.TextField(
        label="Descrição (opcional)", multiline=True, min_lines=2, width=largura_campo(page, 400)
    )

    def criar(_):
        try:
            novo = criar_projeto(
                input_nome.value, input_cliente.value, input_descricao.value, criador_id=usuario.id
            )
        except (ValueError, PermissionError) as erro:
            mensagem.value = str(erro)
            page.update()
            return
        on_project_created(novo)

    if pode_criar:
        corpo = [
            ft.Text("Você ainda não tem projetos.", size=18, weight=ft.FontWeight.BOLD),
            ft.Text("Crie o primeiro para começar a registrar decisões.", color=ft.Colors.GREY_400),
            input_nome,
            input_cliente,
            input_descricao,
            mensagem,
            ft.Button(content="Criar projeto", icon=ft.Icons.ADD, on_click=criar),
        ]
    else:
        corpo = [
            ft.Text("Nenhum projeto disponível.", size=18, weight=ft.FontWeight.BOLD),
            ft.Text(
                "Peça ao responsável pelo projeto para incluir o seu usuário.",
                color=ft.Colors.GREY_400,
            ),
        ]

    return ft.View(
        route="/timeline",
        controls=[
            ft.Container(
                padding=15,
                content=ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Text("Memória de Projetos", size=22, weight=ft.FontWeight.BOLD),
                        ft.IconButton(icon=ft.Icons.LOGOUT, tooltip="Sair", on_click=on_logout),
                    ],
                ),
            ),
            ft.Container(padding=20, content=ft.Column(controls=corpo, spacing=12)),
        ],
    )

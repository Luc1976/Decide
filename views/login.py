import flet as ft
from layout import compacto, largura_campo


def build_login_view(on_login, page=None):
    # No celular o cartão ocupa a tela toda (menos margens); no computador mantém 400 px.
    largura_cartao = largura_campo(page, 400) if page is not None else 400
    espaco = 20 if (page is not None and compacto(page)) else 40
    largura_interna = largura_cartao - 2 * espaco
    input_user = ft.TextField(
        label="Usuário", width=largura_interna, prefix_icon=ft.Icons.PERSON
    )
    input_senha = ft.TextField(
        label="Senha",
        width=largura_interna,
        password=True,
        can_reveal_password=True,
        prefix_icon=ft.Icons.LOCK,
    )
    msg_erro = ft.Text("", color=ft.Colors.RED_400, size=12)

    async def fazer_login(_):
        await on_login(input_user.value, input_senha.value, msg_erro)

    return ft.View(
        route="/login",
        controls=[
            ft.Container(
                expand=True,
                alignment=ft.Alignment.CENTER,
                content=ft.Card(
                    elevation=10,
                    content=ft.Container(
                        padding=espaco,
                        width=largura_cartao,
                        content=ft.Column(
                            tight=True,
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            spacing=20,
                            controls=[
                                ft.Icon(
                                    ft.Icons.ARCHITECTURE,
                                    size=60,
                                    color=ft.Colors.BLUE_400,
                                ),
                                ft.Text(
                                    "Ru.A Estudio",
                                    size=24,
                                    weight=ft.FontWeight.BOLD,
                                ),
                                ft.Text(
                                    "Gestão de Decisões de Projetos",
                                    size=14,
                                    color=ft.Colors.GREY_400,
                                ),
                                ft.Divider(),
                                input_user,
                                input_senha,
                                msg_erro,
                                ft.Button(
                                    content="Entrar",
                                    width=largura_interna,
                                    on_click=fazer_login,
                                ),
                            ],
                        ),
                    ),
                ),
            )
        ],
    )

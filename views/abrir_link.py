"""Abre um anexo no navegador sem depender de page.launch_url (removido no Flet atual).

O link vai dentro de um diálogo, como ft.TextSpan com url: é o mesmo mecanismo que o app
já usa no link de pagamento e funciona em qualquer navegador. Não há abertura automática
porque o navegador só deixa abrir uma aba por clique do usuário."""
import flet as ft


def mostrar_link(page, caminho: str, titulo: str = "Abrir arquivo") -> None:
    def fechar(_=None):
        page.pop_dialog()

    dialogo = ft.AlertDialog(
        title=ft.Text(titulo),
        content=ft.Column(
            [
                ft.Text(
                    spans=[ft.TextSpan(text="Clique aqui para abrir o arquivo", url=caminho)],
                    size=14,
                ),
                ft.Text(
                    "O link vale por alguns minutos. Se não abrir, feche e tente de novo.",
                    size=12,
                    color=ft.Colors.ON_SURFACE_VARIANT,
                ),
            ],
            tight=True,
        ),
        actions=[ft.TextButton(content="Fechar", on_click=fechar)],
    )
    page.show_dialog(dialogo)

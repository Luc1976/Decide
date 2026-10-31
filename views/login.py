import asyncio

import flet as ft
from marca import marca_login

from layout import compacto, largura_campo
from nucleo.legal import url_termos
from views import lembrar_usuario
from views.planos import texto_termos


def build_login_view(on_login, page=None, on_cadastro=None, on_esqueci=None, on_redefinir=None,
                     token_redefinir=None, aviso=None):
    """Tela de entrada com quatro modos: entrar, criar conta, esqueci a senha e nova senha.

    on_cadastro(nome_escritorio, nome_completo, email, senha, aceitou) -> erro (str) ou None.
    on_esqueci(email) -> None (a resposta é sempre a mesma).
    on_redefinir(token, nova_senha) -> erro (str) ou None.
    """
    # No celular o cartão ocupa a tela toda (menos margens); no computador mantém 400 px.
    largura_cartao = largura_campo(page, 400) if page is not None else 400
    espaco = 20 if (page is not None and compacto(page)) else 40
    largura = largura_cartao - 2 * espaco

    msg = ft.Text("", color=ft.Colors.ERROR, size=12)
    aviso_txt = ft.Text(aviso or "", color=ft.Colors.PRIMARY, size=12)

    def atualizar():
        if page is not None:
            page.update()

    # ---------------- entrar
    input_user = ft.TextField(label="Usuário ou e-mail", width=largura, prefix_icon=ft.Icons.PERSON)
    input_senha = ft.TextField(label="Senha", width=largura, password=True, can_reveal_password=True,
                               prefix_icon=ft.Icons.LOCK)

    lembrar = ft.Checkbox(label="Salvar meu usuário neste aparelho", value=False)

    async def preencher_usuario():
        """Traz o usuário guardado da última entrada, se o aparelho tiver um."""
        salvo = await lembrar_usuario.ler(page)
        if salvo and not input_user.value:
            input_user.value = salvo
            lembrar.value = True
            atualizar()

    async def fazer_login(_):
        usuario_digitado = (input_user.value or "").strip()
        await on_login(input_user.value, input_senha.value, msg)
        # só guarda quando a entrada deu certo (sem mensagem de erro)
        if page is not None and not msg.value:
            await lembrar_usuario.gravar(page, usuario_digitado if lembrar.value else "")

    async def ir_planos(_):
        if page is not None:
            await page.push_route("/planos")

    entrar = [
        input_user,
        input_senha,
        lembrar,
        # Botão de entrada em destaque: cinza claro com texto laranja em negrito
        ft.Button(
            content=ft.Text("Entrar", weight=ft.FontWeight.BOLD, size=16, color="#A83F00"),
            width=largura,
            style=ft.ButtonStyle(
                bgcolor="#E0E0E0",
                color="#A83F00",
                padding=ft.Padding.symmetric(vertical=14),
            ),
            on_click=fazer_login,
        ),
        ft.TextButton(content="Criar conta grátis (30 dias)", on_click=lambda _: mostrar("cadastro")),
        ft.TextButton(content="Esqueci minha senha", on_click=lambda _: mostrar("esqueci")),
        ft.TextButton(content="Ver planos e assinar", on_click=ir_planos),
        ft.TextButton(content="Ajuda", icon=ft.Icons.HELP_OUTLINE,
                      url=ft.Url("/ajuda", target=ft.UrlTarget.BLANK)),
    ]

    if page is not None:  # carrega o usuário guardado sem bloquear a tela
        try:
            asyncio.create_task(preencher_usuario())
        except RuntimeError:
            pass

    # ---------------- criar conta
    c_escritorio = ft.TextField(label="Nome do escritório", width=largura, prefix_icon=ft.Icons.BUSINESS)
    c_nome = ft.TextField(label="Seu nome completo", width=largura, prefix_icon=ft.Icons.PERSON)
    c_email = ft.TextField(label="E-mail (será seu login)", width=largura, prefix_icon=ft.Icons.MAIL)
    c_senha = ft.TextField(label="Senha (mínimo 6 caracteres)", width=largura, password=True,
                           can_reveal_password=True, prefix_icon=ft.Icons.LOCK)
    c_senha2 = ft.TextField(label="Confirme a senha", width=largura, password=True,
                            can_reveal_password=True, prefix_icon=ft.Icons.LOCK)
    c_termos = ft.Checkbox(label="Li e aceito os Termos de Serviço", value=False)

    async def criar_conta(_):
        if not all([c_escritorio.value, c_nome.value, c_email.value, c_senha.value]):
            msg.value = "Preencha todos os campos."
            return atualizar()
        if c_senha.value != c_senha2.value:
            msg.value = "As senhas não conferem."
            return atualizar()
        if not c_termos.value:
            msg.value = "Para criar a conta, aceite os Termos de Serviço."
            return atualizar()
        erro = await on_cadastro(c_escritorio.value, c_nome.value, c_email.value, c_senha.value, c_termos.value)
        if erro:
            msg.value = erro
            return atualizar()
        mostrar("entrar", "Conta criada! Enviamos um e-mail para confirmar seu endereço. "
                           "Você já pode entrar com o e-mail e a senha.")

    cadastro = [
        c_escritorio, c_nome, c_email, c_senha, c_senha2, c_termos,
        texto_termos(url_termos(), prefixo="Leia os "),
        ft.Button(content="Começar teste grátis de 30 dias", width=largura, on_click=criar_conta),
        ft.TextButton(content="Já tenho conta", on_click=lambda _: mostrar("entrar")),
    ]

    # ---------------- esqueci a senha
    r_email = ft.TextField(label="E-mail da sua conta", width=largura, prefix_icon=ft.Icons.MAIL)

    async def pedir_link(_):
        if not r_email.value:
            msg.value = "Informe o e-mail da conta."
            return atualizar()
        await on_esqueci(r_email.value)
        mostrar("entrar", "Se este e-mail estiver cadastrado, enviamos o link para criar uma nova senha. "
                           "Ele vale por 30 minutos.")

    esqueci = [
        r_email,
        ft.Button(content="Enviar link de recuperação", width=largura, on_click=pedir_link),
        ft.TextButton(content="Voltar para entrar", on_click=lambda _: mostrar("entrar")),
    ]

    # ---------------- nova senha (abre pelo link do e-mail)
    n_senha = ft.TextField(label="Nova senha (mínimo 6 caracteres)", width=largura, password=True,
                           can_reveal_password=True, prefix_icon=ft.Icons.LOCK)
    n_senha2 = ft.TextField(label="Confirme a nova senha", width=largura, password=True,
                            can_reveal_password=True, prefix_icon=ft.Icons.LOCK)

    async def salvar_senha(_):
        if not n_senha.value or n_senha.value != n_senha2.value:
            msg.value = "As senhas não conferem."
            return atualizar()
        erro = await on_redefinir(token_redefinir, n_senha.value)
        if erro:
            msg.value = erro
            return atualizar()
        mostrar("entrar", "Senha alterada. Entre com seu usuário e a nova senha.")

    nova = [
        n_senha, n_senha2,
        ft.Button(content="Salvar nova senha", width=largura, on_click=salvar_senha),
        ft.TextButton(content="Voltar para entrar", on_click=lambda _: mostrar("entrar")),
    ]

    modos = {"entrar": entrar, "cadastro": cadastro, "esqueci": esqueci, "nova": nova}
    corpo = ft.Column(tight=True, horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=14)

    def mostrar(modo: str, texto_aviso=None):
        corpo.controls = modos[modo]
        aviso_txt.value = texto_aviso or ""
        msg.value = ""
        atualizar()

    inicial = "nova" if token_redefinir and on_redefinir else "entrar"
    corpo.controls = modos[inicial]

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
                            scroll=ft.ScrollMode.AUTO,
                            controls=[
                                marca_login(),
                                ft.Divider(),
                                aviso_txt,
                                corpo,
                                msg,
                            ],
                        ),
                    ),
                ),
            )
        ],
    )

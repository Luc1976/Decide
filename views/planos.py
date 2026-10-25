"""Página de adesão aos planos: explica cada plano e as condições, e gera o link de pagamento
na página segura do Asaas. Acessível sem login (a conta pode estar bloqueada pelo vencimento)."""
import flet as ft

from layout import compacto, largura_campo
from marca import marca_login


def texto_termos(url: str, prefixo: str = "") -> ft.Control:
    """Texto com o link dos Termos de Serviço (ou aviso enquanto o link não existe)."""
    if url:
        return ft.Text(spans=[ft.TextSpan(text=prefixo + "Termos de Serviço", url=url)], size=13)
    return ft.Text(prefixo + "Termos de Serviço (disponíveis em breve)", size=13)


def _linha(texto: str) -> ft.Control:
    return ft.Text(f"• {texto}", size=13)


def build_planos_view(page, on_assinar, on_voltar, url_termos: str = "", vagas_fundador=None):
    """on_assinar(usuario, senha, plano, ciclo, cpf_cnpj) -> (link, erro).
    on_voltar() leva de volta à tela de entrada."""
    largura_pagina = largura_campo(page, 460) if page is not None else 460
    espaco = 16 if (page is not None and compacto(page)) else 24
    largura = largura_pagina - 2 * espaco

    usuario = ft.TextField(label="Usuário ou e-mail do administrador", width=largura,
                           prefix_icon=ft.Icons.PERSON)
    senha = ft.TextField(label="Senha", width=largura, password=True, can_reveal_password=True,
                         prefix_icon=ft.Icons.LOCK)
    cpf = ft.TextField(label="CPF ou CNPJ do responsável pela assinatura", width=largura,
                       prefix_icon=ft.Icons.DESCRIPTION)
    aceite = ft.Checkbox(label="Li e aceito os Termos de Serviço", value=False)
    msg = ft.Text("", color=ft.Colors.ERROR, size=12)
    resultado = ft.Column(tight=True, spacing=8)

    def atualizar():
        if page is not None:
            page.update()

    async def assinar(plano: str, ciclo: str):
        msg.value = ""
        resultado.controls = []
        if not all([usuario.value, senha.value, cpf.value]):
            msg.value = "Para assinar, preencha usuário, senha e CPF ou CNPJ."
            return atualizar()
        if not aceite.value:
            msg.value = "Para assinar, leia e aceite os Termos de Serviço."
            return atualizar()
        link, erro = await on_assinar(usuario.value, senha.value, plano, ciclo, cpf.value)
        if erro:
            msg.value = erro
            return atualizar()
        resultado.controls = [
            ft.Text("Pagamento pronto. Abra a página segura do Asaas para pagar com cartão de crédito:",
                    size=14, weight=ft.FontWeight.BOLD),
            ft.Text(spans=[ft.TextSpan(text="Abrir página de pagamento", url=link)], size=14),
            ft.Text(link, selectable=True, size=11),
            ft.Text("Depois da confirmação do pagamento, o acesso é liberado automaticamente. "
                    "Se não liberar em alguns minutos, fale com contato@decidiu.com.", size=13),
        ]
        atualizar()

    def botao(texto: str, plano: str, ciclo: str):
        async def clique(_):
            await assinar(plano, ciclo)
        return ft.Button(content=texto, on_click=clique)

    def cartao(titulo, preco, descricao, itens, botoes):
        return ft.Card(elevation=3, content=ft.Container(
            padding=16, width=largura,
            content=ft.Column(tight=True, spacing=6, controls=[
                ft.Text(titulo, size=18, weight=ft.FontWeight.BOLD),
                ft.Text(preco, size=15, color=ft.Colors.PRIMARY),
                ft.Text(descricao, size=13),
                *[_linha(i) for i in itens],
                ft.Row(botoes, wrap=True, spacing=8),
            ]),
        ))

    vagas_txt = (f"Vagas restantes: {vagas_fundador} de 15." if vagas_fundador is not None
                 else "Vagas limitadas, para os 15 primeiros escritórios.")

    cartoes = [
        cartao(
            "Solo",
            "R$ 29 por mês  ·  ou R$ 290 por ano (2 meses grátis)",
            "Para autônomos e pequenos estúdios que começam a organizar as decisões dos projetos.",
            ["1 administrador e 2 colaboradores",
             "até 5 projetos ativos",
             "clientes que só acompanham os projetos não contam no limite"],
            [botao("Assinar Solo mensal", "solo", "mensal"),
             botao("Assinar Solo anual", "solo", "anual")],
        ),
        cartao(
            "Equipe",
            "R$ 79 por mês  ·  ou R$ 790 por ano (2 meses grátis)",
            "Para escritórios com equipe, que precisam de mais projetos e de mais pessoas com acesso.",
            ["1 administrador e 15 colaboradores",
             "até 30 projetos ativos",
             "clientes que só acompanham os projetos não contam no limite"],
            [botao("Assinar Equipe mensal", "equipe", "mensal"),
             botao("Assinar Equipe anual", "equipe", "anual")],
        ),
        cartao(
            "Fundador",
            "R$ 49 por mês, para sempre",
            "Oferta especial para os primeiros escritórios. Tem todas as funções do plano Equipe.",
            ["mesmas funções e limites do plano Equipe",
             "fidelidade de 12 meses, em contrato",
             "em troca, pedimos feedback e depoimento sobre o uso",
             vagas_txt],
            [botao("Assinar Fundador", "fundador", "mensal")],
        ),
    ]

    condicoes = ft.Card(elevation=1, content=ft.Container(padding=16, width=largura, content=ft.Column(
        tight=True, spacing=6, controls=[
            ft.Text("Como funciona", size=16, weight=ft.FontWeight.BOLD),
            _linha("30 dias grátis para testar, sem cobrança. A cobrança começa só se você assinar."),
            _linha("Pagamento somente por cartão de crédito, na página segura do Asaas. "
                   "O Decidiu não recebe nem guarda os dados do seu cartão."),
            _linha("Cobrança recorrente automática, no ciclo escolhido (mensal ou anual)."),
            _linha("A fidelidade de 12 meses existe apenas no plano Fundador, em contrato."),
            _linha("O acesso é liberado logo após a confirmação do pagamento."),
            _linha("Dúvidas: contato@decidiu.com."),
            texto_termos(url_termos, prefixo="Leia os "),
        ])))

    formulario = ft.Card(elevation=1, content=ft.Container(padding=16, width=largura, content=ft.Column(
        tight=True, spacing=12, controls=[
            ft.Text("Seus dados para assinar", size=16, weight=ft.FontWeight.BOLD),
            ft.Text("Use o usuário e a senha do administrador da organização. Você pode assinar mesmo "
                    "com a conta bloqueada pelo vencimento do teste.", size=12),
            usuario, senha, cpf, aceite, msg,
        ])))

    conteudo = ft.Column(
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        spacing=16,
        controls=[
            marca_login(altura=120),
            ft.Text("Escolha o seu plano", size=22, weight=ft.FontWeight.BOLD),
            ft.Text("Comece com 30 dias grátis e assine quando quiser.", size=13),
            *cartoes,
            condicoes,
            formulario,
            resultado,
            ft.TextButton(content="Voltar para entrar", on_click=lambda _: on_voltar()),
        ],
    )

    return ft.View(
        route="/planos",
        scroll=ft.ScrollMode.AUTO,
        controls=[ft.Container(
            alignment=ft.Alignment.TOP_CENTER,
            padding=espaco,
            content=ft.Container(width=largura_pagina, content=conteudo),
        )],
    )

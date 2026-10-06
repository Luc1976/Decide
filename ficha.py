import datetime

import flet as ft
from database import (
    listar_caracteristicas,
    nivel_no_projeto,
    listar_historico_ficha,
    mapa_origens_ficha,
    salvar_caracteristicas,
)
from ficha_calculos import calcular_indicadores
from models import CAMPOS_LONGOS, FICHA_GRUPOS, GRUPO_OUTRAS, NIVEL_PAPEL
from layout import col, largura_dialogo, opcoes_dialogo
from views.questionario_sistemas import criar_aba_sistemas_construtivos



def _hora_local(momento: datetime.datetime) -> datetime.datetime:
    if momento.tzinfo is None:  # o SQLite devolve datas sem fuso (gravadas em UTC)
        momento = momento.replace(tzinfo=datetime.timezone.utc)
    return momento.astimezone()


def build_ficha_view(page, projeto, usuario, on_logout, on_voltar):
    """Ficha de características do empreendimento: os inputs iniciais do projeto."""

    # Leitor (cliente) vê a ficha, mas não altera.
    pode_editar = projeto is not None and (
        nivel_no_projeto(usuario.id, projeto.id) >= NIVEL_PAPEL["Editor"]
    )

    salvos = {}
    if projeto is not None:
        salvos = {(c.grupo, c.nome): c for c in listar_caracteristicas(projeto.id)}

    campos = {}  # (grupo, nome) -> (TextField, unidade)
    linhas_por_grupo = {}  # grupo -> ft.Row que recebe os campos
    mensagem = ft.Text("", size=12)
    caixa_indicadores = ft.Column(spacing=6)

    # ---------- Indicadores calculados ----------
    def montar_indicadores():
        valores = {nome: tf.value for (_, nome), (tf, _) in campos.items()}
        linhas = calcular_indicadores(valores)
        if not linhas:
            caixa_indicadores.controls = [
                ft.Text(
                    "Preencha a área do terreno e os parâmetros (TO, CA, permeabilidade) "
                    "para ver os indicadores.",
                    size=13,
                    color=ft.Colors.GREY_400,
                )
            ]
            return
        caixa_indicadores.controls = [
            ft.Row(
                vertical_alignment=ft.CrossAxisAlignment.START,
                controls=[
                    ft.Text(
                        rotulo,
                        size=13,
                        expand=True,
                        color=ft.Colors.AMBER_600 if alerta else ft.Colors.GREY_400,
                    ),
                    ft.Text(
                        texto,
                        size=14,
                        weight=ft.FontWeight.BOLD,
                        color=ft.Colors.AMBER_600 if alerta else None,
                    ),
                ],
            )
            for rotulo, texto, alerta in linhas
        ]

    def ao_digitar(_):
        mensagem.value = ""
        montar_indicadores()
        page.update()

    # ---------- Campos ----------
    def criar_campo(grupo, nome, unidade, valor):
        longo = nome in CAMPOS_LONGOS
        opcoes = {}
        if longo:
            opcoes = {"multiline": True, "min_lines": 3}
        tf = ft.TextField(
            label=f"{nome} ({unidade})" if unidade else nome,
            value=valor,
            col=col(12) if longo else col(12, sm=6, md=4),
            on_change=ao_digitar,
            read_only=not pode_editar,
            **opcoes,
        )
        campos[(grupo, nome)] = (tf, unidade)
        linhas_por_grupo[grupo].controls.append(tf)
        return tf

    def montar_grupo(grupo, modelo):
        linhas_por_grupo[grupo] = ft.ResponsiveRow(spacing=10, run_spacing=10)
        nomes_modelo = {nome for nome, _ in modelo}
        for nome, unidade in modelo:
            salvo = salvos.get((grupo, nome))
            criar_campo(grupo, nome, unidade, salvo.valor if salvo else "")
        # campos salvos que não estão (mais) no modelo continuam aparecendo
        for (g, nome), salvo in salvos.items():
            if g == grupo and nome not in nomes_modelo:
                criar_campo(grupo, nome, salvo.unidade or "", salvo.valor)

    for grupo, modelo in FICHA_GRUPOS.items():
        montar_grupo(grupo, modelo)
    montar_grupo(GRUPO_OUTRAS, [])

    # ---------- Novo campo personalizado ----------
    input_novo_nome = ft.TextField(label="Nome da característica")
    input_nova_unidade = ft.TextField(label="Unidade (opcional)", col=col(12, md=4))
    input_novo_valor = ft.TextField(label="Valor", col=col(12, md=8))
    mensagem_novo = ft.Text("", color=ft.Colors.RED_400, size=12)

    def abrir_novo_campo(_):
        input_novo_nome.value = ""
        input_nova_unidade.value = ""
        input_novo_valor.value = ""
        mensagem_novo.value = ""
        page.show_dialog(modal_novo_campo)

    def adicionar_campo(_):
        nome = (input_novo_nome.value or "").strip()
        if not nome:
            mensagem_novo.value = "Informe o nome da característica."
            page.update()
            return
        if (GRUPO_OUTRAS, nome) in campos:
            mensagem_novo.value = "Já existe uma característica com esse nome."
            page.update()
            return
        criar_campo(
            GRUPO_OUTRAS,
            nome,
            (input_nova_unidade.value or "").strip(),
            (input_novo_valor.value or "").strip(),
        )
        mensagem.value = "Característica adicionada. Clique em Salvar ficha para gravar."
        mensagem.color = ft.Colors.AMBER_600
        page.pop_dialog()
        page.update()

    modal_novo_campo = ft.AlertDialog(
        **opcoes_dialogo(page),
        title=ft.Text("Nova característica"),
        content=ft.Container(
            width=largura_dialogo(page, 500),
            content=ft.Column(
                tight=True,
                controls=[
                    input_novo_nome,
                    ft.ResponsiveRow([input_nova_unidade, input_novo_valor]),
                    mensagem_novo,
                ],
            ),
        ),
        actions=[
            ft.TextButton(content="Cancelar", on_click=lambda _: page.pop_dialog()),
            ft.Button(content="Adicionar", on_click=adicionar_campo),
        ],
    )

    # ---------- Salvar ----------
    def salvar(_):
        if projeto is None:
            return
        itens = [
            (grupo, nome, unidade, tf.value or "")
            for (grupo, nome), (tf, unidade) in campos.items()
        ]
        try:
            qtd = salvar_caracteristicas(
                projeto.id, itens, usuario.nome_completo, usuario_id=usuario.id
            )
        except Exception as erro:
            mensagem.color = ft.Colors.RED_400
            mensagem.value = f"Não foi possível salvar a ficha: {erro}"
            page.update()
            return
        mensagem.color = ft.Colors.GREEN_400
        if qtd == 0:
            mensagem.value = "Nenhuma alteração para salvar."
        elif qtd == 1:
            mensagem.value = "Ficha salva. 1 campo alterado."
        else:
            mensagem.value = f"Ficha salva. {qtd} campos alterados."
        page.update()

    # ---------- Histórico ----------
    modal_historico = ft.AlertDialog(**opcoes_dialogo(page), title=ft.Text("Histórico da ficha"))

    def abrir_historico(_):
        registros = listar_historico_ficha(projeto.id) if projeto else []
        origens = mapa_origens_ficha(projeto.id) if projeto else {}
        if registros:
            controles = []
            for r in registros:
                anterior = r.valor_anterior or "(vazio)"
                novo = r.valor_novo or "(vazio)"
                origem = origens.get(r.id)
                controles.append(
                    ft.Text(
                        f"{_hora_local(r.data_registro).strftime('%d/%m/%Y %H:%M')} · {r.autor}"
                        + (f" · {origem}" if origem else ""),
                        size=11,
                        color=ft.Colors.GREY_400,
                    )
                )
                controles.append(ft.Text(f"{r.nome}: {anterior} → {novo}", size=13))
                controles.append(ft.Divider(height=1))
        else:
            controles = [
                ft.Text("Nenhuma alteração registrada ainda.", color=ft.Colors.GREY_400)
            ]
        modal_historico.content = ft.Container(
            width=largura_dialogo(page, 600),
            content=ft.Column(tight=True, scroll=ft.ScrollMode.AUTO, controls=controles),
        )
        modal_historico.actions = [
            ft.Button(content="Fechar", on_click=lambda _: page.pop_dialog())
        ]
        page.show_dialog(modal_historico)

    # ---------- Montagem da tela ----------
    montar_indicadores()

    def card_grupo(grupo, extra=None):
        controles = [
            ft.Text(grupo, size=16, weight=ft.FontWeight.BOLD),
            ft.Divider(height=1),
            linhas_por_grupo[grupo],
        ]
        if extra is not None:
            controles.append(extra)
        return ft.Card(
            content=ft.Container(padding=15, content=ft.Column(controls=controles))
        )

    cards = [
        ft.Card(
            content=ft.Container(
                padding=15,
                content=ft.Column(
                    controls=[
                        ft.Text(
                            "Indicadores calculados",
                            size=16,
                            weight=ft.FontWeight.BOLD,
                        ),
                        ft.Divider(height=1),
                        caixa_indicadores,
                    ]
                ),
            )
        )
    ]
    for grupo in FICHA_GRUPOS:
        cards.append(card_grupo(grupo))
    cards.append(
        card_grupo(
            GRUPO_OUTRAS,
            ft.Button(
                content="+ Adicionar característica",
                icon=ft.Icons.ADD,
                on_click=abrir_novo_campo,
                visible=pode_editar,
            ),
        )
    )

    header = ft.Container(
        padding=15,
        bgcolor=ft.Colors.SURFACE,
        border_radius=10,
        content=ft.ResponsiveRow(
            controls=[
                ft.Column(
                    col=col(12, md=5),
                    controls=[
                        ft.Text(
                            "Ficha do Empreendimento",
                            size=22,
                            weight=ft.FontWeight.BOLD,
                        ),
                        ft.Text(
                            f"Projeto Ativo: {projeto.nome}" if projeto else "Sem projeto",
                            size=14,
                            color=ft.Colors.BLUE_200,
                        ),
                    ]
                ),
                ft.Row(
                    col=col(12, md=7),
                    wrap=True,
                    alignment=ft.MainAxisAlignment.END,
                    controls=[
                        ft.Button(
                            content="Linha do tempo",
                            icon=ft.Icons.TIMELINE,
                            on_click=on_voltar,
                        ),
                        ft.Button(
                            content="Histórico",
                            icon=ft.Icons.HISTORY,
                            on_click=abrir_historico,
                        ),
                        ft.Button(
                            content="Salvar ficha",
                            icon=ft.Icons.SAVE,
                            on_click=salvar,
                            visible=pode_editar,
                        ),
                        ft.IconButton(
                            icon=ft.Icons.LOGOUT,
                            tooltip="Sair",
                            on_click=on_logout,
                        ),
                    ],
                ),
            ],
        ),
    )

    aba_dados = ft.Column(
        [
            mensagem,
            ft.ListView(
                expand=True,
                spacing=15,
                padding=10,
                controls=cards,
            ),
        ],
        expand=True,
    )
    aba_sistemas = criar_aba_sistemas_construtivos(page, projeto, usuario, pode_editar)

    # Flet 1.0: as abas são um conjunto Tabs > (TabBar + TabBarView); "length" = nº de abas.
    abas = ft.Tabs(
        length=2,
        selected_index=0,
        animation_duration=300,
        expand=True,
        content=ft.Column(
            expand=True,
            controls=[
                ft.TabBar(
                    tabs=[
                        ft.Tab(label="Dados gerais"),
                        ft.Tab(label="Sistemas construtivos"),
                    ]
                ),
                ft.TabBarView(
                    expand=True,
                    controls=[aba_dados, aba_sistemas],
                ),
            ],
        ),
    )

    return ft.View(
        route="/ficha",
        controls=[header, abas],
    )

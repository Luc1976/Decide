import datetime

import flet as ft
from database import (
    adicionar_adendo,
    atualizar_reuniao_rascunho,
    buscar_reuniao,
    buscar_reunioes_projeto,
    campos_da_ficha,
    criar_reuniao,
    extrair_decisoes,
    fechar_reuniao,
    listar_adendos,
    listar_alteracoes_ficha_ata,
    listar_decisoes_reuniao,
    nivel_no_projeto,
)
from models import NIVEL_PAPEL
from layout import col, largura_dialogo, opcoes_dialogo
from ficha_calculos import analisar_alteracoes_ata

CORES_STATUS = {
    "Rascunho": ft.Colors.AMBER_600,
    "Fechada": ft.Colors.GREEN_400,
}
DICA_DECISAO = "Comece a linha com [D] para registrar uma decisão."
DICA_FICHA = "Linha [F] campo = valor altera a ficha (vale para a [D] logo acima)."


def _texto_decisoes(qtd: int) -> str:
    if qtd == 0:
        return "Nenhuma decisão detectada. " + DICA_DECISAO
    if qtd == 1:
        return "1 decisão detectada"
    return f"{qtd} decisões detectadas"


def _converter_data(valor):
    try:
        return datetime.datetime.strptime((valor or "").strip(), "%d/%m/%Y").date()
    except ValueError:
        return None


def _hora_local(momento: datetime.datetime) -> datetime.datetime:
    if momento.tzinfo is None:  # o SQLite devolve datas sem fuso (gravadas em UTC)
        momento = momento.replace(tzinfo=datetime.timezone.utc)
    return momento.astimezone()


def _codigo(decisao) -> str:
    return f"D-{decisao.numero:03d}" if decisao.numero else "D-?"


def build_atas_view(
    page,
    projeto,
    usuario,
    on_logout,
    on_voltar,
    ata_inicial_id=None,
):
    """Tela de atas de reunião. Devolve (view, ao_montar): chame ao_montar() depois
    que a view estiver na página para abrir a ata pedida (ata_inicial_id)."""

    ata_em_edicao = None  # Reuniao em rascunho aberta no editor (None = ata nova)
    # Leitor (cliente) só acompanha: vê atas fechadas e não altera nada.
    pode_editar = projeto is not None and (
        nivel_no_projeto(usuario.id, projeto.id) >= NIVEL_PAPEL["Editor"]
    )

    campo_busca = ft.TextField(
        label="Buscar atas",
        hint_text="Título, participantes, autor ou texto",
        prefix_icon=ft.Icons.SEARCH,
        expand=True,
        on_change=lambda _: carregar_atas(),
    )
    lista_atas = ft.ListView(expand=True, spacing=15, padding=10)

    # ---------- Editor (ata nova ou rascunho) ----------
    input_titulo = ft.TextField(label="Título da reunião")
    input_data = ft.TextField(label="Data (dd/mm/aaaa)", col=col(12, md=4))
    input_participantes = ft.TextField(
        label="Participantes", hint_text="Nomes separados por vírgula", col=col(12, md=8)
    )
    contador_decisoes = ft.Text("", size=12, color=ft.Colors.BLUE_200)

    def atualizar_contador(_=None):
        atualizar_resumo()
        page.update()

    input_texto = ft.TextField(
        label="Texto da ata",
        hint_text="Escreva a ata. Linha [D] = decisão. " + DICA_FICHA,
        multiline=True,
        min_lines=10,
        max_lines=18,
        on_change=atualizar_contador,
    )
    mensagem_editor = ft.Text("", color=ft.Colors.RED_400, size=12)
    aviso_ficha = ft.Text("", size=12, color=ft.Colors.AMBER_600)
    campos_ficha = []  # campos da ficha usados para reconhecer as linhas [F]

    def recarregar_campos_ficha():
        campos_ficha.clear()
        if projeto is not None:
            campos_ficha.extend(campos_da_ficha(projeto.id))

    def atualizar_resumo():
        """Contador de decisões + alterações da ficha + erros das linhas [F]."""
        contador_decisoes.value = _texto_decisoes(
            len(extrair_decisoes(input_texto.value))
        )
        alteracoes, erros = analisar_alteracoes_ata(input_texto.value, campos_ficha)
        if alteracoes:
            contador_decisoes.value += (
                f" · {len(alteracoes)} alteração(ões) da ficha"
            )
        aviso_ficha.value = ("Atenção: " + "; ".join(erros) + ".") if erros else ""

    def gravar_rascunho():
        """Valida e grava a ata como rascunho. Devolve a Reuniao ou None se houver erro."""
        nonlocal ata_em_edicao
        data = _converter_data(input_data.value)
        if data is None:
            mensagem_editor.value = "Use a data no formato dd/mm/aaaa."
            page.update()
            return None
        try:
            if ata_em_edicao is None:
                ata_em_edicao = criar_reuniao(
                    projeto.id,
                    input_titulo.value,
                    data,
                    input_participantes.value,
                    input_texto.value,
                    usuario.nome_completo,
                    usuario_id=usuario.id,
                )
            else:
                ata_em_edicao = atualizar_reuniao_rascunho(
                    ata_em_edicao.id,
                    input_titulo.value,
                    data,
                    input_participantes.value,
                    input_texto.value,
                    usuario_id=usuario.id,
                )
        except (ValueError, PermissionError) as erro:
            mensagem_editor.value = str(erro)
            page.update()
            return None
        return ata_em_edicao

    def salvar_rascunho(_):
        if gravar_rascunho() is None:
            return
        page.pop_dialog()
        carregar_atas()

    def pedir_fechamento(_):
        ata = gravar_rascunho()
        if ata is None:
            return
        recarregar_campos_ficha()
        alteracoes, erros = analisar_alteracoes_ata(ata.texto, campos_ficha)
        if erros:
            mensagem_editor.value = "Corrija as linhas [F] antes de fechar: " + "; ".join(erros) + "."
            page.update()
            return
        qtd = len(extrair_decisoes(ata.texto))
        if qtd == 0:
            registro = "Nenhuma decisão será registrada."
        elif qtd == 1:
            registro = "1 decisão será registrada na linha do tempo."
        else:
            registro = f"{qtd} decisões serão registradas na linha do tempo."
        texto_confirmacao.value = (
            f"A Ata {ata.numero:02d} será fechada e não poderá mais ser editada. "
            f"Correções entrarão como adendos. {registro}"
        )
        if alteracoes:
            texto_confirmacao.value += (
                f" {len(alteracoes)} alteração(ões) serão aplicadas na ficha do empreendimento."
            )
        mensagem_confirmacao.value = ""
        page.pop_dialog()
        page.show_dialog(modal_confirmar)

    modal_editor = ft.AlertDialog(
        **opcoes_dialogo(page),
        title=ft.Text("Nova ata"),
        content=ft.Container(
            width=largura_dialogo(page, 700),
            content=ft.Column(
                tight=True,
                scroll=ft.ScrollMode.AUTO,
                controls=[
                    input_titulo,
                    ft.ResponsiveRow([input_data, input_participantes]),
                    input_texto,
                    contador_decisoes,
                    aviso_ficha,
                    mensagem_editor,
                ],
            ),
        ),
        actions=[
            ft.TextButton(content="Cancelar", on_click=lambda _: page.pop_dialog()),
            ft.Button(content="Salvar rascunho", on_click=salvar_rascunho),
            ft.Button(
                content="Fechar ata",
                icon=ft.Icons.LOCK,
                on_click=pedir_fechamento,
            ),
        ],
    )

    def abrir_editor(reuniao=None):
        nonlocal ata_em_edicao
        ata_em_edicao = reuniao
        if reuniao is None:
            modal_editor.title = ft.Text("Nova ata")
            input_titulo.value = ""
            input_data.value = datetime.date.today().strftime("%d/%m/%Y")
            input_participantes.value = ""
            input_texto.value = ""
        else:
            modal_editor.title = ft.Text(f"Ata {reuniao.numero:02d} (rascunho)")
            input_titulo.value = reuniao.titulo
            input_data.value = reuniao.data_reuniao.strftime("%d/%m/%Y")
            input_participantes.value = reuniao.participantes or ""
            input_texto.value = reuniao.texto
        mensagem_editor.value = ""
        recarregar_campos_ficha()
        atualizar_resumo()
        page.show_dialog(modal_editor)

    # ---------- Confirmação de fechamento ----------
    texto_confirmacao = ft.Text("")
    mensagem_confirmacao = ft.Text("", color=ft.Colors.RED_400, size=12)

    def voltar_ao_editor(_):
        page.pop_dialog()
        page.show_dialog(modal_editor)

    def confirmar_fechamento(_):
        try:
            fechar_reuniao(ata_em_edicao.id, usuario.nome_completo, usuario_id=usuario.id)
        except (ValueError, PermissionError) as erro:
            mensagem_confirmacao.value = str(erro)
            page.update()
            return
        ata_id = ata_em_edicao.id
        page.pop_dialog()
        carregar_atas()
        abrir_visualizacao(ata_id)

    modal_confirmar = ft.AlertDialog(
        **opcoes_dialogo(page),
        title=ft.Text("Fechar ata?"),
        content=ft.Container(
            width=largura_dialogo(page, 450),
            content=ft.Column(
                tight=True, controls=[texto_confirmacao, mensagem_confirmacao]
            ),
        ),
        actions=[
            ft.TextButton(content="Voltar", on_click=voltar_ao_editor),
            ft.Button(content="Fechar ata", icon=ft.Icons.LOCK, on_click=confirmar_fechamento),
        ],
    )

    # ---------- Visualização (ata fechada, com decisões e adendos) ----------
    input_adendo = ft.TextField(
        label="Novo adendo", multiline=True, min_lines=2, hint_text="Correção ou complemento à ata"
    )
    mensagem_adendo = ft.Text("", color=ft.Colors.RED_400, size=12)
    modal_visualizar = ft.AlertDialog(**opcoes_dialogo(page), title=ft.Text(""))
    ata_visualizada_id = None

    def linhas_da_ata(texto: str):
        linhas = []
        for linha in (texto or "").splitlines():
            eh_decisao = linha.strip().upper().startswith("[D]")
            if eh_decisao:
                linhas.append(
                    ft.Container(
                        padding=6,
                        border_radius=4,
                        bgcolor=ft.Colors.BLUE_900,
                        content=ft.Text(linha.strip(), size=14),
                    )
                )
            elif linha.strip().upper().startswith("[F]"):
                linhas.append(
                    ft.Container(
                        padding=6,
                        border_radius=4,
                        bgcolor=ft.Colors.TEAL_900,
                        content=ft.Text(linha.strip(), size=14),
                    )
                )
            else:
                linhas.append(ft.Text(linha if linha.strip() else " ", size=14))
        return linhas

    def montar_visualizacao():
        ata = buscar_reuniao(ata_visualizada_id)
        decisoes = listar_decisoes_reuniao(ata.id)
        adendos = listar_adendos(ata.id)

        modal_visualizar.title = ft.Text(f"Ata {ata.numero:02d} · {ata.titulo}")
        controles = [
            ft.Text(
                f"{ata.data_reuniao.strftime('%d/%m/%Y')} | Status: {ata.status} | "
                f"Autor: {ata.autor}",
                size=12,
                color=ft.Colors.GREY_400,
            ),
            ft.Text(
                f"Participantes: {ata.participantes or 'não informados'}",
                size=12,
                color=ft.Colors.GREY_400,
            ),
            ft.Divider(),
            ft.Text("Texto da ata", weight=ft.FontWeight.BOLD),
            ft.Column(spacing=2, controls=linhas_da_ata(ata.texto)),
            ft.Divider(),
            ft.Text("Decisões desta ata", weight=ft.FontWeight.BOLD),
        ]
        if decisoes:
            for dec in decisoes:
                controles.append(
                    ft.Row(
                        vertical_alignment=ft.CrossAxisAlignment.START,
                        controls=[
                            ft.Text(
                                _codigo(dec),
                                weight=ft.FontWeight.BOLD,
                                color=ft.Colors.BLUE_200,
                            ),
                            ft.Text(dec.descricao, expand=True),
                        ],
                    )
                )
        else:
            controles.append(
                ft.Text("Nenhuma decisão registrada nesta ata.", color=ft.Colors.GREY_400)
            )

        alteracoes_ficha = listar_alteracoes_ficha_ata(ata.id)
        if alteracoes_ficha:
            controles.append(ft.Divider())
            controles.append(ft.Text("Alterações da ficha do empreendimento", weight=ft.FontWeight.BOLD))
            for alteracao in alteracoes_ficha:
                controles.append(
                    ft.Text(
                        f"{alteracao.nome}: {alteracao.valor_anterior or '(vazio)'} → "
                        f"{alteracao.valor_novo or '(vazio)'}"
                    )
                )

        if adendos:
            controles.append(ft.Divider())
            controles.append(ft.Text("Adendos", weight=ft.FontWeight.BOLD))
            for adendo in adendos:
                controles.append(
                    ft.Text(
                        f"{_hora_local(adendo.data_registro).strftime('%d/%m/%Y %H:%M')} · {adendo.autor}",
                        size=11,
                        color=ft.Colors.GREY_400,
                    )
                )
                controles.append(ft.Text(adendo.texto))

        if ata.status == "Fechada" and pode_editar:
            controles.extend(
                [
                    ft.Divider(),
                    input_adendo,
                    mensagem_adendo,
                    ft.Button(
                        content="Registrar adendo",
                        icon=ft.Icons.ADD_COMMENT,
                        on_click=registrar_adendo,
                    ),
                ]
            )

        modal_visualizar.content = ft.Container(
            width=largura_dialogo(page, 700),
            content=ft.Column(tight=True, scroll=ft.ScrollMode.AUTO, controls=controles),
        )

        async def ver_na_timeline(_):
            page.pop_dialog()
            await on_voltar(None)

        def editar_rascunho(_):
            page.pop_dialog()
            abrir_editor(ata)

        acoes = []
        if ata.status == "Fechada":
            acoes.append(
                ft.TextButton(content="Ver na linha do tempo", on_click=ver_na_timeline)
            )
        elif pode_editar:
            acoes.append(ft.TextButton(content="Continuar editando", on_click=editar_rascunho))
        acoes.append(ft.Button(content="Fechar janela", on_click=lambda _: page.pop_dialog()))
        modal_visualizar.actions = acoes

    def registrar_adendo(_):
        try:
            adicionar_adendo(
                ata_visualizada_id, input_adendo.value, usuario.nome_completo, usuario_id=usuario.id
            )
        except (ValueError, PermissionError) as erro:
            mensagem_adendo.value = str(erro)
            page.update()
            return
        input_adendo.value = ""
        mensagem_adendo.value = ""
        montar_visualizacao()
        page.update()

    def abrir_visualizacao(ata_id):
        nonlocal ata_visualizada_id
        ata_visualizada_id = ata_id
        input_adendo.value = ""
        mensagem_adendo.value = ""
        montar_visualizacao()
        page.show_dialog(modal_visualizar)

    # ---------- Lista de atas ----------
    def carregar_atas():
        lista_atas.controls.clear()
        if projeto is None:
            lista_atas.controls.append(
                ft.Text("Nenhum projeto disponível para exibir atas.")
            )
            page.update()
            return

        atas = buscar_reunioes_projeto(projeto.id, campo_busca.value or "")
        if not pode_editar:
            atas = [a for a in atas if a.status == "Fechada"]  # rascunho é só da equipe
        if not atas:
            lista_atas.controls.append(
                ft.Text(
                    "Nenhuma ata encontrada para a busca."
                    if (campo_busca.value or "").strip()
                    else "Nenhuma ata registrada neste projeto ainda.",
                    color=ft.Colors.GREY_400,
                )
            )

        for ata in atas:
            cor_status = CORES_STATUS.get(ata.status, ft.Colors.GREY_600)
            qtd_decisoes = len(listar_decisoes_reuniao(ata.id))

            if ata.status == "Fechada":
                botao = ft.Button(
                    content="Abrir ata",
                    icon=ft.Icons.DESCRIPTION,
                    on_click=lambda _, ata_id=ata.id: abrir_visualizacao(ata_id),
                )
            else:
                botao = ft.Button(
                    content="Continuar editando",
                    icon=ft.Icons.EDIT,
                    on_click=lambda _, ata=ata: abrir_editor(ata),
                )

            lista_atas.controls.append(
                ft.Card(
                    content=ft.Container(
                        padding=15,
                        content=ft.Column(
                            controls=[
                                ft.Row(
                                    wrap=True,
                                    controls=[
                                        ft.Chip(
                                            label=ft.Text(ata.status),
                                            color=cor_status,
                                        ),
                                        ft.Text(
                                            f"Ata {ata.numero:02d} · {ata.titulo}",
                                            size=16,
                                            weight=ft.FontWeight.BOLD,
                                        ),
                                    ]
                                ),
                                ft.Text(
                                    f"{ata.data_reuniao.strftime('%d/%m/%Y')} | "
                                    f"Participantes: {ata.participantes or 'não informados'}",
                                    size=13,
                                ),
                                ft.Divider(height=1),
                                ft.Row(
                                    wrap=True,
                                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                    controls=[
                                        ft.Text(
                                            f"Autor: {ata.autor} | Decisões: {qtd_decisoes}",
                                            size=11,
                                            color=ft.Colors.GREY_400,
                                        ),
                                        botao,
                                    ],
                                ),
                            ]
                        ),
                    ),
                )
            )
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
                        ft.Text(
                            "Atas de Reunião",
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
                            content="+ Nova Ata",
                            icon=ft.Icons.ADD,
                            on_click=lambda _: abrir_editor(None),
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

    def ao_montar():
        if ata_inicial_id is None:
            return
        ata = buscar_reuniao(ata_inicial_id)
        if ata is None:
            return
        if ata.status == "Fechada":
            abrir_visualizacao(ata.id)
        elif pode_editar:
            abrir_editor(ata)

    carregar_atas()
    view = ft.View(
        route="/atas",
        controls=[
            header,
            ft.Row([campo_busca]),
            ft.Divider(),
            lista_atas,
        ],
    )
    return view, ao_montar

import datetime

import flet as ft

import tema
from database import (
    PENDENCIA_ABERTA,
    PENDENCIA_CANCELADA,
    PENDENCIA_RESOLVIDA,
    atualizar_pendencia,
    buscar_decisoes_projeto,
    cancelar_pendencia,
    criar_pendencia,
    listar_pendencias,
    listar_reunioes_projeto,
    nivel_no_projeto,
    reabrir_pendencia,
    resolver_pendencia,
)
from layout import col, largura_dialogo, opcoes_dialogo, rotulo
from models import CATEGORIAS, IMPACTOS, NIVEL_PAPEL

TODAS = "__todas__"
NOVA = "nova"
EXISTENTE = "existente"


def _codigo(pendencia) -> str:
    return f"P-{pendencia.numero:03d}"


def _converter_data(texto):
    """'dd/mm/aaaa' -> date. Vazio devolve None; formato inválido levanta ValueError."""
    texto = (texto or "").strip()
    if not texto:
        return None
    return datetime.datetime.strptime(texto, "%d/%m/%Y").date()


def _hora_local(momento: datetime.datetime) -> datetime.datetime:
    if momento.tzinfo is None:  # o SQLite devolve datas sem fuso (gravadas em UTC)
        momento = momento.replace(tzinfo=datetime.timezone.utc)
    return momento.astimezone()


def build_pendencias_view(page, projeto, usuario, on_logout, on_voltar, on_open_ata=None):
    """Assuntos que aguardam decisão. Entram por aqui (manual) ou pelas linhas [P] das atas
    fechadas; saem resolvidos (ligados a uma decisão) ou cancelados, e ficam no histórico."""

    # Leitor (cliente) acompanha a lista, mas não altera nada.
    pode_editar = nivel_no_projeto(usuario.id, projeto.id) >= NIVEL_PAPEL["Editor"]
    pendencia_atual = None  # a pendência aberta nos diálogos (None = nova)

    campo_busca = ft.TextField(
        label="Buscar pendências",
        hint_text="Assunto, detalhes, responsável ou categoria",
        prefix_icon=ft.Icons.SEARCH,
        col=col(12, md=8),
        on_change=lambda _: carregar(),
    )
    filtro_status = ft.Dropdown(
        label="Situação",
        col=col(12, md=4),
        value=PENDENCIA_ABERTA,
        options=[
            ft.DropdownOption(key=PENDENCIA_ABERTA, text="Em aberto"),
            ft.DropdownOption(key=PENDENCIA_RESOLVIDA, text="Resolvidas"),
            ft.DropdownOption(key=PENDENCIA_CANCELADA, text="Canceladas"),
            ft.DropdownOption(key=TODAS, text="Todas"),
        ],
        on_select=lambda _: carregar(),
    )
    resumo = ft.Text("", size=13, color=ft.Colors.ON_SURFACE_VARIANT)
    lista = ft.ListView(expand=True, spacing=15, padding=10)

    # ---------- Nova / editar pendência ----------
    input_titulo = ft.TextField(label="Assunto que precisa de decisão")
    input_descricao = ft.TextField(
        label="Detalhes (opções em estudo, o que falta para decidir)", multiline=True, min_lines=3
    )
    input_categoria = ft.Dropdown(
        label="Categoria",
        options=[ft.DropdownOption(key=c) for c in CATEGORIAS],
        value="Geral",
        col=col(12, md=6),
    )
    input_responsavel = ft.TextField(label="Quem deve decidir / responder", col=col(12, md=6))
    input_prazo = ft.TextField(label="Prazo (dd/mm/aaaa, opcional)", col=col(12, md=6))
    mensagem_form = ft.Text("", color=ft.Colors.ERROR, size=12)

    def abrir_formulario(pendencia=None):
        nonlocal pendencia_atual
        pendencia_atual = pendencia
        modal_form.title = ft.Text(
            f"Editar {_codigo(pendencia)}" if pendencia else "Nova pendência de decisão"
        )
        input_titulo.value = pendencia.titulo if pendencia else ""
        input_descricao.value = pendencia.descricao if pendencia else ""
        input_categoria.value = pendencia.categoria if pendencia else "Geral"
        input_responsavel.value = pendencia.responsavel if pendencia else ""
        input_prazo.value = pendencia.prazo.strftime("%d/%m/%Y") if pendencia and pendencia.prazo else ""
        mensagem_form.value = ""
        page.show_dialog(modal_form)

    def salvar_formulario(_):
        try:
            prazo = _converter_data(input_prazo.value)
        except ValueError:
            mensagem_form.value = "Use o prazo no formato dd/mm/aaaa."
            page.update()
            return
        try:
            if pendencia_atual is None:
                criar_pendencia(
                    projeto.id,
                    input_titulo.value,
                    input_descricao.value,
                    input_categoria.value,
                    input_responsavel.value,
                    prazo,
                    autor=usuario.nome_completo,
                    usuario_id=usuario.id,
                )
            else:
                atualizar_pendencia(
                    pendencia_atual.id,
                    input_titulo.value,
                    input_descricao.value,
                    input_categoria.value,
                    input_responsavel.value,
                    prazo,
                    usuario_id=usuario.id,
                )
        except (ValueError, PermissionError) as erro:
            mensagem_form.value = str(erro)
            page.update()
            return
        page.pop_dialog()
        carregar()

    modal_form = ft.AlertDialog(
        **opcoes_dialogo(page),
        title=ft.Text(""),
        content=ft.Container(
            width=largura_dialogo(page, 600),
            content=ft.Column(
                tight=True,
                scroll=ft.ScrollMode.AUTO,
                controls=[
                    input_titulo,
                    input_descricao,
                    ft.ResponsiveRow([input_categoria, input_responsavel, input_prazo]),
                    mensagem_form,
                ],
            ),
        ),
        actions=[
            ft.TextButton(content="Cancelar", on_click=lambda _: page.pop_dialog()),
            ft.Button(content="Salvar", icon=ft.Icons.SAVE, on_click=salvar_formulario),
        ],
    )

    # ---------- Resolver (ligar a uma decisão) ----------
    modo_resolucao = ft.RadioGroup(
        value=NOVA,
        content=ft.Column(
            spacing=0,
            controls=[
                ft.Radio(value=NOVA, label="Registrar a decisão agora"),
                ft.Radio(value=EXISTENTE, label="Já existe uma decisão registrada"),
            ],
        ),
    )
    res_titulo = ft.TextField(label="Título da decisão")
    res_descricao = ft.TextField(label="O que foi decidido?", multiline=True, min_lines=2)
    res_categoria = ft.Dropdown(
        label="Categoria", options=[ft.DropdownOption(key=c) for c in CATEGORIAS], col=col(12, md=6)
    )
    res_impacto = ft.Dropdown(
        label="Impacto", options=[ft.DropdownOption(key=i) for i in IMPACTOS], value="Médio", col=col(12, md=6)
    )
    res_justificativa = ft.TextField(label="Justificativa (opcional)", multiline=True, min_lines=2)
    caixa_nova = ft.Column(
        tight=True,
        controls=[res_titulo, res_descricao, ft.ResponsiveRow([res_categoria, res_impacto]), res_justificativa],
    )
    res_decisao = ft.Dropdown(label="Decisão que resolve a pendência", options=[])
    caixa_existente = ft.Column(tight=True, controls=[res_decisao], visible=False)
    res_observacao = ft.TextField(label="Observação (opcional)", multiline=True, min_lines=1)
    mensagem_resolver = ft.Text("", color=ft.Colors.ERROR, size=12)

    def trocar_modo(_=None):
        caixa_nova.visible = modo_resolucao.value == NOVA
        caixa_existente.visible = modo_resolucao.value == EXISTENTE
        page.update()

    modo_resolucao.on_change = trocar_modo

    def abrir_resolver(pendencia):
        nonlocal pendencia_atual
        pendencia_atual = pendencia
        modal_resolver.title = ft.Text(f"Resolver {_codigo(pendencia)} · {pendencia.titulo}")
        decisoes = sorted(
            buscar_decisoes_projeto(projeto.id, ""), key=lambda d: d.numero or 0, reverse=True
        )
        res_decisao.options = [
            ft.DropdownOption(
                key=str(d.id),
                text=f"D-{d.numero:03d} · {d.titulo}" if d.numero else d.titulo,
            )
            for d in decisoes
        ]
        res_decisao.value = None
        modo_resolucao.value = NOVA
        res_titulo.value = pendencia.titulo
        res_descricao.value = ""
        res_categoria.value = pendencia.categoria if pendencia.categoria in CATEGORIAS else "Geral"
        res_impacto.value = "Médio"
        res_justificativa.value = ""
        res_observacao.value = ""
        mensagem_resolver.value = ""
        caixa_nova.visible, caixa_existente.visible = True, False
        page.show_dialog(modal_resolver)

    def confirmar_resolver(_):
        try:
            if modo_resolucao.value == NOVA:
                resolver_pendencia(
                    pendencia_atual.id,
                    usuario.nome_completo,
                    usuario_id=usuario.id,
                    nova_decisao={
                        "titulo": res_titulo.value,
                        "descricao": res_descricao.value,
                        "categoria": res_categoria.value,
                        "impacto": res_impacto.value,
                        "justificativa": res_justificativa.value,
                    },
                    observacao=res_observacao.value,
                )
            else:
                if not res_decisao.value:
                    raise ValueError("Escolha a decisão que resolve a pendência.")
                resolver_pendencia(
                    pendencia_atual.id,
                    usuario.nome_completo,
                    usuario_id=usuario.id,
                    decisao_id=int(res_decisao.value),
                    observacao=res_observacao.value,
                )
        except (ValueError, PermissionError) as erro:
            mensagem_resolver.value = str(erro)
            page.update()
            return
        page.pop_dialog()
        carregar()

    modal_resolver = ft.AlertDialog(
        **opcoes_dialogo(page),
        title=ft.Text(""),
        content=ft.Container(
            width=largura_dialogo(page, 650),
            content=ft.Column(
                tight=True,
                scroll=ft.ScrollMode.AUTO,
                controls=[
                    modo_resolucao,
                    caixa_nova,
                    caixa_existente,
                    res_observacao,
                    mensagem_resolver,
                ],
            ),
        ),
        actions=[
            ft.TextButton(content="Voltar", on_click=lambda _: page.pop_dialog()),
            ft.Button(content="Marcar como resolvida", icon=ft.Icons.CHECK_CIRCLE, on_click=confirmar_resolver),
        ],
    )

    # ---------- Cancelar (o assunto deixou de precisar de decisão) ----------
    input_motivo = ft.TextField(label="Motivo do cancelamento", multiline=True, min_lines=2)
    mensagem_cancelar = ft.Text("", color=ft.Colors.ERROR, size=12)

    def abrir_cancelar(pendencia):
        nonlocal pendencia_atual
        pendencia_atual = pendencia
        modal_cancelar.title = ft.Text(f"Cancelar {_codigo(pendencia)}?")
        input_motivo.value = ""
        mensagem_cancelar.value = ""
        page.show_dialog(modal_cancelar)

    def confirmar_cancelar(_):
        try:
            cancelar_pendencia(
                pendencia_atual.id, input_motivo.value, usuario.nome_completo, usuario_id=usuario.id
            )
        except (ValueError, PermissionError) as erro:
            mensagem_cancelar.value = str(erro)
            page.update()
            return
        page.pop_dialog()
        carregar()

    modal_cancelar = ft.AlertDialog(
        **opcoes_dialogo(page),
        title=ft.Text(""),
        content=ft.Container(
            width=largura_dialogo(page, 450),
            content=ft.Column(
                tight=True,
                controls=[
                    ft.Text(
                        "Use quando o assunto deixou de precisar de decisão. Ele continua no "
                        "histórico (filtro Canceladas) e pode ser reaberto.",
                        size=12,
                        color=ft.Colors.ON_SURFACE_VARIANT,
                    ),
                    input_motivo,
                    mensagem_cancelar,
                ],
            ),
        ),
        actions=[
            ft.TextButton(content="Voltar", on_click=lambda _: page.pop_dialog()),
            ft.Button(content="Cancelar pendência", icon=ft.Icons.BLOCK, on_click=confirmar_cancelar),
        ],
    )

    def reabrir(pendencia):
        try:
            reabrir_pendencia(pendencia.id, usuario_id=usuario.id)
        except (ValueError, PermissionError) as erro:
            resumo.value = str(erro)
            page.update()
            return
        carregar()

    # ---------- Lista ----------
    def card(pendencia, atas, decisoes, hoje):
        cor = tema.CORES_SITUACAO.get(pendencia.status, "#BDBDBD")
        detalhes = [f"Categoria: {pendencia.categoria}"]
        if pendencia.responsavel:
            detalhes.append(f"Responsável: {pendencia.responsavel}")
        atrasada = (
            pendencia.status == PENDENCIA_ABERTA and pendencia.prazo is not None and pendencia.prazo < hoje
        )
        controles = [
            ft.Row(
                wrap=True,
                controls=[
                    tema.selo(pendencia.status, cor),
                    ft.Text(
                        f"{_codigo(pendencia)} · {pendencia.titulo}",
                        size=16,
                        weight=ft.FontWeight.BOLD,
                    ),
                ],
            ),
        ]
        if pendencia.descricao and pendencia.descricao.strip() != pendencia.titulo.strip():
            controles.append(ft.Text(pendencia.descricao, size=14))
        linha_info = [ft.Text(" | ".join(detalhes), size=13)]
        if pendencia.prazo:
            linha_info.append(
                ft.Text(
                    f"Prazo: {pendencia.prazo:%d/%m/%Y}" + (" (atrasada)" if atrasada else ""),
                    size=13,
                    color=ft.Colors.ERROR if atrasada else None,
                    weight=ft.FontWeight.BOLD if atrasada else None,
                )
            )
        controles.append(ft.Row(wrap=True, controls=linha_info))

        origem = atas.get(pendencia.reuniao_id)
        quando = _hora_local(pendencia.data_criacao).strftime("%d/%m/%Y")
        if origem:
            texto_origem = f"Levantada na Ata {origem[0]:02d} - {origem[1]} ({quando})"
        else:
            texto_origem = f"Registrada por {pendencia.autor or '-'} em {quando}"
        linha_origem = [ft.Text(texto_origem, size=11, color=ft.Colors.ON_SURFACE_VARIANT)]
        if origem and on_open_ata:
            async def abrir_ata(_, ata_id=pendencia.reuniao_id):
                await on_open_ata(ata_id)

            linha_origem.append(ft.TextButton(content="Abrir ata", on_click=abrir_ata))
        controles.append(ft.Row(wrap=True, controls=linha_origem))

        if pendencia.status != PENDENCIA_ABERTA:
            data = (
                _hora_local(pendencia.data_resolucao).strftime("%d/%m/%Y")
                if pendencia.data_resolucao
                else ""
            )
            if pendencia.status == PENDENCIA_RESOLVIDA:
                decisao = decisoes.get(pendencia.decisao_id)
                alvo = (
                    f"D-{decisao.numero:03d} · {decisao.titulo}" if decisao and decisao.numero
                    else (decisao.titulo if decisao else "decisão não encontrada")
                )
                texto = f"Resolvida por {pendencia.resolvida_por} em {data} → {alvo}"
            else:
                texto = f"Cancelada por {pendencia.resolvida_por} em {data}"
            controles.append(ft.Text(texto, size=13, color=cor))
            if pendencia.resolucao:
                controles.append(ft.Text(pendencia.resolucao, size=12, color=ft.Colors.ON_SURFACE_VARIANT, italic=True))

        if pode_editar:
            if pendencia.status == PENDENCIA_ABERTA:
                acoes = [
                    ft.TextButton(content="Editar", icon=ft.Icons.EDIT,
                                  on_click=lambda _, p=pendencia: abrir_formulario(p)),
                    ft.TextButton(content="Cancelar", icon=ft.Icons.BLOCK,
                                  on_click=lambda _, p=pendencia: abrir_cancelar(p)),
                    ft.Button(content="Resolver", icon=ft.Icons.CHECK_CIRCLE,
                              on_click=lambda _, p=pendencia: abrir_resolver(p)),
                ]
            else:
                acoes = [
                    ft.TextButton(content="Reabrir", icon=ft.Icons.REPLAY,
                                  on_click=lambda _, p=pendencia: reabrir(p)),
                ]
            controles.append(ft.Divider(height=1))
            controles.append(ft.Row(wrap=True, alignment=ft.MainAxisAlignment.END, controls=acoes))

        return ft.Card(
            content=ft.Container(
                padding=15,
                border=ft.Border.only(left=ft.BorderSide(4, cor)),
                content=ft.Column(controls=controles),
            )
        )

    def carregar():
        hoje = datetime.date.today()
        status = None if filtro_status.value in (None, "", TODAS) else filtro_status.value
        pendencias = listar_pendencias(projeto.id, status=status, termo=campo_busca.value or "")
        abertas = listar_pendencias(projeto.id, status=PENDENCIA_ABERTA)
        atrasadas = sum(1 for p in abertas if p.prazo and p.prazo < hoje)
        resumo.value = f"{len(abertas)} pendência(s) em aberto" + (
            f" · {atrasadas} com prazo vencido" if atrasadas else ""
        )
        atas = {r.id: (r.numero, r.titulo) for r in listar_reunioes_projeto(projeto.id)}
        decisoes = {d.id: d for d in buscar_decisoes_projeto(projeto.id, "")}

        lista.controls.clear()
        if not pendencias:
            if (campo_busca.value or "").strip():
                vazio = "Nenhuma pendência encontrada para a busca."
            elif status == PENDENCIA_ABERTA:
                vazio = (
                    "Nenhum assunto aguardando decisão. Cadastre em '+ Nova pendência' ou use "
                    "linhas [P] nas atas de reunião."
                )
            else:
                vazio = "Nenhuma pendência nesta situação."
            lista.controls.append(ft.Text(vazio, color=ft.Colors.ON_SURFACE_VARIANT))
        for pendencia in pendencias:
            lista.controls.append(card(pendencia, atas, decisoes, hoje))
        page.update()

    header = ft.Container(
        padding=ft.Padding.symmetric(horizontal=18, vertical=14),
        bgcolor=ft.Colors.SURFACE_CONTAINER,
        border_radius=14,
        content=ft.ResponsiveRow(
            controls=[
                ft.Column(
                    col=col(12, md=5),
                    controls=[
                        ft.Text("Pendências de Decisão", size=22, weight=ft.FontWeight.BOLD),
                        ft.Text(f"Projeto Ativo: {projeto.nome}", size=14, color=ft.Colors.PRIMARY),
                        resumo,
                    ],
                ),
                ft.Row(
                    col=col(12, md=7),
                    wrap=True,
                    alignment=ft.MainAxisAlignment.END,
                    controls=[
                        ft.IconButton(icon=ft.Icons.HOME, tooltip="Ir para a linha do tempo", on_click=on_voltar),
                        tema.botao_secundario("Linha do tempo", ft.Icons.TIMELINE, on_voltar),
                        tema.botao_destaque(
                            rotulo(page, "+ Nova Pendência", "+ Pendência"),
                            ft.Icons.ADD_CIRCLE_OUTLINE,
                            lambda _: abrir_formulario(None),
                            visible=pode_editar,
                        ),
                        ft.IconButton(icon=ft.Icons.LOGOUT, tooltip="Sair", on_click=on_logout),
                    ],
                ),
            ],
        ),
    )

    carregar()
    return ft.View(
        route="/pendencias",
        controls=[
            header,
            ft.Divider(height=24, thickness=1, color=ft.Colors.OUTLINE_VARIANT),  # ações | busca
            ft.ResponsiveRow([campo_busca, filtro_status]),
            ft.Divider(),
            lista,
        ],
    )

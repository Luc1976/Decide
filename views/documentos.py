"""Documentos de referência: checklist dos arquivos e informações recebidas do cliente.

Aberta pela Ficha do Empreendimento. Cada item tem situação (Recebido / Pendente / N/A),
observação e arquivos anexos. Itens padrão nascem com o projeto; a equipe acrescenta outros.
Leitor (cliente) acompanha sem alterar. Regras em nucleo/servicos/documentos.py.
"""
import datetime
import inspect
import uuid
from pathlib import Path
from urllib.parse import quote

import flet as ft

import tema
from config import UPLOAD_DIR
from database import (
    anexar_documento,
    atualizar_documento,
    criar_documento,
    documento_tem_anexo,
    excluir_documento,
    listar_documentos,
    nivel_no_projeto,
    remover_anexo_documento,
)
from layout import col, largura_dialogo, opcoes_dialogo, rotulo
from models import NIVEL_PAPEL
from nucleo.armazenamento import TAMANHO_MAXIMO_ANEXO, armazenamento_padrao, nome_seguro
from nucleo.servicos.documentos import anexos_do_documento, resumo
from nucleo.tabelas import DOC_NA, DOC_PENDENTE, DOC_RECEBIDO
from seguranca import assinar_token, segredo_do_servidor

TODOS = "Todos"
ICONES = {DOC_RECEBIDO: ft.Icons.CHECK_CIRCLE, DOC_PENDENTE: ft.Icons.SCHEDULE, DOC_NA: ft.Icons.BLOCK}
FILTROS = {TODOS: None, "Pendentes": DOC_PENDENTE, "Recebidos": DOC_RECEBIDO, "N/A": DOC_NA}


def texto_resumo(contagem: dict) -> str:
    partes = [f"{contagem[DOC_RECEBIDO]} de {contagem['aplicaveis']} recebidos",
              f"{contagem[DOC_PENDENTE]} pendente(s)"]
    if contagem[DOC_NA]:
        partes.append(f"{contagem[DOC_NA]} não se aplica(m)")
    return " · ".join(partes)


def build_documentos_view(page, projeto, usuario, on_logout, on_voltar):
    pode_editar = nivel_no_projeto(usuario.id, projeto.id) >= NIVEL_PAPEL["Editor"]
    file_picker = ft.FilePicker()

    resumo_texto = ft.Text("", size=13, color=ft.Colors.ON_SURFACE_VARIANT)
    progresso = ft.ProgressBar(value=0, bar_height=8, border_radius=4, color=tema.sucesso(page),
                               bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST)
    mensagem = ft.Text("", size=12, color=ft.Colors.ERROR)
    filtro = ft.Dropdown(
        label="Mostrar",
        value=TODOS,
        col=col(12, md=4),
        options=[ft.DropdownOption(key=k, text=k) for k in FILTROS],
        on_select=lambda _: carregar(),
    )
    lista = ft.ListView(expand=True, spacing=10, padding=ft.Padding.only(top=6, bottom=24))

    # ---------------------------------------------------------------- arquivos
    async def abrir_arquivo(chave):
        if page.web:
            if not documento_tem_anexo(projeto.id, chave):
                return
            token = assinar_token(segredo_do_servidor(), {"p": chave}, validade_s=300)
            resultado = page.launch_url(f"/anexo/{quote(token)}")
            if inspect.isawaitable(resultado):
                await resultado
        else:
            from views.timeline import abrir_arquivo_nativo

            caminho = armazenamento_padrao().caminho_local(chave)
            if caminho:
                abrir_arquivo_nativo(str(caminho))

    async def anexar(doc):
        from views.timeline import _aguardar_upload

        arquivos = await file_picker.pick_files(allow_multiple=True, with_data=not page.web)
        if not arquivos:
            return
        mensagem.color = tema.aviso(page)
        mensagem.value = "Enviando arquivo(s)..."
        page.update()
        erros = []
        for arquivo in arquivos:
            if arquivo.size and arquivo.size > TAMANHO_MAXIMO_ANEXO:
                erros.append(f"{arquivo.name}: passa de {TAMANHO_MAXIMO_ANEXO // (1024 * 1024)} MB")
                continue
            relativo = f"p{projeto.id}/{uuid.uuid4().hex}/{nome_seguro(arquivo.name)}"
            chave = f"uploads/{relativo}"
            try:
                if page.web:
                    await file_picker.upload([ft.FilePickerUploadFile(
                        id=arquivo.id, name=arquivo.name, upload_url=page.get_upload_url(relativo, 600),
                    )])
                    if not await _aguardar_upload(UPLOAD_DIR / relativo, arquivo.size):
                        raise TimeoutError("o envio não terminou")
                else:
                    dados = arquivo.bytes if arquivo.bytes is not None else Path(arquivo.path).read_bytes()
                    armazenamento_padrao().salvar(chave, dados)
                anexar_documento(doc.id, chave, usuario.id)
            except (OSError, ValueError, PermissionError, TimeoutError) as erro:
                armazenamento_padrao().apagar([chave])
                erros.append(f"{arquivo.name}: {erro}")
        mensagem.color = ft.Colors.ERROR
        mensagem.value = "Não foi possível anexar: " + "; ".join(erros) if erros else ""
        carregar()

    # ---------------------------------------------------------------- confirmação genérica
    texto_confirmar = ft.Text("")
    acao_confirmada = {"fazer": None}

    def confirmar(titulo, texto, ao_confirmar):
        modal_confirmar.title = ft.Text(titulo)
        texto_confirmar.value = texto
        acao_confirmada["fazer"] = ao_confirmar
        page.show_dialog(modal_confirmar)

    def executar_confirmado(_):
        page.pop_dialog()
        fazer = acao_confirmada["fazer"]
        if fazer:
            fazer()

    modal_confirmar = ft.AlertDialog(
        **opcoes_dialogo(page),
        title=ft.Text(""),
        content=ft.Container(width=largura_dialogo(page, 440), content=texto_confirmar),
        actions=[
            ft.TextButton(content="Cancelar", on_click=lambda _: page.pop_dialog()),
            ft.Button(content="Confirmar", style=ft.ButtonStyle(bgcolor=ft.Colors.ERROR, color=ft.Colors.ON_ERROR),
                      on_click=executar_confirmado),
        ],
    )

    def _tentar(acao):
        try:
            acao()
            mensagem.value = ""
        except (ValueError, PermissionError) as erro:
            mensagem.color = ft.Colors.ERROR
            mensagem.value = str(erro)
        carregar()

    def remover_arquivo(doc, indice, nome):
        def fazer():
            def acao():
                chave = remover_anexo_documento(doc.id, indice, usuario.id)
                armazenamento_padrao().apagar([chave])
            _tentar(acao)
        confirmar("Remover arquivo", f"Remover “{nome}” de “{doc.nome}”? O arquivo será apagado.", fazer)

    def excluir(doc):
        def fazer():
            def acao():
                armazenamento_padrao().apagar(excluir_documento(doc.id, usuario.id))
            _tentar(acao)
        confirmar("Excluir item", f"Excluir “{doc.nome}” da lista? Os arquivos anexados também serão apagados.",
                  fazer)

    # ---------------------------------------------------------------- novo / editar item
    input_nome = ft.TextField(label="Documento ou informação", hint_text="Ex.: Licença ambiental prévia")
    input_obs = ft.TextField(label="Observação (opcional)", multiline=True, min_lines=2, max_lines=5,
                             hint_text="Ex.: recebido por e-mail do cliente, revisão R02")
    mensagem_form = ft.Text("", size=12, color=ft.Colors.ERROR)
    editando = {"doc": None}

    def abrir_formulario(doc=None):
        editando["doc"] = doc
        modal_form.title = ft.Text("Novo item" if doc is None else "Editar item")
        input_nome.value = doc.nome if doc else ""
        input_nome.disabled = bool(doc and doc.padrao)  # itens padrão mantêm o nome
        input_nome.helper = "Item da lista padrão: o nome não muda." if doc and doc.padrao else None
        input_obs.value = doc.observacao if doc else ""
        mensagem_form.value = ""
        page.show_dialog(modal_form)

    def salvar_formulario(_):
        doc = editando["doc"]
        try:
            if doc is None:
                criar_documento(projeto.id, input_nome.value, input_obs.value, usuario.id)
            else:
                atualizar_documento(doc.id, usuario.id, observacao=input_obs.value or "",
                                    nome=None if doc.padrao else input_nome.value)
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
            width=largura_dialogo(page, 520),
            content=ft.Column(tight=True, controls=[input_nome, input_obs, mensagem_form]),
        ),
        actions=[
            ft.TextButton(content="Cancelar", on_click=lambda _: page.pop_dialog()),
            ft.Button(content="Salvar", icon=ft.Icons.SAVE, on_click=salvar_formulario),
        ],
    )

    # ---------------------------------------------------------------- cartão do item
    def mudar_situacao(doc, evento):
        nova = (evento.control.selected or [doc.situacao])[0]
        _tentar(lambda: atualizar_documento(doc.id, usuario.id, situacao=nova))

    def cartao(doc):
        if pode_editar:
            situacao = ft.SegmentedButton(
                selected=[doc.situacao],
                show_selected_icon=False,
                segments=[
                    ft.Segment(value=s, label=ft.Text("N/A" if s == DOC_NA else s), icon=ft.Icon(ICONES[s]))
                    for s in (DOC_RECEBIDO, DOC_PENDENTE, DOC_NA)
                ],
                on_change=lambda e, d=doc: mudar_situacao(d, e),
            )
        else:
            situacao = tema.selo(doc.situacao, tema.CORES_DOCUMENTO[doc.situacao], ICONES[doc.situacao])

        detalhes = []
        if doc.situacao == DOC_RECEBIDO and doc.data_recebimento:
            detalhes.append(ft.Text(
                f"Recebido em {doc.data_recebimento:%d/%m/%Y}" + (f" · marcado por {doc.recebido_por}" if doc.recebido_por else ""),
                size=12, color=ft.Colors.ON_SURFACE_VARIANT,
            ))
        if doc.observacao:
            detalhes.append(ft.Text(doc.observacao, size=13))

        arquivos = []
        for i, chave in enumerate(anexos_do_documento(doc)):
            nome = chave.rsplit("/", 1)[-1]
            arquivos.append(ft.Row(spacing=0, tight=True, controls=[
                ft.TextButton(content=nome, icon=ft.Icons.ATTACH_FILE,
                              on_click=lambda _, c=chave: abrir_arquivo(c)),
                *([ft.IconButton(icon=ft.Icons.CLOSE, icon_size=16, tooltip="Remover arquivo",
                                 on_click=lambda _, d=doc, i=i, n=nome: remover_arquivo(d, i, n))]
                  if pode_editar else []),
            ]))

        acoes = []
        if pode_editar:
            acoes = [
                ft.TextButton(content="Anexar arquivo", icon=ft.Icons.UPLOAD_FILE,
                              on_click=lambda _, d=doc: anexar(d)),
                ft.TextButton(content="Editar", icon=ft.Icons.EDIT_OUTLINED,
                              on_click=lambda _, d=doc: abrir_formulario(d)),
            ]
            if not doc.padrao:
                acoes.append(ft.TextButton(content="Excluir", icon=ft.Icons.DELETE_OUTLINE,
                                           style=ft.ButtonStyle(color=ft.Colors.ERROR, icon_color=ft.Colors.ERROR),
                                           on_click=lambda _, d=doc: excluir(d)))

        apagado = doc.situacao == DOC_NA
        return ft.Container(
            padding=14,
            border_radius=12,
            bgcolor=ft.Colors.SURFACE_CONTAINER,
            border=ft.Border.only(left=ft.BorderSide(4, tema.CORES_DOCUMENTO[doc.situacao])),
            opacity=0.75 if apagado else 1,
            content=ft.Column(
                spacing=8,
                controls=[
                    ft.Row(wrap=True, controls=[
                        ft.Icon(ICONES[doc.situacao], color=tema.cor_documento_forte(page, doc.situacao)),
                        ft.Text(doc.nome, size=16, weight=ft.FontWeight.BOLD,
                                color=ft.Colors.ON_SURFACE_VARIANT if apagado else None),
                        *([] if doc.padrao else [ft.Text("(acrescentado)", size=11, color=ft.Colors.ON_SURFACE_VARIANT)]),
                    ]),
                    situacao,
                    *detalhes,
                    *([ft.Column(spacing=0, controls=arquivos)] if arquivos else []),
                    *([ft.Row(wrap=True, spacing=0, controls=acoes)] if acoes else []),
                ],
            ),
        )

    def carregar():
        documentos = listar_documentos(projeto.id, usuario.id)
        contagem = resumo(documentos)
        resumo_texto.value = texto_resumo(contagem)
        progresso.value = contagem[DOC_RECEBIDO] / contagem["aplicaveis"] if contagem["aplicaveis"] else 1
        escolhido = FILTROS.get(filtro.value)
        visiveis = [d for d in documentos if not escolhido or d.situacao == escolhido]
        lista.controls = [cartao(d) for d in visiveis] or [
            ft.Text("Nenhum item nesta situação.", color=ft.Colors.ON_SURFACE_VARIANT)
        ]
        page.update()

    header = ft.Container(
        padding=ft.Padding.symmetric(horizontal=18, vertical=14),
        bgcolor=ft.Colors.SURFACE_CONTAINER,
        border_radius=14,
        content=ft.ResponsiveRow(
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Column(
                    col=col(12, md=6),
                    spacing=4,
                    controls=[
                        ft.Text("Documentos de Referência", size=22, weight=ft.FontWeight.BOLD),
                        ft.Text(f"Projeto Ativo: {projeto.nome}", size=14, color=ft.Colors.PRIMARY),
                        resumo_texto,
                        progresso,
                    ],
                ),
                ft.Row(
                    col=col(12, md=6),
                    wrap=True,
                    alignment=ft.MainAxisAlignment.END,
                    controls=[
                        tema.botao_secundario(rotulo(page, "Ficha do Empreendimento", "Ficha"),
                                              ft.Icons.ASSIGNMENT, on_voltar),
                        tema.botao_destaque(rotulo(page, "+ Novo Item", "+ Item"), ft.Icons.ADD_CIRCLE_OUTLINE,
                                            lambda _: abrir_formulario(None), visible=pode_editar),
                        ft.IconButton(icon=ft.Icons.LOGOUT, tooltip="Sair", on_click=on_logout),
                    ],
                ),
            ],
        ),
    )

    carregar()
    return ft.View(
        route="/documentos",
        controls=[
            header,
            ft.Divider(height=24, thickness=1, color=ft.Colors.OUTLINE_VARIANT),
            ft.ResponsiveRow([filtro]),
            mensagem,
            lista,
        ],
        services=[file_picker],
    )

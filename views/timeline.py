import asyncio
import datetime
import inspect
import json
import os
import platform
import shutil
import subprocess
import uuid
from pathlib import Path
from urllib.parse import quote

import flet as ft
from database import (
    Reuniao,
    adicionar_decisao,
    alteracoes_ficha_por_decisao,
    alterar_propria_senha,
    anexo_pertence_ao_projeto,
    atualizar_projeto,
    buscar_decisoes_projeto,
    buscar_reunioes_projeto,
    campos_da_ficha,
    listar_caracteristicas,
    criar_projeto,
    criar_usuario,
    definir_membro,
    listar_decisoes_reuniao,
    listar_membros,
    listar_projetos_do_usuario,
    listar_reunioes_projeto,
    listar_usuarios,
    nivel_no_projeto,
    remover_membro,
    resumo_projeto,
    excluir_projeto,
)
from config import NOME_APP, RELATORIOS_DIR, UPLOAD_DIR, apagar_anexos, limpar_relatorios_antigos
from layout import col, largura_dialogo, opcoes_dialogo, rotulo
from models import CATEGORIAS, IMPACTOS, NIVEL_PAPEL, PAPEIS
from seguranca import assinar_token, segredo_do_servidor

PASTA_ANEXOS = "anexos_projetos"
CORES_CATEGORIA = {
    "Arquitetura": ft.Colors.BLUE_400,
    "Estrutura": ft.Colors.TEAL_400,
    "Orçamento": ft.Colors.PURPLE_400,
    "Geral": ft.Colors.GREY_600,
}
CORES_IMPACTO = {
    "Alto": ft.Colors.RED_400,
    "Médio": ft.Colors.AMBER_600,
    "Baixo": ft.Colors.GREEN_400,
}


def abrir_arquivo_nativo(caminho_arquivo):
    if platform.system() == "Windows":
        os.startfile(caminho_arquivo)
    elif platform.system() == "Darwin":
        subprocess.Popen(["open", caminho_arquivo])
    else:
        subprocess.Popen(["xdg-open", caminho_arquivo])


async def _aguardar_upload(destino, tamanho_esperado, tempo_maximo=180):
    """Espera o arquivo enviado pelo navegador terminar de chegar em UPLOAD_DIR.
    Considera pronto quando existe e tem o tamanho esperado (ou parou de crescer)."""
    ultimo_tamanho, estavel = -1, 0
    for _ in range(int(tempo_maximo / 0.3)):
        if destino.is_file():
            tamanho = destino.stat().st_size
            if tamanho_esperado and tamanho >= tamanho_esperado:
                return True
            estavel = estavel + 1 if tamanho == ultimo_tamanho else 0
            ultimo_tamanho = tamanho
            if not tamanho_esperado and estavel >= 4:
                return True
        await asyncio.sleep(0.3)
    return False


def _converter_data(texto):
    """'dd/mm/aaaa' -> date. Vazio devolve None; formato inválido levanta ValueError."""
    texto = (texto or "").strip()
    if not texto:
        return None
    return datetime.datetime.strptime(texto, "%d/%m/%Y").date()


def build_timeline_view(
    page,
    projeto,
    usuario,
    on_logout,
    on_project_created,
    on_project_selected=None,
    on_open_atas=None,
    on_open_ficha=None,
    on_project_deleted=None,
):
    # O FilePicker é um "service" e pertence à View: é passado em ft.View(services=[...])
    # no return. NÃO use page.services aqui, pois ele exige que page.views não esteja vazia.
    file_picker = ft.FilePicker()

    input_nome_projeto = ft.TextField(label="Nome do projeto")
    input_cliente_projeto = ft.TextField(label="Cliente")
    input_descricao_projeto = ft.TextField(
        label="Descrição", multiline=True, min_lines=2
    )
    mensagem_projeto = ft.Text("")

    projetos = listar_projetos_do_usuario(usuario.id)  # só os projetos com acesso
    if projeto is None or all(p.id != projeto.id for p in projetos):
        projeto = projetos[0]  # o app.py garante que existe ao menos um projeto

    # Nível de acesso no projeto atual: 1 Leitor, 2 Editor, 3 Responsável, 4 administrador.
    nivel = nivel_no_projeto(usuario.id, projeto.id)
    pode_criar_projeto = bool(usuario.admin or getattr(usuario, "pode_criar_projetos", False))

    projeto_info = ft.Text(
        f"Projeto Ativo: {projeto.nome}",
        size=14,
        color=ft.Colors.BLUE_200,
    )
    acesso_info = ft.Text("", size=12, color=ft.Colors.GREY_400)

    def ao_selecionar_projeto(evento):
        nonlocal projeto
        escolhido = next(
            (p for p in projetos if str(p.id) == evento.control.value), None
        )
        if escolhido is None:
            return
        projeto = escolhido
        nonlocal nivel
        nivel = nivel_no_projeto(usuario.id, projeto.id)
        projeto_info.value = f"Projeto Ativo: {projeto.nome}"
        aplicar_permissoes()
        if on_project_selected:
            on_project_selected(projeto)  # lembra a escolha no app.py
        carregar_timeline()

    seletor_projeto = ft.Dropdown(
        label="Projeto",
        options=[
            ft.DropdownOption(key=str(p.id), text=p.nome) for p in projetos
        ],
        value=str(projeto.id),
        col=col(12, md=4),
        on_select=ao_selecionar_projeto,
    )
    campo_busca = ft.TextField(
        label="Buscar decisões",
        hint_text="Título, descrição, categoria, responsável ou anexo",
        prefix_icon=ft.Icons.SEARCH,
        col=col(12, md=8),
        on_change=lambda _: carregar_timeline(),
    )
    timeline_list = ft.ListView(expand=True, spacing=15, padding=10)

    async def salvar_projeto(_):
        nome = (input_nome_projeto.value or "").strip()
        cliente = (input_cliente_projeto.value or "").strip()
        if not nome or not cliente:
            mensagem_projeto.value = "Preencha o nome do projeto e o cliente."
            page.update()
            return

        try:
            novo_projeto = criar_projeto(
                nome, cliente, input_descricao_projeto.value, criador_id=usuario.id
            )
        except Exception as erro:
            mensagem_projeto.value = f"Não foi possível criar o projeto: {erro}"
            page.update()
            return

        # Fecha a janela e deixa o navegador processar o fechamento ANTES de trocar a tela;
        # trocar a tela no mesmo instante fazia a janela ficar aberta.
        page.pop_dialog()
        page.update()
        await asyncio.sleep(0.2)
        on_project_created(novo_projeto)

    modal_projeto = ft.AlertDialog(
        **opcoes_dialogo(page),
        title=ft.Text("Criar novo projeto"),
        content=ft.Container(
            width=largura_dialogo(page, 500),
            content=ft.Column(
                tight=True,
                controls=[
                    input_nome_projeto,
                    input_cliente_projeto,
                    input_descricao_projeto,
                    mensagem_projeto,
                ],
            ),
        ),
        actions=[
            ft.TextButton(
                content="Cancelar", on_click=lambda _: page.pop_dialog()
            ),
            ft.Button(content="Criar projeto", on_click=salvar_projeto),
        ],
    )
    # ---------- Editar projeto ----------
    input_edit_nome = ft.TextField(label="Nome do projeto")
    input_edit_cliente = ft.TextField(label="Cliente")
    input_edit_descricao = ft.TextField(
        label="Descrição", multiline=True, min_lines=2
    )
    mensagem_edicao = ft.Text("", color=ft.Colors.RED_400)

    def abrir_edicao_projeto(_):
        input_edit_nome.value = projeto.nome
        input_edit_cliente.value = projeto.cliente
        input_edit_descricao.value = projeto.descricao or ""
        mensagem_edicao.value = ""
        page.show_dialog(modal_edicao_projeto)

    async def salvar_edicao_projeto(_):
        try:
            atualizado = atualizar_projeto(
                projeto.id,
                input_edit_nome.value,
                input_edit_cliente.value,
                input_edit_descricao.value,
                usuario_id=usuario.id,
            )
        except (ValueError, PermissionError) as erro:
            mensagem_edicao.value = str(erro)
            page.update()
            return
        page.pop_dialog()
        page.update()
        await asyncio.sleep(0.2)
        on_project_created(atualizado)  # reconstrói a tela com o projeto atualizado

    modal_edicao_projeto = ft.AlertDialog(
        **opcoes_dialogo(page),
        title=ft.Text("Editar projeto"),
        content=ft.Container(
            width=largura_dialogo(page, 500),
            content=ft.Column(
                tight=True,
                controls=[
                    input_edit_nome,
                    input_edit_cliente,
                    input_edit_descricao,
                    mensagem_edicao,
                ],
            ),
        ),
        actions=[
            ft.TextButton(content="Cancelar", on_click=lambda _: page.pop_dialog()),
            ft.Button(content="Salvar alterações", on_click=salvar_edicao_projeto),
        ],
    )

    # ---------- Relatório de decisões em PDF (qualquer pessoa com acesso ao projeto) ----------
    TODAS = "__todas__"
    rel_data_ini = ft.TextField(label="De (dd/mm/aaaa)", col=col(12, md=6))
    rel_data_fim = ft.TextField(label="Até (dd/mm/aaaa)", col=col(12, md=6))
    rel_categoria = ft.Dropdown(label="Categoria", options=[], value=TODAS)
    rel_incluir_ficha = ft.Checkbox(label="Incluir a ficha do empreendimento", value=True)
    rel_incluir_detalhes = ft.Checkbox(
        label="Incluir justificativa, alternativas e checklist", value=True
    )
    rel_mensagem = ft.Text("", size=12)
    # O botão de baixar recebe o endereço depois que o PDF é gerado; abrir direto pelo botão
    # (e não por código) evita o bloqueio de pop-ups dos navegadores de celular.
    btn_baixar_relatorio = ft.Button(
        content="Baixar PDF", icon=ft.Icons.DOWNLOAD, visible=False
    )

    def abrir_relatorio(_):
        categorias = list(CATEGORIAS)
        for d in buscar_decisoes_projeto(projeto.id, ""):
            if d.categoria not in categorias:
                categorias.append(d.categoria)
        rel_categoria.options = [ft.DropdownOption(key=TODAS, text="Todas as categorias")] + [
            ft.DropdownOption(key=c) for c in categorias
        ]
        rel_categoria.value = TODAS
        rel_data_ini.value = ""
        rel_data_fim.value = ""
        rel_mensagem.value = ""
        btn_baixar_relatorio.visible = False
        page.show_dialog(modal_relatorio)

    async def gerar_relatorio(_):
        btn_baixar_relatorio.visible = False
        rel_mensagem.color = ft.Colors.RED_400
        try:
            data_ini = _converter_data(rel_data_ini.value)
            data_fim = _converter_data(rel_data_fim.value)
        except ValueError:
            rel_mensagem.value = "Use as datas no formato dd/mm/aaaa."
            page.update()
            return
        if data_ini and data_fim and data_ini > data_fim:
            rel_mensagem.value = "A data inicial é depois da data final."
            page.update()
            return
        if nivel_no_projeto(usuario.id, projeto.id) < NIVEL_PAPEL["Leitor"]:
            rel_mensagem.value = "Você não tem acesso a este projeto."
            page.update()
            return

        categoria = None if rel_categoria.value in (None, "", TODAS) else rel_categoria.value
        decisoes = [
            d
            for d in buscar_decisoes_projeto(projeto.id, "")
            if (not data_ini or d.data_decisao >= data_ini)
            and (not data_fim or d.data_decisao <= data_fim)
            and (not categoria or d.categoria == categoria)
        ]
        if not decisoes:
            rel_mensagem.value = "Nenhuma decisão encontrada para esses filtros."
            page.update()
            return

        partes_filtro = []
        if data_ini or data_fim:
            partes_filtro.append(
                f"Período: {data_ini:%d/%m/%Y}" if data_ini else "Período: início"
            )
            partes_filtro[-1] += f" a {data_fim:%d/%m/%Y}" if data_fim else " em diante"
        if categoria:
            partes_filtro.append(f"Categoria: {categoria}")
        filtros_texto = " | ".join(partes_filtro) or "Todas as decisões"

        try:
            from relatorio_pdf import gerar_relatorio_pdf, nome_do_arquivo
        except ImportError:
            rel_mensagem.value = (
                "O pacote 'reportlab' não está instalado no servidor. "
                "Inclua-o no pyproject.toml e publique de novo."
            )
            page.update()
            return

        rel_mensagem.color = ft.Colors.AMBER_600
        rel_mensagem.value = "Gerando o relatório..."
        page.update()

        nome_arquivo = nome_do_arquivo(projeto.nome, datetime.datetime.now())
        relativo = f"relatorios/{uuid.uuid4().hex}/{nome_arquivo}"
        destino = RELATORIOS_DIR.parent / relativo
        atas_por_id = {r.id: (r.numero, r.titulo) for r in listar_reunioes_projeto(projeto.id)}
        try:
            total = await asyncio.to_thread(
                gerar_relatorio_pdf,
                destino,
                projeto,
                decisoes,
                atas_por_id,
                alteracoes_ficha_por_decisao(projeto.id),
                listar_caracteristicas(projeto.id),
                usuario.nome_completo,
                filtros_texto,
                bool(rel_incluir_ficha.value),
                bool(rel_incluir_detalhes.value),
                NOME_APP,
            )
        except Exception as erro:
            rel_mensagem.color = ft.Colors.RED_400
            rel_mensagem.value = f"Não foi possível gerar o relatório: {erro}"
            page.update()
            return
        limpar_relatorios_antigos()

        rel_mensagem.color = ft.Colors.GREEN_400
        if page.web:
            token = assinar_token(segredo_do_servidor(), {"p": relativo}, validade_s=900)
            btn_baixar_relatorio.url = f"/anexo/{quote(token)}"
            btn_baixar_relatorio.visible = True
            rel_mensagem.value = f"Relatório pronto com {total} decisão(ões). Toque em Baixar PDF."
        else:
            abrir_arquivo_nativo(str(destino))
            rel_mensagem.value = f"Relatório com {total} decisão(ões) salvo em {destino}"
        page.update()

    modal_relatorio = ft.AlertDialog(
        **opcoes_dialogo(page),
        title=ft.Text("Relatório de decisões (PDF)"),
        content=ft.Container(
            width=largura_dialogo(page, 500),
            content=ft.Column(
                tight=True,
                scroll=ft.ScrollMode.AUTO,
                controls=[
                    ft.Text(
                        "Deixe as datas em branco para incluir todas as decisões.",
                        size=12,
                        color=ft.Colors.GREY_400,
                    ),
                    ft.ResponsiveRow([rel_data_ini, rel_data_fim]),
                    rel_categoria,
                    rel_incluir_ficha,
                    rel_incluir_detalhes,
                    rel_mensagem,
                    btn_baixar_relatorio,
                ],
            ),
        ),
        actions=[
            ft.TextButton(content="Fechar", on_click=lambda _: page.pop_dialog()),
            ft.Button(
                content="Gerar PDF", icon=ft.Icons.PICTURE_AS_PDF, on_click=gerar_relatorio
            ),
        ],
    )

    # ---------- Excluir projeto (Responsável ou administrador) ----------
    input_confirma_exclusao = ft.TextField(label="Digite o nome do projeto para confirmar")
    texto_exclusao = ft.Text("")
    mensagem_exclusao = ft.Text("", color=ft.Colors.RED_400, size=12)

    def abrir_exclusao_projeto(_):
        if nivel < NIVEL_PAPEL["Responsável"]:
            return
        try:
            resumo = resumo_projeto(projeto.id, usuario.id)
        except (ValueError, PermissionError):
            return
        texto_exclusao.value = (
            f'Isto apaga DEFINITIVAMENTE o projeto "{projeto.nome}" e tudo o que há nele: '
            f"{resumo['decisoes']} decisão(ões), {resumo['atas']} ata(s), "
            f"{resumo['anexos']} anexo(s), a ficha do empreendimento e o acesso de "
            f"{resumo['membros']} membro(s). Não é possível desfazer."
        )
        input_confirma_exclusao.value = ""
        mensagem_exclusao.value = ""
        page.show_dialog(modal_exclusao_projeto)

    async def confirmar_exclusao_projeto(_):
        digitado = (input_confirma_exclusao.value or "").strip().casefold()
        if digitado != projeto.nome.strip().casefold():
            mensagem_exclusao.value = "O nome digitado não confere com o nome do projeto."
            page.update()
            return
        try:
            caminhos = excluir_projeto(projeto.id, usuario.id)
        except (ValueError, PermissionError) as erro:
            mensagem_exclusao.value = str(erro)
            page.update()
            return
        apagar_anexos(caminhos)  # o banco já confirmou: agora os arquivos saem do disco
        page.pop_dialog()
        page.update()
        await asyncio.sleep(0.2)
        if on_project_deleted:
            on_project_deleted()

    modal_exclusao_projeto = ft.AlertDialog(
        **opcoes_dialogo(page),
        title=ft.Text("Excluir projeto"),
        content=ft.Container(
            width=largura_dialogo(page, 500),
            content=ft.Column(
                tight=True,
                scroll=ft.ScrollMode.AUTO,
                controls=[texto_exclusao, input_confirma_exclusao, mensagem_exclusao],
            ),
        ),
        actions=[
            ft.TextButton(content="Cancelar", on_click=lambda _: page.pop_dialog()),
            ft.Button(
                content="Excluir definitivamente",
                icon=ft.Icons.DELETE_FOREVER,
                color=ft.Colors.RED_400,
                on_click=confirmar_exclusao_projeto,
            ),
        ],
    )

    # ---------- Usuários (somente administradores) ----------
    input_user_nome = ft.TextField(label="Nome completo")
    input_user_login = ft.TextField(label="Usuário (login)")
    input_user_senha = ft.TextField(
        label="Senha (mín. 6 caracteres)", password=True, can_reveal_password=True
    )
    input_user_admin = ft.Checkbox(label="Administrador (acessa tudo e cadastra usuários)")
    input_user_pode_criar = ft.Checkbox(
        label="Pode criar projetos próprios (desmarque para clientes que só acompanham)",
        value=True,
    )
    mensagem_usuario = ft.Text("")
    lista_usuarios = ft.Column(spacing=2)

    def atualizar_lista_usuarios():
        lista_usuarios.controls = [
            ft.Text(
                f"• {u.nome_completo} ({u.username})"
                + (" — admin" if u.admin else "" if u.pode_criar_projetos else " — cliente"),
                size=12,
                color=ft.Colors.GREY_400,
            )
            for u in listar_usuarios()
        ]

    def abrir_usuarios(_):
        mensagem_usuario.value = ""
        atualizar_lista_usuarios()
        page.show_dialog(modal_usuarios)

    def salvar_usuario(_):
        if not usuario.admin:
            return
        try:
            novo = criar_usuario(
                input_user_login.value,
                input_user_senha.value,
                input_user_nome.value,
                bool(input_user_admin.value),
                bool(input_user_pode_criar.value),
            )
        except ValueError as erro:
            mensagem_usuario.color = ft.Colors.RED_400
            mensagem_usuario.value = str(erro)
            page.update()
            return
        input_user_nome.value = ""
        input_user_login.value = ""
        input_user_senha.value = ""
        input_user_admin.value = False
        input_user_pode_criar.value = True
        mensagem_usuario.color = ft.Colors.GREEN_400
        mensagem_usuario.value = f"Usuário '{novo.username}' cadastrado."
        atualizar_lista_usuarios()
        page.update()

    modal_usuarios = ft.AlertDialog(
        **opcoes_dialogo(page),
        title=ft.Text("Usuários"),
        content=ft.Container(
            width=largura_dialogo(page, 500),
            content=ft.Column(
                tight=True,
                scroll=ft.ScrollMode.AUTO,
                controls=[
                    input_user_nome,
                    input_user_login,
                    input_user_senha,
                    input_user_admin,
                    input_user_pode_criar,
                    mensagem_usuario,
                    ft.Divider(),
                    ft.Text("Usuários cadastrados", weight=ft.FontWeight.BOLD),
                    lista_usuarios,
                ],
            ),
        ),
        actions=[
            ft.TextButton(content="Fechar", on_click=lambda _: page.pop_dialog()),
            ft.Button(content="Cadastrar usuário", on_click=salvar_usuario),
        ],
    )

    arquivos_temporarios = []
    anexos_web = []  # caminhos "uploads/<id>/<nome>" já enviados pelo navegador
    dados_checklist = []
    lista_nomes_arquivos = ft.Column()
    ui_lista_checklist = ft.Column()

    # ---------- Membros do projeto (Responsável ou administrador) ----------
    input_membro_login = ft.TextField(label="Usuário (login)", col=col(12, md=7))
    input_membro_papel = ft.Dropdown(
        label="Acesso",
        options=[ft.DropdownOption(key=papel) for papel in PAPEIS],
        value="Leitor",
        col=col(12, md=5),
    )
    mensagem_membros = ft.Text("", size=12)
    lista_membros = ft.Column(spacing=4)

    def atualizar_lista_membros():
        controles = []
        for u, papel in listar_membros(projeto.id, usuario.id):

            def remover(_, alvo=u.id):
                try:
                    remover_membro(projeto.id, alvo, usuario.id)
                except (ValueError, PermissionError) as erro:
                    mensagem_membros.color = ft.Colors.RED_400
                    mensagem_membros.value = str(erro)
                    page.update()
                    return
                mensagem_membros.value = ""
                atualizar_lista_membros()
                page.update()

            controles.append(
                ft.Row(
                    controls=[
                        ft.Text(f"{u.nome_completo} ({u.username})", expand=True, size=13),
                        ft.Text(papel, size=12, color=ft.Colors.BLUE_200),
                        ft.IconButton(icon=ft.Icons.DELETE, tooltip="Remover acesso", on_click=remover),
                    ]
                )
            )
        if not controles:
            controles = [ft.Text("Nenhum membro ainda.", color=ft.Colors.GREY_400, size=12)]
        lista_membros.controls = controles

    def abrir_membros(_):
        if nivel < NIVEL_PAPEL["Responsável"]:
            return
        mensagem_membros.value = ""
        input_membro_login.value = ""
        atualizar_lista_membros()
        page.show_dialog(modal_membros)

    def salvar_membro(_):
        try:
            definir_membro(
                projeto.id, input_membro_login.value, input_membro_papel.value, usuario.id
            )
        except (ValueError, PermissionError) as erro:
            mensagem_membros.color = ft.Colors.RED_400
            mensagem_membros.value = str(erro)
            page.update()
            return
        input_membro_login.value = ""
        mensagem_membros.color = ft.Colors.GREEN_400
        mensagem_membros.value = "Acesso atualizado."
        atualizar_lista_membros()
        page.update()

    modal_membros = ft.AlertDialog(
        **opcoes_dialogo(page),
        title=ft.Text("Membros do projeto"),
        content=ft.Container(
            width=largura_dialogo(page, 560),
            content=ft.Column(
                tight=True,
                scroll=ft.ScrollMode.AUTO,
                controls=[
                    ft.Text(
                        "Leitor: acompanha decisões, atas fechadas e a ficha (ideal para clientes).\n"
                        "Editor: também registra decisões e atas e altera a ficha.\n"
                        "Responsável: também edita o projeto e gerencia os membros.",
                        size=12,
                        color=ft.Colors.GREY_400,
                    ),
                    ft.ResponsiveRow([input_membro_login, input_membro_papel]),
                    mensagem_membros,
                    ft.Divider(),
                    ft.Text("Quem tem acesso", weight=ft.FontWeight.BOLD),
                    lista_membros,
                ],
            ),
        ),
        actions=[
            ft.TextButton(content="Fechar", on_click=lambda _: page.pop_dialog()),
            ft.Button(content="Dar acesso", on_click=salvar_membro),
        ],
    )

    # ---------- Minha conta (trocar a própria senha) ----------
    input_senha_atual = ft.TextField(label="Senha atual", password=True, can_reveal_password=True)
    input_senha_nova = ft.TextField(label="Nova senha (mín. 6 caracteres)", password=True, can_reveal_password=True)
    input_senha_repetir = ft.TextField(label="Repita a nova senha", password=True, can_reveal_password=True)
    mensagem_conta = ft.Text("", size=12)

    def abrir_conta(_):
        for campo in (input_senha_atual, input_senha_nova, input_senha_repetir):
            campo.value = ""
        mensagem_conta.value = ""
        page.show_dialog(modal_conta)

    def salvar_senha(_):
        if input_senha_nova.value != input_senha_repetir.value:
            mensagem_conta.color = ft.Colors.RED_400
            mensagem_conta.value = "As senhas novas não conferem."
            page.update()
            return
        try:
            alterar_propria_senha(usuario.id, input_senha_atual.value, input_senha_nova.value)
        except ValueError as erro:
            mensagem_conta.color = ft.Colors.RED_400
            mensagem_conta.value = str(erro)
            page.update()
            return
        mensagem_conta.color = ft.Colors.GREEN_400
        mensagem_conta.value = "Senha alterada."
        for campo in (input_senha_atual, input_senha_nova, input_senha_repetir):
            campo.value = ""
        page.update()

    modal_conta = ft.AlertDialog(
        **opcoes_dialogo(page),
        title=ft.Text(f"Minha conta · {usuario.nome_completo}"),
        content=ft.Container(
            width=largura_dialogo(page, 420),
            content=ft.Column(
                tight=True,
                controls=[input_senha_atual, input_senha_nova, input_senha_repetir, mensagem_conta],
            ),
        ),
        actions=[
            ft.TextButton(content="Fechar", on_click=lambda _: page.pop_dialog()),
            ft.Button(content="Alterar senha", on_click=salvar_senha),
        ],
    )

    async def enviar_arquivos_web(arquivos):
        """Modo site: o navegador envia o arquivo para a pasta de uploads do servidor."""
        itens, destinos = [], []
        for arquivo in arquivos:
            nome_limpo = os.path.basename(arquivo.name).replace(",", "_")
            relativo = f"{uuid.uuid4().hex}/{nome_limpo}"
            itens.append(
                ft.FilePickerUploadFile(
                    id=arquivo.id,
                    name=arquivo.name,
                    upload_url=page.get_upload_url(relativo, 600),
                )
            )
            destinos.append((arquivo, relativo))
        status = ft.Text("Enviando arquivos...", size=12, color=ft.Colors.AMBER_600)
        lista_nomes_arquivos.controls.append(status)
        page.update()
        try:
            await file_picker.upload(itens)
            for arquivo, relativo in destinos:
                ok = await _aguardar_upload(UPLOAD_DIR / relativo, arquivo.size)
                if not ok:
                    raise TimeoutError(f"o envio de '{arquivo.name}' não terminou")
                anexos_web.append(f"uploads/{relativo}")
                lista_nomes_arquivos.controls.append(
                    ft.Row(
                        [
                            ft.Icon(ft.Icons.ATTACH_FILE, size=16),
                            ft.Text(arquivo.name, size=12),
                        ]
                    )
                )
        except Exception as erro:
            mensagem_decisao.value = f"Não foi possível enviar o arquivo: {erro}"
        finally:
            lista_nomes_arquivos.controls.remove(status)
            page.update()

    async def selecionar_arquivos(_):
        arquivos = await file_picker.pick_files(
            allow_multiple=True, with_data=not page.web
        )
        if not arquivos:
            return
        if page.web:
            await enviar_arquivos_web(arquivos)
            return
        for arquivo in arquivos:
            arquivos_temporarios.append(arquivo)
            lista_nomes_arquivos.controls.append(
                ft.Row(
                    [
                        ft.Icon(ft.Icons.ATTACH_FILE, size=16),
                        ft.Text(arquivo.name, size=12),
                    ]
                )
            )
        page.update()

    input_titulo = ft.TextField(label="Título da Decisão")
    input_categoria = ft.Dropdown(
        label="Categoria",
        options=[ft.DropdownOption(key=categoria) for categoria in CATEGORIAS],
        value="Arquitetura",
    )
    input_impacto = ft.Dropdown(
        label="Impacto",
        options=[ft.DropdownOption(key=impacto) for impacto in IMPACTOS],
        value="Médio",
    )
    input_descricao = ft.TextField(
        label="O que foi decidido?", multiline=True, min_lines=2
    )
    input_justificativa = ft.TextField(
        label="Justificativa", multiline=True, min_lines=2
    )
    input_nova_tarefa = ft.TextField(
        label="Adicionar item ao checklist", expand=True
    )

    # Alteração opcional da ficha do empreendimento, ligada a esta decisão.
    campos_ficha_opcoes = []  # [(grupo, nome, unidade)], na ordem do dropdown
    input_campo_ficha = ft.Dropdown(
        label="Campo da ficha", options=[], col=col(12, md=8)
    )
    input_valor_ficha = ft.TextField(label="Novo valor", col=col(12, md=4))
    mensagem_decisao = ft.Text("", color=ft.Colors.RED_400, size=12)

    def carregar_opcoes_ficha():
        """Recarrega o dropdown com os campos da ficha e o valor atual de cada um."""
        campos_ficha_opcoes.clear()
        campos_ficha_opcoes.extend(campos_da_ficha(projeto.id))
        atuais = {(c.grupo, c.nome): c.valor for c in listar_caracteristicas(projeto.id)}
        opcoes = [ft.DropdownOption(key="nenhum", text="(não altera a ficha)")]
        for i, (grupo, nome, unidade) in enumerate(campos_ficha_opcoes):
            atual = atuais.get((grupo, nome)) or "vazio"
            sufixo = f" {unidade}" if unidade and atual != "vazio" else ""
            opcoes.append(
                ft.DropdownOption(key=str(i), text=f"{nome} (atual: {atual}{sufixo})")
            )
        input_campo_ficha.options = opcoes
        input_campo_ficha.value = "nenhum"
        input_valor_ficha.value = ""
        mensagem_decisao.value = ""

    def abrir_modal_decisao(_):
        if projeto is None or nivel < NIVEL_PAPEL["Editor"]:
            return
        carregar_opcoes_ficha()
        page.show_dialog(modal_decisao)

    def adicionar_item_checklist(_):
        tarefa = (input_nova_tarefa.value or "").strip()
        if not tarefa:
            return
        item_dado = {"tarefa": tarefa, "feito": False}
        dados_checklist.append(item_dado)

        def ao_marcar(evento, item=item_dado):
            item["feito"] = evento.control.value

        ui_lista_checklist.controls.append(
            ft.Checkbox(label=tarefa, value=False, on_change=ao_marcar)
        )
        input_nova_tarefa.value = ""
        page.update()

    async def salvar_nova_decisao(_):
        if projeto is None:
            return
        alteracao_ficha = None
        if input_campo_ficha.value not in (None, "", "nenhum"):
            novo_valor = (input_valor_ficha.value or "").strip()
            if not novo_valor:
                mensagem_decisao.value = "Informe o novo valor do campo da ficha."
                page.update()
                return
            grupo, nome, unidade = campos_ficha_opcoes[int(input_campo_ficha.value)]
            alteracao_ficha = (grupo, nome, unidade, novo_valor)
        mensagem_decisao.value = ""
        caminhos_salvos = []
        if page.web:
            caminhos_salvos = list(anexos_web)
        else:
            os.makedirs(PASTA_ANEXOS, exist_ok=True)
        for arquivo in [] if page.web else arquivos_temporarios:
            nome = f"{uuid.uuid4().hex}_{os.path.basename(arquivo.name).replace(',', '_')}"
            destino = os.path.join(PASTA_ANEXOS, nome)
            if arquivo.path and os.path.isfile(arquivo.path):
                shutil.copy2(arquivo.path, destino)
            elif arquivo.bytes is not None:
                with open(destino, "wb") as destino_arquivo:
                    destino_arquivo.write(arquivo.bytes)
            else:
                continue
            caminhos_salvos.append(destino)

        if nivel < NIVEL_PAPEL["Editor"]:
            mensagem_decisao.value = "Você tem acesso somente para leitura neste projeto."
            page.update()
            return
        try:
            adicionar_decisao(
                projeto_id=projeto.id,
                titulo=input_titulo.value or "",
                categoria=input_categoria.value,
                descricao=input_descricao.value or "",
                justificativa=input_justificativa.value or "",
                alternativa_descartada="",
                impacto=input_impacto.value,
                autor=usuario.nome_completo,
                anexos=",".join(caminhos_salvos) if caminhos_salvos else None,
                checklist=json.dumps(dados_checklist, ensure_ascii=False)
                if dados_checklist
                else None,
                alteracao_ficha=alteracao_ficha,
                usuario_id=usuario.id,
            )
        except PermissionError as erro:
            mensagem_decisao.value = str(erro)
            page.update()
            return
        input_titulo.value = ""
        input_descricao.value = ""
        input_justificativa.value = ""
        arquivos_temporarios.clear()
        anexos_web.clear()
        lista_nomes_arquivos.controls.clear()
        dados_checklist.clear()
        ui_lista_checklist.controls.clear()
        page.pop_dialog()
        carregar_timeline()

    modal_decisao = ft.AlertDialog(
        **opcoes_dialogo(page),
        title=ft.Text("Registrar Decisão"),
        content=ft.Container(
            width=largura_dialogo(page, 600),
            content=ft.Column(
                tight=True,
                scroll=ft.ScrollMode.AUTO,
                controls=[
                    input_titulo,
                    ft.Row([input_categoria, input_impacto]),
                    input_descricao,
                    input_justificativa,
                    ft.Container(
                        padding=10,
                        border=ft.Border.all(1, ft.Colors.OUTLINE),
                        border_radius=5,
                        content=ft.Column(
                            controls=[
                                ft.Text(
                                    "Checklist de Aprovações/Verificações",
                                    weight=ft.FontWeight.BOLD,
                                ),
                                ft.Row(
                                    [
                                        input_nova_tarefa,
                                        ft.IconButton(
                                            icon=ft.Icons.ADD_CIRCLE,
                                            on_click=adicionar_item_checklist,
                                        ),
                                    ]
                                ),
                                ui_lista_checklist,
                            ]
                        ),
                    ),
                    ft.Container(
                        padding=10,
                        border=ft.Border.all(1, ft.Colors.OUTLINE),
                        border_radius=5,
                        content=ft.Column(
                            controls=[
                                ft.Text(
                                    "Altera a ficha do empreendimento? (opcional)",
                                    weight=ft.FontWeight.BOLD,
                                ),
                                ft.ResponsiveRow([input_campo_ficha, input_valor_ficha]),
                                mensagem_decisao,
                            ]
                        ),
                    ),
                    ft.Button(
                        content="Anexar Arquivos",
                        icon=ft.Icons.UPLOAD_FILE,
                        on_click=selecionar_arquivos,
                    ),
                    lista_nomes_arquivos,
                ],
            ),
        ),
        actions=[
            ft.TextButton(
                content="Cancelar", on_click=lambda _: page.pop_dialog()
            ),
            ft.Button(content="Salvar", on_click=salvar_nova_decisao),
        ],
    )

    def criar_card_ata(reuniao):
        cor_status = (
            ft.Colors.GREEN_400 if reuniao.status == "Fechada" else ft.Colors.AMBER_600
        )
        qtd_decisoes = len(listar_decisoes_reuniao(reuniao.id))

        async def abrir_ata(_, ata_id=reuniao.id):
            if on_open_atas:
                await on_open_atas(ata_id)

        return ft.Row(
            vertical_alignment=ft.CrossAxisAlignment.START,
            controls=[
                ft.Column(
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Text(
                            reuniao.data_reuniao.strftime("%d/%m\n%Y"),
                            size=12,
                            weight=ft.FontWeight.BOLD,
                            text_align=ft.TextAlign.CENTER,
                        ),
                        ft.Icon(ft.Icons.GROUPS, color=ft.Colors.ORANGE_400),
                        ft.Container(width=2, height=110, bgcolor=ft.Colors.OUTLINE),
                    ],
                ),
                ft.Card(
                    expand=True,
                    content=ft.Container(
                        padding=15,
                        content=ft.Column(
                            controls=[
                                ft.Row(
                                    wrap=True,
                                    controls=[
                                        ft.Chip(
                                            label=ft.Text(reuniao.status),
                                            color=cor_status,
                                        ),
                                        ft.Text(
                                            f"Ata {reuniao.numero:02d} · {reuniao.titulo}",
                                            size=16,
                                            weight=ft.FontWeight.BOLD,
                                        ),
                                    ],
                                ),
                                ft.Text(
                                    f"Participantes: {reuniao.participantes or 'não informados'}",
                                    size=13,
                                ),
                                ft.Divider(height=1),
                                ft.Row(
                                    wrap=True,
                                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                    controls=[
                                        ft.Text(
                                            f"Autor: {reuniao.autor} | Decisões: {qtd_decisoes}",
                                            size=11,
                                            color=ft.Colors.GREY_400,
                                        ),
                                        ft.Button(
                                            content="Abrir ata",
                                            icon=ft.Icons.DESCRIPTION,
                                            on_click=abrir_ata,
                                        ),
                                    ],
                                ),
                            ]
                        ),
                    ),
                ),
            ],
        )

    def criar_abridor_anexo(caminho):
        async def abrir(_):
            if page.web:
                # Site: gera um link assinado que expira em poucos minutos (ver anexos_web.py).
                if nivel_no_projeto(usuario.id, projeto.id) < 1 or not anexo_pertence_ao_projeto(
                    projeto.id, caminho
                ):
                    return
                token = assinar_token(segredo_do_servidor(), {"p": caminho}, validade_s=300)
                resultado = page.launch_url(f"/anexo/{quote(token)}")
                if inspect.isawaitable(resultado):
                    await resultado
            else:
                abrir_arquivo_nativo(caminho)

        return abrir

    def carregar_timeline():
        timeline_list.controls.clear()
        if projeto is None:
            timeline_list.controls.append(
                ft.Text("Nenhum projeto disponível para exibir decisões.")
            )
            page.update()
            return

        decisoes = buscar_decisoes_projeto(projeto.id, campo_busca.value or "")
        alteracoes_ficha = alteracoes_ficha_por_decisao(projeto.id)
        reunioes = buscar_reunioes_projeto(projeto.id, campo_busca.value or "")
        if nivel < NIVEL_PAPEL["Editor"]:
            reunioes = [r for r in reunioes if r.status == "Fechada"]  # rascunho é só da equipe
        numeros_atas = {r.id: r.numero for r in listar_reunioes_projeto(projeto.id)}
        # Mais recente primeiro; no mesmo dia a ata aparece acima das suas decisões.
        itens_timeline = sorted(
            [*decisoes, *reunioes],
            key=lambda i: (
                i.data_reuniao if isinstance(i, Reuniao) else i.data_decisao,
                isinstance(i, Reuniao),
                i.numero or 0,
            ),
            reverse=True,
        )
        if not itens_timeline:
            timeline_list.controls.append(
                ft.Text(
                    "Nenhuma decisão encontrada para a busca."
                    if (campo_busca.value or "").strip()
                    else "Nenhuma decisão registrada neste projeto ainda.",
                    color=ft.Colors.GREY_400,
                )
            )

        for item in itens_timeline:
            if isinstance(item, Reuniao):
                timeline_list.controls.append(criar_card_ata(item))
                continue
            decisao = item
            cor_categoria = CORES_CATEGORIA.get(
                decisao.categoria, ft.Colors.BLUE_400
            )
            area_check = ft.Column(spacing=2)
            if decisao.checklist:
                itens = json.loads(decisao.checklist)
                if itens:
                    area_check.controls.append(
                        ft.Text(
                            "Checklist:",
                            size=12,
                            weight=ft.FontWeight.BOLD,
                            color=ft.Colors.GREY_400,
                        )
                    )
                    for item in itens:
                        area_check.controls.append(
                            ft.Checkbox(
                                label=item["tarefa"],
                                value=item["feito"],
                                disabled=True,
                            )
                        )

            area_anexos = ft.Row(wrap=True, spacing=5)
            if decisao.anexos:
                for caminho in decisao.anexos.split(","):
                    nome = os.path.basename(caminho)
                    area_anexos.controls.append(
                        ft.Button(
                            content=nome,
                            icon=ft.Icons.ATTACHMENT,
                            on_click=criar_abridor_anexo(caminho),
                        )
                    )

            area_origem = ft.Row(wrap=True, spacing=5)
            if decisao.reuniao_id and on_open_atas:
                numero_ata = numeros_atas.get(decisao.reuniao_id)

                async def abrir_ata_origem(_, ata_id=decisao.reuniao_id):
                    await on_open_atas(ata_id)

                area_origem.controls.append(
                    ft.Button(
                        content=f"Origem: Ata {numero_ata:02d}" if numero_ata else "Origem: ata",
                        icon=ft.Icons.DESCRIPTION,
                        on_click=abrir_ata_origem,
                    )
                )

            area_ficha = ft.Column(spacing=2)
            for alteracao in alteracoes_ficha.get(decisao.id, []):
                area_ficha.controls.append(
                    ft.Row(
                        spacing=6,
                        controls=[
                            ft.Icon(ft.Icons.ASSIGNMENT, size=16, color=ft.Colors.TEAL_400),
                            ft.Text(
                                f"Ficha · {alteracao.nome}: "
                                f"{alteracao.valor_anterior or '(vazio)'} → "
                                f"{alteracao.valor_novo or '(vazio)'}",
                                size=12,
                                color=ft.Colors.TEAL_200,
                                expand=True,
                            ),
                        ],
                    )
                )

            timeline_list.controls.append(
                ft.Row(
                    vertical_alignment=ft.CrossAxisAlignment.START,
                    controls=[
                        ft.Column(
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            controls=[
                                ft.Text(
                                    decisao.data_decisao.strftime("%d/%m\n%Y"),
                                    size=12,
                                    weight=ft.FontWeight.BOLD,
                                    text_align=ft.TextAlign.CENTER,
                                ),
                                ft.Icon(
                                    ft.Icons.RADIO_BUTTON_CHECKED,
                                    color=cor_categoria,
                                ),
                                ft.Container(
                                    width=2,
                                    height=150,
                                    bgcolor=ft.Colors.OUTLINE,
                                ),
                            ],
                        ),
                        ft.Card(
                            expand=True,
                            content=ft.Container(
                                padding=15,
                                content=ft.Column(
                                    controls=[
                                        ft.Row(
                                            wrap=True,
                                            controls=[
                                                ft.Chip(
                                                    label=ft.Text(decisao.categoria),
                                                    color=cor_categoria,
                                                ),
                                                ft.Text(
                                                    (f"D-{decisao.numero:03d} · " if decisao.numero else "")
                                                    + decisao.titulo,
                                                    size=16,
                                                    weight=ft.FontWeight.BOLD,
                                                ),
                                            ],
                                        ),
                                        ft.Text(decisao.descricao, size=14),
                                        ft.Text(
                                            f"Justificativa: {decisao.justificativa}",
                                            size=13,
                                            italic=True,
                                            color=ft.Colors.WHITE_70,
                                        ),
                                        area_check,
                                        area_anexos,
                                        area_origem,
                                        area_ficha,
                                        ft.Divider(height=1),
                                        ft.Text(
                                            f"Autor: {decisao.autor} | Impacto: {decisao.impacto}",
                                            size=11,
                                            color=ft.Colors.GREY_400,
                                        ),
                                    ]
                                ),
                            ),
                        ),
                    ],
                )
            )
        page.update()

    async def abrir_lista_atas(_):
        if on_open_atas:
            await on_open_atas(None)

    async def abrir_ficha_empreendimento(_):
        if on_open_ficha:
            await on_open_ficha()

    btn_novo_projeto = ft.Button(
        content=rotulo(page, "+ Novo Projeto", "+ Projeto"),
        icon=ft.Icons.ADD,
        on_click=lambda _: page.show_dialog(modal_projeto),
    )
    btn_editar_projeto = ft.Button(
        content=rotulo(page, "Editar Projeto", "Editar"), icon=ft.Icons.EDIT, on_click=abrir_edicao_projeto
    )
    btn_excluir_projeto = ft.Button(
        content=rotulo(page, "Excluir Projeto", "Excluir"),
        icon=ft.Icons.DELETE,
        color=ft.Colors.RED_400,
        on_click=abrir_exclusao_projeto,
    )
    btn_membros = ft.Button(
        content="Membros", icon=ft.Icons.PEOPLE, on_click=abrir_membros
    )
    btn_relatorio = ft.Button(
        content=rotulo(page, "Relatório PDF", "PDF"),
        icon=ft.Icons.PICTURE_AS_PDF,
        on_click=abrir_relatorio,
    )
    btn_nova_decisao = ft.Button(
        content=rotulo(page, "+ Nova Decisão", "+ Decisão"), icon=ft.Icons.ADD, on_click=abrir_modal_decisao
    )

    def aplicar_permissoes():
        """Mostra só o que o papel do usuário neste projeto permite."""
        btn_novo_projeto.visible = pode_criar_projeto
        btn_editar_projeto.visible = nivel >= NIVEL_PAPEL["Responsável"]
        btn_membros.visible = nivel >= NIVEL_PAPEL["Responsável"]
        btn_excluir_projeto.visible = nivel >= NIVEL_PAPEL["Responsável"]
        btn_nova_decisao.visible = nivel >= NIVEL_PAPEL["Editor"]
        if usuario.admin:
            acesso_info.value = "Acesso: administrador"
        elif nivel >= NIVEL_PAPEL["Responsável"]:
            acesso_info.value = "Acesso: responsável pelo projeto"
        elif nivel >= NIVEL_PAPEL["Editor"]:
            acesso_info.value = "Acesso: editor"
        else:
            acesso_info.value = "Acesso: somente leitura"

    aplicar_permissoes()

    header = ft.Container(
        padding=15,
        bgcolor=ft.Colors.SURFACE,
        border_radius=10,
        content=ft.ResponsiveRow(
            controls=[
                ft.Column(
                    [
                        ft.Text(
                            "Memória de Projetos",
                            size=22,
                            weight=ft.FontWeight.BOLD,
                        ),
                        projeto_info,
                        acesso_info,
                    ],
                    col=col(12, md=4),
                ),
                ft.Row(
                    col=col(12, md=8),
                    wrap=True,
                    alignment=ft.MainAxisAlignment.END,
                    controls=[
                        btn_novo_projeto,
                        btn_editar_projeto,
                        btn_membros,
                        btn_excluir_projeto,
                        ft.Button(
                            content=rotulo(page, "Ficha do Empreendimento", "Ficha"),
                            icon=ft.Icons.ASSIGNMENT,
                            on_click=abrir_ficha_empreendimento,
                        ),
                        ft.Button(
                            content=rotulo(page, "Atas de Reunião", "Atas"),
                            icon=ft.Icons.GROUPS,
                            on_click=abrir_lista_atas,
                        ),
                        btn_nova_decisao,
                        btn_relatorio,
                        *(
                            [
                                ft.Button(
                                    content="Usuários",
                                    icon=ft.Icons.GROUP_ADD,
                                    on_click=abrir_usuarios,
                                )
                            ]
                            if usuario.admin
                            else []
                        ),
                        ft.IconButton(
                            icon=ft.Icons.MANAGE_ACCOUNTS,
                            tooltip="Minha conta (trocar senha)",
                            on_click=abrir_conta,
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

    carregar_timeline()
    return ft.View(
        route="/timeline",
        controls=[
            header,
            ft.ResponsiveRow([seletor_projeto, campo_busca]),
            ft.Divider(),
            timeline_list,
        ],
        services=[file_picker],
    )

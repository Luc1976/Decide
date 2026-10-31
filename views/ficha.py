import datetime

import flet as ft
from marca import marca_cabecalho

import tema
from database import (
    resumo_documentos,
    listar_caracteristicas,
    nivel_no_projeto,
    listar_historico_ficha,
    mapa_origens_ficha,
    salvar_caracteristicas,
)
import catalogo_tipologias as catalogo
from ficha_calculos import calcular_indicadores
from models import CAMPO_TIPOLOGIA, CAMPOS_LONGOS, FICHA_GRUPOS, GRUPO_OUTRAS, GRUPO_PROGRAMA, NIVEL_PAPEL
from layout import rotulo, col, largura_dialogo, opcoes_dialogo

CHAVE_TIPOLOGIA = (GRUPO_PROGRAMA, CAMPO_TIPOLOGIA)
AVISO_SEM_TIPOLOGIA = "Escolha a tipologia no card Programa para ver os sistemas construtivos."
AVISO_TIPOLOGIA_FORA = ("Esta tipologia não tem sistemas construtivos no catálogo. "
                        "Use Outras características.")



def _hora_local(momento: datetime.datetime) -> datetime.datetime:
    if momento.tzinfo is None:  # o SQLite devolve datas sem fuso (gravadas em UTC)
        momento = momento.replace(tzinfo=datetime.timezone.utc)
    return momento.astimezone()


class _CampoLista:
    """Lista de opções + "Outro" com campo de texto ao lado. Usado na tipologia e nos
    campos do catálogo que têm opções."""

    def __init__(self, nome, opcoes, valor, pode_editar, ao_mudar, largura):
        escolha, texto = catalogo.escolha_e_texto(catalogo.CampoCatalogo(nome, tuple(opcoes)), valor)
        self.opcoes = tuple(opcoes)
        self.lista = ft.Dropdown(
            label=nome,
            options=[ft.DropdownOption(key=o, text=o) for o in (*opcoes, catalogo.OUTRO)],
            value=escolha,
            disabled=not pode_editar,
            expand=True,
        )
        self.outro = ft.TextField(
            label=f"{nome} – especifique",
            value=texto,
            visible=escolha == catalogo.OUTRO,
            read_only=not pode_editar,
            expand=True,
        )

        def ao_escolher(_):
            self.outro.visible = self.lista.value == catalogo.OUTRO
            ao_mudar()

        self.lista.on_select = ao_escolher
        self.controle = ft.Container(
            col=largura,
            content=ft.Column(spacing=6, controls=[self.lista, self.outro]),
        )

    @property
    def valor(self) -> str:
        campo = catalogo.CampoCatalogo(self.lista.label, self.opcoes)
        return catalogo.valor_gravado(campo, self.lista.value, self.outro.value)


class _CampoTexto:
    def __init__(self, tf: ft.TextField):
        self.tf = tf
        self.controle = tf

    @property
    def valor(self) -> str:
        return self.tf.value or ""


def build_ficha_view(page, projeto, usuario, on_logout, on_voltar, on_open_documentos=None):
    """Ficha de características do empreendimento: os inputs iniciais do projeto, numa
    tela só. A tipologia (card Programa) define os campos do catálogo que aparecem:
    sistemas construtivos, alturas e características (catalogo_tipologias.py)."""

    # Leitor (cliente) vê a ficha, mas não altera.
    pode_editar = projeto is not None and (
        nivel_no_projeto(usuario.id, projeto.id) >= NIVEL_PAPEL["Editor"]
    )

    def _contagem_documentos() -> str:
        """' (3/7)': recebidos / aplicáveis, para o botão de acesso."""
        try:
            contagem = resumo_documentos(projeto.id, usuario.id)
        except (ValueError, PermissionError):
            return ""
        return f" ({contagem['Recebido']}/{contagem['aplicaveis']})" if contagem["total"] else ""

    salvos = {}
    if projeto is not None:
        salvos = {(c.grupo, c.nome): c for c in listar_caracteristicas(projeto.id)}

    campos = {}  # (grupo, nome) -> (_CampoTexto | _CampoLista, unidade)  — campos fixos e personalizados
    do_catalogo = {}  # (grupo, nome) -> (_CampoTexto | _CampoLista, CampoCatalogo)
    linhas_por_grupo = {}  # grupo -> ft.ResponsiveRow dos campos fixos/personalizados
    linhas_catalogo = {}  # grupo -> ft.ResponsiveRow dos campos do catálogo visíveis
    cards_catalogo = {}  # grupo do catálogo -> ft.Card (escondido quando vazio)
    aviso_sistemas = ft.Text("", size=13, color=ft.Colors.ON_SURFACE_VARIANT)
    mensagem = ft.Text("", size=12)
    caixa_indicadores = ft.Column(spacing=6)

    def valores_da_tela() -> dict:
        valores = {chave: c.valor for chave, (c, _) in campos.items()}
        valores.update({chave: c.valor for chave, (c, _) in do_catalogo.items()})
        return valores

    # ---------- Indicadores calculados ----------
    def montar_indicadores():
        valores = {nome: v for (_, nome), v in valores_da_tela().items()}
        linhas = calcular_indicadores(valores)
        if not linhas:
            caixa_indicadores.controls = [
                ft.Text(
                    "Preencha a área do terreno e os parâmetros (TO, CA, permeabilidade) "
                    "para ver os indicadores.",
                    size=13,
                    color=ft.Colors.ON_SURFACE_VARIANT,
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
                        color=tema.aviso(page) if alerta else ft.Colors.ON_SURFACE_VARIANT,
                    ),
                    ft.Text(
                        texto,
                        size=14,
                        weight=ft.FontWeight.BOLD,
                        color=tema.aviso(page) if alerta else None,
                    ),
                ],
            )
            for rotulo, texto, alerta in linhas
        ]

    def ao_digitar(_):
        mensagem.value = ""
        montar_indicadores()
        page.update()

    # ---------- Campos do catálogo (dependem da tipologia e da cascata) ----------
    def criar_campo_catalogo(campo):
        salvo = salvos.get(campo.chave)
        valor = salvo.valor if salvo else ""
        if campo.opcoes:
            return _CampoLista(campo.nome, campo.opcoes, valor, pode_editar, ao_mudar_catalogo,
                               col(12, sm=6, md=4))
        rotulo_campo = f"{campo.nome} ({campo.unidade})" if campo.unidade else campo.nome
        return _CampoTexto(ft.TextField(
            label=rotulo_campo,
            value=valor,
            col=col(12, sm=6, md=4),
            keyboard_type=ft.KeyboardType.NUMBER,
            on_change=ao_digitar,
            read_only=not pode_editar,
        ))

    def montar_catalogo():
        """Refaz os campos do catálogo visíveis com os valores atuais da tela. Os controles
        são reaproveitados: o que foi digitado num campo escondido volta se ele reaparecer."""
        visiveis = catalogo.campos_visiveis(valores_da_tela())
        # um campo novo pode abrir outro (cascata): repete até estabilizar
        while True:
            for campo in visiveis:
                if campo.chave not in do_catalogo:
                    do_catalogo[campo.chave] = (criar_campo_catalogo(campo), campo)
            novos = catalogo.campos_visiveis(valores_da_tela())
            if [c.chave for c in novos] == [c.chave for c in visiveis]:
                break
            visiveis = novos
        for linha in linhas_catalogo.values():
            linha.controls.clear()
        for campo in visiveis:
            linhas_catalogo[campo.grupo].controls.append(do_catalogo[campo.chave][0].controle)
        for grupo, card in cards_catalogo.items():
            card.visible = bool(linhas_catalogo[grupo].controls) or grupo == catalogo.GRUPO_SISTEMAS
        tipologia = (campos[CHAVE_TIPOLOGIA][0].valor or "").strip()
        sem_campos = not linhas_catalogo[catalogo.GRUPO_SISTEMAS].controls
        aviso_sistemas.visible = sem_campos
        aviso_sistemas.value = AVISO_TIPOLOGIA_FORA if tipologia else AVISO_SEM_TIPOLOGIA

    def ao_mudar_catalogo():
        mensagem.value = ""
        montar_catalogo()
        montar_indicadores()
        page.update()

    # ---------- Campos fixos e personalizados ----------
    def criar_campo(grupo, nome, unidade, valor):
        if (grupo, nome) == CHAVE_TIPOLOGIA:
            campo = _CampoLista(nome, catalogo.TIPOLOGIAS, valor, pode_editar, ao_mudar_catalogo,
                                col(12, sm=6, md=4))
            campos[(grupo, nome)] = (campo, unidade)
            linhas_por_grupo[grupo].controls.append(campo.controle)
            return campo
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
        campos[(grupo, nome)] = (_CampoTexto(tf), unidade)
        linhas_por_grupo[grupo].controls.append(tf)
        return tf

    todos_do_catalogo = catalogo.todos_os_campos()

    def montar_grupo(grupo, modelo):
        linhas_por_grupo[grupo] = ft.ResponsiveRow(spacing=10, run_spacing=10)
        nomes_modelo = {nome for nome, _ in modelo}
        for nome, unidade in modelo:
            salvo = salvos.get((grupo, nome))
            criar_campo(grupo, nome, unidade, salvo.valor if salvo else "")
        # campos salvos que não estão (mais) no modelo continuam aparecendo
        # (menos os do catálogo, que aparecem conforme a tipologia)
        for (g, nome), salvo in salvos.items():
            if g == grupo and nome not in nomes_modelo and (g, nome) not in todos_do_catalogo:
                criar_campo(grupo, nome, salvo.unidade or "", salvo.valor)

    for grupo, modelo in FICHA_GRUPOS.items():
        montar_grupo(grupo, modelo)
    montar_grupo(GRUPO_OUTRAS, [])
    for grupo in catalogo.ordem_dos_grupos():
        linhas_catalogo[grupo] = ft.ResponsiveRow(spacing=10, run_spacing=10)

    # ---------- Novo campo personalizado ----------
    input_novo_nome = ft.TextField(label="Nome da característica")
    input_nova_unidade = ft.TextField(label="Unidade (opcional)", col=col(12, md=4))
    input_novo_valor = ft.TextField(label="Valor", col=col(12, md=8))
    mensagem_novo = ft.Text("", color=ft.Colors.ERROR, size=12)

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
        if (GRUPO_OUTRAS, nome) in campos or any(n == nome for _, n in catalogo.todos_os_campos()):
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
        mensagem.color = tema.aviso(page)
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
            (grupo, nome, unidade, campo.valor)
            for (grupo, nome), (campo, unidade) in campos.items()
        ]
        # só os campos do catálogo visíveis; os escondidos são limpos pelo serviço (com histórico)
        visiveis = {c.chave for c in catalogo.campos_visiveis(valores_da_tela())}
        itens += [
            (c.grupo, c.nome, c.unidade, controle.valor)
            for chave, (controle, c) in do_catalogo.items()
            if chave in visiveis
        ]
        try:
            qtd = salvar_caracteristicas(
                projeto.id, itens, usuario.nome_completo, usuario_id=usuario.id
            )
        except Exception as erro:
            mensagem.color = ft.Colors.ERROR
            mensagem.value = f"Não foi possível salvar a ficha: {erro}"
            page.update()
            return
        mensagem.color = tema.sucesso(page)
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
                        color=ft.Colors.ON_SURFACE_VARIANT,
                    )
                )
                controles.append(ft.Text(f"{r.nome}: {anterior} → {novo}", size=13))
                controles.append(ft.Divider(height=1))
        else:
            controles = [
                ft.Text("Nenhuma alteração registrada ainda.", color=ft.Colors.ON_SURFACE_VARIANT)
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
    def card_grupo(grupo, extra=None):
        controles = [ft.Text(grupo, size=16, weight=ft.FontWeight.BOLD), ft.Divider(height=1)]
        if grupo in linhas_por_grupo:
            controles.append(linhas_por_grupo[grupo])
        if grupo == catalogo.GRUPO_SISTEMAS:
            controles.append(aviso_sistemas)
        controles.append(linhas_catalogo[grupo])
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
    for grupo in catalogo.ordem_dos_grupos():
        extra = None
        if grupo == GRUPO_OUTRAS:
            extra = ft.Button(
                content="+ Adicionar característica",
                icon=ft.Icons.ADD,
                on_click=abrir_novo_campo,
                visible=pode_editar,
            )
        card = card_grupo(grupo, extra)
        if grupo in catalogo.GRUPOS_DO_CATALOGO:
            cards_catalogo[grupo] = card
        cards.append(card)
    montar_catalogo()
    montar_indicadores()

    header = ft.Container(
        padding=ft.Padding.symmetric(horizontal=18, vertical=14),
        bgcolor=ft.Colors.SURFACE_CONTAINER,
        border_radius=14,
        content=ft.ResponsiveRow(
            controls=[
                ft.Column(
                    col=col(12, md=5),
                    controls=[
                        marca_cabecalho(),
                        ft.Text(
                            "Ficha do Empreendimento",
                            size=22,
                            weight=ft.FontWeight.BOLD,
                        ),
                        ft.Text(
                            f"Projeto Ativo: {projeto.nome}" if projeto else "Sem projeto",
                            size=14,
                            color=ft.Colors.PRIMARY,
                        ),
                    ]
                ),
                ft.Row(
                    col=col(12, md=7),
                    wrap=True,
                    alignment=ft.MainAxisAlignment.END,
                    controls=[
                        ft.IconButton(icon=ft.Icons.HOME, tooltip="Ir para a linha do tempo", on_click=on_voltar),
                        tema.botao_secundario("Linha do tempo", ft.Icons.TIMELINE, on_voltar),
                        *(
                            [tema.botao_destaque(
                                rotulo(page, "Documentos de referência", "Documentos") + _contagem_documentos(),
                                ft.Icons.FOLDER_COPY_OUTLINED,
                                on_open_documentos,
                                terciario=True,
                            )]
                            if on_open_documentos and projeto is not None
                            else []
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

    corpo = ft.Column(
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

    return ft.View(
        route="/ficha",
        controls=[header, corpo],
    )

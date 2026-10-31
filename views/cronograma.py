"""Cronograma macro do projeto: Gantt com versões ligadas a decisões.

A versão 1 é a linha de base. "Revisar cronograma" abre o formulário com as datas atuais;
mudar uma entrega recalcula as seguintes na hora (cronograma_calculos.recalcular) e salvar
exige a decisão que motivou (existente ou nova). As regras ficam no serviço
nucleo/servicos/cronograma.py; esta tela só monta e mostra.
"""
import datetime
from typing import Dict, List, Optional

import flet as ft

import cronograma_calculos as calc
import tema
from cronograma_calculos import ETAPA, MARCO, Item
from database import listar_decisoes_projeto, nivel_no_projeto
from layout import col, largura_dialogo, opcoes_dialogo
from marca import marca_cabecalho
from models import CATEGORIAS, IMPACTOS, NIVEL_PAPEL

LARGURA_NOMES = 200
LARGURA_MES = 56
ALTURA_LINHA = 34
NOVA_DECISAO = "nova"
COR_REFERENCIA = ft.Colors.with_opacity(0.35, ft.Colors.ON_SURFACE_VARIANT)


def _data(texto) -> Optional[datetime.date]:
    """'dd/mm/aaaa' -> date; vazio ou inválido -> None."""
    try:
        return datetime.datetime.strptime((texto or "").strip(), "%d/%m/%Y").date()
    except ValueError:
        return None


def _br(dia: Optional[datetime.date]) -> str:
    return dia.strftime("%d/%m/%Y") if dia else ""


def _servicos():
    from nucleo.db import nova_sessao
    from nucleo.servicos import cronograma as servico
    from nucleo.servicos.usuarios import ator_por_id

    return nova_sessao, servico, ator_por_id


class _Linha:
    """Uma linha do formulário: marcar, nome, datas, dependência e o selo 'recalculada'."""

    def __init__(self, item: Item, marcado: bool, pode_remover: bool, ao_mudar, ao_remover):
        self.tipo = item.tipo
        self.padrao = item.padrao
        self.tocado = False  # o usuário digitou uma data nesta revisão
        self.marcar = ft.Checkbox(value=marcado, on_change=lambda _: ao_mudar(self))
        self.nome = ft.TextField(label="Nome do novo item" if not item.nome else "Item", value=item.nome,
                                 read_only=item.padrao, dense=True, col=col(12, md=4),
                                 on_change=lambda _: self._renomear())
        self.inicio = ft.TextField(dense=True, value=_br(item.inicio), hint_text="dd/mm/aaaa",
                                   col=col(6, md=3), on_change=lambda _: self._digitou(ao_mudar))
        self.entrega = ft.TextField(dense=True, value=_br(item.entrega), hint_text="dd/mm/aaaa",
                                    col=col(6, md=3), visible=item.tipo == ETAPA,
                                    on_change=lambda _: self._digitou(ao_mudar))
        self.depende = ft.Checkbox(label="Depende da anterior", value=item.depende_da_anterior,
                                   on_change=lambda _: ao_mudar(self))
        self.recalculada = ft.Text("recalculada", size=11, italic=True, visible=False)
        self.remover = ft.IconButton(ft.Icons.DELETE_OUTLINE, tooltip="Remover", visible=pode_remover,
                                     on_click=lambda _: ao_remover(self))
        self._rotular()
        self.controle = ft.Container(
            padding=ft.Padding.symmetric(vertical=4),
            content=ft.Column(spacing=2, controls=[
                ft.Row([self.marcar, ft.Text("Marco" if item.tipo == MARCO else "Etapa", size=11,
                                             color=ft.Colors.ON_SURFACE_VARIANT),
                        self.depende, self.recalculada, self.remover], wrap=True),
                ft.ResponsiveRow([self.nome, self.inicio, self.entrega], spacing=8),
            ]),
        )

    def _rotular(self):
        nome = (self.nome.value or "").strip() or "Novo item"
        if self.tipo == MARCO:
            self.inicio.label = f"{nome} – data"
        else:
            self.inicio.label = f"{nome} – início"
            self.entrega.label = f"{nome} – entrega"

    def _renomear(self):
        self._rotular()

    def _digitou(self, ao_mudar):
        self.tocado = True
        ao_mudar(self)

    @property
    def nome_atual(self) -> str:
        return (self.nome.value or "").strip()

    def item(self) -> Item:
        inicio = _data(self.inicio.value)
        entrega = inicio if self.tipo == MARCO else _data(self.entrega.value)
        return Item(self.nome_atual, self.tipo, inicio, entrega, bool(self.depende.value), self.padrao)

    def mostrar(self, item: Item, recalculada: bool):
        self.inicio.value = _br(item.inicio)
        if self.tipo == ETAPA:
            self.entrega.value = _br(item.entrega)
        self.recalculada.visible = recalculada


def build_cronograma_view(page, projeto, usuario, on_logout, on_voltar):
    pode_editar = projeto is not None and nivel_no_projeto(usuario.id, projeto.id) >= NIVEL_PAPEL["Editor"]
    nova_sessao, servico, ator_por_id = _servicos()

    estado = {"versao_vista": None, "referencia": "v1", "modo": "ver"}  # ver | criar | revisar
    corpo = ft.Column(spacing=14, expand=True, scroll=ft.ScrollMode.AUTO)
    mensagem = ft.Text("", size=12)

    def carregar(numero=None) -> dict:
        with nova_sessao() as s:
            return servico.obter(s, ator_por_id(s, usuario.id), projeto.id, numero)

    # ------------------------------------------------------------ Gantt

    def _referencia(dados) -> List[Item]:
        if estado["referencia"] == "nenhuma":
            return []
        if estado["referencia"] == "anterior":
            numero = dados["versao"].numero
            if numero <= 1:
                return []
            return carregar(numero - 1)["itens"]
        return dados["itens_v1"] if dados["versao"].numero > 1 else []

    def _detalhe(item: Item, ref: Optional[Item], desvio):
        linhas = [ft.Text(item.nome, size=16, weight=ft.FontWeight.BOLD)]
        if item.tipo == MARCO:
            linhas.append(ft.Text(f"Data: {_br(item.inicio)}"))
        else:
            linhas.append(ft.Text(f"Início: {_br(item.inicio)} · Entrega: {_br(item.entrega)}"))
            linhas.append(ft.Text(f"Duração: {(item.entrega - item.inicio).days} dias", size=12,
                                  color=ft.Colors.ON_SURFACE_VARIANT))
        if desvio is not None and desvio.novo:
            linhas.append(ft.Text("Item novo nesta versão", color=tema.aviso(page)))
        elif ref is not None and desvio is not None:
            linhas.append(ft.Text(f"Entrega: {calc.texto_desvio(desvio.entrega_dias)} em relação à referência "
                                  f"({_br(ref.entrega)})",
                                  color=tema.aviso(page) if desvio.entrega_dias > 0 else None))
        page.show_dialog(ft.AlertDialog(
            **opcoes_dialogo(page),
            content=ft.Container(width=largura_dialogo(page, 420), content=ft.Column(linhas, tight=True)),
            actions=[ft.TextButton(content="Fechar", on_click=lambda _: page.pop_dialog())],
        ))

    def gantt(itens: List[Item], referencia: List[Item]) -> ft.Control:
        inicio, fim, meses = calc.escala(itens, referencia)
        largura = max(len(meses), 1) * LARGURA_MES
        dias = max((fim - inicio).days, 1)
        ref_por_nome = {calc.chave(i.nome): i for i in referencia}
        desv, _ = calc.desvios(itens, referencia) if referencia else ({}, [])
        hoje = datetime.date.today()

        def x(dia):
            return calc.posicao(dia, inicio, fim) * largura

        cabecalho = ft.Stack(width=largura + 40, height=22, controls=[  # +40: rótulo do último mês
            ft.Container(left=x(m), top=0, content=ft.Text(m.strftime("%m/%y"), size=11,
                                                          color=ft.Colors.ON_SURFACE_VARIANT))
            for m in meses
        ])
        linhas = [ft.Row(spacing=0, controls=[ft.Container(width=LARGURA_NOMES), cabecalho])]
        for item in itens:
            ref = ref_por_nome.get(calc.chave(item.nome))
            d = desv.get(calc.chave(item.nome))
            atrasado = d is not None and not d.novo and d.entrega_dias > 0
            cor = tema.aviso(page) if atrasado else ft.Colors.PRIMARY
            camadas = [ft.Container(left=x(m), top=0, width=1, height=ALTURA_LINHA, bgcolor=ft.Colors.OUTLINE_VARIANT)
                       for m in meses]
            if inicio <= hoje <= fim:
                camadas.append(ft.Container(left=x(hoje), top=0, width=2, height=ALTURA_LINHA,
                                            bgcolor=ft.Colors.ERROR))
            if ref is not None and ref.inicio:
                if ref.tipo == MARCO:
                    camadas.append(ft.Container(left=x(ref.inicio) - 6, top=20, content=ft.Icon(
                        ft.Icons.DIAMOND_OUTLINED, size=12, color=COR_REFERENCIA)))
                else:
                    camadas.append(ft.Container(left=x(ref.inicio), top=24, height=5, border_radius=3,
                                                width=max(x(ref.entrega) - x(ref.inicio), 3),
                                                bgcolor=COR_REFERENCIA))
            texto_desvio = ""
            if d is not None and not d.novo and ref is not None:
                texto_desvio = calc.texto_desvio(d.entrega_dias)
            dica = f"{item.nome}: " + (_br(item.inicio) if item.tipo == MARCO
                                       else f"{_br(item.inicio)} – {_br(item.entrega)}")
            dica += f" ({texto_desvio})" if texto_desvio else ""
            ao_tocar = (lambda i, r, dd: (lambda _: _detalhe(i, r, dd)))(item, ref, d)
            if item.tipo == MARCO:
                camadas.append(ft.Container(left=x(item.inicio) - 9, top=1, tooltip=dica, on_click=ao_tocar,
                                            content=ft.Icon(ft.Icons.DIAMOND, size=18, color=cor)))
            else:
                camadas.append(ft.Container(left=x(item.inicio), top=4, height=16, border_radius=4, bgcolor=cor,
                                            width=max(x(item.entrega) - x(item.inicio), 4),
                                            tooltip=dica, on_click=ao_tocar))
            nome = ft.Container(width=LARGURA_NOMES, padding=ft.Padding.only(right=8), content=ft.Column(
                spacing=0, controls=[
                    ft.Text(item.nome, size=13, weight=ft.FontWeight.W_600, no_wrap=True),
                    ft.Text(texto_desvio or (_br(item.entrega) if item.tipo == MARCO else
                                             f"{_br(item.inicio)} – {_br(item.entrega)}"),
                            size=11, color=tema.aviso(page) if atrasado else ft.Colors.ON_SURFACE_VARIANT),
                ]))
            linhas.append(ft.Row(spacing=0, data=f"linha:{item.nome}", controls=[
                nome, ft.Stack(width=largura, height=ALTURA_LINHA, controls=camadas)]))
        legenda = ft.Row(wrap=True, spacing=16, controls=[
            ft.Row([ft.Container(width=18, height=10, bgcolor=ft.Colors.PRIMARY, border_radius=3),
                    ft.Text("Etapa", size=11)], spacing=4, tight=True),
            ft.Row([ft.Icon(ft.Icons.DIAMOND, size=14, color=ft.Colors.PRIMARY), ft.Text("Marco", size=11)], spacing=4, tight=True),
            ft.Row([ft.Container(width=18, height=5, bgcolor=COR_REFERENCIA, border_radius=3),
                    ft.Text("Referência", size=11)], spacing=4, tight=True),
            ft.Row([ft.Container(width=18, height=10, bgcolor=tema.aviso(page), border_radius=3),
                    ft.Text("Entrega depois da referência", size=11)], spacing=4, tight=True),
            ft.Row([ft.Container(width=2, height=12, bgcolor=ft.Colors.ERROR), ft.Text("Hoje", size=11)], spacing=4, tight=True),
        ])
        return ft.Column(spacing=8, controls=[
            ft.Row(scroll=ft.ScrollMode.AUTO, controls=[ft.Column(spacing=2, controls=linhas)]),
            legenda,
        ])

    # ------------------------------------------------------------ modo "ver"

    def resumo(dados) -> str:
        v, itens = dados["versao"], dados["itens"]
        partes = [f"Versão {v.numero}", v.criado_em.strftime("%d/%m/%Y")]
        if v.decisao_id:
            dec = next((d for d in listar_decisoes_projeto(projeto.id) if d.id == v.decisao_id), None)
            if dec is not None:
                partes.append(f"Decisão D-{dec.numero:03d}" if dec.numero else "Decisão")
        else:
            partes.append("linha de base")
        ultimo = itens[-1] if itens else None
        texto = " · ".join(partes)
        if ultimo is not None:
            texto += f" · {ultimo.nome}: {_br(ultimo.entrega)}"
            if v.numero > 1:
                desv, _ = calc.desvios([ultimo], dados["itens_v1"])
                dd = desv.get(calc.chave(ultimo.nome))
                if dd is not None and not dd.novo:
                    texto += f" ({calc.texto_desvio(dd.entrega_dias)} em relação à versão 1)"
        return texto

    def abrir_versoes(_=None):
        dados = carregar()
        decisoes = {d.id: d for d in listar_decisoes_projeto(projeto.id)}

        def ver(numero):
            def acao(_):
                estado["versao_vista"] = numero
                page.pop_dialog()
                montar()
            return acao

        linhas = []
        for v in reversed(dados["versoes"]):
            dec = decisoes.get(v.decisao_id)
            origem = (f"D-{dec.numero:03d} · {dec.titulo}" if dec and dec.numero else "linha de base")
            linhas.append(ft.ListTile(
                title=ft.Text(f"Versão {v.numero} · {v.criado_em.strftime('%d/%m/%Y')} · {v.autor}"),
                subtitle=ft.Text(origem, size=12), on_click=ver(v.numero)))
        page.show_dialog(ft.AlertDialog(
            **opcoes_dialogo(page), title=ft.Text("Versões do cronograma"),
            content=ft.Container(width=largura_dialogo(page, 520),
                                 content=ft.Column(linhas, tight=True, scroll=ft.ScrollMode.AUTO)),
            actions=[ft.TextButton(content="Fechar", on_click=lambda _: page.pop_dialog())],
        ))

    def mostrar_ver():
        dados = carregar(estado["versao_vista"])
        corpo.controls.clear()
        if dados["versao"] is None:
            corpo.controls.append(ft.Text("Este projeto ainda não tem cronograma.", size=15))
            if pode_editar:
                corpo.controls.append(ft.Button(content="Criar cronograma", icon=ft.Icons.ADD,
                                                on_click=lambda _: entrar("criar")))
            return
        vendo_antiga = estado["versao_vista"] is not None and dados["versao"].numero != dados["versoes"][-1].numero

        def trocar_referencia(_):
            estado["referencia"] = seletor.value
            montar()

        seletor = ft.Dropdown(label="Comparar com", value=estado["referencia"], width=270, dense=True,
                              options=[ft.DropdownOption(key="v1", text="Versão 1 (linha de base)"),
                                       ft.DropdownOption(key="anterior", text="Versão anterior"),
                                       ft.DropdownOption(key="nenhuma", text="Nenhuma")],
                              on_select=trocar_referencia)
        acoes = [seletor, ft.Button(content="Versões", icon=ft.Icons.HISTORY, on_click=abrir_versoes)]
        if vendo_antiga:
            def voltar_atual(_):
                estado["versao_vista"] = None
                montar()
            acoes.append(ft.Button(content="Ver versão atual", on_click=voltar_atual))
        elif pode_editar:
            acoes.append(ft.Button(content="Revisar cronograma", icon=ft.Icons.EDIT_CALENDAR,
                                   on_click=lambda _: entrar("revisar")))
        corpo.controls.extend([
            ft.Text(resumo(dados), size=14, weight=ft.FontWeight.W_600),
            ft.Text("Versão antiga, só para consulta." if vendo_antiga else "", size=12,
                    color=tema.aviso(page), visible=vendo_antiga),
            ft.Row(acoes, wrap=True, spacing=10),
            ft.Card(content=ft.Container(padding=12, content=gantt(dados["itens"], _referencia(dados)))),
        ])

    # ------------------------------------------------------------ modo "criar" / "revisar"

    def mostrar_formulario(revisao: bool):
        dados = carregar() if revisao else None
        base: Dict[str, Item] = {}
        linhas: List[_Linha] = []
        lista = ft.Column(spacing=0)
        aviso = ft.Text("", size=12)

        def recalcular(_linha=None):
            if not revisao:
                return
            atuais = [l for l in linhas if l.marcar.value]
            itens_base = [base.get(l.nome_atual) or l.item() for l in atuais]
            editados = {}
            for l in atuais:
                novo = l.item()
                if (l.nome_atual not in base or l.tocado) and novo.inicio and novo.entrega:
                    editados[l.nome_atual] = (novo.inicio, novo.entrega)
            for linha, (item, recalc) in zip(atuais, calc.recalcular(itens_base, editados)):
                if not linha.tocado:
                    linha.mostrar(item, recalc)
            page.update()

        def remover(linha):
            linhas.remove(linha)
            lista.controls.remove(linha.controle)
            recalcular()
            page.update()

        def adicionar(item: Item, marcado=True, pode_remover=False, posicao=None):
            linha = _Linha(item, marcado, pode_remover, recalcular, remover)
            if posicao is None:
                linhas.append(linha)
                lista.controls.append(linha.controle)
            else:
                linhas.insert(posicao, linha)
                lista.controls.insert(posicao, linha.controle)
            return linha

        if revisao:
            for item in dados["itens"]:
                base[item.nome] = item
                adicionar(item, True, pode_remover=not item.padrao)
        else:
            for item, marcado in calc.itens_padrao():
                adicionar(item, marcado)

        def novo_item(tipo):
            def acao(_):
                fim = len(linhas)
                if linhas and linhas[-1].tipo == MARCO and linhas[-1].padrao:
                    fim -= 1  # antes do "Liberado para obra"
                adicionar(Item("", tipo, depende_da_anterior=True), True, pode_remover=True, posicao=fim)
                page.update()
            return acao

        # escolha da decisão (só na revisão)
        decisoes = listar_decisoes_projeto(projeto.id) if revisao else []
        escolha = ft.Dropdown(
            label="Decisão que motivou", visible=revisao,
            options=[ft.DropdownOption(key=NOVA_DECISAO, text="Nova decisão…")] + [
                ft.DropdownOption(key=str(d.id), text=f"D-{d.numero:03d} · {d.titulo}"[:90])
                for d in sorted(decisoes, key=lambda d: -(d.numero or 0))],
        )
        titulo_nova = ft.TextField(label="Título da nova decisão", col=col(12))
        categoria_nova = ft.Dropdown(label="Disciplina", value="Geral", col=col(12, md=6),
                                     options=[ft.DropdownOption(key=c, text=c) for c in CATEGORIAS])
        impacto_nova = ft.Dropdown(label="Impacto", value="Médio", col=col(12, md=6),
                                   options=[ft.DropdownOption(key=i, text=i) for i in IMPACTOS])
        justificativa_nova = ft.TextField(label="Justificativa", multiline=True, min_lines=2, col=col(12))
        bloco_nova = ft.ResponsiveRow([titulo_nova, categoria_nova, impacto_nova, justificativa_nova],
                                      visible=False)

        def ao_escolher(_):
            bloco_nova.visible = escolha.value == NOVA_DECISAO
            page.update()

        escolha.on_select = ao_escolher

        def salvar(_):
            itens = [l.item() for l in linhas if l.marcar.value]
            try:
                with nova_sessao() as s:
                    ator = ator_por_id(s, usuario.id)
                    if revisao:
                        if not escolha.value:
                            raise ValueError("Indique a decisão que motivou a revisão do cronograma.")
                        if escolha.value == NOVA_DECISAO:
                            servico.revisar(s, ator, projeto.id, itens, nova_decisao={
                                "titulo": titulo_nova.value, "categoria": categoria_nova.value,
                                "impacto": impacto_nova.value, "justificativa": justificativa_nova.value,
                                "descricao": titulo_nova.value})
                        else:
                            servico.revisar(s, ator, projeto.id, itens, decisao_id=int(escolha.value))
                    else:
                        servico.criar(s, ator, projeto.id, itens)
            except Exception as erro:  # validação e permissão chegam aqui com mensagem pronta
                aviso.color = ft.Colors.ERROR
                aviso.value = str(erro)
                page.update()
                return
            mensagem.color = tema.sucesso(page)
            mensagem.value = "Cronograma revisado." if revisao else "Cronograma criado (versão 1, linha de base)."
            estado["versao_vista"] = None
            entrar("ver")

        corpo.controls.clear()
        corpo.controls.extend([
            ft.Text("Revisar cronograma" if revisao else "Criar cronograma", size=18, weight=ft.FontWeight.BOLD),
            ft.Text("Mude a entrega de uma etapa e as seguintes se recalculam. Desmarque \"Depende da "
                    "anterior\" para etapas que correm em paralelo." if revisao else
                    "Marque as etapas do projeto e informe as datas (dd/mm/aaaa). Esta será a versão 1, "
                    "a linha de base.", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
            ft.Card(content=ft.Container(padding=12, content=lista)),
            ft.Row(wrap=True, controls=[
                ft.Button(content="+ Adicionar etapa", on_click=novo_item(ETAPA)),
                ft.Button(content="+ Adicionar marco", on_click=novo_item(MARCO)),
            ]),
            escolha,
            bloco_nova,
            aviso,
            ft.Row(wrap=True, controls=[
                ft.Button(content="Salvar revisão" if revisao else "Salvar cronograma", icon=ft.Icons.SAVE,
                          on_click=salvar),
                ft.TextButton(content="Cancelar", on_click=lambda _: entrar("ver")),
            ]),
        ])

    # ------------------------------------------------------------ montagem

    def montar():
        if projeto is None:
            corpo.controls = [ft.Text("Sem projeto ativo.")]
        elif estado["modo"] == "ver":
            mostrar_ver()
        else:
            mostrar_formulario(estado["modo"] == "revisar")
        page.update()

    def entrar(modo):
        if modo != "ver":
            mensagem.value = ""
        estado["modo"] = modo
        montar()

    header = ft.Container(
        padding=ft.Padding.symmetric(horizontal=18, vertical=14),
        bgcolor=ft.Colors.SURFACE_CONTAINER,
        border_radius=14,
        content=ft.ResponsiveRow(controls=[
            ft.Column(col=col(12, md=6), controls=[
                marca_cabecalho(),
                ft.Text("Cronograma", size=22, weight=ft.FontWeight.BOLD),
                ft.Text(f"Projeto Ativo: {projeto.nome}" if projeto else "Sem projeto", size=14,
                        color=ft.Colors.PRIMARY),
            ]),
            ft.Row(col=col(12, md=6), wrap=True, alignment=ft.MainAxisAlignment.END, controls=[
                ft.IconButton(icon=ft.Icons.HOME, tooltip="Ir para a linha do tempo", on_click=on_voltar),
                tema.botao_secundario("Linha do tempo", ft.Icons.TIMELINE, on_voltar),
                ft.IconButton(icon=ft.Icons.LOGOUT, tooltip="Sair", on_click=on_logout),
            ]),
        ]),
    )
    montar()
    return ft.View(route="/cronograma", controls=[header, mensagem, corpo])

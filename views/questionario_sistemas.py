import flet as ft

from database import obter_padrao_construtivo, salvar_padrao_construtivo
from ficha_calculos import numero_br
from models import TipologiaProjeto


def _opcoes(*rotulos):
    return [ft.dropdown.Option(r) for r in rotulos]


def criar_aba_sistemas_construtivos(page, projeto, usuario, pode_editar: bool):
    """Formulário de sistemas construtivos, variável conforme a tipologia."""
    painel_dinamico = ft.Column(spacing=10)
    campos = {}
    mensagem = ft.Text("", size=12)
    salvo = obter_padrao_construtivo(projeto.id) if projeto else None

    def _dropdown(label, opcoes, valor=None):
        return ft.Dropdown(
            label=label,
            options=_opcoes(*opcoes),
            value=valor,
            disabled=not pode_editar,
        )

    def montar_campos(tipologia: str, valores=None):
        valores = valores or {}
        campos.clear()
        painel_dinamico.controls.clear()
        if not tipologia:
            return

        if tipologia == TipologiaProjeto.industrial.value:
            campos["ind_estrutura"] = _dropdown(
                "Estrutura principal",
                ("Pré-moldado de concreto", "Metálica", "Mista (Concreto e Metálica)"),
                valores.get("ind_estrutura"),
            )
            campos["ind_vedacao"] = _dropdown(
                "Vedações",
                (
                    "Blocos",
                    "Telhas",
                    "Mistas (Blocos e Telhas)",
                    "Painéis pré-moldados",
                    "Painéis termo-isolantes",
                ),
                valores.get("ind_vedacao"),
            )
            campos["ind_carga_piso"] = ft.TextField(
                label="Carga de piso (ton/m²)",
                value="" if valores.get("ind_carga_piso") is None else str(valores["ind_carga_piso"]),
                keyboard_type=ft.KeyboardType.NUMBER,
                read_only=not pode_editar,
            )
            campos["ind_pavimento_externo"] = ft.RadioGroup(
                value=valores.get("ind_pavimento_externo"),
                content=ft.Row(
                    wrap=True,
                    controls=[
                        ft.Radio(
                            value="Rígido",
                            label="Pavimento externo rígido",
                            disabled=not pode_editar,
                        ),
                        ft.Radio(
                            value="Flexível",
                            label="Pavimento externo flexível",
                            disabled=not pode_editar,
                        ),
                    ],
                ),
            )
            painel_dinamico.controls.extend(
                [
                    ft.Text("Parâmetros do prédio industrial", weight=ft.FontWeight.BOLD),
                    campos["ind_estrutura"],
                    campos["ind_vedacao"],
                    campos["ind_carga_piso"],
                    campos["ind_pavimento_externo"],
                ]
            )
        elif tipologia == TipologiaProjeto.multifamiliar.value:
            campos["multi_sistema_principal"] = _dropdown(
                "Sistema estrutural",
                (
                    "Alvenaria estrutural",
                    "Concreto armado convencional",
                    "Paredes de concreto in loco",
                ),
                valores.get("multi_sistema_principal"),
            )
            campos["multi_tipo_laje"] = _dropdown(
                "Tipologia de laje",
                ("Maciça", "Treliçada", "Nervurada"),
                valores.get("multi_tipo_laje"),
            )
            painel_dinamico.controls.extend(
                [
                    ft.Text("Parâmetros multifamiliar", weight=ft.FontWeight.BOLD),
                    campos["multi_sistema_principal"],
                    campos["multi_tipo_laje"],
                ]
            )
        elif tipologia == TipologiaProjeto.corporativo.value:
            campos["corp_fachada"] = _dropdown(
                "Fachada",
                ("Cortina de vidro", "ACM", "Concreto aparente", "Mista"),
                valores.get("corp_fachada"),
            )
            painel_dinamico.controls.extend(
                [
                    ft.Text("Parâmetros corporativo", weight=ft.FontWeight.BOLD),
                    campos["corp_fachada"],
                ]
            )
        elif tipologia == TipologiaProjeto.shopping.value:
            campos["shop_estrutura"] = _dropdown(
                "Sistema estrutural",
                ("Concreto armado", "Metálica", "Mista"),
                valores.get("shop_estrutura"),
            )
            campos["shop_cobertura"] = _dropdown(
                "Cobertura",
                ("Telha metálica", "Laje impermeabilizada", "Mista"),
                valores.get("shop_cobertura"),
            )
            painel_dinamico.controls.extend(
                [
                    ft.Text("Parâmetros shopping center", weight=ft.FontWeight.BOLD),
                    campos["shop_estrutura"],
                    campos["shop_cobertura"],
                ]
            )
        elif tipologia == TipologiaProjeto.datacenter.value:
            campos["dc_tier_redundancia"] = _dropdown(
                "Tier / redundância",
                ("Tier I", "Tier II", "Tier III", "Tier IV", "N+1", "2N"),
                valores.get("dc_tier_redundancia"),
            )
            painel_dinamico.controls.extend(
                [
                    ft.Text("Parâmetros data center", weight=ft.FontWeight.BOLD),
                    campos["dc_tier_redundancia"],
                ]
            )

        btn_guardar.visible = bool(tipologia) and pode_editar

    def valores_salvos():
        if salvo is None:
            return {}
        return {
            "ind_estrutura": salvo.ind_estrutura,
            "ind_vedacao": salvo.ind_vedacao,
            "ind_carga_piso": salvo.ind_carga_piso,
            "ind_pavimento_externo": salvo.ind_pavimento_externo,
            "multi_sistema_principal": salvo.multi_sistema_principal,
            "multi_tipo_laje": salvo.multi_tipo_laje,
            "corp_fachada": salvo.corp_fachada,
            "dc_tier_redundancia": salvo.dc_tier_redundancia,
            "shop_estrutura": salvo.shop_estrutura,
            "shop_cobertura": salvo.shop_cobertura,
        }

    def atualizar_formulario(_=None):
        mensagem.value = ""
        montar_campos(dropdown_tipologia.value, valores_salvos() if _mesmo_salvo() else {})
        page.update()

    def _mesmo_salvo() -> bool:
        return salvo is not None and dropdown_tipologia.value == salvo.tipologia

    def guardar_dados(_):
        if projeto is None or not pode_editar:
            return
        tipologia = dropdown_tipologia.value
        if not tipologia:
            mensagem.color = ft.Colors.RED_400
            mensagem.value = "Selecione a tipologia do projeto."
            page.update()
            return
        dados = {"tipologia": tipologia}
        for nome, controle in campos.items():
            valor = controle.value
            if nome == "ind_carga_piso":
                if valor:
                    numero = numero_br(valor)
                    if numero is None:
                        mensagem.color = ft.Colors.RED_400
                        mensagem.value = "Informe a carga de piso com um número válido."
                        page.update()
                        return
                    dados[nome] = numero
                else:
                    dados[nome] = None
            else:
                dados[nome] = valor or None
        try:
            salvar_padrao_construtivo(projeto.id, dados, usuario_id=usuario.id)
        except Exception as erro:
            mensagem.color = ft.Colors.RED_400
            mensagem.value = f"Não foi possível guardar: {erro}"
            page.update()
            return
        nonlocal salvo
        salvo = obter_padrao_construtivo(projeto.id)
        mensagem.color = ft.Colors.GREEN_400
        mensagem.value = "Premissas de sistemas construtivos guardadas."
        page.update()

    btn_guardar = ft.ElevatedButton(
        "Guardar premissas",
        on_click=guardar_dados,
        visible=False,
    )
    dropdown_tipologia = ft.Dropdown(
        label="Selecione a tipologia do projeto",
        options=_opcoes(*(t.value for t in TipologiaProjeto)),
        value=salvo.tipologia if salvo else None,
        on_change=atualizar_formulario,
        disabled=not pode_editar,
    )
    if dropdown_tipologia.value:
        montar_campos(dropdown_tipologia.value, valores_salvos())

    if projeto is None:
        return ft.Column(
            [ft.Text("Sem projeto ativo.", color=ft.Colors.GREY_400)],
            expand=True,
        )

    return ft.Column(
        [
            ft.Text("Padronização de sistemas construtivos", size=20, weight=ft.FontWeight.BOLD),
            dropdown_tipologia,
            ft.Divider(),
            painel_dinamico,
            mensagem,
            btn_guardar,
        ],
        expand=True,
        scroll=ft.ScrollMode.AUTO,
        spacing=12,
    )

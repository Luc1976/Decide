"""
Decidiu — Painel do administrador (acesso exclusivo).

Só é exibido para e-mails listados na variável de ambiente ADMIN_EMAILS.
A checagem é feita aqui, no servidor, toda vez que a tela é montada.
"""

from __future__ import annotations

import flet as ft

from eventos import TipoEvento, eh_admin, metricas, registrar_evento

AZUL = "#0F2232"
AZUL_CLARO = "#3A6D8C"
CINZA = "#6B7785"
FUNDO_CARD = "#F3F6F9"

NOMES_EVENTO = {
    TipoEvento.CADASTRO: "Cadastro",
    TipoEvento.LOGIN: "Login",
    TipoEvento.LOGIN_FALHOU: "Login falhou",
    TipoEvento.ACESSO: "Acesso",
    TipoEvento.TRIAL_INICIADO: "Trial iniciado",
    TipoEvento.ASSINATURA_ATIVADA: "Assinatura ativada",
    TipoEvento.ASSINATURA_CANCELADA: "Assinatura cancelada",
    TipoEvento.PROJETO_CRIADO: "Projeto criado",
    TipoEvento.DECISAO_CRIADA: "Decisão criada",
    TipoEvento.ATA_CRIADA: "Ata criada",
    TipoEvento.RELATORIO_PDF: "Relatório PDF",
    TipoEvento.ACESSO_ADMIN_NEGADO: "Acesso ao painel negado",
}


# --------------------------------------------------------------------------- #
# Componentes
# --------------------------------------------------------------------------- #
def _card(titulo: str, valor: str, subtitulo: str = "") -> ft.Container:
    linhas = [
        ft.Text(titulo, size=12, color=CINZA),
        ft.Text(valor, size=26, weight=ft.FontWeight.BOLD, color=AZUL),
    ]
    if subtitulo:
        linhas.append(ft.Text(subtitulo, size=11, color=CINZA))
    return ft.Container(
        content=ft.Column(linhas, spacing=2, tight=True),
        bgcolor=FUNDO_CARD,
        border_radius=10,
        padding=14,
        width=165,
    )


def _grafico_barras(serie: list) -> ft.Control:
    """Barras simples feitas com Containers (não depende de pacote de gráficos)."""
    maximo = max((v for _, v in serie), default=0) or 1
    altura = 110
    barras = []
    for dia, valor in serie:
        h = max(2, int(valor / maximo * altura))
        barras.append(
            ft.Column(
                [
                    ft.Text(str(valor) if valor else "", size=9, color=CINZA),
                    ft.Container(
                        width=8,
                        height=h,
                        bgcolor=AZUL if valor else "#D5DDE5",
                        border_radius=2,
                        tooltip=f"{dia:%d/%m}: {valor} cadastro(s)",
                    ),
                ],
                spacing=2,
                alignment=ft.MainAxisAlignment.END,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                height=altura + 16,
            )
        )
    inicio, fim = serie[0][0], serie[-1][0]
    return ft.Column(
        [
            ft.Row(barras, spacing=3, scroll=ft.ScrollMode.AUTO,
                   vertical_alignment=ft.CrossAxisAlignment.END),
            ft.Row(
                [ft.Text(f"{inicio:%d/%m}", size=10, color=CINZA),
                 ft.Text(f"{fim:%d/%m}", size=10, color=CINZA)],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            ),
        ],
        spacing=4,
    )


def _tabela_eventos(eventos: list) -> ft.Control:
    if not eventos:
        return ft.Text("Nenhum evento registrado ainda.", color=CINZA)
    return ft.Column(
        [
            ft.Container(
                content=ft.Row(
                    [
                        ft.Text(e["quando"], size=12, color=CINZA, width=80),
                        ft.Text(NOMES_EVENTO.get(e["tipo"], e["tipo"]), size=12,
                                weight=ft.FontWeight.W_500, width=150),
                        ft.Text(e["email"], size=12, color=CINZA, expand=True,
                                overflow=ft.TextOverflow.ELLIPSIS),
                    ],
                    spacing=8,
                ),
                padding=ft.Padding(left=0, top=6, right=0, bottom=6),
                border=ft.Border(bottom=ft.BorderSide(1, "#E4E9EE")),
            )
            for e in eventos
        ],
        spacing=0,
    )


def _secao(titulo: str, conteudo: ft.Control) -> ft.Column:
    return ft.Column(
        [ft.Text(titulo, size=15, weight=ft.FontWeight.BOLD, color=AZUL), conteudo],
        spacing=8,
    )


# --------------------------------------------------------------------------- #
# Tela
# --------------------------------------------------------------------------- #
def painel_admin(page: ft.Page, usuario_id, usuario_email: str) -> ft.Control:
    """Monta o painel. Se o usuário não for admin, devolve aviso e registra a tentativa."""
    if not eh_admin(usuario_email):
        registrar_evento(TipoEvento.ACESSO_ADMIN_NEGADO,
                         usuario_id=usuario_id, usuario_email=usuario_email)
        return ft.Container(
            content=ft.Text("Página não encontrada.", size=16, color=CINZA),
            padding=40,
        )

    corpo = ft.Column(spacing=22, scroll=ft.ScrollMode.AUTO, expand=True)

    def carregar(_=None, atualizar: bool = True):
        corpo.controls.clear()
        try:
            m = metricas()
        except Exception as erro:  # noqa: BLE001
            corpo.controls.append(ft.Text(f"Erro ao carregar métricas: {erro}", color="#B3261E"))
            if atualizar:
                page.update()
            return

        corpo.controls.extend(
            [
                _secao(
                    "Cadastros",
                    ft.Row(
                        [
                            _card("Total", str(m["cadastros_total"])),
                            _card("Últimos 7 dias", str(m["cadastros_7d"])),
                            _card("Últimos 30 dias", str(m["cadastros_30d"])),
                        ],
                        wrap=True, spacing=10, run_spacing=10,
                    ),
                ),
                _secao(
                    "Usuários ativos",
                    ft.Row(
                        [
                            _card("Hoje", str(m["ativos_hoje"])),
                            _card("7 dias", str(m["ativos_7d"])),
                            _card("30 dias", str(m["ativos_30d"])),
                        ],
                        wrap=True, spacing=10, run_spacing=10,
                    ),
                ),
                _secao(
                    "Trial e assinaturas",
                    ft.Row(
                        [
                            _card("Trials iniciados", str(m["trials_total"])),
                            _card("Assinaturas", str(m["assinaturas_total"]),
                                  f"Conversão {m['conversao_trial']:.0f}%"),
                            _card("Cancelamentos", str(m["cancelamentos_total"])),
                        ],
                        wrap=True, spacing=10, run_spacing=10,
                    ),
                ),
                _secao(
                    "Uso do app (30 dias)",
                    ft.Row(
                        [
                            _card("Projetos criados", str(m["projetos_30d"])),
                            _card("Decisões criadas", str(m["decisoes_30d"])),
                            _card("Logins falhos (7d)", str(m["logins_falhos_7d"]),
                                  "Atenção se subir muito"),
                        ],
                        wrap=True, spacing=10, run_spacing=10,
                    ),
                ),
                _secao("Cadastros por dia (30 dias)", _grafico_barras(m["cadastros_por_dia"])),
                _secao("Últimos 50 eventos", _tabela_eventos(m["ultimos_eventos"])),
            ]
        )
        if atualizar:
            page.update()

    cabecalho = ft.Row(
        [
            ft.Text("Painel do administrador", size=20, weight=ft.FontWeight.BOLD, color=AZUL),
            ft.TextButton("Atualizar", on_click=carregar),
        ],
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
    )

    carregar(atualizar=False)  # preenche antes de a tela ser exibida
    return ft.Container(
        content=ft.Column([cabecalho, corpo], spacing=16, expand=True),
        padding=16,
        expand=True,
    )

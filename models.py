"""Opções de domínio usadas na memória de decisões."""

CATEGORIAS = (
    "Arquitetura",
    "Arquitetura de Interiores",
    "Estrutura",
    "Fundações",
    "instalações",
    "Elétrica",
    "Hidrossanitário",
    "HVAC",
    "PPCI",
    "Urbanismo",
    "Orçamento",
    "Geral",
)
IMPACTOS = ("Alto", "Médio", "Baixo")


# --- Ficha de características do empreendimento ---
# Cada campo é (nome, unidade). Para um campo novo, basta acrescentar aqui:
# não precisa alterar o banco (os valores são guardados por grupo + nome).
GRUPO_OUTRAS = "Outras características"  # campos personalizados, criados na tela

CAMPO_AREA_TERRENO = "Área do terreno"
CAMPO_TO = "Taxa de ocupação (TO)"
CAMPO_CA = "Coeficiente de aproveitamento (CA)"
CAMPO_TP = "Taxa de permeabilidade"
CAMPO_AREA_CONSTRUIDA = "Área construída total prevista"

FICHA_GRUPOS = {
    "Terreno e localização": [
        ("Endereço / localização", ""),
        (CAMPO_AREA_TERRENO, "m²"),
        ("Testada", "m"),
        ("Topografia e condicionantes", ""),
    ],
    "Parâmetros urbanísticos": [
        ("Zoneamento", ""),
        (CAMPO_TO, "%"),
        (CAMPO_CA, ""),
        (CAMPO_TP, "%"),
        ("Gabarito / altura máxima", "m"),
        ("Recuos (frontal / laterais / fundos)", "m"),
    ],
    "Programa": [
        ("Uso / tipologia", ""),
        ("Nº de unidades", ""),
        ("Nº de pavimentos", ""),
        (CAMPO_AREA_CONSTRUIDA, "m²"),
        ("Vagas de garagem", ""),
    ],
    "Padrão, prazo e custo": [
        ("Padrão de acabamento", ""),
        ("Orçamento estimado", "R$"),
        ("Prazo previsto", "meses"),
    ],
    "Premissas do cliente": [
        ("Premissas e requisitos", ""),
    ],
}
CAMPOS_LONGOS = {"Topografia e condicionantes", "Premissas e requisitos"}


# --- Acesso por projeto ---
# Leitor      (cliente): acompanha decisões, atas fechadas e ficha; não altera nada.
# Editor      : além de ler, registra decisões, atas e altera a ficha.
# Responsável : além de editar, altera os dados do projeto e gerencia os membros.
# Administrador (flag no usuário) vale como Responsável em TODOS os projetos.
PAPEIS = ("Responsável", "Editor", "Leitor")
NIVEL_PAPEL = {"Leitor": 1, "Editor": 2, "Responsável": 3}
NIVEL_ADMIN = 4


# --- Padrão construtivo (campos específicos por tipologia) ---
# As tabelas agora ficam em nucleo/tabelas.py; reexportadas aqui para as telas Flet.
from nucleo.tabelas import PadraoConstrutivo, TipologiaProjeto  # noqa: E402,F401

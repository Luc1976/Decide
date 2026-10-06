"""Opções de domínio usadas na memória de decisões."""

from enum import Enum
from typing import Optional

from sqlmodel import Field, SQLModel

CATEGORIAS = ("Arquitetura", "Estrutura", "instalações", "Orçamento", "Geral")
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
class TipologiaProjeto(str, Enum):
    industrial = "Industrial"
    multifamiliar = "Multifamiliar"
    corporativo = "Corporativo"
    shopping = "Shopping Center"
    datacenter = "Data Center"


class PadraoConstrutivo(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    projeto_id: int = Field(foreign_key="projeto.id", index=True)
    tipologia: str

    # Campos industriais (nulos se a tipologia for outra)
    ind_estrutura: Optional[str] = None
    ind_vedacao: Optional[str] = None
    ind_carga_piso: Optional[float] = None
    ind_pavimento_externo: Optional[str] = None

    # Campos multifamiliar
    multi_sistema_principal: Optional[str] = None
    multi_tipo_laje: Optional[str] = None

    # Campos corporativo / data center
    corp_fachada: Optional[str] = None
    dc_tier_redundancia: Optional[str] = None

    # Campos shopping
    shop_estrutura: Optional[str] = None
    shop_cobertura: Optional[str] = None

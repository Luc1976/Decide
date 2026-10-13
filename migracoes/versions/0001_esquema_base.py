"""Esquema base (o banco como estava antes das organizações).

Revisão: 0001
Criada em: 2026-10-12

Esta migração é IDEMPOTENTE, para servir a dois casos:
- banco novo (PostgreSQL ou SQLite vazio): cria todas as tabelas;
- banco SQLite que já existe (o do Railway, criado pelo app antes do Alembic): só cria as
  tabelas que faltam e acrescenta as colunas antigas que bancos muito velhos não têm
  (o que antes era feito à mão em database._migrar_banco). Nenhum dado é apagado.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import context, op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _inspetor():
    return sa.inspect(op.get_bind())


def _existe(tabela: str) -> bool:
    if context.is_offline_mode():  # "upgrade --sql": gera o SQL de um banco vazio
        return False
    return _inspetor().has_table(tabela)


def _colunas(tabela: str) -> set:
    return {c["name"] for c in _inspetor().get_columns(tabela)}


def _criar_tabelas() -> None:
    if not _existe("usuario"):
        op.create_table(
            "usuario",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("username", sa.String(), nullable=False),
            sa.Column("senha", sa.String(), nullable=False),
            sa.Column("nome_completo", sa.String(), nullable=False),
            sa.Column("admin", sa.Boolean(), nullable=False),
            sa.Column("pode_criar_projetos", sa.Boolean(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("username"),
        )
    if not _existe("projeto"):
        op.create_table(
            "projeto",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("nome", sa.String(), nullable=False),
            sa.Column("cliente", sa.String(), nullable=False),
            sa.Column("descricao", sa.String(), nullable=True),
            sa.Column("data_criacao", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
    if not _existe("membroprojeto"):
        op.create_table(
            "membroprojeto",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("projeto_id", sa.Integer(), nullable=False),
            sa.Column("usuario_id", sa.Integer(), nullable=False),
            sa.Column("papel", sa.String(), nullable=False),
            sa.ForeignKeyConstraint(["projeto_id"], ["projeto.id"]),
            sa.ForeignKeyConstraint(["usuario_id"], ["usuario.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
    if not _existe("caracteristica"):
        op.create_table(
            "caracteristica",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("projeto_id", sa.Integer(), nullable=False),
            sa.Column("grupo", sa.String(), nullable=False),
            sa.Column("nome", sa.String(), nullable=False),
            sa.Column("valor", sa.String(), nullable=False),
            sa.Column("unidade", sa.String(), nullable=True),
            sa.Column("atualizado_por", sa.String(), nullable=False),
            sa.Column("data_atualizacao", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["projeto_id"], ["projeto.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
    if not _existe("padraoconstrutivo"):
        op.create_table(
            "padraoconstrutivo",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("projeto_id", sa.Integer(), nullable=False),
            sa.Column("tipologia", sa.String(), nullable=False),
            sa.Column("ind_estrutura", sa.String(), nullable=True),
            sa.Column("ind_vedacao", sa.String(), nullable=True),
            sa.Column("ind_carga_piso", sa.Float(), nullable=True),
            sa.Column("ind_pavimento_externo", sa.String(), nullable=True),
            sa.Column("multi_sistema_principal", sa.String(), nullable=True),
            sa.Column("multi_tipo_laje", sa.String(), nullable=True),
            sa.Column("corp_fachada", sa.String(), nullable=True),
            sa.Column("dc_tier_redundancia", sa.String(), nullable=True),
            sa.Column("shop_estrutura", sa.String(), nullable=True),
            sa.Column("shop_cobertura", sa.String(), nullable=True),
            sa.ForeignKeyConstraint(["projeto_id"], ["projeto.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_padraoconstrutivo_projeto_id", "padraoconstrutivo", ["projeto_id"])
    if not _existe("reuniao"):
        op.create_table(
            "reuniao",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("projeto_id", sa.Integer(), nullable=False),
            sa.Column("numero", sa.Integer(), nullable=False),
            sa.Column("titulo", sa.String(), nullable=False),
            sa.Column("data_reuniao", sa.Date(), nullable=False),
            sa.Column("participantes", sa.String(), nullable=True),
            sa.Column("texto", sa.String(), nullable=False),
            sa.Column("status", sa.String(), nullable=False),
            sa.Column("autor", sa.String(), nullable=False),
            sa.Column("data_fechamento", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["projeto_id"], ["projeto.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
    if not _existe("ataadendo"):
        op.create_table(
            "ataadendo",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("reuniao_id", sa.Integer(), nullable=False),
            sa.Column("texto", sa.String(), nullable=False),
            sa.Column("autor", sa.String(), nullable=False),
            sa.Column("data_registro", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["reuniao_id"], ["reuniao.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
    if not _existe("decisao"):
        op.create_table(
            "decisao",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("projeto_id", sa.Integer(), nullable=False),
            sa.Column("titulo", sa.String(), nullable=False),
            sa.Column("categoria", sa.String(), nullable=False),
            sa.Column("descricao", sa.String(), nullable=False),
            sa.Column("justificativa", sa.String(), nullable=False),
            sa.Column("alternativa_descartada", sa.String(), nullable=True),
            sa.Column("impacto", sa.String(), nullable=False),
            sa.Column("autor", sa.String(), nullable=False),
            sa.Column("data_decisao", sa.Date(), nullable=False),
            sa.Column("anexos", sa.String(), nullable=True),
            sa.Column("checklist", sa.String(), nullable=True),
            sa.Column("reuniao_id", sa.Integer(), nullable=True),
            sa.Column("numero", sa.Integer(), nullable=True),
            sa.ForeignKeyConstraint(["projeto_id"], ["projeto.id"]),
            sa.ForeignKeyConstraint(["reuniao_id"], ["reuniao.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
    if not _existe("caracteristicahistorico"):
        op.create_table(
            "caracteristicahistorico",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("projeto_id", sa.Integer(), nullable=False),
            sa.Column("grupo", sa.String(), nullable=False),
            sa.Column("nome", sa.String(), nullable=False),
            sa.Column("valor_anterior", sa.String(), nullable=True),
            sa.Column("valor_novo", sa.String(), nullable=True),
            sa.Column("autor", sa.String(), nullable=False),
            sa.Column("data_registro", sa.DateTime(), nullable=False),
            sa.Column("decisao_id", sa.Integer(), nullable=True),
            sa.Column("reuniao_id", sa.Integer(), nullable=True),
            sa.ForeignKeyConstraint(["decisao_id"], ["decisao.id"]),
            sa.ForeignKeyConstraint(["projeto_id"], ["projeto.id"]),
            sa.ForeignKeyConstraint(["reuniao_id"], ["reuniao.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
    if not _existe("pendencia"):
        op.create_table(
            "pendencia",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("projeto_id", sa.Integer(), nullable=False),
            sa.Column("numero", sa.Integer(), nullable=False),
            sa.Column("titulo", sa.String(), nullable=False),
            sa.Column("descricao", sa.String(), nullable=False),
            sa.Column("categoria", sa.String(), nullable=False),
            sa.Column("responsavel", sa.String(), nullable=False),
            sa.Column("prazo", sa.Date(), nullable=True),
            sa.Column("status", sa.String(), nullable=False),
            sa.Column("autor", sa.String(), nullable=False),
            sa.Column("data_criacao", sa.DateTime(), nullable=False),
            sa.Column("reuniao_id", sa.Integer(), nullable=True),
            sa.Column("decisao_id", sa.Integer(), nullable=True),
            sa.Column("resolucao", sa.String(), nullable=False),
            sa.Column("resolvida_por", sa.String(), nullable=False),
            sa.Column("data_resolucao", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["decisao_id"], ["decisao.id"]),
            sa.ForeignKeyConstraint(["projeto_id"], ["projeto.id"]),
            sa.ForeignKeyConstraint(["reuniao_id"], ["reuniao.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_pendencia_projeto_id", "pendencia", ["projeto_id"])
    if not _existe("registroauditoria"):
        op.create_table(
            "registroauditoria",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("momento", sa.DateTime(), nullable=False),
            sa.Column("usuario_id", sa.Integer(), nullable=True),
            sa.Column("usuario_nome", sa.String(), nullable=False),
            sa.Column("acao", sa.String(), nullable=False),
            sa.Column("projeto_id", sa.Integer(), nullable=True),
            sa.Column("alvo_tipo", sa.String(), nullable=True),
            sa.Column("alvo_id", sa.Integer(), nullable=True),
            sa.Column("detalhes", sa.String(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
        for coluna in ("momento", "usuario_id", "acao", "projeto_id"):
            op.create_index(f"ix_registroauditoria_{coluna}", "registroauditoria", [coluna])


def _completar_bancos_antigos() -> None:
    """Colunas que o app acrescentava à mão em bancos SQLite antigos."""
    conexao = op.get_bind()
    if conexao.dialect.name != "sqlite":
        return  # PostgreSQL sempre nasce por esta migração, já completo

    def alterar(sql: str) -> None:
        conexao.exec_driver_sql(sql)

    colunas = _colunas("decisao")
    if "reuniao_id" not in colunas:
        alterar("ALTER TABLE decisao ADD COLUMN reuniao_id INTEGER REFERENCES reuniao(id)")
    if "numero" not in colunas:
        alterar("ALTER TABLE decisao ADD COLUMN numero INTEGER")

    colunas = _colunas("caracteristicahistorico")
    if "decisao_id" not in colunas:
        alterar("ALTER TABLE caracteristicahistorico ADD COLUMN decisao_id INTEGER REFERENCES decisao(id)")
    if "reuniao_id" not in colunas:
        alterar("ALTER TABLE caracteristicahistorico ADD COLUMN reuniao_id INTEGER REFERENCES reuniao(id)")

    if "pode_criar_projetos" not in _colunas("usuario"):
        alterar("ALTER TABLE usuario ADD COLUMN pode_criar_projetos BOOLEAN NOT NULL DEFAULT 1")
        # Banco de antes das permissões: todos viam todos os projetos. Para ninguém perder
        # acesso, cada usuário comum vira Editor dos projetos que já existem.
        alterar(
            "INSERT INTO membroprojeto (projeto_id, usuario_id, papel) "
            "SELECT p.id, u.id, 'Editor' FROM projeto p CROSS JOIN usuario u WHERE u.admin = 0"
        )

    colunas = _colunas("padraoconstrutivo")
    for nome in ("shop_estrutura", "shop_cobertura"):
        if nome not in colunas:
            alterar(f"ALTER TABLE padraoconstrutivo ADD COLUMN {nome} TEXT")


def upgrade() -> None:
    banco_existente = _existe("usuario")
    _criar_tabelas()  # primeiro: o que falta (num banco muito antigo, até membroprojeto)
    if banco_existente:
        _completar_bancos_antigos()


def downgrade() -> None:
    # Esta é a base: voltar dela apagaria o banco inteiro. De propósito, não faz nada.
    pass

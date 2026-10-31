"""Cronograma macro do projeto: versões (ligadas a decisões) e seus itens.

Revisão: 0012
Anterior: 0011
Criada em: 2026-10-31

Só cria as tabelas cronogramaversao e cronogramaitem. Nenhum dado existente é alterado.
"""
from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel
from alembic import op

revision: str = "0012"
down_revision: Union[str, None] = "0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "cronogramaversao",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("projeto_id", sa.Integer(), nullable=False),
        sa.Column("numero", sa.Integer(), nullable=False),
        sa.Column("criado_em", sa.DateTime(), nullable=False),
        sa.Column("autor", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("decisao_id", sa.Integer(), nullable=True),
        sa.Column("observacao", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.ForeignKeyConstraint(["projeto_id"], ["projeto.id"]),
        sa.ForeignKeyConstraint(["decisao_id"], ["decisao.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("projeto_id", "numero", name="uq_cronograma_projeto_numero"),
    )
    op.create_index("ix_cronogramaversao_projeto_id", "cronogramaversao", ["projeto_id"])
    op.create_table(
        "cronogramaitem",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("versao_id", sa.Integer(), nullable=False),
        sa.Column("ordem", sa.Integer(), nullable=False),
        sa.Column("nome", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("tipo", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("inicio", sa.Date(), nullable=False),
        sa.Column("entrega", sa.Date(), nullable=False),
        sa.Column("depende_da_anterior", sa.Boolean(), nullable=False),
        sa.Column("padrao", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["versao_id"], ["cronogramaversao.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_cronogramaitem_versao_id", "cronogramaitem", ["versao_id"])


def downgrade() -> None:
    op.drop_index("ix_cronogramaitem_versao_id", table_name="cronogramaitem")
    op.drop_table("cronogramaitem")
    op.drop_index("ix_cronogramaversao_projeto_id", table_name="cronogramaversao")
    op.drop_table("cronogramaversao")

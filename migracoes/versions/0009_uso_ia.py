"""Contador mensal de transcrições de IA por organização (limite conforme o plano).

Revisão: 0009
Anterior: 0008
Criada em: 2026-10-26

Só cria a tabela nova. Nenhum dado existente é alterado.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "usoia",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organizacao_id", sa.Integer(), nullable=False),
        sa.Column("ano_mes", sa.String(length=7), nullable=False),
        sa.Column("quantidade", sa.Integer(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organizacao_id", "ano_mes", name="uq_usoia_org_mes"),
    )
    op.create_index("ix_usoia_organizacao_id", "usoia", ["organizacao_id"])


def downgrade() -> None:
    op.drop_index("ix_usoia_organizacao_id", table_name="usoia")
    op.drop_table("usoia")

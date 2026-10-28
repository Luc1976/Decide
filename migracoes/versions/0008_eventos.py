"""Tabela de eventos de uso (cadastros, logins, projetos, decisões, assinaturas) para o painel
do administrador.

Revisão: 0008
Anterior: 0007
Criada em: 2026-10-26

Só cria a tabela nova. Nenhum dado existente é alterado.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "eventos",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tipo", sa.String(length=50), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=True),
        sa.Column("usuario_email", sa.String(length=255), nullable=True),
        sa.Column("projeto_id", sa.Integer(), nullable=True),
        sa.Column("detalhes", sa.JSON(), nullable=True),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_eventos_tipo", "eventos", ["tipo"])
    op.create_index("ix_eventos_usuario_id", "eventos", ["usuario_id"])
    op.create_index("ix_eventos_criado_em", "eventos", ["criado_em"])


def downgrade() -> None:
    op.drop_index("ix_eventos_criado_em", table_name="eventos")
    op.drop_index("ix_eventos_usuario_id", table_name="eventos")
    op.drop_index("ix_eventos_tipo", table_name="eventos")
    op.drop_table("eventos")

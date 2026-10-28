"""Link de pagamento parcelável para os planos anuais (cobrança no ato, até 10x).

Revisão: 0010
Anterior: 0009
Criada em: 2026-10-27

Só acrescenta duas colunas em organizacao. Nenhum dado existente é alterado.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("organizacao") as tabela:
        tabela.add_column(sa.Column("asaas_link_id", sa.String(), nullable=True))
        tabela.add_column(sa.Column("asaas_link_url", sa.String(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("organizacao") as tabela:
        tabela.drop_column("asaas_link_url")
        tabela.drop_column("asaas_link_id")

"""Preferência de aparência (modo claro ou escuro) de cada usuário.

Revisão: 0003
Anterior: 0002
Criada em: 2026-10-12

Coluna opcional: vazia = modo escuro, como o app sempre foi. Nenhum dado muda.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("usuario") as tabela:
        tabela.add_column(sa.Column("tema", sa.String(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("usuario") as tabela:
        tabela.drop_column("tema")

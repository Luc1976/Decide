"""Projetos arquivados e aceite dos Termos no cadastro.

Revisão: 0007
Anterior: 0006
Criada em: 2026-10-24

Projeto arquivado sai das listas e não conta no limite do plano. Os projetos existentes
continuam ativos. Termos: guarda quando o usuário aceitou os Termos de Serviço.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("projeto") as tabela:
        tabela.add_column(sa.Column("arquivado", sa.Boolean(), nullable=False, server_default=sa.false()))
    with op.batch_alter_table("usuario") as tabela:
        tabela.add_column(sa.Column("termos_aceitos_em", sa.DateTime(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("usuario") as tabela:
        tabela.drop_column("termos_aceitos_em")
    with op.batch_alter_table("projeto") as tabela:
        tabela.drop_column("arquivado")

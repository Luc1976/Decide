"""Assinatura (SaaS) na organização e e-mail do usuário.

Revisão: 0006
Anterior: 0005
Criada em: 2026-10-24

Organizações que já existem ficam 'interno' e 'ativa': são a operação atual, sem cobrança.
Só cadastros novos pelo site começam em 'teste'. O e-mail é opcional para quem já existe.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

COLUNAS_ORGANIZACAO = [
    "plano", "assinatura_status", "ciclo", "teste_fim",
    "fidelidade_fim", "asaas_cliente_id", "asaas_assinatura_id",
]


def upgrade() -> None:
    with op.batch_alter_table("organizacao") as tabela:
        tabela.add_column(sa.Column("plano", sa.String(), nullable=False, server_default="interno"))
        tabela.add_column(sa.Column("assinatura_status", sa.String(), nullable=False, server_default="ativa"))
        tabela.add_column(sa.Column("ciclo", sa.String(), nullable=True))
        tabela.add_column(sa.Column("teste_fim", sa.DateTime(), nullable=True))
        tabela.add_column(sa.Column("fidelidade_fim", sa.DateTime(), nullable=True))
        tabela.add_column(sa.Column("asaas_cliente_id", sa.String(), nullable=True))
        tabela.add_column(sa.Column("asaas_assinatura_id", sa.String(), nullable=True))

    with op.batch_alter_table("usuario") as tabela:
        tabela.add_column(sa.Column("email", sa.String(), nullable=True))
        tabela.add_column(sa.Column("email_verificado", sa.Boolean(), nullable=False,
                                    server_default=sa.false()))
        tabela.create_index("ix_usuario_email", ["email"], unique=True)


def downgrade() -> None:
    with op.batch_alter_table("usuario") as tabela:
        tabela.drop_index("ix_usuario_email")
        tabela.drop_column("email_verificado")
        tabela.drop_column("email")

    with op.batch_alter_table("organizacao") as tabela:
        for coluna in reversed(COLUNAS_ORGANIZACAO):
            tabela.drop_column(coluna)

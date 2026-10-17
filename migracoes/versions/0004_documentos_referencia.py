"""Documentos de referência: checklist de arquivos e informações recebidas por projeto.

Revisão: 0004
Anterior: 0003
Criada em: 2026-10-13

Cria a tabela e coloca a lista padrão (como "Pendente") em todos os projetos que já existem.
Projetos novos recebem a lista pelo serviço, ao serem criados.
"""
import datetime
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import context, op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Cópia congelada da lista padrão (a migração não deve depender do código que muda).
ITENS_PADRAO = (
    "Levantamento topográfico",
    "Projetos preliminares",
    "Layout",
    "Relatórios de Sondagens SPT",
    "Relatório de sondagem a trado (CBR)",
    "BEP / EIR",
    "Outros",
)


def upgrade() -> None:
    op.create_table(
        "documentoreferencia",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("projeto_id", sa.Integer(), nullable=False),
        sa.Column("nome", sa.String(), nullable=False),
        sa.Column("situacao", sa.String(), nullable=False),
        sa.Column("padrao", sa.Boolean(), nullable=False),
        sa.Column("ordem", sa.Integer(), nullable=False),
        sa.Column("observacao", sa.String(), nullable=False),
        sa.Column("anexos", sa.String(), nullable=True),
        sa.Column("data_recebimento", sa.Date(), nullable=True),
        sa.Column("recebido_por", sa.String(), nullable=False),
        sa.Column("atualizado_por", sa.String(), nullable=False),
        sa.Column("data_atualizacao", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["projeto_id"], ["projeto.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_documentoreferencia_projeto_id", "documentoreferencia", ["projeto_id"])

    if context.is_offline_mode():
        return
    conexao = op.get_bind()
    projetos = [linha[0] for linha in conexao.execute(sa.text("SELECT id FROM projeto")).all()]
    if not projetos:
        return
    agora = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
    tabela = sa.table(
        "documentoreferencia",
        *(sa.column(c) for c in ("projeto_id", "nome", "situacao", "padrao", "ordem", "observacao",
                                 "recebido_por", "atualizado_por")),
        sa.column("data_atualizacao", sa.DateTime()),
    )
    conexao.execute(tabela.insert(), [
        {"projeto_id": pid, "nome": nome, "situacao": "Pendente", "padrao": True, "ordem": i,
         "observacao": "", "recebido_por": "", "atualizado_por": "", "data_atualizacao": agora}
        for pid in projetos for i, nome in enumerate(ITENS_PADRAO, 1)
    ])


def downgrade() -> None:
    op.drop_index("ix_documentoreferencia_projeto_id", table_name="documentoreferencia")
    op.drop_table("documentoreferencia")

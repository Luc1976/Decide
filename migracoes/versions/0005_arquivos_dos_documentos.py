"""Arquivos dos documentos de referência com data de recebimento própria.

Revisão: 0005
Anterior: 0004
Criada em: 2026-10-13

Antes, os arquivos de cada item ficavam numa coluna de texto (separados por vírgula), sem
data. Agora cada arquivo é uma linha em 'documentoarquivo', com a data em que foi recebido.
Os arquivos que já existiam são convertidos: recebidos na data do item (ou na data da última
alteração dele, se o item não tiver data).
"""
import datetime
import os
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import context, op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _como_data(valor):
    if valor is None:
        return datetime.date.today()
    if isinstance(valor, datetime.datetime):
        return valor.date()
    if isinstance(valor, datetime.date):
        return valor
    return datetime.date.fromisoformat(str(valor)[:10])  # SQLite devolve texto em consultas cruas


def upgrade() -> None:
    op.create_table(
        "documentoarquivo",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("documento_id", sa.Integer(), nullable=False),
        sa.Column("chave", sa.String(), nullable=False),
        sa.Column("nome", sa.String(), nullable=False),
        sa.Column("data_recebimento", sa.Date(), nullable=False),
        sa.Column("enviado_por", sa.String(), nullable=False),
        sa.Column("data_envio", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["documento_id"], ["documentoreferencia.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_documentoarquivo_documento_id", "documentoarquivo", ["documento_id"])

    if not context.is_offline_mode():
        conexao = op.get_bind()
        linhas = conexao.execute(sa.text(
            "SELECT id, anexos, data_recebimento, atualizado_por, data_atualizacao "
            "FROM documentoreferencia WHERE anexos IS NOT NULL AND anexos <> ''"
        )).all()
        tabela = sa.table(
            "documentoarquivo", sa.column("documento_id"), sa.column("chave"), sa.column("nome"),
            sa.column("data_recebimento", sa.Date()), sa.column("enviado_por"),
            sa.column("data_envio", sa.DateTime()),
        )
        novos = []
        for doc_id, anexos, data_rec, autor, data_alt in linhas:
            envio = data_alt if isinstance(data_alt, datetime.datetime) else datetime.datetime.fromisoformat(str(data_alt))
            for chave in [c for c in anexos.split(",") if c]:
                novos.append({
                    "documento_id": doc_id, "chave": chave, "nome": os.path.basename(chave),
                    "data_recebimento": _como_data(data_rec or data_alt), "enviado_por": autor or "",
                    "data_envio": envio,
                })
        if novos:
            conexao.execute(tabela.insert(), novos)

    with op.batch_alter_table("documentoreferencia") as tabela:
        tabela.drop_column("anexos")


def downgrade() -> None:
    with op.batch_alter_table("documentoreferencia") as tabela:
        tabela.add_column(sa.Column("anexos", sa.String(), nullable=True))
    if not context.is_offline_mode():
        conexao = op.get_bind()
        por_doc = {}
        for doc_id, chave in conexao.execute(sa.text(
                "SELECT documento_id, chave FROM documentoarquivo ORDER BY id")).all():
            por_doc.setdefault(doc_id, []).append(chave)
        for doc_id, chaves in por_doc.items():
            conexao.execute(sa.text("UPDATE documentoreferencia SET anexos = :a WHERE id = :i"),
                            {"a": ",".join(chaves), "i": doc_id})
    op.drop_index("ix_documentoarquivo_documento_id", table_name="documentoarquivo")
    op.drop_table("documentoarquivo")

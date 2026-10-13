"""Organizações: isolamento entre os escritórios assinantes do SaaS.

Revisão: 0002
Anterior: 0001
Criada em: 2026-10-12

- tabela 'organizacao';
- usuario.organizacao_id, usuario.superadmin, projeto.organizacao_id,
  registroauditoria.organizacao_id.

Dados que já existem (banco do Railway): todos os usuários e projetos vão para UMA
organização, com o nome de DECIDIU_ORG_INICIAL (padrão "Organização principal"). O
administrador mais antigo vira também superadmin (dono da plataforma). Ninguém perde acesso.
"""
import datetime
import os
import re
import unicodedata
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import context, op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NOME_PADRAO = "Organização principal"


def _slug(nome: str) -> str:
    texto = unicodedata.normalize("NFKD", nome)
    texto = "".join(c for c in texto if not unicodedata.combining(c)).lower()
    return re.sub(r"[^a-z0-9]+", "-", texto).strip("-")[:60] or "organizacao"


def upgrade() -> None:
    op.create_table(
        "organizacao",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("nome", sa.String(), nullable=False),
        sa.Column("slug", sa.String(), nullable=False),
        sa.Column("ativa", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("data_criacao", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_organizacao_slug", "organizacao", ["slug"], unique=True)

    with op.batch_alter_table("usuario") as tabela:
        tabela.add_column(sa.Column("organizacao_id", sa.Integer(), nullable=True))
        tabela.add_column(sa.Column("superadmin", sa.Boolean(), nullable=False, server_default=sa.false()))
        tabela.create_index("ix_usuario_organizacao_id", ["organizacao_id"])
        tabela.create_foreign_key("fk_usuario_organizacao", "organizacao", ["organizacao_id"], ["id"])

    with op.batch_alter_table("projeto") as tabela:
        tabela.add_column(sa.Column("organizacao_id", sa.Integer(), nullable=True))
        tabela.create_index("ix_projeto_organizacao_id", ["organizacao_id"])
        tabela.create_foreign_key("fk_projeto_organizacao", "organizacao", ["organizacao_id"], ["id"])

    with op.batch_alter_table("registroauditoria") as tabela:
        tabela.add_column(sa.Column("organizacao_id", sa.Integer(), nullable=True))
        tabela.create_index("ix_registroauditoria_organizacao_id", ["organizacao_id"])

    _distribuir_dados_existentes()


def _distribuir_dados_existentes() -> None:
    if context.is_offline_mode():  # "upgrade --sql": sem banco, não há dados a distribuir
        return
    conexao = op.get_bind()
    usuario = sa.table("usuario", sa.column("id"), sa.column("admin"), sa.column("organizacao_id"),
                       sa.column("superadmin"))
    projeto = sa.table("projeto", sa.column("id"), sa.column("organizacao_id"))
    auditoria = sa.table("registroauditoria", sa.column("organizacao_id"))
    organizacao = sa.table("organizacao", sa.column("id"), sa.column("nome"), sa.column("slug"),
                           sa.column("ativa"), sa.column("data_criacao"))

    tem_usuarios = conexao.execute(sa.select(sa.func.count()).select_from(usuario)).scalar()
    tem_projetos = conexao.execute(sa.select(sa.func.count()).select_from(projeto)).scalar()
    if not tem_usuarios and not tem_projetos:
        return  # banco novo: a primeira organização é criada pelo app (database.init_db)

    nome = (os.getenv("DECIDIU_ORG_INICIAL") or NOME_PADRAO).strip() or NOME_PADRAO
    slug = _slug(nome)
    conexao.execute(organizacao.insert().values(
        nome=nome, slug=slug, ativa=True,
        data_criacao=datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None),
    ))
    org_id = conexao.execute(sa.select(organizacao.c.id).where(organizacao.c.slug == slug)).scalar_one()

    conexao.execute(usuario.update().values(organizacao_id=org_id))
    conexao.execute(projeto.update().values(organizacao_id=org_id))
    conexao.execute(auditoria.update().values(organizacao_id=org_id))
    primeiro_admin = conexao.execute(
        sa.select(sa.func.min(usuario.c.id)).where(usuario.c.admin == sa.true())
    ).scalar()
    if primeiro_admin is not None:
        conexao.execute(usuario.update().where(usuario.c.id == primeiro_admin).values(superadmin=True))


def downgrade() -> None:
    with op.batch_alter_table("registroauditoria") as tabela:
        tabela.drop_index("ix_registroauditoria_organizacao_id")
        tabela.drop_column("organizacao_id")
    with op.batch_alter_table("projeto") as tabela:
        tabela.drop_constraint("fk_projeto_organizacao", type_="foreignkey")
        tabela.drop_index("ix_projeto_organizacao_id")
        tabela.drop_column("organizacao_id")
    with op.batch_alter_table("usuario") as tabela:
        tabela.drop_constraint("fk_usuario_organizacao", type_="foreignkey")
        tabela.drop_index("ix_usuario_organizacao_id")
        tabela.drop_column("superadmin")
        tabela.drop_column("organizacao_id")
    op.drop_index("ix_organizacao_slug", table_name="organizacao")
    op.drop_table("organizacao")

"""Ambiente do Alembic: usa o mesmo banco e o mesmo modelo do app (nucleo/)."""
from alembic import context
from sqlalchemy import text
from sqlmodel import SQLModel

import nucleo.tabelas  # noqa: F401  (registra as tabelas no metadata)
from nucleo.db import criar_engine, url_do_banco

config = context.config
target_metadata = SQLModel.metadata

# Número fixo da trava do PostgreSQL: se o app e a API iniciarem juntos, um espera o outro
# terminar as migrações em vez de rodarem ao mesmo tempo.
TRAVA_MIGRACOES = 7_310_001


def _configurar(conexao) -> None:
    context.configure(
        connection=conexao,
        target_metadata=target_metadata,
        render_as_batch=conexao.dialect.name == "sqlite",  # SQLite não altera colunas: recria a tabela
        compare_type=True,
    )
    with context.begin_transaction():
        if conexao.dialect.name == "postgresql":
            conexao.execute(text(f"SELECT pg_advisory_xact_lock({TRAVA_MIGRACOES})"))
        context.run_migrations()


def rodar_offline() -> None:
    """'alembic upgrade head --sql': gera o SQL sem conectar."""
    context.configure(url=url_do_banco(), target_metadata=target_metadata, literal_binds=True,
                      dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()


def rodar_online() -> None:
    conexao = config.attributes.get("connection")  # passada pelo app (nucleo/migracoes.py)
    if conexao is not None:
        _configurar(conexao)
        return
    engine = criar_engine()
    try:
        with engine.connect() as conexao:
            _configurar(conexao)
    finally:
        engine.dispose()


if context.is_offline_mode():
    rodar_offline()
else:
    rodar_online()

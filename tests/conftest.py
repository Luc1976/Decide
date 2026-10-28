"""Configuração comum dos testes.

Cada teste roda num banco SQLite novo, numa pasta temporária. MEMORIA_DATA_DIR precisa ser
definida ANTES de importar config/database (o caminho do banco é lido na importação).
"""
import os
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

_PASTA = tempfile.mkdtemp(prefix="decidiu-testes-")
os.environ["MEMORIA_DATA_DIR"] = _PASTA
os.environ.setdefault("MEMORIA_ADMIN_SENHA", "senha-admin")
os.environ.setdefault("DECIDIU_JWT_SEGREDO", "segredo-de-teste-com-mais-de-32-caracteres")

import pytest  # noqa: E402
from sqlmodel import SQLModel  # noqa: E402

import database  # noqa: E402


def zerar_banco():
    SQLModel.metadata.drop_all(database.engine)
    with database.engine.begin() as conexao:
        conexao.exec_driver_sql("DROP TABLE IF EXISTS alembic_version")


@pytest.fixture(autouse=True)
def banco_limpo():
    """Banco zerado a cada teste, recriado pelas migrações (como num banco novo de verdade)."""
    zerar_banco()
    database.init_db()
    yield
    zerar_banco()


@pytest.fixture
def admin():
    from sqlmodel import Session, select

    with Session(database.engine) as s:
        u = s.exec(select(database.Usuario).where(database.Usuario.admin == True)).first()  # noqa: E712
        s.expunge(u)
        return u


@pytest.fixture
def projeto_padrao():
    return database.listar_projetos()[0]

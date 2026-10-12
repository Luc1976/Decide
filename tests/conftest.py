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


@pytest.fixture(autouse=True)
def banco_limpo():
    """Banco zerado a cada teste (mesmo arquivo, tabelas recriadas)."""
    SQLModel.metadata.drop_all(database.engine)
    database.init_db()
    yield
    SQLModel.metadata.drop_all(database.engine)


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

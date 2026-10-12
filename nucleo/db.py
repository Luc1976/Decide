"""Engine e sessões do banco.

DECIDIU_DATABASE_URL (opcional) aponta para o PostgreSQL da nuvem, por exemplo o que o Railway
fornece (postgres://usuario:senha@host:5432/banco). Sem ela, usa o SQLite em
MEMORIA_DATA_DIR, como o app sempre fez.

O nome é próprio do Decidiu DE PROPÓSITO: o Railway cria "DATABASE_URL" sozinho quando há
um PostgreSQL no projeto, e o app não deve trocar de banco sem a migração dos dados.
"""
import os
from typing import Iterator, Optional

from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlmodel import Session, create_engine

from config import DB_PATH


def url_do_banco() -> str:
    url = (os.getenv("DECIDIU_DATABASE_URL") or "").strip()
    if not url:
        return f"sqlite:///{DB_PATH}"
    # O Railway/Heroku entregam "postgres://"; o SQLAlchemy quer o nome do driver.
    if url.startswith("postgres://"):
        url = "postgresql+psycopg://" + url[len("postgres://"):]
    elif url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


def criar_engine(url: Optional[str] = None) -> Engine:
    url = url or url_do_banco()
    if url.startswith("sqlite"):
        # várias sessões (usuários) acessando o mesmo arquivo
        eng = create_engine(url, echo=False, connect_args={"check_same_thread": False, "timeout": 30})

        @event.listens_for(eng, "connect")
        def _sqlite_pragmas(conexao, _):  # pragma: no cover - detalhe do SQLite
            cursor = conexao.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")  # leitores não bloqueiam quem grava
            cursor.close()

        return eng
    # PostgreSQL: pool de conexões; pre_ping descarta conexões derrubadas pelo servidor.
    return create_engine(url, echo=False, pool_size=10, max_overflow=20, pool_pre_ping=True)


engine = criar_engine()


def eh_sqlite(eng: Engine = None) -> bool:
    return (eng or engine).dialect.name == "sqlite"


def nova_sessao(eng: Engine = None) -> Session:
    """Sessão que mantém os objetos legíveis depois do commit (para devolver à tela/API)."""
    return Session(eng or engine, expire_on_commit=False)


def sessao() -> Iterator[Session]:
    """Para usar como dependência (FastAPI) ou com 'with closing(...)'."""
    with nova_sessao() as s:
        yield s

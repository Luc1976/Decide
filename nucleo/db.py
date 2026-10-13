"""Engine e sessões do banco.

DECIDIU_DATABASE_URL (opcional) aponta para o PostgreSQL da nuvem, por exemplo o que o Railway
fornece (postgres://usuario:senha@host:5432/banco). Sem ela, usa o SQLite em
MEMORIA_DATA_DIR, como o app sempre fez.

O nome é próprio do Decidiu DE PROPÓSITO: o Railway cria "DATABASE_URL" sozinho quando há
um PostgreSQL no projeto, e o app não deve trocar de banco sem a migração dos dados.
"""
import os
import time
from typing import Callable, Iterator, Optional

from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError
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
    # connect_timeout curto: sem ele, o driver espera mais de 2 minutos por um host inalcançável.
    return create_engine(url, echo=False, pool_size=10, max_overflow=20, pool_pre_ping=True,
                         connect_args={"connect_timeout": 10})


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


# ---------------------------------------------------------------- conexão na partida

class ErroConexaoBanco(RuntimeError):
    """O banco não respondeu dentro do tempo. A mensagem já traz as causas prováveis."""


def endereco_seguro(eng: Engine = None) -> str:
    """Endereço do banco para o log, SEM a senha."""
    return (eng or engine).url.render_as_string(hide_password=True)


def diagnostico(eng: Engine, erro: Exception) -> str:
    url = (eng or engine).url
    linhas = [f"Não foi possível conectar ao banco {endereco_seguro(eng)}.",
              f"Erro: {str(erro).splitlines()[0][:300]}"]
    if url.get_backend_name() == "sqlite":
        linhas.append("Confira MEMORIA_DATA_DIR e se o volume está montado (no Railway: /dados).")
        return "\n".join(linhas)
    host = url.host or ""
    linhas.append("Causas prováveis:")
    if host.endswith(".railway.internal"):
        linhas += [
            "- O app e o PostgreSQL precisam estar no MESMO projeto e no MESMO ambiente do Railway"
            " (o endereço .railway.internal só funciona lá dentro).",
            "- O serviço do PostgreSQL está parado, com erro ou dormindo (desligue o App Sleeping nele).",
            "- Use a referência em vez de colar o endereço: DECIDIU_DATABASE_URL=${{Postgres.DATABASE_URL}}"
            " (troque 'Postgres' pelo nome do serviço).",
            "- App em outro projeto: use ${{Postgres.DATABASE_PUBLIC_URL}}.",
        ]
    else:
        linhas += ["- Endereço, porta, usuário ou senha em DECIDIU_DATABASE_URL.",
                   "- O PostgreSQL está parado ou não aceita conexões deste servidor."]
    linhas.append("Para voltar ao SQLite (dados em /dados), apague a variável DECIDIU_DATABASE_URL.")
    return "\n".join(linhas)


def aguardar_banco(eng: Engine = None, tempo_total: float = 90, intervalo: float = 5,
                   dormir: Callable[[float], None] = time.sleep, relogio: Callable[[], float] = time.monotonic) -> None:
    """Tenta conectar até 'tempo_total' segundos. Cobre o banco que ainda está subindo e a
    rede interna do Railway que leva alguns segundos para ficar pronta na partida.
    Se não conseguir, levanta ErroConexaoBanco com o diagnóstico."""
    eng = eng or engine
    limite = relogio() + tempo_total
    tentativa = 0
    while True:
        tentativa += 1
        try:
            with eng.connect() as conexao:
                conexao.exec_driver_sql("SELECT 1")
            if tentativa > 1:
                print(f"[memoria] Banco respondeu na tentativa {tentativa}.", flush=True)
            return
        except OperationalError as erro:
            if relogio() + intervalo > limite:
                raise ErroConexaoBanco(diagnostico(eng, erro)) from erro
            print(f"[memoria] Banco ainda não respondeu (tentativa {tentativa}); "
                  f"nova tentativa em {intervalo:.0f} s...", flush=True)
            dormir(intervalo)

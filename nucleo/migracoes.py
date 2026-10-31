"""Aplica as migrações do Alembic a partir do próprio app (sem precisar do terminal)."""
from pathlib import Path
from typing import Optional

from sqlalchemy.engine import Engine

RAIZ = Path(__file__).resolve().parent.parent


def _config(conexao=None):
    from alembic.config import Config

    cfg = Config(str(RAIZ / "alembic.ini"))
    cfg.set_main_option("script_location", str(RAIZ / "migracoes"))
    if conexao is not None:
        cfg.attributes["connection"] = conexao
    return cfg


def atualizar_banco(engine: Optional[Engine] = None, revisao: str = "head") -> None:
    """'alembic upgrade head' no banco do app. Seguro de rodar a cada partida: só aplica
    o que falta. No PostgreSQL, partidas simultâneas esperam umas pelas outras."""
    from alembic import command

    from nucleo.db import engine as engine_padrao

    eng = engine or engine_padrao
    antes = revisao_atual(eng)
    with eng.begin() as conexao:
        command.upgrade(_config(conexao), revisao)
    depois = revisao_atual(eng)
    if depois != antes:
        print(f"[memoria] Banco atualizado: versão {antes or 'sem versão'} -> {depois}", flush=True)


def voltar_banco(revisao: str, engine: Optional[Engine] = None) -> None:
    from alembic import command

    from nucleo.db import engine as engine_padrao

    with (engine or engine_padrao).begin() as conexao:
        command.downgrade(_config(conexao), revisao)


def revisao_mais_nova() -> str:
    """Última migração existente em migracoes/versions (o 'head' do Alembic)."""
    from alembic.script import ScriptDirectory

    return ScriptDirectory.from_config(_config()).get_current_head()


def revisao_atual(engine: Optional[Engine] = None) -> Optional[str]:
    from alembic.migration import MigrationContext

    from nucleo.db import engine as engine_padrao

    with (engine or engine_padrao).connect() as conexao:
        return MigrationContext.configure(conexao).get_current_revision()

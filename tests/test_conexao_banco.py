"""Espera pelo banco na partida e mensagem de diagnóstico."""
from types import SimpleNamespace

import pytest
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError

from nucleo.db import ErroConexaoBanco, aguardar_banco, criar_engine, diagnostico


class _Relogio:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t

    def dormir(self, s):
        self.t += s


def test_banco_que_responde_passa_direto(tmp_path):
    aguardar_banco(criar_engine(f"sqlite:///{tmp_path / 'ok.db'}"), dormir=lambda s: pytest.fail("não devia esperar"))


def test_desiste_depois_do_tempo_com_diagnostico(tmp_path, capsys):
    eng = criar_engine(f"sqlite:///{tmp_path / 'nao-existe' / 'x.db'}")  # pasta inexistente
    relogio = _Relogio()
    with pytest.raises(ErroConexaoBanco, match="MEMORIA_DATA_DIR"):
        aguardar_banco(eng, tempo_total=20, intervalo=5, dormir=relogio.dormir, relogio=relogio)
    assert capsys.readouterr().out.count("ainda não respondeu") == 4


def test_recupera_quando_o_banco_sobe(tmp_path):
    pasta = tmp_path / "sobe-depois"
    eng = criar_engine(f"sqlite:///{pasta / 'x.db'}")
    relogio = _Relogio()

    def dormir(s):
        relogio.dormir(s)
        pasta.mkdir(exist_ok=True)  # "o banco subiu" durante a espera

    aguardar_banco(eng, tempo_total=60, intervalo=5, dormir=dormir, relogio=relogio)
    assert relogio.t == 5


def test_diagnostico_railway_sem_senha():
    eng = SimpleNamespace(url=make_url("postgresql+psycopg://decidiu:SEGREDO123@postgres.railway.internal:5432/railway"))
    texto = diagnostico(eng, OperationalError("connect", {}, Exception("connection timeout expired")))
    assert "SEGREDO123" not in texto and "***" in texto
    assert "MESMO projeto" in texto and "${{Postgres.DATABASE_URL}}" in texto
    assert "apague a variável DECIDIU_DATABASE_URL" in texto

"""'Salvar meu usuário neste aparelho' na tela de login (views/lembrar_usuario.py).

No Flet 1.0 a página não tem mais page.shared_preferences: o armazenamento é o serviço
ft.SharedPreferences, que precisa ser criado e mantido vivo enquanto a sessão existir."""
import asyncio

import pytest

ft = pytest.importorskip("flet")

from views import lembrar_usuario  # noqa: E402


class PreferenciasFalsas:
    criadas = 0

    def __init__(self):
        PreferenciasFalsas.criadas += 1
        self.dados = {}

    async def set(self, chave, valor):
        self.dados[chave] = valor
        return True

    async def get(self, chave):
        return self.dados.get(chave)


class Pagina:  # como a ft.Page do Flet 1.0: sem shared_preferences nem client_storage
    pass


@pytest.fixture
def preferencias(monkeypatch):
    PreferenciasFalsas.criadas = 0
    monkeypatch.setattr(lembrar_usuario.ft, "SharedPreferences", PreferenciasFalsas)


def test_grava_e_le_o_usuario_com_o_servico_do_flet(preferencias):
    pagina = Pagina()
    asyncio.run(lembrar_usuario.gravar(pagina, "demo.helena"))
    assert asyncio.run(lembrar_usuario.ler(pagina)) == "demo.helena"
    assert PreferenciasFalsas.criadas == 1  # um serviço por sessão, reaproveitado


def test_desmarcar_apaga_o_usuario_guardado(preferencias):
    pagina = Pagina()
    asyncio.run(lembrar_usuario.gravar(pagina, "demo.helena"))
    asyncio.run(lembrar_usuario.gravar(pagina, ""))
    assert asyncio.run(lembrar_usuario.ler(pagina)) == ""


def test_sem_armazenamento_o_login_segue_normal(monkeypatch):
    def quebra():
        raise RuntimeError("sem página")

    monkeypatch.setattr(lembrar_usuario.ft, "SharedPreferences", quebra)
    pagina = Pagina()
    asyncio.run(lembrar_usuario.gravar(pagina, "x"))
    assert asyncio.run(lembrar_usuario.ler(pagina)) == ""

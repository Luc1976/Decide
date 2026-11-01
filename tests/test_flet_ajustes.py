"""Resposta atrasada de um controle que já saiu da tela não pode derrubar a conexão.

No iPhone o Safari suspende a aba e reconecta; o navegador reenvia a resposta de um método
(abrir/fechar o menu, por exemplo) de um controle que o servidor já descartou. No Flet 1.0.x
isso levantava RuntimeError no laço de recepção, a conexão caía, o navegador reconectava e
reenviava a mesma resposta: a tela travava num ciclo sem fim."""
import asyncio
from types import SimpleNamespace

import pytest

pytest.importorskip("flet")

from flet.messaging.session import Session  # noqa: E402
from flet.pubsub.pubsub_hub import PubSubHub  # noqa: E402

import flet_ajustes  # noqa: E402


def _sessao():
    flet_ajustes.aplicar()
    return Session(SimpleNamespace(pubsubhub=PubSubHub()))


def test_resposta_de_controle_desconhecido_e_ignorada():
    sessao = _sessao()
    sessao.handle_invoke_method_results(1191, "chamada-antiga", None, None)  # não levanta


def test_quem_espera_a_resposta_ainda_recebe():
    sessao = _sessao()

    async def cenario():
        evento = asyncio.Event()
        sessao._Session__method_calls["abc"] = evento
        sessao.handle_invoke_method_results(1474, "abc", "ok", None)
        assert evento.is_set()
        return sessao._Session__method_call_results[evento]

    assert asyncio.run(cenario()) == ("ok", None)


def test_controle_conhecido_segue_o_caminho_normal():
    sessao = _sessao()
    pagina = sessao.page
    sessao.handle_invoke_method_results(pagina._i, "sem-espera", None, None)


def test_aplicar_duas_vezes_nao_empilha():
    flet_ajustes.aplicar()
    flet_ajustes.aplicar()
    assert getattr(Session.handle_invoke_method_results, "_decidiu", False)

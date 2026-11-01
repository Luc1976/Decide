"""Correções pontuais no Flet, aplicadas na partida do servidor (main.py).

Resposta atrasada de método (Flet 1.0.3 a 1.0.5)
-------------------------------------------------
Quando o servidor chama um método no navegador (abrir/fechar o menu lateral, ler o usuário
salvo, escolher arquivos), o navegador devolve a resposta com o id do controle. Se esse
controle já saiu da tela, ou se a conexão caiu e voltou (o Safari do iPhone faz isso ao
suspender a aba), a resposta chega para um id que o servidor não conhece. O Flet levanta
RuntimeError dentro do laço que recebe as mensagens; a conexão morre, o navegador reconecta,
reenvia a mesma resposta e a tela fica presa nesse ciclo ("Control with ID ... is not
registered" repetido no log).

Aqui a resposta órfã é entregue a quem ainda a espera, se houver alguém, e descartada caso
contrário. A conexão segue viva. Remover quando o Flet corrigir em
flet/messaging/session.py (Session.handle_invoke_method_results)."""
import logging

from flet.messaging.session import Session

logger = logging.getLogger("decidiu.flet")


def aplicar() -> None:
    original = Session.handle_invoke_method_results
    if getattr(original, "_decidiu", False):
        return

    def handle_invoke_method_results(self, control_id, call_id, result, error):
        try:
            return original(self, control_id, call_id, result, error)
        except RuntimeError:
            chamadas = getattr(self, "_Session__method_calls", {})
            evento = chamadas.pop(call_id, None)
            if evento is not None:
                self._Session__method_call_results[evento] = (result, error)
                evento.set()
            logger.info("Resposta de método para o controle %s, que já saiu da tela: ignorada", control_id)

    handle_invoke_method_results._decidiu = True
    Session.handle_invoke_method_results = handle_invoke_method_results

"""Erros de domínio.

Herdam de ValueError/PermissionError para o app Flet continuar tratando como sempre
(as telas fazem 'except ValueError' e 'except PermissionError'). A API traduz cada um
para o código HTTP certo (ver api/erros.py)."""


class ErroDominio(ValueError):
    """Regra de negócio violada; a mensagem pode ir direto ao usuário. (HTTP 422)"""


class NaoEncontrado(ErroDominio):
    """O registro não existe OU o usuário não pode vê-lo. (HTTP 404)

    Responder 404 em vez de 403 para objetos de outros projetos evita revelar que eles
    existem (um id adivinhado não confirma nada)."""


class Conflito(ErroDominio):
    """O registro está num estado que não permite a ação (ex.: ata já fechada). (HTTP 409)"""


class SemPermissao(PermissionError):
    """O usuário vê o projeto mas não tem o papel exigido. (HTTP 403)"""

    def __init__(self, mensagem: str = "Você não tem permissão para esta ação neste projeto."):
        super().__init__(mensagem)

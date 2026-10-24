import datetime

import pytest

from nucleo import planos
from nucleo.tabelas import Organizacao


def _org(**campos) -> Organizacao:
    base = dict(nome="Escritório", slug="escritorio")
    base.update(campos)
    return Organizacao(**base)


def test_precos_combinados():
    assert planos.valor_cobranca("solo", "mensal") == 29.00
    assert planos.valor_cobranca("solo", "anual") == 290.00
    assert planos.valor_cobranca("equipe", "mensal") == 79.00
    assert planos.valor_cobranca("equipe", "anual") == 790.00
    assert planos.valor_cobranca("fundador", "mensal") == 49.00


def test_fundador_nao_tem_anual_e_plano_invalido_falha():
    with pytest.raises(ValueError):
        planos.valor_cobranca("fundador", "anual")
    with pytest.raises(ValueError):
        planos.valor_cobranca("inexistente", "mensal")


def test_operacao_interna_sempre_liberada():
    assert planos.acesso_liberado(_org(plano="interno", assinatura_status="ativa"))


def test_teste_liberado_so_dentro_do_prazo():
    agora = datetime.datetime(2026, 10, 24, 12, 0)
    dentro = _org(plano="teste", assinatura_status="teste", teste_fim=agora + datetime.timedelta(days=1))
    vencido = _org(plano="teste", assinatura_status="teste", teste_fim=agora - datetime.timedelta(seconds=1))
    assert planos.acesso_liberado(dentro, agora)
    assert not planos.acesso_liberado(vencido, agora)


def test_status_pendente_atrasada_cancelada_bloqueiam():
    for status in ("pendente", "atrasada", "cancelada"):
        assert not planos.acesso_liberado(_org(plano="equipe", assinatura_status=status))


def test_teste_com_fuso_aware_nao_quebra_comparacao():
    agora = datetime.datetime(2026, 10, 24, 12, 0)
    fim = datetime.datetime(2026, 10, 25, 9, 0, tzinfo=datetime.timezone.utc)
    assert planos.acesso_liberado(_org(plano="teste", assinatura_status="teste", teste_fim=fim), agora)


def test_limite_usuarios_solo_um_admin_dois_colaboradores():
    solo = _org(plano="solo", assinatura_status="ativa")
    assert planos.erro_limite_usuario(solo, administradores=1, colaboradores=1, novo_admin=False) is None
    assert planos.erro_limite_usuario(solo, administradores=1, colaboradores=2, novo_admin=False) is not None
    assert planos.erro_limite_usuario(solo, administradores=1, colaboradores=0, novo_admin=True) is not None


def test_limite_usuarios_equipe_16_pessoas():
    equipe = _org(plano="equipe", assinatura_status="ativa")
    assert planos.erro_limite_usuario(equipe, administradores=1, colaboradores=14, novo_admin=False) is None
    assert planos.erro_limite_usuario(equipe, administradores=1, colaboradores=15, novo_admin=False) is not None


def test_limite_projetos_solo_5_equipe_30():
    assert planos.erro_limite_projeto(_org(plano="solo", assinatura_status="ativa"), 4) is None
    assert planos.erro_limite_projeto(_org(plano="solo", assinatura_status="ativa"), 5) is not None
    assert planos.erro_limite_projeto(_org(plano="equipe", assinatura_status="ativa"), 29) is None
    assert planos.erro_limite_projeto(_org(plano="equipe", assinatura_status="ativa"), 30) is not None


def test_teste_usa_limites_do_solo_e_interno_nao_tem_limite():
    teste = _org(plano="teste", assinatura_status="teste")
    assert planos.limites_da_org(teste) == planos.LIMITES["solo"]
    assert planos.limites_da_org(_org(plano="interno", assinatura_status="ativa")) is None

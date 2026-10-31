"""Migração 0011: padrão construtivo (tabela antiga) vira campos da ficha, com histórico."""
import datetime

from sqlalchemy import text

from nucleo.db import criar_engine
from nucleo.migracoes import atualizar_banco, revisao_atual, revisao_mais_nova, voltar_banco


def _banco_em_0010(tmp_path):
    eng = criar_engine(f"sqlite:///{tmp_path / 'm.db'}")
    atualizar_banco(eng, "0010")
    agora = datetime.datetime(2026, 9, 1, 10, 0)
    with eng.begin() as c:
        c.execute(text("INSERT INTO projeto (id, nome, cliente, data_criacao, arquivado) VALUES "
                       "(1,'Aurora','X',:a,0),(2,'Galpão','Y',:a,0),(3,'DC','Z',:a,0),(4,'Vazio','W',:a,0)"),
                  {"a": agora})
        c.execute(text("INSERT INTO caracteristica (projeto_id, grupo, nome, valor, unidade, atualizado_por, "
                       "data_atualizacao) VALUES (1,'Programa','Uso / tipologia','Residencial vertical',NULL,'Ana',:a)"),
                  {"a": agora})
        c.execute(text("INSERT INTO padraoconstrutivo (projeto_id, tipologia, multi_sistema_principal, multi_tipo_laje) "
                       "VALUES (1,'Multifamiliar','Concreto armado convencional','Nervurada')"))
        c.execute(text("INSERT INTO padraoconstrutivo (projeto_id, tipologia, ind_estrutura, ind_carga_piso, "
                       "ind_pavimento_externo) VALUES (2,'Industrial','Metálica',5.5,'Rígido')"))
        c.execute(text("INSERT INTO padraoconstrutivo (projeto_id, tipologia, dc_tier_redundancia) "
                       "VALUES (3,'Data Center','Tier III')"))
        c.execute(text("INSERT INTO padraoconstrutivo (projeto_id, tipologia) VALUES (4,'')"))
    return eng


def _ficha(eng, pid):
    with eng.connect() as c:
        return {(g, n): v for g, n, v in c.execute(
            text("SELECT grupo, nome, valor FROM caracteristica WHERE projeto_id=:p"), {"p": pid})}


def test_migra_padrao_para_campos_com_historico(tmp_path):
    eng = _banco_em_0010(tmp_path)
    atualizar_banco(eng)
    assert revisao_atual(eng) == revisao_mais_nova()
    aurora = _ficha(eng, 1)
    assert aurora[("Programa", "Uso / tipologia")] == "Residencial"
    assert aurora[("Sistemas construtivos", "Sistema estrutural")] == "Concreto armado convencional"
    assert aurora[("Sistemas construtivos", "Tipo de laje")] == "Nervurada"
    galpao = _ficha(eng, 2)
    assert galpao[("Programa", "Uso / tipologia")] == "Industrial"
    assert galpao[("Sistemas construtivos", "Carga de piso")] == "5,5"
    assert galpao[("Sistemas construtivos", "Pavimento externo")] == "Rígido"  # fora da lista nova = "Outro"
    assert _ficha(eng, 3)[("Sistemas construtivos", "Classificação Tier")] == "Tier III"
    assert _ficha(eng, 4) == {}
    with eng.connect() as c:
        hist = c.execute(text("SELECT nome, valor_anterior, valor_novo, autor FROM caracteristicahistorico "
                              "WHERE projeto_id=1")).all()
        assert ("Uso / tipologia", "Residencial vertical", "Residencial", "Migração 0011") in hist
        assert len(hist) == 3
        assert c.execute(text("SELECT count(*) FROM padraoconstrutivo")).scalar() == 4  # tabela mantida


def test_downgrade_restaura_o_que_havia(tmp_path):
    eng = _banco_em_0010(tmp_path)
    atualizar_banco(eng)
    voltar_banco("0010", eng)
    assert _ficha(eng, 1) == {("Programa", "Uso / tipologia"): "Residencial vertical"}
    assert _ficha(eng, 2) == {}
    with eng.connect() as c:
        assert c.execute(text("SELECT count(*) FROM caracteristicahistorico")).scalar() == 0
    atualizar_banco(eng)  # e reaplica
    assert _ficha(eng, 2)[("Sistemas construtivos", "Sistema estrutural")] == "Metálica"

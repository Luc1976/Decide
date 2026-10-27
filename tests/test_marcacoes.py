"""Marcação de decisão na ata: [D] (Disciplina) (Impacto) Título: descrição."""
from nucleo.marcacoes import erros_das_decisoes, interpretar_decisao


def test_disciplina_e_impacto_entre_parenteses_em_qualquer_ordem():
    info = interpretar_decisao("(Alto) (estrutura) Adotar laje: vãos de 12 m")
    assert (info["categoria"], info["impacto"], info["texto"], info["erros"]) == (
        "Estrutura", "Alto", "Adotar laje: vãos de 12 m", [])


def test_aceita_acento_e_caixa_diferentes():
    info = interpretar_decisao("(elétrica) (medio) Trocar quadro")
    assert (info["categoria"], info["impacto"]) == ("Elétrica", "Médio")


def test_recusa_valor_fora_da_lista_e_tag_faltando():
    info = interpretar_decisao("(Fase 2) Algo")
    assert info["categoria"] is None and info["impacto"] is None
    assert any("não é uma disciplina" in e for e in info["erros"])
    assert "falta a disciplina entre parênteses" in info["erros"]
    assert "falta o impacto entre parênteses" in info["erros"]


def test_erros_das_decisoes_ignora_pendencias_e_linhas_validas():
    texto = "[D] (Urbanismo) (Baixo) Ok\n[D] Sem tag\n[P] (Qualquer) não conta"
    erros = erros_das_decisoes(texto)
    assert len(erros) == 1 and "Sem tag" in erros[0]

"""Catálogo de tipologias: campos por tipologia, cascata e limpeza na troca."""
import catalogo_tipologias as cat
from models import CAMPO_TIPOLOGIA, GRUPO_OUTRAS, GRUPO_PROGRAMA

T = (GRUPO_PROGRAMA, CAMPO_TIPOLOGIA)
SIS = "Sistemas construtivos"
ALT = "Alturas e dimensões"


def _nomes(campos):
    return [c.nome for c in campos]


def test_sete_tipologias_na_ordem_combinada():
    assert cat.TIPOLOGIAS == ("Residencial", "Comercial", "Industrial", "Condomínio de lotes",
                              "Corporativo", "Shopping Center", "Data Center")
    assert all(cat.campos_da_tipologia(t) for t in cat.TIPOLOGIAS)
    assert cat.campos_da_tipologia("Outro") == () and cat.campos_da_tipologia("") == ()


def test_catalogo_consistente():
    vistos = {}
    for tipologia in cat.TIPOLOGIAS:
        campos = cat.campos_da_tipologia(tipologia)
        chaves = [(c.grupo, c.nome) for c in campos]
        assert len(chaves) == len(set(chaves)), tipologia
        nomes = {c.nome for c in campos}
        for c in campos:
            assert cat.OUTRO not in c.opcoes, c.nome          # "Outro" é acrescentado pela tela
            assert c.grupo not in (GRUPO_OUTRAS,), c.nome
            if c.depende_de:
                assert c.depende_de in nomes and c.valores_que_mostram, c.nome
                pai = next(p for p in campos if p.nome == c.depende_de)
                assert campos.index(pai) < campos.index(c)     # o pai vem antes na tela
            # mesmo campo em tipologias diferentes: mesma unidade
            assert vistos.setdefault((c.grupo, c.nome), c.unidade) == c.unidade, c.nome


def test_residencial_tem_sistemas_e_alturas():
    nomes = _nomes(cat.campos_da_tipologia("Residencial"))
    for nome in ("Sistema estrutural", "Tipo de laje", "Fundações", "Fachada",
                 "Piso a piso – pavimento tipo", "Pé-direito livre mínimo – pavimento tipo",
                 "Pé-direito – cozinhas", "Espessura do contrapiso"):
        assert nome in nomes, nome
    laje = next(c for c in cat.campos_da_tipologia("Residencial") if c.nome == "Tipo de laje")
    assert "Nervurada" in laje.opcoes and laje.depende_de == "Sistema estrutural"
    contrapiso = next(c for c in cat.campos_da_tipologia("Residencial") if c.nome == "Espessura do contrapiso")
    assert contrapiso.unidade == "cm" and contrapiso.opcoes == () and contrapiso.grupo == ALT


def test_parametros_da_revisao_por_tipologia():
    def tem(tipologia, nome):
        return nome in _nomes(cat.campos_da_tipologia(tipologia))

    for t in ("Residencial", "Comercial", "Corporativo"):
        assert tem(t, "Piso a piso – casa de máquinas e barrilete") and tem(t, "Pé-direito – sanitários")
    assert tem("Industrial", "Altura dos portões") and tem("Industrial", "Altura da doca de carga e descarga")
    for nome in ("ABL – área bruta locável", "Nº de lojas âncoras", "Nº de lojas satélites",
                 "Pé-direito – circulações comuns", "Pé-direito – lojas", "Espessura do contrapiso"):
        assert tem("Shopping Center", nome), nome
    assert tem("Data Center", "Potência do data center") and tem("Data Center", "Pé-direito mínimo do data hall")
    assert not tem("Industrial", "Pé-direito – cozinhas")
    abl = next(c for c in cat.campos_da_tipologia("Shopping Center") if c.nome.startswith("ABL"))
    assert abl.grupo == GRUPO_PROGRAMA and abl.unidade == "m²"
    assert not [c for c in cat.campos_da_tipologia("Condomínio de lotes") if c.grupo == ALT]


def test_cascata_mostra_tipo_de_laje_so_com_concreto_armado():
    concreto = {T: "Residencial", (SIS, "Sistema estrutural"): "Concreto armado convencional"}
    alvenaria = {T: "Residencial", (SIS, "Sistema estrutural"): "Alvenaria estrutural"}
    assert "Tipo de laje" in _nomes(cat.campos_visiveis(concreto))
    assert "Tipo de laje" not in _nomes(cat.campos_visiveis(alvenaria))
    assert "Tipo de laje" not in _nomes(cat.campos_visiveis({T: "Residencial"}))


def test_limpa_campos_da_tipologia_anterior_e_mantem_os_comuns():
    atuais = {
        T: "Residencial",
        (SIS, "Sistema estrutural"): "Concreto armado convencional",
        (SIS, "Tipo de laje"): "Nervurada",
        (SIS, "Aquecimento de água"): "Gás individual",
        (ALT, "Pé-direito – cozinhas"): "2,60",
    }
    limpar = cat.campos_a_limpar(atuais, {T: "Industrial"})
    chaves = {(g, n) for g, n, _, v in limpar}
    assert all(v == "" for *_, v in limpar)
    assert (SIS, "Aquecimento de água") in chaves and (ALT, "Pé-direito – cozinhas") in chaves
    assert (SIS, "Tipo de laje") in chaves            # Industrial não tem concreto armado convencional
    assert (SIS, "Sistema estrutural") not in chaves  # existe nas duas: o valor fica (como "Outro")


def test_limpa_dependente_quando_o_pai_muda():
    atuais = {T: "Residencial", (SIS, "Sistema estrutural"): "Concreto armado convencional",
              (SIS, "Tipo de laje"): "Maciça"}
    limpar = cat.campos_a_limpar(atuais, {(SIS, "Sistema estrutural"): "Alvenaria estrutural"})
    assert [(g, n) for g, n, _, _ in limpar] == [(SIS, "Tipo de laje")]
    assert cat.campos_a_limpar(atuais, {(SIS, "Tipo de laje"): "Nervurada"}) == []


def test_tipologia_fora_da_lista_limpa_todos_os_campos_do_catalogo():
    atuais = {T: "Comercial", (SIS, "Climatização"): "VRF"}
    assert [(g, n) for g, n, _, _ in cat.campos_a_limpar(atuais, {T: "Hospital"})] == [(SIS, "Climatização")]


def test_ordem_dos_grupos_poe_os_cards_do_catalogo_depois_do_programa():
    ordem = cat.ordem_dos_grupos()
    i = ordem.index(GRUPO_PROGRAMA)
    assert ordem[i + 1:i + 3] == [SIS, ALT] and ordem[-1] == GRUPO_OUTRAS


def test_valor_da_tela_com_outro():
    campo = next(c for c in cat.campos_da_tipologia("Residencial") if c.nome == "Fachada")
    assert cat.escolha_e_texto(campo, "ACM") == ("ACM", "")
    assert cat.escolha_e_texto(campo, "Tijolo à vista") == (cat.OUTRO, "Tijolo à vista")
    assert cat.escolha_e_texto(campo, "") == (None, "")
    assert cat.valor_gravado(campo, cat.OUTRO, "  Tijolo à vista ") == "Tijolo à vista"
    assert cat.valor_gravado(campo, cat.OUTRO, "") == ""
    assert cat.valor_gravado(campo, "ACM", "ignorado") == "ACM"

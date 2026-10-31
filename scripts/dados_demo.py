"""Conteúdo fictício do projeto de demonstração do Decidiu.

Tudo aqui é inventado: escritório, incorporadora, complementares, pessoas, endereço e zona.
O motor (scripts/seed_demo.py) lê este arquivo e grava pelos serviços do próprio app,
na ordem da lista ETAPAS, reescrevendo depois os carimbos de data para a linha do tempo.

Referências cruzadas: "{D:chave}" vira o código da decisão (ex.: D-009) na hora da carga.
Cada decisão direta tem 'chave'; nas atas, a lista 'chaves' nomeia as linhas [D] na ordem.
Pendências são localizadas por um trecho do título ('pendencia').

Disciplinas aceitas pelo app (models.CATEGORIAS): Arquitetura, Arquitetura de Interiores,
Estrutura, Fundações, instalações, Elétrica, Hidrossanitário, HVAC, PPCI, Urbanismo,
Orçamento, Geral. Fachada entra como Arquitetura; legal/aprovação como Urbanismo; custos
como Orçamento.
"""
from datetime import date, datetime

from catalogo_tipologias import GRUPO_ALTURAS, GRUPO_SISTEMAS
from models import GRUPO_OUTRAS

# ------------------------------------------------------------------ identificação

ORG_SLUG = "demo-decidiu"            # identifica a conta de demonstração (não mude depois de carregar)
ORG_NOME = "Traço Austral Arquitetura"

PROJETO_NOME = "Residencial Alto das Quaresmeiras"
PROJETO_CLIENTE = "Cambará Desenvolvimento Imobiliário"
PROJETO_DESCRICAO = (
    "Edifício residencial multifamiliar em torre única: térreo de lazer, 12 pavimentos tipo "
    "e 2 subsolos de garagem, com unidades de 2 e 3 dormitórios. Projeto completo, do estudo "
    "preliminar ao executivo, com coordenação dos complementares."
)

# Complementares e consultores (aparecem nos textos e nas atas)
ESTRUTURA = "Calço Engenharia Estrutural"
INSTALACOES = "Veio Projetos de Instalações"
GEOTECNIA = "Tálus Geotecnia"
FACHADAS = "Envoltória Consultoria de Fachadas"
LEGALIZACAO = "Rito Legalização Urbana"

# ------------------------------------------------------------------ usuários
# admin=True: administrador da organização (vê todos os projetos; não entra na lista de membros).
# papel: acesso ao projeto de demonstração (Responsável, Editor ou Leitor).
# pode_criar_projetos=False + papel Leitor = cliente que só acompanha.

USUARIOS = [
    {"username": "demo.helena", "nome": "Helena Prado", "cargo": "Sócia-diretora · Traço Austral",
     "admin": True, "pode_criar_projetos": True, "papel": None},
    {"username": "demo.rafael", "nome": "Rafael Antunes", "cargo": "Arquiteto coordenador · Traço Austral",
     "admin": False, "pode_criar_projetos": True, "papel": "Responsável"},
    {"username": "demo.bianca", "nome": "Bianca Moreira", "cargo": "Arquiteta · Traço Austral",
     "admin": False, "pode_criar_projetos": True, "papel": "Editor"},
    {"username": "demo.tiago", "nome": "Tiago Vasconcelos", "cargo": f"Engenheiro estrutural · {ESTRUTURA}",
     "admin": False, "pode_criar_projetos": True, "papel": "Editor"},
    {"username": "demo.camila", "nome": "Camila Rezende", "cargo": f"Engenheira de instalações · {INSTALACOES}",
     "admin": False, "pode_criar_projetos": True, "papel": "Editor"},
    {"username": "demo.marcos", "nome": "Marcos Albuquerque", "cargo": f"Diretor de produto · {PROJETO_CLIENTE}",
     "admin": False, "pode_criar_projetos": False, "papel": "Leitor"},
]

# Quem cria o projeto (vira Responsável automaticamente)
CRIADOR = "demo.rafael"

# Participantes que não têm usuário no app (só aparecem nas atas)
JULIANA = f"Juliana Teles ({PROJETO_CLIENTE}, comercial)"
FERNANDA = f"Fernanda Lopes ({PROJETO_CLIENTE}, orçamentos)"
PATRICIA = f"Patrícia Lemos ({FACHADAS})"
SERGIO = f"Sérgio Nunes ({LEGALIZACAO})"


def _p(*nomes: str) -> str:
    return "; ".join(nomes)


HELENA = "Helena Prado (Traço Austral)"
RAFAEL = "Rafael Antunes (Traço Austral)"
BIANCA = "Bianca Moreira (Traço Austral)"
TIAGO = f"Tiago Vasconcelos ({ESTRUTURA})"
CAMILA = f"Camila Rezende ({INSTALACOES})"
MARCOS = f"Marcos Albuquerque ({PROJETO_CLIENTE})"

O = GRUPO_OUTRAS  # "Outras características" (campos personalizados da ficha)
SIS = GRUPO_SISTEMAS  # campos do catálogo da tipologia (catalogo_tipologias.py)
ALT = GRUPO_ALTURAS

# ------------------------------------------------------------------ ficha inicial
# (grupo, nome, unidade, valor). Os campos em "Outras características" são personalizados
# e vão sendo alterados pelas decisões ao longo do projeto.

FICHA_INICIAL = [
    ("Terreno e localização", "Endereço / localização", "",
     "Av. das Quaresmeiras, 1.250 – Setor Jardim Sul (endereço fictício)"),
    ("Terreno e localização", "Área do terreno", "m²", "1.800,00"),
    ("Terreno e localização", "Testada", "m", "40,00"),
    ("Terreno e localização", "Topografia e condicionantes", "",
     "Declive de 3,5 m da frente para os fundos. Vizinho a leste: edifício de 6 pavimentos "
     "junto à divisa; a oeste, casas térreas. Rede de drenagem pública na avenida."),
    ("Parâmetros urbanísticos", "Zoneamento", "", "ZUM-2 – Zona Urbana Mista 2"),
    ("Parâmetros urbanísticos", "Taxa de ocupação (TO)", "%", "60"),
    ("Parâmetros urbanísticos", "Coeficiente de aproveitamento (CA)", "", "4,0"),
    ("Parâmetros urbanísticos", "Taxa de permeabilidade", "%", "15"),
    ("Parâmetros urbanísticos", "Gabarito / altura máxima", "m", "48,00"),
    ("Parâmetros urbanísticos", "Recuos (frontal / laterais / fundos)", "m",
     "5,00 / 2,50 (h/6 acima do 4º pav.) / 3,00"),
    ("Programa", "Uso / tipologia", "", "Residencial"),
    ("Programa", "Nº de unidades", "", "48"),
    ("Programa", "Nº de pavimentos", "", "Térreo + 12 tipo + 2 subsolos"),
    ("Programa", "Área construída total prevista", "m²", "8.400,00"),
    ("Programa", "Vagas de garagem", "", "A definir no estudo preliminar"),
    ("Padrão, prazo e custo", "Padrão de acabamento", "", "A definir (médio ou médio-alto)"),
    ("Padrão, prazo e custo", "Orçamento estimado", "R$", "38.500.000,00"),
    ("Padrão, prazo e custo", "Prazo previsto", "meses", "14"),
    ("Premissas do cliente", "Premissas e requisitos", "",
     "Unidades de 2 e 3 dormitórios para famílias jovens; lazer completo no térreo; "
     "VGV estimado de R$ 62 milhões; lançamento comercial no 1º semestre de 2026 e início "
     "de obra no 2º semestre de 2026."),
    (SIS, "Tipo de empreendimento", "", "Edifício vertical"),
    (SIS, "Vedações", "", "Bloco cerâmico"),
    (ALT, "Piso a piso – pavimento tipo", "m", "2,80"),
    (ALT, "Piso a piso – térreo", "m", "4,50"),
    (ALT, "Piso a piso – subsolo / estacionamento", "m", "3,00"),
    (ALT, "Piso a piso – cobertura", "m", "3,20"),
    (ALT, "Piso a piso – casa de máquinas e barrilete", "m", "3,50"),
    (ALT, "Pé-direito livre mínimo – pavimento tipo", "m", "2,60"),
    (ALT, "Pé-direito – sanitários", "m", "2,30"),
    (ALT, "Pé-direito – cozinhas", "m", "2,50"),
    (ALT, "Espessura do contrapiso", "cm", "4"),
    (O, "Elevadores", "", "A definir"),
    (O, "Altura da edificação", "m", "40,10"),
    (O, "Situação do projeto legal", "", "Não protocolado"),
]

# Sistemas construtivos: campos da ficha definidos pela tipologia (catalogo_tipologias.py).
# Ficam vazios no início e são preenchidos pelas decisões (D-008, D-009...) e pelas atas.

# ------------------------------------------------------------------ atas (texto)

ATA_01 = """Reunião de partida do projeto, na sede da Cambará.

1. Apresentação das equipes e do cronograma-macro: estudo preliminar até outubro, anteprojeto até janeiro, projeto legal protocolado em fevereiro e executivo concluído até outubro de 2026.
2. A Cambará apresentou a pesquisa de mercado: demanda forte por 3 dormitórios com suíte na região e por 2 dormitórios compactos para investidores.
3. Discutido o padrão de acabamento. A Cambará quer se diferenciar dos lançamentos vizinhos (padrão médio) sem chegar ao alto padrão.

[D] (Arquitetura) (Alto) Programa de 48 unidades: 24 de 2 dormitórios (68 m²) e 24 de 3 dormitórios com suíte (92 m²), quatro por andar.
[D] (Geral) (Médio) Padrão de acabamento médio-alto: porcelanato nas áreas sociais, bancadas em quartzo e pontos de ar-condicionado em todos os dormitórios.
[F] Padrão de acabamento = Médio-alto

[P] Levantamento planialtimétrico atualizado do terreno (o existente é de 2019).
[P] Contratar sondagens SPT, com no mínimo 4 furos.

Próxima reunião: apresentação do estudo preliminar, em setembro."""

ATA_02 = """Apresentação do estudo preliminar (3 alternativas de implantação).

1. Alternativa A (torre na frente do lote): melhor visibilidade comercial, mas sombreia o lazer durante a tarde.
2. Alternativa B (torre recuada aos fundos): lazer voltado para a avenida e boa insolação norte nas unidades.
3. Alternativa C (torre em L): perde 4 unidades e encarece a estrutura.
A Cambará escolheu a alternativa B.

[D] (Arquitetura) (Alto) Implantação da torre recuada aos fundos: lazer e acesso de pedestres voltados para a avenida e insolação norte nas unidades.
[D] (Arquitetura) (Alto) Garagem em dois subsolos com rampa única de mão dupla: 72 vagas, uma por unidade de 2 dormitórios e duas por unidade de 3.
[F] Vagas de garagem = 72
[D] (Arquitetura) (Médio) Lazer no térreo: piscinas adulto e infantil, salão de festas, academia, brinquedoteca e espaço gourmet.

[P] Validar com o comercial a demanda por depósitos privativos nos subsolos.

Encaminhamento: desenvolver o anteprojeto sobre a alternativa B."""

ATA_03 = """Compatibilização estrutural do anteprojeto, com a Calço e a Veio.

1. A Calço apresentou o pré-dimensionamento com lajes maciças (registrado na {D:estrutura_macica}): 28 pilares por pavimento tipo e vigas atravessando salas e dormitórios.
2. A arquitetura pediu planta livre nas unidades de 3 dormitórios, para permitir opções de planta na venda.
3. Comparadas lajes nervuradas com cubetas plásticas: sem vigas internas, pilares reduzidos de 28 para 22 por pavimento e consumo de concreto semelhante, com aumento da altura entre pisos.
4. A Veio pediu que as prumadas hidráulicas fiquem fora das unidades.

[D] (Estrutura) (Alto) Lajes nervuradas no lugar das maciças (revisão da {D:estrutura_macica}): cubetas plásticas, h = 30 cm, nos pavimentos tipo; elimina as vigas internas e reduz o número de pilares.
[F] Tipo de laje = Nervurada
[D] (Arquitetura) (Médio) Piso a piso do tipo de 2,80 para 2,95 m: mantém pé-direito livre de 2,60 m nos ambientes com a laje nervurada.
[F] Piso a piso – pavimento tipo = 2,95
[F] Altura da edificação = 41,90
[D] (Hidrossanitário) (Médio) Prumadas hidráulicas em shafts fora das unidades: shafts visitáveis junto às circulações, para facilitar a manutenção e a medição individual.

[P] Laudo cautelar de vizinhança antes do início das fundações (edifício a leste, junto à divisa).

A Calço envia o novo pré-dimensionamento até 19/11."""

ATA_04 = """Fachada e esquadrias, com a Envoltória.

1. Apresentadas três composições de fachada: ACM + vidro, porcelanato ventilado e textura acrílica com frisos.
2. A Cambará descartou o ACM pela manutenção e pela imagem de prédio comercial.
3. A Envoltória recomendou fixação mecânica (inserts) para placas acima de 60 × 60 cm em altura.
4. Varandas: a convenção já deve prever o envidraçamento, para não haver padrões diferentes na fachada.

[D] (Arquitetura) (Alto) Fachada em porcelanato ventilado: placas 60 × 120 com inserts metálicos nas empenas e na fachada frontal; textura acrílica nas faces internas das varandas.
[F] Fachada = Porcelanato ventilado
[D] (Arquitetura) (Médio) Esquadrias de alumínio linha 30: pintura eletrostática grafite e vidro laminado 6 mm nas varandas.
[F] Esquadrias = Alumínio
[D] (Arquitetura) (Médio) Envidraçamento das varandas na convenção: padrão único definido pela incorporadora, previsto na convenção do condomínio.

[P] Amostra física do porcelanato e mock-up da fixação para aprovação da Cambará."""

ATA_05 = """Análise do comunique-se da prefeitura sobre o projeto legal protocolado em 10/02.

1. A prefeitura exigiu recuo de 1,50 m do subsolo 1 na faixa de arborização da calçada.
2. Pediu o recálculo da taxa de permeabilidade: o jardim sobre laje conta só 50%.
3. Pediu o detalhamento das vagas acessíveis e para idosos.
4. O Sérgio estima reanálise em 30 dias após a reapresentação.

[D] (Urbanismo) (Alto) Atender ao comunique-se: recuar o subsolo 1 em 1,50 m na frente do lote e ampliar o jardim sobre solo natural na faixa frontal.
[F] Vagas de garagem = 70
[F] Área construída total prevista = 8.620,00
[D] (Urbanismo) (Médio) Vagas acessíveis e para idosos no subsolo 1: três acessíveis e duas para idosos, sem reduzir as vagas privativas; as de visitantes vão para o térreo.
[D] (Geral) (Médio) Prazo de projeto estendido em 1 mês: reanálise da prefeitura após o comunique-se.
[F] Prazo previsto = 15

[P] Reapresentar o projeto legal com as correções até 15/04/2026."""

ATA_06 = """Revisão de custos (engenharia de valor), com a equipe de orçamentos da Cambará.

1. A Fernanda apresentou o orçamento paramétrico sobre o anteprojeto compatibilizado: R$ 41,2 milhões, 7% acima da meta.
2. Os maiores desvios: fachada ventilada em todas as faces (+ R$ 1,4 milhão) e aquecimento a gás individual (shafts e chaminés em todas as unidades).
3. A Veio apresentou o sistema central coletivo com apoio solar e medição individual de água quente.

[D] (Orçamento) (Alto) Orçamento paramétrico de R$ 41,2 milhões: CUB + 18% de itens fora do CUB, acima da meta de R$ 39 milhões.
[F] Orçamento estimado = 41.200.000,00
[D] (Hidrossanitário) (Alto) Aquecimento central coletivo a gás (revisão da {D:aquecimento_individual}): com apoio solar e medição individual de água quente.
[F] Aquecimento de água = Gás central coletivo
[D] (Arquitetura) (Médio) Porcelanato ventilado só na fachada frontal (revisão da {D:fachada_ventilada}): empenas laterais em textura acrílica com frisos.
[F] Fachada = Mista
[D] (Orçamento) (Alto) Nova meta de orçamento depois da engenharia de valor: R$ 39,6 milhões.
[F] Orçamento estimado = 39.600.000,00

A Cambará aprovou as três revisões. A Fernanda atualiza o orçamento para o executivo."""

ATA_07 = """Revisão do pavimento de cobertura.

1. O comercial informou que os apartamentos do último andar foram os primeiros reservados no pré-lançamento.
2. Proposta: transformar o 12º pavimento e o ático em duas coberturas duplex com terraço e piscina privativa.
3. A Calço avaliou o impacto: reforço local da laje do terraço, sem mudar a malha de pilares.

[D] (Arquitetura) (Alto) Duas coberturas duplex no último pavimento: terraço e piscina privativa, no lugar de 4 apartamentos tipo.
[F] Nº de unidades = 46
[D] (Estrutura) (Médio) Reforço da laje do terraço da cobertura: sobrecarga de 15 kN/m² na área das piscinas privativas.

[P] Confirmar com o comercial quantas vagas cada cobertura terá."""

ATA_08_RASCUNHO = """Compatibilização final do executivo (rascunho — ainda não fechada).

1. Revisão do modelo federado: 14 interferências entre dutos de exaustão e vigas de transição do térreo.
2. A Veio propõe passar os dutos pela laje nervurada, entre as nervuras.
3. A Calço precisa confirmar as furações.

[D] (HVAC) (Médio) Dutos de exaustão entre as nervuras: passagem dos dutos das churrasqueiras, com furação confirmada pela Calço.
[P] Calço confirmar a furação das nervuras no térreo e no 1º tipo."""

# ------------------------------------------------------------------ cronograma (3 versões)
# (nome, tipo, início, entrega, depende da anterior, padrão). Marco: início = entrega.

def _cron(*linhas):
    return [{"nome": n, "tipo": t, "inicio": i, "entrega": e, "depende": dep, "padrao": pad}
            for n, t, i, e, dep, pad in linhas]


CRONOGRAMA_V1 = _cron(
    ("Kick-off", "marco", date(2025, 8, 19), date(2025, 8, 19), False, True),
    ("Estudo preliminar", "etapa", date(2025, 8, 20), date(2025, 10, 30), True, True),
    ("Anteprojeto", "etapa", date(2025, 11, 3), date(2026, 1, 30), True, True),
    ("Projeto básico", "etapa", date(2026, 2, 2), date(2026, 4, 30), True, True),
    ("Aprovação na prefeitura", "etapa", date(2026, 2, 10), date(2026, 5, 15), False, False),
    ("Projeto executivo", "etapa", date(2026, 5, 4), date(2026, 9, 30), True, True),
    ("Liberado para obra", "marco", date(2026, 10, 15), date(2026, 10, 15), True, True),
)
# D-023: básico +30 dias (reanálise da prefeitura); executivo e liberação recalculados
CRONOGRAMA_V2 = _cron(
    ("Kick-off", "marco", date(2025, 8, 19), date(2025, 8, 19), False, True),
    ("Estudo preliminar", "etapa", date(2025, 8, 20), date(2025, 10, 30), True, True),
    ("Anteprojeto", "etapa", date(2025, 11, 3), date(2026, 1, 30), True, True),
    ("Projeto básico", "etapa", date(2026, 2, 2), date(2026, 5, 30), True, True),
    ("Aprovação na prefeitura", "etapa", date(2026, 2, 10), date(2026, 6, 16), False, False),
    ("Projeto executivo", "etapa", date(2026, 6, 3), date(2026, 10, 30), True, True),
    ("Liberado para obra", "marco", date(2026, 11, 14), date(2026, 11, 14), True, True),
)
# D-032: coberturas duplex, executivo +15 dias; liberação recalculada
CRONOGRAMA_V3 = _cron(
    ("Kick-off", "marco", date(2025, 8, 19), date(2025, 8, 19), False, True),
    ("Estudo preliminar", "etapa", date(2025, 8, 20), date(2025, 10, 30), True, True),
    ("Anteprojeto", "etapa", date(2025, 11, 3), date(2026, 1, 30), True, True),
    ("Projeto básico", "etapa", date(2026, 2, 2), date(2026, 5, 30), True, True),
    ("Aprovação na prefeitura", "etapa", date(2026, 2, 10), date(2026, 6, 16), False, False),
    ("Projeto executivo", "etapa", date(2026, 6, 3), date(2026, 11, 14), True, True),
    ("Liberado para obra", "marco", date(2026, 11, 29), date(2026, 11, 29), True, True),
)

# ------------------------------------------------------------------ etapas (ordem cronológica)
# 'quando' é horário de Brasília. 'autor' é o username de quem executa a etapa.


def _d(ano, mes, dia, hora=10, minuto=0):
    return datetime(ano, mes, dia, hora, minuto)


ETAPAS = [
    # ---------------- Estudo preliminar (ago–out/2025)
    {"tipo": "projeto", "quando": _d(2025, 8, 11, 9, 30), "autor": "demo.rafael"},
    {"tipo": "membros", "quando": _d(2025, 8, 11, 9, 40), "autor": "demo.rafael"},
    {"tipo": "ficha", "quando": _d(2025, 8, 12, 15, 10), "autor": "demo.rafael", "itens": FICHA_INICIAL},
    {"tipo": "documento", "quando": _d(2025, 8, 13, 11), "autor": "demo.bianca", "nome": "Layout",
     "situacao": "Recebido", "data_recebimento": date(2025, 8, 8),
     "observacao": "Programa de necessidades da Cambará (planilha rev. 02)"},
    {"tipo": "documento", "quando": _d(2025, 8, 13, 11, 5), "autor": "demo.bianca",
     "nome": "Projetos preliminares", "situacao": "N/A",
     "observacao": "Terreno sem estudo anterior"},
    {"tipo": "documento", "quando": _d(2025, 8, 13, 11, 6), "autor": "demo.bianca",
     "nome": "Relatório de sondagem a trado (CBR)", "situacao": "N/A",
     "observacao": "Não se aplica: sem pavimentação externa relevante"},

    {"tipo": "ata", "quando": _d(2025, 8, 19, 14), "fechamento": _d(2025, 8, 20, 9, 15),
     "autor": "demo.rafael", "titulo": "Reunião de partida com a incorporadora",
     "participantes": _p(HELENA, RAFAEL, MARCOS, JULIANA), "texto": ATA_01,
     "chaves": ["programa", "padrao_acabamento"],
     "pendencias": [
         {"pendencia": "planialtimétrico", "categoria": "Geral", "responsavel": "Cambará (contratação)",
          "prazo": date(2025, 9, 5)},
         {"pendencia": "sondagens SPT", "categoria": "Fundações", "responsavel": "Cambará (contratação)",
          "prazo": date(2025, 10, 10)},
     ]},
    {"tipo": "cronograma", "quando": _d(2025, 8, 19, 18), "autor": "demo.rafael", "itens": CRONOGRAMA_V1},

    {"tipo": "decisao", "quando": _d(2025, 9, 2, 16, 40), "autor": "demo.helena", "chave": "sem_outorga",
     "titulo": "Projeto dentro do CA básico, sem outorga onerosa",
     "categoria": "Urbanismo", "impacto": "Alto",
     "descricao": "O projeto será desenvolvido dentro do coeficiente de aproveitamento básico da "
                  "ZUM-2 (CA 4,0), sem compra de potencial construtivo.",
     "justificativa": "O programa de 48 unidades cabe no CA básico, com as áreas de garagem e lazer "
                      "como não computáveis. A outorga exigiria análise do conselho municipal "
                      "(4 a 6 meses a mais) e pagamento estimado de R$ 1,9 milhão.",
     "alternativa": "Outorga onerosa para CA 4,8 (+2 pavimentos, +8 unidades): descartada pelo custo "
                    "e pelo risco ao prazo de lançamento.",
     "checklist": [{"tarefa": "Consulta prévia de viabilidade protocolada", "feito": True},
                   {"tarefa": "Certidão de uso do solo emitida", "feito": True},
                   {"tarefa": "Quadro de áreas preliminar conferido", "feito": True}]},

    {"tipo": "documento", "quando": _d(2025, 9, 5, 17), "autor": "demo.bianca",
     "nome": "Levantamento topográfico", "situacao": "Recebido", "data_recebimento": date(2025, 9, 5),
     "observacao": "Planialtimétrico cadastral, setembro/2025 (DWG + PDF)"},
    {"tipo": "resolver", "quando": _d(2025, 9, 8, 10), "autor": "demo.rafael", "pendencia": "planialtimétrico",
     "nova_decisao": {"chave": "base_topografica",
                      "titulo": "Planialtimétrico de setembro/2025 como base oficial do projeto",
                      "categoria": "Geral", "impacto": "Baixo",
                      "descricao": "Todas as disciplinas passam a usar o levantamento de 05/09/2025, "
                                   "que substitui o de 2019.",
                      "justificativa": "O novo levantamento mostrou declive 0,6 m maior que o de 2019 "
                                       "nos fundos do lote."},
     "observacao": "Arquivo distribuído aos complementares em 08/09."},

    {"tipo": "ata", "quando": _d(2025, 9, 23, 14, 30), "fechamento": _d(2025, 9, 24, 10),
     "autor": "demo.bianca", "titulo": "Apresentação do estudo preliminar",
     "participantes": _p(HELENA, RAFAEL, BIANCA, MARCOS, JULIANA), "texto": ATA_02,
     "chaves": ["implantacao", "garagem", "lazer"],
     "pendencias": [{"pendencia": "depósitos privativos", "categoria": "Arquitetura",
                     "responsavel": "Juliana (comercial Cambará)", "prazo": date(2025, 10, 31)}]},

    {"tipo": "documento", "quando": _d(2025, 10, 10, 15), "autor": "demo.bianca",
     "nome": "Relatórios de Sondagens SPT", "situacao": "Recebido", "data_recebimento": date(2025, 10, 10),
     "observacao": f"4 furos (SP-01 a SP-04), {GEOTECNIA}, rev. R01"},
    {"tipo": "decisao", "quando": _d(2025, 10, 16, 11, 20), "autor": "demo.tiago", "chave": "fundacoes",
     "titulo": "Fundações em estacas hélice contínua Ø50 e Ø60 cm",
     "categoria": "Fundações", "impacto": "Alto",
     "descricao": "Estacas hélice contínua monitorada, diâmetros de 50 e 60 cm, comprimento "
                  "previsto de 16 m, com blocos de coroamento sobre a laje do subsolo 2.",
     "justificativa": "As sondagens SP-01 a SP-04 indicam a camada resistente entre 14 e 16 m e nível "
                      "d'água a 6 m. A hélice contínua não vibra, o que protege o edifício vizinho "
                      "junto à divisa leste.",
     "alternativa": "Estacas pré-moldadas cravadas (vibração na vizinhança) e tubulões (inviáveis "
                    "abaixo do nível d'água).",
     "checklist": [{"tarefa": "Relatório de sondagens R01 analisado", "feito": True},
                   {"tarefa": "Estimativa de cargas por pilar", "feito": True},
                   {"tarefa": "Consulta a 2 executoras sobre disponibilidade", "feito": False}],
     "ficha": (SIS, "Fundações", "", "Estaca hélice contínua")},
    {"tipo": "resolver", "quando": _d(2025, 10, 16, 11, 30), "autor": "demo.tiago", "pendencia": "sondagens SPT",
     "decisao": "fundacoes", "observacao": "Sondagens recebidas em 10/10 e usadas na definição das fundações."},

    {"tipo": "decisao", "quando": _d(2025, 10, 21, 17), "autor": "demo.tiago", "chave": "estrutura_macica",
     "titulo": "Estrutura em concreto armado convencional com lajes maciças",
     "categoria": "Estrutura", "impacto": "Alto",
     "descricao": "Pórticos de concreto armado com lajes maciças de 12 cm nos pavimentos tipo e "
                  "vigas de borda e internas; pré-dimensionamento com 28 pilares por pavimento.",
     "justificativa": "Solução conhecida pelas construtoras da região, com mão de obra disponível e "
                      "menor custo de fôrmas para a geometria do estudo preliminar.",
     "alternativa": "Alvenaria estrutural: descartada porque impede as opções de planta pedidas pelo comercial.",
     "ficha": [(SIS, "Sistema estrutural", "", "Concreto armado convencional"),
               (SIS, "Tipo de laje", "", "Maciça")]},

    {"tipo": "cancelar", "quando": _d(2025, 10, 30, 9), "autor": "demo.rafael", "pendencia": "depósitos privativos",
     "motivo": "O comercial descartou os depósitos privativos; o espaço no subsolo 2 vira bicicletário."},

    # ---------------- Anteprojeto (nov/2025–jan/2026)
    {"tipo": "ata", "quando": _d(2025, 11, 18, 9), "fechamento": _d(2025, 11, 18, 18, 20),
     "autor": "demo.rafael", "titulo": "Compatibilização estrutural do anteprojeto",
     "participantes": _p(HELENA, RAFAEL, TIAGO, CAMILA), "texto": ATA_03,
     "chaves": ["estrutura_nervurada", "piso_a_piso", "shafts"],
     "pendencias": [{"pendencia": "Laudo cautelar", "categoria": "Fundações",
                     "responsavel": "Cambará (contratação)", "prazo": date(2026, 11, 13)}]},
    {"tipo": "adendo", "quando": _d(2025, 11, 20, 8, 45), "autor": "demo.rafael", "ata": 3,
     "texto": "Correção do item 3, conforme o pré-dimensionamento revisado que a Calço enviou em "
              "19/11: com as lajes nervuradas, os pilares do pavimento tipo passam de 28 para 24 "
              "(e não para 22, como foi dito na reunião)."},

    {"tipo": "decisao", "quando": _d(2025, 12, 2, 14), "autor": "demo.camila", "chave": "eletrica",
     "titulo": "Medição individual de energia e infraestrutura para recarga de veículos elétricos",
     "categoria": "Elétrica", "impacto": "Médio",
     "descricao": "Centro de medição no térreo, junto ao acesso de serviço. Eletrodutos secos e "
                  "reserva de carga para recarga de veículos elétricos em 20% das vagas.",
     "justificativa": "Atende à concessionária e antecipa uma demanda crescente dos compradores, "
                      "sem custo de equipamentos agora.",
     "alternativa": "Carregadores instalados na entrega: custo de R$ 380 mil, descartado pela Cambará.",
     "checklist": [{"tarefa": "Consulta de viabilidade à concessionária", "feito": True},
                   {"tarefa": "Cálculo de demanda com a reserva para recarga", "feito": True}]},
    {"tipo": "decisao", "quando": _d(2025, 12, 9, 10, 30), "autor": "demo.camila", "chave": "ar_condicionado",
     "titulo": "Infraestrutura para ar-condicionado split com condensadoras em nichos técnicos",
     "categoria": "HVAC", "impacto": "Médio",
     "descricao": "Pontos elétricos, dreno e linha frigorífica embutida para split em salas e "
                  "dormitórios. Condensadoras em nichos ventilados na fachada, com grelha.",
     "justificativa": "Mantém a fachada limpa e dá ao comprador liberdade para instalar os aparelhos.",
     "alternativa": "VRF central: descartado pelo custo de implantação e pelo aumento da taxa de condomínio."},
    {"tipo": "decisao", "quando": _d(2025, 12, 16, 15), "autor": "demo.camila", "chave": "aquecimento_individual",
     "titulo": "Aquecimento de água a gás individual (aquecedor de passagem)",
     "categoria": "Hidrossanitário", "impacto": "Médio",
     "descricao": "Aquecedor de passagem a gás em cada unidade, na área de serviço, com medição "
                  "individual de gás e chaminé coletiva por prumada.",
     "justificativa": "Padrão de mercado para o médio-alto e sem custo condominial de operação.",
     "alternativa": "Aquecimento elétrico de passagem: consumo alto e risco de sobrecarga na demanda.",
     "ficha": (SIS, "Aquecimento de água", "", "Gás individual")},

    {"tipo": "ata", "quando": _d(2026, 1, 27, 14), "fechamento": _d(2026, 1, 28, 11),
     "autor": "demo.bianca", "titulo": "Fachada e esquadrias",
     "participantes": _p(HELENA, RAFAEL, BIANCA, MARCOS, PATRICIA), "texto": ATA_04,
     "chaves": ["fachada_ventilada", "esquadrias", "envidracamento"],
     "pendencias": [{"pendencia": "Amostra física", "categoria": "Arquitetura",
                     "responsavel": "Patrícia (Envoltória)", "prazo": date(2026, 3, 6)}]},

    # ---------------- Projeto legal e básico (fev–jun/2026)
    {"tipo": "decisao", "quando": _d(2026, 2, 10, 17, 30), "autor": "demo.helena", "chave": "protocolo",
     "titulo": "Protocolo do projeto legal na prefeitura",
     "categoria": "Urbanismo", "impacto": "Alto",
     "descricao": f"Projeto legal protocolado com área computável de 6.980 m², pelo escritório "
                  f"{LEGALIZACAO}.",
     "justificativa": "Prazo combinado com a Cambará para manter o lançamento no 1º semestre.",
     "checklist": [{"tarefa": "RRT de projeto emitido", "feito": True},
                   {"tarefa": "Memorial descritivo e quadro de áreas", "feito": True},
                   {"tarefa": "Anuência prévia do Corpo de Bombeiros", "feito": False}],
     "ficha": (O, "Situação do projeto legal", "", "Protocolado em 10/02/2026")},
    {"tipo": "decisao", "quando": _d(2026, 2, 24, 11), "autor": "demo.rafael", "chave": "escada",
     "titulo": "Escada à prova de fumaça com antecâmara e elevador de emergência",
     "categoria": "PPCI", "impacto": "Alto",
     "descricao": "Escada enclausurada à prova de fumaça, com antecâmara ventilada por duto, e um "
                  "dos elevadores sociais tratado como elevador de emergência.",
     "justificativa": "A altura da edificação passa de 30 m, o que exige esse tipo de escada pela "
                      "instrução técnica do Corpo de Bombeiros.",
     "alternativa": "Escada enclausurada protegida: não atende à exigência para a altura do edifício."},
    {"tipo": "resolver", "quando": _d(2026, 3, 9, 16), "autor": "demo.bianca", "pendencia": "Amostra física",
     "decisao": "fachada_ventilada",
     "observacao": "Amostra e mock-up aprovados pela Cambará em visita à fábrica, em 09/03."},

    {"tipo": "ata", "quando": _d(2026, 3, 17, 10), "fechamento": _d(2026, 3, 17, 17, 40),
     "autor": "demo.rafael", "titulo": "Comunique-se da prefeitura sobre o projeto legal",
     "participantes": _p(HELENA, RAFAEL, MARCOS, SERGIO), "texto": ATA_05,
     "chaves": ["recuo_subsolo", "vagas_pne", "prazo_extendido"],
     "pendencias": [{"pendencia": "Reapresentar o projeto legal", "categoria": "Urbanismo",
                     "responsavel": "Sérgio (Rito)", "prazo": date(2026, 4, 15)}]},
    {"tipo": "revisao_cronograma", "quando": _d(2026, 3, 17, 18), "autor": "demo.rafael",
     "decisao": "prazo_extendido", "itens": CRONOGRAMA_V2},
    {"tipo": "resolver", "quando": _d(2026, 4, 14, 15), "autor": "demo.rafael", "pendencia": "Reapresentar o projeto legal",
     "nova_decisao": {"chave": "reapresentacao",
                      "titulo": "Projeto legal reapresentado com as correções do comunique-se",
                      "categoria": "Urbanismo", "impacto": "Médio",
                      "descricao": "Reapresentado com recuo do subsolo, permeabilidade recalculada "
                                   "e quadro de vagas acessíveis.",
                      "justificativa": "Atende integralmente aos 3 itens do comunique-se."},
     "observacao": "Protocolo de reapresentação feito em 14/04."},
    {"tipo": "decisao", "quando": _d(2026, 4, 28, 10), "autor": "demo.tiago", "chave": "contencao",
     "titulo": "Contenção em estacas justapostas com tirantes provisórios na divisa leste",
     "categoria": "Fundações", "impacto": "Médio",
     "descricao": "Cortina de estacas hélice contínua justapostas (Ø40) com uma linha de tirantes "
                  "provisórios na divisa leste; nas demais divisas, talude e cortina atirantada.",
     "justificativa": "O edifício vizinho está a 1,2 m da divisa leste e tem fundação rasa: a "
                      "contenção precisa ser executada antes da escavação.",
     "alternativa": "Parede diafragma: mais rígida, porém 40% mais cara e com equipamento indisponível na região."},

    {"tipo": "ata", "quando": _d(2026, 5, 19, 9, 30), "fechamento": _d(2026, 5, 20, 10),
     "autor": "demo.rafael", "titulo": "Revisão de custos (engenharia de valor)",
     "participantes": _p(HELENA, RAFAEL, MARCOS, CAMILA, FERNANDA), "texto": ATA_06,
     "chaves": ["orcamento_parametrico", "aquecimento_central", "fachada_revisada", "meta_orcamento"]},

    {"tipo": "decisao", "quando": _d(2026, 6, 16, 16), "autor": "demo.helena", "chave": "alvara",
     "titulo": "Alvará de construção emitido: início do projeto executivo",
     "categoria": "Urbanismo", "impacto": "Alto",
     "descricao": "Projeto legal aprovado sem novas exigências; alvará emitido em 16/06/2026.",
     "justificativa": "Com o alvará, o executivo começa sobre a versão aprovada, congelada como "
                      "referência para as disciplinas.",
     "checklist": [{"tarefa": "Alvará arquivado no projeto", "feito": True},
                   {"tarefa": "Versão aprovada distribuída aos complementares", "feito": True},
                   {"tarefa": "Cronograma do executivo atualizado", "feito": True}],
     "ficha": (O, "Situação do projeto legal", "", "Alvará emitido em 16/06/2026")},

    # ---------------- Executivo (jul–out/2026)
    {"tipo": "decisao", "quando": _d(2026, 7, 7, 11), "autor": "demo.rafael", "chave": "elevadores",
     "titulo": "Dois elevadores de 8 passageiros a 1,5 m/s",
     "categoria": "Arquitetura", "impacto": "Médio",
     "descricao": "Dois elevadores sociais de 8 passageiros, velocidade de 1,5 m/s, sem casa de "
                  "máquinas; um deles atende como elevador de emergência.",
     "justificativa": "O cálculo de tráfego para 46–48 unidades atende ao intervalo de 45 s no "
                      "horário de pico com duas cabines.",
     "alternativa": "Três elevadores (social, social e serviço): perda de 9 m² privativos por andar.",
     "ficha": (O, "Elevadores", "", "2 × 8 passageiros, 1,5 m/s (1 de emergência)")},

    {"tipo": "ata", "quando": _d(2026, 8, 25, 14), "fechamento": _d(2026, 8, 26, 9, 30),
     "autor": "demo.bianca", "titulo": "Revisão do pavimento de cobertura",
     "participantes": _p(HELENA, RAFAEL, BIANCA, MARCOS, JULIANA, TIAGO), "texto": ATA_07,
     "chaves": ["coberturas", "reforco_laje"],
     "pendencias": [{"pendencia": "vagas cada cobertura", "categoria": "Arquitetura",
                     "responsavel": "Juliana (comercial Cambará)", "prazo": date(2026, 9, 15)}]},
    {"tipo": "revisao_cronograma", "quando": _d(2026, 8, 26, 10), "autor": "demo.bianca",
     "decisao": "coberturas", "itens": CRONOGRAMA_V3},
    {"tipo": "pendencia", "quando": _d(2026, 9, 1, 10), "autor": "demo.rafael",
     "titulo": "Aprovação do projeto de PPCI no Corpo de Bombeiros",
     "descricao": "Protocolar o PPCI com escada à prova de fumaça, hidrantes e sistema de alarme.",
     "categoria": "PPCI", "responsavel": "Sérgio (Rito)", "prazo": date(2026, 11, 30)},
    {"tipo": "resolver", "quando": _d(2026, 9, 15, 11), "autor": "demo.rafael", "pendencia": "vagas cada cobertura",
     "nova_decisao": {"chave": "vagas_coberturas",
                      "titulo": "Três vagas para cada cobertura duplex",
                      "categoria": "Arquitetura", "impacto": "Baixo",
                      "descricao": "Cada cobertura recebe 3 vagas no subsolo 2, em sequência "
                                   "(vagas presas), sem alterar o total de vagas.",
                      "justificativa": "As 4 vagas dos apartamentos que deram lugar às coberturas "
                                       "foram redistribuídas."},
     "observacao": "Confirmado por e-mail pela Juliana em 14/09."},
    {"tipo": "decisao", "quando": _d(2026, 10, 6, 15), "autor": "demo.bianca", "chave": "interiores",
     "titulo": "Decoração das áreas comuns: madeira natural, terracota e verde-oliva",
     "categoria": "Arquitetura de Interiores", "impacto": "Médio",
     "descricao": "Paleta em madeira natural, terracota e verde-oliva no hall, no salão de festas e "
                  "no espaço gourmet; mobiliário de design nacional e iluminação indireta.",
     "justificativa": "Reforça o conceito de jardim do empreendimento e conversa com as quaresmeiras "
                      "do paisagismo frontal.",
     "alternativa": "Paleta neutra em cinza e branco: descartada por parecer igual aos concorrentes.",
     "checklist": [{"tarefa": "Moodboard aprovado pela Cambará", "feito": True},
                   {"tarefa": "Orçamento de mobiliário dentro da verba", "feito": True},
                   {"tarefa": "Amostras de revestimento recebidas", "feito": False}]},
    {"tipo": "pendencia", "quando": _d(2026, 10, 14, 16), "autor": "demo.camila",
     "titulo": "Definir fornecedor dos coletores solares",
     "descricao": "Comparar 3 propostas de coletores para o sistema de aquecimento central.",
     "categoria": "Hidrossanitário", "responsavel": "Camila (Veio)", "prazo": date(2026, 11, 6)},
    {"tipo": "ata", "quando": _d(2026, 10, 20, 14), "fechamento": None,
     "autor": "demo.rafael", "titulo": "Compatibilização final do executivo",
     "participantes": _p(RAFAEL, BIANCA, TIAGO, CAMILA), "texto": ATA_08_RASCUNHO, "chaves": []},
]

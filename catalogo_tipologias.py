"""Catálogo da ficha por tipologia: quais campos cada tipologia mostra, com quais opções.

Para incluir um sistema construtivo, um parâmetro ou uma característica ligada à
tipologia, basta acrescentar um CampoCatalogo em CAMPOS: não precisa alterar o banco
(os valores ficam na tabela da ficha, por grupo + nome) nem a tela.

Regras (ver docs/superpowers/specs/2026-10-30-ficha-por-tipologia-design.md):
- toda lista ganha a opção "Outro" na tela, que abre um campo de texto;
- um campo pode depender de outro da mesma tipologia (depende_de + valores_que_mostram);
- campo do catálogo que deixa de aparecer (outra tipologia ou dependência não atendida)
  é limpo ao gravar, e a limpeza entra no histórico.

Sem Flet e sem banco: usado pela tela, pelo serviço da ficha, pelas atas, pelo PDF e pela API.
"""
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple

from models import CAMPO_TIPOLOGIA, FICHA_GRUPOS, GRUPO_OUTRAS, GRUPO_PROGRAMA

OUTRO = "Outro"
GRUPO_SISTEMAS = "Sistemas construtivos"
GRUPO_ALTURAS = "Alturas e dimensões"
GRUPOS_DO_CATALOGO = (GRUPO_SISTEMAS, GRUPO_ALTURAS)  # cards novos, logo depois de Programa

TIPOLOGIAS = (
    "Residencial",
    "Comercial",
    "Industrial",
    "Condomínio de lotes",
    "Corporativo",
    "Shopping Center",
    "Data Center",
)

Chave = Tuple[str, str]  # (grupo, nome)


@dataclass(frozen=True)
class CampoCatalogo:
    nome: str
    opcoes: Tuple[str, ...] = ()           # vazio = campo de texto (ex.: números)
    unidade: str = ""
    grupo: str = GRUPO_SISTEMAS
    depende_de: Optional[str] = None       # nome de outro campo da mesma tipologia
    valores_que_mostram: Tuple[str, ...] = ()

    @property
    def chave(self) -> Chave:
        return (self.grupo, self.nome)


# ---------------------------------------------------------------- listas comuns

CONCRETO_ARMADO = "Concreto armado convencional"

FUNDACOES = CampoCatalogo("Fundações", (
    "Estaca hélice contínua", "Estaca escavada", "Estaca pré-moldada", "Estaca metálica",
    "Sapatas", "Radier", "Tubulão",
))
TIPO_DE_LAJE = CampoCatalogo(
    "Tipo de laje", ("Maciça", "Nervurada", "Treliçada", "Protendida", "Lisa (cogumelo)"),
    depende_de="Sistema estrutural", valores_que_mostram=(CONCRETO_ARMADO,),
)
VEDACOES_ALVENARIA = CampoCatalogo("Vedações", ("Bloco cerâmico", "Bloco de concreto", "Drywall (internas)"))


def _numero(nome: str, unidade: str, grupo: str = GRUPO_ALTURAS) -> CampoCatalogo:
    return CampoCatalogo(nome, unidade=unidade, grupo=grupo)


# Alturas de edifícios (Residencial, Comercial, Corporativo)
ALTURAS_EDIFICIO = (
    _numero("Piso a piso – pavimento tipo", "m"),
    _numero("Piso a piso – térreo", "m"),
    _numero("Piso a piso – subsolo / estacionamento", "m"),
    _numero("Piso a piso – cobertura", "m"),
    _numero("Piso a piso – casa de máquinas e barrilete", "m"),
    _numero("Pé-direito livre mínimo – pavimento tipo", "m"),
    _numero("Pé-direito – sanitários", "m"),
    _numero("Pé-direito – cozinhas", "m"),
    _numero("Espessura do contrapiso", "cm"),
)

# ---------------------------------------------------------------- campos por tipologia

CAMPOS: Dict[str, Tuple[CampoCatalogo, ...]] = {
    "Residencial": (
        CampoCatalogo("Tipo de empreendimento", ("Edifício vertical", "Casas em condomínio", "Casa unifamiliar")),
        CampoCatalogo("Sistema estrutural", (
            CONCRETO_ARMADO, "Alvenaria estrutural", "Paredes de concreto in loco", "Estrutura metálica",
            "Light steel frame", "Wood frame",
        )),
        TIPO_DE_LAJE,
        FUNDACOES,
        VEDACOES_ALVENARIA,
        CampoCatalogo("Fachada", (
            "Textura acrílica", "Porcelanato aderido", "Porcelanato ventilado", "ACM", "Pele de vidro", "Mista",
        )),
        CampoCatalogo("Esquadrias", ("Alumínio", "PVC", "Madeira")),
        CampoCatalogo("Aquecimento de água", (
            "Gás individual", "Gás central coletivo", "Solar com apoio", "Bomba de calor", "Elétrico",
        )),
        *ALTURAS_EDIFICIO,
    ),
    "Comercial": (
        CampoCatalogo("Sistema estrutural", (
            CONCRETO_ARMADO, "Estrutura metálica", "Pré-moldado de concreto", "Mista",
        )),
        TIPO_DE_LAJE,
        FUNDACOES,
        VEDACOES_ALVENARIA,
        CampoCatalogo("Fachada", ("Textura acrílica", "Porcelanato", "ACM", "Pele de vidro", "Mista")),
        CampoCatalogo("Climatização", ("Split", "VRF", "Central de água gelada", "Ventilação natural")),
        *ALTURAS_EDIFICIO,
    ),
    "Industrial": (
        CampoCatalogo("Sistema estrutural", ("Pré-moldado de concreto", "Metálica", "Mista (concreto e metálica)")),
        FUNDACOES,
        CampoCatalogo("Vedações", (
            "Blocos", "Telhas", "Mistas (blocos e telhas)", "Painéis pré-moldados", "Painéis termoisolantes",
        )),
        CampoCatalogo("Cobertura", ("Telha metálica simples", "Telha metálica termoacústica", "Telha zipada")),
        CampoCatalogo("Carga de piso", unidade="tf/m²"),
        CampoCatalogo("Pavimento externo", ("Rígido (concreto)", "Flexível (asfalto)", "Intertravado")),
        _numero("Altura dos portões", "m"),
        _numero("Altura da doca de carga e descarga", "m"),
    ),
    "Condomínio de lotes": (
        CampoCatalogo("Pavimentação viária", ("Asfalto (CBUQ)", "Bloquete intertravado", "Paralelepípedo", "Concreto")),
        CampoCatalogo("Drenagem pluvial", ("Rede convencional com galerias", "Rede com bacia de retenção")),
        CampoCatalogo("Abastecimento de água", ("Rede pública", "Poço com reservatório elevado")),
        CampoCatalogo("Esgotamento sanitário", (
            "Rede pública", "Estação de tratamento própria (ETE)", "Fossa e sumidouro por lote",
        )),
        CampoCatalogo("Rede elétrica", ("Aérea", "Subterrânea")),
        CampoCatalogo("Iluminação viária", ("LED em postes", "Convencional em postes")),
        CampoCatalogo("Fechamento do perímetro", ("Muro de alvenaria", "Muro pré-moldado", "Gradil")),
    ),
    "Corporativo": (
        CampoCatalogo("Sistema estrutural", (CONCRETO_ARMADO, "Estrutura metálica", "Mista")),
        TIPO_DE_LAJE,
        FUNDACOES,
        CampoCatalogo("Fachada", ("Pele de vidro (cortina de vidro)", "ACM", "Concreto aparente", "Mista")),
        CampoCatalogo("Climatização", ("VRF", "Central de água gelada", "Split")),
        *ALTURAS_EDIFICIO,
    ),
    "Shopping Center": (
        _numero("ABL – área bruta locável", "m²", GRUPO_PROGRAMA),
        _numero("Nº de lojas âncoras", "", GRUPO_PROGRAMA),
        _numero("Nº de lojas satélites", "", GRUPO_PROGRAMA),
        CampoCatalogo("Sistema estrutural", (CONCRETO_ARMADO, "Metálica", "Mista")),
        FUNDACOES,
        CampoCatalogo("Cobertura", ("Telha metálica", "Laje impermeabilizada", "Mista")),
        CampoCatalogo("Climatização", ("Central de água gelada", "VRF", "Rooftop")),
        _numero("Pé-direito – circulações comuns", "m"),
        _numero("Pé-direito – lojas", "m"),
        _numero("Espessura do contrapiso", "cm"),
    ),
    "Data Center": (
        _numero("Potência do data center", "MW", GRUPO_PROGRAMA),
        CampoCatalogo("Sistema estrutural", (CONCRETO_ARMADO, "Pré-moldado de concreto", "Estrutura metálica")),
        FUNDACOES,
        CampoCatalogo("Classificação Tier", ("Tier I", "Tier II", "Tier III", "Tier IV")),
        CampoCatalogo("Redundância", ("N", "N+1", "2N", "2N+1")),
        CampoCatalogo("Climatização", ("Expansão direta (DX)", "Água gelada", "Free cooling")),
        _numero("Pé-direito mínimo do data hall", "m"),
    ),
}


# ---------------------------------------------------------------- consultas

def campos_da_tipologia(tipologia: Optional[str]) -> Tuple[CampoCatalogo, ...]:
    return CAMPOS.get((tipologia or "").strip(), ())


def todos_os_campos() -> Dict[Chave, CampoCatalogo]:
    """Todos os campos do catálogo (de todas as tipologias), por (grupo, nome)."""
    todos: Dict[Chave, CampoCatalogo] = {}
    for campos in CAMPOS.values():
        for c in campos:
            todos.setdefault(c.chave, c)
    return todos


def ordem_dos_grupos() -> List[str]:
    """Ordem dos cards na tela e no PDF: os do catálogo entram logo depois de Programa."""
    ordem = []
    for grupo in FICHA_GRUPOS:
        ordem.append(grupo)
        if grupo == GRUPO_PROGRAMA:
            ordem.extend(GRUPOS_DO_CATALOGO)
    ordem.append(GRUPO_OUTRAS)
    return ordem


def campos_visiveis(valores: Dict[Chave, str]) -> List[CampoCatalogo]:
    """Campos do catálogo que aparecem com estes valores (tipologia + dependências).
    Um campo cujo pai está escondido também fica escondido."""
    tipologia = (valores.get((GRUPO_PROGRAMA, CAMPO_TIPOLOGIA)) or "").strip()
    visiveis: List[CampoCatalogo] = []
    nomes_visiveis = set()
    campos = campos_da_tipologia(tipologia)
    por_nome = {c.nome: c for c in campos}
    for c in campos:
        if c.depende_de:
            pai = por_nome[c.depende_de]
            if pai.nome not in nomes_visiveis:
                continue
            if (valores.get(pai.chave) or "").strip() not in c.valores_que_mostram:
                continue
        visiveis.append(c)
        nomes_visiveis.add(c.nome)
    return visiveis


def campos_a_limpar(atuais: Dict[Chave, str], novos: Dict[Chave, str]) -> List[Tuple[str, str, str, str]]:
    """Itens (grupo, nome, unidade, "") para limpar os campos do catálogo que têm valor e
    deixam de aparecer depois de aplicar 'novos' sobre 'atuais'. Itens que já vêm em
    'novos' não são repetidos."""
    combinados = dict(atuais)
    combinados.update(novos)
    visiveis = {c.chave for c in campos_visiveis(combinados)}
    limpar = []
    for chave, campo in todos_os_campos().items():
        if chave in visiveis or chave in novos:
            continue
        if (combinados.get(chave) or "").strip():
            limpar.append((campo.grupo, campo.nome, campo.unidade, ""))
    return limpar


# ---------------------------------------------------------------- tela: "Outro" + texto

def escolha_e_texto(campo: CampoCatalogo, valor: Optional[str]) -> Tuple[Optional[str], str]:
    """Como mostrar um valor gravado: (opção da lista, texto do campo 'Outro')."""
    valor = (valor or "").strip()
    if not valor:
        return None, ""
    if valor in campo.opcoes:
        return valor, ""
    return OUTRO, valor


def valor_gravado(campo: CampoCatalogo, escolha: Optional[str], texto: Optional[str]) -> str:
    """O que gravar a partir da tela. "Outro" grava o texto digitado (nunca a palavra)."""
    if escolha == OUTRO:
        return (texto or "").strip()
    return (escolha or "").strip()


def opcoes_da_tipologia() -> Iterable[str]:
    return TIPOLOGIAS + (OUTRO,)

"""Tabelas do banco (SQLModel).

Movidas de database.py e models.py sem mudar nenhuma coluna: o banco existente continua
valendo. database.py e models.py reexportam estas classes, então as telas Flet não mudam.

Toda mudança aqui precisa de uma migração em migracoes/versions/ (Alembic). O teste
tests/test_migracoes.py falha se o modelo e as migrações divergirem.

Mudanças de esquema ainda planejadas (ver docs/ARQUITETURA_API.md):
- autor_id (FK usuario) ao lado dos campos 'autor' em texto;
- tabela Anexo no lugar do texto 'anexos' separado por vírgula;
- índice único (projeto_id, numero) em Decisao, Reuniao e Pendencia.
"""
import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


def _agora() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


# ---------------------------------------------------------------- organizações (SaaS)

class Organizacao(SQLModel, table=True):
    """O escritório assinante. Usuários e projetos pertencem a uma organização, e nada
    atravessa essa fronteira: nem projetos, nem usuários, nem logos, nem auditoria."""
    id: Optional[int] = Field(default=None, primary_key=True)
    nome: str
    slug: str = Field(unique=True, index=True)   # identificador curto (ex.: "rua-estudio")
    ativa: bool = Field(default=True)            # desativada = ninguém dela entra
    data_criacao: datetime.datetime = Field(default_factory=_agora)
    # Assinatura (SaaS). Organizações antigas ficam 'interno' e 'ativa': não têm cobrança.
    plano: str = Field(default="interno")        # teste, solo, equipe, fundador ou interno
    assinatura_status: str = Field(default="ativa")  # teste, ativa, pendente, atrasada, cancelada
    ciclo: Optional[str] = None                  # mensal ou anual
    teste_fim: Optional[datetime.datetime] = None      # fim do teste grátis (UTC, sem fuso)
    fidelidade_fim: Optional[datetime.datetime] = None  # fim da fidelidade do plano Fundador
    asaas_cliente_id: Optional[str] = None
    asaas_assinatura_id: Optional[str] = None
    asaas_link_id: Optional[str] = None         # plano anual: link de pagamento parcelável
    asaas_link_url: Optional[str] = None


# ---------------------------------------------------------------- usuários e acesso

class Usuario(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(unique=True)          # único na plataforma toda (é o login)
    senha: str
    nome_completo: str
    admin: bool = Field(default=False)          # administrador DA SUA organização
    pode_criar_projetos: bool = Field(default=True)  # False = cliente (só acompanha)
    organizacao_id: Optional[int] = Field(default=None, foreign_key="organizacao.id", index=True)
    # Dono da plataforma: cria e desativa organizações. NÃO dá acesso aos projetos delas.
    superadmin: bool = Field(default=False)
    tema: Optional[str] = None  # "claro" ou "escuro" (vazio = escuro, o padrão)
    email: Optional[str] = Field(default=None, unique=True, index=True)  # recuperação de senha
    email_verificado: bool = Field(default=False)
    termos_aceitos_em: Optional[datetime.datetime] = None  # aceite dos Termos no cadastro


class MembroProjeto(SQLModel, table=True):
    """Quem tem acesso a cada projeto e com qual papel (Responsável, Editor ou Leitor)."""
    id: Optional[int] = Field(default=None, primary_key=True)
    projeto_id: int = Field(foreign_key="projeto.id")
    usuario_id: int = Field(foreign_key="usuario.id")
    papel: str = "Leitor"


# ---------------------------------------------------------------- projeto e ficha

class Projeto(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    nome: str
    cliente: str
    descricao: Optional[str] = None
    data_criacao: datetime.datetime = Field(default_factory=_agora)
    arquivado: bool = Field(default=False)  # projeto arquivado sai das listas e não conta no plano
    # Sem organização, o projeto fica inacessível (falha segura). Os serviços sempre preenchem.
    organizacao_id: Optional[int] = Field(default=None, foreign_key="organizacao.id", index=True)


class Caracteristica(SQLModel, table=True):
    """Um campo da ficha do empreendimento (ex.: 'Área do terreno' = '1.250,00')."""
    id: Optional[int] = Field(default=None, primary_key=True)
    projeto_id: int = Field(foreign_key="projeto.id")
    grupo: str
    nome: str
    valor: str = ""
    unidade: Optional[str] = None
    atualizado_por: str = ""
    data_atualizacao: datetime.datetime = Field(default_factory=_agora)


class CaracteristicaHistorico(SQLModel, table=True):
    """Cada alteração da ficha fica registrada: quem mudou, o quê e quando."""
    id: Optional[int] = Field(default=None, primary_key=True)
    projeto_id: int = Field(foreign_key="projeto.id")
    grupo: str
    nome: str
    valor_anterior: Optional[str] = None
    valor_novo: Optional[str] = None
    autor: str
    data_registro: datetime.datetime = Field(default_factory=_agora)
    decisao_id: Optional[int] = Field(default=None, foreign_key="decisao.id")  # decisão que motivou
    reuniao_id: Optional[int] = Field(default=None, foreign_key="reuniao.id")  # ata de origem


class TipologiaProjeto(str, Enum):
    industrial = "Industrial"
    multifamiliar = "Multifamiliar"
    corporativo = "Corporativo"
    shopping = "Shopping Center"
    datacenter = "Data Center"


class PadraoConstrutivo(SQLModel, table=True):
    """SEM USO desde a migração 0011: os sistemas construtivos viraram campos da ficha
    (catalogo_tipologias.py). A tabela fica no banco só para não apagar dados antigos."""
    id: Optional[int] = Field(default=None, primary_key=True)
    projeto_id: int = Field(foreign_key="projeto.id", index=True)
    tipologia: str

    # Campos industriais (nulos se a tipologia for outra)
    ind_estrutura: Optional[str] = None
    ind_vedacao: Optional[str] = None
    ind_carga_piso: Optional[float] = None
    ind_pavimento_externo: Optional[str] = None

    # Campos multifamiliar
    multi_sistema_principal: Optional[str] = None
    multi_tipo_laje: Optional[str] = None

    # Campos corporativo / data center
    corp_fachada: Optional[str] = None
    dc_tier_redundancia: Optional[str] = None

    # Campos shopping
    shop_estrutura: Optional[str] = None
    shop_cobertura: Optional[str] = None


CAMPOS_PADRAO = (
    "tipologia",
    "ind_estrutura",
    "ind_vedacao",
    "ind_carga_piso",
    "ind_pavimento_externo",
    "multi_sistema_principal",
    "multi_tipo_laje",
    "corp_fachada",
    "dc_tier_redundancia",
    "shop_estrutura",
    "shop_cobertura",
)


# ---------------------------------------------------------------- atas, decisões, pendências

ATA_RASCUNHO, ATA_FECHADA = "Rascunho", "Fechada"


class Reuniao(SQLModel, table=True):
    """Ata de reunião. Depois de fechada, o texto não muda: correções entram como adendos."""
    id: Optional[int] = Field(default=None, primary_key=True)
    projeto_id: int = Field(foreign_key="projeto.id")
    numero: int                       # sequencial dentro do projeto (Ata 01, 02...)
    titulo: str
    data_reuniao: datetime.date = Field(default_factory=datetime.date.today)
    participantes: Optional[str] = None
    texto: str = ""
    status: str = ATA_RASCUNHO        # "Rascunho" ou "Fechada"
    autor: str = ""
    data_fechamento: Optional[datetime.datetime] = None


class AtaAdendo(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    reuniao_id: int = Field(foreign_key="reuniao.id")
    texto: str
    autor: str
    data_registro: datetime.datetime = Field(default_factory=_agora)


class Decisao(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    projeto_id: int = Field(foreign_key="projeto.id")
    titulo: str
    categoria: str
    descricao: str
    justificativa: str
    alternativa_descartada: Optional[str] = None
    impacto: str
    autor: str
    data_decisao: datetime.date = Field(default_factory=datetime.date.today)
    anexos: Optional[str] = None      # Caminhos dos arquivos, separados por vírgula
    checklist: Optional[str] = None   # JSON com a lista de verificações
    reuniao_id: Optional[int] = Field(default=None, foreign_key="reuniao.id")  # ata de origem
    numero: Optional[int] = None      # sequencial no projeto (D-001, D-002...)


PENDENCIA_ABERTA, PENDENCIA_RESOLVIDA, PENDENCIA_CANCELADA = "Aberta", "Resolvida", "Cancelada"
SITUACOES_PENDENCIA = (PENDENCIA_ABERTA, PENDENCIA_RESOLVIDA, PENDENCIA_CANCELADA)


class Pendencia(SQLModel, table=True):
    """Assunto que ainda aguarda decisão. Entra pela tela de pendências ou por uma linha [P]
    de uma ata fechada. É resolvido ligando-o a uma decisão (existente ou criada na hora)."""
    id: Optional[int] = Field(default=None, primary_key=True)
    projeto_id: int = Field(foreign_key="projeto.id", index=True)
    numero: int                        # sequencial no projeto (P-001, P-002...)
    titulo: str
    descricao: str = ""
    categoria: str = "Geral"
    responsavel: str = ""              # quem precisa decidir / trazer a resposta
    prazo: Optional[datetime.date] = None
    status: str = PENDENCIA_ABERTA
    autor: str = ""
    data_criacao: datetime.datetime = Field(default_factory=_agora)
    reuniao_id: Optional[int] = Field(default=None, foreign_key="reuniao.id")  # ata de origem
    decisao_id: Optional[int] = Field(default=None, foreign_key="decisao.id")  # decisão que resolveu
    resolucao: str = ""                # observação ao resolver/cancelar
    resolvida_por: str = ""
    data_resolucao: Optional[datetime.datetime] = None


# ---------------------------------------------------------------- documentos de referência

DOC_PENDENTE, DOC_RECEBIDO, DOC_NA = "Pendente", "Recebido", "N/A"
SITUACOES_DOCUMENTO = (DOC_RECEBIDO, DOC_PENDENTE, DOC_NA)


class DocumentoReferencia(SQLModel, table=True):
    """Item do checklist de arquivos e informações recebidas do cliente (topografia,
    sondagens, BEP...). Os itens padrão nascem com o projeto; a equipe acrescenta outros."""
    id: Optional[int] = Field(default=None, primary_key=True)
    projeto_id: int = Field(foreign_key="projeto.id", index=True)
    nome: str
    situacao: str = DOC_PENDENTE          # "Recebido", "Pendente" ou "N/A" (não aplicável)
    padrao: bool = Field(default=False)   # veio da lista padrão (não pode ser excluído)
    ordem: int = 0
    observacao: str = ""                  # ex.: "recebido por e-mail, revisão R02"
    data_recebimento: Optional[datetime.date] = None  # quando o item foi recebido (editável)
    recebido_por: str = ""
    atualizado_por: str = ""
    data_atualizacao: datetime.datetime = Field(default_factory=_agora)


class DocumentoArquivo(SQLModel, table=True):
    """Arquivo recebido para um item dos documentos de referência, com a DATA EM QUE FOI
    RECEBIDO (informada por quem anexa; pode ser anterior ao envio para o app)."""
    id: Optional[int] = Field(default=None, primary_key=True)
    documento_id: int = Field(foreign_key="documentoreferencia.id", index=True)
    chave: str                            # caminho no armazenamento (uploads/p<id>/...)
    nome: str                             # nome do arquivo, para exibir
    data_recebimento: datetime.date
    enviado_por: str = ""
    data_envio: datetime.datetime = Field(default_factory=_agora)


# ---------------------------------------------------------------- auditoria (tabela nova)

class RegistroAuditoria(SQLModel, table=True):
    """Trilha de auditoria: quem fez o quê, em qual projeto e quando. Só recebe inserções.
    Tabela nova: create_all a cria em bancos existentes sem mexer nas outras."""
    id: Optional[int] = Field(default=None, primary_key=True)
    momento: datetime.datetime = Field(default_factory=_agora, index=True)
    organizacao_id: Optional[int] = Field(default=None, index=True)  # sem FK: o registro sobrevive
    usuario_id: Optional[int] = Field(default=None, index=True)
    usuario_nome: str = ""
    acao: str = Field(index=True)          # ex.: "decisao.criar", "ata.fechar", "projeto.excluir"
    projeto_id: Optional[int] = Field(default=None, index=True)
    alvo_tipo: Optional[str] = None        # "decisao", "reuniao", "pendencia"...
    alvo_id: Optional[int] = None
    detalhes: Optional[str] = None         # texto curto (ou JSON) para leitura humana


class UsoIA(SQLModel, table=True):
    """Transcrições de IA (rascunho de ata) geradas por organização em cada mês.
    Tabela nova: create_all/migração 0009 a criam sem mexer nas outras."""
    __tablename__ = "usoia"
    __table_args__ = (UniqueConstraint("organizacao_id", "ano_mes", name="uq_usoia_org_mes"),)
    id: Optional[int] = Field(default=None, primary_key=True)
    organizacao_id: int = Field(index=True)  # sem FK: o registro sobrevive
    ano_mes: str = Field(max_length=7)       # "AAAA-MM"
    quantidade: int = 0

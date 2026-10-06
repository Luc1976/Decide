import datetime
import hashlib
import hmac
import os
import re
import secrets
import unicodedata
from typing import Optional, List
from sqlmodel import Field, SQLModel, create_engine, Session, select

from config import DB_PATH
from ficha_calculos import analisar_alteracoes_ata, calcular_alteracoes
from models import (
    FICHA_GRUPOS,
    GRUPO_OUTRAS,
    NIVEL_ADMIN,
    NIVEL_PAPEL,
    PAPEIS,
    PadraoConstrutivo,
)

# --- MODELOS DE DADOS ---

class Usuario(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(unique=True)
    senha: str  
    nome_completo: str
    admin: bool = Field(default=False)
    pode_criar_projetos: bool = Field(default=True)  # False = cliente (só acompanha)

class MembroProjeto(SQLModel, table=True):
    """Quem tem acesso a cada projeto e com qual papel (Responsável, Editor ou Leitor)."""
    id: Optional[int] = Field(default=None, primary_key=True)
    projeto_id: int = Field(foreign_key="projeto.id")
    usuario_id: int = Field(foreign_key="usuario.id")
    papel: str = "Leitor"

class Projeto(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    nome: str
    cliente: str
    descricao: Optional[str] = None
    data_criacao: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )

class Caracteristica(SQLModel, table=True):
    """Um campo da ficha do empreendimento (ex.: 'Área do terreno' = '1.250,00')."""
    id: Optional[int] = Field(default=None, primary_key=True)
    projeto_id: int = Field(foreign_key="projeto.id")
    grupo: str
    nome: str
    valor: str = ""
    unidade: Optional[str] = None
    atualizado_por: str = ""
    data_atualizacao: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )

class CaracteristicaHistorico(SQLModel, table=True):
    """Cada alteração da ficha fica registrada: quem mudou, o quê e quando."""
    id: Optional[int] = Field(default=None, primary_key=True)
    projeto_id: int = Field(foreign_key="projeto.id")
    grupo: str
    nome: str
    valor_anterior: Optional[str] = None
    valor_novo: Optional[str] = None
    autor: str
    data_registro: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )
    decisao_id: Optional[int] = Field(default=None, foreign_key="decisao.id")  # decisão que motivou
    reuniao_id: Optional[int] = Field(default=None, foreign_key="reuniao.id")  # ata de origem

class Reuniao(SQLModel, table=True):
    """Ata de reunião. Depois de fechada, o texto não muda: correções entram como adendos."""
    id: Optional[int] = Field(default=None, primary_key=True)
    projeto_id: int = Field(foreign_key="projeto.id")
    numero: int                       # sequencial dentro do projeto (Ata 01, 02...)
    titulo: str
    data_reuniao: datetime.date = Field(default_factory=datetime.date.today)
    participantes: Optional[str] = None
    texto: str = ""
    status: str = "Rascunho"          # "Rascunho" ou "Fechada"
    autor: str = ""
    data_fechamento: Optional[datetime.datetime] = None

class AtaAdendo(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    reuniao_id: int = Field(foreign_key="reuniao.id")
    texto: str
    autor: str
    data_registro: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )

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

# --- CONFIGURAÇÃO DO BANCO ---

sqlite_file_name = str(DB_PATH)  # pasta definida por MEMORIA_DATA_DIR (ver config.py)
# check_same_thread=False + timeout: várias sessões (usuários) acessando o mesmo arquivo
engine = create_engine(
    f"sqlite:///{sqlite_file_name}",
    echo=False,
    connect_args={"check_same_thread": False, "timeout": 30},
)

# --- SENHAS (PBKDF2-SHA256 com sal; nunca guardamos a senha em texto puro) ---
# No Pyodide (Python no navegador) o hashlib NÃO tem pbkdf2_hmac (falta o OpenSSL),
# então usamos uma implementação em Python puro. O resultado é idêntico, por isso
# hashes gerados num ambiente são verificáveis no outro.

_ITERACOES_NATIVO = 200_000
_ITERACOES_PURO = 50_000  # Python puro em WebAssembly é lento; menos iterações


def _pbkdf2_puro(senha: bytes, sal: bytes, iteracoes: int) -> bytes:
    """PBKDF2-HMAC-SHA256, 1 bloco (32 bytes), só com hashlib.sha256."""
    if len(senha) > 64:
        senha = hashlib.sha256(senha).digest()
    senha = senha.ljust(64, b"\0")
    interno = hashlib.sha256(bytes(b ^ 0x36 for b in senha))
    externo = hashlib.sha256(bytes(b ^ 0x5C for b in senha))

    def prf(dados: bytes) -> bytes:
        i = interno.copy()
        i.update(dados)
        o = externo.copy()
        o.update(i.digest())
        return o.digest()

    u = prf(sal + b"\x00\x00\x00\x01")
    t = int.from_bytes(u, "big")
    for _ in range(iteracoes - 1):
        u = prf(u)
        t ^= int.from_bytes(u, "big")
    return t.to_bytes(32, "big")


def _pbkdf2(senha: str, sal: bytes, iteracoes: int) -> bytes:
    nativo = getattr(hashlib, "pbkdf2_hmac", None)
    if nativo is not None:
        return nativo("sha256", senha.encode(), sal, iteracoes)
    return _pbkdf2_puro(senha.encode(), sal, iteracoes)


def hash_senha(senha: str) -> str:
    iteracoes = (
        _ITERACOES_NATIVO if hasattr(hashlib, "pbkdf2_hmac") else _ITERACOES_PURO
    )
    sal = secrets.token_hex(16)
    h = _pbkdf2(senha, bytes.fromhex(sal), iteracoes)
    return f"pbkdf2${iteracoes}${sal}${h.hex()}"


def _senha_confere(senha: str, armazenada: str) -> bool:
    if not armazenada.startswith("pbkdf2$"):  # legado: texto puro
        return hmac.compare_digest(senha, armazenada)
    _, iteracoes, sal, esperado = armazenada.split("$")
    h = _pbkdf2(senha, bytes.fromhex(sal), int(iteracoes))
    return hmac.compare_digest(h.hex(), esperado)


def _migrar_banco():
    """create_all não altera tabelas já existentes: adiciona as colunas novas de
    'decisao' em bancos criados antes das atas e numera as decisões antigas."""
    with engine.begin() as conn:
        colunas = {c[1] for c in conn.exec_driver_sql("PRAGMA table_info(decisao)").fetchall()}
        if "reuniao_id" not in colunas:
            conn.exec_driver_sql("ALTER TABLE decisao ADD COLUMN reuniao_id INTEGER REFERENCES reuniao(id)")
        if "numero" not in colunas:
            conn.exec_driver_sql("ALTER TABLE decisao ADD COLUMN numero INTEGER")

    with engine.begin() as conn:
        colunas = {
            c[1]
            for c in conn.exec_driver_sql("PRAGMA table_info(caracteristicahistorico)").fetchall()
        }
        if "decisao_id" not in colunas:
            conn.exec_driver_sql(
                "ALTER TABLE caracteristicahistorico ADD COLUMN decisao_id INTEGER REFERENCES decisao(id)"
            )
        if "reuniao_id" not in colunas:
            conn.exec_driver_sql(
                "ALTER TABLE caracteristicahistorico ADD COLUMN reuniao_id INTEGER REFERENCES reuniao(id)"
            )

    with engine.begin() as conn:
        colunas = {c[1] for c in conn.exec_driver_sql("PRAGMA table_info(usuario)").fetchall()}
        if "pode_criar_projetos" not in colunas:
            conn.exec_driver_sql(
                "ALTER TABLE usuario ADD COLUMN pode_criar_projetos BOOLEAN NOT NULL DEFAULT 1"
            )
            # Banco de antes das permissões: todos viam todos os projetos. Para ninguém
            # perder acesso, cada usuário comum vira Editor dos projetos que já existem
            # (administradores já enxergam tudo). Roda uma única vez.
            conn.exec_driver_sql(
                "INSERT INTO membroprojeto (projeto_id, usuario_id, papel) "
                "SELECT p.id, u.id, 'Editor' FROM projeto p CROSS JOIN usuario u WHERE u.admin = 0"
            )

    with engine.begin() as conn:
        tabelas = {
            r[0]
            for r in conn.exec_driver_sql(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        if "padraoconstrutivo" in tabelas:
            colunas = {
                c[1]
                for c in conn.exec_driver_sql("PRAGMA table_info(padraoconstrutivo)").fetchall()
            }
            for nome, tipo in (
                ("shop_estrutura", "TEXT"),
                ("shop_cobertura", "TEXT"),
            ):
                if nome not in colunas:
                    conn.exec_driver_sql(
                        f"ALTER TABLE padraoconstrutivo ADD COLUMN {nome} {tipo}"
                    )

    with Session(engine) as session:
        sem_numero = session.exec(
            select(Decisao)
            .where(Decisao.numero == None)  # noqa: E711
            .order_by(Decisao.projeto_id, Decisao.data_decisao, Decisao.id)
        ).all()
        proximos: dict[int, int] = {}
        for dec in sem_numero:
            if dec.projeto_id not in proximos:
                proximos[dec.projeto_id] = _proximo_numero_decisao(session, dec.projeto_id)
            dec.numero = proximos[dec.projeto_id]
            proximos[dec.projeto_id] += 1
            session.add(dec)
        session.commit()


def _criar_admin_inicial(session: Session) -> None:
    """Só cria o administrador quando NÃO há nenhum usuário (banco novo).
    Usuário/senha vêm de MEMORIA_ADMIN_USUARIO / MEMORIA_ADMIN_SENHA. Sem a senha,
    gera uma aleatória e mostra uma única vez no log. Nunca há senha fixa."""
    if session.exec(select(Usuario)).first():
        return
    username = (os.getenv("MEMORIA_ADMIN_USUARIO") or "lucas").strip().lower()
    nome = (os.getenv("MEMORIA_ADMIN_NOME") or "Administrador").strip()
    senha = os.getenv("MEMORIA_ADMIN_SENHA") or ""
    gerada = len(senha) < 6
    if gerada:
        senha = secrets.token_urlsafe(9)
    session.add(Usuario(username=username, senha=hash_senha(senha), nome_completo=nome, admin=True))
    if gerada:
        print(
            f"[memoria] Usuário inicial criado: '{username}' com senha temporária '{senha}'. "
            "Anote e troque (python gerenciar.py trocar-senha).",
            flush=True,
        )


def usuarios_com_senha_padrao() -> List[str]:
    """Usuários que ainda usam a senha '123' de versões antigas (risco na web)."""
    with Session(engine) as session:
        return [
            u.username
            for u in session.exec(select(Usuario)).all()
            if _senha_confere("123", u.senha)
        ]


def alterar_senha(username: str, nova_senha: str) -> None:
    if len(nova_senha or "") < 6:
        raise ValueError("A senha deve ter pelo menos 6 caracteres.")
    with Session(engine) as session:
        usuario = session.exec(
            select(Usuario).where(Usuario.username == (username or "").strip().lower())
        ).first()
        if usuario is None:
            raise ValueError(f"Usuário '{username}' não encontrado.")
        usuario.senha = hash_senha(nova_senha)
        session.add(usuario)
        session.commit()


def listar_usernames() -> List[str]:
    with Session(engine) as session:
        return [u.username for u in session.exec(select(Usuario).order_by(Usuario.username)).all()]


def aplicar_reset_de_senha_do_ambiente() -> None:
    """Recuperação de acesso sem terminal: MEMORIA_RESETAR_SENHA=usuario:nova_senha redefine
    a senha na partida do servidor. REMOVA a variável depois: enquanto existir, a senha
    volta a esse valor a cada reinício."""
    valor = os.getenv("MEMORIA_RESETAR_SENHA") or ""
    if not valor:
        return
    usuario, _, nova = valor.partition(":")
    usuario = usuario.strip().lower()
    try:
        alterar_senha(usuario, nova)
    except ValueError as erro:
        print(
            f"[memoria] Não foi possível redefinir a senha: {erro} "
            f"Usuários existentes: {', '.join(listar_usernames()) or '(nenhum)'}",
            flush=True,
        )
        return
    print(
        f"[memoria] Senha de '{usuario}' redefinida. REMOVA a variável MEMORIA_RESETAR_SENHA agora.",
        flush=True,
    )


def init_db():
    SQLModel.metadata.create_all(engine)
    _migrar_banco()
    
    with Session(engine) as session:
        _criar_admin_inicial(session)
        
        # Cria projeto padrão se não existir
        if not session.exec(select(Projeto)).first():
            proj = Projeto(nome="Sede Corporativa Ru.A", cliente="Cliente Modelo")
            session.add(proj)
            
        session.commit()

# --- FUNÇÕES CRUD ---

def _normalizar(texto: str) -> str:
    """Minúsculas e sem acentos: 'Orçamento' casa com 'orcamento'."""
    sem_acento = unicodedata.normalize("NFKD", texto or "")
    return "".join(c for c in sem_acento if not unicodedata.combining(c)).casefold().strip()


def autenticar_usuario(username: str, senha: str) -> Optional[Usuario]:
    with Session(engine) as session:
        usuario = session.exec(
            select(Usuario).where(Usuario.username == (username or "").strip().lower())
        ).first()
        if not usuario or not _senha_confere(senha or "", usuario.senha):
            return None
        if not usuario.senha.startswith("pbkdf2$"):  # migra senha legada para hash
            usuario.senha = hash_senha(senha)
            session.add(usuario)
            session.commit()
            session.refresh(usuario)
        session.expunge(usuario)
        return usuario


def criar_usuario(username: str, senha: str, nome_completo: str, admin: bool = False, pode_criar_projetos: bool = True) -> Usuario:
    username = (username or "").strip().lower()
    nome_completo = (nome_completo or "").strip()
    if not username or not nome_completo:
        raise ValueError("Preencha o nome completo e o usuário.")
    if " " in username:
        raise ValueError("O usuário não pode conter espaços.")
    if len(senha or "") < 6:
        raise ValueError("A senha deve ter pelo menos 6 caracteres.")
    with Session(engine) as session:
        if session.exec(select(Usuario).where(Usuario.username == username)).first():
            raise ValueError(f"O usuário '{username}' já existe.")
        usuario = Usuario(
            username=username,
            senha=hash_senha(senha),
            nome_completo=nome_completo,
            admin=admin,
            pode_criar_projetos=pode_criar_projetos or admin,
        )
        session.add(usuario)
        session.commit()
        session.refresh(usuario)
        session.expunge(usuario)
        return usuario


def listar_usuarios() -> List[Usuario]:
    with Session(engine) as session:
        return session.exec(select(Usuario).order_by(Usuario.nome_completo)).all()


def atualizar_projeto(projeto_id: int, nome: str, cliente: str, descricao: Optional[str] = None, usuario_id: Optional[int] = None) -> Projeto:
    nome = (nome or "").strip()
    cliente = (cliente or "").strip()
    if not nome or not cliente:
        raise ValueError("Preencha o nome do projeto e o cliente.")
    with Session(engine) as session:
        _exigir(session, usuario_id, projeto_id, "Responsável")
        projeto = session.get(Projeto, projeto_id)
        if projeto is None:
            raise ValueError("Projeto não encontrado.")
        projeto.nome = nome
        projeto.cliente = cliente
        projeto.descricao = (descricao or "").strip() or None
        session.add(projeto)
        session.commit()
        session.refresh(projeto)
        return Projeto(
            id=projeto.id,
            nome=projeto.nome,
            cliente=projeto.cliente,
            descricao=projeto.descricao,
            data_criacao=projeto.data_criacao,
        )


def listar_projetos() -> List[Projeto]:
    with Session(engine) as session:
        return session.exec(select(Projeto)).all()
        
def buscar_decisoes_projeto(projeto_id: int, termo: str = "") -> list[Decisao]:
    """Filtra as decisões do projeto por título, descrição, categoria,
    justificativa, impacto, autor ou nome dos anexos (sem diferenciar
    maiúsculas/minúsculas nem acentos)."""
    decisoes = listar_decisoes_projeto(projeto_id)
    termo_busca = _normalizar(termo)
    if not termo_busca:
        return decisoes

    campos_busca = (
        "titulo",
        "categoria",
        "descricao",
        "justificativa",
        "alternativa_descartada",
        "impacto",
        "autor",
    )

    def texto_decisao(decisao: Decisao) -> str:
        partes = [getattr(decisao, campo) or "" for campo in campos_busca]
        if decisao.anexos:
            partes.extend(os.path.basename(c) for c in decisao.anexos.split(","))
        return _normalizar(" ".join(partes))

    return [d for d in decisoes if termo_busca in texto_decisao(d)]


def criar_projeto(nome: str, cliente: str, descricao: Optional[str] = None, criador_id: Optional[int] = None) -> Projeto:
    """Cria o projeto; quem cria vira Responsável por ele (admin já enxerga tudo)."""
    if not (nome or "").strip() or not (cliente or "").strip():
        raise ValueError("Preencha o nome do projeto e o cliente.")
    projeto = Projeto(
        nome=nome.strip(),
        cliente=cliente.strip(),
        descricao=(descricao or "").strip() or None,
    )
    with Session(engine) as session:
        criador = session.get(Usuario, criador_id) if criador_id is not None else None
        if criador is None or not (criador.admin or criador.pode_criar_projetos):
            raise PermissionError("Seu usuário não pode criar projetos.")
        session.add(projeto)
        session.flush()  # gera o id
        if not criador.admin:
            session.add(MembroProjeto(projeto_id=projeto.id, usuario_id=criador.id, papel="Responsável"))
        session.commit()
        session.refresh(projeto)
        return Projeto(
            id=projeto.id,
            nome=projeto.nome,
            cliente=projeto.cliente,
            descricao=projeto.descricao,
            data_criacao=projeto.data_criacao,
        )

def _proximo_numero_decisao(session: Session, projeto_id: int) -> int:
    ultimo = session.exec(
        select(Decisao.numero)
        .where(Decisao.projeto_id == projeto_id, Decisao.numero != None)  # noqa: E711
        .order_by(Decisao.numero.desc())
    ).first()
    return (ultimo or 0) + 1


def adicionar_decisao(projeto_id, titulo, categoria, descricao, justificativa, alternativa_descartada, impacto, autor, anexos, checklist, alteracao_ficha=None, usuario_id=None):
    """Registra a decisão. 'alteracao_ficha' (opcional) é (grupo, nome, unidade, novo_valor):
    a ficha é atualizada na mesma transação, ligada a esta decisão."""
    with Session(engine) as session:
        _exigir(session, usuario_id, projeto_id, "Editor")
        dec = Decisao(
            projeto_id=projeto_id, titulo=titulo, categoria=categoria, descricao=descricao,
            justificativa=justificativa, alternativa_descartada=alternativa_descartada, 
            impacto=impacto, autor=autor, anexos=anexos, checklist=checklist,
            numero=_proximo_numero_decisao(session, projeto_id),
        )
        session.add(dec)
        if alteracao_ficha:
            session.flush()  # gera o id da decisão
            _aplicar_ficha(session, projeto_id, [alteracao_ficha], autor, decisao_id=dec.id)
        session.commit()

def listar_decisoes_projeto(projeto_id: int) -> List[Decisao]:
    with Session(engine) as session:
        return session.exec(select(Decisao).where(Decisao.projeto_id == projeto_id).order_by(Decisao.data_decisao.desc())).all()


# --- ATAS DE REUNIÃO ---

_PADRAO_DECISAO = re.compile(r"^\s*\[D\]\s*(.+?)\s*$", re.IGNORECASE)


def extrair_decisoes(texto: str) -> List[str]:
    """Linhas da ata que começam com [D] (sem diferenciar maiúsculas/minúsculas)."""
    encontradas = []
    for linha in (texto or "").splitlines():
        m = _PADRAO_DECISAO.match(linha)
        if m:
            encontradas.append(m.group(1))
    return encontradas


def _titulo_da_linha(linha: str, limite: int = 70) -> str:
    if len(linha) <= limite:
        return linha
    return linha[: limite - 1].rstrip() + "…"


def _copia_reuniao(session: Session, reuniao: Reuniao) -> Reuniao:
    session.refresh(reuniao)
    session.expunge(reuniao)
    return reuniao


def criar_reuniao(
    projeto_id: int,
    titulo: str,
    data_reuniao: datetime.date,
    participantes: str,
    texto: str,
    autor: str,
    usuario_id: Optional[int] = None,
) -> Reuniao:
    titulo = (titulo or "").strip()
    if not titulo:
        raise ValueError("Informe o título da reunião.")
    with Session(engine) as session:
        _exigir(session, usuario_id, projeto_id, "Editor")
        ultimo = session.exec(
            select(Reuniao.numero)
            .where(Reuniao.projeto_id == projeto_id)
            .order_by(Reuniao.numero.desc())
        ).first()
        reuniao = Reuniao(
            projeto_id=projeto_id,
            numero=(ultimo or 0) + 1,
            titulo=titulo,
            data_reuniao=data_reuniao,
            participantes=(participantes or "").strip() or None,
            texto=texto or "",
            autor=autor,
        )
        session.add(reuniao)
        session.commit()
        return _copia_reuniao(session, reuniao)


def atualizar_reuniao_rascunho(
    reuniao_id: int,
    titulo: str,
    data_reuniao: datetime.date,
    participantes: str,
    texto: str,
    usuario_id: Optional[int] = None,
) -> Reuniao:
    titulo = (titulo or "").strip()
    if not titulo:
        raise ValueError("Informe o título da reunião.")
    with Session(engine) as session:
        reuniao = session.get(Reuniao, reuniao_id)
        if reuniao is None:
            raise ValueError("Ata não encontrada.")
        _exigir(session, usuario_id, reuniao.projeto_id, "Editor")
        if reuniao.status != "Rascunho":
            raise ValueError("Esta ata já foi fechada. Registre um adendo.")
        reuniao.titulo = titulo
        reuniao.data_reuniao = data_reuniao
        reuniao.participantes = (participantes or "").strip() or None
        reuniao.texto = texto or ""
        session.add(reuniao)
        session.commit()
        return _copia_reuniao(session, reuniao)


def fechar_reuniao(reuniao_id: int, autor: str, usuario_id: Optional[int] = None) -> List[Decisao]:
    """Fecha a ata e cria uma decisão para cada linha [D], tudo na mesma transação."""
    with Session(engine) as session:
        reuniao = session.get(Reuniao, reuniao_id)
        if reuniao is None:
            raise ValueError("Ata não encontrada.")
        _exigir(session, usuario_id, reuniao.projeto_id, "Editor")
        if reuniao.status != "Rascunho":
            raise ValueError("Esta ata já está fechada.")

        # Valida as linhas [F] ANTES de criar qualquer coisa: se houver erro, nada é gravado.
        alteracoes_ficha, erros = analisar_alteracoes_ata(
            reuniao.texto, _campos_ficha(session, reuniao.projeto_id)
        )
        if erros:
            raise ValueError("Corrija as linhas [F]: " + "; ".join(erros) + ".")

        numero = _proximo_numero_decisao(session, reuniao.projeto_id)
        criadas = []
        for linha in extrair_decisoes(reuniao.texto):
            dec = Decisao(
                projeto_id=reuniao.projeto_id,
                titulo=_titulo_da_linha(linha),
                categoria="Geral",
                descricao=linha,
                justificativa=f"Registrada na Ata {reuniao.numero:02d} - {reuniao.titulo}",
                impacto="Médio",
                autor=autor,
                data_decisao=reuniao.data_reuniao,
                reuniao_id=reuniao.id,
                numero=numero,
            )
            numero += 1
            session.add(dec)
            criadas.append(dec)

        session.flush()  # gera os ids das decisões
        for indice, grupo, nome, unidade, valor in alteracoes_ficha:
            decisao = criadas[indice] if indice is not None else None
            _aplicar_ficha(
                session,
                reuniao.projeto_id,
                [(grupo, nome, unidade, valor)],
                autor,
                decisao_id=decisao.id if decisao is not None else None,
                reuniao_id=reuniao.id,
            )

        reuniao.status = "Fechada"
        reuniao.data_fechamento = datetime.datetime.now(datetime.timezone.utc)
        session.add(reuniao)
        session.commit()
        for dec in criadas:
            session.refresh(dec)
            session.expunge(dec)
        return criadas


def buscar_reuniao(reuniao_id: int) -> Optional[Reuniao]:
    with Session(engine) as session:
        reuniao = session.get(Reuniao, reuniao_id)
        if reuniao is not None:
            session.expunge(reuniao)
        return reuniao


def listar_reunioes_projeto(projeto_id: int) -> List[Reuniao]:
    with Session(engine) as session:
        return session.exec(
            select(Reuniao)
            .where(Reuniao.projeto_id == projeto_id)
            .order_by(Reuniao.data_reuniao.desc(), Reuniao.numero.desc())
        ).all()


def buscar_reunioes_projeto(projeto_id: int, termo: str = "") -> List[Reuniao]:
    """Filtra as atas por título, participantes, autor ou texto (sem acentos)."""
    reunioes = listar_reunioes_projeto(projeto_id)
    termo_busca = _normalizar(termo)
    if not termo_busca:
        return reunioes
    return [
        r
        for r in reunioes
        if termo_busca
        in _normalizar(" ".join([r.titulo, r.participantes or "", r.autor, r.texto]))
    ]


def listar_decisoes_reuniao(reuniao_id: int) -> List[Decisao]:
    with Session(engine) as session:
        return session.exec(
            select(Decisao).where(Decisao.reuniao_id == reuniao_id).order_by(Decisao.numero)
        ).all()


def adicionar_adendo(reuniao_id: int, texto: str, autor: str, usuario_id: Optional[int] = None) -> AtaAdendo:
    texto = (texto or "").strip()
    if not texto:
        raise ValueError("Escreva o texto do adendo.")
    with Session(engine) as session:
        reuniao = session.get(Reuniao, reuniao_id)
        if reuniao is None:
            raise ValueError("Ata não encontrada.")
        _exigir(session, usuario_id, reuniao.projeto_id, "Editor")
        if reuniao.status != "Fechada":
            raise ValueError("Adendos só podem ser registrados em atas fechadas.")
        adendo = AtaAdendo(reuniao_id=reuniao_id, texto=texto, autor=autor)
        session.add(adendo)
        session.commit()
        session.refresh(adendo)
        session.expunge(adendo)
        return adendo


def listar_adendos(reuniao_id: int) -> List[AtaAdendo]:
    with Session(engine) as session:
        return session.exec(
            select(AtaAdendo)
            .where(AtaAdendo.reuniao_id == reuniao_id)
            .order_by(AtaAdendo.data_registro)
        ).all()


# --- PERMISSÕES POR PROJETO ---

def _nivel(session: Session, usuario_id: Optional[int], projeto_id: int) -> int:
    """0 = sem acesso, 1 = Leitor, 2 = Editor, 3 = Responsável, 4 = administrador."""
    if usuario_id is None:
        return 0
    usuario = session.get(Usuario, usuario_id)
    if usuario is None or session.get(Projeto, projeto_id) is None:
        return 0
    if usuario.admin:
        return NIVEL_ADMIN
    membro = session.exec(
        select(MembroProjeto).where(
            MembroProjeto.projeto_id == projeto_id, MembroProjeto.usuario_id == usuario_id
        )
    ).first()
    return NIVEL_PAPEL.get(membro.papel, 0) if membro else 0


def _exigir(session: Session, usuario_id: Optional[int], projeto_id: int, minimo: str) -> None:
    """Barra a gravação se o usuário não tem o papel mínimo (vale mesmo que a tela falhe)."""
    if _nivel(session, usuario_id, projeto_id) < NIVEL_PAPEL[minimo]:
        raise PermissionError("Você não tem permissão para esta ação neste projeto.")


def nivel_no_projeto(usuario_id: int, projeto_id: int) -> int:
    with Session(engine) as session:
        return _nivel(session, usuario_id, projeto_id)


def pode_no_projeto(usuario_id: int, projeto_id: int, minimo: str = "Leitor") -> bool:
    return nivel_no_projeto(usuario_id, projeto_id) >= NIVEL_PAPEL[minimo]


def listar_projetos_do_usuario(usuario_id: int) -> List[Projeto]:
    """Só os projetos que o usuário pode ver (administrador vê todos)."""
    with Session(engine) as session:
        usuario = session.get(Usuario, usuario_id)
        if usuario is None:
            return []
        if usuario.admin:
            return session.exec(select(Projeto).order_by(Projeto.nome)).all()
        ids = session.exec(
            select(MembroProjeto.projeto_id).where(MembroProjeto.usuario_id == usuario_id)
        ).all()
        if not ids:
            return []
        return session.exec(select(Projeto).where(Projeto.id.in_(ids)).order_by(Projeto.nome)).all()


def listar_membros(projeto_id: int, solicitante_id: int) -> list:
    """[(Usuario, papel)]. Só o Responsável (ou admin) vê a lista de membros."""
    with Session(engine) as session:
        _exigir(session, solicitante_id, projeto_id, "Responsável")
        membros = session.exec(
            select(MembroProjeto).where(MembroProjeto.projeto_id == projeto_id)
        ).all()
        resultado = []
        for m in membros:
            u = session.get(Usuario, m.usuario_id)
            if u is not None:
                session.expunge(u)
                resultado.append((u, m.papel))
        resultado.sort(key=lambda par: (-NIVEL_PAPEL.get(par[1], 0), par[0].nome_completo.lower()))
        return resultado


def _exigir_ao_menos_um_responsavel(session: Session, projeto_id: int, alvo_id: int, novo_papel: Optional[str]) -> None:
    atual = session.exec(
        select(MembroProjeto).where(
            MembroProjeto.projeto_id == projeto_id, MembroProjeto.usuario_id == alvo_id
        )
    ).first()
    if atual is None or atual.papel != "Responsável" or novo_papel == "Responsável":
        return
    outros = session.exec(
        select(MembroProjeto).where(
            MembroProjeto.projeto_id == projeto_id,
            MembroProjeto.papel == "Responsável",
            MembroProjeto.usuario_id != alvo_id,
        )
    ).all()
    if not outros:
        raise ValueError("O projeto precisa ter ao menos um Responsável.")


def definir_membro(projeto_id: int, username: str, papel: str, por_usuario_id: int) -> None:
    """Adiciona o usuário ao projeto ou muda o papel dele. Quem executa precisa ser Responsável."""
    if papel not in PAPEIS:
        raise ValueError("Escolha o tipo de acesso.")
    with Session(engine) as session:
        _exigir(session, por_usuario_id, projeto_id, "Responsável")
        alvo = session.exec(
            select(Usuario).where(Usuario.username == (username or "").strip().lower())
        ).first()
        if alvo is None:
            raise ValueError(
                "Usuário não encontrado. O cadastro de novos usuários é feito pelo administrador."
            )
        if alvo.admin:
            raise ValueError("Administradores já têm acesso a todos os projetos.")
        _exigir_ao_menos_um_responsavel(session, projeto_id, alvo.id, papel)
        membro = session.exec(
            select(MembroProjeto).where(
                MembroProjeto.projeto_id == projeto_id, MembroProjeto.usuario_id == alvo.id
            )
        ).first()
        if membro is None:
            session.add(MembroProjeto(projeto_id=projeto_id, usuario_id=alvo.id, papel=papel))
        else:
            membro.papel = papel
            session.add(membro)
        session.commit()


def remover_membro(projeto_id: int, usuario_id_alvo: int, por_usuario_id: int) -> None:
    with Session(engine) as session:
        _exigir(session, por_usuario_id, projeto_id, "Responsável")
        _exigir_ao_menos_um_responsavel(session, projeto_id, usuario_id_alvo, None)
        membro = session.exec(
            select(MembroProjeto).where(
                MembroProjeto.projeto_id == projeto_id, MembroProjeto.usuario_id == usuario_id_alvo
            )
        ).first()
        if membro is not None:
            session.delete(membro)
            session.commit()


def resumo_projeto(projeto_id: int, usuario_id: int) -> dict:
    """Quantidades que seriam apagadas junto com o projeto (para a tela de confirmação)."""
    with Session(engine) as session:
        _exigir(session, usuario_id, projeto_id, "Responsável")
        decisoes = session.exec(select(Decisao).where(Decisao.projeto_id == projeto_id)).all()
        atas = session.exec(select(Reuniao).where(Reuniao.projeto_id == projeto_id)).all()
        membros = session.exec(select(MembroProjeto).where(MembroProjeto.projeto_id == projeto_id)).all()
        anexos = sum(len([c for c in (d.anexos or "").split(",") if c]) for d in decisoes)
        return {"decisoes": len(decisoes), "atas": len(atas), "anexos": anexos, "membros": len(membros)}


def excluir_projeto(projeto_id: int, usuario_id: int) -> list:
    """Apaga o projeto e TUDO que pertence a ele, numa única transação (ou nada é apagado).
    Só o Responsável do projeto ou um administrador. Devolve os caminhos dos anexos, para o
    chamador apagar os arquivos do disco depois que o banco confirmar."""
    with Session(engine) as session:
        _exigir(session, usuario_id, projeto_id, "Responsável")
        projeto = session.get(Projeto, projeto_id)
        if projeto is None:
            raise ValueError("Projeto não encontrado.")
        executor = session.get(Usuario, usuario_id)
        nome_projeto = projeto.nome

        decisoes = session.exec(select(Decisao).where(Decisao.projeto_id == projeto_id)).all()
        reunioes = session.exec(select(Reuniao).where(Reuniao.projeto_id == projeto_id)).all()
        caminhos = [c for d in decisoes for c in (d.anexos or "").split(",") if c]

        # A ordem importa por causa das chaves estrangeiras: primeiro quem aponta para
        # decisões/atas, depois as decisões, depois as atas e por fim o próprio projeto.
        historico = session.exec(
            select(CaracteristicaHistorico).where(CaracteristicaHistorico.projeto_id == projeto_id)
        ).all()
        caracteristicas = session.exec(
            select(Caracteristica).where(Caracteristica.projeto_id == projeto_id)
        ).all()
        padroes = session.exec(
            select(PadraoConstrutivo).where(PadraoConstrutivo.projeto_id == projeto_id)
        ).all()
        for item in [*historico, *caracteristicas, *padroes]:
            session.delete(item)
        session.flush()
        for reuniao in reunioes:
            for adendo in session.exec(select(AtaAdendo).where(AtaAdendo.reuniao_id == reuniao.id)).all():
                session.delete(adendo)
        session.flush()
        for decisao in decisoes:
            session.delete(decisao)
        session.flush()
        for reuniao in reunioes:
            session.delete(reuniao)
        session.flush()
        for membro in session.exec(select(MembroProjeto).where(MembroProjeto.projeto_id == projeto_id)).all():
            session.delete(membro)
        session.flush()
        session.delete(projeto)
        session.commit()
        print(
            f"[memoria] Projeto '{nome_projeto}' (id {projeto_id}) excluído por "
            f"'{executor.username if executor else usuario_id}'.",
            flush=True,
        )
        return caminhos


def anexo_pertence_ao_projeto(projeto_id: int, caminho: str) -> bool:
    """O anexo está numa decisão deste projeto? (evita abrir arquivo de outro projeto)"""
    with Session(engine) as session:
        decisoes = session.exec(
            select(Decisao).where(Decisao.projeto_id == projeto_id, Decisao.anexos != None)  # noqa: E711
        ).all()
        return any(caminho in (d.anexos or "").split(",") for d in decisoes)


def alterar_propria_senha(usuario_id: int, senha_atual: str, nova_senha: str) -> None:
    if len(nova_senha or "") < 6:
        raise ValueError("A nova senha deve ter pelo menos 6 caracteres.")
    with Session(engine) as session:
        usuario = session.get(Usuario, usuario_id)
        if usuario is None or not _senha_confere(senha_atual or "", usuario.senha):
            raise ValueError("A senha atual está incorreta.")
        usuario.senha = hash_senha(nova_senha)
        session.add(usuario)
        session.commit()


# --- FICHA DE CARACTERÍSTICAS DO EMPREENDIMENTO ---

def listar_caracteristicas(projeto_id: int) -> List[Caracteristica]:
    with Session(engine) as session:
        return session.exec(
            select(Caracteristica).where(Caracteristica.projeto_id == projeto_id)
        ).all()


def _campos_ficha(session: Session, projeto_id: int) -> list:
    """Todos os campos da ficha do projeto: [(grupo, nome, unidade)].
    Modelo (models.FICHA_GRUPOS) + campos personalizados já salvos."""
    campos = [
        (grupo, nome, unidade)
        for grupo, itens in FICHA_GRUPOS.items()
        for nome, unidade in itens
    ]
    conhecidos = {(g, n) for g, n, _ in campos}
    salvos = session.exec(
        select(Caracteristica).where(Caracteristica.projeto_id == projeto_id)
    ).all()
    for c in salvos:
        if (c.grupo, c.nome) not in conhecidos:
            campos.append((c.grupo, c.nome, c.unidade or ""))
    return campos


def campos_da_ficha(projeto_id: int) -> list:
    with Session(engine) as session:
        return _campos_ficha(session, projeto_id)


def _aplicar_ficha(
    session: Session,
    projeto_id: int,
    itens: list,
    autor: str,
    decisao_id: Optional[int] = None,
    reuniao_id: Optional[int] = None,
) -> int:
    """Aplica na sessão (sem commit) as mudanças da ficha e registra o histórico.
    'itens' é [(grupo, nome, unidade, valor)]. Só o que mudou é gravado.
    Campo personalizado esvaziado é removido. Devolve quantos campos mudaram."""
    salvos = session.exec(
        select(Caracteristica).where(Caracteristica.projeto_id == projeto_id)
    ).all()
    por_chave = {(c.grupo, c.nome): c for c in salvos}
    mudancas = calcular_alteracoes(
        {chave: c.valor for chave, c in por_chave.items()}, itens
    )
    agora = datetime.datetime.now(datetime.timezone.utc)
    for grupo, nome, unidade, anterior, novo in mudancas:
        existente = por_chave.get((grupo, nome))
        if existente is None:
            session.add(
                Caracteristica(
                    projeto_id=projeto_id,
                    grupo=grupo,
                    nome=nome,
                    valor=novo or "",
                    unidade=unidade or None,
                    atualizado_por=autor,
                    data_atualizacao=agora,
                )
            )
        elif novo is None and grupo == GRUPO_OUTRAS:
            session.delete(existente)
        else:
            existente.valor = novo or ""
            existente.atualizado_por = autor
            existente.data_atualizacao = agora
            session.add(existente)
        session.add(
            CaracteristicaHistorico(
                projeto_id=projeto_id,
                grupo=grupo,
                nome=nome,
                valor_anterior=anterior,
                valor_novo=novo,
                autor=autor,
                data_registro=agora,
                decisao_id=decisao_id,
                reuniao_id=reuniao_id,
            )
        )
    return len(mudancas)


def salvar_caracteristicas(
    projeto_id: int,
    itens: list,
    autor: str,
    decisao_id: Optional[int] = None,
    reuniao_id: Optional[int] = None,
    usuario_id: Optional[int] = None,
) -> int:
    """Grava a ficha (edição direta na tela da ficha). Devolve quantos campos mudaram."""
    with Session(engine) as session:
        _exigir(session, usuario_id, projeto_id, "Editor")
        qtd = _aplicar_ficha(session, projeto_id, itens, autor, decisao_id, reuniao_id)
        session.commit()
        return qtd


def listar_historico_ficha(projeto_id: int, limite: int = 200) -> List[CaracteristicaHistorico]:
    with Session(engine) as session:
        return session.exec(
            select(CaracteristicaHistorico)
            .where(CaracteristicaHistorico.projeto_id == projeto_id)
            .order_by(CaracteristicaHistorico.data_registro.desc(), CaracteristicaHistorico.id.desc())
            .limit(limite)
        ).all()


def mapa_origens_ficha(projeto_id: int) -> dict:
    """{id do registro do histórico: 'Decisão D-005 · Ata 04'} só para quem tem origem."""
    with Session(engine) as session:
        registros = session.exec(
            select(CaracteristicaHistorico).where(
                CaracteristicaHistorico.projeto_id == projeto_id
            )
        ).all()
        origens = {}
        for r in registros:
            partes = []
            if r.decisao_id:
                dec = session.get(Decisao, r.decisao_id)
                if dec is not None and dec.numero:
                    partes.append(f"Decisão D-{dec.numero:03d}")
            if r.reuniao_id:
                ata = session.get(Reuniao, r.reuniao_id)
                if ata is not None:
                    partes.append(f"Ata {ata.numero:02d}")
            if partes:
                origens[r.id] = " · ".join(partes)
        return origens


def alteracoes_ficha_por_decisao(projeto_id: int) -> dict:
    """{decisao_id: [CaracteristicaHistorico, ...]} das decisões que mexeram na ficha."""
    with Session(engine) as session:
        registros = session.exec(
            select(CaracteristicaHistorico)
            .where(
                CaracteristicaHistorico.projeto_id == projeto_id,
                CaracteristicaHistorico.decisao_id != None,  # noqa: E711
            )
            .order_by(CaracteristicaHistorico.id)
        ).all()
        por_decisao: dict = {}
        for r in registros:
            por_decisao.setdefault(r.decisao_id, []).append(r)
        return por_decisao


def obter_padrao_construtivo(projeto_id: int) -> Optional[PadraoConstrutivo]:
    with Session(engine) as session:
        padrao = session.exec(
            select(PadraoConstrutivo).where(PadraoConstrutivo.projeto_id == projeto_id)
        ).first()
        if padrao is not None:
            session.expunge(padrao)
        return padrao


_CAMPOS_PADRAO = (
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


def salvar_padrao_construtivo(
    projeto_id: int, dados: dict, usuario_id: Optional[int] = None
) -> PadraoConstrutivo:
    """Grava (ou atualiza) o padrão construtivo do projeto. Um registro por projeto."""
    with Session(engine) as session:
        _exigir(session, usuario_id, projeto_id, "Editor")
        padrao = session.exec(
            select(PadraoConstrutivo).where(PadraoConstrutivo.projeto_id == projeto_id)
        ).first()
        if padrao is None:
            padrao = PadraoConstrutivo(projeto_id=projeto_id, tipologia="")
        for campo in _CAMPOS_PADRAO:
            if campo == "tipologia":
                continue
            setattr(padrao, campo, None)
        for campo in _CAMPOS_PADRAO:
            if campo in dados:
                setattr(padrao, campo, dados[campo])
        session.add(padrao)
        session.commit()
        session.refresh(padrao)
        session.expunge(padrao)
        return padrao


def listar_alteracoes_ficha_ata(reuniao_id: int) -> List[CaracteristicaHistorico]:
    with Session(engine) as session:
        return session.exec(
            select(CaracteristicaHistorico)
            .where(CaracteristicaHistorico.reuniao_id == reuniao_id)
            .order_by(CaracteristicaHistorico.id)
        ).all()

"""Acesso a dados do app Flet (camada de compatibilidade).

As regras de negócio agora moram em nucleo/servicos/ e são as MESMAS usadas pela API
(pasta api/). Este módulo mantém as funções que as telas Flet já chamam, com os mesmos
nomes e parâmetros, abrindo a sessão e delegando para os serviços.

Quando o app Flet for desligado, este arquivo pode ser apagado.
"""
import datetime
import json
import os
import secrets
from typing import List, Optional

from sqlmodel import Session, select

from nucleo.ator import Ator
from nucleo.db import engine, nova_sessao
from nucleo.marcacoes import extrair_decisoes, extrair_pendencias  # noqa: F401  (reexportadas)
from nucleo.marcacoes import normalizar as _normalizar  # noqa: F401
from nucleo.permissoes import nivel as _nivel_sessao
from nucleo.senhas import hash_senha, senha_confere as _senha_confere  # noqa: F401
from nucleo.servicos import atas as s_atas
from nucleo.servicos import decisoes as s_decisoes
from nucleo.servicos import organizacoes as s_organizacoes
from nucleo.servicos import ficha as s_ficha
from nucleo.servicos import pendencias as s_pendencias
from nucleo.servicos import projetos as s_projetos
from nucleo.servicos import usuarios as s_usuarios
from nucleo.servicos.decisoes import DadosDecisao
from nucleo.tabelas import (  # noqa: F401  (reexportadas para as telas e scripts)
    PENDENCIA_ABERTA,
    PENDENCIA_CANCELADA,
    PENDENCIA_RESOLVIDA,
    SITUACOES_PENDENCIA,
    AtaAdendo,
    Caracteristica,
    CaracteristicaHistorico,
    Decisao,
    MembroProjeto,
    Organizacao,
    PadraoConstrutivo,
    Pendencia,
    Projeto,
    RegistroAuditoria,
    Reuniao,
    Usuario,
)
from models import GRUPO_OUTRAS, NIVEL_PAPEL  # noqa: F401

sqlite_file_name = str(engine.url.database or "")


def _ator(s: Session, usuario_id: Optional[int], autor: Optional[str] = None) -> Ator:
    """As telas passam 'usuario_id' e o nome em 'autor'; os serviços querem um Ator."""
    return s_usuarios.ator_por_id(s, usuario_id, autor)


# ---------------------------------------------------------------- banco: criação e migração

def _numerar_decisoes_antigas() -> None:
    """Decisões de antes da numeração D-xxx recebem número (só age se houver alguma)."""
    with Session(engine) as session:
        from nucleo.numeracao import proxima_decisao

        sem_numero = session.exec(
            select(Decisao).where(Decisao.numero == None)  # noqa: E711
            .order_by(Decisao.projeto_id, Decisao.data_decisao, Decisao.id)
        ).all()
        proximos: dict = {}
        for dec in sem_numero:
            if dec.projeto_id not in proximos:
                proximos[dec.projeto_id] = proxima_decisao(session, dec.projeto_id)
            dec.numero = proximos[dec.projeto_id]
            proximos[dec.projeto_id] += 1
            session.add(dec)
        session.commit()


def _criar_primeira_organizacao(session: Session) -> None:
    """Banco novo (nenhum usuário): cria a organização inicial e o administrador dela,
    que também é o superadmin (dono da plataforma). Nunca há senha fixa:
    MEMORIA_ADMIN_USUARIO / MEMORIA_ADMIN_SENHA, ou uma senha aleatória mostrada no log."""
    if session.exec(select(Usuario)).first():
        return
    from nucleo.servicos.organizacoes import nova_organizacao

    org = session.exec(select(Organizacao)).first() or nova_organizacao(
        session, (os.getenv("DECIDIU_ORG_INICIAL") or "Organização principal").strip() or "Organização principal"
    )
    username = (os.getenv("MEMORIA_ADMIN_USUARIO") or "lucas").strip().lower()
    nome = (os.getenv("MEMORIA_ADMIN_NOME") or "Administrador").strip()
    senha = os.getenv("MEMORIA_ADMIN_SENHA") or ""
    gerada = len(senha) < 6
    if gerada:
        senha = secrets.token_urlsafe(9)
    session.add(Usuario(username=username, senha=hash_senha(senha), nome_completo=nome, admin=True,
                        organizacao_id=org.id, superadmin=True))
    if not session.exec(select(Projeto)).first():  # projeto de exemplo
        session.add(Projeto(nome="Sede Corporativa Ru.A", cliente="Cliente Modelo", organizacao_id=org.id))
    if gerada:
        print(
            f"[memoria] Usuário inicial criado: '{username}' com senha temporária '{senha}'. "
            "Anote e troque (python gerenciar.py trocar-senha).",
            flush=True,
        )


def init_db():
    """Leva o banco à versão mais nova (Alembic) e prepara o primeiro acesso."""
    from nucleo.db import aguardar_banco
    from nucleo.migracoes import atualizar_banco

    aguardar_banco(engine)  # espera o banco subir; se não der, explica a causa provável
    atualizar_banco(engine)
    _numerar_decisoes_antigas()
    with Session(engine) as session:
        _criar_primeira_organizacao(session)
        session.commit()
        primeira = session.exec(select(Organizacao).order_by(Organizacao.id)).first()
    if primeira is not None:
        from logos import migrar_logo_legado

        migrar_logo_legado(primeira.id)  # logo único de antes vai para a 1ª organização


# ---------------------------------------------------------------- usuários

def usuarios_com_senha_padrao() -> List[str]:
    """Usuários que ainda usam a senha '123' de versões antigas (risco na web)."""
    with nova_sessao() as s:
        return [u.username for u in s.exec(select(Usuario)).all() if _senha_confere("123", u.senha)]


def alterar_senha(username: str, nova_senha: str) -> None:
    with nova_sessao() as s:
        s_usuarios.redefinir_senha(s, username, nova_senha)


def listar_usernames() -> List[str]:
    with nova_sessao() as s:
        return [u.username for u in s.exec(select(Usuario).order_by(Usuario.username)).all()]


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
    print(f"[memoria] Senha de '{usuario}' redefinida. REMOVA a variável MEMORIA_RESETAR_SENHA agora.", flush=True)


def autenticar_usuario(username: str, senha: str) -> Optional[Usuario]:
    """None se a senha não confere OU se a organização do usuário está desativada."""
    with nova_sessao() as s:
        try:
            return s_usuarios.autenticar(s, username, senha)
        except PermissionError:
            return None


def criar_usuario(username: str, senha: str, nome_completo: str, admin: bool = False,
                  pode_criar_projetos: bool = True, criador_id: Optional[int] = None,
                  organizacao_slug: Optional[str] = None) -> Usuario:
    """Pelas telas, informe 'criador_id' (o administrador): o usuário entra na organização dele.
    Pela linha de comando: 'organizacao_slug', ou a única organização existente."""
    with nova_sessao() as s:
        ator = _ator(s, criador_id) if criador_id is not None else None
        org_id = None
        if organizacao_slug:
            org = s.exec(select(Organizacao).where(Organizacao.slug == organizacao_slug.strip())).first()
            if org is None:
                raise ValueError(f"Organização '{organizacao_slug}' não encontrada.")
            org_id = org.id
        return s_usuarios.criar(s, username, senha, nome_completo, admin, pode_criar_projetos,
                                ator=ator, organizacao_id=org_id)


# ---------------------------------------------------------------- plataforma (superadmin)

def listar_organizacoes_plataforma(solicitante_id: int) -> list:
    """[ResumoOrganizacao(organizacao, usuarios, projetos)]. Só para o superadmin."""
    with nova_sessao() as s:
        return s_organizacoes.listar(s, _ator(s, solicitante_id))


def criar_organizacao(solicitante_id: int, nome: str, admin_username: str, admin_nome: str,
                      admin_senha: str) -> Organizacao:
    """Nova organização já com o primeiro administrador. Só para o superadmin."""
    with nova_sessao() as s:
        return s_organizacoes.criar(s, _ator(s, solicitante_id), nome, admin_username, admin_nome, admin_senha)


def definir_organizacao_ativa(solicitante_id: int, organizacao_id: int, ativa: bool) -> Organizacao:
    """Suspende (ninguém dela entra) ou reativa. Só para o superadmin."""
    with nova_sessao() as s:
        return s_organizacoes.definir_ativa(s, _ator(s, solicitante_id), organizacao_id, ativa)


def listar_organizacoes() -> List[Organizacao]:
    with nova_sessao() as s:
        return list(s.exec(select(Organizacao).order_by(Organizacao.nome)).all())


def listar_usuarios(solicitante_id: Optional[int] = None) -> List[Usuario]:
    """Com 'solicitante_id' (administrador): só os usuários da organização dele."""
    with nova_sessao() as s:
        return s_usuarios.listar(s, _ator(s, solicitante_id) if solicitante_id is not None else None)


def definir_tema(usuario_id: int, tema: str) -> None:
    """Guarda o modo (claro/escuro) escolhido pelo usuário."""
    with nova_sessao() as s:
        s_usuarios.definir_tema(s, _ator(s, usuario_id), tema)


def alterar_propria_senha(usuario_id: int, senha_atual: str, nova_senha: str) -> None:
    with nova_sessao() as s:
        s_usuarios.alterar_propria_senha(s, _ator(s, usuario_id), senha_atual, nova_senha)


# ---------------------------------------------------------------- projetos e membros

def listar_projetos() -> List[Projeto]:
    with nova_sessao() as s:
        return list(s.exec(select(Projeto)).all())


def listar_projetos_do_usuario(usuario_id: int) -> List[Projeto]:
    with nova_sessao() as s:
        return s_projetos.listar_do_usuario(s, _ator(s, usuario_id))


def criar_projeto(nome: str, cliente: str, descricao: Optional[str] = None,
                  criador_id: Optional[int] = None) -> Projeto:
    with nova_sessao() as s:
        return s_projetos.criar(s, _ator(s, criador_id), nome, cliente, descricao)


def atualizar_projeto(projeto_id: int, nome: str, cliente: str, descricao: Optional[str] = None,
                      usuario_id: Optional[int] = None) -> Projeto:
    with nova_sessao() as s:
        return s_projetos.atualizar(s, _ator(s, usuario_id), projeto_id, nome, cliente, descricao)


def resumo_projeto(projeto_id: int, usuario_id: int) -> dict:
    with nova_sessao() as s:
        return s_projetos.resumo(s, _ator(s, usuario_id), projeto_id)


def excluir_projeto(projeto_id: int, usuario_id: int) -> list:
    """Apaga o projeto e tudo que pertence a ele. Devolve os caminhos dos anexos, para o
    chamador apagar os arquivos do disco depois que o banco confirmar."""
    with nova_sessao() as s:
        ator = _ator(s, usuario_id)
        nome = (s.get(Projeto, projeto_id).nome if s.get(Projeto, projeto_id) else "?")
        caminhos = s_projetos.excluir(s, ator, projeto_id)
    print(f"[memoria] Projeto '{nome}' (id {projeto_id}) excluído por '{ator.username or usuario_id}'.", flush=True)
    return caminhos


def nivel_no_projeto(usuario_id: int, projeto_id: int) -> int:
    with nova_sessao() as s:
        return _nivel_sessao(s, usuario_id, projeto_id)


def pode_no_projeto(usuario_id: int, projeto_id: int, minimo: str = "Leitor") -> bool:
    return nivel_no_projeto(usuario_id, projeto_id) >= NIVEL_PAPEL[minimo]


def listar_membros(projeto_id: int, solicitante_id: int) -> list:
    with nova_sessao() as s:
        return s_projetos.listar_membros(s, _ator(s, solicitante_id), projeto_id)


def definir_membro(projeto_id: int, username: str, papel: str, por_usuario_id: int) -> None:
    with nova_sessao() as s:
        s_projetos.definir_membro(s, _ator(s, por_usuario_id), projeto_id, username, papel)


def remover_membro(projeto_id: int, usuario_id_alvo: int, por_usuario_id: int) -> None:
    with nova_sessao() as s:
        s_projetos.remover_membro(s, _ator(s, por_usuario_id), projeto_id, usuario_id_alvo)


# ---------------------------------------------------------------- decisões

def adicionar_decisao(projeto_id, titulo, categoria, descricao, justificativa, alternativa_descartada,
                      impacto, autor, anexos, checklist, alteracao_ficha=None, usuario_id=None):
    """Registra a decisão. 'alteracao_ficha' (opcional) é (grupo, nome, unidade, novo_valor):
    a ficha é atualizada na mesma transação, ligada a esta decisão."""
    dados = DadosDecisao(
        titulo=titulo, categoria=categoria, descricao=descricao, justificativa=justificativa,
        impacto=impacto, alternativa_descartada=alternativa_descartada,
        anexos=[c for c in (anexos or "").split(",") if c],
        checklist=json.loads(checklist) if checklist else None,
        alteracao_ficha=alteracao_ficha,
    )
    with nova_sessao() as s:
        s_decisoes.criar(s, _ator(s, usuario_id, autor), projeto_id, dados, verificar_anexos=False)


def listar_decisoes_projeto(projeto_id: int) -> List[Decisao]:
    with nova_sessao() as s:
        return s_decisoes.consultar(s, projeto_id)


def buscar_decisoes_projeto(projeto_id: int, termo: str = "") -> List[Decisao]:
    """Filtra as decisões do projeto por texto (sem diferenciar maiúsculas nem acentos)."""
    with nova_sessao() as s:
        return s_decisoes.filtrar(s_decisoes.consultar(s, projeto_id), termo)


def anexo_pertence_ao_projeto(projeto_id: int, caminho: str) -> bool:
    with nova_sessao() as s:
        return s_decisoes.anexo_pertence_ao_projeto(s, projeto_id, caminho)


# ---------------------------------------------------------------- atas

def criar_reuniao(projeto_id: int, titulo: str, data_reuniao: datetime.date, participantes: str,
                  texto: str, autor: str, usuario_id: Optional[int] = None) -> Reuniao:
    with nova_sessao() as s:
        return s_atas.criar(s, _ator(s, usuario_id, autor), projeto_id, titulo, data_reuniao, participantes, texto)


def atualizar_reuniao_rascunho(reuniao_id: int, titulo: str, data_reuniao: datetime.date,
                               participantes: str, texto: str, usuario_id: Optional[int] = None) -> Reuniao:
    with nova_sessao() as s:
        return s_atas.atualizar_rascunho(s, _ator(s, usuario_id), reuniao_id, titulo, data_reuniao, participantes, texto)


def fechar_reuniao(reuniao_id: int, autor: str, usuario_id: Optional[int] = None) -> List[Decisao]:
    """Fecha a ata e cria uma decisão para cada linha [D], tudo na mesma transação."""
    with nova_sessao() as s:
        return s_atas.fechar(s, _ator(s, usuario_id, autor), reuniao_id)


def buscar_reuniao(reuniao_id: int) -> Optional[Reuniao]:
    with nova_sessao() as s:
        return s.get(Reuniao, reuniao_id)


def listar_reunioes_projeto(projeto_id: int) -> List[Reuniao]:
    with nova_sessao() as s:
        return s_atas.consultar(s, projeto_id)


def buscar_reunioes_projeto(projeto_id: int, termo: str = "") -> List[Reuniao]:
    with nova_sessao() as s:
        return s_atas.consultar(s, projeto_id, termo)


def listar_decisoes_reuniao(reuniao_id: int) -> List[Decisao]:
    with nova_sessao() as s:
        return s_decisoes.consultar_da_ata(s, reuniao_id)


def adicionar_adendo(reuniao_id: int, texto: str, autor: str, usuario_id: Optional[int] = None) -> AtaAdendo:
    with nova_sessao() as s:
        return s_atas.adicionar_adendo(s, _ator(s, usuario_id, autor), reuniao_id, texto)


def listar_adendos(reuniao_id: int) -> List[AtaAdendo]:
    with nova_sessao() as s:
        return s_atas.consultar_adendos(s, reuniao_id)


# ---------------------------------------------------------------- pendências

def criar_pendencia(projeto_id: int, titulo: str, descricao: str = "", categoria: str = "Geral",
                    responsavel: str = "", prazo: Optional[datetime.date] = None, autor: str = "",
                    usuario_id: Optional[int] = None) -> Pendencia:
    with nova_sessao() as s:
        return s_pendencias.criar(s, _ator(s, usuario_id, autor), projeto_id, titulo, descricao,
                                  categoria, responsavel, prazo)


def atualizar_pendencia(pendencia_id: int, titulo: str, descricao: str, categoria: str, responsavel: str,
                        prazo: Optional[datetime.date], usuario_id: Optional[int] = None) -> Pendencia:
    with nova_sessao() as s:
        return s_pendencias.atualizar(s, _ator(s, usuario_id), pendencia_id, titulo, descricao,
                                      categoria, responsavel, prazo)


def resolver_pendencia(pendencia_id: int, autor: str, usuario_id: Optional[int] = None,
                       decisao_id: Optional[int] = None, nova_decisao: Optional[dict] = None,
                       observacao: str = "") -> Pendencia:
    with nova_sessao() as s:
        return s_pendencias.resolver(s, _ator(s, usuario_id, autor), pendencia_id, decisao_id,
                                     nova_decisao, observacao)


def cancelar_pendencia(pendencia_id: int, motivo: str, autor: str, usuario_id: Optional[int] = None) -> Pendencia:
    with nova_sessao() as s:
        return s_pendencias.cancelar(s, _ator(s, usuario_id, autor), pendencia_id, motivo)


def reabrir_pendencia(pendencia_id: int, usuario_id: Optional[int] = None) -> Pendencia:
    with nova_sessao() as s:
        return s_pendencias.reabrir(s, _ator(s, usuario_id), pendencia_id)


def listar_pendencias(projeto_id: int, status: Optional[str] = None, termo: str = "") -> List[Pendencia]:
    with nova_sessao() as s:
        return s_pendencias.consultar(s, projeto_id, status, termo)


def contar_pendencias_abertas(projeto_id: int) -> int:
    with nova_sessao() as s:
        return s_pendencias.contar_abertas(s, projeto_id)


def listar_pendencias_reuniao(reuniao_id: int) -> List[Pendencia]:
    with nova_sessao() as s:
        return list(s.exec(select(Pendencia).where(Pendencia.reuniao_id == reuniao_id).order_by(Pendencia.numero)).all())


# ---------------------------------------------------------------- ficha do empreendimento

def listar_caracteristicas(projeto_id: int) -> List[Caracteristica]:
    with nova_sessao() as s:
        return s_ficha.consultar_caracteristicas(s, projeto_id)


def campos_da_ficha(projeto_id: int) -> list:
    with nova_sessao() as s:
        return s_ficha.consultar_campos(s, projeto_id)


def salvar_caracteristicas(projeto_id: int, itens: list, autor: str, decisao_id: Optional[int] = None,
                           reuniao_id: Optional[int] = None, usuario_id: Optional[int] = None) -> int:
    """Grava a ficha (edição direta na tela da ficha). Devolve quantos campos mudaram."""
    with nova_sessao() as s:
        return s_ficha.salvar(s, _ator(s, usuario_id, autor), projeto_id, itens, decisao_id, reuniao_id)


def listar_historico_ficha(projeto_id: int, limite: int = 200) -> List[CaracteristicaHistorico]:
    with nova_sessao() as s:
        return s_ficha.consultar_historico(s, projeto_id, limite)


def mapa_origens_ficha(projeto_id: int) -> dict:
    with nova_sessao() as s:
        return s_ficha.consultar_origens(s, projeto_id)


def alteracoes_ficha_por_decisao(projeto_id: int) -> dict:
    with nova_sessao() as s:
        return s_ficha.consultar_alteracoes_por_decisao(s, projeto_id)


def listar_alteracoes_ficha_ata(reuniao_id: int) -> List[CaracteristicaHistorico]:
    with nova_sessao() as s:
        return s_ficha.consultar_alteracoes_da_ata(s, reuniao_id)


def obter_padrao_construtivo(projeto_id: int) -> Optional[PadraoConstrutivo]:
    with nova_sessao() as s:
        return s_ficha.consultar_padrao(s, projeto_id)


def salvar_padrao_construtivo(projeto_id: int, dados: dict, usuario_id: Optional[int] = None) -> PadraoConstrutivo:
    with nova_sessao() as s:
        return s_ficha.salvar_padrao(s, _ator(s, usuario_id), projeto_id, dados)

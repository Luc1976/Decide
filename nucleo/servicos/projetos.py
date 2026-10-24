"""Projetos e membros (quem acessa cada projeto e com qual papel)."""
from typing import List, Optional, Tuple

from sqlmodel import Session, select

from models import NIVEL_PAPEL, PAPEIS
from nucleo import auditoria, planos
from nucleo.ator import Ator
from nucleo.erros import NaoEncontrado, SemPermissao
from nucleo.permissoes import LEITOR, RESPONSAVEL, exigir, organizacao_ativa
from nucleo.servicos.documentos import consultar_arquivos
from nucleo.tabelas import (
    Organizacao,
    AtaAdendo,
    Caracteristica,
    CaracteristicaHistorico,
    Decisao,
    DocumentoReferencia,
    MembroProjeto,
    PadraoConstrutivo,
    Pendencia,
    Projeto,
    Reuniao,
    Usuario,
)


def _validar(nome: str, cliente: str) -> Tuple[str, str]:
    nome, cliente = (nome or "").strip(), (cliente or "").strip()
    if not nome or not cliente:
        raise ValueError("Preencha o nome do projeto e o cliente.")
    return nome, cliente


# ---------------------------------------------------------------- leitura

def listar_do_usuario(s: Session, ator: Ator) -> List[Projeto]:
    """Só os projetos que o ator pode ver, sempre dentro da organização dele
    (o administrador vê todos os projetos DA SUA organização)."""
    usuario = s.get(Usuario, ator.id) if ator.id is not None else None
    if usuario is None or not organizacao_ativa(s, usuario.organizacao_id):
        return []
    consulta = select(Projeto).where(Projeto.organizacao_id == usuario.organizacao_id)
    if not usuario.admin:
        ids = s.exec(select(MembroProjeto.projeto_id).where(MembroProjeto.usuario_id == ator.id)).all()
        if not ids:
            return []
        consulta = consulta.where(Projeto.id.in_(ids))
    return list(s.exec(consulta.order_by(Projeto.nome)).all())


def obter(s: Session, ator: Ator, projeto_id: int) -> Projeto:
    exigir(s, ator, projeto_id, LEITOR)
    return s.get(Projeto, projeto_id)


# ---------------------------------------------------------------- gravação

def criar(s: Session, ator: Ator, nome: str, cliente: str, descricao: Optional[str] = None) -> Projeto:
    """Cria o projeto; quem cria vira Responsável por ele (admin já enxerga tudo)."""
    nome, cliente = _validar(nome, cliente)
    criador = s.get(Usuario, ator.id) if ator.id is not None else None
    if criador is None or not (criador.admin or criador.pode_criar_projetos):
        raise SemPermissao("Seu usuário não pode criar projetos.")
    if not organizacao_ativa(s, criador.organizacao_id):
        raise SemPermissao("Seu usuário não está ligado a uma organização ativa.")
    org = s.get(Organizacao, criador.organizacao_id)
    erro = planos.erro_limite_projeto(org, planos.contar_projetos(s, org.id))
    if erro:
        raise SemPermissao(erro)
    projeto = Projeto(nome=nome, cliente=cliente, descricao=(descricao or "").strip() or None,
                      organizacao_id=criador.organizacao_id)
    s.add(projeto)
    s.flush()  # gera o id
    if not criador.admin:
        s.add(MembroProjeto(projeto_id=projeto.id, usuario_id=criador.id, papel=RESPONSAVEL))
    from nucleo.servicos.documentos import criar_lista_padrao

    criar_lista_padrao(s, projeto.id)  # checklist de documentos de referência
    auditoria.registrar(s, ator, "projeto.criar", projeto.id, "projeto", projeto.id, {"nome": nome})
    s.commit()
    s.refresh(projeto)
    return projeto


def atualizar(s: Session, ator: Ator, projeto_id: int, nome: str, cliente: str,
              descricao: Optional[str] = None) -> Projeto:
    nome, cliente = _validar(nome, cliente)
    exigir(s, ator, projeto_id, RESPONSAVEL)
    projeto = s.get(Projeto, projeto_id)
    projeto.nome, projeto.cliente = nome, cliente
    projeto.descricao = (descricao or "").strip() or None
    s.add(projeto)
    auditoria.registrar(s, ator, "projeto.atualizar", projeto_id, "projeto", projeto_id)
    s.commit()
    s.refresh(projeto)
    return projeto


def resumo(s: Session, ator: Ator, projeto_id: int) -> dict:
    """Quantidades que seriam apagadas junto com o projeto (para a tela de confirmação)."""
    exigir(s, ator, projeto_id, RESPONSAVEL)
    decisoes = s.exec(select(Decisao).where(Decisao.projeto_id == projeto_id)).all()
    atas = s.exec(select(Reuniao.id).where(Reuniao.projeto_id == projeto_id)).all()
    membros = s.exec(select(MembroProjeto.id).where(MembroProjeto.projeto_id == projeto_id)).all()
    pendencias = s.exec(select(Pendencia.id).where(Pendencia.projeto_id == projeto_id)).all()
    anexos = sum(len([c for c in (d.anexos or "").split(",") if c]) for d in decisoes)
    anexos += sum(len(lista) for lista in consultar_arquivos(s, projeto_id).values())
    return {"decisoes": len(decisoes), "atas": len(atas), "anexos": anexos,
            "membros": len(membros), "pendencias": len(pendencias)}


def excluir(s: Session, ator: Ator, projeto_id: int) -> List[str]:
    """Apaga o projeto e TUDO que pertence a ele, numa única transação (ou nada é apagado).
    Devolve os caminhos dos anexos, para o chamador apagar os arquivos DEPOIS do commit."""
    exigir(s, ator, projeto_id, RESPONSAVEL)
    projeto = s.get(Projeto, projeto_id)
    decisoes = s.exec(select(Decisao).where(Decisao.projeto_id == projeto_id)).all()
    reunioes = s.exec(select(Reuniao).where(Reuniao.projeto_id == projeto_id)).all()
    caminhos = [c for d in decisoes for c in (d.anexos or "").split(",") if c]
    arquivos_docs = [a for lista in consultar_arquivos(s, projeto_id).values() for a in lista]
    caminhos += [a.chave for a in arquivos_docs]

    # A ordem importa por causa das chaves estrangeiras: primeiro quem aponta para
    # decisões/atas, depois as decisões, depois as atas e por fim o próprio projeto.
    for arquivo in arquivos_docs:  # antes dos documentos (chave estrangeira)
        s.delete(arquivo)
    s.flush()
    for tabela in (CaracteristicaHistorico, Caracteristica, PadraoConstrutivo, Pendencia, DocumentoReferencia):
        for item in s.exec(select(tabela).where(tabela.projeto_id == projeto_id)).all():
            s.delete(item)
    s.flush()
    for reuniao in reunioes:
        for adendo in s.exec(select(AtaAdendo).where(AtaAdendo.reuniao_id == reuniao.id)).all():
            s.delete(adendo)
    s.flush()
    for decisao in decisoes:
        s.delete(decisao)
    s.flush()
    for reuniao in reunioes:
        s.delete(reuniao)
    s.flush()
    for membro in s.exec(select(MembroProjeto).where(MembroProjeto.projeto_id == projeto_id)).all():
        s.delete(membro)
    s.flush()
    s.delete(projeto)
    # A auditoria fica (sem FK para o projeto): registra quem apagou e o que havia.
    auditoria.registrar(s, ator, "projeto.excluir", projeto_id, "projeto", projeto_id,
                        {"nome": projeto.nome, "decisoes": len(decisoes), "atas": len(reunioes)})
    s.commit()
    return caminhos


# ---------------------------------------------------------------- membros

def listar_membros(s: Session, ator: Ator, projeto_id: int) -> List[Tuple[Usuario, str]]:
    """[(Usuario, papel)]. Só o Responsável (ou admin) vê a lista de membros."""
    exigir(s, ator, projeto_id, RESPONSAVEL)
    resultado = []
    for m in s.exec(select(MembroProjeto).where(MembroProjeto.projeto_id == projeto_id)).all():
        u = s.get(Usuario, m.usuario_id)
        if u is not None:
            resultado.append((u, m.papel))
    resultado.sort(key=lambda par: (-NIVEL_PAPEL.get(par[1], 0), par[0].nome_completo.lower()))
    return resultado


def _membro(s: Session, projeto_id: int, usuario_id: int) -> Optional[MembroProjeto]:
    return s.exec(
        select(MembroProjeto).where(
            MembroProjeto.projeto_id == projeto_id, MembroProjeto.usuario_id == usuario_id
        )
    ).first()


def _exigir_ao_menos_um_responsavel(s: Session, projeto_id: int, alvo_id: int,
                                    novo_papel: Optional[str]) -> None:
    atual = _membro(s, projeto_id, alvo_id)
    if atual is None or atual.papel != RESPONSAVEL or novo_papel == RESPONSAVEL:
        return
    outros = s.exec(
        select(MembroProjeto.id).where(
            MembroProjeto.projeto_id == projeto_id,
            MembroProjeto.papel == RESPONSAVEL,
            MembroProjeto.usuario_id != alvo_id,
        )
    ).all()
    if not outros:
        raise ValueError("O projeto precisa ter ao menos um Responsável.")


def definir_membro(s: Session, ator: Ator, projeto_id: int, username: str, papel: str) -> None:
    """Adiciona o usuário ao projeto ou muda o papel dele. Quem executa precisa ser Responsável."""
    if papel not in PAPEIS:
        raise ValueError("Escolha o tipo de acesso.")
    exigir(s, ator, projeto_id, RESPONSAVEL)
    alvo = s.exec(select(Usuario).where(Usuario.username == (username or "").strip().lower())).first()
    # Usuário de outra organização é tratado como inexistente (não revela quem existe).
    if alvo is None or alvo.organizacao_id != s.get(Projeto, projeto_id).organizacao_id:
        raise NaoEncontrado(
            "Usuário não encontrado. O cadastro de novos usuários é feito pelo administrador."
        )
    if alvo.admin:
        raise ValueError("Administradores já têm acesso a todos os projetos.")
    _exigir_ao_menos_um_responsavel(s, projeto_id, alvo.id, papel)
    membro = _membro(s, projeto_id, alvo.id)
    if membro is None:
        s.add(MembroProjeto(projeto_id=projeto_id, usuario_id=alvo.id, papel=papel))
    else:
        membro.papel = papel
        s.add(membro)
    auditoria.registrar(s, ator, "membro.definir", projeto_id, "usuario", alvo.id,
                        {"username": alvo.username, "papel": papel})
    s.commit()


def remover_membro(s: Session, ator: Ator, projeto_id: int, usuario_id_alvo: int) -> None:
    exigir(s, ator, projeto_id, RESPONSAVEL)
    _exigir_ao_menos_um_responsavel(s, projeto_id, usuario_id_alvo, None)
    membro = _membro(s, projeto_id, usuario_id_alvo)
    if membro is not None:
        s.delete(membro)
        auditoria.registrar(s, ator, "membro.remover", projeto_id, "usuario", usuario_id_alvo)
        s.commit()

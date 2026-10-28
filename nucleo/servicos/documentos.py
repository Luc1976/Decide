"""Documentos de referência: checklist de arquivos e informações recebidas.

Cada projeto nasce com a lista padrão (ITENS_PADRAO), todos "Pendente". A equipe marca cada
item como Recebido, Pendente ou N/A (não aplicável), anota observações, anexa arquivos e
acrescenta itens próprios. Itens padrão não são excluídos (quando não se aplicam, ficam N/A);
os acrescentados podem ser excluídos.

Leitura: qualquer membro do projeto (inclusive o cliente, Leitor). Alterações: Editor ou acima.
"""
import datetime
from typing import Dict, List, Optional, Tuple

from sqlmodel import Session, func, select

from nucleo import auditoria
from nucleo.armazenamento import chave_do_projeto
from nucleo.ator import Ator
from nucleo.erros import Conflito, NaoEncontrado
from nucleo.permissoes import EDITOR, LEITOR, exigir
from nucleo.tabelas import (
    DOC_NA,
    DOC_PENDENTE,
    DOC_RECEBIDO,
    SITUACOES_DOCUMENTO,
    DocumentoArquivo,
    DocumentoReferencia,
)

ITENS_PADRAO = (
    "Levantamento topográfico",
    "Projetos preliminares",
    "Layout",
    "Relatórios de Sondagens SPT",
    "Relatório de sondagem a trado (CBR)",
    "BEP / EIR",
    "Outros",
)


def _agora() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def _validar_data(data: Optional[datetime.date]) -> datetime.date:
    """Data de recebimento: hoje se não informada; nunca no futuro."""
    data = data or datetime.date.today()
    if data > datetime.date.today():
        raise ValueError("A data de recebimento não pode ser futura.")
    return data


# ---------------------------------------------------------------- consultas sem checagem

def criar_lista_padrao(s: Session, projeto_id: int) -> None:
    """Itens padrão do projeto novo (SEM commit; vai na transação de quem cria o projeto)."""
    for ordem, nome in enumerate(ITENS_PADRAO, 1):
        s.add(DocumentoReferencia(projeto_id=projeto_id, nome=nome, padrao=True, ordem=ordem))


def consultar(s: Session, projeto_id: int) -> List[DocumentoReferencia]:
    return list(s.exec(
        select(DocumentoReferencia).where(DocumentoReferencia.projeto_id == projeto_id)
        .order_by(DocumentoReferencia.ordem, DocumentoReferencia.id)
    ).all())


def resumo(documentos: List[DocumentoReferencia]) -> Dict[str, int]:
    """{'Recebido': n, 'Pendente': n, 'N/A': n, 'total': n, 'aplicaveis': n}"""
    contagem = {situacao: 0 for situacao in SITUACOES_DOCUMENTO}
    for doc in documentos:
        contagem[doc.situacao] = contagem.get(doc.situacao, 0) + 1
    contagem["total"] = len(documentos)
    contagem["aplicaveis"] = len(documentos) - contagem[DOC_NA]
    return contagem


def consultar_arquivos(s: Session, projeto_id: int) -> Dict[int, List[DocumentoArquivo]]:
    """{documento_id: [arquivos, do mais antigo ao mais recente]} do projeto."""
    arquivos = s.exec(
        select(DocumentoArquivo)
        .join(DocumentoReferencia, DocumentoArquivo.documento_id == DocumentoReferencia.id)
        .where(DocumentoReferencia.projeto_id == projeto_id)
        .order_by(DocumentoArquivo.data_recebimento, DocumentoArquivo.id)
    ).all()
    por_doc: Dict[int, List[DocumentoArquivo]] = {}
    for a in arquivos:
        por_doc.setdefault(a.documento_id, []).append(a)
    return por_doc


def consultar_com_arquivos(s: Session, projeto_id: int) -> List[Tuple[DocumentoReferencia, List[DocumentoArquivo]]]:
    arquivos = consultar_arquivos(s, projeto_id)
    return [(d, arquivos.get(d.id, [])) for d in consultar(s, projeto_id)]


def documento_tem_anexo(s: Session, projeto_id: int, chave: str) -> bool:
    """O arquivo pertence a um documento deste projeto? (antes de gerar o link de download)"""
    return any(a.chave == chave for lista in consultar_arquivos(s, projeto_id).values() for a in lista)


def _arquivo_do_projeto(s: Session, arquivo_id: int, projeto_id: Optional[int]) -> Tuple[DocumentoArquivo, DocumentoReferencia]:
    arquivo = s.get(DocumentoArquivo, arquivo_id)
    doc = s.get(DocumentoReferencia, arquivo.documento_id) if arquivo else None
    if doc is None or (projeto_id is not None and doc.projeto_id != projeto_id):
        raise NaoEncontrado("Arquivo não encontrado.")
    return arquivo, doc


def _do_projeto(s: Session, documento_id: int, projeto_id: Optional[int]) -> DocumentoReferencia:
    doc = s.get(DocumentoReferencia, documento_id)
    if doc is None or (projeto_id is not None and doc.projeto_id != projeto_id):
        raise NaoEncontrado("Documento não encontrado.")
    return doc


# ---------------------------------------------------------------- leitura

def listar(s: Session, ator: Ator, projeto_id: int, situacao: Optional[str] = None) -> List[DocumentoReferencia]:
    exigir(s, ator, projeto_id, LEITOR)
    docs = consultar(s, projeto_id)
    return [d for d in docs if not situacao or d.situacao == situacao]


def listar_com_arquivos(s: Session, ator: Ator, projeto_id: int, situacao: Optional[str] = None):
    """[(documento, [arquivos])] para telas e PDFs."""
    exigir(s, ator, projeto_id, LEITOR)
    return [(d, a) for d, a in consultar_com_arquivos(s, projeto_id) if not situacao or d.situacao == situacao]


def resumo_do_projeto(s: Session, ator: Ator, projeto_id: int) -> Dict[str, int]:
    exigir(s, ator, projeto_id, LEITOR)
    return resumo(consultar(s, projeto_id))


def arquivo(s: Session, ator: Ator, projeto_id: int, arquivo_id: int) -> DocumentoArquivo:
    """Um arquivo, depois de checar o acesso (para gerar o link de download)."""
    exigir(s, ator, projeto_id, LEITOR)
    return _arquivo_do_projeto(s, arquivo_id, projeto_id)[0]


# ---------------------------------------------------------------- gravação

def _validar_nome(nome: str) -> str:
    nome = (nome or "").strip()
    if not nome:
        raise ValueError("Informe o nome do documento ou informação.")
    if len(nome) > 200:
        raise ValueError("Nome muito longo (máximo 200 caracteres).")
    return nome


def criar(s: Session, ator: Ator, projeto_id: int, nome: str, observacao: str = "") -> DocumentoReferencia:
    """Acrescenta um item próprio ao checklist (entra como Pendente, no fim da lista)."""
    exigir(s, ator, projeto_id, EDITOR)
    nome = _validar_nome(nome)
    ja = {d.nome.strip().casefold() for d in consultar(s, projeto_id)}
    if nome.casefold() in ja:
        raise ValueError(f"“{nome}” já está na lista.")
    ultima = s.exec(
        select(func.max(DocumentoReferencia.ordem)).where(DocumentoReferencia.projeto_id == projeto_id)
    ).one()
    doc = DocumentoReferencia(
        projeto_id=projeto_id, nome=nome, ordem=(ultima or 0) + 1, observacao=(observacao or "").strip(),
        atualizado_por=ator.nome, data_atualizacao=_agora(),
    )
    s.add(doc)
    s.flush()
    auditoria.registrar(s, ator, "documento.criar", projeto_id, "documento", doc.id, {"nome": nome})
    s.commit()
    s.refresh(doc)
    return doc


def atualizar(s: Session, ator: Ator, documento_id: int, *, situacao: Optional[str] = None,
              observacao: Optional[str] = None, nome: Optional[str] = None,
              data_recebimento: Optional[datetime.date] = None,
              projeto_id: Optional[int] = None) -> DocumentoReferencia:
    """Muda a situação, a observação, a data de recebimento e (só em itens acrescentados) o nome.
    Ao marcar Recebido, guarda a data (hoje, se não informada) e quem marcou; ao desmarcar, limpa."""
    doc = _do_projeto(s, documento_id, projeto_id)
    exigir(s, ator, doc.projeto_id, EDITOR)
    mudancas = {}
    if situacao is not None and situacao != doc.situacao:
        if situacao not in SITUACOES_DOCUMENTO:
            raise ValueError("Escolha Recebido, Pendente ou N/A.")
        mudancas["situacao"] = [doc.situacao, situacao]
        doc.situacao = situacao
        if situacao == DOC_RECEBIDO:
            doc.data_recebimento = _validar_data(data_recebimento)
            doc.recebido_por = ator.nome
        else:
            doc.data_recebimento = None
            doc.recebido_por = ""
    if data_recebimento is not None and data_recebimento != doc.data_recebimento:
        if doc.situacao != DOC_RECEBIDO:
            raise ValueError("Só itens recebidos têm data de recebimento.")
        mudancas["data_recebimento"] = [str(doc.data_recebimento), str(_validar_data(data_recebimento))]
        doc.data_recebimento = data_recebimento
    if observacao is not None and observacao.strip() != doc.observacao:
        doc.observacao = observacao.strip()
        mudancas["observacao"] = True
    if nome is not None and nome.strip() != doc.nome:
        if doc.padrao:
            raise Conflito("Os itens da lista padrão não podem ser renomeados.")
        novo = _validar_nome(nome)
        if novo.casefold() in {d.nome.strip().casefold() for d in consultar(s, doc.projeto_id) if d.id != doc.id}:
            raise ValueError(f"“{novo}” já está na lista.")
        mudancas["nome"] = [doc.nome, novo]
        doc.nome = novo
    if not mudancas:
        return doc
    doc.atualizado_por = ator.nome
    doc.data_atualizacao = _agora()
    s.add(doc)
    auditoria.registrar(s, ator, "documento.atualizar", doc.projeto_id, "documento", doc.id, mudancas)
    s.commit()
    s.refresh(doc)
    return doc


def excluir(s: Session, ator: Ator, documento_id: int, projeto_id: Optional[int] = None) -> List[str]:
    """Exclui um item ACRESCENTADO. Devolve as chaves dos anexos, para apagar os arquivos."""
    doc = _do_projeto(s, documento_id, projeto_id)
    exigir(s, ator, doc.projeto_id, EDITOR)
    if doc.padrao:
        raise Conflito("Itens da lista padrão não são excluídos: marque como N/A se não se aplicar.")
    arquivos = list(s.exec(select(DocumentoArquivo).where(DocumentoArquivo.documento_id == doc.id)).all())
    chaves = [a.chave for a in arquivos]
    auditoria.registrar(s, ator, "documento.excluir", doc.projeto_id, "documento", doc.id, {"nome": doc.nome})
    for a in arquivos:
        s.delete(a)
    s.flush()
    s.delete(doc)
    s.commit()
    return chaves


def anexar(s: Session, ator: Ator, documento_id: int, chave: str,
           data_recebimento: Optional[datetime.date] = None, nome: Optional[str] = None,
           projeto_id: Optional[int] = None, marcar_recebido: bool = True) -> DocumentoArquivo:
    """Liga um arquivo já enviado (para este projeto) ao item, com a data em que foi RECEBIDO
    (hoje, se não informada). Se o item ainda não estava recebido, passa a Recebido nessa data."""
    doc = _do_projeto(s, documento_id, projeto_id)
    exigir(s, ator, doc.projeto_id, EDITOR)
    if not chave_do_projeto(doc.projeto_id, chave):
        raise ValueError("Arquivo inválido: envie o arquivo para este projeto antes de anexar.")
    data = _validar_data(data_recebimento)
    novo = DocumentoArquivo(
        documento_id=doc.id, chave=chave, nome=(nome or chave.rsplit("/", 1)[-1]).strip(),
        data_recebimento=data, enviado_por=ator.nome, data_envio=_agora(),
    )
    s.add(novo)
    if marcar_recebido and doc.situacao != DOC_RECEBIDO:
        doc.situacao = DOC_RECEBIDO
        doc.data_recebimento = data
        doc.recebido_por = ator.nome
    doc.atualizado_por = ator.nome
    doc.data_atualizacao = _agora()
    s.add(doc)
    s.flush()
    auditoria.registrar(s, ator, "documento.anexar", doc.projeto_id, "documento", doc.id,
                        {"arquivo": novo.nome, "recebido_em": str(data)})
    s.commit()
    s.refresh(novo)
    return novo


def definir_data_arquivo(s: Session, ator: Ator, arquivo_id: int, data_recebimento: datetime.date,
                         projeto_id: Optional[int] = None) -> DocumentoArquivo:
    """Corrige a data em que um arquivo foi recebido."""
    arq, doc = _arquivo_do_projeto(s, arquivo_id, projeto_id)
    exigir(s, ator, doc.projeto_id, EDITOR)
    data = _validar_data(data_recebimento)
    if data != arq.data_recebimento:
        auditoria.registrar(s, ator, "documento.data_arquivo", doc.projeto_id, "documento", doc.id,
                            {"arquivo": arq.nome, "de": str(arq.data_recebimento), "para": str(data)})
        arq.data_recebimento = data
        s.add(arq)
        s.commit()
        s.refresh(arq)
    return arq


def remover_arquivo(s: Session, ator: Ator, arquivo_id: int, projeto_id: Optional[int] = None) -> str:
    """Tira um arquivo do item. Devolve a chave, para apagar o arquivo depois do commit."""
    arq, doc = _arquivo_do_projeto(s, arquivo_id, projeto_id)
    exigir(s, ator, doc.projeto_id, EDITOR)
    chave = arq.chave
    auditoria.registrar(s, ator, "documento.remover_arquivo", doc.projeto_id, "documento", doc.id,
                        {"arquivo": arq.nome})
    s.delete(arq)
    doc.atualizado_por = ator.nome
    doc.data_atualizacao = _agora()
    s.add(doc)
    s.commit()
    return chave


__all__ = [
    "ITENS_PADRAO", "DOC_PENDENTE", "DOC_RECEBIDO", "DOC_NA", "SITUACOES_DOCUMENTO",
    "criar_lista_padrao", "consultar", "consultar_arquivos", "consultar_com_arquivos", "resumo",
    "listar", "listar_com_arquivos", "resumo_do_projeto", "criar", "atualizar", "excluir", "anexar",
    "definir_data_arquivo", "remover_arquivo", "arquivo", "documento_tem_anexo",
]

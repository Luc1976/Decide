from typing import List, Optional

from fastapi import APIRouter

from api.deps import AtorAtual, Sessao
from api.esquemas.decisoes import LinkSaida
from api.esquemas.documentos import (
    AnexarEntrada,
    AtualizarDocumentoEntrada,
    DocumentoSaida,
    NovoDocumentoEntrada,
    ResumoDocumentosSaida,
    Situacao,
)
from nucleo.armazenamento import armazenamento_padrao
from nucleo.servicos import anexos, documentos

rotas = APIRouter(prefix="/projetos/{projeto_id}/documentos", tags=["Documentos de referência"])


@rotas.get("", response_model=List[DocumentoSaida], summary="Checklist de documentos recebidos")
def listar(projeto_id: int, ator: AtorAtual, s: Sessao, situacao: Optional[Situacao] = None):
    return [DocumentoSaida.de(d) for d in documentos.listar(s, ator, projeto_id, situacao)]


@rotas.get("/resumo", response_model=ResumoDocumentosSaida)
def resumo(projeto_id: int, ator: AtorAtual, s: Sessao):
    c = documentos.resumo_do_projeto(s, ator, projeto_id)
    return ResumoDocumentosSaida(recebidos=c["Recebido"], pendentes=c["Pendente"], nao_aplicaveis=c["N/A"],
                                 total=c["total"], aplicaveis=c["aplicaveis"])


@rotas.post("", response_model=DocumentoSaida, status_code=201, summary="Acrescentar item (Editor)")
def criar(projeto_id: int, dados: NovoDocumentoEntrada, ator: AtorAtual, s: Sessao):
    return DocumentoSaida.de(documentos.criar(s, ator, projeto_id, dados.nome, dados.observacao))


@rotas.put("/{documento_id}", response_model=DocumentoSaida, summary="Situação, observação ou nome (Editor)")
def atualizar(projeto_id: int, documento_id: int, dados: AtualizarDocumentoEntrada, ator: AtorAtual, s: Sessao):
    return DocumentoSaida.de(documentos.atualizar(
        s, ator, documento_id, situacao=dados.situacao, observacao=dados.observacao, nome=dados.nome,
        projeto_id=projeto_id,
    ))


@rotas.delete("/{documento_id}", status_code=204, summary="Excluir item acrescentado (Editor)")
def excluir(projeto_id: int, documento_id: int, ator: AtorAtual, s: Sessao):
    armazenamento_padrao().apagar(documentos.excluir(s, ator, documento_id, projeto_id))


@rotas.post("/{documento_id}/anexos", response_model=DocumentoSaida,
            summary="Ligar arquivo enviado ao item (marca como Recebido)")
def anexar(projeto_id: int, documento_id: int, dados: AnexarEntrada, ator: AtorAtual, s: Sessao):
    return DocumentoSaida.de(documentos.anexar(s, ator, documento_id, dados.chave, projeto_id))


@rotas.delete("/{documento_id}/anexos/{indice}", response_model=DocumentoSaida)
def remover_anexo(projeto_id: int, documento_id: int, indice: int, ator: AtorAtual, s: Sessao):
    doc, chave = documentos.remover_anexo(s, ator, documento_id, indice, projeto_id)
    armazenamento_padrao().apagar([chave])
    return DocumentoSaida.de(doc)


@rotas.get("/{documento_id}/anexos/{indice}/link", response_model=LinkSaida,
           summary="Link temporário para baixar o arquivo")
def link(projeto_id: int, documento_id: int, indice: int, ator: AtorAtual, s: Sessao):
    chave = documentos.anexo(s, ator, projeto_id, documento_id, indice)
    return LinkSaida(url=anexos.gerar_link(chave), expira_em_segundos=anexos.VALIDADE_LINK_S)

from typing import List, Optional

from fastapi import APIRouter
from fastapi.responses import Response

from api.deps import AtorAtual, Sessao
from api.esquemas.decisoes import LinkSaida
from api.esquemas.documentos import (
    AnexarEntrada,
    ArquivoDocumentoSaida,
    AtualizarDocumentoEntrada,
    DataArquivoEntrada,
    DocumentoSaida,
    NovoDocumentoEntrada,
    ResumoDocumentosSaida,
    Situacao,
)
from api.rotas.pdf import resposta_pdf
from nucleo.armazenamento import armazenamento_padrao
from nucleo.erros import NaoEncontrado
from nucleo.servicos import anexos, documentos, relatorios

rotas = APIRouter(prefix="/projetos/{projeto_id}/documentos", tags=["Documentos de referência"])


def _saida(s, doc) -> DocumentoSaida:
    return DocumentoSaida.de(doc, documentos.consultar_arquivos(s, doc.projeto_id).get(doc.id, []))


def _arquivo_do_documento(s, ator, projeto_id, documento_id, arquivo_id):
    arq = documentos.arquivo(s, ator, projeto_id, arquivo_id)
    if arq.documento_id != documento_id:
        raise NaoEncontrado("Arquivo não encontrado.")
    return arq


@rotas.get("", response_model=List[DocumentoSaida], summary="Checklist com os arquivos e datas de recebimento")
def listar(projeto_id: int, ator: AtorAtual, s: Sessao, situacao: Optional[Situacao] = None):
    return [DocumentoSaida.de(d, a) for d, a in documentos.listar_com_arquivos(s, ator, projeto_id, situacao)]


@rotas.get("/resumo", response_model=ResumoDocumentosSaida)
def resumo(projeto_id: int, ator: AtorAtual, s: Sessao):
    c = documentos.resumo_do_projeto(s, ator, projeto_id)
    return ResumoDocumentosSaida(recebidos=c["Recebido"], pendentes=c["Pendente"], nao_aplicaveis=c["N/A"],
                                 total=c["total"], aplicaveis=c["aplicaveis"])


@rotas.get("/relatorio.pdf", response_class=Response, tags=["Relatórios"], summary="Lista de documentos em PDF")
def relatorio_pdf(projeto_id: int, ator: AtorAtual, s: Sessao):
    nome, conteudo = relatorios.pdf_documentos(s, ator, projeto_id)
    return resposta_pdf(nome, conteudo)


@rotas.post("", response_model=DocumentoSaida, status_code=201, summary="Acrescentar item (Editor)")
def criar(projeto_id: int, dados: NovoDocumentoEntrada, ator: AtorAtual, s: Sessao):
    return _saida(s, documentos.criar(s, ator, projeto_id, dados.nome, dados.observacao))


@rotas.put("/{documento_id}", response_model=DocumentoSaida,
           summary="Situação, data de recebimento, observação ou nome (Editor)")
def atualizar(projeto_id: int, documento_id: int, dados: AtualizarDocumentoEntrada, ator: AtorAtual, s: Sessao):
    doc = documentos.atualizar(
        s, ator, documento_id, situacao=dados.situacao, observacao=dados.observacao, nome=dados.nome,
        data_recebimento=dados.data_recebimento, projeto_id=projeto_id,
    )
    return _saida(s, doc)


@rotas.delete("/{documento_id}", status_code=204, summary="Excluir item acrescentado (Editor)")
def excluir(projeto_id: int, documento_id: int, ator: AtorAtual, s: Sessao):
    armazenamento_padrao().apagar(documentos.excluir(s, ator, documento_id, projeto_id))


@rotas.post("/{documento_id}/arquivos", response_model=ArquivoDocumentoSaida, status_code=201,
            summary="Ligar arquivo enviado ao item, com a data de recebimento")
def anexar(projeto_id: int, documento_id: int, dados: AnexarEntrada, ator: AtorAtual, s: Sessao):
    return documentos.anexar(s, ator, documento_id, dados.chave, data_recebimento=dados.data_recebimento,
                             nome=dados.nome, projeto_id=projeto_id)


@rotas.put("/{documento_id}/arquivos/{arquivo_id}", response_model=ArquivoDocumentoSaida,
           summary="Corrigir a data de recebimento do arquivo (Editor)")
def data_arquivo(projeto_id: int, documento_id: int, arquivo_id: int, dados: DataArquivoEntrada,
                 ator: AtorAtual, s: Sessao):
    _arquivo_do_documento(s, ator, projeto_id, documento_id, arquivo_id)
    return documentos.definir_data_arquivo(s, ator, arquivo_id, dados.data_recebimento, projeto_id)


@rotas.delete("/{documento_id}/arquivos/{arquivo_id}", status_code=204)
def remover_arquivo(projeto_id: int, documento_id: int, arquivo_id: int, ator: AtorAtual, s: Sessao):
    _arquivo_do_documento(s, ator, projeto_id, documento_id, arquivo_id)
    armazenamento_padrao().apagar([documentos.remover_arquivo(s, ator, arquivo_id, projeto_id)])


@rotas.get("/{documento_id}/arquivos/{arquivo_id}/link", response_model=LinkSaida,
           summary="Link temporário para baixar o arquivo")
def link(projeto_id: int, documento_id: int, arquivo_id: int, ator: AtorAtual, s: Sessao):
    arq = _arquivo_do_documento(s, ator, projeto_id, documento_id, arquivo_id)
    return LinkSaida(url=anexos.gerar_link(arq.chave), expira_em_segundos=anexos.VALIDADE_LINK_S)

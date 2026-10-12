import datetime
from typing import List, Optional

from fastapi import APIRouter, File, UploadFile

from api.deps import AtorAtual, Sessao
from api.esquemas.comum import Categoria
from api.esquemas.decisoes import AnexoEnviadoSaida, DecisaoEntrada, DecisaoSaida, LinkSaida
from nucleo.armazenamento import TAMANHO_MAXIMO_ANEXO
from nucleo.servicos import anexos, decisoes
from nucleo.servicos.decisoes import DadosDecisao

rotas = APIRouter(prefix="/projetos/{projeto_id}", tags=["Decisões"])


@rotas.get("/decisoes", response_model=List[DecisaoSaida], summary="Linha do tempo (com filtros)")
def listar(projeto_id: int, ator: AtorAtual, s: Sessao, q: str = "", categoria: Optional[Categoria] = None,
           de: Optional[datetime.date] = None, ate: Optional[datetime.date] = None):
    return [DecisaoSaida.de(d) for d in decisoes.listar(s, ator, projeto_id, q, categoria, de, ate)]


@rotas.post("/decisoes", response_model=DecisaoSaida, status_code=201, summary="Registrar decisão (Editor)")
def criar(projeto_id: int, dados: DecisaoEntrada, ator: AtorAtual, s: Sessao):
    alteracao = dados.alteracao_ficha
    d = decisoes.criar(s, ator, projeto_id, DadosDecisao(
        titulo=dados.titulo, categoria=dados.categoria, descricao=dados.descricao,
        justificativa=dados.justificativa, impacto=dados.impacto,
        alternativa_descartada=dados.alternativa_descartada, data_decisao=dados.data_decisao,
        anexos=dados.anexos,
        checklist=[i.model_dump() for i in dados.checklist] if dados.checklist else None,
        alteracao_ficha=(alteracao.grupo, alteracao.nome, alteracao.unidade or "", alteracao.valor)
        if alteracao else None,
    ))
    return DecisaoSaida.de(d)


@rotas.get("/decisoes/{decisao_id}", response_model=DecisaoSaida)
def obter(projeto_id: int, decisao_id: int, ator: AtorAtual, s: Sessao):
    return DecisaoSaida.de(decisoes.obter(s, ator, projeto_id, decisao_id))


@rotas.post("/anexos", response_model=AnexoEnviadoSaida, status_code=201, tags=["Anexos"],
            summary="Enviar arquivo (antes de registrar a decisão)")
def enviar_anexo(projeto_id: int, ator: AtorAtual, s: Sessao, arquivo: UploadFile = File(...)):
    dados = arquivo.file.read(TAMANHO_MAXIMO_ANEXO + 1)
    chave = anexos.enviar(s, ator, projeto_id, arquivo.filename or "arquivo", dados)
    return AnexoEnviadoSaida(chave=chave, nome=chave.rsplit("/", 1)[-1])


@rotas.get("/decisoes/{decisao_id}/anexos/{indice}/link", response_model=LinkSaida, tags=["Anexos"],
           summary="Link temporário para baixar o anexo")
def link_anexo(projeto_id: int, decisao_id: int, indice: int, ator: AtorAtual, s: Sessao):
    return LinkSaida(url=anexos.link_do_anexo(s, ator, projeto_id, decisao_id, indice),
                     expira_em_segundos=anexos.VALIDADE_LINK_S)

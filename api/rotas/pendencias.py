from typing import List, Optional

from fastapi import APIRouter

from api.deps import AtorAtual, Sessao
from api.esquemas.comum import SituacaoPendencia
from api.esquemas.pendencias import CancelarEntrada, PendenciaEntrada, PendenciaSaida, ResolverEntrada
from nucleo.servicos import pendencias

rotas = APIRouter(prefix="/projetos/{projeto_id}/pendencias", tags=["Pendências"])


@rotas.get("", response_model=List[PendenciaSaida], summary="Abertas primeiro (prazo mais próximo antes)")
def listar(projeto_id: int, ator: AtorAtual, s: Sessao, status: Optional[SituacaoPendencia] = None, q: str = ""):
    return pendencias.listar(s, ator, projeto_id, status, q)


@rotas.post("", response_model=PendenciaSaida, status_code=201)
def criar(projeto_id: int, dados: PendenciaEntrada, ator: AtorAtual, s: Sessao):
    return pendencias.criar(s, ator, projeto_id, dados.titulo, dados.descricao, dados.categoria,
                            dados.responsavel, dados.prazo)


@rotas.get("/{pendencia_id}", response_model=PendenciaSaida)
def obter(projeto_id: int, pendencia_id: int, ator: AtorAtual, s: Sessao):
    return pendencias.obter(s, ator, projeto_id, pendencia_id)


@rotas.put("/{pendencia_id}", response_model=PendenciaSaida, summary="Editar (só em aberto)")
def atualizar(projeto_id: int, pendencia_id: int, dados: PendenciaEntrada, ator: AtorAtual, s: Sessao):
    return pendencias.atualizar(s, ator, pendencia_id, dados.titulo, dados.descricao, dados.categoria,
                                dados.responsavel, dados.prazo, projeto_id)


@rotas.post("/{pendencia_id}/resolver", response_model=PendenciaSaida,
            summary="Resolver ligando a uma decisão (existente ou nova)")
def resolver(projeto_id: int, pendencia_id: int, dados: ResolverEntrada, ator: AtorAtual, s: Sessao):
    nova = dados.nova_decisao.model_dump(exclude_none=True) if dados.nova_decisao else None
    return pendencias.resolver(s, ator, pendencia_id, dados.decisao_id, nova, dados.observacao, projeto_id)


@rotas.post("/{pendencia_id}/cancelar", response_model=PendenciaSaida)
def cancelar(projeto_id: int, pendencia_id: int, dados: CancelarEntrada, ator: AtorAtual, s: Sessao):
    return pendencias.cancelar(s, ator, pendencia_id, dados.motivo, projeto_id)


@rotas.post("/{pendencia_id}/reabrir", response_model=PendenciaSaida)
def reabrir(projeto_id: int, pendencia_id: int, ator: AtorAtual, s: Sessao):
    return pendencias.reabrir(s, ator, pendencia_id, projeto_id)

from typing import Optional

from fastapi import APIRouter

import cronograma_calculos as calc
from api.deps import AtorAtual, Sessao
from api.esquemas.cronograma import (
    CronogramaEntrada,
    CronogramaSaida,
    ItemCronogramaSaida,
    RevisaoEntrada,
    VersaoSaida,
)
from nucleo.servicos import cronograma

rotas = APIRouter(prefix="/projetos/{projeto_id}/cronograma", tags=["Cronograma"])


def _itens(dados: CronogramaEntrada):
    return [calc.Item(i.nome, i.tipo, i.inicio, i.entrega or i.inicio, i.depende_da_anterior, i.padrao)
            for i in dados.itens]


def _saida(dados: dict) -> CronogramaSaida:
    if dados["versao"] is None:
        return CronogramaSaida()
    comparar = dados["versao"].numero > 1
    desvios, removidos = calc.desvios(dados["itens"], dados["itens_v1"]) if comparar else ({}, [])
    itens = []
    for i in dados["itens"]:
        d = desvios.get(calc.chave(i.nome))
        itens.append(ItemCronogramaSaida(
            nome=i.nome, tipo=i.tipo, inicio=i.inicio, entrega=i.entrega,
            depende_da_anterior=i.depende_da_anterior, padrao=i.padrao,
            desvio_entrega_dias=d.entrega_dias if d is not None and not d.novo else None,
            novo=bool(d is not None and d.novo)))
    return CronogramaSaida(
        versao=VersaoSaida.model_validate(dados["versao"], from_attributes=True),
        itens=itens,
        versoes=[VersaoSaida.model_validate(v, from_attributes=True) for v in dados["versoes"]],
        removidos_desde_v1=removidos,
    )


@rotas.get("", response_model=CronogramaSaida,
           summary="Versão atual (ou ?versao=N) com desvios em relação à versão 1")
def obter(projeto_id: int, ator: AtorAtual, s: Sessao, versao: Optional[int] = None):
    return _saida(cronograma.obter(s, ator, projeto_id, versao))


@rotas.post("", response_model=CronogramaSaida, status_code=201, summary="Criar a versão 1 (linha de base)")
def criar(projeto_id: int, dados: CronogramaEntrada, ator: AtorAtual, s: Sessao):
    cronograma.criar(s, ator, projeto_id, _itens(dados), dados.observacao)
    return _saida(cronograma.obter(s, ator, projeto_id))


@rotas.post("/revisoes", response_model=CronogramaSaida, status_code=201,
            summary="Revisar: cria a versão seguinte, ligada a uma decisão (existente ou nova)")
def revisar(projeto_id: int, dados: RevisaoEntrada, ator: AtorAtual, s: Sessao):
    nova = dados.nova_decisao.model_dump(exclude_none=True) if dados.nova_decisao else None
    cronograma.revisar(s, ator, projeto_id, _itens(dados), dados.decisao_id, nova, dados.observacao)
    return _saida(cronograma.obter(s, ator, projeto_id))

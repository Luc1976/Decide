import datetime
from typing import List, Optional

from fastapi import APIRouter
from fastapi.responses import Response

from api.deps import AtorAtual, Sessao
from api.esquemas.comum import Categoria
from api.esquemas.ficha import (
    FichaEntrada,
    FichaGravadaSaida,
    FichaSaida,
    HistoricoFichaSaida,
)
from api.rotas.pdf import resposta_pdf
from nucleo.servicos import ficha, relatorios

rotas = APIRouter(prefix="/projetos/{projeto_id}", tags=["Ficha do empreendimento"])


@rotas.get("/ficha", response_model=FichaSaida, summary="Campos, valores e indicadores calculados")
def obter(projeto_id: int, ator: AtorAtual, s: Sessao):
    return ficha.obter(s, ator, projeto_id)


@rotas.put("/ficha", response_model=FichaGravadaSaida,
           summary="Gravar campos (só o que mudou entra no histórico; inclui os sistemas da tipologia)")
def salvar(projeto_id: int, dados: FichaEntrada, ator: AtorAtual, s: Sessao):
    itens = [(i.grupo, i.nome, i.unidade or "", i.valor) for i in dados.itens]
    return FichaGravadaSaida(campos_alterados=ficha.salvar(s, ator, projeto_id, itens))


@rotas.get("/ficha/historico", response_model=List[HistoricoFichaSaida])
def historico(projeto_id: int, ator: AtorAtual, s: Sessao, limite: int = 200):
    return [HistoricoFichaSaida.model_validate(h).model_copy(update={"origem": origem})
            for h, origem in ficha.historico(s, ator, projeto_id, min(max(limite, 1), 1000))]


@rotas.get("/relatorios/decisoes.pdf", response_class=Response, tags=["Relatórios"],
           summary="Relatório de decisões em PDF (qualquer membro, inclusive Leitor)")
def relatorio_decisoes(projeto_id: int, ator: AtorAtual, s: Sessao,
                       de: Optional[datetime.date] = None, ate: Optional[datetime.date] = None,
                       categoria: Optional[Categoria] = None,
                       incluir_ficha: bool = True, incluir_detalhes: bool = True,
                       incluir_documentos: bool = True):
    nome, conteudo, _ = relatorios.relatorio_decisoes(s, ator, projeto_id, de, ate, categoria,
                                                      incluir_ficha, incluir_detalhes, incluir_documentos)
    return resposta_pdf(nome, conteudo)

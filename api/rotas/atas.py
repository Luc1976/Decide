from typing import List

from fastapi import APIRouter
from fastapi.responses import Response

from api.deps import AtorAtual, Sessao
from api.esquemas.atas import (
    AdendoEntrada,
    AdendoSaida,
    AtaDetalhesSaida,
    AtaEntrada,
    AtaResumoSaida,
    AtaSaida,
    PreVisualizacaoSaida,
    RascunhoIASaida,
    TextoAtaEntrada,
    TranscricaoEntrada,
)
from api.esquemas.decisoes import DecisaoSaida
from api.esquemas.ficha import HistoricoFichaSaida
from api.esquemas.pendencias import PendenciaSaida
from api.rotas.pdf import resposta_pdf
from nucleo.servicos import atas, ia, relatorios

rotas = APIRouter(prefix="/projetos/{projeto_id}/atas", tags=["Atas"])


@rotas.get("", response_model=List[AtaResumoSaida], summary="Atas (Leitor só vê as fechadas)")
def listar(projeto_id: int, ator: AtorAtual, s: Sessao, q: str = ""):
    return atas.listar(s, ator, projeto_id, q)


@rotas.post("", response_model=AtaSaida, status_code=201, summary="Nova ata em rascunho (Editor)")
def criar(projeto_id: int, dados: AtaEntrada, ator: AtorAtual, s: Sessao):
    return atas.criar(s, ator, projeto_id, dados.titulo, dados.data_reuniao, dados.participantes, dados.texto)


@rotas.post("/pre-visualizar", response_model=PreVisualizacaoSaida,
            summary="O que o fechamento vai gerar ([D], [F], [P]) sem gravar")
def pre_visualizar(projeto_id: int, dados: TextoAtaEntrada, ator: AtorAtual, s: Sessao):
    return atas.pre_visualizar(s, ator, projeto_id, dados.texto)


@rotas.post("/rascunho-ia", response_model=RascunhoIASaida, tags=["IA"],
            summary="Rascunho de ata a partir da transcrição (não grava nada)")
def rascunho_ia(projeto_id: int, dados: TranscricaoEntrada, ator: AtorAtual, s: Sessao):
    r = ia.rascunho_de_ata(s, ator, projeto_id, dados.transcricao)
    return RascunhoIASaida(**r, aviso_privacidade=ia.AVISO_PRIVACIDADE)


@rotas.get("/{ata_id}", response_model=AtaDetalhesSaida, summary="Ata com o que ela gerou")
def obter(projeto_id: int, ata_id: int, ator: AtorAtual, s: Sessao):
    from nucleo.servicos.ficha import consultar_origens

    d = atas.detalhes(s, ator, ata_id, projeto_id)
    origens = consultar_origens(s, projeto_id)
    return AtaDetalhesSaida(
        ata=AtaSaida.model_validate(d["ata"]),
        decisoes=[DecisaoSaida.de(x) for x in d["decisoes"]],
        pendencias=[PendenciaSaida.model_validate(x) for x in d["pendencias"]],
        alteracoes_ficha=[HistoricoFichaSaida.model_validate(x).model_copy(update={"origem": origens.get(x.id)})
                          for x in d["alteracoes_ficha"]],
        adendos=[AdendoSaida.model_validate(x) for x in d["adendos"]],
    )


@rotas.put("/{ata_id}", response_model=AtaSaida, summary="Editar rascunho (Editor)")
def atualizar(projeto_id: int, ata_id: int, dados: AtaEntrada, ator: AtorAtual, s: Sessao):
    return atas.atualizar_rascunho(s, ator, ata_id, dados.titulo, dados.data_reuniao, dados.participantes,
                                   dados.texto, projeto_id)


@rotas.post("/{ata_id}/fechar", response_model=List[DecisaoSaida],
            summary="Fechar a ata: cria decisões, pendências e altera a ficha (Editor)")
def fechar(projeto_id: int, ata_id: int, ator: AtorAtual, s: Sessao):
    return [DecisaoSaida.de(d) for d in atas.fechar(s, ator, ata_id, projeto_id)]


@rotas.post("/{ata_id}/adendos", response_model=AdendoSaida, status_code=201,
            summary="Correção em ata fechada (Editor)")
def adendo(projeto_id: int, ata_id: int, dados: AdendoEntrada, ator: AtorAtual, s: Sessao):
    return atas.adicionar_adendo(s, ator, ata_id, dados.texto, projeto_id)


@rotas.get("/{ata_id}/pdf", response_class=Response, tags=["Relatórios"], summary="PDF da ata")
def pdf(projeto_id: int, ata_id: int, ator: AtorAtual, s: Sessao):
    nome, conteudo = relatorios.pdf_ata(s, ator, projeto_id, ata_id)
    return resposta_pdf(nome, conteudo)

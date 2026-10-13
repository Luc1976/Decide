from typing import List

from fastapi import APIRouter

from api.deps import AtorAtual, Sessao
from api.esquemas.organizacoes import (
    NovaOrganizacaoEntrada,
    OrganizacaoResumoSaida,
    OrganizacaoSaida,
    RenomearOrganizacaoEntrada,
    SituacaoOrganizacaoEntrada,
)
from nucleo.servicos import organizacoes

rotas = APIRouter(tags=["Organização"])


@rotas.get("/organizacao", response_model=OrganizacaoSaida, summary="A minha organização")
def minha(ator: AtorAtual, s: Sessao):
    return organizacoes.minha(s, ator)


@rotas.put("/organizacao", response_model=OrganizacaoSaida, summary="Renomear (administrador)")
def renomear(dados: RenomearOrganizacaoEntrada, ator: AtorAtual, s: Sessao):
    return organizacoes.renomear(s, ator, dados.nome)


# ---------------------------------------------------------------- plataforma (superadmin)

plataforma = APIRouter(prefix="/plataforma", tags=["Plataforma"])


@plataforma.get("/organizacoes", response_model=List[OrganizacaoResumoSaida],
                summary="Todas as organizações, com contagens (superadmin)")
def listar(ator: AtorAtual, s: Sessao):
    return [OrganizacaoResumoSaida(**OrganizacaoSaida.model_validate(r.organizacao).model_dump(),
                                   usuarios=r.usuarios, projetos=r.projetos)
            for r in organizacoes.listar(s, ator)]


@plataforma.post("/organizacoes", response_model=OrganizacaoSaida, status_code=201,
                 summary="Nova organização com o primeiro administrador (superadmin)")
def criar(dados: NovaOrganizacaoEntrada, ator: AtorAtual, s: Sessao):
    return organizacoes.criar(s, ator, dados.nome, dados.admin.username, dados.admin.nome_completo,
                              dados.admin.senha)


@plataforma.put("/organizacoes/{organizacao_id}/situacao", response_model=OrganizacaoSaida,
                summary="Ativar ou suspender (bloqueia o login de todos dela)")
def situacao(organizacao_id: int, dados: SituacaoOrganizacaoEntrada, ator: AtorAtual, s: Sessao):
    return organizacoes.definir_ativa(s, ator, organizacao_id, dados.ativa)

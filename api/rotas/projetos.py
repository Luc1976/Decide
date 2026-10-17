from typing import List

from fastapi import APIRouter, File, UploadFile

from api.deps import AtorAtual, Sessao
from api.esquemas.projetos import (
    AuditoriaSaida,
    MembroEntrada,
    MembroSaida,
    ProjetoEntrada,
    ProjetoSaida,
    ResumoProjetoSaida,
)
from models import NIVEL_ADMIN, NIVEL_PAPEL
from nucleo import auditoria
from nucleo.armazenamento import armazenamento_padrao
from nucleo.permissoes import RESPONSAVEL, exigir, nivel
from nucleo.servicos import projetos

rotas = APIRouter(prefix="/projetos", tags=["Projetos"])

_NOME_NIVEL = {v: k for k, v in NIVEL_PAPEL.items()} | {NIVEL_ADMIN: "Administrador"}


def _saida(s, ator, p) -> ProjetoSaida:
    saida = ProjetoSaida.model_validate(p)
    saida.meu_papel = _NOME_NIVEL.get(nivel(s, ator.id, p.id))
    return saida


@rotas.get("", response_model=List[ProjetoSaida], summary="Projetos que eu posso ver")
def listar(ator: AtorAtual, s: Sessao):
    return [_saida(s, ator, p) for p in projetos.listar_do_usuario(s, ator)]


@rotas.post("", response_model=ProjetoSaida, status_code=201, summary="Criar projeto")
def criar(dados: ProjetoEntrada, ator: AtorAtual, s: Sessao):
    return _saida(s, ator, projetos.criar(s, ator, dados.nome, dados.cliente, dados.descricao))


@rotas.get("/{projeto_id}", response_model=ProjetoSaida)
def obter(projeto_id: int, ator: AtorAtual, s: Sessao):
    return _saida(s, ator, projetos.obter(s, ator, projeto_id))


@rotas.put("/{projeto_id}", response_model=ProjetoSaida, summary="Alterar dados (Responsável)")
def atualizar(projeto_id: int, dados: ProjetoEntrada, ator: AtorAtual, s: Sessao):
    return _saida(s, ator, projetos.atualizar(s, ator, projeto_id, dados.nome, dados.cliente, dados.descricao))


@rotas.get("/{projeto_id}/resumo", response_model=ResumoProjetoSaida,
           summary="O que seria apagado junto (tela de confirmação)")
def resumo(projeto_id: int, ator: AtorAtual, s: Sessao):
    return projetos.resumo(s, ator, projeto_id)


@rotas.delete("/{projeto_id}", status_code=204, summary="Excluir projeto e tudo dele (Responsável)")
def excluir(projeto_id: int, ator: AtorAtual, s: Sessao):
    caminhos = projetos.excluir(s, ator, projeto_id)
    armazenamento_padrao().apagar(caminhos)  # só depois que o banco confirmou
    from logos import remover_logo_projeto
    remover_logo_projeto(projeto_id)


# ---------------------------------------------------------------- membros

@rotas.get("/{projeto_id}/membros", response_model=List[MembroSaida], tags=["Membros"])
def listar_membros(projeto_id: int, ator: AtorAtual, s: Sessao):
    return [MembroSaida(usuario_id=u.id, username=u.username, nome_completo=u.nome_completo, papel=papel)
            for u, papel in projetos.listar_membros(s, ator, projeto_id)]


@rotas.put("/{projeto_id}/membros", status_code=204, tags=["Membros"],
           summary="Adicionar membro ou mudar o papel (Responsável)")
def definir_membro(projeto_id: int, dados: MembroEntrada, ator: AtorAtual, s: Sessao):
    projetos.definir_membro(s, ator, projeto_id, dados.username, dados.papel)


@rotas.delete("/{projeto_id}/membros/{usuario_id}", status_code=204, tags=["Membros"])
def remover_membro(projeto_id: int, usuario_id: int, ator: AtorAtual, s: Sessao):
    projetos.remover_membro(s, ator, projeto_id, usuario_id)


# ---------------------------------------------------------------- logo do cliente e auditoria

@rotas.put("/{projeto_id}/logo", status_code=204, summary="Logo do cliente nos PDFs (Responsável)")
def enviar_logo(projeto_id: int, ator: AtorAtual, s: Sessao, arquivo: UploadFile = File(...)):
    from logos import TAMANHO_MAXIMO, salvar_logo_projeto

    exigir(s, ator, projeto_id, RESPONSAVEL)
    salvar_logo_projeto(projeto_id, arquivo.file.read(TAMANHO_MAXIMO + 1), ator)
    auditoria.registrar(s, ator, "logo.projeto", projeto_id)
    s.commit()


@rotas.delete("/{projeto_id}/logo", status_code=204)
def remover_logo(projeto_id: int, ator: AtorAtual, s: Sessao):
    from logos import remover_logo_projeto

    exigir(s, ator, projeto_id, RESPONSAVEL)
    remover_logo_projeto(projeto_id, ator)


@rotas.get("/{projeto_id}/auditoria", response_model=List[AuditoriaSaida], tags=["Auditoria"],
           summary="Quem fez o quê neste projeto (Responsável)")
def listar_auditoria(projeto_id: int, ator: AtorAtual, s: Sessao, limite: int = 200):
    exigir(s, ator, projeto_id, RESPONSAVEL)
    return auditoria.listar(s, projeto_id, min(max(limite, 1), 1000))

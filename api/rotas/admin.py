from typing import List

from fastapi import APIRouter, File, UploadFile

from api.deps import AtorAtual, Sessao
from api.esquemas.auth import NovoUsuarioEntrada, UsuarioSaida
from nucleo import auditoria
from nucleo.permissoes import exigir_admin
from nucleo.servicos import usuarios

rotas = APIRouter(prefix="/admin", tags=["Administração"])


@rotas.get("/usuarios", response_model=List[UsuarioSaida])
def listar_usuarios(ator: AtorAtual, s: Sessao):
    return usuarios.listar(s, ator)


@rotas.post("/usuarios", response_model=UsuarioSaida, status_code=201)
def criar_usuario(dados: NovoUsuarioEntrada, ator: AtorAtual, s: Sessao):
    return usuarios.criar(s, dados.username, dados.senha, dados.nome_completo, dados.admin,
                          dados.pode_criar_projetos, ator=ator)


@rotas.put("/logo-empresa", status_code=204, summary="Logo do escritório nos PDFs")
def logo_empresa(ator: AtorAtual, s: Sessao, arquivo: UploadFile = File(...)):
    from logos import TAMANHO_MAXIMO, salvar_logo_empresa

    exigir_admin(s, ator)
    salvar_logo_empresa(arquivo.file.read(TAMANHO_MAXIMO + 1), ator)
    auditoria.registrar(s, ator, "logo.empresa")
    s.commit()

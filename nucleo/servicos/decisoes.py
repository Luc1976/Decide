"""Decisões: o registro central do Decidiu.

Uma decisão registrada NÃO é editada nem apagada (é a memória do projeto). Correções
entram como nova decisão; a ficha guarda o histórico de cada valor."""
import datetime
import json
import os
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from sqlmodel import Session, select

from models import CATEGORIAS, IMPACTOS
from nucleo import auditoria, numeracao
from nucleo.armazenamento import chave_do_projeto
from nucleo.ator import Ator
from nucleo.erros import NaoEncontrado
from nucleo.marcacoes import normalizar
from nucleo.permissoes import EDITOR, LEITOR, exigir
from nucleo.servicos import ficha as servico_ficha
from nucleo.tabelas import Decisao


@dataclass
class DadosDecisao:
    titulo: str
    categoria: str
    descricao: str
    justificativa: str
    impacto: str
    alternativa_descartada: Optional[str] = None
    data_decisao: Optional[datetime.date] = None
    anexos: List[str] = field(default_factory=list)       # chaves do armazenamento
    checklist: Optional[list] = None                      # [{"texto": ..., "feito": bool}]
    alteracao_ficha: Optional[Tuple[str, str, str, str]] = None  # (grupo, nome, unidade, valor)


def anexos_da_decisao(decisao: Decisao) -> List[str]:
    return [c for c in (decisao.anexos or "").split(",") if c]


def checklist_da_decisao(decisao: Decisao) -> list:
    try:
        return json.loads(decisao.checklist) if decisao.checklist else []
    except ValueError:
        return []


def _validar(dados: DadosDecisao) -> None:
    if not (dados.titulo or "").strip():
        raise ValueError("Informe o título da decisão.")
    if dados.categoria not in CATEGORIAS:
        raise ValueError("Escolha a categoria da decisão.")
    if dados.impacto not in IMPACTOS:
        raise ValueError("Escolha o impacto da decisão.")


# ---------------------------------------------------------------- consultas sem checagem

def consultar(s: Session, projeto_id: int) -> List[Decisao]:
    return list(s.exec(
        select(Decisao).where(Decisao.projeto_id == projeto_id).order_by(Decisao.data_decisao.desc())
    ).all())


def filtrar(decisoes: List[Decisao], termo: str = "", categoria: Optional[str] = None,
            de: Optional[datetime.date] = None, ate: Optional[datetime.date] = None) -> List[Decisao]:
    """Filtra por texto (título, descrição, categoria, justificativa, alternativa, impacto,
    autor ou nome dos anexos, sem acentos), categoria e período."""
    termo_busca = normalizar(termo)
    campos = ("titulo", "categoria", "descricao", "justificativa", "alternativa_descartada", "impacto", "autor")

    def texto(d: Decisao) -> str:
        partes = [getattr(d, c) or "" for c in campos]
        partes.extend(os.path.basename(c) for c in anexos_da_decisao(d))
        return normalizar(" ".join(partes))

    return [
        d for d in decisoes
        if (not termo_busca or termo_busca in texto(d))
        and (not categoria or d.categoria == categoria)
        and (not de or d.data_decisao >= de)
        and (not ate or d.data_decisao <= ate)
    ]


def consultar_da_ata(s: Session, reuniao_id: int) -> List[Decisao]:
    return list(s.exec(select(Decisao).where(Decisao.reuniao_id == reuniao_id).order_by(Decisao.numero)).all())


# ---------------------------------------------------------------- serviços

def listar(s: Session, ator: Ator, projeto_id: int, termo: str = "", categoria: Optional[str] = None,
           de: Optional[datetime.date] = None, ate: Optional[datetime.date] = None) -> List[Decisao]:
    exigir(s, ator, projeto_id, LEITOR)
    return filtrar(consultar(s, projeto_id), termo, categoria, de, ate)


def obter(s: Session, ator: Ator, projeto_id: int, decisao_id: int) -> Decisao:
    exigir(s, ator, projeto_id, LEITOR)
    decisao = s.get(Decisao, decisao_id)
    if decisao is None or decisao.projeto_id != projeto_id:
        raise NaoEncontrado("Decisão não encontrada.")
    return decisao


def criar(s: Session, ator: Ator, projeto_id: int, dados: DadosDecisao,
          verificar_anexos: bool = True) -> Decisao:
    """Registra a decisão. Se 'alteracao_ficha' vier preenchida, a ficha é atualizada na
    mesma transação, ligada a esta decisão.

    verificar_anexos=False só para o app Flet legado, cujos anexos já estão gravados em
    caminhos antigos; pela API, todo anexo precisa ter sido enviado para ESTE projeto."""
    exigir(s, ator, projeto_id, EDITOR)
    _validar(dados)
    anexos = [a for a in (dados.anexos or []) if a]
    if verificar_anexos and any(not chave_do_projeto(projeto_id, a) for a in anexos):
        raise ValueError("Anexo inválido: envie o arquivo para este projeto antes de registrar.")

    numeracao.travar_projeto(s, projeto_id)
    decisao = Decisao(
        projeto_id=projeto_id,
        titulo=dados.titulo.strip(),
        categoria=dados.categoria,
        descricao=dados.descricao,
        justificativa=dados.justificativa,
        alternativa_descartada=dados.alternativa_descartada,
        impacto=dados.impacto,
        autor=ator.nome,
        anexos=",".join(anexos) if anexos else None,
        checklist=json.dumps(dados.checklist, ensure_ascii=False) if dados.checklist else None,
        numero=numeracao.proxima_decisao(s, projeto_id),
    )
    if dados.data_decisao:
        decisao.data_decisao = dados.data_decisao
    s.add(decisao)
    s.flush()  # gera o id
    if dados.alteracao_ficha:
        servico_ficha.aplicar(s, projeto_id, [dados.alteracao_ficha], ator.nome, decisao_id=decisao.id)
    auditoria.registrar(s, ator, "decisao.criar", projeto_id, "decisao", decisao.id,
                        {"numero": decisao.numero, "titulo": decisao.titulo})
    s.commit()
    s.refresh(decisao)
    return decisao


def anexo(s: Session, ator: Ator, projeto_id: int, decisao_id: int, indice: int) -> str:
    """Chave do anexo nº 'indice' da decisão, depois de checar o acesso."""
    decisao = obter(s, ator, projeto_id, decisao_id)
    lista = anexos_da_decisao(decisao)
    if not 0 <= indice < len(lista):
        raise NaoEncontrado("Anexo não encontrado.")
    return lista[indice]


def anexo_pertence_ao_projeto(s: Session, projeto_id: int, caminho: str) -> bool:
    """O anexo está numa decisão deste projeto? (evita abrir arquivo de outro projeto)"""
    decisoes = s.exec(
        select(Decisao).where(Decisao.projeto_id == projeto_id, Decisao.anexos != None)  # noqa: E711
    ).all()
    return any(caminho in anexos_da_decisao(d) for d in decisoes)

"""Cronograma macro do projeto: versões completas, revisão ligada a decisão.

Uma versão gravada nunca muda. A versão 1 é a linha de base (sem decisão); cada revisão
cria a versão seguinte e precisa de uma decisão do projeto (existente ou criada na mesma
gravação). Os cálculos (dependência, desvios, validação) ficam em cronograma_calculos.py.
"""
from typing import Dict, List, Optional

from sqlmodel import Session, select

import cronograma_calculos as calc
from cronograma_calculos import Item
from nucleo import auditoria, numeracao
from nucleo.ator import Ator
from nucleo.erros import Conflito
from nucleo.permissoes import EDITOR, LEITOR, exigir
from nucleo.tabelas import CronogramaItem, CronogramaVersao, Decisao


# ---------------------------------------------------------------- consultas sem checagem

def consultar_versoes(s: Session, projeto_id: int) -> List[CronogramaVersao]:
    return list(s.exec(select(CronogramaVersao).where(CronogramaVersao.projeto_id == projeto_id)
                       .order_by(CronogramaVersao.numero)).all())


def consultar_itens(s: Session, versao_id: int) -> List[Item]:
    linhas = s.exec(select(CronogramaItem).where(CronogramaItem.versao_id == versao_id)
                    .order_by(CronogramaItem.ordem, CronogramaItem.id)).all()
    return [Item(l.nome, l.tipo, l.inicio, l.entrega, l.depende_da_anterior, l.padrao) for l in linhas]


def versoes_por_decisao(s: Session, projeto_id: int) -> Dict[int, int]:
    """{decisao_id: número da versão} — para o selo "Impacta cronograma" na linha do tempo."""
    return {v.decisao_id: v.numero for v in consultar_versoes(s, projeto_id) if v.decisao_id}


def para_relatorio(s: Session, projeto_id: int) -> Optional[dict]:
    """Dados da seção "Cronograma" do relatório PDF (quem chama já checou o acesso).
    {"atual": [Item], "v1": [Item], "numero": int, "versoes": [(numero, data, autor, origem)]}
    ou None se o projeto não tem cronograma."""
    versoes = consultar_versoes(s, projeto_id)
    if not versoes:
        return None
    decisoes = {d.id: d for d in s.exec(select(Decisao).where(Decisao.projeto_id == projeto_id)).all()}
    linhas = []
    for v in versoes:
        dec = decisoes.get(v.decisao_id)
        origem = f"D-{dec.numero:03d} · {dec.titulo}" if dec is not None and dec.numero else "Linha de base"
        linhas.append((v.numero, v.criado_em, v.autor, origem))
    return {"atual": consultar_itens(s, versoes[-1].id), "v1": consultar_itens(s, versoes[0].id),
            "numero": versoes[-1].numero, "versoes": linhas}


def excluir_do_projeto(s: Session, projeto_id: int) -> None:
    """Apaga o cronograma (SEM commit; usado na exclusão do projeto)."""
    for versao in consultar_versoes(s, projeto_id):
        for item in s.exec(select(CronogramaItem).where(CronogramaItem.versao_id == versao.id)).all():
            s.delete(item)
        s.flush()
        s.delete(versao)
    s.flush()


# ---------------------------------------------------------------- leitura

def obter(s: Session, ator: Ator, projeto_id: int, numero: Optional[int] = None) -> dict:
    """{"versao", "itens", "versoes", "itens_v1"}: a versão pedida (ou a atual), seus itens,
    a lista de versões e os itens da versão 1 (referência padrão). Sem cronograma: versao None."""
    exigir(s, ator, projeto_id, LEITOR)
    versoes = consultar_versoes(s, projeto_id)
    if not versoes:
        return {"versao": None, "itens": [], "versoes": [], "itens_v1": []}
    versao = next((v for v in versoes if v.numero == numero), None) if numero else versoes[-1]
    if versao is None:
        raise ValueError(f"A versão {numero} não existe.")
    return {
        "versao": versao,
        "itens": consultar_itens(s, versao.id),
        "versoes": versoes,
        "itens_v1": consultar_itens(s, versoes[0].id),
    }


# ---------------------------------------------------------------- gravação

def _validar(itens: List[Item]) -> List[Item]:
    itens = [calc.normalizar_item(Item((i.nome or "").strip(), i.tipo, i.inicio, i.entrega,
                                       i.depende_da_anterior, i.padrao)) for i in itens]
    erros = calc.validar(itens)
    if erros:
        raise ValueError(" ".join(erros))
    return itens


def _gravar_versao(s: Session, ator: Ator, projeto_id: int, numero: int, itens: List[Item],
                   decisao_id: Optional[int], observacao: str) -> CronogramaVersao:
    versao = CronogramaVersao(projeto_id=projeto_id, numero=numero, autor=ator.nome,
                              decisao_id=decisao_id, observacao=(observacao or "").strip())
    s.add(versao)
    s.flush()
    for ordem, item in enumerate(itens):
        s.add(CronogramaItem(versao_id=versao.id, ordem=ordem, nome=item.nome, tipo=item.tipo,
                             inicio=item.inicio, entrega=item.entrega,
                             depende_da_anterior=item.depende_da_anterior, padrao=item.padrao))
    return versao


def criar(s: Session, ator: Ator, projeto_id: int, itens: List[Item], observacao: str = "") -> CronogramaVersao:
    """Versão 1, a linha de base (sem decisão). Recusa se o projeto já tem cronograma."""
    exigir(s, ator, projeto_id, EDITOR)
    itens = _validar(itens)
    numeracao.travar_projeto(s, projeto_id)
    if consultar_versoes(s, projeto_id):
        raise Conflito("Este projeto já tem cronograma. Use Revisar cronograma.")
    versao = _gravar_versao(s, ator, projeto_id, 1, itens, None, observacao)
    auditoria.registrar(s, ator, "cronograma.criar", projeto_id, "cronograma", versao.id,
                        {"numero": 1, "itens": len(itens)})
    s.commit()
    s.refresh(versao)
    return versao


def revisar(s: Session, ator: Ator, projeto_id: int, itens: List[Item], decisao_id: Optional[int] = None,
            nova_decisao: Optional[dict] = None, observacao: str = "") -> CronogramaVersao:
    """Cria a versão seguinte, ligada a uma decisão: 'decisao_id' (do mesmo projeto) ou
    'nova_decisao' {"titulo", "categoria", "impacto", "descricao", "justificativa"}, criada
    na mesma gravação. Se algo falhar, nada é gravado."""
    from nucleo.servicos import decisoes

    exigir(s, ator, projeto_id, EDITOR)
    itens = _validar(itens)
    versoes = consultar_versoes(s, projeto_id)
    if not versoes:
        raise Conflito("Crie o cronograma antes de revisá-lo.")
    if calc.iguais(itens, consultar_itens(s, versoes[-1].id)):
        raise ValueError("Nada mudou em relação à versão atual.")
    try:
        if nova_decisao is not None:
            titulo = (nova_decisao.get("titulo") or "").strip()
            descricao = (nova_decisao.get("descricao") or "").strip() or titulo
            dados = decisoes.DadosDecisao(
                titulo=titulo,
                categoria=nova_decisao.get("categoria") or "Geral",
                descricao=descricao,
                justificativa=(nova_decisao.get("justificativa") or "").strip()
                or f"Revisão do cronograma (versão {versoes[-1].numero + 1})",
                impacto=nova_decisao.get("impacto") or "Médio",
            )
            decisao_id = decisoes.criar_sem_gravar(s, ator, projeto_id, dados).id
        elif decisao_id is not None:
            decisao = s.get(Decisao, decisao_id)
            if decisao is None or decisao.projeto_id != projeto_id:
                raise ValueError("Escolha uma decisão deste projeto.")
        else:
            raise ValueError("Indique a decisão que motivou a revisão do cronograma.")
        numeracao.travar_projeto(s, projeto_id)
        numero = (consultar_versoes(s, projeto_id)[-1].numero) + 1
        versao = _gravar_versao(s, ator, projeto_id, numero, itens, decisao_id, observacao)
        auditoria.registrar(s, ator, "cronograma.revisar", projeto_id, "cronograma", versao.id,
                            {"numero": numero, "decisao_id": decisao_id})
        s.commit()
    except Exception:
        s.rollback()
        raise
    s.refresh(versao)
    return versao

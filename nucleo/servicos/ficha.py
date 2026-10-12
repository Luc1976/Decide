"""Ficha de características do empreendimento e padrão construtivo."""
import datetime
from typing import Dict, List, Optional

from sqlmodel import Session, select

from ficha_calculos import calcular_alteracoes, calcular_indicadores
from models import FICHA_GRUPOS, GRUPO_OUTRAS
from nucleo import auditoria
from nucleo.ator import Ator
from nucleo.numeracao import codigo_decisao
from nucleo.permissoes import EDITOR, LEITOR, exigir
from nucleo.tabelas import (
    CAMPOS_PADRAO,
    Caracteristica,
    CaracteristicaHistorico,
    Decisao,
    PadraoConstrutivo,
    Reuniao,
)


# ---------------------------------------------------------------- consultas sem checagem
# (usadas por outros serviços que já checaram o acesso, e pelo database.py legado)

def consultar_caracteristicas(s: Session, projeto_id: int) -> List[Caracteristica]:
    return list(s.exec(select(Caracteristica).where(Caracteristica.projeto_id == projeto_id)).all())


def consultar_campos(s: Session, projeto_id: int) -> list:
    """Todos os campos da ficha do projeto: [(grupo, nome, unidade)].
    Modelo (models.FICHA_GRUPOS) + campos personalizados já salvos."""
    campos = [(grupo, nome, unidade) for grupo, itens in FICHA_GRUPOS.items() for nome, unidade in itens]
    conhecidos = {(g, n) for g, n, _ in campos}
    for c in consultar_caracteristicas(s, projeto_id):
        if (c.grupo, c.nome) not in conhecidos:
            campos.append((c.grupo, c.nome, c.unidade or ""))
    return campos


def consultar_historico(s: Session, projeto_id: int, limite: int = 200) -> List[CaracteristicaHistorico]:
    return list(s.exec(
        select(CaracteristicaHistorico)
        .where(CaracteristicaHistorico.projeto_id == projeto_id)
        .order_by(CaracteristicaHistorico.data_registro.desc(), CaracteristicaHistorico.id.desc())
        .limit(limite)
    ).all())


def consultar_origens(s: Session, projeto_id: int) -> Dict[int, str]:
    """{id do registro do histórico: 'Decisão D-005 · Ata 04'} só para quem tem origem."""
    registros = s.exec(
        select(CaracteristicaHistorico).where(CaracteristicaHistorico.projeto_id == projeto_id)
    ).all()
    decisoes = {d.id: d for d in s.exec(select(Decisao).where(Decisao.projeto_id == projeto_id)).all()}
    atas = {r.id: r for r in s.exec(select(Reuniao).where(Reuniao.projeto_id == projeto_id)).all()}
    origens = {}
    for r in registros:
        partes = []
        dec = decisoes.get(r.decisao_id) if r.decisao_id else None
        if dec is not None and dec.numero:
            partes.append(f"Decisão {codigo_decisao(dec.numero)}")
        ata = atas.get(r.reuniao_id) if r.reuniao_id else None
        if ata is not None:
            partes.append(f"Ata {ata.numero:02d}")
        if partes:
            origens[r.id] = " · ".join(partes)
    return origens


def consultar_alteracoes_por_decisao(s: Session, projeto_id: int) -> Dict[int, List[CaracteristicaHistorico]]:
    """{decisao_id: [CaracteristicaHistorico, ...]} das decisões que mexeram na ficha."""
    registros = s.exec(
        select(CaracteristicaHistorico)
        .where(CaracteristicaHistorico.projeto_id == projeto_id,
               CaracteristicaHistorico.decisao_id != None)  # noqa: E711
        .order_by(CaracteristicaHistorico.id)
    ).all()
    por_decisao: dict = {}
    for r in registros:
        por_decisao.setdefault(r.decisao_id, []).append(r)
    return por_decisao


def consultar_alteracoes_da_ata(s: Session, reuniao_id: int) -> List[CaracteristicaHistorico]:
    return list(s.exec(
        select(CaracteristicaHistorico)
        .where(CaracteristicaHistorico.reuniao_id == reuniao_id)
        .order_by(CaracteristicaHistorico.id)
    ).all())


def consultar_padrao(s: Session, projeto_id: int) -> Optional[PadraoConstrutivo]:
    return s.exec(select(PadraoConstrutivo).where(PadraoConstrutivo.projeto_id == projeto_id)).first()


# ---------------------------------------------------------------- regra central

def aplicar(
    s: Session,
    projeto_id: int,
    itens: list,
    autor: str,
    decisao_id: Optional[int] = None,
    reuniao_id: Optional[int] = None,
) -> int:
    """Aplica na sessão (SEM commit) as mudanças da ficha e registra o histórico.
    'itens' é [(grupo, nome, unidade, valor)]. Só o que mudou é gravado.
    Campo personalizado esvaziado é removido. Devolve quantos campos mudaram.

    É chamada por: edição direta da ficha, decisão que altera a ficha e fechamento de
    ata com linhas [F] — sempre dentro da transação de quem chamou."""
    por_chave = {(c.grupo, c.nome): c for c in consultar_caracteristicas(s, projeto_id)}
    mudancas = calcular_alteracoes({chave: c.valor for chave, c in por_chave.items()}, itens)
    agora = datetime.datetime.now(datetime.timezone.utc)
    for grupo, nome, unidade, anterior, novo in mudancas:
        existente = por_chave.get((grupo, nome))
        if existente is None:
            s.add(Caracteristica(
                projeto_id=projeto_id, grupo=grupo, nome=nome, valor=novo or "",
                unidade=unidade or None, atualizado_por=autor, data_atualizacao=agora,
            ))
        elif novo is None and grupo == GRUPO_OUTRAS:
            s.delete(existente)
        else:
            existente.valor = novo or ""
            existente.atualizado_por = autor
            existente.data_atualizacao = agora
            s.add(existente)
        s.add(CaracteristicaHistorico(
            projeto_id=projeto_id, grupo=grupo, nome=nome, valor_anterior=anterior,
            valor_novo=novo, autor=autor, data_registro=agora,
            decisao_id=decisao_id, reuniao_id=reuniao_id,
        ))
    return len(mudancas)


# ---------------------------------------------------------------- serviços (com permissão)

def obter(s: Session, ator: Ator, projeto_id: int) -> dict:
    """Ficha completa para a tela: campos, valores, indicadores calculados e padrão."""
    exigir(s, ator, projeto_id, LEITOR)
    salvos = {(c.grupo, c.nome): c for c in consultar_caracteristicas(s, projeto_id)}
    campos = []
    for grupo, nome, unidade in consultar_campos(s, projeto_id):
        c = salvos.get((grupo, nome))
        campos.append({
            "grupo": grupo, "nome": nome, "unidade": unidade or None,
            "valor": c.valor if c else "",
            "atualizado_por": c.atualizado_por if c else None,
            "data_atualizacao": c.data_atualizacao if c else None,
            "personalizado": grupo == GRUPO_OUTRAS,
        })
    valores = {nome: c.valor for (_, nome), c in salvos.items()}
    indicadores = [
        {"rotulo": r, "texto": t, "alerta": a} for r, t, a in calcular_indicadores(valores)
    ]
    return {"campos": campos, "indicadores": indicadores, "padrao": consultar_padrao(s, projeto_id)}


def salvar(s: Session, ator: Ator, projeto_id: int, itens: list,
           decisao_id: Optional[int] = None, reuniao_id: Optional[int] = None) -> int:
    """Grava a ficha (edição direta). Devolve quantos campos mudaram."""
    exigir(s, ator, projeto_id, EDITOR)
    qtd = aplicar(s, projeto_id, itens, ator.nome, decisao_id, reuniao_id)
    if qtd:
        auditoria.registrar(s, ator, "ficha.salvar", projeto_id, "ficha", None, {"campos": qtd})
    s.commit()
    return qtd


def historico(s: Session, ator: Ator, projeto_id: int, limite: int = 200):
    exigir(s, ator, projeto_id, LEITOR)
    origens = consultar_origens(s, projeto_id)
    return [(h, origens.get(h.id)) for h in consultar_historico(s, projeto_id, limite)]


def obter_padrao(s: Session, ator: Ator, projeto_id: int) -> Optional[PadraoConstrutivo]:
    exigir(s, ator, projeto_id, LEITOR)
    return consultar_padrao(s, projeto_id)


def salvar_padrao(s: Session, ator: Ator, projeto_id: int, dados: dict) -> PadraoConstrutivo:
    """Grava (ou atualiza) o padrão construtivo do projeto. Um registro por projeto.
    Os campos da tipologia anterior são limpos."""
    exigir(s, ator, projeto_id, EDITOR)
    padrao = consultar_padrao(s, projeto_id) or PadraoConstrutivo(projeto_id=projeto_id, tipologia="")
    for campo in CAMPOS_PADRAO:
        if campo != "tipologia":
            setattr(padrao, campo, None)
    for campo in CAMPOS_PADRAO:
        if campo in dados:
            setattr(padrao, campo, dados[campo])
    s.add(padrao)
    auditoria.registrar(s, ator, "padrao.salvar", projeto_id, "padrao", None,
                        {"tipologia": padrao.tipologia})
    s.commit()
    s.refresh(padrao)
    return padrao

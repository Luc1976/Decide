"""Ficha de características do empreendimento.

Os campos de cada tipologia (sistemas construtivos, alturas, características) vêm de
catalogo_tipologias.py e são gravados como campos comuns da ficha, com histórico.
A tabela antiga PadraoConstrutivo não é mais usada (migração 0011)."""
import datetime
from typing import Dict, List, Optional

from sqlmodel import Session, select

import catalogo_tipologias as catalogo
from ficha_calculos import calcular_alteracoes, calcular_indicadores
from models import CAMPO_TIPOLOGIA, FICHA_GRUPOS, GRUPO_OUTRAS, GRUPO_PROGRAMA
from nucleo import auditoria
from nucleo.ator import Ator
from nucleo.numeracao import codigo_decisao
from nucleo.permissoes import EDITOR, LEITOR, exigir
from nucleo.tabelas import Caracteristica, CaracteristicaHistorico, Decisao, Reuniao


# ---------------------------------------------------------------- consultas sem checagem
# (usadas por outros serviços que já checaram o acesso, e pelo database.py legado)

def consultar_caracteristicas(s: Session, projeto_id: int) -> List[Caracteristica]:
    return list(s.exec(select(Caracteristica).where(Caracteristica.projeto_id == projeto_id)).all())


def consultar_valores(s: Session, projeto_id: int) -> Dict[tuple, str]:
    return {(c.grupo, c.nome): c.valor for c in consultar_caracteristicas(s, projeto_id)}


def consultar_campos(s: Session, projeto_id: int, simular: Optional[Dict[tuple, str]] = None) -> list:
    """Todos os campos da ficha do projeto: [(grupo, nome, unidade)].
    Modelo (models.FICHA_GRUPOS) + campos do catálogo que valem para a tipologia atual
    + campos personalizados já salvos.

    'simular' sobrepõe valores (grupo, nome) -> valor antes de decidir quais campos do
    catálogo valem: usado pela ata que troca a tipologia e já preenche a nova."""
    valores = consultar_valores(s, projeto_id)
    valores.update(simular or {})
    campos = [(grupo, nome, unidade) for grupo, itens in FICHA_GRUPOS.items() for nome, unidade in itens]
    campos += [(c.grupo, c.nome, c.unidade) for c in catalogo.campos_visiveis(valores)]
    conhecidos = {(g, n) for g, n, _ in campos}
    do_catalogo = catalogo.todos_os_campos()
    for c in consultar_caracteristicas(s, projeto_id):
        chave = (c.grupo, c.nome)
        if chave not in conhecidos and chave not in do_catalogo:
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
    Campo personalizado ou do catálogo esvaziado é removido. Devolve quantos campos mudaram.

    Tipologia: um campo do catálogo só pode receber valor se vale para a tipologia
    (ValueError, caso contrário). Os campos que deixam de valer (troca de tipologia ou do
    campo do qual dependem) são limpos aqui mesmo, com o mesmo autor e a mesma origem.

    É chamada por: edição direta da ficha, decisão que altera a ficha e fechamento de
    ata com linhas [F] — sempre dentro da transação de quem chamou."""
    por_chave = {(c.grupo, c.nome): c for c in consultar_caracteristicas(s, projeto_id)}
    atuais = {chave: c.valor for chave, c in por_chave.items()}
    itens = list(itens) + _limpezas_e_validacao(atuais, itens)
    mudancas = calcular_alteracoes(atuais, itens)
    do_catalogo = catalogo.todos_os_campos()
    agora = datetime.datetime.now(datetime.timezone.utc)
    for grupo, nome, unidade, anterior, novo in mudancas:
        existente = por_chave.get((grupo, nome))
        if existente is None:
            s.add(Caracteristica(
                projeto_id=projeto_id, grupo=grupo, nome=nome, valor=novo or "",
                unidade=unidade or None, atualizado_por=autor, data_atualizacao=agora,
            ))
        elif novo is None and (grupo == GRUPO_OUTRAS or (grupo, nome) in do_catalogo):
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


def _limpezas_e_validacao(atuais: Dict[tuple, str], itens: list) -> list:
    """Itens extras que limpam campos do catálogo que deixam de valer. Recusa valor em
    campo do catálogo que não vale para a tipologia (ex.: altura da doca em residencial)."""
    novos = {(g, n): (v or "").strip() for g, n, _, v in itens}
    combinados = dict(atuais)
    combinados.update(novos)
    visiveis = {c.chave for c in catalogo.campos_visiveis(combinados)}
    do_catalogo = catalogo.todos_os_campos()
    for chave, valor in novos.items():
        if chave in do_catalogo and valor and chave not in visiveis:
            tipologia = combinados.get((GRUPO_PROGRAMA, CAMPO_TIPOLOGIA)) or "sem tipologia"
            raise ValueError(f"O campo '{chave[1]}' não se aplica a esta ficha ({tipologia}).")
    return catalogo.campos_a_limpar(atuais, novos)


def ordenar_para_aplicar(itens: list, chave=lambda item: (item[0], item[1])) -> list:
    """Tipologia primeiro, depois os campos sem dependência, depois os dependentes:
    numa ata, '[F] Altura da doca' pode vir antes de '[F] Uso / tipologia = Industrial'."""
    do_catalogo = catalogo.todos_os_campos()

    def nivel(item):
        g, n = chave(item)
        if (g, n) == (GRUPO_PROGRAMA, CAMPO_TIPOLOGIA):
            return 0
        campo = do_catalogo.get((g, n))
        return 2 if campo is not None and campo.depende_de else 1

    return sorted(itens, key=nivel)


# ---------------------------------------------------------------- serviços (com permissão)

def obter(s: Session, ator: Ator, projeto_id: int) -> dict:
    """Ficha completa: campos (com os do catálogo da tipologia), valores e indicadores."""
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
    return {"campos": campos, "indicadores": indicadores}


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

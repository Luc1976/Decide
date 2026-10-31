"""Atas de reunião.

Ciclo: Rascunho (editável pela equipe) -> Fechada (texto congelado; correções por adendo).
Ao fechar, as linhas marcadas viram registros, tudo na mesma transação:
    [D] texto        -> decisão D-xxx
    [F] campo = valor -> alteração da ficha (ligada à última [D] acima dela)
    [P] texto        -> pendência P-xxx
"""
import datetime
from typing import List, Optional

from sqlmodel import Session, select

from ficha_calculos import analisar_alteracoes_ata
from nucleo import auditoria, numeracao
from nucleo.ator import Ator
from nucleo.erros import Conflito, NaoEncontrado
from nucleo.marcacoes import (
    FORMATO_DECISAO, erros_das_decisoes, extrair_decisoes, extrair_pendencias,
    interpretar_decisao, normalizar, titulo_da_linha,
)
from nucleo.permissoes import EDITOR, LEITOR, exigir, pode_editar
from nucleo.servicos import ficha as servico_ficha
from nucleo.tabelas import ATA_FECHADA, ATA_RASCUNHO, AtaAdendo, Decisao, Pendencia, Reuniao


def _validar_titulo(titulo: str) -> str:
    titulo = (titulo or "").strip()
    if not titulo:
        raise ValueError("Informe o título da reunião.")
    return titulo


# ---------------------------------------------------------------- consultas sem checagem

def consultar(s: Session, projeto_id: int, termo: str = "") -> List[Reuniao]:
    """Atas do projeto, mais recentes primeiro; 'termo' filtra por título, participantes,
    autor ou texto (sem acentos)."""
    atas = list(s.exec(
        select(Reuniao).where(Reuniao.projeto_id == projeto_id)
        .order_by(Reuniao.data_reuniao.desc(), Reuniao.numero.desc())
    ).all())
    termo_busca = normalizar(termo)
    if not termo_busca:
        return atas
    return [a for a in atas
            if termo_busca in normalizar(" ".join([a.titulo, a.participantes or "", a.autor, a.texto]))]


def consultar_adendos(s: Session, reuniao_id: int) -> List[AtaAdendo]:
    return list(s.exec(
        select(AtaAdendo).where(AtaAdendo.reuniao_id == reuniao_id).order_by(AtaAdendo.data_registro)
    ).all())


def _carregar(s: Session, reuniao_id: int) -> Reuniao:
    ata = s.get(Reuniao, reuniao_id)
    if ata is None:
        raise NaoEncontrado("Ata não encontrada.")
    return ata


def _da_rota(s: Session, projeto_id: Optional[int], reuniao_id: int) -> Reuniao:
    """Carrega a ata e confere que ela é do projeto informado (quando informado)."""
    ata = _carregar(s, reuniao_id)
    if projeto_id is not None and ata.projeto_id != projeto_id:
        raise NaoEncontrado("Ata não encontrada.")
    return ata


def _campos_para_texto(s: Session, projeto_id: int, texto: str) -> list:
    """Campos que as linhas [F] desta ata podem usar. Se a própria ata troca a tipologia
    (ou um sistema do qual outro depende), os campos da situação nova também valem."""
    import catalogo_tipologias as catalogo

    amplo = servico_ficha.consultar_campos(s, projeto_id)
    conhecidos = {(g, n) for g, n, _ in amplo}
    amplo += [(c.grupo, c.nome, c.unidade) for c in catalogo.todos_os_campos().values()
              if (c.grupo, c.nome) not in conhecidos]
    previstas, _ = analisar_alteracoes_ata(texto, amplo)  # 1ª leitura: só para simular
    simular = {(g, n): v for _, g, n, _, v in previstas}
    return servico_ficha.consultar_campos(s, projeto_id, simular=simular)


# ---------------------------------------------------------------- leitura

def listar(s: Session, ator: Ator, projeto_id: int, termo: str = "") -> List[Reuniao]:
    """Leitor (cliente) só vê atas fechadas: rascunho é só da equipe."""
    nivel = exigir(s, ator, projeto_id, LEITOR)
    atas = consultar(s, projeto_id, termo)
    return atas if pode_editar(nivel) else [a for a in atas if a.status == ATA_FECHADA]


def obter(s: Session, ator: Ator, reuniao_id: int, projeto_id: Optional[int] = None) -> Reuniao:
    ata = _da_rota(s, projeto_id, reuniao_id)
    nivel = exigir(s, ator, ata.projeto_id, LEITOR)
    if ata.status != ATA_FECHADA and not pode_editar(nivel):
        raise NaoEncontrado("Ata não encontrada.")
    return ata


def detalhes(s: Session, ator: Ator, reuniao_id: int, projeto_id: Optional[int] = None) -> dict:
    """Ata + o que ela gerou (decisões, pendências, alterações da ficha) + adendos."""
    ata = obter(s, ator, reuniao_id, projeto_id)
    return {
        "ata": ata,
        "decisoes": list(s.exec(select(Decisao).where(Decisao.reuniao_id == ata.id).order_by(Decisao.numero)).all()),
        "pendencias": list(s.exec(select(Pendencia).where(Pendencia.reuniao_id == ata.id).order_by(Pendencia.numero)).all()),
        "alteracoes_ficha": servico_ficha.consultar_alteracoes_da_ata(s, ata.id),
        "adendos": consultar_adendos(s, ata.id),
    }


def pre_visualizar(s: Session, ator: Ator, projeto_id: int, texto: str) -> dict:
    """O que o fechamento vai gerar, sem gravar nada (para o editor avisar antes)."""
    exigir(s, ator, projeto_id, EDITOR)
    alteracoes, erros = analisar_alteracoes_ata(texto, _campos_para_texto(s, projeto_id, texto))
    return {
        "decisoes": extrair_decisoes(texto),
        "erros_decisoes": erros_das_decisoes(texto),
        "pendencias": extrair_pendencias(texto),
        "alteracoes_ficha": [
            {"decisao_indice": i, "grupo": g, "nome": n, "unidade": u or None, "valor": v}
            for i, g, n, u, v in alteracoes
        ],
        "erros": erros,
    }


# ---------------------------------------------------------------- gravação

def criar(s: Session, ator: Ator, projeto_id: int, titulo: str, data_reuniao: datetime.date,
          participantes: Optional[str], texto: str) -> Reuniao:
    titulo = _validar_titulo(titulo)
    exigir(s, ator, projeto_id, EDITOR)
    numeracao.travar_projeto(s, projeto_id)
    ata = Reuniao(
        projeto_id=projeto_id,
        numero=numeracao.proxima_ata(s, projeto_id),
        titulo=titulo,
        data_reuniao=data_reuniao,
        participantes=(participantes or "").strip() or None,
        texto=texto or "",
        autor=ator.nome,
    )
    s.add(ata)
    s.flush()
    auditoria.registrar(s, ator, "ata.criar", projeto_id, "reuniao", ata.id, {"numero": ata.numero})
    s.commit()
    s.refresh(ata)
    return ata


def atualizar_rascunho(s: Session, ator: Ator, reuniao_id: int, titulo: str,
                       data_reuniao: datetime.date, participantes: Optional[str], texto: str,
                       projeto_id: Optional[int] = None) -> Reuniao:
    titulo = _validar_titulo(titulo)
    ata = _da_rota(s, projeto_id, reuniao_id)
    exigir(s, ator, ata.projeto_id, EDITOR)
    if ata.status != ATA_RASCUNHO:
        raise Conflito("Esta ata já foi fechada. Registre um adendo.")
    ata.titulo = titulo
    ata.data_reuniao = data_reuniao
    ata.participantes = (participantes or "").strip() or None
    ata.texto = texto or ""
    s.add(ata)
    s.commit()
    s.refresh(ata)
    return ata


def fechar(s: Session, ator: Ator, reuniao_id: int, projeto_id: Optional[int] = None) -> List[Decisao]:
    """Fecha a ata e cria decisões [D], alterações da ficha [F] e pendências [P], tudo na
    mesma transação. Se alguma linha [F] estiver errada, nada é gravado."""
    ata = _da_rota(s, projeto_id, reuniao_id)
    exigir(s, ator, ata.projeto_id, EDITOR)
    if ata.status != ATA_RASCUNHO:
        raise Conflito("Esta ata já está fechada.")
    pid = ata.projeto_id

    # Valida as linhas [F] ANTES de criar qualquer coisa.
    alteracoes_ficha, erros = analisar_alteracoes_ata(ata.texto, _campos_para_texto(s, pid, ata.texto))
    if erros:
        raise ValueError("Corrija as linhas [F]: " + "; ".join(erros) + ".")
    # Cada [D] precisa de disciplina e impacto padrão do app; senão nada é gravado.
    erros_d = erros_das_decisoes(ata.texto)
    if erros_d:
        raise ValueError(
            "Corrija as linhas [D]: " + "; ".join(erros_d) + f". Formato: {FORMATO_DECISAO}."
        )

    numeracao.travar_projeto(s, pid)
    numero = numeracao.proxima_decisao(s, pid)
    criadas = []
    for linha in extrair_decisoes(ata.texto):
        marcas = interpretar_decisao(linha)
        dec = Decisao(
            projeto_id=pid,
            titulo=titulo_da_linha(marcas["texto"]),
            categoria=marcas["categoria"],
            descricao=marcas["texto"],
            justificativa=f"Registrada na Ata {ata.numero:02d} - {ata.titulo}",
            impacto=marcas["impacto"],
            autor=ator.nome,
            data_decisao=ata.data_reuniao,
            reuniao_id=ata.id,
            numero=numero,
        )
        numero += 1
        s.add(dec)
        criadas.append(dec)

    numero_pendencia = numeracao.proxima_pendencia(s, pid)
    for linha in extrair_pendencias(ata.texto):
        s.add(Pendencia(
            projeto_id=pid, numero=numero_pendencia, titulo=titulo_da_linha(linha),
            descricao=linha, autor=ator.nome, reuniao_id=ata.id,
        ))
        numero_pendencia += 1

    s.flush()  # gera os ids das decisões
    # Tipologia antes dos campos que dependem dela (a ordem das linhas na ata não importa).
    alteracoes_ficha = servico_ficha.ordenar_para_aplicar(alteracoes_ficha, chave=lambda a: (a[1], a[2]))
    for indice, grupo, nome, unidade, valor in alteracoes_ficha:
        decisao = criadas[indice] if indice is not None else None
        servico_ficha.aplicar(
            s, pid, [(grupo, nome, unidade, valor)], ator.nome,
            decisao_id=decisao.id if decisao is not None else None, reuniao_id=ata.id,
        )

    ata.status = ATA_FECHADA
    ata.data_fechamento = datetime.datetime.now(datetime.timezone.utc)
    s.add(ata)
    auditoria.registrar(s, ator, "ata.fechar", pid, "reuniao", ata.id,
                        {"numero": ata.numero, "decisoes": len(criadas)})
    s.commit()
    for dec in criadas:
        s.refresh(dec)
    return criadas


def adicionar_adendo(s: Session, ator: Ator, reuniao_id: int, texto: str,
                     projeto_id: Optional[int] = None) -> AtaAdendo:
    texto = (texto or "").strip()
    if not texto:
        raise ValueError("Escreva o texto do adendo.")
    ata = _da_rota(s, projeto_id, reuniao_id)
    exigir(s, ator, ata.projeto_id, EDITOR)
    if ata.status != ATA_FECHADA:
        raise Conflito("Adendos só podem ser registrados em atas fechadas.")
    adendo = AtaAdendo(reuniao_id=reuniao_id, texto=texto, autor=ator.nome)
    s.add(adendo)
    s.flush()
    auditoria.registrar(s, ator, "ata.adendo", ata.projeto_id, "reuniao", ata.id)
    s.commit()
    s.refresh(adendo)
    return adendo

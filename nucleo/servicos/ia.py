"""Rascunho de ata a partir da transcrição de uma reunião (IA).

A IA nunca grava nada: devolve um texto com linhas [D]/[F]/[P] que a pessoa revisa no
editor da ata e só então fecha. Reaproveita ia_transcricao.py.

Limite mensal por organização conforme o plano (nucleo/planos.LIMITES_IA_MENSAL). O contador
sobe só quando o rascunho é gerado com sucesso pela API real."""
from typing import Callable, Optional

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

import ia_transcricao
from models import CATEGORIAS, IMPACTOS
from nucleo import planos
from nucleo.ator import Ator
from nucleo.numeracao import codigo_decisao, codigo_pendencia
from nucleo.permissoes import EDITOR, LEITOR, exigir
from nucleo.servicos import decisoes as servico_decisoes
from nucleo.servicos import ficha as servico_ficha
from nucleo.servicos import pendencias as servico_pendencias
from nucleo.tabelas import PENDENCIA_ABERTA, Organizacao, Projeto, UsoIA

ErroIA = ia_transcricao.ErroIA
AVISO_PRIVACIDADE = ia_transcricao.AVISO_PRIVACIDADE


def _mes_atual() -> str:
    return planos.agora_utc().strftime("%Y-%m")


def _quantidade_no_mes(s: Session, organizacao_id: int, ano_mes: str) -> int:
    registro = s.exec(
        select(UsoIA).where(UsoIA.organizacao_id == organizacao_id, UsoIA.ano_mes == ano_mes)
    ).first()
    return registro.quantidade if registro else 0


def _org_do_projeto(s: Session, projeto_id: int) -> Organizacao:
    projeto = s.get(Projeto, projeto_id)
    org = s.get(Organizacao, projeto.organizacao_id) if projeto and projeto.organizacao_id else None
    if org is None:
        raise ErroIA("Não foi possível identificar a organização deste projeto.")
    return org


def situacao_uso(s: Session, ator: Ator, projeto_id: int) -> dict:
    """Uso do mês da organização do projeto: {"usado", "limite" (None = sem limite), "plano"}."""
    exigir(s, ator, projeto_id, LEITOR)
    org = _org_do_projeto(s, projeto_id)
    return {
        "usado": _quantidade_no_mes(s, org.id, _mes_atual()),
        "limite": planos.limite_ia_mensal(org),
        "plano": planos.nome_do_plano(org),
    }


def verificar_cota(s: Session, ator: Ator, projeto_id: int) -> int:
    """Barra antes da chamada à IA se a organização já usou o limite do mês. Devolve o id da org."""
    exigir(s, ator, projeto_id, EDITOR)
    org = _org_do_projeto(s, projeto_id)
    limite = planos.limite_ia_mensal(org)
    if limite is None:
        return org.id
    usado = _quantidade_no_mes(s, org.id, _mes_atual())
    if usado >= limite:
        raise ErroIA(
            f"Seu plano ({planos.nome_do_plano(org)}) permite {limite} transcrições de IA por mês "
            f"e este mês já foram usadas as {usado}. Escreva a ata manualmente, aguarde o próximo mês "
            "ou troque de plano."
        )
    return org.id


def registrar_uso(s: Session, organizacao_id: int) -> None:
    """Soma uma transcrição gerada com sucesso no mês atual."""
    mes = _mes_atual()
    for _ in range(2):  # segunda tentativa se outra requisição criou o registro ao mesmo tempo
        try:
            registro = s.exec(
                select(UsoIA).where(UsoIA.organizacao_id == organizacao_id, UsoIA.ano_mes == mes)
            ).first()
            if registro is None:
                s.add(UsoIA(organizacao_id=organizacao_id, ano_mes=mes, quantidade=1))
            else:
                registro.quantidade += 1
                s.add(registro)
            s.commit()
            return
        except IntegrityError:
            s.rollback()
    # se as duas tentativas falharem, a ata já foi gerada: o uso não é perdido por isso


def rascunho_de_ata(s: Session, ator: Ator, projeto_id: int, transcricao: str,
                    chamar: Optional[Callable[[str, str], str]] = None) -> dict:
    """Devolve {"texto", "participantes", "avisos"}. Pode levar de 20 s a minutos.
    Conta no limite do plano só quando a chamada real à IA (chamar=None) dá certo."""
    organizacao_id = verificar_cota(s, ator, projeto_id)
    projeto = s.get(Projeto, projeto_id)
    recentes = [f"{codigo_decisao(d.numero)} {d.titulo}" for d in servico_decisoes.consultar(s, projeto_id)]
    abertas = [f"{codigo_pendencia(p.numero)} {p.titulo}"
               for p in servico_pendencias.consultar(s, projeto_id, status=PENDENCIA_ABERTA)]
    resultado = ia_transcricao.gerar_rascunho(
        transcricao, projeto_id, projeto.nome, CATEGORIAS, IMPACTOS,
        servico_ficha.consultar_campos(s, projeto_id), recentes, chamar, abertas,
    )
    if chamar is None:
        registrar_uso(s, organizacao_id)
    return resultado


def configurada() -> bool:
    return ia_transcricao.ia_configurada()

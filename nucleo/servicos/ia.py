"""Rascunho de ata a partir da transcrição de uma reunião (IA).

A IA nunca grava nada: devolve um texto com linhas [D]/[F]/[P] que a pessoa revisa no
editor da ata e só então fecha. Reaproveita ia_transcricao.py."""
from typing import Callable, Optional

from sqlmodel import Session

import ia_transcricao
from models import CATEGORIAS, IMPACTOS
from nucleo.ator import Ator
from nucleo.numeracao import codigo_decisao, codigo_pendencia
from nucleo.permissoes import EDITOR, exigir
from nucleo.servicos import decisoes as servico_decisoes
from nucleo.servicos import ficha as servico_ficha
from nucleo.servicos import pendencias as servico_pendencias
from nucleo.tabelas import PENDENCIA_ABERTA, Projeto

ErroIA = ia_transcricao.ErroIA
AVISO_PRIVACIDADE = ia_transcricao.AVISO_PRIVACIDADE


def rascunho_de_ata(s: Session, ator: Ator, projeto_id: int, transcricao: str,
                    chamar: Optional[Callable[[str, str], str]] = None) -> dict:
    """Devolve {"texto", "participantes", "avisos"}. Pode levar de 20 s a minutos."""
    exigir(s, ator, projeto_id, EDITOR)
    projeto = s.get(Projeto, projeto_id)
    recentes = [f"{codigo_decisao(d.numero)} {d.titulo}" for d in servico_decisoes.consultar(s, projeto_id)]
    abertas = [f"{codigo_pendencia(p.numero)} {p.titulo}"
               for p in servico_pendencias.consultar(s, projeto_id, status=PENDENCIA_ABERTA)]
    return ia_transcricao.gerar_rascunho(
        transcricao, projeto_id, projeto.nome, CATEGORIAS, IMPACTOS,
        servico_ficha.consultar_campos(s, projeto_id), recentes, chamar, abertas,
    )


def configurada() -> bool:
    return ia_transcricao.ia_configurada()

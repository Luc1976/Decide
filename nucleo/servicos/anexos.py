"""Envio e entrega de arquivos anexados às decisões."""
from typing import Optional
from urllib.parse import quote

from sqlmodel import Session

from nucleo.armazenamento import TAMANHO_MAXIMO_ANEXO, Armazenamento, armazenamento_padrao, chave_anexo
from nucleo.ator import Ator
from nucleo.permissoes import EDITOR, exigir
from nucleo.servicos import decisoes as servico_decisoes
from seguranca import assinar_token, segredo_do_servidor, verificar_token

VALIDADE_LINK_S = 300  # 5 minutos, como no app


def enviar(s: Session, ator: Ator, projeto_id: int, nome: str, dados: bytes,
           armazenamento: Optional[Armazenamento] = None) -> str:
    """Guarda o arquivo na pasta do projeto e devolve a chave, que depois vai na lista
    'anexos' da nova decisão. Só Editor ou acima."""
    exigir(s, ator, projeto_id, EDITOR)
    if not dados:
        raise ValueError("O arquivo está vazio.")
    if len(dados) > TAMANHO_MAXIMO_ANEXO:
        raise ValueError(f"O arquivo passa de {TAMANHO_MAXIMO_ANEXO // (1024 * 1024)} MB.")
    chave = chave_anexo(projeto_id, nome)
    (armazenamento or armazenamento_padrao()).salvar(chave, dados)
    return chave


def gerar_link(chave: str, validade_s: int = VALIDADE_LINK_S, prefixo: str = "/api/v1/arquivos") -> str:
    """Link assinado e temporário (o navegador baixa sem precisar mandar o token de login)."""
    token = assinar_token(segredo_do_servidor(), {"p": chave}, validade_s=validade_s)
    return f"{prefixo}/{quote(token)}"


def link_do_anexo(s: Session, ator: Ator, projeto_id: int, decisao_id: int, indice: int) -> str:
    chave = servico_decisoes.anexo(s, ator, projeto_id, decisao_id, indice)
    return gerar_link(chave)


def chave_do_link(token: str) -> Optional[str]:
    dados = verificar_token(segredo_do_servidor(), token)
    return dados.get("p") if dados else None

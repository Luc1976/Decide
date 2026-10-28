"""PDFs: relatório de decisões e ata. Reaproveita relatorio_pdf.py e ata_pdf.py.

Hoje o PDF é gerado durante a requisição (alguns segundos). Com muitos usuários, o passo
seguinte é mandar para uma fila (worker) e avisar quando ficar pronto."""
import datetime
import tempfile
from pathlib import Path
from typing import Optional, Tuple

from sqlmodel import Session

from config import NOME_APP
from nucleo.ator import Ator
from nucleo.permissoes import LEITOR, exigir
from nucleo.servicos import atas as servico_atas
from nucleo.servicos import decisoes as servico_decisoes
from nucleo.servicos import documentos as servico_documentos
from nucleo.servicos import ficha as servico_ficha
from nucleo.tabelas import Projeto


def texto_dos_filtros(de: Optional[datetime.date], ate: Optional[datetime.date],
                      categoria: Optional[str]) -> str:
    partes = []
    if de or ate:
        partes.append(f"Período: {de:%d/%m/%Y}" if de else "Período: início")
        partes[-1] += f" a {ate:%d/%m/%Y}" if ate else " em diante"
    if categoria:
        partes.append(f"Categoria: {categoria}")
    return " | ".join(partes) or "Todas as decisões"


def _logos(projeto: Projeto):
    from logos import logo_empresa, logo_projeto
    return logo_empresa(projeto.organizacao_id), logo_projeto(projeto.id)


def relatorio_decisoes(
    s: Session, ator: Ator, projeto_id: int,
    de: Optional[datetime.date] = None, ate: Optional[datetime.date] = None,
    categoria: Optional[str] = None, incluir_ficha: bool = True, incluir_detalhes: bool = True,
    incluir_documentos: bool = True,
) -> Tuple[str, bytes, int]:
    """Devolve (nome do arquivo, conteúdo do PDF, quantidade de decisões)."""
    exigir(s, ator, projeto_id, LEITOR)
    if de and ate and de > ate:
        raise ValueError("A data inicial é depois da data final.")
    decisoes = servico_decisoes.filtrar(servico_decisoes.consultar(s, projeto_id), "", categoria, de, ate)
    if not decisoes:
        raise ValueError("Nenhuma decisão encontrada para esses filtros.")
    from relatorio_pdf import gerar_relatorio_pdf, nome_do_arquivo

    projeto = s.get(Projeto, projeto_id)
    atas_por_id = {r.id: (r.numero, r.titulo) for r in servico_atas.consultar(s, projeto_id)}
    nome = nome_do_arquivo(projeto.nome, datetime.datetime.now())
    logo_empresa, logo_cliente = _logos(projeto)
    with tempfile.TemporaryDirectory() as pasta:
        destino = Path(pasta) / nome
        total = gerar_relatorio_pdf(
            destino, projeto, decisoes, atas_por_id,
            servico_ficha.consultar_alteracoes_por_decisao(s, projeto_id),
            servico_ficha.consultar_caracteristicas(s, projeto_id),
            ator.nome, texto_dos_filtros(de, ate, categoria),
            incluir_ficha, incluir_detalhes, NOME_APP, None, logo_empresa, logo_cliente,
            documentos=servico_documentos.consultar_com_arquivos(s, projeto_id) if incluir_documentos else None,
        )
        return nome, destino.read_bytes(), total


def pdf_ata(s: Session, ator: Ator, projeto_id: int, reuniao_id: int) -> Tuple[str, bytes]:
    det = servico_atas.detalhes(s, ator, reuniao_id, projeto_id)
    from ata_pdf import gerar_ata_pdf, nome_do_arquivo_ata

    ata = det["ata"]
    projeto = s.get(Projeto, ata.projeto_id)
    nome = nome_do_arquivo_ata(ata.numero, ata.titulo, datetime.date.today())
    logo_empresa, logo_cliente = _logos(projeto)
    with tempfile.TemporaryDirectory() as pasta:
        destino = Path(pasta) / nome
        gerar_ata_pdf(destino, projeto.nome, ata, det["decisoes"], det["alteracoes_ficha"],
                      det["adendos"], ator.nome, NOME_APP, logo_empresa, logo_cliente)
        return nome, destino.read_bytes()


def pdf_documentos(s: Session, ator: Ator, projeto_id: int) -> Tuple[str, bytes]:
    """PDF do checklist de documentos de referência (qualquer membro, inclusive Leitor)."""
    documentos = servico_documentos.listar_com_arquivos(s, ator, projeto_id)
    from relatorio_pdf import gerar_documentos_pdf, nome_do_arquivo_documentos

    projeto = s.get(Projeto, projeto_id)
    nome = nome_do_arquivo_documentos(projeto.nome, datetime.datetime.now())
    logo_empresa, logo_cliente = _logos(projeto)
    with tempfile.TemporaryDirectory() as pasta:
        destino = Path(pasta) / nome
        gerar_documentos_pdf(destino, projeto, documentos, ator.nome, NOME_APP, None, logo_empresa, logo_cliente)
        return nome, destino.read_bytes()

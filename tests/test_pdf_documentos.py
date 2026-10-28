"""Documentos de referência dentro dos PDFs (texto extraído com pdftotext)."""
import datetime
import shutil
import subprocess

import pytest

pytest.importorskip("reportlab")
if not shutil.which("pdftotext"):
    pytest.skip("pdftotext não instalado", allow_module_level=True)

from nucleo.armazenamento import ArmazenamentoLocal  # noqa: E402
from nucleo.ator import Ator  # noqa: E402
from nucleo.db import nova_sessao  # noqa: E402
from nucleo.servicos import anexos, decisoes, documentos, projetos, relatorios, usuarios  # noqa: E402
from nucleo.servicos.decisoes import DadosDecisao  # noqa: E402


def _texto(conteudo: bytes, tmp_path) -> str:
    arquivo = tmp_path / "x.pdf"
    arquivo.write_bytes(conteudo)
    return subprocess.run(["pdftotext", "-layout", str(arquivo), "-"], capture_output=True, text=True).stdout


@pytest.fixture
def projeto(tmp_path):
    with nova_sessao() as s:
        ana = Ator.de_usuario(usuarios.criar(s, "ana", "senha123", "Ana"))
        p = projetos.criar(s, ana, "Galpão Sinop", "Cliente X")
        decisoes.criar(s, ana, p.id, DadosDecisao("Estrutura metálica", "Estrutura", "d", "j", "Alto"))
        topo = next(d for d in documentos.listar(s, ana, p.id) if d.nome == "Levantamento topográfico")
        chave = anexos.enviar(s, ana, p.id, "topografia R01.pdf", b"%PDF", ArmazenamentoLocal(tmp_path))
        documentos.anexar(s, ana, topo.id, chave, data_recebimento=datetime.date(2026, 9, 2))
        cbr = next(d for d in documentos.listar(s, ana, p.id) if "CBR" in d.nome)
        documentos.atualizar(s, ana, cbr.id, situacao="N/A", observacao="Sem pavimento externo")
        return ana, p.id


def test_secao_no_relatorio_de_decisoes(projeto, tmp_path):
    ana, pid = projeto
    with nova_sessao() as s:
        _, conteudo, _ = relatorios.relatorio_decisoes(s, ana, pid, incluir_documentos=True)
        _, sem, _ = relatorios.relatorio_decisoes(s, ana, pid, incluir_documentos=False)
    texto = _texto(conteudo, tmp_path)
    assert "Documentos de referência" in texto
    assert "1 de 6 recebidos" in texto and "5 pendente(s)" in texto
    assert "02/09/2026" in texto and "topografia R01.pdf" in texto
    assert "Não se" in texto and "Sem pavimento externo" in texto
    assert "Estrutura metálica" in texto  # as decisões continuam lá
    assert "Documentos de referência" not in _texto(sem, tmp_path)


def test_pdf_proprio_da_lista(projeto, tmp_path):
    ana, pid = projeto
    with nova_sessao() as s:
        nome, conteudo = relatorios.pdf_documentos(s, ana, pid)
    assert nome.startswith("Documentos-referencia-Galpao-Sinop-")
    texto = _texto(conteudo, tmp_path)
    assert "Documentos de Referência" in texto and "Galpão Sinop" in texto
    assert texto.count("1 de 6 recebidos") == 1  # resumo uma vez só
    for nome_item in ("Levantamento topográfico", "Projetos preliminares", "Layout", "BEP / EIR", "Outros"):
        assert nome_item in texto
